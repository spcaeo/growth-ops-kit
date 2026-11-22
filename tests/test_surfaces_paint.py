"""Issue #68: page.surfaces-paint reads each fold's painted background in a browser; a label that lies fails."""
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

CSS = ('body{margin:0;background:#fff}[data-surface=tint]{background:#eef}[data-surface=warm]{background:#fdf6ec}'
       'section{min-height:200px}[data-surface=geo-grid]::before{content:"";position:absolute;inset:0;'
       'background-image:linear-gradient(#000 1px,transparent 1px);opacity:.07}')


def page(folds):
    secs = "".join(f'<section data-fold="{n}" data-surface="{s}" style="{st}"><p>{n}</p></section>' for n, s, st in folds)
    return f"<!doctype html><html><head><style>{CSS}</style></head><body><main>{secs}</main></body></html>"


PAGES = {
    "honest": page([("a", "plain", ""), ("b", "tint", ""), ("c", "warm", "")]),
    "lying": page([("a", "plain", ""), ("b", "tint", "background:transparent"), ("c", "warm", "")]),
    "before": page([("a", "plain", ""), ("b", "geo-grid", "position:relative"), ("c", "tint", "")]),
    "same": page([("a", "tint", ""), ("b", "warm", "background:#eef"), ("c", "plain", "")]),
}


@pytest.fixture(scope="module")
def base():
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            p.chromium.launch(headless=True).close()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"chromium cannot launch: {str(e).splitlines()[0][:80]}")
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
        try:
            yield f"http://127.0.0.1:{port}"
        finally:
            srv.shutdown()
            srv.server_close()
            t.join(5)


def level(base, name):
    url = f"{base}/{name}.html"
    c = Ctx(project=Path("/nonexistent"), path=f"/{name}.html", key="x", ptype="money", cfg={}, html=urlopen(url).read().decode(),
            url=url, status=200)
    run_check(c, CHECKS["page.surfaces-paint"])
    return c.lines[-1]


def test_an_honest_page_passes(base):
    assert level(base, "honest").level == "OK"


def test_a_tint_label_that_paints_nothing_fails(base):
    ln = level(base, "lying")
    assert ln.level == "FAIL" and "labelled 'tint'" in ln.what


def test_two_neighbours_that_paint_alike_fail_whatever_their_labels(base):
    ln = level(base, "same")
    assert ln.level == "FAIL" and "paint the same background" in ln.what


def test_a_surface_painted_only_on_before_counts(base):
    """#72: the pseudo argument reaches getComputedStyle, so a ::before pattern is seen."""
    ln = level(base, "before")
    assert ln.level == "OK", ln.what
