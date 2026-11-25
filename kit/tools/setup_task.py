"""Setup is a task (library): task "Project setup" in docs/tasks.json, one step per doctor step.

`growth new-project` and the wizard open it with `ensure`; `growth doctor` ticks a step with its own result line as the
proof when the step turns OK (or BUSY) and un-ticks it when it is TODO or FAIL again (`sync`). The step list is read from
doctor.py itself, so the task and doctor can never drift apart.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import records  # noqa: E402  (the one access layer for the task list)

TITLE = "Project setup"
OWNER_WORDS = "Set the project up: every setup step doctor lists, in order, ticked with its proof."
DOCTOR = Path(__file__).resolve().parent / "doctor.py"


def doctor_steps() -> list[tuple[str, str]]:
    """[("A1", "Understand the business and site"), ...] in doctor's order."""
    seen: dict[str, str] = {}
    for sid, title in re.findall(r'^\s*row\("(A\d+b?) ([^"]+)"', DOCTOR.read_text(), re.M):     # a step may report from several branches
        seen.setdefault(sid, title)
    return list(seen.items())


def _now(cfg: dict) -> str:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(cfg.get("timezone", "UTC"))).strftime("%Y-%m-%d %H:%M %Z")
    except Exception:  # noqa: BLE001
        return datetime.now().strftime("%Y-%m-%d %H:%M")


def _default(cfg: dict) -> dict:
    return {"project": cfg.get("name", ""), "site": cfg.get("site_url", ""), "updated": "", "tasks": [], "questions": []}


def find(db: dict) -> dict | None:
    return next((t for t in db.get("tasks", []) if t.get("title") == TITLE), None)


def ensure(project, cfg: dict | None = None) -> str:
    """Open the setup task (or add the steps a newer doctor has and it lacks). Returns its id. Never changes a step's status."""
    project = Path(project)
    cfg = cfg if cfg is not None else json.loads((project / "growth.json").read_text())
    out = []

    def change(db):
        task = find(db)
        if task is None:
            top = max((int(t['id'][1:]) for t in db['tasks'] if re.fullmatch(r'T\d+', t['id'])), default=0)
            tid = f"T{top + 1}"
            task = {"id": tid, "title": TITLE, "owner_words": OWNER_WORDS, "status": "doing", "started": _now(cfg),
                    "finished": None, "steps": []}
            db["tasks"].append(task)
        have = {s["what"].split(" ", 1)[0] for s in task["steps"]}
        for sid, title in doctor_steps():
            if sid not in have:
                task["steps"].append({"n": len(task["steps"]) + 1, "what": f"{sid} {title}", "status": "todo", "at": _now(cfg), "output": None})
        db["updated"] = _now(cfg)
        out.append(task["id"])
    records.tasks_update(project, change, default=_default(cfg))      # one transaction: another writer's change is never lost
    return out[0]


# Steps that cannot start before something outside the agent's hands exists (owner, 24 Nov 2026: the bar must say where we
# are, not show a step as "now" that nobody can work on). step id -> (what it waits for, test on growth.json: True = still waiting)
WAITS = {"A7": ("the site to build and serve", lambda c: not c.get("site_repo")),
         "A7b": ("the site to build and serve", lambda c: not c.get("site_repo"))}


def waiting_for(sid: str, cfg: dict) -> str:
    w = WAITS.get(sid)
    return w[0] if w and w[1](cfg) else ""


def sync(project, results, cfg: dict | None = None) -> bool:
    """results: [(step name as doctor prints it, state "OK  "|"BUSY"|"TODO"|"FAIL", result line)]. Ticks done steps with the
    line as proof, un-ticks the others. Returns True when the list changed. Does nothing when there is no setup task."""
    project = Path(project)
    cfg = cfg if cfg is not None else json.loads((project / "growth.json").read_text())
    if not records.tasks_exists(project):
        return False
    changed = []

    def change(db):
        task = find(db)
        if task is None:
            return
        for name, st, what in results:
            sid = name.split(" ", 1)[0]
            step = next((s for s in task["steps"] if s["what"].split(" ", 1)[0] == sid), None)
            if step is None:
                continue
            done = st.strip() in ("OK", "BUSY")
            wait = "" if done else waiting_for(sid, cfg)
            new = "done" if done else ("waiting" if wait else "todo")
            proof = f"doctor {st.strip()}: {what}"[:240]
            if step["status"] != new or (done and step.get("output") != proof) or step.get("waiting_for", "") != wait:
                step["status"], step["at"], step["output"] = new, _now(cfg), proof if done else None
                if wait:
                    step["waiting_for"] = wait
                else:
                    step.pop("waiting_for", None)
                changed.append(1)
        left = [s for s in task["steps"] if s["status"] != "done"]
        if not left:
            want = "done"
        elif all(s["status"] == "waiting" for s in left):
            want = "waiting"                  # every open step waits on something outside: the bar says so instead of "now"
        else:
            want = "doing"
        if want != task["status"]:
            task["status"], task["finished"] = want, (_now(cfg) if want == "done" else None)
            changed.append(1)
        if changed:
            db["updated"] = _now(cfg)
    try:
        records.tasks_update(project, change)                          # nothing is written when nothing changed
    except (OSError, ValueError):                                      # a task list that cannot be read is left as it is
        return False
    return bool(changed)
