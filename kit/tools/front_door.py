#!/usr/bin/env python3
"""The front door: the few commands a person needs. Each one wraps tools that all keep working unchanged.

  growth setup [folder] [--site URL]    one-time setup. At a terminal it asks a few plain questions, one at a time.
                                        With no terminal (an agent, a script) it keeps the QUESTION / answer protocol of `growth wizard`.
  growth page <url-or-path> [--type post|money|core|hub] [--playbook NAME]
                                        start a page job: open the task with the playbook's steps, run pre-flight, write the brief
  growth check [path]                   the gate on the page of the open job, against the preview address; plain summary first
  growth ready [path]                   is the page ready to show the owner? plain summary first
  growth measure [path] [--release D]   did the page help? schedules the re-checks once, then measures
  growth status                         what is open, how far along, what is next

Every safety check still runs: these commands only start the same tools, in the right order, and say the result in plain words
before the exact lines.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import records  # noqa: E402  (the one access layer for tasks, journal and verdicts)

PAGE_TYPES = ("post", "money", "core", "hub")
PLAYBOOK_FOR = {"post": "update-post", "money": "money-page", "core": "change-a-page", "hub": "cluster-redesign"}
PREVIEW_PORTS = {"astro": 4321, "nextjs": 3000, "next": 3000, "hugo": 1313, "vite": 5173, "eleventy": 8080, "jekyll": 4000}
TLD_COUNTRY = {"ca": "CA", "uk": "GB", "au": "AU", "nz": "NZ", "ie": "IE", "in": "IN", "de": "DE", "fr": "FR", "es": "ES", "it": "IT",
               "nl": "NL", "se": "SE", "mx": "MX", "br": "BR", "jp": "JP", "sg": "SG", "za": "ZA"}
SETUP_TASK = "Project setup"
YES = ("y", "yes")


def say(msg: str = "") -> None:
    print(msg, flush=True)


# ---- helpers ---------------------------------------------------------------------------------------------------------

def find_project() -> Path | None:
    from config import find_project as fp
    return fp()


def need_project() -> Path:
    p = find_project()
    if p is None:
        say("There is no growth project in this folder yet.")
        say("Next: growth setup --site https://your-site.example")
        raise SystemExit(2)
    return p


def cfg_of(project: Path) -> dict:
    return json.loads((project / "growth.json").read_text())


def load_tasks(project: Path) -> dict:
    try:
        return records.tasks_doc(project)
    except (OSError, ValueError):
        return {"tasks": [], "questions": []}


def run_tool(project: Path, tool: str, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "GROWTH_PROJECT": str(project), "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run([sys.executable, str(HERE / tool), *args], capture_output=True, text=True, cwd=project, env=env)


def to_path(target: str, cfg: dict) -> str:
    """A page address as a path: a full address loses its host (this command never fetches it), a bare path gets its slash."""
    t = target.strip()
    path = urlsplit(t).path if re.match(r"^https?://", t) else t.split("#")[0].split("?")[0]
    path = "/" + path.lstrip("/")
    return path.rstrip("/") or "/"


def default_key(path: str) -> str:
    import paths
    return paths.default_key(path)


def guess_type(path: str, cfg: dict) -> str:
    """The home page, pricing and the pages in growth.json "money_pages" sell: they get the money-page playbook (book: "the
    main service pages, pricing and the home page"). 24 Nov 2026: the home page was guessed "core" (change-a-page)."""
    segs = [s for s in path.split("/") if s]
    if not segs or path in (cfg.get("money_pages") or []) or segs == ["pricing"]:
        return "money"
    if path in (cfg.get("core_pages") or {}):
        return "core"
    if len(segs) >= 2:
        return "post"
    return "money"


def open_page_task(project: Path, path: str | None = None) -> dict | None:
    tasks = [t for t in load_tasks(project)["tasks"] if t.get("page") and t.get("status") != "done"]
    if path:
        tasks = [t for t in tasks if t["page"]["path"] == path]
    return tasks[-1] if tasks else None


def page_from(project: Path, arg: str | None, flags: dict) -> dict | None:
    """(path, type, key) from the argument and flags, else from the open page job; None when neither is known."""
    cfg = cfg_of(project)
    if arg:
        path = to_path(arg, cfg)
        t = open_page_task(project, path)
        known = (t or {}).get("page") or {}
        ptype = flags.get("type") or known.get("type") or guess_type(path, cfg)
        return {"path": path, "type": ptype, "key": flags.get("key") or known.get("key") or default_key(path),
                "task": (t or {}).get("id", "")}
    t = open_page_task(project)
    if t:
        return {**t["page"], "task": t["id"]}
    return None


def no_page_message() -> None:
    say("I do not know which page you mean: no page job is open.")
    say("Next: growth page /your-page   (or name the page: growth <command> /your-page)")


def plain_fail(line: str) -> str:
    """One gate line ('FAIL 36h [ev.x] what -> fix') as a plain sentence."""
    m = re.match(r"^(?:NOT READY|FAIL)\s+(?:\S+\s+)?(?:\[[^\]]+\]\s*)?(.*)$", line.strip())
    text = re.sub(r"^\d+ problem\(s\): ", "", (m.group(1) if m else line).split(" -> ")[0].strip())
    return text if len(text) <= 200 else text[:200].rsplit(" ", 1)[0] + "…"



def summary(n_problems: int, lines: list[str], what: str) -> None:
    if not n_problems:
        say(f"No problems found {what}.")
        return
    say(f"{n_problems} problem{'s' if n_problems != 1 else ''} {what}. " + ("Here it is:" if n_problems == 1 else "Here they are:" if n_problems <= 3 else "The first 3:"))
    for l in lines[:3]:
        say(f"  - {plain_fail(l).rstrip('.')}.")


def split_flags(argv: list[str], names: tuple[str, ...]) -> tuple[list[str], dict]:
    """Pull '--name value' pairs for the given names out of argv; the rest is returned in order."""
    rest, flags, i = [], {}, 0
    while i < len(argv):
        a = argv[i]
        if a in names and i + 1 < len(argv):
            flags[a.lstrip("-")] = argv[i + 1]
            i += 2
        else:
            rest.append(a)
            i += 1
    return rest, flags


# ---- setup -----------------------------------------------------------------------------------------------------------

def yes_no(raw: str, default: bool) -> bool:
    raw = raw.strip().lower()
    return default if not raw else raw in YES


def country_from(raw: str, default: str) -> str:
    import research_gate as gate
    s = raw.strip()
    if not s:
        return default
    for code, (name, _lang) in gate.COUNTRIES.items():
        if s.upper() == code or gate.norm(s) == gate.norm(name):
            return code
    return ""


def detect_repo(project: Path, given: str) -> str:
    """The site's code folder: --repo, else the folder `growth setup` was run from when it is a git checkout outside the project."""
    import harness
    if given:
        return str(Path(given).expanduser().resolve())
    here = Path.cwd().resolve()
    inside = here == project or project in here.parents or here in project.parents
    if not inside and harness.git_repo_of(here) and ((here / "package.json").exists() or any(here.glob("*config*"))):
        return str(here)
    return ""


def setup_human(a, ask, out=say) -> int:
    """The plain-question setup. `ask(prompt)` returns what the person typed; `out(line)` prints. Returns 0 (done) or 3 (waiting)."""
    import detect
    import harness
    import new_project
    import research_gate as gate
    import wizard
    import wizard_state as ws

    site = a.site
    while not site:
        site = ask("What is your website's address? (for example https://example.com) ").strip()
        if not re.match(r"^https?://[^/\s]+\.[^/\s]+$", site.rstrip("/")):
            out("That does not look like an address. Start with https://")
            site = ""
    site = site.rstrip("/")
    project = Path(a.folder).expanduser().resolve() if a.folder else (find_project() or
                  Path.cwd() / (new_project.name_from(site).lower().replace(" ", "-") + "-growth"))
    if not (project / "growth.json").is_file():
        project, _ = new_project.make(project, site, a.name, "static", with_harness=False)
        out(f"Made your growth folder: {project}")
    cfg = wizard.cfg_of(project)
    host = urlsplit(site).netloc.lower().removeprefix("www.")
    default_cc = TLD_COUNTRY.get(host.rsplit(".", 1)[-1], "US")
    default_name = gate.COUNTRIES[default_cc][0]
    code = ""
    while not code:
        code = country_from(ask(f"Which country do you want to rank in? [{default_name}] "), default_cc)
        if not code:
            out("I do not know that country. Try its two-letter code, for example US or CA.")
    approver = ask("Who approves a page before it goes live? (a name) [the owner] ").strip() or "the owner"
    crawl = yes_no(ask("May I read your live website page by page? Recommended: no. [y/N] "), False)
    repo = detect_repo(project, a.repo)
    framework = ""
    if repo:
        framework = ((detect.detect_all(Path(repo), "").get("stack") or {}).get("framework") or "").lower()
    preview = f"http://localhost:{PREVIEW_PORTS[framework]}" if framework in PREVIEW_PORTS else ""
    git_hooks = bool(repo and harness.git_repo_of(Path(repo)))
    extra = " and quick checks before each commit in your site's code folder" if git_hooks else ""
    helpers = yes_no(ask(f"Add the safety helpers to your agent (rules it must follow, a progress bar, no git push or deploys){extra}? [Y/n] "), True)
    answers = {"market": {"country": code}, "site_repo": {"path": repo} if repo else "none", "analytics": "later",
               "live_rule": {"rule": "crawl-ok" if crawl else "no-crawl", "preview_url": preview}, "approver": approver,
               "harness": {"permissions": helpers, "git_hooks": helpers and git_hooks}, "detect": {"confirm": True}}
    if a.sitemap:
        answers["sitemap"] = a.sitemap
    session = wizard.Session(project, answers, False, False)
    shown = {"market": "Target country", "site_repo": "Site code folder", "analytics": "Analytics (add it later)", "live_rule": "Live-site rule",
             "approver": "Approver", "harness": "Agent safety helpers", "detect": "What your site is built with"}
    real_say, wizard.say = wizard.say, lambda *_a, **_k: None          # the step details stay in setup-state.json
    try:
        for step in wizard.ORDER[:7]:
            if ws.get(project, step).get("status") in ws.CLOSED:
                continue
            msg = wizard.HANDLERS[step](session)
            out(f"  done: {shown[step]}: {msg.split(';')[0][:90]}")
    finally:
        wizard.say = real_say
    if preview:
        out(f"  I expect page previews at {preview} (change it in growth.json: preview_url).")
    if not repo:
        out("  No site code folder found. Pages are checked through their live address only. Add one later with --repo.")
    market = wizard.cfg_of(project).get("market") or {}
    want = gate.country_name(market)
    # the two steps the code cannot do for you
    if ws.get(project, "browser").get("status") != "done":
        out("\nStep 1 of 2: connect your research browser.")
        out("  Open Chrome and type /chrome in Claude Code, pick your browser, and tick \"By default: on\".")
        if not yes_no(ask("  Done? [y/N] "), False):
            out("\nNo problem. Do that, then run `growth setup` again: I pick up where I stopped.")
            wizard.write_setup_md(project)
            return 3
        wizard.confirm_browser(project, "Browser 1", "owner")
    if ws.get(project, "region").get("status") != "done":
        out(f"\nStep 2 of 2: set Google to {want}.")
        out("  In that browser open Google's search settings (Other settings > Language & region > Results region).")
        for _try in range(3):
            seen = ask("  Open Google settings > Results region. What does it say? ").strip()
            if not seen:
                break
            if not gate.region_matches(seen, market):
                out(f"  Google shows \"{seen}\", not {want}. Choose {want} there, save, and read it again.")
                continue
            ok = yes_no(ask(f"  Is that right for {want}? [y/N] "), False)
            good, msg = wizard.confirm_region(project, seen, ok, "owner")
            if good:
                break
            out("  " + msg)
            break
    rc = wizard.finish(project, human=True)
    wizard.write_setup_md(project)
    if rc == 0:
        out(f"\nSetup is done. Next: {'cd ' + str(project) + ' && ' if Path.cwd().resolve() != project else ''}growth page /your-page")
    else:
        out("\nSetup is not finished yet. Do the step above, then run `growth setup` again: I pick up where I stopped.")
    return rc


def cmd_setup(argv: list[str], ask=None) -> int:
    ap = argparse.ArgumentParser(prog="growth setup", description="One-time setup, in plain questions.")
    ap.add_argument("folder", nargs="?", default="")
    ap.add_argument("--site", default="")
    ap.add_argument("--name", default="")
    ap.add_argument("--repo", default="", help="the folder of your site's code (default: the folder you run this from, if it is one)")
    ap.add_argument("--answers", default="", help="answers file: no questions are asked")
    ap.add_argument("--sitemap", default="", help="a sitemap address or saved file")
    ap.add_argument("--yes", action="store_true")
    a, extra = ap.parse_known_args(argv)
    human = ask is not None or (sys.stdin.isatty() and sys.stdout.isatty() and not a.answers)
    if human:
        return setup_human(a, ask or input)
    # no terminal: the wizard's own QUESTION / answer protocol (exit 3 = waiting for an answer)
    import wizard
    wargs = []
    folder = a.folder
    if not folder and not find_project():
        if not a.site:
            say("There is no growth project here yet. Next: growth setup <folder> --site https://your-site.example")
            return 2
        import new_project
        folder = str(Path.cwd() / (new_project.name_from(a.site).lower().replace(" ", "-") + "-growth"))
    if folder:
        wargs.append(folder)
    for flag, val in (("--site", a.site), ("--name", a.name), ("--answers", a.answers), ("--sitemap", a.sitemap)):
        if val:
            wargs += [flag, val]
    if a.yes:
        wargs.append("--yes")
    rc = wizard.main(wargs + extra)
    if rc == 0:
        say("Setup done. Next: growth page /your-page")
    elif rc == 3:
        say("Setup is not finished: answer the question above (growth wizard answer <step> <value>), then run growth setup again.")
    return rc


# ---- page ------------------------------------------------------------------------------------------------------------

def playbook_lines(name: str) -> list[str]:
    from config import BOOK
    pb = BOOK / "playbooks" / f"{name}.md"
    if not pb.is_file():
        return []
    text = pb.read_text()
    m = re.search(r"(?ms)^## Part 2\..*?(?=^---|\Z)", text) or re.search(r"(?ms)^## .*?(?=^---|\Z)", text)
    body = (m.group(0) if m else text).splitlines()
    body = [l.replace("**", "") for l in body]
    numbered = [re.sub(r"\s+", " ", l).strip() for l in body if re.match(r"^\s*\d+[a-z]?\. ", l)]
    return (numbered or [re.sub(r"\s+", " ", l).strip() for l in body if re.match(r"^\s*- ", l)])[:40]


def cmd_page(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="growth page", description="Start a page job.")
    ap.add_argument("target", help="the page: a path (/pricing) or its address")
    ap.add_argument("--type", choices=PAGE_TYPES, default="")
    ap.add_argument("--playbook", default="")
    ap.add_argument("--key", default="")
    ap.add_argument("--new", action="store_true", help="a new blog post (uses the new-post playbook)")
    a = ap.parse_args(argv)
    project = need_project()
    cfg = cfg_of(project)
    path = to_path(a.target, cfg)
    ptype = a.type or guess_type(path, cfg)
    key = a.key or default_key(path)
    playbook = a.playbook or ("new-post" if a.new and ptype == "post" else PLAYBOOK_FOR[ptype])
    say(f"Page job for {path}: a {ptype} page, playbook {playbook}." + ("" if a.type else f" (I guessed the type; change it with --type {'|'.join(PAGE_TYPES)})"))
    existing = open_page_task(project, path)
    if existing:
        tid = existing["id"]
        say(f"  A job for this page is already open: {tid}. I keep it.")
    else:
        r = run_tool(project, "tasks.py", "add", f"Page: {path}", f"Work on {path} ({ptype} page)", "--playbook", playbook)
        if r.returncode:
            reason = (r.stderr or r.stdout).strip().splitlines()[-1] if (r.stderr or r.stdout).strip() else "unknown"
            if "research" in reason:
                say("I cannot start this job yet: the research browser and Google's region are not confirmed.")
                say("Next: growth setup")
            else:
                say(f"I could not open the job: {reason}")
            say(f"Exact message: {reason}")
            return 1
        tid = r.stdout.strip().splitlines()[-1]
        stamp = dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
        lines = playbook_lines(playbook)
        counts = []

        def add_playbook(db):          # one transaction: another agent's change to the list is never lost
            task = next(t for t in db["tasks"] if t["id"] == tid)
            task["page"] = {"path": path, "type": ptype, "key": key, "playbook": playbook}
            for line in lines:
                task["steps"].append({"n": len(task["steps"]) + 1, "what": line[:200], "status": "todo", "at": stamp, "output": None})
            counts.append(len(task["steps"]))
        records.tasks_update(project, add_playbook)
        say(f"  Opened {tid} with {counts[0]} playbook steps.")
    pre = run_tool(project, "preflight.py", path, "--type", ptype, "--key", key)
    out = (pre.stdout + pre.stderr).strip()
    todo = [l for l in out.splitlines() if l.startswith("FAIL") or l.startswith("  FAIL")]
    if pre.returncode == 0:
        say("  Pre-flight: passed. The build may start.")
    elif "no preview_url" in out:
        say("  Pre-flight could not run: I do not know your preview address.")
        say("  Next: set preview_url in growth.json (the address where you look at pages while you work).")
    else:
        summary(len(todo) or 1, todo or [out.splitlines()[-1] if out else "pre-flight did not finish"], "to prepare before the build")
    brief = f"research/briefs/{key}.md"
    b = run_tool(project, "brief.py", path, "--type", ptype, "--task", tid, "--playbook", playbook, "--key", key, "--out", brief)
    if b.returncode == 0:
        say(f"  Brief for your agent: {brief}")
    else:
        say(f"  I could not write the brief: {(b.stderr or b.stdout).strip().splitlines()[-1:]}")
    say(f"\nNext: give {brief} to your agent and build the page on your preview. When it is built, run: growth check")
    return 0


# ---- check, ready, measure, status -----------------------------------------------------------------------------------

def preview_problem(cfg: dict) -> str:
    return "" if cfg.get("preview_url") else "I do not know your preview address. Set preview_url in growth.json first."


def cmd_check(argv: list[str]) -> int:
    rest, flags = split_flags(argv, ("--type", "--key"))
    gate_extra = [x for x in rest if x.startswith("--")]
    target = next((x for x in rest if not x.startswith("--")), None)
    project = need_project()
    page = page_from(project, target, flags)
    if not page:
        no_page_message()
        return 2
    cfg = cfg_of(project)
    if preview_problem(cfg):
        say(preview_problem(cfg))
        return 2
    url = cfg["preview_url"].rstrip("/") + page["path"]
    args = ["page", page["path"], "--url", url, "--type", page["type"], "--key", page["key"], "--no-link-status", *gate_extra]
    if cfg.get("preview_repo") or cfg.get("site_repo"):
        args += ["--repo", str(((project / (cfg.get("preview_repo") or cfg.get("site_repo"))).expanduser().resolve()))]
    r = run_tool(project, "gate.py", *args)
    text = r.stdout + r.stderr
    fails = [l for l in text.splitlines() if l.startswith("FAIL")]
    if "Gate:" not in text:
        say(f"The check could not run on {page['path']}. Is your preview running at {cfg['preview_url']}?")
        say("Exact message: " + (text.strip().splitlines()[-1] if text.strip() else "none"))
        return 1
    summary(len(fails), fails, f"on {page['path']}")
    if fails:
        say("Fix these, then run growth check again. Full details:")
    else:
        say("Next: growth ready")
    say("")
    say(text.rstrip())
    return r.returncode


def cmd_ready(argv: list[str]) -> int:
    if "--batch" in argv:   # 2.8.1: many pages side by side; verdicts stream as they land (before, "ledger" was taken for a page)
        project = need_project()
        env = {**os.environ, "GROWTH_PROJECT": str(project), "PYTHONDONTWRITEBYTECODE": "1"}
        return subprocess.run([sys.executable, str(HERE / "ready.py"), *argv], cwd=project, env=env).returncode
    if "--list" in argv or ("--type" in argv and "--key" in argv and argv and not argv[0].startswith("--")):
        r = run_tool(need_project(), "ready.py", *argv)           # the exact old form: unchanged output
        sys.stdout.write(r.stdout)
        sys.stderr.write(r.stderr)
        return r.returncode
    rest, flags = split_flags(argv, ("--type", "--key", "--repo"))
    target = next((x for x in rest if not x.startswith("--")), None)
    project = need_project()
    page = page_from(project, target, flags)
    if not page:
        no_page_message()
        return 2
    repo = ["--repo", flags["repo"]] if flags.get("repo") else []
    r = run_tool(project, "ready.py", page["path"], "--type", page["type"], "--key", page["key"], *repo)
    text = (r.stdout + r.stderr).strip()
    lines = text.splitlines()
    if r.returncode == 0 and lines and lines[0].startswith("READY"):
        say(f"{page['path']} is ready. You may look at it: {cfg_of(project).get('preview_url', '').rstrip('/')}{page['path']}")
    elif lines and lines[0].startswith("NOT READY"):
        fails = [l.strip() for l in lines[1:] if l.strip().startswith("FAIL")]
        say(f"{page['path']} is not ready yet.")
        summary(len(fails), fails, "still open")
    else:
        say(f"I cannot say yet whether {page['path']} is ready: {lines[-1] if lines else 'no output'}")
    say("")
    say(text)
    return r.returncode


def cmd_measure(argv: list[str]) -> int:
    if argv[:1] in (["run"], ["schedule"]):
        r = run_tool(need_project(), "measure.py", *argv)
        sys.stdout.write(r.stdout)
        sys.stderr.write(r.stderr)
        return r.returncode
    rest, flags = split_flags(argv, ("--release", "--key", "--type", "--today"))
    target = next((x for x in rest if not x.startswith("--")), None)
    project = need_project()
    page = page_from(project, target, flags)
    if not page:
        no_page_message()
        return 2
    release = flags.get("release")
    if not release:
        try:
            at = records.verdicts(project, "ready").get(page["path"], {}).get("at", "")
        except (OSError, ValueError):
            at = ""
        release = at[:10] if re.match(r"\d{4}-\d{2}-\d{2}", at) else dt.date.today().isoformat()
        say(f"No release day given: using {release} ({'the day it was marked ready' if at else 'today'}). Use --release YYYY-MM-DD to change it.")
    try:
        entries = [json.loads(l) for l in records.journal_lines(project) if l.strip()]
    except (OSError, ValueError):
        entries = []
    scheduled = any("measure" in (e.get("tags") or []) and f"growth measure run {page['path']}" in e.get("title", "") for e in entries)
    if not scheduled:
        s = run_tool(project, "measure.py", "schedule", page["path"], "--release", release)
        say("Scheduled the day 7, 14, 28 and 56 re-checks." if s.returncode == 0 else f"I could not schedule the re-checks: {(s.stderr or s.stdout).strip()[-160:]}")
    args = ["run", page["path"], "--key", page["key"], "--release", release]
    if flags.get("today"):
        args += ["--today", flags["today"]]
    if page.get("task"):
        args += ["--task", page["task"]]
    r = run_tool(project, "measure.py", *args)
    text = (r.stdout + r.stderr).strip()
    own = text.split("== THE WHOLE SITE")[0]
    done = len(re.findall(r"^\s+day \d+ \(", own, re.M))
    waiting = re.findall(r"^\s+day (\d+): not yet\s*(\S*)", own, re.M)
    if r.returncode:
        say(f"The measurement could not run: {text.splitlines()[-1] if text else 'no output'}")
    else:
        say(f"Measured {done} of 4 windows for {page['path']}." + (f" The next one (day {waiting[0][0]}) is ready on {waiting[0][1]}." if waiting and waiting[0][1] else ""))
    say("")
    say(text)
    return r.returncode


def cmd_status(argv: list[str]) -> int:
    import statusline
    project = need_project()
    tasks = load_tasks(project)["tasks"]
    open_t = [t for t in tasks if t.get("status") != "done" and any(s.get("status") != "done" for s in t.get("steps") or [])]
    setup = [t for t in open_t if t.get("title") == SETUP_TASK]
    work = [t for t in open_t if t.get("title") != SETUP_TASK]
    say(f"{cfg_of(project).get('name', 'Your project')}")
    nxt = ""
    for t in work:
        steps = t.get("steps") or []
        done = sum(1 for s in steps if s.get("status") == "done")
        now = next((s for s in steps if s.get("status") != "done"), None)
        say(f"  {t['id']:<4} {t['title'][:40]:<40} {statusline.bar(done, len(steps))} {done}/{len(steps)}")
        if now:
            say(f"       next step {now.get('n')}: {statusline.label(now)}")
            nxt = nxt or ("growth check" if t.get("page") else f"step {now.get('n')} of {t['id']}")
    for t in setup:
        steps = t.get("steps") or []
        done = sum(1 for s in steps if s.get("status") == "done")
        say(f"  Setup {statusline.bar(done, len(steps))} {done}/{len(steps)}")
        nxt = "growth setup" if not work else nxt
    if not open_t:
        say("  Nothing is open.")
    say(f"\nNext: {nxt or 'growth page /your-page'}")
    return 0


COMMANDS = {"setup": cmd_setup, "page": cmd_page, "check": cmd_check, "ready": cmd_ready, "measure": cmd_measure, "status": cmd_status}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help") or argv[0] not in COMMANDS:
        say(__doc__)
        return 0 if not argv or argv[0] in ("-h", "--help") else 2
    return COMMANDS[argv[0]](argv[1:]) or 0


if __name__ == "__main__":
    sys.exit(main())
