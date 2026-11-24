"""kit 3.0 work board (kit/tools/board.py, work.py): claim, needs, leases, proofs, ticks, times."""
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

import board
import store
from board_helpers import TOOLS, growth, make_project, proof_file


def fresh(tmp_path, **cfg):
    project = make_project(tmp_path, **cfg)
    return project, store.Store(project)


def take(st, agent="a1", **kw):
    return board.claim(agent, st=st, **kw)


def finish(st, j, agent="a1"):
    return board.done(j["id"], agent, "https://example.com/proof/%d" % j["id"], st=st)


# -- pages and the pipeline -------------------------------------------------------------------------------------------
def test_a_page_gets_one_job_per_step_of_its_pipeline(tmp_path):
    _, st = fresh(tmp_path)
    r = board.add_page("/lawn-mowing/", "money", "lawn-mowing", cluster="mowing", st=st)
    assert r["created"] and r["path"] == "/lawn-mowing" and len(r["jobs"]) == 22
    again = board.add_page("/lawn-mowing", "money", "lawn-mowing", st=st)
    assert not again["created"] and again["jobs"] == r["jobs"]
    kinds = [j["kind"] for j in board.jobs_view(page="/lawn-mowing", st=st)]
    assert kinds[0] == "snapshot" and kinds[-1] == "measure" and "ai-baseline" in kinds
    assert board.add_page("/blog/x", "post", "x", st=st)["created"]
    assert len(board.jobs_view(page="/blog/x", st=st)) == 17           # the lighter set: no dossier, no AI baseline
    with pytest.raises(KeyError):
        board.add_page("/y", "poster", "y", st=st)


def test_needs_are_respected_and_the_stage_moves(tmp_path):
    _, st = fresh(tmp_path)
    board.add_page("/p", "money", "p", st=st)
    j = take(st)
    assert j["kind"] == "snapshot" and take(st, "a2") is None            # nothing else is ready while the snapshot runs
    assert board.pages_view(st=st)[0]["holder"] == "a1"
    r = finish(st, j)
    assert len(r["ready"]) == 3                                           # dossier, figures, ai-baseline
    got = [take(st, f"w{i}")["kind"] for i in range(3)]
    assert sorted(got) == ["ai-baseline", "dossier", "figures"]
    assert take(st, "w9") is None                                         # record needs all three
    page = board.pages_view(st=st)[0]
    assert page["stage"] == "research" and "working:" in page["waits"]
    for j in board.jobs_view(status="claimed", st=st):
        finish(st, j, j["holder"])
    assert take(st)["kind"] == "record"


def test_kit_and_runner_narrow_the_choice_and_owner_jobs_are_never_given_out(tmp_path):
    _, st = fresh(tmp_path)
    board.add_page("/p", "core", "p", st=st)
    assert take(st, kit="plan") is None
    assert take(st, runner="agent:build") is None
    assert take(st, runner="agent") is None                               # the snapshot is the machine's
    j = take(st, runner="machine")
    assert j["kind"] == "snapshot"
    finish(st, j)
    rec = take(st, "w", runner="agent")
    assert rec["kind"] == "record"
    finish(st, rec, "w")
    # push the page to the owner step: no claim without runner=owner ever returns it
    for _ in range(40):
        j = take(st, "x")
        if j is None:
            break
        finish(st, j, "x")
    assert board.pages_view(st=st)[0]["stage"] == "owner"
    assert take(st, "x") is None
    owner_job = take(st, "the-owner", runner="owner")
    assert owner_job["kind"] == "owner-checkin-2"
    finish(st, owner_job, "the-owner")
    assert take(st, "x") is None                                          # release is the owner's too
    assert take(st, "lead", runner="owner")["kind"] == "release"


def test_oldest_job_first_and_a_page_sent_back_goes_first(tmp_path):
    _, st = fresh(tmp_path)
    board.add_page("/a", "core", "a", st=st)
    board.add_page("/b", "core", "b", st=st)
    j1, j2 = take(st, "w1"), take(st, "w2")
    assert (j1["page"], j2["page"]) == ("/a", "/b")
    finish(st, j1, "w1"), finish(st, j2, "w2")
    assert take(st, "w1")["page"] == "/a"                                 # record of /a before record of /b
    ids = board.send_back("/b", "snapshot", "the owner wants new research", st=st)
    assert len(ids) == 16 and board.pages_view(st=st)[1]["stage"] == "research"
    assert take(st, "w3")["page"] == "/b"                                 # rework first, ahead of older queued work
    with pytest.raises(board.BoardError):
        board.send_back("/b", "snapshot", "", st=st)


