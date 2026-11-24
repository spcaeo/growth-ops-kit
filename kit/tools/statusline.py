#!/usr/bin/env python3
"""Claude Code status line: the open task's progress, always visible at the bottom of the agent's window.

  T3 ▰▰▱▱▱▱▱▱▱▱ 9/44 · now: step 10 Search Console research · manual checks 3/12 · +1 other open

"manual checks 3/12" counts the project's own rules in the page's checkpoints file (research/<key>-checkpoints.md, the one
the open task names, else the newest) that are ticked with a proof, out of all of them; it hides when the file has none.

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


def bar(done: int, total: int, style: str = "bars") -> str:
    on, off = STYLES.get(style, STYLES["bars"])
    filled = round(WIDTH * done / total) if total else 0
    return on * filled + off * (WIDTH - filled)


def label(step: dict) -> str:
    """A short name for a step: no leading "Step 7." and no command after the first ":" or "(" (fits one line)."""
    import re
    what = " ".join((step.get("what") or "").split())
    what = re.sub(r"^(step\s*)?\d+[.):]?\s*", "", what, flags=re.I)
    what = re.split(r"[:(]", what, maxsplit=1)[0].strip(" .-")
    return what[:42] + ("…" if len(what) > 42 else "")


ACTIVE = ("doing", "in_progress", "in progress", "active")
STUCK = ("blocked", "waiting-owner", "waiting")


def manual_checks(project: Path, data: dict) -> str:
    """"manual checks n/m" from the page's checkpoints file, or "" (no file, none, or unreadable)."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import checkpoints
        files = sorted((project / "research").glob("*-checkpoints.md"), key=lambda p: p.stat().st_mtime, reverse=True)
        words = " ".join(f"{t.get('title', '')} {t.get('owner_words', '')}" for t in data.get("tasks") or [] if t.get("status") != "done").lower()
        pick = next((f for f in files if f.name[:-len("-checkpoints.md")].lower() in words), files[0] if files else None)
        if pick is None:
            return ""
        total, done, _ = checkpoints.manual_status(pick.read_text())
        return f"manual checks {done}/{total}" if total else ""
    except Exception:  # noqa: BLE001  (never break the status line)
        return ""


def line(data: dict, style: str = "bars", manual: str = "") -> str:
    tasks = data.get("tasks") or []
    open_t = [t for t in tasks if t.get("status") != "done" and any(s.get("status") != "done" for s in t.get("steps") or [])]
    if not open_t:
        return f"no open task · {len(tasks)} task(s) recorded" if tasks else "no task yet: growth tasks add \"...\""
    # the main job: a task being worked on (status doing) first, then one still to start; a task that is blocked or waiting
    # (for a date, for the owner) never takes the bar from live work (friction 47: blocked T3, 60 steps, hid doing T13).
    # Among equals, the one with most steps.
    tstat = lambda t: (t.get("status") or "todo").lower()  # noqa: E731
    rank = lambda t: (tstat(t) in ACTIVE, tstat(t) not in STUCK, len(t.get("steps") or []))  # noqa: E731
    main = max(open_t, key=rank)
    steps = main.get("steps") or []
    done = sum(1 for s in steps if s.get("status") == "done")
    # "now" is the step being worked on (status doing), else the first step still to do; stuck steps are listed apart,
    # so a blocked early step never hides that later steps are moving.
    now = next((s for s in steps if (s.get("status") or "").lower() in ACTIVE), None) or \
        next((s for s in steps if (s.get("status") or "todo").lower() not in ("done", *STUCK)), None)
    stuck = [s for s in steps if (s.get("status") or "").lower() in STUCK]
    parts = [f"{main.get('id', '?')}{' (waiting)' if tstat(main) in STUCK else ''} {bar(done, len(steps), style)} {done}/{len(steps)}"]
    if now:
        parts.append(f"now: {now.get('n', '?')} {label(now)}")
    if stuck:
        parts.append("blocked: " + ", ".join(str(s.get("n", "?")) for s in stuck))
    if manual:
        parts.append(manual)
    if len(open_t) > 1:
        waiting = sum(1 for t in open_t if t is not main and tstat(t) in STUCK)
        parts.append(f"+{len(open_t) - 1} other open" + (f" ({waiting} waiting)" if waiting else ""))
    return " · ".join(parts)


def main() -> None:
    try:
        if not sys.stdin.isatty():
            sys.stdin.read()
    except (OSError, ValueError):
        pass
    try:
        project = project_dir()
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import records
        data = records.tasks_doc(project)
        print(line(data, settings(project).get("statusline_style") or "bars", manual_checks(project, data)))
    except FileNotFoundError:
        print("no task list yet (docs/tasks.json)")
    except Exception as e:  # noqa: BLE001  (a status line must never break the agent's window)
        print(f"task list unreadable: {type(e).__name__}")


if __name__ == "__main__":
    main()
