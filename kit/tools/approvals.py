#!/usr/bin/env python3
"""Owner-only approvals: `growth approve <what>`, and the log the gate checks (docs/approvals.jsonl).

  growth approve exception <check-id>            a growth.json design_exceptions entry (needs a why and an until date
                                                 at most 30 days ahead; evidence and process checks can never be excused)
  growth approve decision <journal-id>           an owner decision filed in the journal (growth journal add --kind decision)
  growth approve browser [--name "Browser 1"]     the research browser (named here, or as recorded by growth wizard confirm)
  growth approve region [--seen "United States"] Google's results region (as read here, or as recorded by the wizard)
  growth approve answer <Q-id> "the answer"      answer an owner question in docs/tasks.json
  growth approve review <research/file.md>       sign off an independent review file
  growth approve baseline <key> --reason "..."   allow one re-freeze of a page's research baseline
  growth approve pending                         everything that waits for you, on one screen, one code
  growth approve <decision|review|exception|answer|baseline> <id> --delegated
                                                 the lead agent approves LOCAL work itself, with no terminal and no code, but
                                                 only while growth.json approvals.delegate_local is true (see DELEGABLE below)
  growth approve list | verify                   show the log (delegated lines carry a [delegated] tag); check nobody edited it by hand
  growth approve key                             make the signing key (~/.config/growth-ops-kit/approvals.key)

Each approval is typed by a person in a real terminal: the command shows what is approved and a 4-digit code, and runs
only when `approve <code>` is typed back. The generated agent permissions deny this command. The log line records what
was approved, the sha256 of the approved content, who, when, the hash of the previous line (a chain) and, once the key
exists, an HMAC signature with a key kept in your home folder outside the project.

What this is and is not: an agent with a shell on the same machine as you can in the end do anything you can (open a
pseudo-terminal, read your home folder). The log makes such a bypass visible instead of silent: a hand-written or edited
line breaks the chain or the signature, and content changed after approval no longer matches its hash, so the gate FAILs.
"""
from __future__ import annotations

import datetime as dt
import getpass
import hashlib
import hmac
import json
import os
import re
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import records  # noqa: E402  (the one access layer for tasks, journal and verdicts)

LOG_NAME = "approvals.jsonl"
EXCUSE_MAX_DAYS = 30
# Never excused by a growth.json exception: evidence (ev.*) and process (proc.*) checks, and any line that says the check
# could not run at all (the page did not load, an input is missing, the check crashed).
NEVER_EXCUSED = ("ev.", "proc.")
NEVER_EXCUSED_LINES = ("input missing", "check crashed", "check printed no result")
KINDS = ("exception", "decision", "browser", "region", "answer", "review", "baseline")
# What the owner may hand to the lead agent (growth.json approvals.delegate_local). Never delegated: the research browser and
# Google region (a person must see them), `pending` (it holds those) and any go-live or release act. The kit has NO release
# approval kind of its own: a release or go-live stays the owner's own act, typed in their terminal, outside this log.
DELEGABLE = ("decision", "review", "exception", "answer", "baseline")


class NoTerminal(SystemExit):
    pass


# ---- content and hashes -------------------------------------------------------------------------------------------------
def canon(obj) -> bytes:
    if isinstance(obj, bytes):
        return obj
    if isinstance(obj, str):
        return obj.encode()
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(obj) -> str:
    return hashlib.sha256(canon(obj)).hexdigest()


def key_path() -> Path:
    return Path(os.path.expanduser("~")) / ".config" / "growth-ops-kit" / "approvals.key"


def read_key() -> bytes | None:
    try:
        k = key_path().read_bytes().strip()
        return k or None
    except OSError:
        return None


def ensure_key() -> bytes:
    k = read_key()
    if k:
        return k
    p = key_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    k = secrets.token_hex(32).encode()
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(k + b"\n")
    return k


def _sign(entry: dict, key: bytes) -> str:
    body = {k: v for k, v in entry.items() if k != "sig"}
    return hmac.new(key, canon(body), hashlib.sha256).hexdigest()


# ---- the log ------------------------------------------------------------------------------------------------------------
def log_path(docs) -> Path:
    return Path(docs) / LOG_NAME


def _lines(docs) -> list[str]:
    try:
        return [ln for ln in log_path(docs).read_text().splitlines() if ln.strip()]
    except OSError:
        return []