# -- leases ----------------------------------------------------------------------------------------------------------
def test_an_expired_lease_returns_the_job_and_the_old_holder_cannot_finish_it(tmp_path):
    _, st = fresh(tmp_path)
    board.add_page("/p", "core", "p", st=st)
    j = take(st, "slow", lease_s=1)
    st.conn.execute("UPDATE jobs SET lease_until='2000-01-01T00:00:00+00:00' WHERE id=?", (j["id"],))
    j2 = take(st, "quick")                                                # every claim sweeps first
    assert j2["id"] == j["id"] and j2["holder"] == "quick"
    assert st.events("job-expired", str(j["id"]))
    with pytest.raises(board.BoardError, match="held by quick"):
        board.done(j["id"], "slow", "https://example.com/x", st=st)
    assert board.beat(j["id"], "slow", st=st) is False                    # the old holder learns the job is gone
    assert board.beat(j["id"], "quick", st=st) is True
    assert board.renew(j["id"], "quick", lease_s=600, st=st)["lease_until"] > store.now()


def test_a_lease_that_ran_out_frees_the_resource(tmp_path):
    _, st = fresh(tmp_path)
    j = board.add_job("build", st=st)
    got = take(st, "lane-1")
    assert got["port"] and st.q1("SELECT COUNT(*) n FROM leases")["n"] == 1
    st.conn.execute("UPDATE jobs SET lease_until='2000-01-01T00:00:00+00:00' WHERE id=?", (j,))
    assert board.expire(st=st) == [j]
    assert st.q1("SELECT COUNT(*) n FROM leases")["n"] == 0
    assert board.jobs_view(st=st)[0]["status"] == "queued" and board.jobs_view(st=st)[0]["attempts"] == 0


def test_fail_requeues_with_one_more_attempt_and_stops_after_three(tmp_path):
    _, st = fresh(tmp_path)
    j = board.add_job("build", st=st)
    for n in (1, 2):
        got = take(st, "a1")
        r = board.fail(got["id"], "a1", "the build broke", st=st)
        assert r["status"] == "queued" and r["attempts"] == n and r["holder"] is None
    got = take(st, "a1")
    r = board.fail(got["id"], "a1", "still broken", st=st)
    assert r["status"] == "failed" and r["attempts"] == 3
    assert take(st, "a1") is None
    board.unblock(j, st=st)
    assert take(st, "a1")["id"] == j
    with pytest.raises(board.BoardError):
        board.fail(j, "a1", "", st=st)


# -- proof and ticks --------------------------------------------------------------------------------------------------
def test_done_without_a_proof_is_refused(tmp_path):
    project, st = fresh(tmp_path)
    j = board.add_job("cleanup", st=st)
    got = take(st)
    for bad in ("", "   ", "x", "done", "ok yes"):
        with pytest.raises(board.BoardError):
            board.done(got["id"], "a1", bad, st=st)
    assert board.jobs_view(st=st)[0]["status"] == "claimed"
    r = growth(project, "work", "done", str(j), "--proof", "", agent="a1")
    assert r.returncode == 1 and "proof" in r.stderr
    assert board.done(j, "a1", proof_file(project), st=st)["status"] == "done"


def test_a_job_with_a_task_step_ticks_that_step_with_the_proof(tmp_path):
    project, st = fresh(tmp_path)
    tid = growth(project, "tasks", "add", "Fix the pricing page", "make it right", check=True).stdout.strip().splitlines()[-1]
    growth(project, "tasks", "step", tid, "Snapshot the page", check=True)
    growth(project, "tasks", "step", tid, "Write the dossier", check=True)
    board.add_page("/pricing", "post", "pricing", task=tid, steps={"snapshot": 1, "record": 2}, st=st)
    j = take(st)
    assert (j["task"], j["step"]) == (tid, 1)
    proof = proof_file(project, "snapshot.md")
    board.done(j["id"], "a1", proof, st=st)
    shown = growth(project, "tasks", "show", tid, check=True).stdout
    assert "1. [done]" in shown and proof in shown and "2. [todo]" in shown


