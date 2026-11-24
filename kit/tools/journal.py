#!/usr/bin/env python3
"""The page journal: what we found, asked, decided and ran, per page, with time stamps.

Like a person's working notes. Every finding, question, decision and check (an AI-answer prompt, a Google search, a
Search Console pull, an audit) is filed against the page(s) it concerns, so the next person who works on that page,
or the re-check on day 21, 28 or 56, has it all at hand and can compare.

Data: the entries live in the project's database (state/growth.db, through records.py); their readable, git-friendly mirror
is a plain file (no server):
  journal/entries.jsonl         one JSON line per entry (append-only; answers and status changes are new lines)
  journal/runs/<date>/<id>.json the full query and the full response of every check we ran
  journal/pages/<slug>.md       one note per page, rebuilt from the entries (Obsidian-ready: open journal/ as a vault)
  journal/INDEX.md              every page with open questions and due re-checks

  growth journal add  --page /pricing --kind finding --tag pricing --title "..." --text "..." \\
                                [--page /other] [--source "..."] [--recheck 2026-12-15]
  growth journal ask  --page /pricing --tag pricing "Question for the owner" [--recheck ...]
  growth journal answer J0007 "The owner's answer"   # the owner only: goes through growth approve answer (their own terminal)
  growth journal done J0007 "what was done"
  growth journal close J0007 --output "commit abc1234, the fix and its proof"   # closes a finding; the output is required
  growth journal run  --page /x --kind ai-answer --engine chatgpt --market US --query "..." \\
                                --response-file answer.txt [--capture-method browser] [--title "..."] [--named yes|no] [--recheck ...]
  growth journal action --page /x --due 2026-11-30 --tag listings "What the owner must do" [--why "..."]
  growth journal actions              # the owner's own to-do list (also journal/OWNER-ACTIONS.md)
  growth journal show /pricing        # the page's note
  growth journal due [--days 0]       # re-checks due today (or within N days)
  growth journal open                 # open questions, all pages
  growth journal render               # rebuild pages/*.md and INDEX.md
A new finding starts OPEN and stays open (ev.open-findings fails on one older than 7 days) until `journal close`.
Kinds: finding, question, decision, run, note, owner-action (things only the owner can do, kept as a separate list). Status: open, answered, done.
"""
import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import PROJECT, TZ, CFG  # noqa: E402
import paths  # noqa: E402  (one form of a site path)
import atomic  # noqa: E402  (lock + atomic write: the page notes are rebuilt under one lock)
import records  # noqa: E402  (the one access layer: ids are taken inside the write transaction, so parallel adds never clash)

J = PROJECT / "journal"
ENTRIES = records.journal_path(PROJECT)   # the mirror file
PAGES = J / "pages"
RUNS = J / "runs"


def now():
    """Stored time: ISO 8601 to the minute with the UTC offset, e.g. 2026-11-19 06:48-05:00 (the zone is part of the value)."""
    return dt.datetime.now(TZ).isoformat(sep=" ", timespec="minutes")


_LEGACY_AT = re.compile(r"^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}) ([A-Za-z]{2,5})$")


def parse_at(value):
    """A journal time as an aware datetime, or None when it is not a real time with a zone.

    Accepts ISO 8601 with an offset ("2026-11-19 06:48-05:00", "2026-11-19T06:48:00Z") and the older "2026-11-19 06:48 EST"
    form only when the zone name is UTC/GMT or is the project's own timezone name at that moment. Anything else (no zone,
    a made-up zone, text) is None: callers must ignore such an entry, never count it as fresh."""
    if not isinstance(value, str) or not value.strip():
        return None
    v = value.strip()
    m = _LEGACY_AT.match(v)
    if m:
        try:
            naive = dt.datetime.strptime(f"{m.group(1)} {m.group(2)}", "%Y-%m-%d %H:%M")
        except ValueError:
            return None
        if m.group(3).upper() in ("UTC", "GMT"):
            return naive.replace(tzinfo=dt.timezone.utc)
        local = naive.replace(tzinfo=TZ)
        return local if local.tzname() == m.group(3) else None
    try:
        d = dt.datetime.fromisoformat(v)
    except ValueError:
        return None
    return d if d.tzinfo is not None and d.utcoffset() is not None else None


