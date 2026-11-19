"""The task workflow is a rule: the Stop hook blocks work with no open task and steps done with no proof; a chat task is
the way out; `tasks step` starts a step as todo; the stage hook prints the page's open manual checkpoints."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GROWTH = str(ROOT / "growth")


def run(project, *args, stdin=""):
    env = {**os.environ, "GROWTH_PROJECT": str(project), "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.com",
           "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@example.com"}
    return subprocess.run([sys.executable, GROWTH, *args], capture_output=True, text=True, env=env, input=stdin)


def proj(tmp_path):
    p = tmp_path / "proj"
    (p / "docs").mkdir(parents=True)
    (p / "growth.json").write_text(json.dumps({"name": "T", "site_url": "https://t.example"}))
    (p / "docs" / "tasks.json").write_text(json.dumps({"tasks": [], "questions": []}))
    subprocess.run(["git", "init", "-q"], cwd=p)
    subprocess.run(["git", "add", "-A"], cwd=p)
    subprocess.run(["git", "-c", "user.email=t@example.com", "-c", "user.name=T", "commit", "-qm", "init"], cwd=p)
    return p


def test_no_open_task_with_changed_files_blocks_and_chat_task_clears(tmp_path):
    p = proj(tmp_path)
    assert run(p, "workflow", "check").returncode == 0          # nothing changed: fine
    (p / "page.md").write_text("work\n")
    r = run(p, "workflow", "check")
    assert r.returncode == 2 and "no task is open" in r.stderr and "--type chat" in r.stderr
    assert run(p, "tasks", "add", "Chat: setup talk", "", "--type", "chat").stdout.strip() == "T1"
    assert run(p, "workflow", "check").returncode == 2           # a chat task needs no steps, but covers no file changes
    run(p, "tasks", "status", "T1", "done")
    assert run(p, "workflow", "check").returncode == 2
    # bookkeeping files alone are not work
    subprocess.run(["git", "checkout", "--", "."], cwd=p)
    (p / "page.md").unlink()
    assert run(p, "workflow", "check").returncode == 0


def test_page_task_needs_steps_and_a_done_step_needs_proof(tmp_path):
    p = proj(tmp_path)
    run(p, "tasks", "add", "Page job", "words")
    assert "no steps" in run(p, "workflow", "check").stderr
    run(p, "tasks", "step", "T1", "Research the page")
    db = json.loads((p / "docs" / "tasks.json").read_text())
    assert db["tasks"][0]["steps"][0]["status"] == "todo"        # the default is todo, not done
    assert run(p, "workflow", "check").returncode == 0
    r = run(p, "tasks", "step", "T1", "Edit it", "--status", "done")
    assert r.returncode != 0 and "--output" in (r.stderr + r.stdout)
    # audit H1: the proof must name something that exists; "commit abc1234" (no such commit) is refused now
    assert run(p, "tasks", "step", "T1", "Edit it", "--status", "done", "--output", "commit abc1234").returncode != 0
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=p, capture_output=True, text=True).stdout.strip()
    assert run(p, "tasks", "step", "T1", "Edit it", "--status", "done", "--output", f"commit {head}").returncode == 0
    db = json.loads((p / "docs" / "tasks.json").read_text())
    db["tasks"][0]["steps"][0].update(status="done", output="")  # a hand-edited lie
    (p / "docs" / "tasks.json").write_text(json.dumps(db))
    r = run(p, "workflow", "check")
    assert r.returncode == 2 and "done with no proof" in r.stderr and "tasks tick T1 1" in r.stderr


def test_stop_hook_blocks_even_on_the_second_stop(tmp_path):
    p = proj(tmp_path)
    (p / "page.md").write_text("work\n")
    for active in (False, True):
        r = run(p, "hook", "stop", stdin=json.dumps({"stop_hook_active": active}))
        assert r.returncode == 2 and "no task is open" in r.stderr


def test_stage_hook_prints_the_open_manual_checkpoints(tmp_path):
    p = proj(tmp_path)
    (p / "research").mkdir()
    (p / "research" / "pricing-checkpoints.md").write_text(
        "# Checkpoints\n\n## 5. Manual checks (2)\n\n- [ ] rule 530: click test\n- [x] rule 531: ok -- seen J0028\n")
    run(p, "tasks", "add", "Page pricing", "")
    tick = lambda cmd: run(p, "hook", "stage", stdin=json.dumps({"tool_input": {"command": cmd}}))
    run(p, "tasks", "step", "T1", "Research: Search Console and the live page")
    r = tick('growth tasks tick T1 1 --output "x"')
    out = json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "rule 530" in out and "rule 531" not in out and "pricing-checkpoints.md" in out
    assert tick("ls").stdout == "" and tick('growth tasks tick T1 9 --output "x"').stdout == ""   # not a stage step


def test_preflight_merges_site_rules_and_a_rerun_keeps_them(demo_project, monkeypatch):
    monkeypatch.setenv("GROWTH_PROJECT", str(demo_project))
    import preflight
    monkeypatch.setattr(preflight, "PROJECT", demo_project)
    rules = demo_project / "site-rules.md"
    rules.write_text("- site rule 7: logo on every tool\n- site rule 8: no stock photos\n")
    args = ("/x", "money", "x", preflight.checks_in_scope("money"))
    p, counts = preflight.write_plan(*args, extra_rules=[rules])
    assert "- [ ] site rule 7: logo on every tool" in p.read_text() and counts["manual"] >= 2
    p.write_text(p.read_text().replace("- [ ] site rule 7: logo on every tool", "- [x] site rule 7: logo on every tool -- checked J1"))
    preflight.write_plan(*args)          # a run without the file does not drop the rule or its proof
    assert "- [x] site rule 7: logo on every tool -- checked J1" in p.read_text()

