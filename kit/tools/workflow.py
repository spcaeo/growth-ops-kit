#!/usr/bin/env python3
"""The task workflow as a rule, not a suggestion: checks the hooks run.

  growth workflow check            # Stop hook: work without an open task, an open task with no steps, a done step with no proof
  growth workflow resolve [dir]   # print the project folder found from dir (default: here); exit 2 and say why when none
  growth workflow stage            # PostToolUse hook (stdin = Claude's JSON): after `growth tasks tick/step` at a stage boundary
                                   # (research, edit, test, hand-over) print the page's open manual checkpoints to re-read

`check` exits 2 and prints the problems and the command that clears each one. The way out for a chat that is not page
work (a question, a setup talk): `growth tasks add "Chat: <topic>" "" --type chat`. A chat task needs no steps; close it
with `growth tasks status <id> done`. "Work" means files changed (git) or committed since the last page task, in the project
or the site checkout, apart from the bookkeeping files (task list, steps log, journal, .claude). Only a page task covers
work: a chat task covers no file changes, and the "Project setup" task covers only the setup files (growth.json, SETUP.md,
BRAND.md, OWNER-RULES.md, CLAUDE.md, ...). Committing the work does not hide it.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import checkpoints  # noqa: E402
import records  # noqa: E402  (the one access layer for the task list)
from config import find_project  # noqa: E402

BOOKKEEPING = ("state/", "docs/tasks.json", "docs/steps-log.md", "docs/owner-messages-map.json", "journal/", ".claude/", ".tmp")
STAGE = re.compile(r"\b(research|edit|build|fold|test|gate|hand-?over|ready|publish|release|review)\b", re.I)
TICK = re.compile(r"\btasks\s+(tick|step)\b")


def load_cfg(project: Path) -> dict:
    try:
        return json.loads((project / "growth.json").read_text())
    except (OSError, ValueError):
        return {}


def load_tasks(project: Path) -> list:
    try:
        return records.tasks_doc(project).get("tasks") or []
    except (OSError, ValueError):
        return []


# Files the project setup itself edits (the setup task covers these and nothing else). Page files, in the project or in a
# site checkout, always need a page task.
SETUP_FILES = ("growth.json", "SETUP.md", "BRAND.md", "OWNER-RULES.md", "CLAUDE.md", ".gitignore", "docs/setup-state.json",
               "setup-state.json", "docs/design.json", "design.json")
SETUP_TITLE = "Project setup"


def kind_of(task: dict) -> str:
    """chat (covers no file changes), setup (covers the setup files) or work (a page task: covers everything)."""
    if task.get("type") == "chat":
        return "chat"
    return "setup" if task.get("title") == SETUP_TITLE else "work"


def roots_of(project: Path) -> list:
    cfg = load_cfg(project)
    roots, seen = [], set()
    for r in [project] + [(project / cfg[k]).expanduser() for k in ("site_repo", "preview_repo") if cfg.get(k)]:
        try:
            r = r.resolve()
        except OSError:
            continue
        if r not in seen and r.is_dir():
            seen.add(r)
            roots.append(r)
    return roots


def _skip(project: Path, root: Path, p: str) -> bool:
    return (root == project.resolve() and p.startswith(BOOKKEEPING)) or "owner-journal" in p


def changed_files(project: Path) -> list:
    """Changed paths (git status) in the project and the site checkouts, bookkeeping files left out."""
    out = []
    for r in roots_of(project):
        try:
            res = subprocess.run(["git", "-C", str(r), "status", "--porcelain", "-uall"], capture_output=True, text=True, timeout=20)
        except (OSError, subprocess.SubprocessError):
            continue
        if res.returncode != 0:
            continue
        for ln in res.stdout.splitlines():
            p = ln[3:].split(" -> ")[-1].strip().strip('"')
            if not _skip(project, r, p):
                out.append(p if r == project.resolve() else str(r / p))   # a site checkout's file never looks like a setup file
    return out


def _parse_at(project: Path, text: str):
    """Minute-resolution 'YYYY-MM-DD HH:MM ZONE' stamp of docs/tasks.json -> epoch seconds, or None."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    try:
        tz = ZoneInfo(load_cfg(project).get("timezone", "UTC"))
        return datetime.strptime((text or "")[:16], "%Y-%m-%d %H:%M").replace(tzinfo=tz).timestamp()
    except (ValueError, KeyError, OSError):
        return None


def _checked(step: dict):
    """The commit stored with a step's proof (tasks.checked_commit); the same rule if the tasks tool cannot load."""
    try:
        import tasks
        return tasks.checked_commit(step)
    except BaseException:  # noqa: BLE001  (config exits when there is no project)
        return step.get("last_checked_commit")