def today():
    return dt.datetime.now(TZ).date()


def slug(path):
    """The page's folder/note name: paths.snapshot_slug, the same one every tool uses ("site"/"off-site" stay words)."""
    return paths.snapshot_slug(path) if path.startswith("/") else (re.sub(r"[^a-z0-9-]+", "-", path.lower()).strip("-") or "site")


def load():
    """Every entry with a readable time. A line with a bad or zone-less time (or broken JSON) is left out and reported on
    stderr, so an edited or damaged entry can never count as fresh."""
    if not records.journal_present(PROJECT):
        return []
    out = []
    for n, l in enumerate(records.journal_lines(PROJECT), 1):
        if not l.strip():
            continue
        try:
            e = json.loads(l)
        except ValueError:
            print(f"journal: line {n} of entries.jsonl is not valid JSON and is ignored", file=sys.stderr)
            continue
        if parse_at(e.get("at")) is None:
            print(f"journal: {e.get('id') or e.get('of') or 'line ' + str(n)} has an unreadable time {e.get('at')!r} "
                  f"(needs an ISO time with a zone) and is ignored", file=sys.stderr)
            continue
        out.append(e)
    return out


def state():
    """Fold the append-only lines into the current entries (updates carry `of`)."""
    cur = {}
    for e in load():
        if "of" in e:
            if e["of"] in cur:
                base = cur[e["of"]]
                base.setdefault("history", []).append({k: v for k, v in e.items() if k != "of"})
                for k in ("status", "answer", "answered_by", "answered_at", "done_note", "done_at"):
                    if k in e:
                        base[k] = e[k]
        else:
            cur[e["id"]] = dict(e)
    return cur


def next_id():
    """The id the next entry would get: a peek only. cmd_add and cmd_run take the real id inside the write transaction
    (records.journal_add), so two writers never get the same one. It counts the highest id used, not the lines, so an
    ignored line never makes an id repeat."""
    return records.journal_next_id(PROJECT)


def append(obj):
    """File an entry that is complete (it has its id, or it is an update line with `of`)."""
    records.journal_append(PROJECT, obj)


def norm_pages(pages):
    out = []
    for p in pages or []:
        p = p.strip()
        if p and not p.startswith("/") and p not in ("site", "off-site"):
            p = "/" + p
        out.append(paths.key(p) if p.startswith("/") else p)   # one form: /x/y, whatever the caller typed
    return out or ["site"]


def check_date(value, what="--recheck"):
    """A re-check date must be a real YYYY-MM-DD date; anything else would crash `journal due` later (#52)."""
    if not value:
        return ""
    try:
        return dt.date.fromisoformat(value).isoformat()
    except ValueError:
        sys.exit(f"{what} must be a real date as YYYY-MM-DD, got '{value}'")


def attach_fingerprint(e, url=""):
    """Evidence entries (click-test, share-preview, speed) store the page's fingerprint (fingerprint.py), so the gate can tell
    the page's built output has not changed since. Best effort: with no build to read nothing is stored."""
    import fingerprint
    from config import SITE_REPO
    fingerprint.attach(e, CFG, PROJECT, SITE_REPO if CFG.get("site_repo") else None, url)


def cmd_add(a, kind=None, text=None):
    a.recheck = check_date(a.recheck)
    e = {"id": None, "at": now(), "kind": kind or a.kind, "pages": norm_pages(a.page), "tags": a.tag or [],
         "title": a.title or (text or a.text or "")[:90], "text": text or a.text or "", "source": a.source or "",
         "status": "open" if (kind or a.kind) in ("question", "owner-action", "finding") else ("open" if a.recheck else "done"),
         "recheck_on": a.recheck or "", "by": "lead"}
    attach_fingerprint(e, getattr(a, "url", "") or "")
    e = records.journal_add(PROJECT, lambda jid: {**e, "id": jid})     # the id is taken inside the write transaction
    render()
    print(e["id"])
    if e["kind"] == "decision":
        print(f"A decision counts only when the owner approves it: the owner runs   growth approve decision {e['id']}   "
              "in their own terminal.")


def cmd_ask(a):
    a.title = a.title or a.question
    cmd_add(a, kind="question", text=a.question)


