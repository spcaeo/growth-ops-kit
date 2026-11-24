"""The agent harness: installed in one go, never overwriting the owner's settings, checked as doctor A13 (#32 #33 #41),
with the workflow guard (`growth hook stage`, #24)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import harness  # noqa: E402
import new_project  # noqa: E402
import wizard_state as ws  # noqa: E402
from wizard_helpers import growth  # noqa: E402


def settings(folder):
    return json.loads((folder / ".claude" / "settings.json").read_text())


def test_install_writes_every_piece_with_status_messages(tmp_path):
    folder, _ = new_project.make(tmp_path / "p", "https://shop.example")
    cfg = settings(folder)
    stop = cfg["hooks"]["Stop"][0]["hooks"][0]
    stage = cfg["hooks"]["PostToolUse"][0]
    assert stop["statusMessage"] and stage["matcher"] == "Bash" and stage["hooks"][0]["command"].endswith("hook stage")
    assert stage["hooks"][0]["statusMessage"] == "Re-reading the page checkpoints"
    assert "Bash(growth *)" in cfg["permissions"]["allow"] and "Bash(git push*)" in cfg["permissions"]["deny"]
    assert "Bash(git merge* main*)" in cfg["permissions"]["deny"]
    assert cfg["statusLine"]["command"].endswith("statusline")
    assert (folder / ".claude" / "skills" / "onboard" / "SKILL.md").is_file()
    assert "growth-harness:start" in (folder / "CLAUDE.md").read_text()
    assert all(st != "todo" for _, st, _, _ in harness.check(folder, json.loads((folder / "growth.json").read_text())))


def test_stage_hook_is_registered_once_and_never_duplicated(tmp_path):
    folder, _ = new_project.make(tmp_path / "p", "https://shop.example")
    new_project.make(folder, "https://shop.example", force=True)
    assert json.dumps(settings(folder)["hooks"]["PostToolUse"]).count("hook stage") == 1
    assert len(settings(folder)["hooks"]["Stop"]) == 1


def test_owner_settings_are_never_overwritten(tmp_path):
    f = tmp_path / "p"
    (f / ".claude").mkdir(parents=True)
    (f / ".claude" / "settings.json").write_text(json.dumps({"model": "mine", "statusLine": {"type": "command", "command": "my-bar"},
                                                             "permissions": {"allow": ["Bash(ls)"], "deny": ["Bash(git push*)"]},
                                                             "hooks": {"PostToolUse": [{"matcher": "Edit", "hooks": [{"type": "command", "command": "x"}]}]}}))
    (f / "CLAUDE.md").write_text("# mine\n")
    new_project.make(f, "https://shop.example", force=True)
    cfg = settings(f)
    assert cfg["model"] == "mine" and cfg["statusLine"]["command"] == "my-bar"
    assert cfg["permissions"]["allow"][0] == "Bash(ls)" and cfg["permissions"]["deny"].count("Bash(git push*)") == 1
    assert cfg["hooks"]["PostToolUse"][0]["matcher"] == "Edit" and len(cfg["hooks"]["PostToolUse"]) == 2
    assert (f / "CLAUDE.md").read_text().startswith("# mine\n")


def test_permissions_deny_deploys_and_a_live_fetch_when_the_rule_says_so():
    allow, deny = harness.permissions_wanted({"site_url": "https://shop.example", "live_site_rule": "no-crawl", "deploy_commands": ["./ship.sh"]})
    assert "Bash(./ship.sh*)" in deny and "WebFetch(domain:shop.example)" in deny
    assert not any("shop.example" in d for d in harness.permissions_wanted({"site_url": "https://shop.example"})[1])
    assert "Bash(git status*)" in allow and not any("push" in a for a in allow)


def test_a13_lists_each_piece_todo_then_repair_fixes_it_and_keeps_the_owner_entries(tmp_path):
    folder, _ = new_project.make(tmp_path / "p", "https://shop.example")
    p = folder / ".claude" / "settings.json"
    cfg = settings(folder)
    del cfg["hooks"]["PostToolUse"]
    cfg["hooks"]["Stop"][0]["hooks"][0].pop("statusMessage")
    del cfg["permissions"]
    cfg["permissions"] = {"allow": ["Bash(ls)"]}
    p.write_text(json.dumps(cfg))
    out = growth(tmp_path, "doctor", cwd=folder).stdout
    a13 = next(l for l in out.splitlines() if "A13" in l)
    assert a13.startswith("TODO") and "Workflow guard (hook stage): TODO" in a13 and "Stop hook with status message: TODO" in a13
    assert "growth wizard --repair" in out
    assert growth(tmp_path, "wizard", "--repair", cwd=folder).returncode == 0
    fixed = settings(folder)
    assert "Bash(ls)" in fixed["permissions"]["allow"] and "Bash(git push*)" in fixed["permissions"]["deny"]
    assert next(l for l in growth(tmp_path, "doctor", cwd=folder).stdout.splitlines() if "A13" in l).startswith("OK")


def test_a_declined_permissions_block_is_not_a_todo(tmp_path):
    folder, _ = new_project.make(tmp_path / "p", "https://shop.example", permissions=False)
    ws.record(folder, "harness", "done", answer={"permissions": False, "git_hooks": False}, source="owner")
    rows = {r[0]: r for r in harness.check(folder, json.loads((folder / "growth.json").read_text()))}
    assert rows["Permissions block"][1] == "na" and rows["Git hooks"][1] == "na"


def test_a10_and_a12_expect_the_stage_hook(tmp_path):
    folder, _ = new_project.make(tmp_path / "p", "https://shop.example")
    assert next(l for l in growth(tmp_path, "doctor", cwd=folder).stdout.splitlines() if "A10" in l).startswith("OK")
    cfg = settings(folder)
    del cfg["hooks"]["PostToolUse"]
    (folder / ".claude" / "settings.json").write_text(json.dumps(cfg))
    a10 = next(l for l in growth(tmp_path, "doctor", cwd=folder).stdout.splitlines() if "A10" in l)
    assert a10.startswith("TODO") and "hook stage" in a10
    cfg = settings(folder)
    cfg["hooks"]["PostToolUse"] = [{"matcher": "Bash", "hooks": [{"type": "command", "command": 'GROWTH_PROJECT=x "${GROWTH_KIT:-/nowhere/kit}/growth" hook stage'}]}]
    (folder / ".claude" / "settings.json").write_text(json.dumps(cfg))
    # GROWTH_KIT="" : a kit path exported in the caller's shell must not make the hook resolve (it made this test flaky)
    assert next(l for l in growth(tmp_path, "doctor", cwd=folder, PATH="/usr/bin:/bin", GROWTH_KIT="").stdout.splitlines() if "A12" in l).startswith("FAIL")


def test_git_hooks_are_installed_only_with_a_yes_and_a13_checks_them(tmp_path):
    folder, _ = new_project.make(tmp_path / "p", "https://shop.example")
    ws.record(folder, "harness", "done", answer={"permissions": True, "git_hooks": True}, source="owner")
    cfg = json.loads((folder / "growth.json").read_text())
    assert dict((r[0], r[1]) for r in harness.check(folder, cfg))["Git hooks"] == "todo"
    assert growth(tmp_path, "wizard", "--repair", cwd=folder).returncode == 0
    assert dict((r[0], r[1]) for r in harness.check(folder, cfg))["Git hooks"] == "ok"


# ---- audit C4: the permissions hand the agent no arbitrary code, no ref or hook changes, no owner-only commands ----------

def test_no_allow_entry_runs_arbitrary_code_or_moves_a_branch():
    allow, deny = harness.permissions_wanted({"site_url": "https://shop.example"})
    assert not any("python" in a or "pytest" in a for a in allow), allow
    assert "Bash(git branch*)" not in allow and "Bash(git branch --list*)" in allow
    for d in ("Bash(git branch -f*)", "Bash(git branch -D*)", "Bash(git update-ref*)", "Bash(*core.hooksPath*)", "Bash(*--no-verify*)",
              "Bash(git * push*)", "Bash(env git*)"):
        assert d in deny, d


def test_owner_only_commands_and_protected_files_are_denied():
    _, deny = harness.permissions_wanted({})
    for cmd in ("approve", "wizard confirm", "tasks answer", "journal answer", "install_hooks remove"):
        assert f"Bash(growth {cmd}*)" in deny and f"Bash(*/growth {cmd}*)" in deny, cmd
    for f in (".claude/settings.json", "growth.json", "approvals.jsonl", ".git/hooks/**", "docs/tasks.json", "setup-state.json"):
        assert f"Edit(**/{f})" in deny, f           # Edit rules cover every file-writing tool in Claude Code
    assert not any(d.startswith("Write(") for d in deny)   # Write(path) rules are never matched: only warnings
    assert "Read(~/.config/growth-ops-kit/**)" in deny
    assert any(d.startswith("Edit(//") and d.endswith("/**)") for d in deny)          # the kit folder itself


def test_repair_removes_the_old_unsafe_allow_entries_and_doctor_flags_them(tmp_path):
    folder, _ = new_project.make(tmp_path / "p", "https://shop.example")
    p = folder / ".claude" / "settings.json"
    cfg = settings(folder)
    cfg["permissions"]["allow"] += ["Bash(/x/.growth-ops-kit/venv/bin/python *)", "Bash(git branch*)", "Bash(pytest*)", "Bash(ls)"]
    p.write_text(json.dumps(cfg))
    row = next(r for r in harness.check(folder, json.loads((folder / "growth.json").read_text())) if r[0] == "Permissions block")
    assert row[1] == "todo" and "runs any code or moves a branch" in row[2]
    harness.install(folder, "p", "https://shop.example")
    allow = settings(folder)["permissions"]["allow"]
    assert "Bash(ls)" in allow and not any(harness.unsafe_allow(a) for a in allow)


def test_a_removed_deny_entry_or_a_bypassed_git_hook_is_noticed(tmp_path):
    import subprocess
    folder, _ = new_project.make(tmp_path / "p", "https://shop.example")
    cfg = json.loads((folder / "growth.json").read_text())
    p = folder / ".claude" / "settings.json"
    s = settings(folder)
    s["permissions"]["deny"].remove("Bash(git push*)")
    p.write_text(json.dumps(s))
    row = next(r for r in harness.check(folder, cfg) if r[0] == "Permissions block")
    assert row[1] == "todo" and "missing" in row[2]
    ws.record(folder, "harness", "done", answer={"permissions": True, "git_hooks": True})
    subprocess.run(["git", "init", "-q", str(folder)], check=True)
    subprocess.run(["git", "-C", str(folder), "config", "core.hooksPath", "/dev/null"], check=True)
    row = next(r for r in harness.check(folder, cfg) if r[0] == "Git hooks")
    assert row[1] == "todo" and "core.hooksPath" in row[2]


def test_growth_runs_only_kit_tools_by_name_never_a_path(tmp_path):
    import shutil
    import tempfile
    d = Path(tempfile.mkdtemp(prefix="gokevil"))           # the system temp folder: no hyphen, which growth would turn into _
    try:
        assert "-" not in str(d), d
        (d / "evil.py").write_text("print('RAN')\n")
        r = growth(tmp_path, "../" * 12 + str(d / "evil").lstrip("/"))
        assert r.returncode == 2 and "RAN" not in r.stdout
    finally:
        shutil.rmtree(d)