def test_a_proof_the_task_list_refuses_keeps_the_job_claimed(tmp_path):
    project, st = fresh(tmp_path)
    board.add_job("cleanup", task="T99", step=1, st=st)
    j = take(st)
    with pytest.raises(board.BoardError, match="task list"):
        board.done(j["id"], "a1", proof_file(project), st=st)
    assert board.jobs_view(st=st)[0]["status"] == "claimed"


def test_link_task_and_cancel_and_block(tmp_path):
    project, st = fresh(tmp_path)
    board.add_page("/p", "core", "p", st=st)
    snap = board.jobs_view(st=st)[0]["id"]
    board.link_task(snap, "T1", 3, st=st)
    assert board.jobs_view(st=st)[0]["task"] == "T1"
    board.block(snap, "waiting for the owner's answer", st=st)
    assert take(st) is None and "BLOCKED" in board.pages_view(st=st)[0]["waits"]
    board.cancel(snap, "not needed", st=st)                               # a cancelled need counts as done
    assert take(st)["kind"] == "record"


# -- many claimers at once ---------------------------------------------------------------------------------------------
WORKER = r"""
import json, sys, time
sys.path.insert(0, %r)
import board, store
st = store.open(sys.argv[1]); agent = sys.argv[2]
out = []
while True:
    j = board.claim(agent, lease_s=120, st=st)
    if j is None:
        if st.q1("SELECT COUNT(*) n FROM jobs WHERE status='claimed'")["n"] == 0:
            break
        time.sleep(0.01)
        continue
    t0 = time.time()
    open_needs = st.q1("SELECT COUNT(*) n FROM jobs WHERE id IN (%%s) AND status != 'done'" %% (",".join(map(str, j["needs"])) or "0"))["n"]
    time.sleep(0.01)
    t1 = time.time()
    board.done(j["id"], agent, "https://example.com/p/%%d" %% j["id"], st=st)
    out.append({"id": j["id"], "agent": agent, "kind": j["kind"], "needs_open": open_needs, "resource": j["resource"],
                "slot": j["slot"], "t0": t0, "t1": t1})
print(json.dumps(out))
""" % str(TOOLS)


def test_eight_parallel_claimers_never_share_a_job_and_never_jump_the_needs(tmp_path):
    project, st = fresh(tmp_path, resources={"port_range": [28440, 28442], "browser": 2})
    for n in range(8):
        board.add_page(f"/page-{n}", "core", f"page-{n}", st=st)
    procs = [subprocess.Popen([sys.executable, "-c", WORKER, str(project), f"w{n}"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
             for n in range(8)]
    outs = [p.communicate(timeout=240) for p in procs]
    assert all(p.returncode == 0 for p in procs), outs
    rows = [r for o, _ in outs for r in json.loads(o)]
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids)) == 8 * 13                            # every job of the agents' line, each exactly once
    assert all(r["needs_open"] == 0 for r in rows)
    assert len({r["agent"] for r in rows}) > 1                            # the work really was shared
    held = [r for r in rows if r["slot"] is not None]
    assert {r["resource"] for r in held} == {"port", "browser", "owner-preview"}
    for a in held:                                                        # no two holders of one slot overlapped in time
        for b in held:
            if a["id"] < b["id"] and (a["resource"], a["slot"]) == (b["resource"], b["slot"]):
                assert a["t1"] <= b["t0"] or b["t1"] <= a["t0"], (a, b)
    assert {p["stage"] for p in board.pages_view(st=st)} == {"owner"}
    assert st.q1("SELECT COUNT(*) n FROM leases")["n"] == 0


