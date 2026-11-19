#!/usr/bin/env python3
"""Onboarding health check: is every setup step of book/01-flow.md stage A done for this project?

  growth doctor

Prints one line per step (OK / TODO / FAIL) with the command that fixes it. Read-only: it never changes anything,
never prints a key, and calls the analytics server only to list its tools (only when that connector is switched on).
"""
import json
import re
import sqlite3
import subprocess
import sys
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import CFG, DOCS, KEYS, PROJECT, SITE_REPO, connector_on, keys  # noqa: E402

rows = []


def row(step, ok, what, fix=""):
    rows.append((step, "OK  " if ok is True else ("TODO" if ok is None else "FAIL"), what, "" if ok is True else fix))


LAUNCHD_DIRS = ["~/Library/LaunchAgents", "/Library/LaunchAgents", "/Library/LaunchDaemons"]


def auto_start_jobs(project):
    """The jobs that start THIS project's work with the computer: a launchd plist or a crontab line that runs something
    inside the project folder, or names it (GROWTH_PROJECT=<folder>). Matched on the folder's path, never on the
    business name, so another tool for the same business (its own folder) is not counted.
    GROWTH_LAUNCHD_DIRS (os.pathsep list) and GROWTH_CRONTAB (the crontab text) replace the real ones in tests.
    Known limits: a job that names the folder through ~ or a symlink is not matched (only the project side is resolved),
    and Linux systemd user timers are not checked (nor were they before)."""
    import os
    import plistlib
    folder = re.escape(str(Path(project).resolve()).rstrip("/"))
    mine = re.compile(folder + r"(?=$|[/\\\s\"';:])")
    found = []
    dirs = os.environ["GROWTH_LAUNCHD_DIRS"].split(os.pathsep) if "GROWTH_LAUNCHD_DIRS" in os.environ else LAUNCHD_DIRS
    for d in dirs:
        for f in sorted(Path(d).expanduser().glob("*.plist")):
            try:
                pl = plistlib.loads(f.read_bytes())
            except Exception:  # noqa: BLE001  (unreadable or not a plist)
                continue
            vals = [pl.get("Program", ""), pl.get("WorkingDirectory", ""), *(pl.get("ProgramArguments") or []),
                    *(pl.get("EnvironmentVariables") or {}).values()]
            if any(isinstance(v, str) and mine.search(v) for v in vals):
                found.append(f"launchd {pl.get('Label') or f.stem}")
    cron = os.environ.get("GROWTH_CRONTAB")
    if cron is None:
        try:
            cron = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=10).stdout
        except (OSError, subprocess.SubprocessError):
            cron = ""
    found += [f"cron: {l.strip()[:80]}" for l in cron.splitlines() if l.strip() and not l.lstrip().startswith("#") and mine.search(l)]
    return found


# A1 understand
row("A1 Understand the business and site", any(DOCS.glob("01-*.md")) or None,
    f"{DOCS.name}/01-*.md", "write docs/01-project-understanding.md (book/01-flow.md A1)")
# A2 project adapted: no words of a previous site (growth.json old_brand_words) left in the project folder
leftover = []
if CFG.get("old_brand_words"):
    leftover = subprocess.run(["grep", "-rliIE", CFG["old_brand_words"], str(PROJECT), "--exclude-dir=.git",
                               "--exclude-dir=research", "--exclude-dir=inventory", "--exclude-dir=.claude",
                               "--exclude-dir=journal", "--exclude-dir=archive", "--exclude=*.db", "--exclude=growth.json"],
                              capture_output=True, text=True).stdout.split()
row("A2 Project adapted to this business", not leftover and bool(CFG.get("site_url")),
    "growth.json filled in + no old-brand words" + (f" ({len(leftover)} files still mention the old site)" if leftover else ""),
    "fill in growth.json (site_url, name, product) and rewrite the files that still name the old site")
# A3 site repo studied (optional: a site with no code checkout is read through its live pages only)
if not CFG.get("site_repo"):
    row("A3 Site repo cloned and studied", True, "no site repo (growth.json site_repo is empty): live-page checks only")
