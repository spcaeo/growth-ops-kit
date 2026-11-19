"""The status line: the open task's progress in the chosen style, and new-project registers it. No network."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "kit" / "tools"))
import statusline  # noqa: E402

TASKS = {"tasks": [
    {"id": "T1", "status": "done", "steps": [{"n": 1, "what": "a", "status": "done"}]},
    {"id": "T3", "status": "doing", "steps": [{"n": i, "what": f"step {i}", "status": "done" if i <= 9 else "todo"} for i in range(1, 45)]},
    {"id": "T4", "status": "doing", "steps": [{"n": 1, "what": "x", "status": "todo"}]},
]}


def test_main_job_progress_in_squares():
    out = statusline.line(TASKS)
    assert out.startswith("T3 ▰▰▱▱▱▱▱▱▱▱ 9/44 · now: step 10 step 10")
    assert out.endswith("+1 other open")


def test_styles_and_unknown_style_falls_back():
    assert statusline.bar(5, 10, "dots") == "●●●●●○○○○○"
    assert statusline.bar(5, 10, "plain") == "#####-----"
    assert statusline.bar(5, 10, "nonsense") == "▰▰▰▰▰▱▱▱▱▱"


def test_blocked_step_is_named():
    t = {"tasks": [{"id": "T2", "status": "doing", "steps": [{"n": 1, "what": "snapshot", "status": "blocked"}]}]}
    assert statusline.line(t).endswith("now: step 1 snapshot (blocked)")


def test_no_tasks_and_broken_file_never_fail(tmp_path):
    (tmp_path / "growth.json").write_text("{}")
    run = lambda: subprocess.run([sys.executable, str(ROOT / "kit/tools/statusline.py")], input="{}", text=True,
                                 capture_output=True, env={"GROWTH_PROJECT": str(tmp_path), "PATH": ""})
    r = run()
    assert r.returncode == 0 and "no task list yet" in r.stdout
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "tasks.json").write_text("{not json")
    r = run()
    assert r.returncode == 0 and "unreadable" in r.stdout
    (tmp_path / "growth.json").write_text(json.dumps({"statusline_style": "checks"}))
    (tmp_path / "docs" / "tasks.json").write_text(json.dumps(TASKS))
    assert "☑☑☐☐☐☐☐☐☐☐ 9/44" in run().stdout


def test_new_project_registers_statusline_and_keeps_other_settings(tmp_path):
    import new_project
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.json").write_text(json.dumps({"model": "keep-me"}))
    new_project.agent_files(tmp_path, "Demo", "https://example.com", ROOT)
    cfg = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    assert cfg["model"] == "keep-me"
    assert "statusline.py" in cfg["statusLine"]["command"]
    assert cfg["hooks"]["Stop"][0]["hooks"][0]["statusMessage"]
    cfg["statusLine"] = {"type": "command", "command": "my own"}
    (tmp_path / ".claude" / "settings.json").write_text(json.dumps(cfg))
    new_project.agent_files(tmp_path, "Demo", "https://example.com", ROOT)
    assert json.loads((tmp_path / ".claude" / "settings.json").read_text())["statusLine"]["command"] == "my own"