def verify(docs) -> tuple[list[dict], list[str]]:
    """(entries, problems). A problem means the log was edited by hand: a broken chain, a bad or missing signature, a line
    that is not JSON. Callers treat any problem as "no approval can be trusted"."""
    key = read_key()
    out, probs, prev = [], [], ""
    for i, raw in enumerate(_lines(docs), 1):
        try:
            e = json.loads(raw)
            assert isinstance(e, dict)
        except (ValueError, AssertionError):
            probs.append(f"line {i} is not an approval record")
            prev = hashlib.sha256(raw.encode()).hexdigest()
            continue
        if e.get("prev", "") != prev:
            probs.append(f"line {i} ({e.get('id', '?')}) does not follow the line before it (the log was edited)")
        if key:
            if not e.get("sig"):
                probs.append(f"line {i} ({e.get('id', '?')}) is not signed")
            elif not hmac.compare_digest(str(e["sig"]), _sign(e, key)):
                probs.append(f"line {i} ({e.get('id', '?')}) has a signature that does not match (written or edited by hand)")
        elif e.get("sig"):
            probs.append(f"line {i} ({e.get('id', '?')}) is signed but the signing key is gone ({key_path()})")
        out.append(e)
        prev = hashlib.sha256(raw.encode()).hexdigest()
    return out, probs


def delegation(docs_or_project) -> dict | None:
    """growth.json "approvals" when delegate_local is on, else None. `docs` is the project's docs folder (its parent holds growth.json)."""
    p = Path(docs_or_project)
    p = p.parent if p.name == "docs" else p
    try:
        a = json.loads((p / "growth.json").read_text()).get("approvals") or {}
    except (OSError, ValueError, AttributeError):
        return None
    return a if isinstance(a, dict) and a.get("delegate_local") is True else None


def delegated_by(a: dict) -> str:
    return f"{a.get('delegated_to') or 'lead agent'} (delegated by owner {a.get('since') or 'since an unrecorded date'})"


def record(docs, kind: str, ref: str, content, summary: str = "", by: str | None = None, via: str = "terminal",
           extra: dict | None = None) -> dict:
    """Append one approval (library; `approve` is the owner's door to it)."""
    if kind not in KINDS:
        raise ValueError(f"unknown approval kind {kind}")
    lines = _lines(docs)
    entry = {"id": f"A{len(lines) + 1:04d}", "kind": kind, "ref": str(ref), "sha256": digest(content), "summary": summary[:200],
             "by": by or _who(), "at": dt.datetime.now().astimezone().isoformat(timespec="seconds"), "via": via,
             "prev": hashlib.sha256(lines[-1].encode()).hexdigest() if lines else "", **(extra or {})}
    key = read_key()
    if key:
        entry["sig"] = _sign(entry, key)
    p = log_path(docs)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def _who() -> str:
    try:
        return getpass.getuser()
    except Exception:  # noqa: BLE001
        return "owner"


def status(docs, kind: str, ref: str, content) -> tuple[str, dict | str | None]:
    """("ok", entry) | ("missing", None) | ("changed", entry) | ("tampered", problem)."""
    entries, probs = verify(docs)
    if probs:
        return "tampered", probs[0]
    mine = [e for e in entries if e.get("kind") == kind and e.get("ref") == str(ref)]
    h = digest(content)
    good = [e for e in mine if e.get("sha256") == h]
    if good:
        if good[-1].get("mode") == "delegated" and not delegation(docs):      # delegation was turned off: it no longer counts
            return "delegation_off", good[-1]
        return "ok", good[-1]
    return ("changed", mine[-1]) if mine else ("missing", None)


def explain(state: str, info, what: str, fix: str) -> str:
    """One plain line for a state that is not ok."""
    if state == "tampered":
        return f"the approvals log cannot be trusted: {info}; the owner checks it with growth approve verify"
    if state == "delegation_off":
        return (f"{what} was approved by the lead agent under the owner's delegation ({info.get('id')}), and growth.json approvals.delegate_local "
                f"is no longer on; the owner approves it in their own terminal: {fix}")
    if state == "changed":
        return f"{what} changed after the owner approved it ({info.get('id')}, {str(info.get('at'))[:10]}); the owner approves it again: {fix}"
    return f"{what} has no owner approval; the owner runs, in their own terminal: {fix}"


# ---- what each kind approves (the gate builds the same content) --------------------------------------------------------
def excusable(cid: str) -> bool:
    return not str(cid).startswith(NEVER_EXCUSED)


