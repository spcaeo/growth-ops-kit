"""Proof must name something checkable (audit H1): tasks, checkpoints and the gate share one rule, a task is not done while
its steps are open, and the step keeps the files' hashes and the commit it was checked at."""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import checkpoints  # noqa: E402
from test_workflow import proj, run  # noqa: E402


def steps(p):
    return json.loads((p / "docs" / "tasks.json").read_text())["tasks"][0]["steps"]


def test_a_tick_with_a_meaningless_proof_is_refused(tmp_path):
    p = proj(tmp_path)
    run(p, "tasks", "add", "Page job: /x", "words")
    run(p, "tasks", "step", "T1", "Research the page")
    for weak in (" .", "x", "abc", "yes", "looks good to me", "commit 1234abc"):     # the last: no such commit
        r = run(p, "tasks", "tick", "T1", "1", "--output", weak)
        assert r.returncode != 0 and "refused" in r.stderr, weak
    assert steps(p)[0]["status"] == "todo"


def test_a_real_proof_is_stored_with_its_file_hash_and_the_commit(tmp_path):
    p = proj(tmp_path)
    (p / "research").mkdir()
    (p / "research" / "x-notes.md").write_text("what I saw\n")
    run(p, "tasks", "add", "Page job: /x", "words")
    run(p, "tasks", "step", "T1", "Research the page")
    r = run(p, "tasks", "tick", "T1", "1", "--output", "notes in research/x-notes.md")
    assert r.returncode == 0, r.stderr
    st = steps(p)[0]
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=p, capture_output=True, text=True).stdout.strip()
    assert st["status"] == "done" and st["proof_refs"]["files"][0]["path"] == "research/x-notes.md" and len(st["proof_refs"]["files"][0]["sha256"]) == 64
    assert st["last_checked_commit"] == head
    for good in ("growth gate page /x -> 0 FAIL", "https://example.com/x checked", f"commit {head[:8]}"):
        run(p, "tasks", "step", "T1", "Another")
        assert run(p, "tasks", "tick", "T1", str(len(steps(p))), "--output", good).returncode == 0, good


def test_a_task_is_not_done_while_a_step_is_open_unless_forced_with_a_logged_reason(tmp_path):
    p = proj(tmp_path)
    run(p, "tasks", "add", "Page job: /x", "words")
    run(p, "tasks", "step", "T1", "Research the page")
    r = run(p, "tasks", "status", "T1", "done")
    assert r.returncode != 0 and "not done" in r.stderr
    assert run(p, "tasks", "status", "T1", "done", "--force-reason", "short").returncode != 0
    assert run(p, "tasks", "status", "T1", "done", "--force-reason", "owner stopped this job on the call").returncode == 0
    t = json.loads((p / "docs" / "tasks.json").read_text())["tasks"][0]
    assert t["status"] == "done" and t["forced"][0]["reason"] == "owner stopped this job on the call" and t["forced"][0]["open_steps"] == [1]
    assert run(p, "tasks", "add", "Project setup", "", "--type", "setup").returncode == 0


def test_the_gate_rechecks_proofs_typed_into_the_task_list(tmp_path):
    from gatelib.core import CHECKS, Ctx, run_check
    (tmp_path / "docs").mkdir()
    (tmp_path / "research").mkdir()
    (tmp_path / "research" / "a.md").write_text("x\n")
    st = [{"n": i, "what": f"Step {i}.", "status": "done", "at": "2026-11-19 10:00", "output": "see research/a.md"} for i in range(1, 7)]
    st[2]["output"] = "x"
    st[3]["output"] = "see research/gone.md"
    (tmp_path / "docs" / "tasks.json").write_text(json.dumps({"tasks": [{"id": "T1", "title": "Job: /a", "status": "doing", "steps": st}]}))
    ctx = Ctx(project=tmp_path, path="/a", ptype="post", docs=tmp_path / "docs", cfg={})
    run_check(ctx, CHECKS["ev.task-steps"])
    ln = ctx.lines[0]
    assert ln.level == "FAIL" and "step 3 proof is not checkable" in ln.what and "step 4 proof is not checkable" in ln.what


def test_checkpoint_proofs_follow_the_same_rule():
    text = "## 5. Manual checks (3)\n\n- [x] rule 530: click test -- abc\n- [x] rule 531: x -- J0028, 53/53\n- [x] rule 532: y -- yes\n"
    total, done, probs = checkpoints.manual_status(text)
    assert (total, done) == (3, 1) and len(probs) == 2
    assert checkpoints.missing_extra("## 5. Manual checks (0)\n", ["rule 530: click test"]) == ["missing from the checkpoints file: rule 530: click test"]


def test_with_a_project_a_checkpoint_proof_must_exist(tmp_path):
    (tmp_path / "journal").mkdir()
    (tmp_path / "journal" / "entries.jsonl").write_text(json.dumps({"id": "J0028"}) + "\n")
    text = "## 5. Manual checks (2)\n\n- [x] rule 1: a -- J0028\n- [x] rule 2: b -- J0099\n"
    assert checkpoints.manual_status(text, tmp_path)[:2] == (2, 1)


def test_a_file_named_with_a_commit_is_hashed_as_in_that_commit(tmp_path):
    # issue #66: work done on a branch in a worktree was hashed from the main checkout's OLD file
    import hashlib
    import subprocess
    import checkpoints
    repo = tmp_path / "site"
    repo.mkdir()
    g = lambda *a: subprocess.run(["git", "-C", str(repo), *a], capture_output=True, check=True, text=True).stdout.strip()  # noqa: E731
    g("init", "-q")
    g("config", "user.email", "t@example.com")
    g("config", "user.name", "t")
    (repo / "kit.css").write_text("old\n")
    g("add", "-A")
    g("commit", "-qm", "old")
    g("checkout", "-qb", "fix/tabs")
    (repo / "kit.css").write_text("new\n")
    g("commit", "-qam", "new")
    new_sha = g("rev-parse", "HEAD")[:8]
    g("checkout", "-q", "-")                                       # the main checkout is back on the OLD file
    refs = checkpoints.proof_refs(f"commit {new_sha} on fix/tabs: kit.css tabs wrap", repos=[repo])
    assert refs["commit"] == [new_sha]
    assert refs["file"] == [("kit.css", hashlib.sha256(b"new\n").hexdigest())]
    plain = checkpoints.proof_refs("kit.css tabs wrap", repos=[repo])  # no commit named: the checkout's file, as before
    assert plain["file"] == [("kit.css", hashlib.sha256(b"old\n").hexdigest())]


def test_rule_ids_are_proof_of_a_reread_and_problems_name_their_stage():
    # issue #25: a re-read-checkpoints step is proved by the rule ids checked; unticked items say which stage they belong to
    import checkpoints
    assert checkpoints.proof_problem("rules 18, 32a and 36b re-read before the build") is None
    assert checkpoints.proof_problem("rule 18 re-read") is not None          # one id is not a re-read of the checkpoints
    text = "# Checkpoints\n\n## Manual checks: edit (2)\n- [ ] the hero answers first\n- [x] fold plan -- rules 18, 32a, 36b\n"
    total, done, probs = checkpoints.manual_status(text)
    assert total == 2 and done == 1 and probs[0].startswith("unticked") and probs[0].endswith("[stage: Manual checks: edit]")