def cover_commit(tasks: list):
    """The commit the project was at when the latest proof-bearing step of a page (work) task was recorded: work after
    it is not covered. None when no step stored one (tasks from before the commit was stored)."""
    best = (None, "")
    for t in tasks:
        if kind_of(t) != "work":
            continue
        for s in t.get("steps") or []:
            sha = _checked(s)
            if sha and s.get("status") == "done" and (s.get("output") or "").strip() and (s.get("at") or "") >= best[1]:
                best = (sha, s.get("at") or "")
    return best[0]


def _commit_time(repo: Path, sha: str):
    try:
        res = subprocess.run(["git", "-C", str(repo), "show", "-s", "--format=%ct", sha], capture_output=True, text=True, timeout=20)
        return float(res.stdout.strip()) if res.returncode == 0 and res.stdout.strip() else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def cover_time(project: Path, tasks: list):
    """Fallback when no step stored a commit: when work was last under a page task (latest proof-bearing step or finish
    of a page task), else the start of the earliest task, else the last commit of the task list."""
    stamps = []
    for t in tasks:
        if kind_of(t) != "work":
            continue
        if t.get("status") == "done":
            stamps.append(_parse_at(project, t.get("finished") or ""))
        stamps += [_parse_at(project, s.get("at")) for s in t.get("steps") or []
                   if s.get("status") == "done" and (s.get("output") or "").strip()]
    stamps = [x for x in stamps if x]
    if stamps:
        return max(stamps) + 60
    starts = [x for x in (_parse_at(project, t.get("started")) for t in tasks) if x]
    if starts:
        return min(starts)
    try:
        res = subprocess.run(["git", "-C", str(project), "log", "-1", "--format=%ct", "--", records.tasks_rel(project)],
                             capture_output=True, text=True, timeout=20)
        return float(res.stdout.strip()) if res.returncode == 0 and res.stdout.strip() else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def committed_files(project: Path, since, sha=None) -> list:
    """Paths committed (in the project or a site checkout) after the cut-off, bookkeeping left out. With `sha` (the commit
    stored with the last proof) the project's own history is cut exactly at that commit (sha..HEAD) and a site checkout
    at that commit's time; else `since` (epoch). Committed work counts as work: the dirty tree alone hides everything an
    agent commits before it stops."""
    if since is None and not sha:
        return []
    out = []
    for r in roots_of(project):
        cmd = ["git", "-C", str(r), "log", "--format=@@%ct", "--name-only", "-n", "300"]
        cut = since
        if sha:
            if r == project.resolve() and _commit_time(r, sha) is not None:
                cmd.insert(4, f"{sha}..HEAD")
                cut = 0
            else:
                cut = _commit_time(project, sha) if _commit_time(project, sha) is not None else since
        if cut is None:
            continue
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            continue
        if res.returncode != 0:
            continue
        ts = 0.0
        for ln in res.stdout.splitlines():
            if ln.startswith("@@"):
                ts = float(ln[2:] or 0)
            elif ln.strip() and ts > cut and not _skip(project, r, ln.strip()):
                out.append(ln.strip() if r == project.resolve() else str(r / ln.strip()))
    return out


def problems(project: Path) -> list:
    tasks = load_tasks(project)
    open_t = [t for t in tasks if t.get("status") != "done"]
    out = []
    for t in tasks:
        bad = [s for s in t.get("steps") or [] if s.get("status") == "done" and not (s.get("output") or "").strip()]
        if bad:
            out.append(f"{t['id']} step {bad[0]['n']} is done with no proof ({len(bad)} such). "
                       f"Fix: growth tasks tick {t['id']} {bad[0]['n']} --output \"<file, commit or command and result>\" "
                       f"(or --status todo if it was not done)")
    empty = [t for t in open_t if t.get("type") != "chat" and not t.get("steps")]
    if empty:
        out.append(f"{empty[0]['id']} is open with no steps. Copy the playbook steps: growth tasks step {empty[0]['id']} \"<step>\" "
                   f"(not page work? growth tasks status {empty[0]['id']} done)")
    kinds = {kind_of(t) for t in open_t}
    if "work" in kinds:
        return out                                   # a page task is open: it covers the work
    dirty = changed_files(project)
    sha = cover_commit(tasks)
    committed = committed_files(project, None if sha else cover_time(project, tasks), sha)
    work = dirty + committed
    if "setup" in kinds:                             # the setup task covers the setup files and nothing else
        work = [f for f in work if f not in SETUP_FILES and not f.endswith("/.gitkeep") and f != ".gitkeep"]
    if work:
        how = "changed" if dirty else "committed since the last page task"
        first = work[0]
        if kinds:
            what = "only a chat or setup task is open" if "chat" in kinds or "setup" in kinds else "no task is open"
            out.append(f"{len(work)} file(s) {how} ({first}...) and {what}: a chat task covers no file changes and the setup "
                       "task covers only the setup files. Open a page task: growth tasks add \"<title>\" \"<owner's words>\" "
                       "and add its steps")
        else:
            out.append(f"{len(work)} file(s) {how} ({first}...) and no task is open. Open one: growth tasks add \"<title>\" "
                       "\"<owner's words>\" and add its steps; a chat that is not page work and changes no file: "
                       "growth tasks add \"Chat: <topic>\" \"\" --type chat")
    return out