def exception_problem(e: dict, approved_on: dt.date) -> str | None:
    """Why a design_exceptions entry may not be approved (or no longer counts): None when it is fine."""
    cid = e.get("check", "")
    if not excusable(cid):
        return f"{cid} is an evidence or process check; no exception can excuse it"
    if len(str(e.get("why") or "").strip()) < 10:
        return "an exception needs a reason ('why', 10 characters or more)"
    try:
        until = dt.date.fromisoformat(str(e.get("until") or "")[:10])
    except ValueError:
        return f"an exception needs an 'until' date (YYYY-MM-DD) at most {EXCUSE_MAX_DAYS} days ahead"
    if (until - approved_on).days > EXCUSE_MAX_DAYS:
        return f"'until' {until} is more than {EXCUSE_MAX_DAYS} days after {approved_on}"
    return None


def exception_state(docs, cfg: dict, cid: str, today: dt.date, task_done=None):
    """Does growth.json design_exceptions excuse check `cid` today? One answer for the gate and for READY.

    ("ok", entry, why_line)    an entry for cid, approved by the owner (same content), until not passed and within 30 days
                               of the approval, its task (if any) not done
    ("refused", entry, why)    an entry exists but does not count: evidence/process check, no approval, changed since,
                               log tampered, no or too far 'until', date passed, task done
    ("none", None, "")         no entry names cid
    task_done: a function(task_id) -> bool (docs/tasks.json), optional."""
    mine = [e for e in (cfg or {}).get("design_exceptions") or [] if isinstance(e, dict) and e.get("check") == cid]
    if not mine:
        return "none", None, ""
    why = ""
    for e in mine:
        state, info = status(docs, "exception", cid, e)
        if state != "ok":
            why = explain(state, info, f"the growth.json exception for {cid}", f"growth approve exception {cid}")
            if not excusable(cid):
                why = f"{cid} is an evidence or process check; no exception can excuse it"
            continue
        try:
            approved_on = dt.date.fromisoformat(str(info.get("at"))[:10])
        except ValueError:
            approved_on = today
        prob = exception_problem(e, approved_on)
        if prob:
            why = prob
            continue
        if today > dt.date.fromisoformat(str(e["until"])[:10]):
            why = f"the exception for {cid} ended on {e['until']}"
            continue
        if e.get("task") and task_done and task_done(e["task"]):
            why = f"the exception's task {e['task']} is done"
            continue
        return "ok", e, f"{e['why'].strip()}{'; task ' + e['task'] if e.get('task') else ''}; owner approval {info.get('id')}"
    return "refused", mine[0], why


def excuses_blocked_skip(project, cfg: dict, cid: str, today: dt.date | None = None) -> tuple[bool, str]:
    """For READY: may a BLOCKED-SKIP of `cid` be accepted? Only when an owner-approved, unexpired design exception names
    it, and never for an evidence or process check. (accepted, one plain line)."""
    def done(tid):
        try:
            return any(t.get("id") == tid and t.get("status") == "done"
                       for t in records.tasks_doc(project)["tasks"])
        except (OSError, ValueError, KeyError):
            return False
    state, _e, why = exception_state(Path(project) / "docs", cfg, cid, today or dt.date.today(), done)
    if state == "ok":
        return True, f"{cid} could not run; excused by the owner: {why}"
    return False, why or f"{cid} could not run and no owner-approved exception names it"


def decision_content(e: dict) -> dict:
    return {k: e.get(k) for k in ("id", "kind", "pages", "title", "text")}


def answer_content(q: dict) -> dict:
    return {"id": q.get("id"), "question": q.get("question"), "answer": q.get("answer")}


def region_content(seen: str, country: str) -> dict:
    return {"seen": seen, "country": country}


def browser_content(name: str) -> dict:
    return {"name": name}


def baseline_content(key: str, reason: str) -> dict:
    return {"key": key, "reason": reason}


def journal_entries(project) -> dict:
    """The journal's entries folded by id (the base line of each, not its later updates)."""
    out = {}
    try:
        for ln in records.journal_lines(project):
            if ln.strip():
                e = json.loads(ln)
                if "of" not in e and e.get("id"):
                    out[e["id"]] = e
    except (OSError, ValueError):
        pass
    return out


