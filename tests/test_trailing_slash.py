"""Sites whose addresses end in "/" (/blog/post/): the inventory matches its sitemap paths to the tracker's numbers and to
growth.json lists whichever form each uses, and the page tracker asks analytics for the site's own form (/x/), because
Search Console keys a page by its exact address (/x returned 0). No network beyond 127.0.0.1."""
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


def test_inventory_rows_match_numbers_and_lists_with_or_without_the_slash(demo_project, monkeypatch):
    cfg = json.loads((demo_project / "growth.json").read_text())
    cfg["money_core"] = ["/lawn-mowing"]                 # growth.json without the slash
    cfg["core_pages"] = {"/about": ["trust", "MOFU"]}
    (demo_project / "growth.json").write_text(json.dumps(cfg))
    monkeypatch.setenv("GROWTH_PROJECT", str(demo_project))
    sys.path.insert(0, str(ROOT / "kit" / "tools"))
    for m in ("config", "inventory"):
        sys.modules.pop(m, None)
    import inventory
    sm = {"/lawn-mowing/": "2026-11-10", "/about/": None}   # the sitemap with it
    pages = {p: (200, "<html><head><title>t</title></head><body><main><h1>x</h1></main></body></html>") for p in sm}
    rows = {r["path"]: r for r in inventory.build(sm, pages, gsc={"/lawn-mowing": (6, 13860, 3.2)}, readers={"/about": 40})}
    assert rows["/lawn-mowing/"]["gsc_impressions"] == 13860 and rows["/lawn-mowing/"]["gsc_clicks"] == 6
    assert rows["/lawn-mowing/"]["money_page"] and rows["/about/"]["visitors"] == 40 and rows["/about/"]["type"] == "trust"


def serve_sitemap(folder, locs):
    (folder / "sitemap.xml").write_text('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                                        + "".join(f"<url><loc>{l}</loc></url>" for l in locs) + "</urlset>")
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(folder)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


@pytest.mark.parametrize("slash,expect", [(True, "/blog/a-post/"), (False, "/blog/a-post")])
def test_the_tracker_asks_for_the_sites_own_address_form(demo_project, tmp_path, slash, expect):
    end = "/" if slash else ""
    srv = serve_sitemap(tmp_path, ["https://brightline.example/", f"https://brightline.example/blog/a-post{end}",
                                   f"https://brightline.example/about{end}"])
    try:
        cfg = json.loads((demo_project / "growth.json").read_text())
        cfg["sitemap_url"] = f"http://127.0.0.1:{srv.server_address[1]}/sitemap.xml"
        (demo_project / "growth.json").write_text(json.dumps(cfg))
        code = ("import sitepaths, config; r = sitepaths.fetch(force=True); "
                "print(sorted(p['path'] for p in r['pages'])); print(config.variants('/blog/a-post'), config.variants('/'))")
        r = subprocess.run([sys.executable, "-c", code], cwd=ROOT / "kit" / "page-tracker", capture_output=True, text=True,
                           env={**os.environ, "GROWTH_PROJECT": str(demo_project), "PYTHONDONTWRITEBYTECODE": "1"}, timeout=60)
    finally:
        srv.shutdown()
        srv.server_close()
    assert r.returncode == 0, r.stderr
    assert "['/', '/about', '/blog/a-post']" in r.stdout          # the tracker keeps one form inside
    assert f"['{expect}'] ['/']" in r.stdout                        # and asks analytics for the site's own
