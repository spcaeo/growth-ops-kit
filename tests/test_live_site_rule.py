"""Audit H8: with live_site_rule "no-crawl", inventory and link_graph never ask the live host, with or without --base,
and the sitemap for a crawl comes from the preview. A local or preview address still works."""
import functools
import http.server
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

import fetch_rule

ROOT = Path(__file__).resolve().parent.parent
LIVE = "https://shop.example"


def project(demo_project, rule="no-crawl", **extra):
    cfg = json.loads((demo_project / "growth.json").read_text())
    cfg.update(site_url=LIVE, sitemap_url=LIVE + "/sitemap.xml", live_site_rule=rule, **extra)
    (demo_project / "growth.json").write_text(json.dumps(cfg))
    return demo_project


def run(proj, tool, *args):
    env = {**os.environ, "GROWTH_PROJECT": str(proj), "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run([sys.executable, str(ROOT / "growth"), tool, *args], capture_output=True, text=True, env=env,
                          cwd=proj, timeout=120)


@pytest.fixture
def preview(tmp_path):
    root = tmp_path / "dist"
    (root / "a").mkdir(parents=True)
    (root / "index.html").write_text("<html><title>Home</title><body><main><h1>Home</h1><a href='/a/'>a</a></main></body></html>")
    (root / "a" / "index.html").write_text("<html><title>A</title><body><main><h1>A</h1></main></body></html>")
    (root / "sitemap.xml").write_text(f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>{LIVE}/</loc></url>'
                                      f'<url><loc>{LIVE}/a/</loc></url></urlset>')
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    handler.log_message = lambda *a, **k: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def test_the_rule_helper():
    cfg = {"site_url": LIVE, "live_site_rule": "no-crawl", "preview_url": "http://127.0.0.1:3000"}
    assert fetch_rule.blocked(LIVE + "/x", cfg) and fetch_rule.blocked("https://www.shop.example/", cfg)
    assert not fetch_rule.blocked("http://127.0.0.1:3000/x", cfg)
    assert not fetch_rule.blocked(LIVE + "/x", {**cfg, "live_site_rule": "crawl-ok"})
    with pytest.raises(SystemExit) as e:
        fetch_rule.assert_may_fetch(LIVE + "/x", cfg)
    assert "REFUSED" in str(e.value) and "--base" in str(e.value)


def test_inventory_refuses_the_live_host(demo_project):
    proj = project(demo_project)
    for args in ((), ("--base", LIVE)):
        r = run(proj, "inventory", *args)
        assert r.returncode != 0 and "REFUSED" in (r.stdout + r.stderr), args


def test_link_graph_crawl_and_update_refuse_the_live_host(demo_project):
    proj = project(demo_project)
    for args in (("crawl",), ("crawl", "--base", LIVE), ("update", "/a", "--base", LIVE)):
        r = run(proj, "link_graph", *args)
        assert r.returncode != 0 and "REFUSED" in (r.stdout + r.stderr), args


def test_a_preview_is_fine_and_the_sitemap_is_read_from_it(demo_project, preview):
    proj = project(demo_project)
    r = run(proj, "link_graph", "crawl", "--base", preview, "--delay", "0", "--concurrency", "2")
    assert r.returncode == 0 and "pages 2," in r.stdout + r.stderr, r.stdout + r.stderr
    r = run(proj, "inventory", "--base", preview, "--no-pages")
    assert r.returncode == 0, r.stdout + r.stderr


def test_crawl_ok_projects_are_unchanged(demo_project):
    proj = project(demo_project, rule="crawl-ok")
    r = run(proj, "inventory", "--offline", str(demo_project / "none.xml"), "--no-pages")
    assert "REFUSED" not in r.stdout + r.stderr


def test_a_preview_crawl_reads_the_previews_own_sitemap_on_a_crawl_ok_site_too(demo_project, preview):
    """2.7.6: --base always reads the preview's sitemap, so a branch's new page (not yet in the live sitemap) is mapped."""
    proj = project(demo_project, rule="crawl-ok")
    r = run(proj, "link_graph", "crawl", "--base", preview, "--delay", "0", "--concurrency", "2")
    assert r.returncode == 0 and "pages 2," in r.stdout + r.stderr, r.stdout + r.stderr
