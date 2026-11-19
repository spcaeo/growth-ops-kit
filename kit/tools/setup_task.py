"""Setup is a task (library): task "Project setup" in docs/tasks.json, one step per doctor step.

`growth new-project` and the wizard open it with `ensure`; `growth doctor` ticks a step with its own result line as the
proof when the step turns OK (or BUSY) and un-ticks it when it is TODO or FAIL again (`sync`). The step list is read from
doctor.py itself, so the task and doctor can never drift apart.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

TITLE = "Project setup"
OWNER_WORDS = "Set the project up: every setup step doctor lists, in order, ticked with its proof."
DOCTOR = Path(__file__).resolve().parent / "doctor.py"


def doctor_steps() -> list[tuple[str, str]]:
    """[("A1", "Understand the business and site"), ...] in doctor's order."""
    return re.findall(r'^\s*row\("(A\d+b?) ([^"]+)"', DOCTOR.read_text(), re.M)


def _file(project: Path, cfg: dict) -> Path:
    return Path(project) / (cfg.get("project_docs") or "docs") / "tasks.json"


def _now(cfg: dict) -> str:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(cfg.get("timezone", "UTC"))).strftime("%Y-%m-%d %H:%M %Z")
    except Exception:  # noqa: BLE001
        return datetime.now().strftime("%Y-%m-%d %H:%M")


def _load(f: Path, project: Path, cfg: dict) -> dict:
    try:
        return json.loads(f.read_text())
    except (OSError, ValueError):
        return {"project": cfg.get("name", ""), "site": cfg.get("site_url", ""), "updated": "", "tasks": [], "questions": []}


def _save(f: Path, db: dict, cfg: dict) -> None:
    db["updated"] = _now(cfg)
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(db, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(f)


def find(db: dict) -> dict | None:
    return next((t for t in db.get("tasks", []) if t.get("title") == TITLE), None)


def ensure(project, cfg: dict | None = None) -> str:
    """Open the setup task (or add the steps a newer doctor has and it lacks). Returns its id. Never changes a step's status."""
    project = Path(project)
    cfg = cfg if cfg is not None else json.loads((project / "growth.json").read_text())
    f = _file(project, cfg)
    db = _load(f, project, cfg)
    task = find(db)
    if task is None:
        tid = f"T{max((int(t['id'][1:]) for t in db['tasks'] if re.fullmatch(r'T\d+', t['id'])), default=0) + 1}"
        task = {"id": tid, "title": TITLE, "owner_words": OWNER_WORDS, "status": "doing", "started": _now(cfg),
                "finished": None, "steps": []}
        db["tasks"].append(task)
    have = {s["what"].split(" ", 1)[0] for s in task["steps"]}
    for sid, title in doctor_steps():
        if sid not in have:
            task["steps"].append({"n": len(task["steps"]) + 1, "what": f"{sid} {title}", "status": "todo", "at": _now(cfg), "output": None})
    _save(f, db, cfg)
    return task["id"]


def sync(project, results, cfg: dict | None = None) -> bool:
    """results: [(step name as doctor prints it, state "OK  "|"BUSY"|"TODO"|"FAIL", result line)]. Ticks done steps with the
    line as proof, un-ticks the others. Returns True when the file changed. Does nothing when there is no setup task."""
    project = Path(project)
    cfg = cfg if cfg is not None else json.loads((project / "growth.json").read_text())
    f = _file(project, cfg)
    if not f.is_file():
        return False
    db = _load(f, project, cfg)
    task = find(db)
    if task is None:
        return False
    changed = False
    for name, st, what in results:
        sid = name.split(" ", 1)[0]
        step = next((s for s in task["steps"] if s["what"].split(" ", 1)[0] == sid), None)
        if step is None:
            continue
        done = st.strip() in ("OK", "BUSY")
        new = "done" if done else "todo"
        proof = f"doctor {st.strip()}: {what}"[:240]
        if step["status"] != new or (done and step.get("output") != proof):
            step["status"], step["at"], step["output"] = new, _now(cfg), proof if done else None
            changed = True
    all_done = all(s["status"] == "done" for s in task["steps"])
    want = "done" if all_done else ("doing" if task["status"] == "done" else task["status"])
    if want != task["status"]:
        task["status"], task["finished"] = want, (_now(cfg) if want == "done" else None)
        changed = True
    if changed:
        _save(f, db, cfg)
    return changed
