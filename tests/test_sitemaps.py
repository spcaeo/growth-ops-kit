"""One sitemap reader for every tool: a sitemap INDEX is followed to its pages (never its child sitemap files taken as
pages), a saved index reads its children from the same folder, and the inventory, the page tracker, the link graph and
the technical SEO check all see the pages behind an index. No network beyond 127.0.0.1."""
import functools
import http.server
import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "kit" / "tools"))
import sitemaps  # noqa: E402

DEMO = ROOT / "examples" / "demo-site"
DEMO_PAGES = {"/", "/lawn-mowing", "/blog", "/blog/best-mowing-height", "/about", "/contact"}
INDEX = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<sitemap><loc>{host}/sitemap-pages.xml</loc><lastmod>2026-11-10</lastmod></sitemap>
<sitemap><loc>{host}/sitemap-blog.xml</loc></sitemap>
</sitemapindex>"""
PAGES = """<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://www.example.com/</loc><lastmod>2026-11-01</lastmod></url>
<url><loc>https://www.example.com/services/</loc></url></urlset>"""
BLOG = """<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://www.example.com/blog/a-post/</loc><lastmod>2026-10-02</lastmod></url>
<url><loc>https://www.example.com/services/</loc></url></urlset>"""


def test_parse_tells_an_index_from_a_page_list():
    assert sitemaps.parse(PAGES) == (False, [("https://www.example.com/", "2026-11-01"), ("https://www.example.com/services/", None)])
    is_index, entries = sitemaps.parse(INDEX.format(host="https://www.example.com"))
    assert is_index and [e[0] for e in entries] == ["https://www.example.com/sitemap-pages.xml", "https://www.example.com/sitemap-blog.xml"]


def test_an_index_is_followed_to_its_pages_without_duplicates():
    files = {"https://www.example.com/sitemap.xml": INDEX.format(host="https://www.example.com"),
             "https://www.example.com/sitemap-pages.xml": PAGES, "https://www.example.com/sitemap-blog.xml": BLOG}
    got = sitemaps.read("https://www.example.com/sitemap.xml", get=lambda u: (200, files[u]) if u in files else (404, ""))
    assert got == [("https://www.example.com/", "2026-11-01"), ("https://www.example.com/services/", None),
                   ("https://www.example.com/blog/a-post/", "2026-10-02")]


def test_a_missing_child_sitemap_is_an_error_not_an_empty_site():
    with pytest.raises(sitemaps.SitemapError, match="sitemap-blog.xml"):
        sitemaps.read("https://www.example.com/sitemap.xml", get=lambda u: (200, INDEX.format(host="https://www.example.com"))
                      if u.endswith("/sitemap.xml") else (200, PAGES) if u.endswith("pages.xml") else (404, ""))


def test_a_saved_index_reads_its_children_from_the_same_folder(tmp_path):
    (tmp_path / "sitemap.xml").write_text(INDEX.format(host="https://www.example.com"))
    (tmp_path / "sitemap-pages.xml").write_text(PAGES)
    (tmp_path / "sitemap-blog.xml").write_text(BLOG)
    never = lambda u: pytest.fail(f"fetched {u}: a saved index must read its own folder")  # noqa: E731
    assert len(sitemaps.read(str(tmp_path / "sitemap.xml"), get=never)) == 3


def _index_site(tmp_path, host):
    """A copy of the demo site whose /sitemap.xml is an index of two child sitemaps that hold the demo's six pages."""
    site = tmp_path / "site"
    shutil.copytree(DEMO / "site", site)
    _, entries = sitemaps.parse((DEMO / "site" / "sitemap.xml").read_text())
    half = len(entries) // 2
    for name, part in (("sitemap-pages.xml", entries[:half]), ("sitemap-blog.xml", entries[half:])):
        urls = "".join(f"<url><loc>{loc}</loc><lastmod>{lm}</lastmod></url>" for loc, lm in part)
        (site / name).write_text(f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>')
    (site / "sitemap.xml").write_text(INDEX.format(host=host))
    return site


@pytest.fixture
def index_server(tmp_path):
    """Serve the index copy of the demo site with the demo's clean addresses on a free 127.0.0.1 port (our own thread,
    stopped at the end). The index names its children on this server, as a live site's index names its own host."""
    sys.path.insert(0, str(DEMO))
    import serve
    site = _index_site(tmp_path, "https://brightline.example")
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(serve.Clean, directory=str(site)))
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    (site / "sitemap.xml").write_text(INDEX.format(host=base))
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield site, base
    finally:
        srv.shutdown()
        srv.server_close()


def test_inventory_follows_a_saved_index_and_records_what_it_read(demo_project, index_server):
    site, base = index_server
    env = {**os.environ, "GROWTH_PROJECT": str(demo_project)}
    r = subprocess.run([sys.executable, str(ROOT / "kit" / "tools" / "inventory.py"), "--base", base, "--offline", str(site / "sitemap.xml")],
                       capture_output=True, text=True, env=env, cwd=demo_project)
    assert r.returncode == 0, r.stderr
    inv = json.loads((demo_project / "inventory" / "inventory.json").read_text())
    assert {p["path"] for p in inv["pages"]} == DEMO_PAGES
    assert inv["meta"]["base"] == base and inv["meta"]["sitemap_source"] == str(site / "sitemap.xml")
    head = (demo_project / "inventory" / "INVENTORY.md").read_text()
    assert f"Pages read from {base}" in head and "run `growth page-tracker sync`" in head


