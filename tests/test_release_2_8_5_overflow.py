"""2.8.5 (rule 158a): text past the border of its box, content under the sticky header, and a clipped breadcrumb at 390 px.
Small pages are served from a temp folder on a free 127.0.0.1 port; skipped when Playwright's chromium cannot launch."""
import functools
import http.server
import socket
import tempfile
import threading
from pathlib import Path
from urllib.request import urlopen

import pytest

from gatelib import CHECKS
from gatelib.core import Ctx, run_check

CSS = "body{margin:0;font:16px/20px sans-serif}p{margin:0}"
LONG = "A line of text that is much longer than its card"


def page(body, head="", css=""):
    return f"<!doctype html><html><head><style>{CSS}{css}</style></head><body>{head}<main>{body}</main></body></html>"


HDR_OK = "<header style='position:sticky;top:0;height:70px;background:#fff'><a href='/'>Home</a></header>"
HDR_FIXED = "<header style='position:fixed;top:0;left:0;right:0;height:70px;background:#fff'><a href='/'>Home</a></header>"
PAGES = {
    "card-bad": page(f"<section><div style='width:140px;border:2px solid #000;padding:8px'><p style='white-space:nowrap'>{LONG}</p></div></section>"),
    "card-ok": page(f"<section><div style='width:140px;border:2px solid #000;padding:8px'><p>{LONG}</p></div></section>"),
    "svg-bad": page(f"<section><svg width='300' height='100'><rect x='10' y='10' width='100' height='60' fill='none' stroke='#000' stroke-width='2'/>"
                    f"<text x='20' y='45' font-size='14'>{LONG}</text></svg></section>"),
    "svg-ok": page("<section><svg width='300' height='100'><rect x='10' y='10' width='200' height='60' fill='none' stroke='#000' stroke-width='2'/>"
                   "<text x='20' y='45' font-size='14'>Short line</text></svg></section>"),
    "hdr-bad": page("<section><h1>Title under the bar</h1><p>Words.</p></section>", HDR_FIXED),
    "hdr-ok": page("<section style='padding-top:90px'><h1>Title under the bar</h1><p>Words.</p></section>", HDR_FIXED),
    "hdr-sticky": page("<section><h1>Title under the bar</h1><p>Words.</p></section>", HDR_OK),
    "clip-table": page(f"<section><div style='width:140px;border:2px solid #000;overflow-x:auto'><table style='width:400px'><tr><td style='white-space:nowrap'>{LONG}</td></tr></table></div></section>"),
    "clip-ellipsis": page(f"<section><div style='width:140px;border:2px solid #000'><p style='white-space:nowrap;overflow:hidden;text-overflow:ellipsis'>{LONG}</p></div></section>"),
    "clip-slide": page(f"<section><div style='width:200px;overflow:hidden'><div style='display:flex;width:600px'>"
                       f"<div style='width:150px;border:1px solid #000'>One</div><div style='width:150px;border:1px solid #000;margin-left:20px'><p style='white-space:nowrap'>{LONG}</p></div></div></div></section>"),
    "hdr-none": page("<section><h1>Title</h1><p>Words.</p></section>"),
    "crumb-bad": page("<section><h1>T</h1></section>", "<nav class='breadcrumb' aria-label='Breadcrumb' style='width:200px;overflow:hidden'>"
                      "<ol style='display:flex;justify-content:flex-end;list-style:none;margin:0;padding:0;white-space:nowrap'><li><a href='/'>Home</a></li>"
                      "<li>/ Long section name here</li><li>/ Another long level name</li></ol></nav>"),
    "crumb-ok": page("<section><h1>T</h1></section>", "<nav class='breadcrumb' aria-label='Breadcrumb'><ol style='display:flex;flex-wrap:wrap;list-style:none;margin:0;padding:0'>"
                     "<li><a href='/'>Home</a></li><li>/ Long section name here</li><li>/ Another long level name</li></ol></nav>"),
}


@pytest.fixture(scope="module")
def run():
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            p.chromium.launch(headless=True).close()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"chromium cannot launch: {str(e).splitlines()[0][:100]}")
    with tempfile.TemporaryDirectory() as d:
        for k, v in PAGES.items():
            (Path(d) / f"{k}.html").write_text(v)
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        quiet = type("H", (http.server.SimpleHTTPRequestHandler,), {"log_message": lambda *a: None})
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), functools.partial(quiet, directory=d))
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()

        def go(name, cid):
            url = f"http://127.0.0.1:{port}/{name}.html"
            c = Ctx(project=Path("/nonexistent"), path=f"/{name}.html", key="x", ptype="money", cfg={}, html=urlopen(url).read().decode(), url=url, status=200)
            run_check(c, CHECKS[cid])
            return c.lines[-1]
        try:
            yield go
        finally:
            srv.shutdown()
            srv.server_close()
            t.join(5)


def test_text_past_its_html_card_fails_and_a_wrapped_line_passes(run):
    bad = run("card-bad", "layout.text-overflow")
    assert bad.level == "FAIL" and "crosses its html box" in bad.what and "1024" in bad.what, bad.text()
    assert run("card-ok", "layout.text-overflow").level == "OK"


def test_text_past_its_svg_card_fails_and_a_fitting_line_passes(run):
    bad = run("svg-bad", "layout.text-overflow")
    assert bad.level == "FAIL" and "svg" in bad.what, bad.text()
    assert run("svg-ok", "layout.text-overflow").level == "OK"


def test_content_under_a_fixed_header_fails_and_padding_or_sticky_passes(run):
    bad = run("hdr-bad", "layout.under-header")
    assert bad.level == "FAIL" and "under the sticky header" in bad.what, bad.text()
    assert run("hdr-ok", "layout.under-header").level == "OK"
    assert run("hdr-sticky", "layout.under-header").level == "OK"


def test_a_breadcrumb_with_its_first_item_scrolled_out_fails(run):
    bad = run("crumb-bad", "layout.breadcrumb-390")
    assert bad.level == "FAIL" and "first item" in bad.what, bad.text()
    assert run("crumb-ok", "layout.breadcrumb-390").level == "OK"


def test_clipping_elements_between_the_text_and_its_box_are_not_overflow(run):
    for name in ("clip-table", "clip-ellipsis"):
        assert run(name, "layout.text-overflow").level == "OK", name
    assert run("clip-slide", "layout.text-overflow").level == "OK"


def test_a_page_with_no_sticky_header_is_a_skip_not_an_ok(run):
    assert run("hdr-none", "layout.under-header").level == "SKIP"