# ---- the owner's terminal -------------------------------------------------------------------------------------------------
class Terminal:
    """The owner's own terminal: stdin and stdout are a terminal and /dev/tty opens. An agent's tool call has neither."""

    def __init__(self, rd, wr, name="tty"):
        self.rd, self.wr, self.name = rd, wr, name

    @classmethod
    def open(cls):
        if not (sys.stdin.isatty() and sys.stdout.isatty()):
            raise NoTerminal("growth approve is for the owner, typed in their own terminal; it does not run from an agent or a "
                             "script. Ask the owner to run the same command themselves.")
        try:
            rd, wr = open("/dev/tty"), open("/dev/tty", "w")
        except OSError:
            raise NoTerminal("growth approve needs a real terminal (/dev/tty); ask the owner to run it themselves.")
        try:
            name = os.ttyname(sys.stdin.fileno())
        except OSError:
            name = "tty"
        return cls(rd, wr, name)

    def write(self, s):
        self.wr.write(s)
        self.wr.flush()

    def readline(self):
        return self.rd.readline()


def approve(docs, kind: str, ref: str, content, summary: str, show: str = "", tty=None) -> dict:
    """Ask the owner, in their own terminal, to type the code back; then record the approval."""
    t = tty or Terminal.open()
    code = f"{secrets.randbelow(10 ** 4):04d}"
    t.write(f"\nYou are approving ({kind} {ref}):\n{show or summary}\n\nsha256 {digest(content)[:16]}...\n"
            f"Type exactly   approve {code}   to approve, anything else to stop.\n> ")
    got = (t.readline() or "").strip()
    if got != f"approve {code}":
        raise SystemExit("not approved: the words typed did not match")
    ensure_key()
    d = getattr(t, "delegated", None)
    if d:
        e = record(docs, kind, ref, content, summary, by=delegated_by(d), via="delegated",
                   extra={"mode": "delegated", "owner_words": str(d.get("owner_words") or ""), "since": str(d.get("since") or "")})
        t.write(f"approved (delegated): {e['id']}\n")
        return e
    e = record(docs, kind, ref, content, summary, via=f"terminal {getattr(t, 'name', 'tty')}")
    t.write(f"approved: {e['id']}\n")
    return e


class Delegated:
    """Stands in for the owner's terminal when growth.json approvals.delegate_local is on and --delegated is given: it types the
    code back itself. The log line it leads to says mode "delegated" and who delegated; it is never the owner's typed yes."""
    name = "delegated"

    def __init__(self, settings: dict):
        self.delegated, self._code = settings, ""

    def write(self, s):
        import re as _re
        m = _re.search(r"approve (\d{4})", s)
        if m:
            self._code = m.group(1)

    def readline(self):
        return f"approve {self._code}\n"


def approve_many(docs, items, tty=None) -> list:
    """Many approvals on one screen with one code (the owner reads the whole list once). items: dicts with kind, ref,
    content, summary, show and an optional after(entry) callback. Each item is still recorded as its own log line."""
    if not items:
        return []
    t = tty or Terminal.open()
    code = f"{secrets.randbelow(10 ** 4):04d}"
    lines = [f"  {i}. {it['kind']} {it['ref']}: {it['summary']}" for i, it in enumerate(items, 1)]
    t.write(f"\nYou are approving {len(items)} item(s):\n" + "\n".join(lines)
            + f"\n\nType exactly   approve {code}   to approve ALL of them, anything else to stop.\n> ")
    got = (t.readline() or "").strip()
    if got != f"approve {code}":
        raise SystemExit("not approved: the words typed did not match")
    ensure_key()
    out = []
    for it in items:
        e = record(docs, it["kind"], it["ref"], it["content"], it["summary"], via=f"terminal {getattr(t, 'name', 'tty')} (batch)")
        if it.get("after"):
            it["after"](e)
        out.append(e)
    t.write(f"approved: {', '.join(e['id'] for e in out)}\n")
    return out


