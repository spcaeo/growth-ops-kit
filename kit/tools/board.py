#!/usr/bin/env python3
"""The work board (kit 3.0, micro kit core): every page, its stage, and a queue of jobs that agents and the machine
runner pull one at a time.

  growth board                                     every page: stage, holder, what it waits for
  growth board add <path> --type T --key K [--cluster C] [--task T5 --steps snapshot=1,dossier=2]
  growth board import <file>                       lines "<path> <type> <key> [cluster]" (ready --batch files)
  growth board show <path>                         one page with every job
  growth board jobs [--kit K] [--status S] [--page P]
  growth board refresh                             queue a refresh job for every done result within 3 days of its use-by date (claim does it too)
  growth board times                               per job kind: median wait (ready -> started) and work (started -> done)
  growth board back <path> <kind> --why "..."      send a page back: that job and every later one run again, first in line
  growth board link <job> --task T5 --step 3       tick that task step with the proof when the job is done
  growth board block|unblock|cancel <job> [--why ...]
  growth board resources                           pools, locks and who holds each slot

The life of a job: queued -> claimed (a lease; `beat` renews it; a lease that runs out puts it back in the queue) -> done
(needs a proof; frees its resource and moves the page's stage) | failed (back to queued with attempts + 1, failed for
good after 3) | blocked | cancelled. A job is claimable when every job it needs is done (or cancelled) and its resource
has a free slot; the claim is ONE write transaction, so two claimers never get the same job. Every change is an event
(job-created, job-ready, job-claimed, job-done, job-failed, job-expired, ...), which is where `board times` reads from.

Library use (the machine runner, lanes):
  add_page(path, type, key, cluster=None, task=None, steps=None) -> {"path", "created", "jobs": [ids]}
  add_job(kind, page=None, needs=(), task=None, step=None, priority=0) -> id
  claim(agent, kit=None, runner=None, lease_s=1800, project=None) -> job dict or None
  beat(job, agent, project=None) -> bool · done(job, agent, proof, project=None) -> dict · fail(job, agent, why, project=None) -> dict
  acquire(resource, holder, lease_s=1800, project=None) -> {"resource","slot","holder","until"} or None
  release(resource, holder, project=None) -> bool · held(resource=None, project=None) -> list
  renew · block / unblock / cancel / send_back · expire() · refresh_expiring() · pages_view() · jobs_view() · times()
Every function takes project (a folder; default: the current project) and, last, st=<store.Store> (default store.open(project)).
A project's growth.json can drop steps or change who runs one: "pipeline_overrides": {"drop": [kinds], "runner": {kind: runner}}.
Exit codes of the command line: 0 done, 1 refused (the reason is printed), 2 usage, 3 nothing to claim now.
"""
from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kits  # noqa: E402
import paths  # noqa: E402
import store  # noqa: E402
from boardlib import resources, schema as board_schema  # noqa: E402

KIT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_LEASE_S = resources.DEFAULT_LEASE_S
MAX_ATTEMPTS = 3
OPEN = ("queued", "claimed", "blocked", "failed")          # a job that is not finished (done or cancelled)
SATISFIED = ("done", "cancelled")


class BoardError(Exception):
    """A refusal with a plain reason (the command line prints it and exits 1)."""


def _st(st=None, project=None):
    """The store to use: `st`, else the database of `project`, else the current project's."""
    s = st or store.open(project)
    board_schema.ready(s)
    return s


def _needs(row) -> list:
    return json.loads(row["needs"] or "[]")


def _stage_of(kind: str) -> str:
    try:
        return kits.job(kind)["stage"] or kind
    except KeyError:
        return kind


def _job(db, jid) -> dict:
    """One job as a plain dict (with its page's type, key and cluster, and the state of the jobs it needs)."""
    j = db.execute("SELECT j.*, p.type AS page_type, p.key AS page_key, p.cluster AS page_cluster FROM jobs j "
                   "LEFT JOIN pages p ON p.path = j.page WHERE j.id=?", (int(jid),)).fetchone()
    if j is None:
        raise BoardError(f"no job {jid}")
    out = dict(j)
    out["needs"] = _needs(j)
    out["needs_info"] = [dict(r) for r in db.execute(
        f"SELECT id, kind, status FROM jobs WHERE id IN ({','.join('?' * len(out['needs']))}) ORDER BY id", out["needs"])] if out["needs"] else []
    out["port"] = j["slot"] if j["resource"] == "port" else None
    return out


def _jid(value) -> int:
    try:
        return int(str(value).lstrip("#Jj"))
    except ValueError:
        raise BoardError(f"'{value}' is not a job number")


# -- pages and jobs ---------------------------------------------------------------------------------------------------
def pipeline_overrides(st) -> dict:
    """This project's changes to the kit's pipelines (growth.json pipeline_overrides): {"drop": [kinds], "runner": {kind:
    runner}, "resource": {kind: resource}, "way": {kind: way}}. The kit's default stays the book's."""
    ov = resources.project_cfg(st).get("pipeline_overrides") or {}
    kits.check_overrides(ov)
    return ov