def check(project: Path) -> int:
    probs = problems(project)
    if not probs:
        return 0
    print("Workflow not followed (book/01-flow.md, tasks):\n" + "\n".join("- " + p for p in probs), file=sys.stderr)
    return 2


def open_manual(project: Path, task_text: str) -> tuple:
    """(file, [open manual items]) for the page the task names, else the newest checkpoints file."""
    files = sorted((project / "research").glob("*-checkpoints.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return None, []
    pick = next((f for f in files if f.name[:-len("-checkpoints.md")].lower() in task_text.lower()), files[0])
    return pick, checkpoints.manual_status(pick.read_text())[2]


def stage(project: Path, raw: str) -> int:
    try:
        data = json.loads(raw or "{}")
    except ValueError:
        return 0
    cmd = (data.get("tool_input") or {}).get("command", "") or ""
    if not TICK.search(cmd):
        return 0
    text = cmd
    m = re.search(r"\btasks\s+tick\s+(\S+)\s+(\d+)", cmd)       # a tick names the step by number: read its words
    if m:
        for t in load_tasks(project):
            if t["id"].lower() == m.group(1).lower():
                text += " " + " ".join(s.get("what", "") for s in t.get("steps") or [] if str(s.get("n")) == m.group(2))
    if not STAGE.search(text):
        return 0
    f, items = open_manual(project, cmd + " " + " ".join(t.get("title", "") for t in load_tasks(project) if t.get("status") != "done"))
    if not f or not items:
        return 0
    msg = (f"Stage boundary: re-read {f.relative_to(project)} now. {len(items)} manual check(s) still open:\n"
           + "\n".join("- " + i for i in items[:12]) + ("\n- ..." if len(items) > 12 else "")
           + "\nTick each with its proof (- [x] rule: text -- proof) before you hand over.")
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": msg}}))
    return 0


def resolve_project(start: Path | None = None, env: dict | None = None):
    """(project folder or None, message). The hooks start in whatever folder Claude was started in, often a workspace above
    the project. Order: $GROWTH_PROJECT when it holds growth.json; else the nearest folder at or above `start`; else exactly one
    growth.json one or two levels below it; else, when several, the one whose files are changed (git). Otherwise None and a
    message that says where Claude was started and what to do."""
    env = os.environ if env is None else env
    given = env.get("GROWTH_PROJECT", "").strip()
    here = Path(given or start or Path.cwd()).expanduser().resolve()
    if given and not here.is_dir():
        return None, f"GROWTH_PROJECT={given} is not a folder, so none of the rule guards can run. Fix GROWTH_PROJECT or unset it."
    for d in (here, *here.parents):
        if (d / "growth.json").is_file():
            return d, ""
    found = sorted({p.parent for depth in ("*", "*/*") for p in here.glob(depth + "/growth.json") if ".git" not in p.parts})
    if len(found) > 1:
        dirty = [f for f in found if changed_files(f)]
        found = dirty if len(dirty) == 1 else found
    if len(found) == 1:
        return found[0], ""
    where = f"GROWTH_PROJECT={given} has no growth.json; " if given else ""
    if found:
        return None, (f"{where}Claude was started in {here}, which holds {len(found)} projects ({', '.join(f.name for f in found)}) "
                      "and none stands out. Restart Claude inside the project folder you work on, or set GROWTH_PROJECT=<that folder>.")
    return None, (f"{where}Claude was started in {here}, which is not inside a growth project (no growth.json at or around it), "
                  "so none of the rule guards can run. Restart Claude in the project folder, or set GROWTH_PROJECT=<project folder>.")


def main(argv: list) -> int:
    if not argv or argv[0] in ("-h", "--help") or argv[0] not in ("check", "stage", "resolve"):
        print(__doc__)
        return 0 if not argv or argv[0] in ("-h", "--help") else 2
    if argv[0] == "resolve":                 # the Stop hook: print the project folder, or say why there is none (exit 2)
        project, msg = resolve_project(Path(argv[1]) if len(argv) > 1 else None)
        if project is None:
            print(msg, file=sys.stderr)
            return 2
        print(project)
        return 0
    project, msg = resolve_project()
    if project is None and argv[0] == "stage":
        return 0                              # a tool hook outside a project says nothing
    if project is None:
        print("Workflow guard cannot run: " + msg, file=sys.stderr)
        return 2
    os.environ["GROWTH_PROJECT"] = str(project)
    return check(project) if argv[0] == "check" else stage(project, sys.stdin.read())


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
