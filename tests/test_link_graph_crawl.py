"""link_graph on a static server: it asks for each page the way the sitemap spells it (a trailing slash gets no 301), and
the anchor-word report joins a page with its language copies and leaves pager links out. 127.0.0.1 only."""
import functools
import http.server
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "kit" / "tools"))

HOST = "https://shop.example"


def page(title, links="", head=""):
    return (f"<html><head><title>{title}</title>{head}</head><body><main><h1>{title}</h1>{links}</main></body></html>")


def alt(path, lang):
    return f'<link rel="alternate" hreflang="{lang}" href="{HOST}{path}">'


@pytest.fixture
def site(tmp_path):
    root = tmp_path / "dist"
    pages = {
        "": page("Home", '<a href="/tools/a/">the tool</a> <a href="/en-us/tools/a/">the tool</a> <a href="/tools/b/">the tool</a> '
                         '<a href="/blog/page/2/" rel="next">2</a> <a href="/blog/page/3/">3</a>'),
        "tools/a": page("A", head=alt("/tools/a/", "en") + alt("/en-us/tools/a/", "en-us")),
        "en-us/tools/a": page("A US", head=alt("/tools/a/", "en") + alt("/en-us/tools/a/", "en-us")),
        "tools/b": page("B"),
        "blog": page("Blog"),
    }
    for path, html in pages.items():
        d = root / path
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(html)
    locs = "".join(f"<url><loc>{HOST}/{p}{'/' if p else ''}</loc></url>" for p in pages)
    (root / "sitemap.xml").write_text(f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{locs}</urlset>')
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    handler.log_message = lambda *a, **k: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)   # a plain static server: /x answers 301 to /x/
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", root / "sitemap.xml"
    srv.shutdown()


def run(project, *args):
    env = {**os.environ, "GROWTH_PROJECT": str(project), "PYTHONDONTWRITEBYTECODE": "1"}
    r = subprocess.run([sys.executable, str(ROOT / "growth"), "link_graph", *args], capture_output=True, text=True, env=env,
                       cwd=project, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout


def crawl(demo_project, site):
    base, sitemap = site
    cfg = json.loads((demo_project / "growth.json").read_text())
    cfg.update(site_url=HOST, sitemap_url=str(sitemap))
    (demo_project / "growth.json").write_text(json.dumps(cfg))
    return run(demo_project, "crawl", "--base", base, "--delay", "0", "--concurrency", "2")


def test_a_trailing_slash_site_is_crawled_without_301s(demo_project, site):
    out = crawl(demo_project, site)
    assert "non-200 pages 0" in out, out
    assert "pages 5," in out


def test_language_copies_and_pagers_are_not_anchor_collisions(demo_project, site):
    crawl(demo_project, site)
    run(demo_project, "report", "--out", str(demo_project / "r.md"))
    report = (demo_project / "r.md").read_text()
    # "the tool" goes to /tools/a/ (and its /en-us/ copy: one page) and to /tools/b/: one real collision
    assert "`the tool`" in report and "`/tools/a`" in report and "`/tools/b`" in report
    assert "`/en-us/tools/a`" not in report.split("Same anchor words")[1]
    # the pager words "2" and "3" collide nowhere
    assert "`2`" not in report and "`3`" not in report
    assert "pager links" in report
