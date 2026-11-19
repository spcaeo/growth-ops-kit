#!/usr/bin/env python3
"""Claude Code status line: the open task's progress, always visible at the bottom of the agent's window.

  T3 ▰▰▱▱▱▱▱▱▱▱ 9/44 · now: step 10 Search Console research · +1 other open

Read from the project's task list (docs/tasks.json, or growth.json "project_docs"), the one record `growth tasks` keeps.
`growth new-project` registers it in .claude/settings.json ("statusLine"), so the owner sees each step tick off from
the first minute, even when the agent has no on-screen task list of its own. It never fails: on any problem it prints
one plain line. Standard library only; Claude Code's JSON on stdin is read and ignored.

  growth statusline            # print the line for the project in this folder (or GROWTH_PROJECT)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

WIDTH = 10
# growth.json "statusline_style" picks the look (default "bars"). Each is (done, to do).
STYLES = {
    "squares": ("■", "□"),     # T3 ■■■□□□□□□□ 9/44
    "blocks": ("█", "░"),      # T3 ███░░░░░░░ 9/44
    "dots": ("●", "○"),        # T3 ●●●○○○○○○○ 9/44
    "bars": ("▰", "▱"),        # T3 ▰▰▰▱▱▱▱▱▱▱ 9/44  (default)
    "checks": ("☑", "☐"),      # T3 ☑☑☑☐☐☐☐☐☐☐ 9/44
    "plain": ("#", "-"),       # T3 ###------- 9/44  (any terminal or font)
}


def project_dir() -> Path:
    for env in ("GROWTH_PROJECT", "CLAUDE_PROJECT_DIR"):
        if os.environ.get(env):
            return Path(os.environ[env])
    here = Path.cwd()
    for p in (here, *here.parents):
        if (p / "growth.json").is_file():
            return p
    return here


def settings(project: Path) -> dict:
    try:
        return json.loads((project / "growth.json").read_text())
    except (OSError, ValueError):
        return {}


def tasks_file(project: Path) -> Path:
    return project / (settings(project).get("project_docs") or "docs") / "tasks.json"


def bar(done: int, total: int, style: str = "bars") -> str:
    on, off = STYLES.get(style, STYLES["bars"])
    filled = round(WIDTH * done / total) if total else 0
    return on * filled + off * (WIDTH - filled)


def line(data: dict, style: str = "bars") -> str:
    tasks = data.get("tasks") or []
    open_t = [t for t in tasks if t.get("status") != "done" and any(s.get("status") != "done" for s in t.get("steps") or [])]
    if not open_t:
        return f"no open task · {len(tasks)} task(s) recorded" if tasks else "no task yet: growth tasks add \"...\""
    main = max(open_t, key=lambda t: len(t.get("steps") or []))   # the main job: the open task with most steps
    steps = main.get("steps") or []
    done = sum(1 for s in steps if s.get("status") == "done")
    now = next((s for s in steps if s.get("status") != "done"), {})
    what = " ".join((now.get("what") or "").split())[:60]
    flag = f" ({now['status']})" if now.get("status") in ("blocked", "waiting-owner") else ""
    more = f" · +{len(open_t) - 1} other open" if len(open_t) > 1 else ""
    return f"{main.get('id', '?')} {bar(done, len(steps), style)} {done}/{len(steps)} · now: step {now.get('n', '?')} {what}{flag}{more}"


def main() -> None:
    try:
        if not sys.stdin.isatty():
            sys.stdin.read()
    except (OSError, ValueError):
        pass
    try:
        project = project_dir()
        print(line(json.loads(tasks_file(project).read_text()), settings(project).get("statusline_style") or "bars"))
    except FileNotFoundError:
        print("no task list yet (docs/tasks.json)")
    except Exception as e:  # noqa: BLE001  (a status line must never break the agent's window)
        print(f"task list unreadable: {type(e).__name__}")


if __name__ == "__main__":
    main()