# -- views, commands, times --------------------------------------------------------------------------------------------
def test_board_commands_import_show_and_the_work_commands(tmp_path):
    project, _ = fresh(tmp_path)
    batch = tmp_path / "pages.txt"
    batch.write_text("# the pages\n/a money a mowing\n/blog/b post b\n\n")
    assert growth(project, "board", "import", str(batch)).stdout.strip() == "imported 2 page(s), 0 already on the board"
    assert "0 page(s), 2 already" in growth(project, "board", "import", str(batch)).stdout
    out = growth(project, "board", check=True).stdout
    assert "/a" in out and "/blog/b" in out and "research" in out and "ready to take" in out
    assert "snapshot" in growth(project, "board", "show", "/a", check=True).stdout
    bad = tmp_path / "bad.txt"
    bad.write_text("/only-a-path\n")
    assert growth(project, "board", "import", str(bad)).returncode == 1
    r = growth(project, "work", "next", "--kit", "research", "--agent", "r1", "--runner", "machine")
    assert r.returncode == 0 and "job " in r.stdout and "snapshot for /a" in r.stdout
    nothing = growth(project, "work", "next", "--kit", "plan", "--agent", "r1")
    assert nothing.returncode == 3
    jid = r.stdout.split()[1].rstrip(":")
    assert growth(project, "work", "beat", jid, "--agent", "r1").returncode == 0
    assert growth(project, "work", "done", jid, "--proof", proof_file(project), "--agent", "r2").returncode == 1   # not the holder
    d = growth(project, "work", "done", jid, "--proof", proof_file(project), "--agent", "r1")
    assert d.returncode == 0 and "done" in d.stdout
    assert "claimed" not in growth(project, "work", "list", "--status", "claimed").stdout
    js = json.loads(growth(project, "work", "next", "--agent", "r1", "--json").stdout)
    assert js["page"] in ("/a", "/blog/b") and js["status"] == "claimed"


def _insert_events(st, rows):
    for at, kind, subject, data in rows:
        st.conn.execute("INSERT INTO events(at, actor, kind, subject, data) VALUES(?, 'x', ?, ?, ?)", (at, kind, subject, json.dumps(data) if data else None))


def test_times_prints_the_medians_from_the_events(tmp_path):
    project, st = fresh(tmp_path)
    board._st(st)

    def stamp(sec):
        return "2026-11-24T10:%02d:%02d+00:00" % (sec // 60, sec % 60)
    rows = []
    # three build jobs: ready at 0, claimed after 10 s, 20 s and 90 s (median 20 s), worked 100 s, 300 s and 700 s (median 300 s)
    for jid, (wait, work) in zip((1, 2, 3), ((10, 100), (20, 300), (90, 700))):
        rows += [(stamp(0), "job-created", str(jid), {"kind": "build"}), (stamp(0), "job-ready", str(jid), {"kind": "build"}),
                 (stamp(wait), "job-claimed", str(jid), {"kind": "build"}), (stamp(wait + work), "job-done", str(jid), {"kind": "build"})]
    # a shots job created at 0 but ready only at 600 (its needs finished then): the wait counts from ready, 30 s
    rows += [(stamp(0), "job-created", "4", {"kind": "shots"}), (stamp(600), "job-ready", "4", {"kind": "shots"}),
             (stamp(630), "job-claimed", "4", {"kind": "shots"}), (stamp(650), "job-done", "4", {"kind": "shots"})]
    # a job claimed twice (the first agent stopped): work counts from the last claim
    rows += [(stamp(0), "job-created", "5", {"kind": "cleanup"}), (stamp(5), "job-claimed", "5", {"kind": "cleanup"}),
             (stamp(100), "job-claimed", "5", {"kind": "cleanup"}), (stamp(160), "job-done", "5", {"kind": "cleanup"})]
    # an unfinished job is left out
    rows += [(stamp(0), "job-created", "6", {"kind": "review"}), (stamp(50), "job-claimed", "6", {"kind": "review"})]
    _insert_events(st, rows)
    got = {r["kind"]: r for r in board.times(st=st)}
    assert got["build"]["jobs"] == 3 and got["build"]["median_wait_s"] == 20 and got["build"]["median_work_s"] == 300
    assert got["shots"]["median_wait_s"] == 30 and got["shots"]["median_work_s"] == 20
    assert got["cleanup"]["median_wait_s"] == 5 and got["cleanup"]["median_work_s"] == 60
    assert "review" not in got
    out = growth(project, "board", "times", check=True).stdout
    build_line = next(l for l in out.splitlines() if l.startswith("build"))
    assert "20s" in build_line and "5m 00s" in build_line and build_line.split()[1] == "3"


def test_every_board_change_is_an_event_and_times_reads_real_runs(tmp_path):
    _, st = fresh(tmp_path)
    board.add_page("/p", "core", "p", st=st)
    j = take(st)
    time.sleep(1.1)
    finish(st, j)
    kinds = {e["kind"] for e in st.events(limit=200)}
    assert {"page-added", "job-created", "job-claimed", "job-done", "job-ready"} <= kinds
    snap = next(r for r in board.times(st=st) if r["kind"] == "snapshot")
    assert snap["jobs"] == 1 and snap["median_work_s"] >= 1 and snap["median_wait_s"] >= 0