def _new_job(db, st, kind, page, needs, task=None, step=None, priority=0, refresh=0, overrides=None) -> int:
    d = kits.job(kind, overrides)
    cur = db.execute(
        "INSERT INTO jobs(kind, kit, page, way, runner, resource, needs, priority, refresh, task, step, created) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        (kind, d["kit"], page, d["way"], d["runner"], d["resource"], json.dumps(sorted(needs)), priority, refresh, task, step, store.now()))
    st.event("job-created", str(cur.lastrowid), {"kind": kind, "kit": d["kit"], "page": page, "needs": sorted(needs), "refresh": bool(refresh)})
    return cur.lastrowid


def add_page(path: str, type: str, key: str, cluster: str | None = None, task: str | None = None,
             steps: dict | None = None, project=None, st=None) -> dict:
    """Put a page on the board with one job per step of its type's pipeline (kit/kits.json). A page already on the board
    is left as it is ("created": False). `steps` maps a job kind to the step of `task` to tick when that job is done."""
    st = _st(st, project)
    path = paths.normalize(path)
    ov = pipeline_overrides(st)
    line = kits.pipeline(type, ov)                               # raises a plain KeyError for an unknown type
    with st.tx() as db:
        old = db.execute("SELECT path FROM pages WHERE path=?", (path,)).fetchone()
        if old:
            ids = [r["id"] for r in db.execute("SELECT id FROM jobs WHERE page=? ORDER BY id", (path,))]
            return {"path": path, "created": False, "jobs": ids}
        now = store.now()
        db.execute("INSERT INTO pages(path, key, type, cluster, stage, created, updated) VALUES(?,?,?,?,?,?,?)",
                   (path, key, type, cluster, _stage_of(line[0]["kind"]), now, now))
        ids, by_kind = [], {}
        for step in line:
            needs = [by_kind[k] for k in step["needs"]]
            jid = _new_job(db, st, step["kind"], path, needs, task if (steps or {}).get(step["kind"]) else None,
                           (steps or {}).get(step["kind"]), overrides=ov)
            by_kind[step["kind"]] = jid
            ids.append(jid)
        st.event("page-added", path, {"type": type, "key": key, "cluster": cluster, "jobs": len(ids)})
        return {"path": path, "created": True, "jobs": ids}


def add_job(kind: str, page: str | None = None, needs=(), task: str | None = None, step: int | None = None,
            priority: int = 0, project=None, st=None) -> int:
    """A single job outside a page's pipeline (a re-check, a shared-code change). `needs` are job ids."""
    st = _st(st, project)
    page = paths.normalize(page) if page else None
    with st.tx() as db:
        if page and not db.execute("SELECT 1 FROM pages WHERE path=?", (page,)).fetchone():
            raise BoardError(f"{page} is not on the board (growth board add {page} --type ... --key ...)")
        jid = _new_job(db, st, kind, page, [_jid(n) for n in needs], task, step, priority, overrides=pipeline_overrides(st))
        if page:
            _refresh_page(db, st, page)
        return jid


def link_task(job: int, task: str, step: int, project=None, st=None) -> None:
    st = _st(st, project)
    with st.tx() as db:
        _job(db, job)
        db.execute("UPDATE jobs SET task=?, step=? WHERE id=?", (task, int(step), _jid(job)))


def _refresh_page(db, st, path: str | None) -> None:
    """The page's stage is the stage of its first unfinished job ("done" when none is left); its holder is whoever holds
    a job of it now."""
    if not path:
        return
    rows = db.execute("SELECT kind, status, holder, refresh FROM jobs WHERE page=? ORDER BY id", (path,)).fetchall()
    first = next((r for r in rows if r["status"] not in SATISFIED and not r["refresh"]), None)
    stage = _stage_of(first["kind"]) if first else "done"
    holders = sorted({r["holder"] for r in rows if r["status"] == "claimed" and r["holder"]})
    old = db.execute("SELECT stage FROM pages WHERE path=?", (path,)).fetchone()
    db.execute("UPDATE pages SET stage=?, holder=?, updated=? WHERE path=?", (stage, ", ".join(holders) or None, store.now(), path))
    if old and old["stage"] != stage:
        st.event("page-stage", path, {"from": old["stage"], "to": stage})


def _satisfied_ids(db) -> set:
    return {r["id"] for r in db.execute("SELECT id FROM jobs WHERE status IN ('done','cancelled')")}


def _free(db, st, jid, kind: str, data: dict, who: str) -> None:
    """Take a claimed job's lease away and write the event (the caller sets the new status)."""
    resources.release_job(db, jid)
    st.event(kind, str(jid), data, who=who)


# -- the life of a job ------------------------------------------------------------------------------------------------
def _expire(db, st) -> list:
    """Claimed jobs whose lease ran out go back to the queue (no attempt counted: the agent stopped, the job did not fail);
    hand-taken locks whose time ran out are freed."""
    gone = db.execute("SELECT * FROM jobs WHERE status='claimed' AND lease_until < ?", (store.now(),)).fetchall()
    for j in gone:
        db.execute("UPDATE jobs SET status='queued', holder=NULL, lease_until=NULL, slot=NULL, started=NULL WHERE id=?", (j["id"],))
        _free(db, st, j["id"], "job-expired", {"kind": j["kind"], "page": j["page"], "was": j["holder"]}, j["holder"] or "lead")
        _refresh_page(db, st, j["page"])
    resources.expire_manual(db, st)
    return [j["id"] for j in gone]


def expire(project=None, st=None) -> list:
    """Run the lease sweep by itself (claim runs it too). Returns the ids of the jobs that went back to the queue."""
    st = _st(st, project)
    with st.tx() as db:
        return _expire(db, st)


def _public(db, jid) -> dict:
    """A job for a caller: the row, its page's path, key and type, and the resource slot it holds (the port of a build)."""
    j = _job(db, jid)
    j["path"], j["key"], j["type"], j["cluster"] = j["page"], j["page_key"], j["page_type"], j["page_cluster"]
    j["resource_slot"] = None if j["slot"] is None else ("lock" if j["slot"] == 0 else str(j["slot"]))
    return j


def claim(agent: str, kit: str | None = None, runner: str | None = None, lease_s: int | None = None, project=None, st=None):
    """Claim the next job `agent` may do, atomically. `kit` and `runner` narrow the choice: runner is "machine", "owner",
    "agent:<role>" or "agent" (any worker role). With no runner, and for runner "agent", the jobs of the owner and of the lead
    (runner agent:lead, which a project may set in pipeline_overrides) are never given out: ask for them by name. The oldest
    job comes first (a page sent back first of all). A job whose resource has no free slot is skipped, not waited for. A
    done job near its use-by date is refreshed first (refresh_expiring). Returns the job (a dict with "path", "key",
    "type" of its page and "port" when it holds one) or None."""
    st = _st(st, project)
    lease_s = int(lease_s or DEFAULT_LEASE_S)
    with st.tx() as db:
        _expire(db, st)
        _refresh_expiring(db, st)
        conds, args = ["status='queued'"], []
        if kit:
            conds.append("kit=?")
            args.append(kit)
        if runner == "agent":
            conds.append("runner LIKE 'agent:%' AND runner != 'agent:lead'")
        elif runner:
            conds.append("runner=?")
            args.append(runner)
        else:
            conds.append("runner NOT IN ('owner', 'agent:lead')")
        rows = db.execute(f"SELECT * FROM jobs WHERE {' AND '.join(conds)} ORDER BY priority DESC, id", args).fetchall()
        finished = _satisfied_ids(db)
        for j in rows:
            if any(n not in finished for n in _needs(j)):
                continue
            if j["way"] == "single" and db.execute("SELECT 1 FROM jobs WHERE kind=? AND status='claimed'", (j["kind"],)).fetchone():
                continue
            if j["kind"] == "ready" and j["page"] and db.execute(
                    "SELECT 1 FROM jobs WHERE page=? AND refresh=1 AND status IN ('queued','claimed','blocked','failed')", (j["page"],)).fetchone():
                continue                                           # READY waits while a result of the page is being renewed
            until = resources.ts(lease_s)
            ok, slot = resources.acquire(db, st, j["resource"], agent, j["id"], until)
            if not ok:
                continue
            db.execute("UPDATE jobs SET status='claimed', holder=?, lease_until=?, lease_s=?, slot=?, started=? WHERE id=?",
                       (agent, until, lease_s, slot, store.now(), j["id"]))
            _refresh_page(db, st, j["page"])
            st.event("job-claimed", str(j["id"]), {"kind": j["kind"], "page": j["page"], "lease_s": lease_s,
                                                   "resource": j["resource"], "slot": slot}, who=agent)
            return _public(db, j["id"])
    return None


def _mine(db, jid, agent, action: str):
    j = db.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone()
    if j is None:
        raise BoardError(f"no job {jid}")
    if j["status"] != "claimed":
        extra = " (its lease ran out and it went back to the queue: claim it again)" if j["status"] == "queued" else ""
        raise BoardError(f"job {jid} is {j['status']}, not claimed: cannot {action}{extra}")
    if agent and j["holder"] != agent:
        raise BoardError(f"job {jid} is held by {j['holder']}, not by {agent}: cannot {action}")
    return j


def renew(job, agent: str | None = None, lease_s: int | None = None, project=None, st=None) -> dict:
    """Renew the lease of a claimed job (its job lease and its resource lease). Refused when the job is not yours any more."""
    st, jid = _st(st, project), _jid(job)
    with st.tx() as db:
        j = _mine(db, jid, agent, "renew")
        secs = int(lease_s or j["lease_s"] or DEFAULT_LEASE_S)
        until = resources.ts(secs)
        db.execute("UPDATE jobs SET lease_until=?, lease_s=? WHERE id=?", (until, secs, jid))
        resources.renew_job(db, jid, until)
        return _job(db, jid)


def beat(job, agent: str | None = None, project=None, lease_s: int | None = None, st=None) -> bool:
    """Renew the lease; False when the job is not claimed by `agent` any more (its lease ran out and it went back)."""
    try:
        renew(job, agent, lease_s, project, st)
        return True
    except BoardError:
        return False


def proof_problem(proof: str, st) -> str | None:
    """None when the proof is meaningful: the one rule `growth tasks` and the gate use (checkpoints.proof_problem)."""
    import checkpoints
    return checkpoints.proof_problem(proof, Path(st.project))


def _tick(st, task: str, step: int, proof: str) -> None:
    """Tick the task step with the proof through the tasks command line. Outside any transaction of ours: tasks keeps its
    own writes to the database."""
    env = {**os.environ, "GROWTH_PROJECT": str(st.project), "PYTHONDONTWRITEBYTECODE": "1"}
    r = subprocess.run([sys.executable, str(Path(__file__).resolve().parent / "tasks.py"), "tick", task, str(step), "--output", proof],
                       capture_output=True, text=True, cwd=str(st.project), env=env)
    if r.returncode:
        out = (r.stdout + r.stderr).strip()
        raise BoardError(f"the proof was refused by the task list (growth tasks tick {task} {step}): "
                         f"{out.splitlines()[-1][:300] if out else 'no reason given'}")


def done(job, agent: str | None, proof: str, project=None, st=None) -> dict:
    """Finish a claimed job. A proof is required and must pass the same rule as a task step's (a file that exists, a commit,
    a journal id, a command with its output line, an address). A job linked to a task step ticks that step with the proof.
    Frees the job's resource, moves the page's stage and says which jobs are ready now ("ready": [ids])."""
    st, jid = _st(st, project), _jid(job)
    proof = (proof or "").strip()
    if not proof:
        raise BoardError("a job is done only with a proof (--proof \"...\"): name what you checked")
    why = proof_problem(proof, st)
    if why:
        raise BoardError("refused: " + why)
    j = _mine(st.conn, jid, agent, "finish")
    if j["task"] and j["step"]:
        _tick(st, j["task"], int(j["step"]), proof)
    with st.tx() as db:
        j = _mine(db, jid, agent, "finish")
        now = store.now()
        db.execute("UPDATE jobs SET status='done', proof=?, finished=?, lease_until=NULL WHERE id=?", (proof, now, jid))
        _free(db, st, jid, "job-done", {"kind": j["kind"], "page": j["page"], "proof": proof[:200], "ticked": bool(j["task"] and j["step"])},
              j["holder"] or "lead")
        ready = _announce_ready(db, st, jid, j["page"])
        _refresh_page(db, st, j["page"])
        out = _public(db, jid)
        out["ready"] = ready
        return out


def _announce_ready(db, st, finished: int, page) -> list:
    """After a job is done: the queued jobs that now have all their needs done get a job-ready event (the start of their wait)."""
    done_ids = _satisfied_ids(db)
    out = []
    for r in db.execute("SELECT * FROM jobs WHERE status='queued'"):
        needs = _needs(r)
        if finished in needs and all(n in done_ids for n in needs):
            out.append(r["id"])
            st.event("job-ready", str(r["id"]), {"kind": r["kind"], "page": r["page"]})
    return out


def fail(job, agent: str | None, why: str, project=None, st=None) -> dict:
    """The job did not work out: back to the queue with one more attempt, or failed for good after MAX_ATTEMPTS."""
    st, jid = _st(st, project), _jid(job)
    if not (why or "").strip():
        raise BoardError("say why it failed (--why \"...\")")
    with st.tx() as db:
        j = _mine(db, jid, agent, "fail")
        attempts = j["attempts"] + 1
        status = "failed" if attempts >= MAX_ATTEMPTS else "queued"
        db.execute("UPDATE jobs SET status=?, attempts=?, why=?, holder=?, lease_until=NULL, slot=NULL, started=NULL WHERE id=?",
                   (status, attempts, why.strip(), j["holder"] if status == "failed" else None, jid))
        _free(db, st, jid, "job-failed", {"kind": j["kind"], "page": j["page"], "why": why.strip()[:300],
                                          "attempts": attempts, "now": status}, j["holder"] or "lead")
        _refresh_page(db, st, j["page"])
        return _job(db, jid)


# -- slots by hand: acquire / release / held ---------------------------------------------------------------------------
def acquire(resource: str, holder: str, lease_s: int = DEFAULT_LEASE_S, project=None, st=None):
    """A slot of a pool (browser, port) or a lock (owner-preview, shared-code), outside any job: {"resource", "slot", "holder",
    "until"} (slot: the port number as text, "1".."N" for a pool, "lock" for a lock) or None when none is free. The same
    holder asking again gets its own slot back with a renewed lease. A lease that runs out frees the slot."""
    return resources.take(_st(st, project), resource, holder, int(lease_s))


def release(resource: str, holder: str, project=None, st=None) -> bool:
    """Give back the slot `holder` took with acquire. False when it held none."""
    return resources.give(_st(st, project), resource, holder)


def held(resource: str | None = None, project=None, st=None) -> list:
    """Who holds which slot now (the slots of jobs too): [{"resource", "slot", "holder", "until", "job"}]."""
    return resources.held(_st(st, project), resource)


# -- shelf life -------------------------------------------------------------------------------------------------------
REFRESH_DAYS = 3


def _utc(text: str) -> datetime:
    return datetime.fromisoformat(text)


def shelf(db) -> list:
    """The done jobs whose result expires, of pages that are not READY yet (their ready job is not done): the latest done job of
    each page and kind that has use_by_days: [{"page", "kind", "job", "expires", "days_left"}], soonest first."""
    use_by = {k: j["use_by_days"] for k, j in kits.jobs().items() if j.get("use_by_days")}
    if not use_by:
        return []
    now = datetime.now(timezone.utc)
    latest: dict = {}
    for r in db.execute(f"SELECT id, kind, page, finished FROM jobs WHERE status='done' AND page IS NOT NULL AND finished IS NOT NULL "
                        f"AND kind IN ({','.join('?' * len(use_by))}) ORDER BY finished, id", list(use_by)):
        latest[(r["page"], r["kind"])] = r
    not_ready = {r["page"] for r in db.execute("SELECT page FROM jobs WHERE kind='ready' AND status != 'done' AND page IS NOT NULL")}
    out = []
    for (page, kind), r in latest.items():
        if page not in not_ready:
            continue
        expires = _utc(r["finished"]) + timedelta(days=use_by[kind])
        out.append({"page": page, "kind": kind, "job": r["id"], "expires": expires.isoformat(),
                    "days_left": (expires - now).total_seconds() / 86400})
    return sorted(out, key=lambda x: x["days_left"])


def _refresh_expiring(db, st) -> list:
    """A done job within REFRESH_DAYS of its use-by date (or past it) on a page that is not READY yet gets a refresh job of the
    same kind (no needs; the page's stage ignores it, and READY waits for it). One open refresh per page and kind."""
    made = []
    for x in shelf(db):
        if x["days_left"] > REFRESH_DAYS:
            break
        if db.execute("SELECT 1 FROM jobs WHERE page=? AND kind=? AND refresh=1 AND status IN ('queued','claimed','blocked','failed')",
                      (x["page"], x["kind"])).fetchone():
            continue
        jid = _new_job(db, st, x["kind"], x["page"], [], refresh=1, overrides=pipeline_overrides(st))
        db.execute("UPDATE jobs SET why=? WHERE id=?", (f"refresh: the result of job {x['job']} expires {x['expires'][:10]}", jid))
        st.event("job-refresh", str(jid), {"kind": x["kind"], "page": x["page"], "old": x["job"], "expires": x["expires"]})
        made.append(jid)
    return made


def refresh_expiring(project=None, st=None) -> list:
    """Queue the refresh jobs now (claim does it too). Returns the new job ids."""
    st = _st(st, project)
    with st.tx() as db:
        return _refresh_expiring(db, st)


def shelf_view(project=None, st=None) -> list:
    st = _st(st, project)
    return shelf(st.conn)


def _simple(job, status: str, event: str, why: str | None, project, st, only=OPEN) -> dict:
    st, jid = _st(st, project), _jid(job)
    with st.tx() as db:
        j = db.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone()
        if j is None:
            raise BoardError(f"no job {jid}")
        if j["status"] not in only:
            raise BoardError(f"job {jid} is {j['status']}: cannot {event.split('-')[1]}")
        resources.release_job(db, jid)
        db.execute("UPDATE jobs SET status=?, why=?, holder=NULL, lease_until=NULL, slot=NULL, started=NULL WHERE id=?", (status, why, jid))
        st.event(event, str(jid), {"kind": j["kind"], "page": j["page"], "why": why})
        if status == "queued":
            db.execute("UPDATE jobs SET attempts=0 WHERE id=?", (jid,))
        if status == "queued" and all(n in _satisfied_ids(db) for n in _needs(j)):
            st.event("job-ready", str(jid), {"kind": j["kind"], "page": j["page"]})
        _refresh_page(db, st, j["page"])
        return _job(db, jid)


def block(job, why: str, project=None, st=None) -> dict:
    """Park a job (for example it waits for the owner's answer); nothing that needs it runs."""
    return _simple(job, "blocked", "job-blocked", why, project, st, only=("queued", "claimed"))


def unblock(job, project=None, st=None) -> dict:
    return _simple(job, "queued", "job-unblocked", None, project, st, only=("blocked", "failed"))


def cancel(job, why: str | None = None, project=None, st=None) -> dict:
    """The step is not needed (it counts as done for the jobs that need it)."""
    return _simple(job, "cancelled", "job-cancelled", why, project, st, only=OPEN)


def send_back(path: str, kind: str, why: str, project=None, st=None) -> list:
    """A review (or the owner) sent the page back: the job of `kind` and every job after it in the page's line run again,
    ahead of everything else in the queue. Returns the ids reopened."""
    st = _st(st, project)
    path = paths.normalize(path)
    if not (why or "").strip():
        raise BoardError("say why the page goes back (--why \"...\")")
    with st.tx() as db:
        rows = db.execute("SELECT * FROM jobs WHERE page=? ORDER BY id", (path,)).fetchall()
        start = next((i for i, r in enumerate(rows) if r["kind"] == kind), None)
        if start is None:
            raise BoardError(f"{path} has no '{kind}' job")
        ids = []
        for r in rows[start:]:
            resources.release_job(db, r["id"])
            db.execute("UPDATE jobs SET status='queued', holder=NULL, lease_until=NULL, slot=NULL, started=NULL, finished=NULL, proof=NULL, "
                       "attempts=0, why=?, priority=1 WHERE id=?", (why.strip(), r["id"]))
            ids.append(r["id"])
        st.event("page-sent-back", path, {"to": kind, "why": why.strip()[:300], "jobs": ids})
        done_ids = _satisfied_ids(db)
        for r in rows[start:]:
            if all(n in done_ids for n in _needs(r)):
                st.event("job-ready", str(r["id"]), {"kind": r["kind"], "page": path})
        _refresh_page(db, st, path)
        return ids


# -- views ------------------------------------------------------------------------------------------------------------
def _ago(secs: float) -> str:
    secs = int(max(secs, 0))
    if secs < 90:
        return f"{secs}s"
    if secs < 5400:
        return f"{secs // 60}m {secs % 60:02d}s" if secs < 600 else f"{secs // 60}m"
    return f"{secs // 3600}h {secs % 3600 // 60:02d}m"


def _left(until: str | None) -> str:
    if not until:
        return ""
    try:
        return _ago((datetime.fromisoformat(until) - datetime.now(datetime.fromisoformat(until).tzinfo)).total_seconds())
    except ValueError:
        return ""


def waiting(rows: list, kinds: dict) -> str:
    """What a page waits for, from its jobs (in order): who holds a job, or what is queued and ready, or what blocks it."""
    open_ = [r for r in rows if r["status"] not in SATISFIED]
    if not open_:
        return "nothing: all jobs done"
    held = [f"{r['kind']} by {r['holder']} ({_left(r['lease_until'])} left)" for r in open_ if r["status"] == "claimed"]
    if held:
        return "working: " + "; ".join(held)
    bad = [r for r in open_ if r["status"] in ("blocked", "failed")]
    if bad:
        return "; ".join(f"{r['status'].upper()} {r['kind']}: {(r['why'] or '')[:60]}" for r in bad)
    done_ids = {r["id"] for r in rows if r["status"] in SATISFIED}
    ready = [r for r in open_ if all(n in done_ids for n in _needs(r))]
    if ready:
        return "queued, ready to take: " + ", ".join(f"{r['kind']} ({r['runner']})" for r in ready)
    first = next((r for r in open_ if not r["refresh"]), open_[0])
    left = [kinds.get(n, str(n)) for n in _needs(first) if n not in done_ids]
    return f"{first['kind']} waits for " + ", ".join(left)


def pages_view(stage: str | None = None, project=None, st=None) -> list:
    """Every page: path, type, key, cluster, stage, holder, "waits" (plain words), counts of its jobs by status, and "shelf": the
    soonest-expiring done result of a page that is not READY yet ("ai-baseline expires in 12 days")."""
    st = _st(st, project)
    out = []
    soonest: dict = {}
    for x in shelf(st.conn):                                  # soonest first: the first one of a page is the one to show
        soonest.setdefault(x["page"], x)
    for p in st.q("SELECT * FROM pages ORDER BY created, path"):
        if stage and p["stage"] != stage:
            continue
        rows = st.q("SELECT id, kind, status, holder, lease_until, runner, needs, why, refresh FROM jobs WHERE page=? ORDER BY id", (p["path"],))
        kinds = {r["id"]: r["kind"] for r in rows}
        counts: dict = {}
        for r in rows:
            counts[r["status"]] = counts.get(r["status"], 0) + 1
        x = soonest.get(p["path"])
        out.append({**dict(p), "waits": waiting(rows, kinds), "counts": counts,
                    "shelf": (f"{x['kind']} {'expired' if x['days_left'] < 0 else 'expires in ' + str(int(x['days_left'])) + ' days'}" if x else "")})
    return out


def jobs_view(kit: str | None = None, status: str | None = None, page: str | None = None, kind: str | None = None, project=None, st=None) -> list:
    st = _st(st, project)
    conds, args = [], []
    for col, val in (("kit", kit), ("status", status), ("page", paths.normalize(page) if page else None), ("kind", kind)):
        if val:
            conds.append(f"{col}=?")
            args.append(val)
    sql = "SELECT * FROM jobs" + (" WHERE " + " AND ".join(conds) if conds else "") + " ORDER BY id"
    return [{**dict(r), "needs": _needs(r)} for r in st.q(sql, args)]


def _secs(a: str, b: str) -> float:
    return (datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds()


def times(project=None, st=None) -> list:
    """Per job kind from the events: how many jobs finished, the median wait (the moment the job was ready, else created,
    to its first claim) and the median work (its last claim to done), in seconds."""
    st = _st(st, project)
    jobs: dict = {}
    for ev in st.q("SELECT at, kind, subject, data FROM events WHERE kind IN ('job-created','job-ready','job-claimed','job-done') ORDER BY id"):
        j = jobs.setdefault(ev["subject"], {})
        if ev["kind"] == "job-created":
            j.setdefault("created", ev["at"])
            j.setdefault("what", (json.loads(ev["data"]) if ev["data"] else {}).get("kind", "?"))
        elif ev["kind"] == "job-ready":
            j.setdefault("ready", ev["at"])
        elif ev["kind"] == "job-claimed":
            j.setdefault("first", ev["at"])
            j["last"] = ev["at"]
            if "what" not in j:
                j["what"] = (json.loads(ev["data"]) if ev["data"] else {}).get("kind", "?")
        elif ev["kind"] == "job-done":
            j["done"] = ev["at"]
    waits: dict = {}
    works: dict = {}
    for j in jobs.values():
        if "done" not in j or "last" not in j:
            continue
        start = j.get("ready") or j.get("created")
        if start and "first" in j:
            waits.setdefault(j["what"], []).append(_secs(start, j["first"]))
        works.setdefault(j["what"], []).append(_secs(j["last"], j["done"]))
    order = {k: i for i, k in enumerate(kits.jobs())}
    return [{"kind": k, "jobs": len(works[k]), "median_wait_s": statistics.median(waits[k]) if waits.get(k) else None,
             "median_work_s": statistics.median(works[k])} for k in sorted(works, key=lambda k: (order.get(k, 99), k))]


# -- command line -----------------------------------------------------------------------------------------------------
def _table(rows: list, cols: list) -> None:
    if not rows:
        return
    widths = [max(len(c), *(len(str(r[i])) for r in rows)) for i, c in enumerate(cols)]
    print("  ".join(c.ljust(w) for c, w in zip(cols, widths)).rstrip())
    for r in rows:
        print("  ".join(str(v).ljust(w) for v, w in zip(r, widths)).rstrip())


def _import_lines(text: str) -> list:
    out = []
    for n, ln in enumerate(text.splitlines(), 1):
        ln = ln.split("#", 1)[0].strip()
        if not ln:
            continue
        f = ln.split()
        if len(f) not in (3, 4):
            raise BoardError(f"line {n}: want '<path> <type> <key> [cluster]', got: {ln}")
        out.append((f[0], f[1], f[2], f[3] if len(f) == 4 else None))
    return out


def _parse_steps(text: str | None) -> dict:
    out = {}
    for part in (text or "").split(","):
        if part.strip():
            k, _, v = part.partition("=")
            out[k.strip()] = int(v)
    return out


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="growth board", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("pages")
    a_ = sub.add_parser("add")
    a_.add_argument("path"); a_.add_argument("--type", required=True); a_.add_argument("--key", required=True)
    a_.add_argument("--cluster"); a_.add_argument("--task"); a_.add_argument("--steps", help="kind=step,kind=step")
    i_ = sub.add_parser("import"); i_.add_argument("file")
    s_ = sub.add_parser("show"); s_.add_argument("path")
    j_ = sub.add_parser("jobs")
    j_.add_argument("--kit"); j_.add_argument("--status"); j_.add_argument("--page"); j_.add_argument("--kind")
    sub.add_parser("times")
    sub.add_parser("resources")
    sub.add_parser("refresh")
    b_ = sub.add_parser("back"); b_.add_argument("path"); b_.add_argument("kind"); b_.add_argument("--why", required=True)
    l_ = sub.add_parser("link"); l_.add_argument("job"); l_.add_argument("--task", required=True); l_.add_argument("--step", type=int, required=True)
    for name in ("block", "unblock", "cancel"):
        x = sub.add_parser(name); x.add_argument("job"); x.add_argument("--why", default="")
    a = ap.parse_args(argv)
    try:
        return _run(a)
    except (BoardError, KeyError) as e:
        print(f"growth board: {e.args[0] if e.args else e}", file=sys.stderr)
        return 1


def _run(a) -> int:
    st = _st()
    cmd = a.cmd or "pages"
    if cmd == "pages":
        rows = pages_view(st=st)
        if not rows:
            print("The board is empty. Add pages: growth board add <path> --type money --key <key>  or  growth board import <file>")
            return 0
        _table([(p["path"], p["type"], p["stage"], p["holder"] or "-", p["waits"], p["shelf"] or "-") for p in rows],
               ["page", "type", "stage", "holder", "waits for", "shelf life"])
        n = {}
        for p in rows:
            n[p["stage"]] = n.get(p["stage"], 0) + 1
        print("\n" + ", ".join(f"{k}: {v}" for k, v in sorted(n.items(), key=lambda kv: (kits.stages().index(kv[0]) if kv[0] in kits.stages() else 99, kv[0]))))
    elif cmd == "add":
        r = add_page(a.path, a.type, a.key, a.cluster, a.task, _parse_steps(a.steps), st=st)
        print(f"{r['path']}: {'added with ' + str(len(r['jobs'])) + ' jobs' if r['created'] else 'already on the board'}")
    elif cmd == "import":
        text = Path(a.file).read_text(encoding="utf-8") if a.file != "-" else sys.stdin.read()
        added = skipped = 0
        for path, typ, key, cluster in _import_lines(text):
            r = add_page(path, typ, key, cluster, st=st)
            added, skipped = added + r["created"], skipped + (not r["created"])
        print(f"imported {added} page(s), {skipped} already on the board")
    elif cmd == "show":
        path = paths.normalize(a.path)
        p = st.q1("SELECT * FROM pages WHERE path=?", (path,))
        if not p:
            raise BoardError(f"{path} is not on the board")
        print(f"{p['path']}  type {p['type']}  key {p['key']}  cluster {p['cluster'] or '-'}  stage {p['stage']}  holder {p['holder'] or '-'}")
        _table([(j["id"], j["kind"], j["status"], j["runner"], j["resource"], j["holder"] or "-", ",".join(map(str, j["needs"])) or "-", j["attempts"])
                for j in jobs_view(page=path, st=st)], ["job", "kind", "status", "runner", "resource", "holder", "needs", "tries"])
    elif cmd == "jobs":
        _table([(j["id"], j["kind"], j["status"], j["page"] or "-", j["kit"], j["way"], j["runner"], j["resource"], j["holder"] or "-")
                for j in jobs_view(a.kit, a.status, a.page, a.kind, st=st)],
               ["job", "kind", "status", "page", "kit", "way", "runner", "resource", "holder"])
    elif cmd == "times":
        rows = times(st=st)
        if not rows:
            print("No finished jobs yet.")
        _table([(r["kind"], r["jobs"], _ago(r["median_wait_s"]) if r["median_wait_s"] is not None else "-", _ago(r["median_work_s"])) for r in rows],
               ["job kind", "jobs", "median wait", "median work"])
    elif cmd == "resources":
        for name, d in resources.defs(st).items():
            slots = [r for r in resources.lease_rows(st) if r["resource"] == name]
            detail = {"pacer": "paced (growth pace)", "none": "-"}.get(d["kind"], f"{len(slots)} held")
            print(f"{name:<14} {d['kind']:<6} {detail}")
            for r in slots:
                print(f"    slot {r['slot']}: {r['holder']}{' (job ' + str(r['job']) + ')' if r['job'] else ''} until {r['until']}")
    elif cmd == "refresh":
        made = refresh_expiring(st=st)
        shown = shelf_view(st=st)
        print(f"{len(made)} refresh job(s) queued" + (f": {', '.join(map(str, made))}" if made else "")
              + f"; {len(shown)} result(s) of pages not READY yet have a use-by date" + (f", the soonest is {shown[0]['kind']} of {shown[0]['page']} ({shown[0]['days_left']:.0f} days)" if shown else ""))
    elif cmd == "back":
        ids = send_back(a.path, a.kind, a.why, st=st)
        print(f"{paths.normalize(a.path)} sent back to {a.kind}: jobs {', '.join(map(str, ids))} run again, first in line")
    elif cmd == "link":
        link_task(a.job, a.task, a.step, st=st)
        print(f"job {a.job} will tick {a.task} step {a.step} when it is done")
    else:
        fn = {"block": lambda: block(a.job, a.why or "blocked", st=st), "unblock": lambda: unblock(a.job, st=st),
              "cancel": lambda: cancel(a.job, a.why or None, st=st)}[cmd]
        j = fn()
        print(f"job {j['id']} ({j['kind']}) is now {j['status']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
