"""The setup wizard end to end, non-interactive (--answers), on a fixture site with a sitemap index, trailing slashes, redirects
and a language copy (#36 #34 #35 #37 #41)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import wizard_state as ws  # noqa: E402
from wizard_helpers import growth, make_site, owner_approve  # noqa: E402


def answers(tmp, repo, **over):
    a = {"market": {"country": "US", "language": "en"}, "site_repo": {"path": str(repo)}, "analytics": "later",
         "live_rule": {"rule": "no-crawl", "preview_url": "http://localhost:4321"}, "approver": "Pat, owner",
         "harness": {"permissions": True, "git_hooks": True}, "detect": {"confirm": True}}
    a.update(over)
    f = tmp / "answers.json"
    f.write_text(json.dumps(a))
    return f


def start(tmp):
    repo, index = make_site(tmp)
    r = growth(tmp, "wizard", str(tmp / "proj"), "--site", "https://shop.example", "--answers", str(answers(tmp, repo)), "--sitemap", str(index))
    return tmp / "proj", r, repo


def test_wizard_does_every_step_then_waits_on_the_guided_ones(tmp_path):
    proj, r, _ = start(tmp_path)
    assert r.returncode == 3, r.stdout + r.stderr
    assert "WAITING browser" in r.stdout and "/chrome" in r.stdout
    st = ws.load(proj)["steps"]
    for step in ("market", "site_repo", "analytics", "live_rule", "approver", "harness", "detect"):
        assert st[step]["status"] in ("done", "declined"), step
        assert st[step]["date"] and st[step]["source"]
    assert st["analytics"]["status"] == "declined" and st["detect"]["source"] == "detected" and st["market"]["test"]["result"] == "gl=us&hl=en&pws=0"
    assert st["browser"]["status"] == "asked"
    cfg = json.loads((proj / "growth.json").read_text())
    assert cfg["market"]["google_params"] == "gl=us&hl=en&pws=0" and cfg["live_site_rule"] == "no-crawl" and cfg["release_approver"] == "Pat, owner"
    assert cfg["stack"] == "static" and cfg["detected"]["framework"]["value"] == "astro" and cfg["detected"]["framework"]["source"] == "detected"
    assert cfg["detected"]["sitemap_trailing_slash"]["value"] == "slash" and cfg["detected"]["sitemap_languages"]["value"] == ["en-us"]
    assert cfg["redirect_files"] == ["public/_redirects"] and cfg["build_cmd"] == "npm run build"
    setup = (proj / "SETUP.md").read_text()
    assert "Target market:** United States" in setup and "Research browser:** NOT connected" in setup
    assert (proj / ".claude" / "settings.json").is_file() and "PostToolUse" in (proj / ".claude" / "settings.json").read_text()


def test_setup_is_not_done_until_browser_and_region_are_confirmed(tmp_path):
    proj, _, _ = start(tmp_path)
    assert growth(tmp_path, "wizard", cwd=proj).returncode == 3                      # still waiting: resumes at browser
    growth(tmp_path, "wizard", "confirm", "browser", "--name", "Browser 1", cwd=proj)
    assert growth(tmp_path, "wizard", cwd=proj).returncode == 3                      # recorded, not yet approved by the owner
    assert owner_approve(tmp_path, "browser", cwd=proj)[0] == 0
    r = growth(tmp_path, "wizard", cwd=proj)
    assert r.returncode == 3 and "WAITING region" in r.stdout
    bad = growth(tmp_path, "wizard", "confirm", "region", "--seen", "Current Region", cwd=proj)
    assert bad.returncode == 1 and growth(tmp_path, "wizard", cwd=proj).returncode == 3
    growth(tmp_path, "wizard", "confirm", "region", "--seen", "United States", cwd=proj)
    assert growth(tmp_path, "wizard", cwd=proj).returncode == 3                      # audit C4: needs the owner, not a flag
    assert owner_approve(tmp_path, "region", cwd=proj)[0] == 0
    r = growth(tmp_path, "wizard", cwd=proj)
    assert r.returncode == 0 and "SETUP NOT DONE" not in r.stdout
    out = growth(tmp_path, "doctor", cwd=proj).stdout
    for step in ("A10", "A13", "A14"):
        assert next(l for l in out.splitlines() if step + " " in l).startswith("OK"), step
    setup = (proj / "SETUP.md").read_text()
    assert "Research browser:** Browser 1" in setup and "Google region:** United States" in setup
    t = json.loads((proj / "docs" / "tasks.json").read_text())["tasks"][0]
    assert {s["what"].split(" ")[0]: s["status"] for s in t["steps"]}["A14"] == "done"


def test_a_rerun_resumes_and_never_overwrites_what_the_owner_set(tmp_path):
    proj, _, repo = start(tmp_path)
    cfg = json.loads((proj / "growth.json").read_text())
    cfg["release_approver"] = "Someone else"
    (proj / "growth.json").write_text(json.dumps(cfg))
    settings = json.loads((proj / ".claude" / "settings.json").read_text())
    settings["permissions"]["allow"].append("Bash(my-own-tool)")
    (proj / ".claude" / "settings.json").write_text(json.dumps(settings))
    r = growth(tmp_path, "wizard", "--answers", str(answers(tmp_path, repo, approver="Changed")), cwd=proj)
    assert "[    done] market: United" not in r.stdout and "[    done] approver: releases" not in r.stdout            # done steps are skipped
    assert json.loads((proj / "growth.json").read_text())["release_approver"] == "Someone else"
    assert "Bash(my-own-tool)" in json.loads((proj / ".claude" / "settings.json").read_text())["permissions"]["allow"]


def test_without_answers_the_question_is_printed_and_the_run_stops(tmp_path):
    r = growth(tmp_path, "wizard", str(tmp_path / "proj"), "--site", "https://shop.example")
    assert r.returncode == 3 and "QUESTION market:" in r.stdout and "country and language" in r.stdout
    assert ws.get(tmp_path / "proj", "market")["status"] == "asked"
    assert growth(tmp_path, "wizard", "answer", "market", '{"country": "CA", "language": "en"}', cwd=tmp_path / "proj").returncode == 0
    r = growth(tmp_path, "wizard", cwd=tmp_path / "proj")
    assert "QUESTION market" not in r.stdout and "QUESTION site_repo" in r.stdout
    assert json.loads((tmp_path / "proj" / "growth.json").read_text())["market"]["google_params"] == "gl=ca&hl=en&pws=0"


def test_market_is_the_first_question(tmp_path):
    from wizard import ORDER
    assert ORDER[0] == "market"


def test_check_reports_drift(tmp_path):
    proj, _, repo = start(tmp_path)
    r = growth(tmp_path, "wizard", "--check", cwd=proj)
    assert "OK       harness" in r.stdout and "OK       detect" in r.stdout and "OK       site_repo" in r.stdout
    (proj / ".claude" / "settings.json").unlink()
    (repo / "astro.config.mjs").unlink()
    r = growth(tmp_path, "wizard", "--check", cwd=proj)
    assert r.returncode == 1 and "CHANGED  harness" in r.stdout and "CHANGED  detect" in r.stdout
    assert ws.get(proj, "harness")["last_check"]["result"].startswith("CHANGED")


def test_status_lists_every_step_with_its_source(tmp_path):
    proj, _, _ = start(tmp_path)
    out = growth(tmp_path, "wizard", "status", cwd=proj).stdout
    assert "done      market" in out and "answers-file" in out and "asked     browser" in out


def test_state_keeps_the_answer_when_a_later_test_is_recorded(tmp_path):
    ws.record(tmp_path, "x", "answered", answer={"a": 1}, source="owner")
    ws.record(tmp_path, "x", "tested", test={"command": "c", "result": "r"})
    e = ws.get(tmp_path, "x")
    assert e["answer"] == {"a": 1} and e["source"] == "owner" and e["test"]["result"] == "r" and e["date"]
    assert ws.first_open(tmp_path, ["x", "y"]) == "x"
    ws.record(tmp_path, "x", "declined")
    assert ws.first_open(tmp_path, ["x", "y"]) == "y"
