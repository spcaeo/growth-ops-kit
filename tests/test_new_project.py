"""growth new-project makes a project folder from templates/project, never by copying another project."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

import new_project

ROOT = Path(__file__).resolve().parent.parent


def test_makes_the_folder_and_fills_the_site(tmp_path):
    folder, made = new_project.make(tmp_path / "acme", "https://www.acme-roofing.example", stack="nextjs")
    cfg = json.loads((folder / "growth.json").read_text())
    assert cfg["site_url"] == "https://www.acme-roofing.example" and cfg["name"] == "Www" or cfg["name"]
    assert cfg["stack"] == "nextjs"
    assert cfg["sitemap_url"] == "https://www.acme-roofing.example/sitemap.xml"
    for f in ("BRAND.md", "OWNER-RULES.md", "SETUP.md", "CLAUDE.md", "docs/steps-log.md", "docs/tasks.json", ".gitignore"):
        assert (folder / f).is_file(), f
    for d in ("journal", "research", "inventory", "archive", "page-tracker"):
        assert (folder / d).is_dir()
    assert [t["title"] for t in json.loads((folder / "docs" / "tasks.json").read_text())["tasks"]] == ["Project setup"]
    assert "{{" not in (folder / "growth.json").read_text()


def test_name_comes_from_the_address_or_the_flag(tmp_path):
    assert new_project.name_from("https://www.brightline-lawn.example") == "Brightline Lawn"
    folder, _ = new_project.make(tmp_path / "x", "https://x.example", name="Ex Ample")
    assert json.loads((folder / "growth.json").read_text())["name"] == "Ex Ample"


def test_refuses_a_folder_that_has_files_and_never_overwrites(tmp_path):
    f = tmp_path / "p"
    f.mkdir()
    (f / "mine.txt").write_text("keep")
    with pytest.raises(SystemExit):
        new_project.make(f, "https://x.example")
    folder, made = new_project.make(f, "https://x.example", force=True)
    assert (f / "mine.txt").read_text() == "keep"
    (f / "BRAND.md").write_text("my brand")
    new_project.make(f, "https://x.example", force=True)
    assert (f / "BRAND.md").read_text() == "my brand"


def test_bad_site_address_is_refused(tmp_path):
    with pytest.raises(SystemExit):
        new_project.make(tmp_path / "p", "not a url")


def test_it_comes_from_the_template_not_from_another_project(tmp_path):
    """Change the template and the new project changes; nothing is read from any other folder."""
    t = tmp_path / "tpl"
    (t / "docs").mkdir(parents=True)
    (t / "growth.json").write_text('{"name": "{{name}}", "site_url": "{{site_url}}"}')
    (t / "docs" / "note.md").write_text("Hello {{name}}")
    folder, made = new_project.make(tmp_path / "out", "https://q.example", name="Qq", template=t)
    assert (folder / "docs" / "note.md").read_text() == "Hello Qq"


def test_cli_and_doctor_work_on_the_new_project(tmp_path):
    r = subprocess.run([sys.executable, str(ROOT / "growth"), "new-project", str(tmp_path / "np"), "--site", "https://np.example"],
                       capture_output=True, text=True)
    assert r.returncode == 0 and "Project made" in r.stdout
    d = subprocess.run([sys.executable, str(ROOT / "growth"), "doctor"], capture_output=True, text=True, cwd=tmp_path / "np")
    assert "A2 Project adapted" in d.stdout


def test_a_new_project_gets_the_onboard_skill_and_the_stop_hook(tmp_path):
    folder, made = new_project.make(tmp_path / "acme", "https://acme.example", name="Acme Mowing")
    skill = folder / ".claude" / "skills" / "onboard" / "SKILL.md"
    assert skill.is_file()
    text = skill.read_text()
    assert "Acme Mowing" in text and "https://acme.example" in text and "name: onboard" in text
    assert "](../../../book/" not in text and str(new_project.KIT_DIR.parent) in text        # links resolve from the project
    cfg = json.loads((folder / ".claude" / "settings.json").read_text())
    cmd = cfg["hooks"]["Stop"][0]["hooks"][0]["command"]
    assert "growth" in cmd and cmd.endswith("hook stop") and "CLAUDE_PROJECT_DIR" in cmd
    assert "command -v growth" in cmd and str(new_project.KIT_DIR.parent) in cmd       # PATH first, this kit folder only as the fallback
    claude = (folder / "CLAUDE.md").read_text()
    assert "Acme Mowing" in claude and "<fill in" not in claude and str(new_project.KIT_DIR.parent) in claude


def test_the_stop_hook_merges_into_existing_settings_and_is_not_added_twice(tmp_path):
    f = tmp_path / "p"
    (f / ".claude").mkdir(parents=True)
    (f / ".claude" / "settings.json").write_text(json.dumps({"permissions": {"allow": ["Bash(ls)"]}}))
    new_project.make(f, "https://x.example", force=True)
    new_project.make(f, "https://x.example", force=True)
    cfg = json.loads((f / ".claude" / "settings.json").read_text())
    assert cfg["permissions"]["allow"][0] == "Bash(ls)" and len(cfg["hooks"]["Stop"]) == 1       # the owner's own entry stays first


def test_doctor_checks_the_hook_and_the_preview_address(tmp_path):
    folder, _ = new_project.make(tmp_path / "acme", "https://acme.example")
    def doctor():
        return subprocess.run([sys.executable, str(ROOT / "kit" / "tools" / "doctor.py")], cwd=folder, capture_output=True, text=True,
                              env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)}).stdout
    out = doctor()
    assert "OK    A10 Agent guards installed" in out and "TODO  A11 Preview address set" in out
    (folder / ".claude" / "settings.json").unlink()
    assert "FAIL  A10 Agent guards installed" in doctor()


def test_a_fresh_project_passes_the_setup_steps_that_need_no_keys(tmp_path):
    r = subprocess.run([sys.executable, str(ROOT / "kit" / "tools" / "new_project.py"), str(tmp_path / "acme"), "--site", "https://acme.example"],
                       capture_output=True, text=True, env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)})
    assert r.returncode == 0, r.stderr
    out = subprocess.run([sys.executable, str(ROOT / "kit" / "tools" / "doctor.py")], cwd=tmp_path / "acme", capture_output=True, text=True,
                         env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)}).stdout
    for step in ("A2 ", "A3 ", "A4 ", "A6 ", "A9 ", "A10 "):
        assert any(l.startswith("OK") and step in l for l in out.splitlines()), (step, out)
    for step in ("A1 ", "A5 ", "A7 ", "A8 ", "A11 "):         # these wait for work or the owner, each with a fix line
        line = next(l for l in out.splitlines() if step in l[:10])
        assert not line.startswith("OK") and "fix:" in out.split(line, 1)[1].splitlines()[1]


def test_new_project_moves_the_tracker_port_when_the_default_is_taken(tmp_path, monkeypatch):
    default = json.loads((ROOT / "templates" / "project" / "growth.json").read_text())["tracker_port"]
    monkeypatch.setattr(new_project, "port_is_free", lambda p: p != default)
    folder, _ = new_project.make(tmp_path / "busy", "https://x.example")
    assert json.loads((folder / "growth.json").read_text())["tracker_port"] == default + 1
    monkeypatch.setattr(new_project, "port_is_free", lambda p: True)
    folder, _ = new_project.make(tmp_path / "free", "https://x.example")
    assert json.loads((folder / "growth.json").read_text())["tracker_port"] == default


def test_doctor_warns_when_another_program_holds_the_tracker_port(tmp_path):
    import socket
    import os
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    try:
        folder, _ = new_project.make(tmp_path / "p", "https://x.example")
        cfg = json.loads((folder / "growth.json").read_text())
        cfg["tracker_port"] = port
        (folder / "growth.json").write_text(json.dumps(cfg))
        db = folder / "page-tracker" / "tracker.db"
        import sqlite3
        c = sqlite3.connect(db)
        c.execute("create table search (day text, path text)")
        c.commit()
        c.close()
        env = {**os.environ, "GROWTH_PROJECT": str(folder), "GROWTH_CRONTAB": "", "GROWTH_LAUNCHD_DIRS": str(folder / "none")}
        out = subprocess.run([sys.executable, str(ROOT / "kit" / "tools" / "doctor.py")], cwd=folder, capture_output=True, text=True, env=env).stdout
        assert f"port {port} is in use by another program" in out
        assert f"set tracker_port in growth.json to a free port ({port} is taken)" in out
    finally:
        srv.close()
def test_hook_commands_use_the_growth_command_and_old_ones_are_moved(tmp_path):
    f = tmp_path / "p"
    (f / ".claude").mkdir(parents=True)
    old = 'GROWTH_PROJECT="$CLAUDE_PROJECT_DIR" bash "${GROWTH_KIT:-/old/place}/kit/hooks/stop_hook.sh"'
    old_status = 'GROWTH_PROJECT="$CLAUDE_PROJECT_DIR" python3 "${GROWTH_KIT:-/old/place}/kit/tools/statusline.py"'
    (f / ".claude" / "settings.json").write_text(json.dumps({"hooks": {"Stop": [{"hooks": [{"type": "command", "command": old}]}]},
                                                             "statusLine": {"type": "command", "command": old_status}}))
    new_project.make(f, "https://x.example", force=True)
    cfg = json.loads((f / ".claude" / "settings.json").read_text())
    assert len(cfg["hooks"]["Stop"]) == 1
    assert cfg["hooks"]["Stop"][0]["hooks"][0]["command"].endswith("growth\")\" hook stop") and "/old/place" not in json.dumps(cfg)
    assert cfg["statusLine"]["command"].endswith("statusline") and "statusline.py" not in cfg["statusLine"]["command"]


def test_growth_hook_stop_runs_the_stop_hook(tmp_path):
    r = subprocess.run([sys.executable, str(ROOT / "growth"), "hook"], capture_output=True, text=True)
    assert r.returncode == 2 and "Available: stop" in r.stderr
    assert "hook" in subprocess.run([sys.executable, str(ROOT / "growth"), "help", "--all"], capture_output=True, text=True).stdout


def test_doctor_a12_flags_a_kit_folder_that_is_gone(tmp_path):
    folder, _ = new_project.make(tmp_path / "acme", "https://acme.example")
    def a12():
        out = subprocess.run([sys.executable, str(ROOT / "kit" / "tools" / "doctor.py")], cwd=folder, capture_output=True, text=True,
                             env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)}).stdout
        return [l for l in out.splitlines() if "A12" in l][0]
    assert a12().startswith("OK")
    settings = folder / ".claude" / "settings.json"
    settings.write_text(settings.read_text().replace(str(new_project.KIT_DIR.parent), "/nowhere/kit"))
    assert a12().startswith("FAIL") and "/nowhere/kit" in a12()
