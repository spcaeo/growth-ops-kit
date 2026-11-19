"""A done step needs its proof in every project; only a project's own growth.json date may grandfather older steps (audit M4)."""
import json
from pathlib import Path

from gatelib.core import CHECKS, Ctx, run_check


def run(tmp_path, at, **cfg):
    (tmp_path / "docs").mkdir()
    steps = [{"n": i, "what": f"Step {i}.", "status": "done", "at": at, "output": "proof" if i > 1 else None} for i in range(1, 7)]
    task = {"id": "T1", "title": "Update post: /blog/a", "status": "doing", "steps": steps}
    (tmp_path / "docs" / "tasks.json").write_text(json.dumps({"tasks": [task]}))
    ctx = Ctx(project=Path(tmp_path), path="/blog/a", ptype="post", docs=tmp_path / "docs", cfg=cfg)
    run_check(ctx, CHECKS["ev.task-steps"])
    return ctx.lines[0]


def test_an_old_done_step_with_no_proof_fails_when_the_project_sets_no_date(tmp_path):
    line = run(tmp_path, "2026-01-05 09:00 EST")
    assert line.level == "FAIL" and "step 1 done with no proof" in line.what


def test_the_project_may_grandfather_steps_before_its_own_date(tmp_path):
    assert run(tmp_path, "2026-01-05 09:00 EST", proof_required_since="2026-03-01").level == "OK"


def test_steps_on_or_after_the_project_date_still_need_proof(tmp_path):
    assert run(tmp_path, "2026-03-01 09:00 EST", proof_required_since="2026-03-01").level == "FAIL"
