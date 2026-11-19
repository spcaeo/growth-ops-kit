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
    """ok: True (OK), None (TODO), False (FAIL), or "busy" (BUSY: a normal moment of work in progress, such as a database
    being written or a page about to be rebuilt; it counts as done and never fails the run)."""
    st = "OK  " if ok is True else ("BUSY" if ok == "busy" else ("TODO" if ok is None else "FAIL"))
    rows.append((step, st, what, "" if ok is True or ok == "busy" else fix))


def port_in_use(port):
    import socket
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


def port_is_our_tracker(port):
    """True when what answers on the port is a page tracker dashboard."""
    try:
        return b"page change tracker" in urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2).read(200_000)
    except Exception:  # noqa: BLE001
        return False


def a5_state(setup_text, repo=None):
    """(ok, what) for the 'Control check' row of SETUP.md: the status cell (the last one) says done, and the row names at
    least one commit id. With a site repo, every id must exist in it (git cat-file), so a made-up id does not pass."""
    line = next((l for l in setup_text.splitlines() if "Control check" in l and "|" in l), None)
    if line is None:
        return None, "SETUP.md has no 'Control check' row"
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    status = re.sub(r"<[^>]*>", "", cells[-1])           # a template placeholder such as <fill in: done or not> is not an answer
    ids = [m for m in re.findall(r"\b[0-9a-f]{7,40}\b", " ".join(cells[1:])) if re.search(r"\d", m)]
    if not re.search(r"\bdone\b", status, re.I):
        return None, "SETUP.md 'Control check' row does not say done in its status cell"
    if not ids:
        return None, "SETUP.md 'Control check' row says done but names no commit id (the release and the rollback)"
    if repo is not None:
        bad = [i for i in ids if subprocess.run(["git", "-C", str(repo), "cat-file", "-e", f"{i}^{{commit}}"], capture_output=True).returncode]
        if bad:
            return None, f"SETUP.md 'Control check' row names commit ids not found in the site repo: {', '.join(bad)}"
    return True, "SETUP.md 'Control check' row says done, with commit ids" + (" found in the site repo" if repo is not None else "")


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
# A2 project adapted: no words of a previous site (growth.json old_brand_words) left in the project folder or the built site
SKIP_DIRS = {".git", "research", "inventory", ".claude", "journal", "archive", "node_modules", "page-tracker"}
QUOTE_FILES = {"growth.json", "steps-log.md", "owner-messages-map.json"}   # the definition, and logs that quote the owner
BAN_LINE = re.compile(r"\bnever\b|\bbann?ed\b|\bdo not (?:use|say|write)\b|\bnot to (?:use|say)\b|old_brand_words", re.I)
SITE_EXT = {".html", ".htm", ".txt", ".xml", ".md", ".json", ".webmanifest"}


def old_brand_hits(words, root, skip_dirs=(), skip_files=(), exts=None):
    """(files searched, files with a line naming an old-brand word), except lines that BAN the words (a brand sheet's
    "never say" line) and the files that define or quote them."""
    rx, hits, searched = re.compile(words, re.I), [], 0
    for f in sorted(Path(root).rglob("*")):
        rel = f.relative_to(root)
        if not f.is_file() or any(part in skip_dirs for part in rel.parts[:-1]) or f.name in skip_files:
            continue
        if exts is not None and f.suffix.lower() not in exts or f.suffix in (".db", ".sqlite") or f.stat().st_size > 5_000_000:
            continue
        try:
            text = f.read_text(errors="strict")
        except (UnicodeDecodeError, OSError):
            continue
        searched += 1
        if any(rx.search(l) and not BAN_LINE.search(l) for l in text.splitlines()):
            hits.append(str(rel))
    return searched, hits


def built_site():
    """The built site to search: growth.json build_dir (relative to site_repo, or absolute), else site_dir."""
    b = CFG.get("build_dir")
    if b:
        q = Path(b).expanduser()
        return q if q.is_absolute() else (SITE_REPO / q if CFG.get("site_repo") else PROJECT / q)
    return PROJECT / CFG["site_dir"] if CFG.get("site_dir") else None


leftover, site_hits, site_note, site_ok = [], [], "", True
if CFG.get("old_brand_words"):
    n_proj, leftover = old_brand_hits(CFG["old_brand_words"], PROJECT, SKIP_DIRS, QUOTE_FILES)
    site = built_site()
    if site is None:
        site_ok, site_note = None, "; built site not searched: set growth.json build_dir (the production build)"
    elif not site.is_dir():
        site_ok, site_note = None, f"; built site not searched: {site.resolve()} does not exist (build the site)"
    else:
        n_site, site_hits = old_brand_hits(CFG["old_brand_words"], site, exts=SITE_EXT)
        if n_site == 0:
            site_ok, site_note = None, f"; built site not searched: no page files in {site.resolve()} (build the site)"
        else:
            site_note = f"; built site {site.resolve()}: {n_site} files searched, {len(site_hits)} mention the old brand"
    site_note = f"; project: {n_proj} files searched, {len(leftover)} mention the old brand" + site_note
