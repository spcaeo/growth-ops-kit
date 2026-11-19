"""The research and measure path on a site that is not laid out like the Next.js default (an Astro-style repo:
posts in src/content/blog/<slug>.md served at /<cluster>/<slug>/, pages as JSON with a "uri"), and with addresses
that end in "/": the tracker maps pages to files through page_tracker.content_globs (C1), doctor fails A8 when a site
repo has no tracked change, task steps are ordered by their label (C2), journal entries are found for either path form
(C3), and the title check reads the tracker's slash-less queries (C4). No network."""
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TRACKER = ROOT / "kit" / "page-tracker"


def astro_repo(tmp):
    repo = Path(tmp) / "site"
    (repo / "src/content/blog").mkdir(parents=True)
    (repo / "src/content/pages").mkdir(parents=True)
    (repo / "src/content/blog/best-mowing-height.md").write_text("---\ntitle: Best mowing height\nslug: best-mowing-height\ncluster: lawn-care\n---\nBody\n")
    (repo / "src/content/blog/draft-post.md").write_text("---\ntitle: Draft\nslug: draft-post\ncluster: lawn-care\ndraft: true\n---\n")
    (repo / "src/content/blog/old-id.md").write_text("---\ntitle: Old id\nslug: old-id\ncluster: mowing\n---\n")
    (repo / "src/content/pages/about.json").write_text(json.dumps({"title": "About", "uri": "/about-us/"}))
    return repo


def mapped(project, cfg_globs):
    cfg = json.loads((project / "growth.json").read_text())
    cfg["site_repo"] = str(astro_repo(project.parent))
    cfg["page_tracker"] = {"content_globs": cfg_globs}
    (project / "growth.json").write_text(json.dumps(cfg))
    code = "import json, repo_meta; print(json.dumps(repo_meta.files()))"
    r = subprocess.run([sys.executable, "-c", code], cwd=TRACKER, capture_output=True, text=True,
                       env={**os.environ, "GROWTH_PROJECT": str(project), "PYTHONDONTWRITEBYTECODE": "1"}, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_content_globs_map_an_astro_repo_to_its_addresses(demo_project):
    files = mapped(demo_project, [
        {"glob": "src/content/blog/*.md", "address": "/{cluster}/{slug}/", "values": {"cluster": {"mowing": "lawn-mowing"}}},
        {"glob": "src/content/pages/*.json", "address": "{uri}"}])
    assert files["/lawn-care/best-mowing-height"] == "src/content/blog/best-mowing-height.md"
    assert files["/lawn-mowing/old-id"] == "src/content/blog/old-id.md"            # cluster id mapped to its folder
    assert files["/about-us"] == "src/content/pages/about.json"
    assert "/lawn-care/draft-post" not in files                                     # drafts are not pages


def test_without_globs_the_astro_repo_maps_nothing(demo_project):
    assert mapped(demo_project, []) == {}


def test_doctor_fails_a8_when_a_site_repo_has_no_tracked_change(demo_project):
    cfg = json.loads((demo_project / "growth.json").read_text())
    cfg["site_repo"] = str(astro_repo(demo_project.parent))
    cfg["search_console_history_start"] = ""
    (demo_project / "growth.json").write_text(json.dumps(cfg))
    (demo_project / "page-tracker").mkdir(exist_ok=True)
    c = sqlite3.connect(demo_project / "page-tracker" / "tracker.db")
    c.executescript("create table search(path, day, clicks, impressions, ctr, position, final);"
                    "create table pages(path, file, slug, kind, title); create table changes(path, at);"
                    "insert into search values('*', date('now'), 1, 1, 1, 1, 1); insert into pages values('/x', NULL, 'x', 'post', 'X');")
    c.commit(); c.close()
    r = subprocess.run([sys.executable, str(ROOT / "kit/tools/doctor.py")], capture_output=True, text=True, cwd=demo_project,
                       env={**os.environ, "GROWTH_PROJECT": str(demo_project), "GROWTH_LAUNCHD_DIRS": str(demo_project / "none"), "GROWTH_CRONTAB": ""})
    line = next(l for l in r.stdout.splitlines() if "A8 Page tracker" in l)
    assert line.startswith("FAIL") and "changes tracked: 0" in line and "content_globs" in r.stdout


def test_task_steps_are_ordered_by_their_label_not_their_place():
    from gatelib import CHECKS
    from gatelib.core import Ctx, run_check
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp)
        (p / "docs").mkdir()
        st = lambda n, w, s: {"n": n, "what": w, "status": s, "at": "2026-11-18 10:00", "output": "commit abc1234 proof"}  # noqa: E731
        steps = [st(1, "Step 1. a", "done"), st(2, "Step 2. b", "done"), st(3, "Step 3. c", "todo"), st(4, "Step 4. d", "todo"),
                 st(5, "Step 5. e", "todo"), st(6, "Step 2a. added later", "done")]   # appended at the end, done
        (p / "docs/tasks.json").write_text(json.dumps({"tasks": [{"id": "T1", "title": "Job: /blog/post/", "steps": steps}]}))
        ctx = Ctx(project=p, path="/blog/post", ptype="post", docs=p / "docs", cfg={"site_url": "https://www.example.com"})
        run_check(ctx, CHECKS["ev.task-steps"])
        assert ctx.lines[0].level == "OK", ctx.lines[0].what


def test_journal_entries_are_found_for_either_path_form():
    from gatelib.core import Ctx
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp)
        (p / "journal").mkdir()
        (p / "journal/entries.jsonl").write_text(json.dumps({"id": "J0001", "pages": ["/blog/post/"], "kind": "decision", "tags": []}) + "\n")
        for given in ("/blog/post", "/blog/post/"):
            assert [e["id"] for e in Ctx(project=p, path=given).page_entries()] == ["J0001"]


def test_the_title_check_reads_the_trackers_slashless_queries():
    from gatelib.c_page import gsc_top
    from gatelib.core import Ctx
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp)
        (p / "page-tracker").mkdir()
        c = sqlite3.connect(p / "page-tracker/tracker.db")
        c.executescript("create table search_queries(path, snapshot, query, clicks, impressions, position);"
                        "insert into search_queries values('/blog/post', '2026-11-18', 'best mowing height', 3, 900, 4.1);")
        c.commit(); c.close()
        assert gsc_top(Ctx(project=p, path="/blog/post/"), 2) == [("best mowing height", 900)]