def test_the_tracker_follows_an_index_to_its_pages(demo_project, index_server):
    _, base = index_server
    cfg = json.loads((demo_project / "growth.json").read_text())
    cfg["sitemap_url"] = base + "/sitemap.xml"
    (demo_project / "growth.json").write_text(json.dumps(cfg))
    env = {**os.environ, "GROWTH_PROJECT": str(demo_project), "PYTHONDONTWRITEBYTECODE": "1"}
    r = subprocess.run([sys.executable, str(ROOT / "kit" / "page-tracker" / "sitepaths.py"), "--force"],
                       capture_output=True, text=True, env=env, cwd=demo_project, timeout=60)
    assert r.returncode == 0, r.stderr
    assert "source sitemap" in r.stdout and "6 pages" in r.stdout


def test_link_graph_reads_the_pages_behind_an_index(demo_project, index_server, monkeypatch):
    _, base = index_server
    monkeypatch.setenv("GROWTH_PROJECT", str(demo_project))
    sys.path.insert(0, str(ROOT / "kit" / "tools"))
    import link_graph
    locs = link_graph.read_sitemap(base + "/sitemap.xml")
    assert {loc.replace("https://brightline.example", "") or "/" for loc in locs} == DEMO_PAGES


def test_the_tech_seo_sitemap_check_follows_an_index(demo_project, index_server):
    _, base = index_server
    env = {**os.environ, "GROWTH_PROJECT": str(demo_project)}
    r = subprocess.run([sys.executable, str(ROOT / "growth"), "tech_seo_check", base + "/lawn-mowing", "--site-origin",
                        "https://brightline.example"],
                       capture_output=True, text=True, env=env, cwd=demo_project, timeout=120)
    out = r.stdout + r.stderr
    assert "6 URLs" in out, out[-2000:]
    assert "MAP-02" in out and "is not in the sitemap" not in out


def test_doctor_points_the_inventory_at_the_preview_never_the_live_site(demo_project):
    cfg = json.loads((demo_project / "growth.json").read_text())
    cfg["preview_url"] = "http://127.0.0.1:4321"
    (demo_project / "growth.json").write_text(json.dumps(cfg))
    shutil.rmtree(demo_project / "inventory", ignore_errors=True)
    r = subprocess.run([sys.executable, str(ROOT / "kit" / "tools" / "doctor.py")], capture_output=True, text=True, cwd=demo_project,
                       env={**os.environ, "GROWTH_PROJECT": str(demo_project)})
    assert "growth inventory --base http://127.0.0.1:4321" in r.stdout, r.stdout


def test_a_plain_urlset_is_returned_without_duplicates():
    got = sitemaps.read("x", get=lambda u: (200, BLOG.replace("</urlset>", "<url><loc>https://www.example.com/blog/a-post/</loc></url></urlset>")))
    assert [loc for loc, _ in got] == ["https://www.example.com/blog/a-post/", "https://www.example.com/services/"]


@pytest.fixture
def prod_named_server(tmp_path):
    """Like index_server, but the index names its children on the PRODUCTION host (as a real build does) and lives at
    /sitemap_index.xml, named in robots.txt; there is no /sitemap.xml. The production host never resolves here, so any
    request to it fails the test."""
    sys.path.insert(0, str(DEMO))
    import serve
    site = _index_site(tmp_path, "https://brightline.example")
    (site / "sitemap.xml").rename(site / "sitemap_index.xml")
    (site / "robots.txt").write_text("User-agent: *\nAllow: /\n\nSitemap: https://brightline.example/sitemap_index.xml\n")
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(serve.Clean, directory=str(site)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        yield site, f"http://127.0.0.1:{srv.server_address[1]}"
    finally:
        srv.shutdown()
        srv.server_close()


def test_inventory_with_base_reads_every_sitemap_from_the_preview(demo_project, prod_named_server):
    site, base = prod_named_server
    cfg = json.loads((demo_project / "growth.json").read_text())
    cfg["sitemap_url"] = "https://brightline.example/sitemap_index.xml"
    (demo_project / "growth.json").write_text(json.dumps(cfg))
    env = {**os.environ, "GROWTH_PROJECT": str(demo_project)}
    r = subprocess.run([sys.executable, str(ROOT / "kit" / "tools" / "inventory.py"), "--base", base],
                       capture_output=True, text=True, env=env, cwd=demo_project)
    assert r.returncode == 0, r.stderr   # a request to brightline.example would fail: it does not resolve
    inv = json.loads((demo_project / "inventory" / "inventory.json").read_text())
    assert {p["path"] for p in inv["pages"]} == DEMO_PAGES and all(p["status"] == "live" for p in inv["pages"])
    assert inv["meta"]["sitemap_source"] == base + "/sitemap_index.xml"


def test_the_tech_seo_check_reads_the_index_robots_names(demo_project, prod_named_server):
    _, base = prod_named_server
    env = {**os.environ, "GROWTH_PROJECT": str(demo_project)}
    r = subprocess.run([sys.executable, str(ROOT / "growth"), "tech_seo_check", base + "/lawn-mowing", "--site-origin",
                        "https://brightline.example"], capture_output=True, text=True, env=env, cwd=demo_project, timeout=120)
    out = r.stdout + r.stderr
    assert "/sitemap_index.xml is valid XML, 6 URLs" in out, out[-2000:]
    assert "is not in the sitemap" not in out
