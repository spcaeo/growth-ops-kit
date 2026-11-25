"""Owner, 24 Nov 2026: "is that possible that our kit is setup like a wizard and step by step process, that keeps user updated
and informed and also progress bar". The bar shows where Claude Code is opened (the workspace around the project), and the
wizard prints the numbered steps and a PROGRESS line."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import harness  # noqa: E402
import new_project  # noqa: E402
import wizard  # noqa: E402


def _make_inside(tmp_path):
    here = os.getcwd()
    os.chdir(tmp_path)
    try:
        folder, _ = new_project.make(tmp_path / "growth", "https://shop.example")
    finally:
        os.chdir(here)
    return folder


def test_project_made_inside_the_open_folder_records_it_and_gets_the_bar(tmp_path):
    folder = _make_inside(tmp_path)
    cfg = json.loads((folder / "growth.json").read_text())
    assert Path(cfg["workspace"]) == tmp_path.resolve()
    made = harness.install_workspace(folder, cfg)
    s = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    assert made and "statusline" in s["statusLine"]["command"] and str(folder.resolve()) in s["statusLine"]["command"]
    assert "hook stop" in json.dumps(s["hooks"]["Stop"]) and "hook stage" in json.dumps(s["hooks"]["PostToolUse"])
    assert harness.workspace_ok(folder, cfg) is True
    assert ("Workspace progress bar", "ok") in [(p, st) for p, st, _, _ in harness.check(folder, cfg)]
    assert harness.install_workspace(folder, cfg) == []          # a second run adds nothing


def test_owner_status_line_in_the_workspace_is_never_replaced(tmp_path):
    folder = _make_inside(tmp_path)
    (tmp_path / ".claude").mkdir(exist_ok=True)
    (tmp_path / ".claude" / "settings.json").write_text(json.dumps({"statusLine": {"type": "command", "command": "my-own-bar"}}))
    harness.install_workspace(folder)
    s = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    assert s["statusLine"]["command"] == "my-own-bar"


def test_no_workspace_when_the_project_is_made_elsewhere(tmp_path):
    folder, _ = new_project.make(tmp_path / "p", "https://shop.example")
    cfg = json.loads((folder / "growth.json").read_text())
    if Path.cwd().resolve() not in folder.parents:
        assert not cfg.get("workspace")
    assert harness.workspace_ok(folder, {**cfg, "workspace": ""}) is None


def test_every_wizard_step_has_a_plain_name_and_a_progress_line(tmp_path):
    folder = _make_inside(tmp_path)
    assert set(wizard.PLAIN) == set(wizard.ORDER)
    line = wizard.progress(folder, 1, "market")
    assert line.startswith("PROGRESS ") and "▱" in line and f"/{len(wizard.ORDER)}" in line and wizard.PLAIN["market"] in line


def _task(steps, status="doing", title="Project setup"):
    return {"tasks": [{"id": "T1", "title": title, "status": status, "steps": steps}]}


def test_bar_names_what_open_steps_wait_for_instead_of_a_fake_now():
    """Owner, 24 Nov 2026: the bar showed "now: A7" while A7 could not start before the site exists."""
    import statusline
    steps = [{"n": i, "what": f"A{i} x", "status": "done"} for i in range(1, 7)]
    steps += [{"n": 7, "what": "A7 Full site inventory", "status": "waiting", "waiting_for": "the site to build and serve"},
              {"n": 8, "what": "A7b Site link graph", "status": "waiting", "waiting_for": "the site to build and serve"}]
    out = statusline.line(_task(steps, status="waiting"))
    assert "now:" not in out and "waiting for the site to build and serve (7, 8)" in out and "6/8" in out and "Project setup" in out


def test_bar_clears_when_every_task_is_done():
    import statusline
    out = statusline.line(_task([{"n": 1, "what": "A1 x", "status": "done"}], status="done"))
    assert out.startswith("✓ all 1 task(s) done")


def test_setup_sync_marks_site_steps_waiting_and_the_task_waiting(tmp_path):
    import setup_task
    folder = _make_inside(tmp_path)
    cfg = json.loads((folder / "growth.json").read_text())
    cfg["site_repo"] = ""
    rows = [(f"{sid} {title}", "OK  " if sid not in ("A7", "A7b") else "FAIL", "r") for sid, title in setup_task.doctor_steps()]
    setup_task.sync(folder, rows, cfg)
    t = setup_task.find(json.loads((folder / "docs" / "tasks.json").read_text()))
    assert t["status"] == "waiting"
    assert {s["what"].split()[0] for s in t["steps"] if s["status"] == "waiting"} == {"A7", "A7b"}
    cfg["site_repo"] = str(tmp_path / "site")            # the site exists: the steps are real work again
    setup_task.sync(folder, rows, cfg)
    t = setup_task.find(json.loads((folder / "docs" / "tasks.json").read_text()))
    assert t["status"] == "doing" and all(s["status"] in ("done", "todo") for s in t["steps"])


def test_status_line_redraws_on_a_timer_and_transcripts_include_the_workspace(tmp_path, monkeypatch):
    folder = _make_inside(tmp_path)
    monkeypatch.setenv("GROWTH_PROJECT", str(folder))
    import owner_messages
    cfg = json.loads((folder / "growth.json").read_text())
    harness.install(folder, "Shop", "https://shop.example", cfg=cfg)
    harness.install_workspace(folder, cfg)
    for s in (folder / ".claude" / "settings.json", tmp_path / ".claude" / "settings.json"):
        assert json.loads(s.read_text())["statusLine"]["refreshInterval"] == harness.REFRESH_SECONDS
    home = tmp_path / "home"
    (home / ".claude" / "projects" / owner_messages.slug(tmp_path.resolve())).mkdir(parents=True)
    dirs = owner_messages.transcript_dirs(folder, home=home, cfg=cfg)
    assert home / ".claude" / "projects" / owner_messages.slug(tmp_path.resolve()) in dirs


def test_owner_message_check_hides_typed_passwords_and_skips_chat_before_the_project(tmp_path, monkeypatch):
    folder = _make_inside(tmp_path)
    monkeypatch.setenv("GROWTH_PROJECT", str(folder))
    import owner_messages
    shown = owner_messages.hide_secrets("connect with admin TEeVf!%(6SIwz0ge and https://wp.example.com/login/")
    assert "TEeVf" not in shown and "[hidden]" in shown and "https://wp.example.com/login/" in shown
    (folder / "setup-state.json").write_text(json.dumps({"started": "2026-11-24T19:33+05:30"}))
    assert owner_messages.project_start(folder, {}) == "2026-11-24T13:33"
    assert owner_messages.project_start(folder, {"owner_messages_since": "2026-11-20T08:00"}) == "2026-11-20T08:00"


def test_missing_owner_messages_are_logged_quietly_with_passwords_hidden(tmp_path, monkeypatch):
    """Owner, 24 Nov 2026: "update kit not to create so much updated and noise in chat"."""
    folder = _make_inside(tmp_path)
    monkeypatch.setenv("GROWTH_PROJECT", str(folder))
    import owner_messages
    monkeypatch.setattr(owner_messages, "LOG", folder / "docs" / "steps-log.md")   # an earlier test may have loaded another project
    n = owner_messages.log_missing([{"at": "2026-11-24 14:47", "text": "use login admin Xy9!kq#Lm2pQ please"}])
    rows = [l for l in (folder / "docs" / "steps-log.md").read_text().splitlines() if l.startswith("| I-")]
    assert n == 1 and rows[-1].startswith("| I-1 | 2026-11-24 |") and "Xy9" not in rows[-1] and "(to fill" in rows[-1]
    assert owner_messages.logged("use login admin Xy9!kq#Lm2pQ please", rows)


def test_our_claude_md_block_follows_the_kit_and_keeps_the_owners_text(tmp_path):
    md = tmp_path / "CLAUDE.md"
    md.write_text("My own note.\n\n" + harness.CLAUDE_START + "\nold kit lines\n" + harness.CLAUDE_END + "\n\nMore of mine.\n")
    harness.install(tmp_path, "Shop", "https://shop.example", permissions=False)
    t = md.read_text()
    assert "My own note." in t and "More of mine." in t and "old kit lines" not in t and "simply and quietly" in t


def test_stop_hook_never_shows_soft_rule_warnings_in_the_owners_chat():
    t = (Path(__file__).resolve().parent.parent / "kit" / "hooks" / "stop_hook.sh").read_text()
    assert "Rule checks still failing" not in t and "owner_messages log-missing" in t


def test_claude_md_says_explain_every_next_step():
    assert "never a bare label" in harness.CLAUDE_BLOCK and "yes or no" in harness.CLAUDE_BLOCK


def test_home_and_pricing_are_money_pages():
    """Book: a money page is "the main service pages, pricing and the home page" (24 Nov 2026: home was guessed core)."""
    import front_door
    cfg = {"core_pages": {"/": ["home"], "/contact": ["conversion"]}, "money_pages": ["/ehr-development/"]}
    assert front_door.guess_type("/", cfg) == "money"
    assert front_door.guess_type("/pricing", cfg) == "money"
    assert front_door.guess_type("/ehr-development/", cfg) == "money"
    assert front_door.guess_type("/contact", cfg) == "core"


def test_only_the_sitemap_may_be_read_under_no_crawl():
    """24 Nov 2026: the sitemap-only inventory (no page visited) works on a no-crawl project; a page read stays refused."""
    import fetch_rule
    cfg = {"live_site_rule": "no-crawl", "site_url": "https://www.shop.example"}
    assert fetch_rule.blocked("https://shop.example/a", cfg)
    fetch_rule.assert_may_fetch("https://shop.example/sitemap.xml", cfg, sitemap_only=True)     # no SystemExit


def test_sitemap_only_inventory_counts_listed_pages_as_live_not_fetched():
    import inventory
    rows = inventory.build({"/": "2026-11-01", "/a/": ""}, {}, listed_is_live=True)
    assert all(r["status"] == "live" and r["fetched"] is False for r in rows)


def test_a_short_answer_is_logged_once_and_mapped(tmp_path, monkeypatch):
    folder = _make_inside(tmp_path)
    monkeypatch.setenv("GROWTH_PROJECT", str(folder))
    import owner_messages
    monkeypatch.setattr(owner_messages, "LOG", folder / "docs" / "steps-log.md")
    monkeypatch.setattr(owner_messages, "MAP", folder / "docs" / "owner-messages-map.json")
    assert owner_messages.log_missing([{"at": "2026-11-24 15:18", "text": "yes"}]) == 1
    assert json.loads((folder / "docs" / "owner-messages-map.json").read_text()) == {"2026-11-24 15:18": "I-1"}