def cmd_action(a):
    a.title = a.task
    a.kind = "owner-action"
    a.recheck = a.due
    cmd_add(a, kind="owner-action", text=a.task + (f"\nWhy: {a.why}" if a.why else ""))


def render_actions(cur):
    rows = [e for e in cur.values() if e["kind"] == "owner-action"]
    out = ["# Owner action items", "",
           "Things only the owner can do (outside the site, accounts, money, decisions on listings). Kept apart from the",
           "page notes so nothing gets lost in a report. Add with `growth journal action`; close with",
           "`growth journal done <id> \"what was done\"`. Rebuilt " + now() + ".", "",
           "## Open", "", "| # | Action | Why | Pages | Due | Added |", "| --- | --- | --- | --- | --- | --- |"]
    for e in sorted([r for r in rows if r.get("status") == "open"], key=lambda e: (e.get("recheck_on") or "9999", e["id"])):
        task, _, why = e["text"].partition("\nWhy: ")
        out.append(f"| {e['id']} | {task} | {why} | {', '.join(e['pages'])} | {e.get('recheck_on') or 'any time'} | {e['at'][:10]} |")
    out += ["", "## Done", "", "| # | Action | Done | Note |", "| --- | --- | --- | --- |"]
    for e in [r for r in rows if r.get("status") != "open"]:
        out.append(f"| {e['id']} | {e['title']} | {e.get('done_at', '')} | {e.get('done_note', '')} |")
    atomic.write_text(J / "OWNER-ACTIONS.md", "\n".join(out) + "\n")


def cmd_actions(a):
    rows = [e for e in state().values() if e["kind"] == "owner-action" and e.get("status") == "open"]
    for e in sorted(rows, key=lambda e: (e.get("recheck_on") or "9999", e["id"])):
        print(f"{e['id']}  due {e.get('recheck_on') or 'any time':10}  {e['title']}")
    if not rows:
        print("No open owner actions.")


def cmd_answer(a):
    """The owner's answer is the owner's act: typed in their own terminal and logged in the approvals log (growth approve
    answer). The journal line is written by that approval, never by an agent's own command."""
    if state().get(a.id) is None:
        sys.exit(f"no entry {a.id}")
    import approvals
    approvals.main(["answer", a.id, a.text])
    print("ok")


def cmd_done(a):
    append({"of": a.id, "at": now(), "status": "done", "done_note": a.text, "done_at": now()})
    render()
    print("ok")


def cmd_close(a):
    if not (a.output or "").strip():
        sys.exit("journal close needs --output: what was done and its proof (a commit, a file, a run id)")
    cur = state().get(a.id)
    if cur is None:
        sys.exit(f"no entry {a.id}")
    append({"of": a.id, "at": now(), "status": "done", "done_note": a.output.strip(), "done_at": now()})
    render()
    print("ok")


def cmd_run(a):
    a.recheck = check_date(a.recheck)
    d = today().isoformat()
    folder = RUNS / d
    import hashlib
    raw = Path(a.response_file).read_bytes() if a.response_file else (a.response or "").encode()
    resp = raw.decode("utf-8", errors="replace")
    sha = hashlib.sha256(raw).hexdigest()
    method = a.capture_method or ("response-file" if a.response_file else "typed-inline")
    market = a.market or CFG.get("market", {}).get("primary_country", "")
    pages = norm_pages(a.page)
    tags = (a.tag or []) + [a.kind, a.engine]
    fp = {"tags": tags, "pages": pages}
    attach_fingerprint(fp, getattr(a, "url", "") or "")      # before the transaction: it may read the preview
    made = {}

    def make(rid):            # runs inside the write transaction, with the id this entry gets
        folder.mkdir(parents=True, exist_ok=True)
        run = {"id": rid, "at": now(), "kind": a.kind, "engine": a.engine, "market": market, "settings": a.settings or "",
               "pages": pages, "query": a.query, "named": a.named or "", "response": resp,
               "response_sha256": sha, "capture_method": method}
        rf = folder / f"{rid}-{a.engine}-{slug(pages[0])}.json"
        atomic.write_text(rf, json.dumps(run, ensure_ascii=False, indent=1) + "\n")
        made["rf"] = rf
        e = {"id": rid, "at": run["at"], "kind": "run", "pages": run["pages"], "tags": tags,
             "title": a.title or f"{a.engine} ({market}): {a.query[:70]}", "text": a.summary or "",
             "source": str(rf.relative_to(PROJECT)), "status": "open" if a.recheck else "done", "recheck_on": a.recheck or "",
             "by": "lead", "named": a.named or "", "market": market, "response_sha256": sha, "capture_method": method}
        if "fp" in fp:
            e["fp"] = fp["fp"]
        return e
    e = records.journal_add(PROJECT, make)
    render()
    print(e["id"], made["rf"].relative_to(PROJECT))