bad = leftover + [f"site: {h}" for h in site_hits]
ok2 = bool(CFG.get("site_url")) and not bad and site_ok
row("A2 Project adapted to this business", ok2 if ok2 or bad or not CFG.get("site_url") else None,
    "growth.json filled in + no old-brand words" + site_note
    + (f" (still named in: {', '.join(bad[:5])})" if bad else ""),
    "fill in growth.json (site_url, name, product), rewrite the files that still name the old site, "
    "and set build_dir to a production build so the site is searched too")
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
_a5_ok, _a5_what = a5_state(setup, SITE_REPO if CFG.get("site_repo") and (SITE_REPO / ".git").exists() else None)
row("A5 Control of the live site proven", _a5_ok, _a5_what,
    "book/01-flow.md A5: tiny visible edit, owner checks, roll back; then fill the row: the commit ids and 'done'")
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
    locked = False                       # a sync is writing right now: wait, it is not a fault
    try:
        lo, hi = c.execute("select min(day), max(day) from search where path='*'").fetchone()
    except sqlite3.Error as e:
        lo = hi = None
        locked = "locked" in str(e).lower() or "busy" in str(e).lower()
    start = CFG.get("search_console_history_start")
    # with a site repo, the tracker must know which file each page is built from, or no change is ever measured
    try:
        n_files, n_changes = c.execute("select count(file), (select count(*) from changes) from pages").fetchone()
    except sqlite3.Error as e:
        n_files = n_changes = None
        locked = locked or "locked" in str(e).lower() or "busy" in str(e).lower()
    measured = not CFG.get("site_repo") or bool(n_changes)
    ok8 = (lo == start or not start) and hi and hi >= (date.today() - timedelta(days=3)).isoformat() and not auto_jobs and measured
    _port = int(CFG.get("tracker_port", 18700))
    _foreign = port_in_use(_port) and not port_is_our_tracker(_port)
    jobs_note += f"; port {_port} is in use by another program" if _foreign else ""
    st8 = True if ok8 else (False if not measured else None)
    if locked and st8 is not True:
        st8, jobs_note = "busy", jobs_note + "; database is busy (a sync is writing), check again in a minute"
    elif _foreign and st8 is True:
        st8 = None
    row("A8 Page tracker running, history backfilled", st8,
        f"Search Console {lo} to {hi} (history starts {start}); {jobs_note}"
        + (f"; pages with a content file: {n_files}, changes tracked: {n_changes}" if CFG.get("site_repo") else ""),
        ("set growth.json page_tracker.content_globs (or content_dirs / page_sources) so pages map to their files, then "
         "growth page-tracker sync" if not measured else
         "growth page-tracker sync | growth page-tracker search-history | remove any auto-start job"
         + (f" | set tracker_port in growth.json to a free port ({_port} is taken)" if _foreign else "")))
else:
    row("A8 Page tracker running, history backfilled", False, f"page-tracker/tracker.db missing; {jobs_note}",
        "growth page-tracker sync (book/01-flow.md A8)" + (" | remove any auto-start job" if auto_jobs else ""))

# A9 the owner's journal page is current
_oj = PROJECT / "journal" / "owner-journal.html"
_src = [DOCS / "steps-log.md", PROJECT / "journal" / "entries.jsonl"]
_fresh = _oj.exists() and all(_oj.stat().st_mtime >= p.stat().st_mtime - 1 for p in _src if p.exists())
_newest = max([p.stat().st_mtime for p in _src if p.exists()] or [0])
_recent = (datetime.now().timestamp() - _newest) < 15 * 60   # just logged: the Stop hook rebuilds the page when the agent stops
row("A9 Owner journal page current", True if _fresh else ("busy" if _recent and _oj.exists() else False),
    "journal/owner-journal.html is newer than the steps log and the journal" if _fresh else
    ("journal/owner-journal.html is behind a log line written in the last 15 minutes (BUSY: the Stop hook rebuilds it)"
     if _recent and _oj.exists() else "journal/owner-journal.html is older than the steps log or the journal"),
    "growth owner_journal --no-open")

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
done = sum(1 for r in rows if r[1] in ("OK  ", "BUSY"))
busy = sum(1 for r in rows if r[1] == "BUSY")
print(f"\n{done}/{len(rows)} setup steps done." + (f" ({busy} BUSY: work in progress, not a fault)" if busy else "")
      + ("" if done == len(rows) else " Page work starts only when all are OK (book/01-flow.md)."))
sys.exit(0 if all(r[1] != "FAIL" for r in rows) else 1)