else:
    ok3 = (SITE_REPO / ".git").exists()
    row("A3 Site repo cloned and studied", (ok3 and any(DOCS.glob("02-*.md"))) or (False if not ok3 else None),
        f"{SITE_REPO.name} cloned; {DOCS.name}/02-*.md", f"git clone {CFG.get('site_repo_remote') or '<the site repo>'}; write docs/02-<site>.md")
# A4 connectors (optional): analytics, Search Console, Bing, each switched on in growth.json "connectors"
on = [n for n in (CFG.get("connectors") or {}) if not n.startswith("_") and n != "google_updates" and connector_on(n)]  # google_updates needs no key
if not on:
    row("A4 Analytics + Search Console connected", True, "no connectors switched on (growth.json connectors): optional, the tools run without them")
elif KEYS is None or not KEYS.exists():
    row("A4 Analytics + Search Console connected", False, f"connectors on ({', '.join(on)}) but the keys file is missing",
        "set keys_file in growth.json to a file outside git (book/01-flow.md A4)")
else:
    mode = oct(KEYS.stat().st_mode & 0o777)
    env = keys()
    try:
        n = 6
        if "skald" in on:
            req = urllib.request.Request(env["SKALD_MCP_URL"], data=b'{"jsonrpc":"2.0","id":1,"method":"tools/list"}',
                                         headers={"Authorization": "Bearer " + env["SKALD_MCP_TOKEN"],
                                                  "Content-Type": "application/json", "Accept": "application/json, text/event-stream"})
            n = len(re.findall(r'"name"', urllib.request.urlopen(req, timeout=30).read().decode()))
        row("A4 Analytics + Search Console connected", mode == "0o600" and n > 5 or (None if n > 5 else False),
            f"keys file {mode}; connectors on: {', '.join(on)}", "chmod 600 the keys file" if mode != "0o600" else "re-run book/01-flow.md A4")
    except Exception as e:
        row("A4 Analytics + Search Console connected", False, f"analytics call failed: {type(e).__name__}", "check the keys file and network")
# A5 control check
setup_f = PROJECT / "SETUP.md"
setup = setup_f.read_text() if setup_f.exists() else ""
row("A5 Control of the live site proven", bool(re.search(r"Control check[^\n]*\| *done", setup)) or None,
    "SETUP.md 'Control check' row says done", "book/01-flow.md A5: tiny visible edit, owner checks, roll back")
# A6 task tracker
try:
    t = json.loads((DOCS / "tasks.json").read_text())
    open_t = sum(1 for x in t["tasks"] if x.get("status") != "done")
    open_q = sum(1 for q in t.get("questions", []) if not q.get("answer"))
    row("A6 Task tracker", True, f"{len(t['tasks'])} tasks ({open_t} open), {open_q} open owner questions")
except Exception:
    row("A6 Task tracker", False, "docs/tasks.json missing or unreadable", "growth tasks add ... (book/01-flow.md A6)")
# A7 inventory: read the pages from the preview (a local build) when there is one, never page by page from the live site
INVENTORY_FIX = (f"build the site, serve it, then growth inventory --base {CFG['preview_url']}" if CFG.get("preview_url")
                 else "growth inventory (run a production build of the site first for page elements)")
inv = PROJECT / "inventory" / "inventory.json"
if inv.exists():
    meta = json.loads(inv.read_text())["meta"]
    pages = json.loads(inv.read_text())["pages"]
    # a live page marked noindex is left out of the sitemap on purpose
    live = sum(1 for p in pages if p["status"] == "live" and not p.get("noindex"))
    fresh = meta["generated"][:10] >= (date.today() - timedelta(days=7)).isoformat()
    row("A7 Full site inventory", (live == meta["sitemap_urls"] and fresh) or None,
        f"{live} live pages vs {meta['sitemap_urls']} in the sitemap; built {meta['generated']}",
        INVENTORY_FIX)
else:
    row("A7 Full site inventory", False, "inventory/inventory.json missing", INVENTORY_FIX)
