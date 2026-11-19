#!/usr/bin/env python3
"""The page journal: what we found, asked, decided and ran, per page, with time stamps.

Like a person's working notes. Every finding, question, decision and check (an AI-answer prompt, a Google search, a
Search Console pull, an audit) is filed against the page(s) it concerns, so the next person who works on that page,
or the re-check on day 21, 28 or 56, has it all at hand and can compare.

Data (plain files, git-friendly, no server):
  journal/entries.jsonl         one JSON line per entry (append-only; answers and status changes are new lines)
  journal/runs/<date>/<id>.json the full query and the full response of every check we ran
  journal/pages/<slug>.md       one note per page, rebuilt from the entries (Obsidian-ready: open journal/ as a vault)
  journal/INDEX.md              every page with open questions and due re-checks

  growth journal add  --page /pricing --kind finding --tag pricing --title "..." --text "..." \\
                                [--page /other] [--source "..."] [--recheck 2026-12-15]
  growth journal ask  --page /pricing --tag pricing "Question for the owner" [--recheck ...]
  growth journal answer J0007 "The owner's answer" [--by owner]
  growth journal done J0007 "what was done"
  growth journal run  --page /x --kind ai-answer --engine chatgpt --market US --query "..." \\
                                --response-file answer.txt [--title "..."] [--named yes|no] [--recheck ...]
  growth journal action --page /x --due 2026-11-30 --tag listings "What the owner must do" [--why "..."]
  growth journal actions              # the owner's own to-do list (also journal/OWNER-ACTIONS.md)
  growth journal show /pricing        # the page's note
  growth journal due [--days 0]       # re-checks due today (or within N days)
  growth journal open                 # open questions, all pages
  growth journal render               # rebuild pages/*.md and INDEX.md
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

J = PROJECT / "journal"
ENTRIES = J / "entries.jsonl"
PAGES = J / "pages"
RUNS = J / "runs"


def now():
    return dt.datetime.now(TZ).strftime("%Y-%m-%d %H:%M %Z")


def today():
    return dt.datetime.now(TZ).date()


def slug(path):
    s = path.strip("/") or "home"
    return re.sub(r"[^a-z0-9-]+", "-", s.lower()).strip("-")


def load():
    if not ENTRIES.exists():
        return []
    return [json.loads(l) for l in ENTRIES.read_text().splitlines() if l.strip()]


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
    n = sum(1 for e in load() if "of" not in e) + 1
    return f"J{n:04d}"


def append(obj):
    J.mkdir(parents=True, exist_ok=True)
    with ENTRIES.open("a") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def norm_pages(pages):
    out = []
    for p in pages or []:
        p = p.strip()
        if p and not p.startswith("/") and p not in ("site", "off-site"):
            p = "/" + p
        out.append(paths.key(p) if p.startswith("/") else p)   # one form: /x/y, whatever the caller typed
    return out or ["site"]


def cmd_add(a, kind=None, text=None):
    e = {"id": next_id(), "at": now(), "kind": kind or a.kind, "pages": norm_pages(a.page), "tags": a.tag or [],
         "title": a.title or (text or a.text or "")[:90], "text": text or a.text or "", "source": a.source or "",
         "status": "open" if (kind or a.kind) in ("question", "owner-action") else ("open" if a.recheck else "done"),
         "recheck_on": a.recheck or "", "by": "lead"}
    append(e)
    render()
    print(e["id"])


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
    (J / "OWNER-ACTIONS.md").write_text("\n".join(out) + "\n")


def cmd_actions(a):
    rows = [e for e in state().values() if e["kind"] == "owner-action" and e.get("status") == "open"]
    for e in sorted(rows, key=lambda e: (e.get("recheck_on") or "9999", e["id"])):
        print(f"{e['id']}  due {e.get('recheck_on') or 'any time':10}  {e['title']}")
    if not rows:
        print("No open owner actions.")


def cmd_answer(a):
    append({"of": a.id, "at": now(), "status": "answered", "answer": a.text, "answered_by": a.by, "answered_at": now()})
    render()
    print("ok")


def cmd_done(a):
    append({"of": a.id, "at": now(), "status": "done", "done_note": a.text, "done_at": now()})
    render()
    print("ok")


def cmd_run(a):
    rid = next_id()
    d = today().isoformat()
    folder = RUNS / d
    folder.mkdir(parents=True, exist_ok=True)
    resp = Path(a.response_file).read_text() if a.response_file else (a.response or "")
    market = a.market or CFG.get("market", {}).get("primary_country", "")
    run = {"id": rid, "at": now(), "kind": a.kind, "engine": a.engine, "market": market, "settings": a.settings or "",
           "pages": norm_pages(a.page), "query": a.query, "named": a.named or "", "response": resp}
    rf = folder / f"{rid}-{a.engine}-{slug(norm_pages(a.page)[0])}.json"
    rf.write_text(json.dumps(run, ensure_ascii=False, indent=1) + "\n")
    e = {"id": rid, "at": run["at"], "kind": "run", "pages": run["pages"], "tags": (a.tag or []) + [a.kind, a.engine],
         "title": a.title or f"{a.engine} ({market}): {a.query[:70]}", "text": a.summary or "",
         "source": str(rf.relative_to(PROJECT)), "status": "open" if a.recheck else "done", "recheck_on": a.recheck or "",
         "by": "lead", "named": a.named or "", "market": market}
    append(e)
    render()
    print(rid, rf.relative_to(PROJECT))


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
        (PAGES / f"{slug(p)}.md").write_text("\n".join(out))
        idx.append(f"| [[{slug(p)}]] | {len(es)} | {len(openq)} | {len(due)} | {es[-1]['at'] if es else ''} |")
    idx += ["", "Owner action items: [[OWNER-ACTIONS]]"]
    (J / "INDEX.md").write_text("\n".join(idx) + "\n")
    render_actions(cur)


def cmd_show(a):
    p = norm_pages([a.page])[0]
    f = PAGES / f"{slug(p)}.md"
    render()
    print(f.read_text() if f.exists() else f"No entries for {p}.")


def cmd_due(a):
    lim = today() + dt.timedelta(days=a.days)
    rows = [e for e in state().values() if e.get("recheck_on") and e.get("status") == "open"
            and dt.date.fromisoformat(e["recheck_on"]) <= lim]
    for e in sorted(rows, key=lambda e: e["recheck_on"]):
        print(f"{e['recheck_on']}  {e['id']}  {', '.join(e['pages'])}  {e['title']}")
    if not rows:
        print("Nothing due.")


def cmd_open(a):
    rows = [e for e in state().values() if e["kind"] == "question" and e.get("status") == "open"]
    for e in rows:
        print(f"{e['id']}  {', '.join(e['pages'])}  {e['title']}")
    if not rows:
        print("No open questions.")


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
        if name == "add":
            s.add_argument("--kind", default="finding", choices=["finding", "decision", "note", "question"])
            s.add_argument("--text", default="")
        else:
            s.add_argument("question")
    s = sub.add_parser("answer"); s.add_argument("id"); s.add_argument("text"); s.add_argument("--by", default="owner")
    s = sub.add_parser("done"); s.add_argument("id"); s.add_argument("text")
    s = sub.add_parser("run")
    s.add_argument("--page", action="append"); s.add_argument("--tag", action="append")
    s.add_argument("--kind", default="ai-answer"); s.add_argument("--engine", required=True)
    s.add_argument("--market"); s.add_argument("--settings"); s.add_argument("--query", required=True)
    s.add_argument("--response-file"); s.add_argument("--response"); s.add_argument("--title")
    s.add_argument("--summary"); s.add_argument("--named"); s.add_argument("--recheck")
    s = sub.add_parser("action"); s.add_argument("task"); s.add_argument("--page", action="append")
    s.add_argument("--tag", action="append"); s.add_argument("--due"); s.add_argument("--why"); s.add_argument("--source")
    sub.add_parser("actions")
    s = sub.add_parser("show"); s.add_argument("page")
    s = sub.add_parser("due"); s.add_argument("--days", type=int, default=0)
    sub.add_parser("open")
    sub.add_parser("render")
    a = ap.parse_args()
    {"add": cmd_add, "ask": cmd_ask, "answer": cmd_answer, "done": cmd_done, "run": cmd_run, "show": cmd_show,
     "due": cmd_due, "open": cmd_open, "action": cmd_action, "actions": cmd_actions, "render": lambda a: (render(), print("ok"))}[a.cmd](a)


if __name__ == "__main__":
    main()
