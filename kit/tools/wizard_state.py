"""The setup wizard's memory: setup-state.json in the project folder (library; `growth wizard` is the command).

Each wizard step keeps a status (todo / asked / answered / tested / done / declined), the answer, where it came from
(owner, detected, answers-file, agent), the date, and the test that proved it (the command and its result line). A
stopped run resumes at the first step that is not done or declined. No secret is ever stored here: a keys file is
named by its path only.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

FILE = "setup-state.json"
STATUSES = ("todo", "asked", "answered", "tested", "done", "declined")
CLOSED = ("done", "declined")


def path(project) -> Path:
    return Path(project) / FILE


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="minutes")


def load(project) -> dict:
    try:
        data = json.loads(path(project).read_text())
        if isinstance(data.get("steps"), dict):
            return data
    except (OSError, ValueError):
        pass
    return {"version": 1, "started": now(), "steps": {}}


def save(project, state: dict) -> None:
    state["updated"] = now()
    tmp = path(project).with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(path(project))


def get(project, step: str) -> dict:
    return load(project)["steps"].get(step) or {"status": "todo"}


def record(project, step: str, status: str, answer=None, source: str = "", test: dict | None = None, **extra) -> dict:
    """Write one step. A field left out keeps what was there, so a later test never erases the answer."""
    if status not in STATUSES:
        raise ValueError(f"unknown status {status}")
    state = load(project)
    entry = state["steps"].get(step) or {}
    entry["status"] = status
    entry["date"] = now()
    if answer is not None:
        entry["answer"] = answer
    if source:
        entry["source"] = source
    if test:
        entry["test"] = test
    entry.update(extra)
    state["steps"][step] = entry
    save(project, state)
    return entry


def first_open(project, order) -> str | None:
    steps = load(project)["steps"]
    return next((s for s in order if (steps.get(s) or {}).get("status", "todo") not in CLOSED), None)