def page_entries(cur, page):
    k = paths.key(page)
    return [e for e in cur.values() if k in {paths.key(x) for x in e["pages"]}]


def fmt(e):
    head = f"- **{e['id']}** · {e['at']} · {e['kind']}"
    if e.get("tags"):
        head += " · " + " ".join("#" + t.replace(" ", "-") for t in e["tags"])
    head += f" · {e.get('status', '')}"
    lines = [head, f"  **{e['title']}**"]
    if e.get("text") and e["text"] != e["title"]:
        lines.append("  " + e["text"].replace("\n", "\n  "))
    if e.get("named"):
        lines.append(f"  Named us: {e['named']} · market {e.get('market', '')}")
    if e.get("source"):
        src = e["source"]
        lines.append(f"  Source: [[{src}]]" if src.startswith("journal/") or src.startswith("research/") else f"  Source: {src}")
    if e.get("recheck_on"):
        lines.append(f"  Re-check on: {e['recheck_on']}")
    if e.get("answer"):
        lines.append(f"  Answer ({e.get('answered_by', '')}, {e.get('answered_at', '')}): {e['answer']}")
    if e.get("done_note"):
        lines.append(f"  Done ({e.get('done_at', '')}): {e['done_note']}")
    others = [p for p in e["pages"]]
    if len(others) > 1:
        lines.append("  Also on: " + ", ".join(f"[[{slug(p)}]]" for p in others))
    return "\n".join(lines)


def render():
    """Rebuild the page notes, the index and the owner's page from the entries. One rebuild at a time (a second one waits and
    then reads the newest entries), so the notes never go back to an older state."""
    with atomic.locked(J / "journal"):
        _render_notes()
        try:  # the owner's one-page journal (from a real project: "keeping the journals updated is your job")
            import owner_journal
            owner_journal.build()
        except Exception as e:  # noqa: BLE001  never lose a journal write over the page
            print(f"owner journal page not rebuilt: {e}", file=sys.stderr)


def _render_notes():
    cur = state()
    PAGES.mkdir(parents=True, exist_ok=True)
    pages = sorted({paths.key(p) if p.startswith("/") else p for e in cur.values() for p in e["pages"]})   # /x and /x/ are one page
    idx = ["# Page journal index", "", f"Rebuilt {now()} by `growth journal render`. Open `journal/` as an Obsidian vault.",
           "", "| Page | Entries | Open questions | Re-checks due | Last entry |", "| --- | --- | --- | --- | --- |"]
    for p in pages:
        es = sorted(page_entries(cur, p), key=lambda e: e["id"])
        openq = [e for e in es if e["kind"] == "question" and e.get("status") == "open"]
        due = [e for e in es if e.get("recheck_on") and e.get("status") == "open"]
        out = ["---", f"page: \"{p}\"", f"slug: {slug(p)}", f"updated: {now()}",
               "tags: [" + ", ".join(sorted({t for e in es for t in e.get('tags', [])})) + "]", "---", "",
               f"# {p}", "", "Rebuilt from `journal/entries.jsonl`; add entries with `growth journal`, never edit this file.", ""]
        for title, sel in (("Open questions", openq),
                           ("Re-checks due", due),
                           ("Findings", [e for e in es if e["kind"] == "finding"]),
                           ("Decisions", [e for e in es if e["kind"] == "decision"]),
                           ("Checks we ran (queries and responses)", [e for e in es if e["kind"] == "run"]),
                           ("Owner action items", [e for e in es if e["kind"] == "owner-action"]),
                           ("Answered and done questions", [e for e in es if e["kind"] == "question" and e.get("status") != "open"]),
                           ("Notes", [e for e in es if e["kind"] == "note"])):
            out += [f"## {title}", ""] + ([fmt(e) for e in sel] or ["- none"]) + [""]
        atomic.write_text(PAGES / f"{slug(p)}.md", "\n".join(out))
        idx.append(f"| [[{slug(p)}]] | {len(es)} | {len(openq)} | {len(due)} | {es[-1]['at'] if es else ''} |")
    idx += ["", "Owner action items: [[OWNER-ACTIONS]]"]
    atomic.write_text(J / "INDEX.md", "\n".join(idx) + "\n")
    render_actions(cur)


