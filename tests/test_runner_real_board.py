"""The runner against the real board (kit/tools/board.py), with page-less machine jobs: both are done with a proof."""
import json
import sys

import pytest

import runner  # noqa: E402  (kit/tools is on sys.path from conftest)

board = pytest.importorskip("board")


def test_the_runner_finishes_the_boards_page_less_machine_jobs(tmp_path, monkeypatch):
    sys.modules.pop("board", None)       # the stand-in some other test may have left there
    import board as real
    project = tmp_path / "p"
    project.mkdir()
    (project / "growth.json").write_text(json.dumps({"name": "T", "site_url": "https://t.example", "runner_max_load": 1000,
                                                     "runner_min_free_pct": 0, "machine_jobs": {"inventory": "echo inv", "link-graph": "echo lg"}}))
    monkeypatch.setenv("GROWTH_PROJECT", str(project))
    a, b = real.add_job("inventory", project=project), real.add_job("link-graph", project=project)
    assert runner.Runner(project, jobs=2, once=True, poll=0.2, out=lambda t: None).run() == 0
    rows = {j["id"]: j for j in real.jobs_view(project=project)}
    assert rows[a]["status"] == "done" and rows[b]["status"] == "done"
    assert rows[a]["proof"].startswith("exit 0, log journal/runs/inventory-")
