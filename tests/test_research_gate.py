"""The research browser is a hard gate: no research job starts until the browser is connected and Google's region is the
target country, both confirmed (#37)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import new_project  # noqa: E402
import research_gate as gate  # noqa: E402
import wizard_state as ws  # noqa: E402
from wizard_helpers import growth, owner_approve  # noqa: E402


def project(tmp_path, country="US", mode="terminal"):
    """These tests guard terminal mode (the 2.x way: the owner approves in their own terminal); chat mode, the 3.0
    default, has its own tests at the end of this file."""
    folder, _ = new_project.make(tmp_path / "p", "https://shop.example")
    cfg = json.loads((folder / "growth.json").read_text())
    cfg["approvals"]["mode"] = mode
    cfg["market"].update({"primary_country": country, "google_params": gate.google_params(country, "en")})
    (folder / "growth.json").write_text(json.dumps(cfg))
    import harness
    harness.install(folder, cfg.get("name") or "Shop", "https://shop.example")     # the agent permissions follow the mode
    return folder, cfg


def confirm_both(tmp_path, folder):
    """The agent records what it sees; the owner approves both in their own terminal (audit C4: --owner-confirmed on a
    command line, which the agent could type, no longer confirms anything)."""
    growth(tmp_path, "wizard", "confirm", "browser", "--name", "Browser 1", cwd=folder)
    growth(tmp_path, "wizard", "confirm", "region", "--seen", "United States", cwd=folder)
    for step in ("browser", "region"):
        rc, out = owner_approve(tmp_path, step, cwd=folder)
        assert rc == 0, out


def test_region_matching_never_trusts_current_region():
    m = {"primary_country": "US"}
    assert gate.region_matches("United States", m) and gate.region_matches("us", m)
    assert not gate.region_matches("Current Region", m) and not gate.region_matches("Canada", m) and not gate.region_matches("", m)


def test_gate_lists_what_is_missing_then_passes(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))                 # never the real signing key
    folder, cfg = project(tmp_path)
    probs = "; ".join(gate.problems(folder, cfg))
    assert "/chrome" in probs and "By default: on" in probs and "not verified" in probs
    ws.record(folder, "browser", "done", answer={"name": "Browser 1"})
    ws.record(folder, "region", "done", answer={"seen": "United States", "owner_confirmed": True})
    probs = gate.problems(folder, cfg)                      # "done" typed into setup-state.json is not the owner's approval
    assert len(probs) == 2 and all("no owner approval" in p and "growth approve" in p for p in probs)
    import approvals
    approvals.record(folder / "docs", "browser", "browser", approvals.browser_content("Browser 1"))
    approvals.record(folder / "docs", "region", "region", approvals.region_content("United States", "United States"))
    assert gate.problems(folder, cfg) == []


def test_gate_is_off_when_not_required(tmp_path):
    folder, cfg = project(tmp_path)
    cfg["research_browser"] = {"required": False}
    assert gate.problems(folder, cfg) == []


def test_google_params_carry_country_language_and_no_personalisation():
    assert gate.google_params("CA", "en-CA") == "gl=ca&hl=en&pws=0"


def test_confirm_region_current_region_fails_with_the_one_line_fix(tmp_path):
    folder, _ = project(tmp_path)
    r = growth(tmp_path, "wizard", "confirm", "region", "--seen", "Current Region", "--owner-confirmed", cwd=folder)
    assert r.returncode == 1 and "Results region" in r.stdout and "Current Region" in r.stdout
    assert ws.get(folder, "region")["status"] != "done"


def test_confirm_region_needs_the_owner_to_confirm(tmp_path):
    folder, _ = project(tmp_path)
    r = growth(tmp_path, "wizard", "confirm", "region", "--seen", "United States", cwd=folder)
    assert "growth approve region" in r.stdout and ws.get(folder, "region")["status"] == "tested"
    # audit C4: the flag the agent could type no longer confirms anything
    r = growth(tmp_path, "wizard", "confirm", "region", "--seen", "United States", "--owner-confirmed", cwd=folder)
    assert "no longer taken" in r.stdout and ws.get(folder, "region")["status"] == "tested"
    assert growth(tmp_path, "approve", "region", cwd=folder).returncode != 0          # no terminal: refused
    assert ws.get(folder, "region")["status"] == "tested"
    rc, out = owner_approve(tmp_path, "region", cwd=folder)
    assert rc == 0, out
    assert ws.get(folder, "region")["status"] == "done"


def test_doctor_a14_is_fail_until_confirmed_then_ok(tmp_path):
    folder, _ = project(tmp_path)
    assert growth(tmp_path, "doctor", cwd=folder).stdout.count("FAIL  A14") == 1
    confirm_both(tmp_path, folder)
    out = growth(tmp_path, "doctor", cwd=folder).stdout
    assert "OK    A14" in out and "OK    A13" in out


def test_tasks_add_with_a_research_playbook_is_refused_until_ready(tmp_path):
    folder, _ = project(tmp_path)
    r = growth(tmp_path, "tasks", "add", "New post", "write it", "--playbook", "new-post", cwd=folder)
    assert r.returncode != 0 and "research step" in (r.stdout + r.stderr) and "/chrome" in (r.stdout + r.stderr)
    assert growth(tmp_path, "tasks", "add", "Release", "", "--playbook", "release", cwd=folder).returncode == 0   # no research step (fix-a-fact re-reads the vendor page now, so it is research)
    assert growth(tmp_path, "tasks", "add", "x", "", "--research", cwd=folder).returncode != 0
    confirm_both(tmp_path, folder)
    assert growth(tmp_path, "tasks", "add", "New post", "write it", "--playbook", "new-post", cwd=folder).returncode == 0


def test_preflight_stops_before_anything_else_while_the_browser_is_not_ready(tmp_path):
    folder, _ = project(tmp_path)
    r = growth(tmp_path, "preflight", "/x", "--type", "post", "--key", "x", cwd=folder)
    assert r.returncode != 0 and "research browser is not ready" in (r.stdout + r.stderr)


def test_research_check_blocks_the_step_when_the_browser_is_gone(tmp_path):
    folder, _ = project(tmp_path)
    confirm_both(tmp_path, folder)
    assert growth(tmp_path, "wizard", "research-check", "--connected", "Browser 1", cwd=folder).returncode == 0
    tid = growth(tmp_path, "tasks", "add", "Post", "w", cwd=folder).stdout.strip()
    growth(tmp_path, "tasks", "step", tid, "ChatGPT research", cwd=folder)
    r = growth(tmp_path, "wizard", "research-check", "--connected", "", "--task", tid, "--step", "1", cwd=folder)
    assert r.returncode == 1 and "BLOCKED" in r.stdout and "/chrome" in r.stdout
    assert json.loads((folder / "docs" / "tasks.json").read_text())["tasks"][-1]["steps"][0]["status"] == "blocked"
    assert ws.get(folder, "browser")["status"] == "asked"          # confirmed again only by a person's word


def test_the_owner_can_confirm_both_in_one_command_each(tmp_path, monkeypatch):
    folder, cfg = project(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))       # the same temp home the owner's terminal used (its signing key)
    assert owner_approve(tmp_path, "browser", "--name", "Browser 1", cwd=folder)[0] == 0
    rc, out = owner_approve(tmp_path, "region", "--seen", "Current Region", cwd=folder)
    assert rc != 0 and "not United States" in out
    assert owner_approve(tmp_path, "region", "--seen", "United States", cwd=folder)[0] == 0
    assert gate.problems(folder, cfg) == []


def test_chat_mode_the_kit_checks_browser_and_region_itself_and_nothing_waits_for_the_owner(tmp_path):
    """Owner, 24 Nov 2026: "before its aksing me such permission calude code and the kit should check the chome wa already
    connected". In chat mode (the default) the agent's check is the confirmation: no terminal, no code."""
    folder, _ = project(tmp_path, mode="chat")
    assert growth(tmp_path, "wizard", "confirm", "browser", "--name", "Browser 1", cwd=folder).returncode == 0
    r = growth(tmp_path, "wizard", "confirm", "region", "--seen", "United States", cwd=folder)
    assert r.returncode == 0 and "checked" in r.stdout
    assert gate.problems(folder, json.loads((folder / "growth.json").read_text())) == []
    log = [json.loads(l) for l in (folder / "docs" / "approvals.jsonl").read_text().splitlines()]
    assert [e["kind"] for e in log] == ["browser", "region"] and all(e["via"].startswith("checked:") for e in log)


def test_chat_mode_a_wrong_region_is_still_refused(tmp_path):
    folder, _ = project(tmp_path, mode="chat")
    assert growth(tmp_path, "wizard", "confirm", "region", "--seen", "India", cwd=folder).returncode == 1