def cmd_show(a):
    p = norm_pages([a.page])[0]
    f = PAGES / f"{slug(p)}.md"
    render()
    print(f.read_text() if f.exists() else f"No entries for {p}.")


def cmd_due(a):
    lim = today() + dt.timedelta(days=a.days)
    rows = []
    for e in state().values():
        if e.get("recheck_on") and e.get("status") == "open":
            try:
                if dt.date.fromisoformat(e["recheck_on"]) <= lim:
                    rows.append(e)
            except ValueError:   # a bad date filed before it was validated: show it, never crash
                print(f"BAD DATE '{e['recheck_on']}'  {e['id']}  {', '.join(e['pages'])}  {e['title']}", file=sys.stderr)
    for e in sorted(rows, key=lambda e: e["recheck_on"]):
        print(f"{e['recheck_on']}  {e['id']}  {', '.join(e['pages'])}  {e['title']}")
    if not rows:
        print("Nothing due.")


def cmd_open(a):
    rows = [e for e in state().values() if e["kind"] in ("question", "finding") and e.get("status") == "open"]
    for e in rows:
        print(f"{e['id']}  {e['kind']:8}  {', '.join(e['pages'])}  {e['title']}")
    if not rows:
        print("No open questions or findings.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("add", "ask"):
        s = sub.add_parser(name)
        s.add_argument("--page", action="append")
        s.add_argument("--tag", action="append")
        s.add_argument("--title")
        s.add_argument("--source")
        s.add_argument("--recheck")
        s.add_argument("--url", default="", help="the page's preview address, read for its fingerprint when there is no build_dir")
        if name == "add":
            s.add_argument("--kind", default="finding", choices=["finding", "decision", "note", "question"])
            s.add_argument("--text", default="")
        else:
            s.add_argument("question")
    s = sub.add_parser("answer"); s.add_argument("id"); s.add_argument("text"); s.add_argument("--by", default="owner")
    s = sub.add_parser("done"); s.add_argument("id"); s.add_argument("text")
    s = sub.add_parser("close"); s.add_argument("id"); s.add_argument("--output", required=True)
    s = sub.add_parser("run")
    s.add_argument("--page", action="append"); s.add_argument("--tag", action="append")
    s.add_argument("--kind", default="ai-answer"); s.add_argument("--engine", required=True)
    s.add_argument("--market"); s.add_argument("--settings"); s.add_argument("--query", required=True)
    s.add_argument("--response-file"); s.add_argument("--response"); s.add_argument("--title")
    s.add_argument("--url", default=""); s.add_argument("--summary"); s.add_argument("--named"); s.add_argument("--recheck")
    s.add_argument("--capture-method", help="how the answer was captured: browser, api, copied, ... (default: response-file or typed-inline)")
    s = sub.add_parser("action"); s.add_argument("task"); s.add_argument("--page", action="append")
    s.add_argument("--tag", action="append"); s.add_argument("--due"); s.add_argument("--why"); s.add_argument("--source")
    sub.add_parser("actions")
    s = sub.add_parser("show"); s.add_argument("page")
    s = sub.add_parser("due"); s.add_argument("--days", type=int, default=0)
    sub.add_parser("open")
    sub.add_parser("render")
    a = ap.parse_args()
    fn = {"add": cmd_add, "ask": cmd_ask, "answer": cmd_answer, "done": cmd_done, "close": cmd_close, "run": cmd_run, "show": cmd_show,
          "due": cmd_due, "open": cmd_open, "action": cmd_action, "actions": cmd_actions, "render": lambda a: (render(), print("ok"))}[a.cmd]
    return fn(a)       # an entry takes its id and adds its line inside one transaction (records.journal_add); render() has its own lock


if __name__ == "__main__":
    main()
