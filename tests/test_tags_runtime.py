"""tags.not-local judges what a local page really requests (headless browser), and without a browser reads the markup,
where a tag loader behind a hostname guard for the site's own host counts as off; embeds.lazy ignores <noscript>
iframes. Example pages only; served on 127.0.0.1 by our own thread; the browser always closes. No request leaves the
machine on purpose (a blocked tag request still shows as a request, which is what is judged)."""
import functools
import http.server
import tempfile
import threading
from pathlib import Path

import pytest

from gatelib import CHECKS
from gatelib.core import Ctx, run_check

LOADER = "var s=document.createElement('script');s.src='https://www.googletagmanager.com/gtm.js?id=GTM-TEST';document.head.appendChild(s);"
PAGES = {
    "unguarded.html": f"<script>{LOADER}</script>",
    "guarded.html": f"<script>if (/(^|\\.)example\\.com$/.test(location.hostname)) {{ {LOADER} }}</script>",
    "fires-locally.html": f"<script>if (location.hostname !== 'example.org') {{ {LOADER} }}</script>",
    "other-host.html": f"<script>if (/(^|\\.)other\\.example$/.test(location.hostname)) {{ {LOADER} }}</script>",
}
CFG = {"site_url": "https://www.example.com"}


def page(body):
    return f"<!doctype html><html><head><title>t</title></head><body><main><h1>t</h1>{body}</main></body></html>"


@pytest.fixture(scope="module")
def site():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        for name, body in PAGES.items():
            (d / name).write_text(page(body))

        class Quiet(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *a):
                pass

        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(d)))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            yield d, f"http://127.0.0.1:{srv.server_address[1]}"
        finally:
            srv.shutdown()
            srv.server_close()


def run(d, base, name, cid="tags.not-local", browser=True):
    with tempfile.TemporaryDirectory() as tmp:
        ctx = Ctx(project=Path(tmp), path="/x", url=f"{base}/{name}", cfg=CFG, html=(d / name).read_text(), status=200)
        if not browser:
            ctx.cache["no_browser"] = True
        run_check(ctx, CHECKS[cid])
        return ctx.lines[0]


def browser_ok():
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            p.chromium.launch(headless=True).close()
        return True
    except Exception:  # noqa: BLE001
        return False


@pytest.mark.skipif(not browser_ok(), reason="no headless browser installed")
@pytest.mark.parametrize("name,level", [("unguarded.html", "FAIL"), ("guarded.html", "OK"), ("fires-locally.html", "FAIL")])
def test_the_browser_judges_real_requests(site, name, level):
    d, base = site
    line = run(d, base, name)
    assert line.level == level, (name, line.what)
    if level == "OK":
        assert "headless browser" in line.what


@pytest.mark.parametrize("name,level", [("unguarded.html", "FAIL"), ("guarded.html", "OK"), ("other-host.html", "FAIL")])
def test_without_a_browser_a_guard_for_the_sites_own_host_counts(site, name, level):
    d, base = site
    line = run(d, base, name, browser=False)
    assert line.level == level, (name, line.what)


def test_a_noscript_iframe_is_not_an_eager_embed():
    tag = '<iframe src="https://www.googletagmanager.com/ns.html?id=GTM-TEST" height="0" width="0"></iframe>'
    for html, level in ((page(f"<noscript>{tag}</noscript>"), "OK"), (page(tag), "FAIL")):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = Ctx(project=Path(tmp), path="/x", url="http://127.0.0.1:9/x", cfg=CFG, html=html, status=200)
            run_check(ctx, CHECKS["embeds.lazy"])
            assert ctx.lines[0].level == level
