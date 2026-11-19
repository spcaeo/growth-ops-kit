"""The research browser is a hard gate: no research job starts until the browser is connected and Google's region is the
target country, both confirmed (#37)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import new_project  # noqa: E402
import research_gate as gate  # noqa: E402
import wizard_state as ws  # noqa: E402
from wizard_helpers import growth  # noqa: E402


def project(tmp_path, country="US"):
    folder, _ = new_project.make(tmp_path / "p", "https://shop.example")
    cfg = json.loads((folder / "growth.json").read_text())
    cfg["market"].update({"primary_country": country, "google_params": gate.google_params(country, "en")})
    (folder / "growth.json").write_text(json.dumps(cfg))
    return folder, cfg


def test_region_matching_never_trusts_current_region():
    m = {"primary_country": "US"}
    assert gate.region_matches("United States", m) and gate.region_matches("us", m)
    assert not gate.region_matches("Current Region", m) and not gate.region_matches("Canada", m) and not gate.region_matches("", m)


def test_gate_lists_what_is_missing_then_passes(tmp_path):
    folder, cfg = project(tmp_path)
    probs = "; ".join(gate.problems(folder, cfg))
    assert "/chrome" in probs and "By default: on" in probs and "not verified" in probs
    ws.record(folder, "browser", "done", answer={"name": "Browser 1"})
    ws.record(folder, "region", "done", answer={"seen": "United States", "owner_confirmed": True})
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
    assert r.returncode == 1 and "--owner-confirmed" in r.stdout and ws.get(folder, "region")["status"] == "tested"
    assert growth(tmp_path, "wizard", "confirm", "region", "--seen", "United States", "--owner-confirmed", cwd=folder).returncode == 0
    assert ws.get(folder, "region")["status"] == "done"


def test_doctor_a14_is_fail_until_confirmed_then_ok(tmp_path):
    folder, _ = project(tmp_path)
    assert growth(tmp_path, "doctor", cwd=folder).stdout.count("FAIL  A14") == 1
    growth(tmp_path, "wizard", "confirm", "browser", "--name", "Browser 1", cwd=folder)
    growth(tmp_path, "wizard", "confirm", "region", "--seen", "United States", "--owner-confirmed", cwd=folder)
    out = growth(tmp_path, "doctor", cwd=folder).stdout
    assert "OK    A14" in out and "OK    A13" in out


def test_tasks_add_with_a_research_playbook_is_refused_until_ready(tmp_path):
    folder, _ = project(tmp_path)
    r = growth(tmp_path, "tasks", "add", "New post", "write it", "--playbook", "new-post", cwd=folder)
    assert r.returncode != 0 and "research step" in (r.stdout + r.stderr) and "/chrome" in (r.stdout + r.stderr)
    assert growth(tmp_path, "tasks", "add", "Release", "", "--playbook", "release", cwd=folder).returncode == 0   # no research step (fix-a-fact re-reads the vendor page now, so it is research)
    assert growth(tmp_path, "tasks", "add", "x", "", "--research", cwd=folder).returncode != 0
    growth(tmp_path, "wizard", "confirm", "browser", "--name", "Browser 1", cwd=folder)
    growth(tmp_path, "wizard", "confirm", "region", "--seen", "United States", "--owner-confirmed", cwd=folder)
    assert growth(tmp_path, "tasks", "add", "New post", "write it", "--playbook", "new-post", cwd=folder).returncode == 0


def test_preflight_stops_before_anything_else_while_the_browser_is_not_ready(tmp_path):
    folder, _ = project(tmp_path)
    r = growth(tmp_path, "preflight", "/x", "--type", "post", "--key", "x", cwd=folder)
    assert r.returncode != 0 and "research browser is not ready" in (r.stdout + r.stderr)


def test_research_check_blocks_the_step_when_the_browser_is_gone(tmp_path):
    folder, _ = project(tmp_path)
    growth(tmp_path, "wizard", "confirm", "browser", "--name", "Browser 1", cwd=folder)
    growth(tmp_path, "wizard", "confirm", "region", "--seen", "United States", "--owner-confirmed", cwd=folder)
    assert growth(tmp_path, "wizard", "research-check", "--connected", "Browser 1", cwd=folder).returncode == 0
    tid = growth(tmp_path, "tasks", "add", "Post", "w", cwd=folder).stdout.strip()
    growth(tmp_path, "tasks", "step", tid, "ChatGPT research", cwd=folder)
    r = growth(tmp_path, "wizard", "research-check", "--connected", "", "--task", tid, "--step", "1", cwd=folder)
    assert r.returncode == 1 and "BLOCKED" in r.stdout and "/chrome" in r.stdout
    assert json.loads((folder / "docs" / "tasks.json").read_text())["tasks"][-1]["steps"][0]["status"] == "blocked"
    assert ws.get(folder, "browser")["status"] == "asked"          # confirmed again only by a person's word
