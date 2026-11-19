"""Setup itself is a task: new-project opens it, doctor ticks and un-ticks its steps with proof, the status bar shows it (#26),
and doctor A15 flags work outside any task (#24)."""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import new_project  # noqa: E402
import setup_task  # noqa: E402
from wizard_helpers import ROOT, env, growth  # noqa: E402


def tasks(folder):
    return json.loads((folder / "docs" / "tasks.json").read_text())["tasks"]


def test_new_project_opens_the_setup_task_with_one_step_per_doctor_step(tmp_path):
    folder, _ = new_project.make(tmp_path / "p", "https://shop.example")
    t = tasks(folder)[0]
    assert t["title"] == "Project setup" and t["status"] == "doing"
    assert [s["what"].split(" ", 1)[0] for s in t["steps"]] == [i for i, _ in setup_task.doctor_steps()]
    assert {"A1", "A7b", "A13", "A14", "A15"} <= {i for i, _ in setup_task.doctor_steps()}
    new_project.make(folder, "https://shop.example", force=True)
    assert len(tasks(folder)) == 1                              # opened once


def test_doctor_ticks_a_step_with_its_own_line_and_unticks_it_again(tmp_path):
    folder, _ = new_project.make(tmp_path / "p", "https://shop.example")
    growth(tmp_path, "doctor", cwd=folder)
    steps = {s["what"].split(" ", 1)[0]: s for s in tasks(folder)[0]["steps"]}
    assert steps["A6"]["status"] == "done" and steps["A6"]["output"].startswith("doctor OK:") and steps["A1"]["status"] == "todo"
    (folder / "docs" / "01-project-understanding.md").write_text("x")
    growth(tmp_path, "doctor", cwd=folder)
    assert {s["what"].split(" ", 1)[0]: s for s in tasks(folder)[0]["steps"]}["A1"]["status"] == "done"
    (folder / "docs" / "01-project-understanding.md").unlink()
    growth(tmp_path, "doctor", cwd=folder)
    assert {s["what"].split(" ", 1)[0]: s for s in tasks(folder)[0]["steps"]}["A1"]["status"] == "todo"


def test_the_task_is_done_only_when_every_step_is(tmp_path):
    folder, _ = new_project.make(tmp_path / "p", "https://shop.example")
    rows = [(f"{i} {t}", "OK  ", "fine") for i, t in setup_task.doctor_steps()]
    assert setup_task.sync(folder, rows) and tasks(folder)[0]["status"] == "done"
    rows[0] = (rows[0][0], "FAIL", "gone")
    setup_task.sync(folder, rows)
    assert tasks(folder)[0]["status"] == "doing" and tasks(folder)[0]["finished"] is None


def test_the_status_bar_shows_setup_progress_from_minute_one(tmp_path):
    folder, _ = new_project.make(tmp_path / "p", "https://shop.example")
    growth(tmp_path, "doctor", cwd=folder)
    line = growth(tmp_path, "statusline", cwd=folder).stdout
    assert line.startswith("T1 ▰") and "now:" in line


def test_the_onboard_skill_and_the_task_share_doctors_step_list(tmp_path):
    skill = (ROOT / "kit" / "skills" / "onboard" / "SKILL.md").read_text()
    for sid, _ in setup_task.doctor_steps():
        assert f"| {sid} " in skill


def test_a15_flags_changed_files_with_no_open_task(tmp_path):
    folder, _ = new_project.make(tmp_path / "p", "https://shop.example")
    e = env(tmp_path)
    subprocess.run(["git", "init", "-q", str(folder)], check=True, env=e)
    a15 = next(l for l in growth(tmp_path, "doctor", cwd=folder).stdout.splitlines() if "A15" in l)
    assert a15.startswith("OK")                                 # the setup task is open: the setup files belong to it
    (folder / "notes.txt").write_text("work")                   # a page-like file needs a page task, not the setup task
    assert next(l for l in growth(tmp_path, "doctor", cwd=folder).stdout.splitlines() if "A15" in l).startswith("TODO")
    growth(tmp_path, "tasks", "status", "T1", "done", cwd=folder)
    out = growth(tmp_path, "doctor", cwd=folder).stdout
    a15 = next(l for l in out.splitlines() if "A15" in l)
    assert a15.startswith("TODO") and ("no task is open" in a15 or "no file changes" in a15 or "page task" in a15) and "growth tasks add" in out
    growth(tmp_path, "tasks", "add", "Chat: x", "", "--type", "chat", cwd=folder)
    assert next(l for l in growth(tmp_path, "doctor", cwd=folder).stdout.splitlines() if "A15" in l).startswith("TODO")   # a chat task covers no file changes