def pending_items(project, docs, today):
    """What waits for the owner: design exceptions with no (or a changed) approval, and a recorded research browser or
    Google region the owner has not confirmed. Items that cannot be approved (bad exception) are returned as problems."""
    items, problems = [], []
    cfg = _json(project / "growth.json")
    for e in cfg.get("design_exceptions") or []:
        if not isinstance(e, dict) or not e.get("check"):
            continue
        if status(docs, "exception", e["check"], e)[0] == "ok":
            continue
        why = exception_problem(e, today)
        if why:
            problems.append(f"exception {e['check']}: {why}")
            continue
        items.append({"kind": "exception", "ref": e["check"], "content": e,
                      "summary": f"design exception {e['check']} until {e['until']}: {e['why'][:80]}"})
    import wizard_state as ws
    import research_gate as gate
    for what in ("browser", "region"):
        st = ws.get(project, what) or {}
        ans = st.get("answer") if isinstance(st.get("answer"), dict) else {}
        if not ans or ans.get("owner_confirmed"):
            continue
        if what == "browser":
            if not ans.get("name"):
                continue
            c, line = browser_content(ans["name"]), f"research browser {ans['name']}"
        else:
            market = cfg.get("market") or {}
            seen = ans.get("seen", "")
            if not gate.region_matches(seen, market):
                problems.append(f"region: Google reads \"{seen}\", not {gate.country_name(market)}")
                continue
            c, line = region_content(seen, gate.country_name(market)), f"Google results region {seen}"
        if status(docs, what, what, c)[0] == "ok":
            continue
        items.append({"kind": what, "ref": what, "content": c, "summary": line,
                      "after": (lambda e, w=what, a=ans: ws.record(project, w, "done", answer={**a, "owner_confirmed": True,
                                                                                             "approval": e["id"]}, source="owner"))})
    return items, problems


def _answer_journal(project, docs, jid: str, text: str, tty) -> int:
    e = journal_entries(project).get(jid)
    if not e or e.get("kind") not in ("question", "owner-action"):
        raise SystemExit(f"no open question {jid} in the journal")
    q = {"id": jid, "question": e.get("title") or e.get("text"), "answer": text}
    a = approve(docs, "answer", jid, answer_content(q), f"answer to {jid}: {text[:80]}",
                f"Question: {q['question']}\nAnswer:   {text}", tty)
    import journal
    when = journal.now()
    journal.append({"of": jid, "at": when, "status": "answered", "answer": text, "answered_by": "owner", "answered_at": when,
                    "approval": a["id"]})
    journal.render()
    return 0


# ---- command line -------------------------------------------------------------------------------------------------------
def _project():
    from config import find_project
    p = find_project()
    if p is None:
        raise SystemExit("No project here: run growth approve inside the project folder (or set GROWTH_PROJECT)")
    return p


def _json(p: Path):
    return json.loads(p.read_text())


