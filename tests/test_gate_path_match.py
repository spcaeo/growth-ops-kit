"""Gate evidence checks on a site whose addresses end in "/": the inventory row "/blog/post/", a task titled with the
page's full address, and the snapshot folder page_snapshot writes are all found for "/blog/post" and "/blog/post/";
seo.kept compares a page with its live row instead of calling it new. No network."""
import json
import tempfile
from pathlib import Path

import pytest

import paths
from gatelib import CHECKS
from gatelib.core import Ctx, run_check

SITE = "https://www.example.com"
PAGE = "/blog/best-mowing-height/"


def project(tmp):
    p = Path(tmp)
    (p / "inventory").mkdir()
    (p / "docs").mkdir()
    row = {"path": PAGE, "status": "live", "money_page": False, "title": "Best mowing height", "h1": "Best mowing height",
           "meta_description": "How high to mow."}
    (p / "inventory" / "inventory.json").write_text(json.dumps({"meta": {"generated": "2999-01-01 00:00 UTC"}, "pages": [row]}))
    steps = [{"n": i, "what": f"Step {i}.", "status": "todo", "at": "2026-11-18 10:00 UTC", "output": None} for i in range(1, 7)]
    task = {"id": "T1", "title": f"Update post: {SITE}{PAGE}", "status": "doing", "steps": steps}
    (p / "docs" / "tasks.json").write_text(json.dumps({"tasks": [task], "questions": []}))
    snap = p / "inventory" / "pages" / paths.snapshot_slug(PAGE)
    snap.mkdir(parents=True)
    (snap / "2026-11-18.md").write_text("# snapshot")
    return p


@pytest.mark.parametrize("given", [PAGE, PAGE.rstrip("/")])
@pytest.mark.parametrize("cid", ["ev.inventory", "ev.task-steps", "ev.snapshot"])
def test_evidence_checks_find_a_trailing_slash_page(cid, given):
    with tempfile.TemporaryDirectory() as tmp:
        p = project(tmp)
        ctx = Ctx(project=p, path=given, ptype="post", docs=p / "docs", cfg={"site_url": SITE})
        run_check(ctx, CHECKS[cid])
        assert ctx.lines[0].level == "OK", (cid, given, ctx.lines[0].what)


def test_snapshot_folder_is_the_one_page_snapshot_writes():
    assert paths.snapshot_slug("/blog/best-mowing-height/") == paths.snapshot_slug("/blog/best-mowing-height") == "blog__best-mowing-height"
    assert paths.snapshot_slug("/") == "home"


def test_a_task_for_another_page_is_not_this_pages_task():
    with tempfile.TemporaryDirectory() as tmp:
        p = project(tmp)
        ctx = Ctx(project=p, path="/blog/best-mowing", ptype="post", docs=p / "docs", cfg={"site_url": SITE})
        run_check(ctx, CHECKS["ev.task-steps"])
        assert ctx.lines[0].level == "FAIL"   # "/blog/best-mowing" is not "/blog/best-mowing-height/"


def test_seo_kept_compares_with_the_live_row():
    with tempfile.TemporaryDirectory() as tmp:
        p = project(tmp)
        ctx = Ctx(project=p, path=PAGE.rstrip("/"), ptype="post", docs=p / "docs", cfg={"site_url": SITE},
                  html="<html><head><title>Something else</title></head><body><main><h1>Best mowing height</h1></main></body></html>", status=200)
        run_check(ctx, CHECKS["seo.kept"])
        assert "nothing live to keep" not in ctx.lines[0].what


def test_a_fresh_task_with_no_step_done_is_not_called_stale():
    with tempfile.TemporaryDirectory() as tmp:
        p = project(tmp)          # six steps, all todo
        ctx = Ctx(project=p, path=PAGE, ptype="post", docs=p / "docs", cfg={"site_url": SITE})
        run_check(ctx, CHECKS["ev.task-steps"])
        assert "still todo while later steps are done" not in ctx.lines[0].what