# A7b site link graph
lg = PROJECT / "inventory" / "link-graph.db"
if lg.exists():
    age = (datetime.now() - datetime.fromtimestamp(lg.stat().st_mtime)).days
    try:
        n = sqlite3.connect(f"file:{lg}?mode=ro", uri=True).execute("select count(*) from links").fetchone()[0]
    except Exception:
        n = 0
    row("A7b Site link graph", (age < 8 and n > 0) or None, f"link-graph.db: {n} links, {age} day(s) old",
        "growth link_graph crawl (weekly, or after each release)")
else:
    row("A7b Site link graph", False, "inventory/link-graph.db missing", "growth link_graph crawl; then report (book/01-flow.md A7b)")
# A8 tracker running + backfilled, no auto-start
db = PROJECT / "page-tracker" / "tracker.db"
auto_jobs = auto_start_jobs(PROJECT)
jobs_note = f"auto-start jobs: {len(auto_jobs)}" + (f" ({', '.join(auto_jobs)})" if auto_jobs else "")
if db.exists():
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        lo, hi = c.execute("select min(day), max(day) from search where path='*'").fetchone()
    except sqlite3.Error:
        lo = hi = None
    start = CFG.get("search_console_history_start")
    ok8 = (lo == start or not start) and hi and hi >= (date.today() - timedelta(days=3)).isoformat() and not auto_jobs
    row("A8 Page tracker running, history backfilled", ok8 or None,
        f"Search Console {lo} to {hi} (history starts {start}); {jobs_note}",
        "growth page-tracker sync | growth page-tracker search-history | remove any auto-start job")
else:
    row("A8 Page tracker running, history backfilled", False, f"page-tracker/tracker.db missing; {jobs_note}",
        "growth page-tracker sync (book/01-flow.md A8)" + (" | remove any auto-start job" if auto_jobs else ""))

# A9 the owner's journal page is current
_oj = PROJECT / "journal" / "owner-journal.html"
_src = [DOCS / "steps-log.md", PROJECT / "journal" / "entries.jsonl"]
_fresh = _oj.exists() and all(_oj.stat().st_mtime >= p.stat().st_mtime - 1 for p in _src if p.exists())
row("A9 Owner journal page current", _fresh, "journal/owner-journal.html is newer than the steps log and the journal"
    if _fresh else "journal/owner-journal.html is older than the steps log or the journal", "growth owner_journal --no-open")

# A10 the agent's guards: the Stop hook is wired into Claude Code's settings for this project
_settings = PROJECT / ".claude" / "settings.json"
_hook = False
try:
    _hook = "stop_hook.sh" in json.dumps(json.loads(_settings.read_text()).get("hooks", {}).get("Stop", []))
except (OSError, ValueError, AttributeError):
    pass
row("A10 Agent guards installed (Stop hook)", _hook, ".claude/settings.json runs kit/hooks/stop_hook.sh when the agent stops"
    if _hook else ".claude/settings.json has no Stop hook, so nothing stops an agent that skips the rules",
    "growth new-project <this folder> --site <url> --force   (adds the missing .claude files; never overwrites)")

# A11 the golden rule's guard needs the one preview address
_pv = (CFG.get("preview_url") or "").strip()
row("A11 Preview address set (golden rule guard)", True if _pv else None,
    f"preview_url {_pv}" if _pv else "preview_url is empty: no guard stops an address going to the owner before READY",
    "set preview_url in growth.json to the one address every review happens on (book/01-flow.md A11)")

w = max(len(r[0]) for r in rows)
print(f"{CFG.get('name', 'This project')} growth setup ({CFG.get('site_url', 'no site_url')})\n")
for step, st, what, fix in rows:
    print(f"{st}  {step.ljust(w)}  {what}" + (f"\n      fix: {fix}" if fix else ""))
done = sum(1 for r in rows if r[1] == "OK  ")
print(f"\n{done}/{len(rows)} setup steps done." + ("" if done == len(rows) else " Page work starts only when all are OK (book/01-flow.md)."))
sys.exit(0 if all(r[1] != "FAIL" for r in rows) else 1)