def main(argv=None, tty=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    what, rest = argv[0], argv[1:]
    delegated = "--delegated" in rest
    rest = [x for x in rest if x != "--delegated"]
    if delegated and what not in DELEGABLE:
        raise SystemExit(f"growth approve {what} is never delegated: the owner types it in their own terminal "
                         "(the research browser, Google region and any go-live or release act stay with the owner)")
    flags = {}
    for flag in ("--reason", "--name", "--seen"):
        if flag in rest:
            i = rest.index(flag)
            flags[flag] = " ".join(rest[i + 1:i + 2]).strip()
            del rest[i:i + 2]
    reason = flags.get("--reason", "")
    if what == "key":
        existed = read_key() is not None
        ensure_key()
        print(("signing key already in " if existed else "signing key made: ") + str(key_path()))
        return 0
    project = _project()
    docs = project / "docs"
    if delegated:
        d = delegation(project)
        if not d:
            raise SystemExit("--delegated is off: the owner has not delegated local approvals (growth.json approvals.delegate_local). "
                             "The owner approves it in their own terminal.")
        tty = Delegated(d)
    if what in ("list", "verify"):
        entries, probs = verify(docs)
        if what == "list":
            for e in entries:
                tag = "  [delegated]" if e.get("mode") == "delegated" else ""
                print(f"{e.get('id')}  {str(e.get('at'))[:16]}  {e.get('kind'):<9} {e.get('ref')}  by {e.get('by')}{tag}  {e.get('summary', '')}")
        for p in probs:
            print("PROBLEM " + p)
        if what == "verify" and not probs:
            print(f"approvals log OK: {len(entries)} entries" + ("" if read_key() else " (not signed: run growth approve key)"))
        return 1 if probs else 0
    today = dt.date.today()
    if what == "pending":
        items, problems = pending_items(project, docs, today)
        for p in problems:
            print("cannot approve: " + p)
        if not items:
            print("nothing waits for your approval" + (" (fix the lines above first)" if problems else ""))
            return 1 if problems else 0
        approve_many(docs, items, tty)
        return 1 if problems else 0
    if what == "exception":
        if not rest:
            raise SystemExit("growth approve exception <check-id>")
        cid = rest[0]
        cfg = _json(project / "growth.json")
        e = next((x for x in cfg.get("design_exceptions") or [] if isinstance(x, dict) and x.get("check") == cid), None)
        if e is None:
            raise SystemExit(f"growth.json design_exceptions has no entry for {cid}")
        why = exception_problem(e, today)
        if why:
            raise SystemExit("cannot approve: " + why)
        approve(docs, "exception", cid, e, f"design exception {cid} until {e['until']}: {e['why'][:80]}",
                json.dumps(e, indent=1, ensure_ascii=False), tty)
    elif what == "decision":
        if not rest:
            raise SystemExit("growth approve decision <journal-id>")
        e = journal_entries(project).get(rest[0])
        if not e or e.get("kind") != "decision":
            raise SystemExit(f"no decision {rest[0]} in the journal (growth journal add --kind decision ...)")
        c = decision_content(e)
        approve(docs, "decision", e["id"], c, f"decision {e['id']} for {', '.join(e.get('pages') or [])}: {e.get('title', '')[:80]}",
                json.dumps(c, indent=1, ensure_ascii=False), tty)
    elif what in ("browser", "region"):
        import wizard_state as ws
        import research_gate as gate
        if what == "browser" and flags.get("--name"):        # the owner names it here instead of the agent's record
            ws.record(project, "browser", "tested", answer={"name": flags["--name"]}, source="owner")
        if what == "region" and flags.get("--seen"):
            ws.record(project, "region", "tested", answer={"seen": flags["--seen"], "owner_confirmed": False}, source="owner")
        st = ws.get(project, what)
        ans = st.get("answer") if isinstance(st.get("answer"), dict) else {}
        if what == "browser":
            name = (ans or {}).get("name", "")
            if not name:
                raise SystemExit('nothing to approve yet: first growth wizard confirm browser --name "<its name>"')
            c, line = browser_content(name), f"research browser {name}"
        else:
            market = (_json(project / "growth.json").get("market") or {})
            seen = (ans or {}).get("seen", "")
            if not gate.region_matches(seen, market):
                raise SystemExit(f"Google's region reads \"{seen}\", not {gate.country_name(market)}: fix it first, then "
                                 "growth wizard confirm region --seen \"<what Google says>\"")
            c, line = region_content(seen, gate.country_name(market)), f"Google results region {seen}"
        e = approve(docs, what, what, c, line, line, tty)
        ws.record(project, what, "done", answer={**(ans or {}), "owner_confirmed": True, "approval": e["id"]}, source="owner")
    elif what == "answer":
        if len(rest) < 2:
            raise SystemExit('growth approve answer <Q-id> "the answer"')
        if re.fullmatch(r"J\d+", rest[0], re.I):               # a question filed in the journal (growth journal ask)
            return _answer_journal(project, docs, rest[0].upper(), " ".join(rest[1:]), tty)
        db = records.tasks_doc(project)
        q = next((x for x in db.get("questions", []) if x.get("id", "").lower() == rest[0].lower()), None)
        if q is None:
            raise SystemExit(f"no question {rest[0]}")
        new = {**q, "answer": " ".join(rest[1:])}
        e = approve(docs, "answer", q["id"], answer_content(new), f"answer to {q['id']}: {new['answer'][:80]}",
                    f"Question: {q['question']}\nAnswer:   {new['answer']}", tty)
        mark = dict(answer=new["answer"], answered=dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z"), approval=e["id"])

        def put_answer(cur):         # the owner's yes took a while: apply it to the list as it is now, never to an old copy
            for x in cur.get("questions", []):
                if x.get("id") == q["id"]:
                    x.update(mark)
        records.tasks_update(project, put_answer)
    elif what == "review":
        if not rest:
            raise SystemExit("growth approve review research/<key>-review-<date>.md")
        p = Path(rest[0])
        p = p if p.is_absolute() else project / p
        if not p.is_file():
            raise SystemExit(f"no file {rest[0]}")
        approve(docs, "review", p.name, p.read_bytes(), f"review sign-off {p.name}", p.read_text(errors="replace")[:1500], tty)
    elif what == "baseline":
        if not rest or len(reason) < 10:
            raise SystemExit('growth approve baseline <key> --reason "why the frozen baseline may be taken again (10+ characters)"')
        approve(docs, "baseline", rest[0], baseline_content(rest[0], reason), f"re-freeze baseline {rest[0]}: {reason[:80]}",
                f"Re-freeze the research baseline of {rest[0]}. Reason: {reason}", tty)
    else:
        raise SystemExit(f"unknown: growth approve {what}. Try growth approve --help")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.exit(main())
