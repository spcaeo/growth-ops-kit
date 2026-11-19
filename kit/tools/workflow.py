#!/usr/bin/env python3
"""The task workflow as a rule, not a suggestion: checks the hooks run.

  growth workflow check            # Stop hook: work without an open task, an open task with no steps, a done step with no proof
  growth workflow stage            # PostToolUse hook (stdin = Claude's JSON): after `growth tasks tick/step` at a stage boundary
                                   # (research, edit, test, hand-over) print the page's open manual checkpoints to re-read

`check` exits 2 and prints the problems and the command that clears each one. The way out for a chat that is not page
work (a question, a setup talk): `growth tasks add "Chat: <topic>" "" --type chat`. A chat task needs no steps; close it
with `growth tasks status <id> done`. "Work" means files changed (git) in the project or the site checkout, apart from the
bookkeeping files (task list, steps log, journal, .claude).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import checkpoints  # noqa: E402
from config import find_project  # noqa: E402

BOOKKEEPING = ("docs/tasks.json", "docs/steps-log.md", "docs/owner-messages-map.json", "journal/", ".claude/", ".tmp")
STAGE = re.compile(r"\b(research|edit|build|fold|test|gate|hand-?over|ready|publish|release|review)\b", re.I)
TICK = re.compile(r"\btasks\s+(tick|step)\b")


def load_cfg(project: Path) -> dict:
    try:
        return json.loads((project / "growth.json").read_text())
    except (OSError, ValueError):
        return {}


def load_tasks(project: Path) -> list:
    docs = load_cfg(project).get("project_docs") or "docs"
    try:
        return json.loads((project / docs / "tasks.json").read_text()).get("tasks") or []
    except (OSError, ValueError):
        return []


def changed_files(project: Path) -> list:
    """Changed paths (git status) in the project and the site checkouts, bookkeeping files left out."""
    cfg = load_cfg(project)
    roots = [project] + [(project / cfg[k]).expanduser() for k in ("site_repo", "preview_repo") if cfg.get(k)]
    seen, out = set(), []
    for r in roots:
        try:
            r = r.resolve()
            if r in seen or not r.is_dir():
                continue
            seen.add(r)
            res = subprocess.run(["git", "-C", str(r), "status", "--porcelain", "-uall"], capture_output=True, text=True, timeout=20)
        except (OSError, subprocess.SubprocessError):
            continue
        if res.returncode != 0:
            continue
        for ln in res.stdout.splitlines():
            p = ln[3:].split(" -> ")[-1].strip().strip('"')
            if r == project.resolve() and p.startswith(BOOKKEEPING):
                continue
            if "owner-journal" in p:
                continue
            out.append(p)
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
    if not open_t:
        files = changed_files(project)
        if files:
            out.append(f"{len(files)} file(s) changed ({files[0]}...) and no task is open. Open one: growth tasks add \"<title>\" \"<owner's words>\" "
                       "and add its steps; a chat that is not page work: growth tasks add \"Chat: <topic>\" \"\" --type chat")
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


def main(argv: list) -> int:
    if not argv or argv[0] in ("-h", "--help") or argv[0] not in ("check", "stage"):
        print(__doc__)
        return 0 if not argv or argv[0] in ("-h", "--help") else 2
    project = find_project()
    if project is None:
        return 0
    return check(project) if argv[0] == "check" else stage(project, sys.stdin.read())


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
