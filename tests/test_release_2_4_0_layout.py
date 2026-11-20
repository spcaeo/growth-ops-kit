"""2.4.0: measured design checks (rule 158a). Small HTML pages are served from a temp folder by Python's http.server on a free
127.0.0.1 port (started and stopped here) and every layout check gets one passing and one failing page. Skipped when
Playwright's chromium cannot launch."""
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

CSS = ("body{margin:0;font:16px/20px sans-serif}p{margin:0}.book-cta{display:inline-block;padding:10px;background:#e8743b;color:#fff}"
       ":root{--color-cta:#e8743b}")
TXT = "Some words that fill this block with enough text to count."


def sec(name, inner, pad=60):
    return f'<section data-fold="{name}" style="padding:{pad}px 40px">{inner}</section>'


def block(h, cls=""):
    return f'<p class="{cls}" style="height:{h}px">{TXT}</p>'


CTA = '<a class="book-cta" href="/c">Book a call</a>'
HERO = sec("hero", f'<h1 style="margin:0;height:60px">Title</h1>{block(100)}{CTA}', pad=30)
FILL = lambda n: sec(n, block(900))        # noqa: E731


def cols(a, b):
    return f'<div style="display:flex;gap:20px"><div style="width:45%">{a}</div><div style="width:45%">{b}</div></div>'


def svg(w, h):
    return f'<svg width="{w}" height="{h}" viewBox="0 0 10 10"><rect width="10" height="10" fill="#369"/></svg>'


def grid(n):
    cells = "".join(f"<div><p style='height:100px'>Card {i} {TXT}</p></div>" for i in range(n))
    return f'<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:20px">{cells}</div>'


def page(*secs, header="", extra=""):
    return f"<!doctype html><html><head><style>{CSS}</style></head><body>{header}<main>{''.join(secs)}</main>{extra}</body></html>"


CLOSE = sec("close", block(100) + CTA)
PAGES = {
    "good": page(HERO, sec("a", cols(block(300), block(330)) + block(600)), sec("b", cols(block(300), svg(450, 300)) + grid(6) + block(300)),
                 sec("c", '<div class="flip-card">x</div>' + block(200)), sec("d", '<div class="flip-card">y</div>' + block(200)), CLOSE),
    "gap": page(HERO, sec("proof", block(100), pad=200), sec("cases", block(100), pad=200)),
    "hero": page(sec("hero", block(100) + CTA, pad=150), FILL("a")),
    "cols": page(HERO, sec("a", cols(block(300), block(600)))),
    "pic": page(HERO, sec("a", cols(block(300), svg(50, 50)))),
    "cards": page(HERO, sec("a", grid(4))),
    "view": page(HERO, FILL("a"), header=f"<header style='height:40px'>{CTA}</header>"),
    "space": page(HERO, sec("a", block(900) + CTA)),
    "mech": page(HERO, *[sec(n, '<div class="flip-card">x</div>' + block(100)) for n in "abc"]),
    "terms-good": page(sec("text", block(300))),
    "terms-bad": page(sec("text", block(300) + CTA), extra='<div class="sticky-cta"><p>Call us</p></div>'),
}
EXPECT = [("layout.fold-gap", "gap"), ("layout.hero-height", "hero"), ("layout.column-ratio", "cols"), ("layout.picture-text", "pic"),
          ("layout.card-orphan", "cards"), ("cta.one-per-view", "view"), ("cta.spacing", "space"), ("engage.one-mechanic", "mech")]


@pytest.fixture(scope="module")
def base():
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


@pytest.fixture(scope="module")
def run(base):
    ctxs = {}

    def go(name, cid, cfg=None, no_browser=False):
        key = (name, str(cfg), no_browser)
        if key not in ctxs:
            url = f"{base}/{name}.html"
            c = Ctx(project=Path("/nonexistent"), path=f"/{name}.html", key="x", ptype="money", cfg=cfg or {}, html=urlopen(url).read().decode(), url=url, status=200)
            c.cache["no_browser"] = no_browser
            ctxs[key] = c
        c = ctxs[key]
        n = len(c.lines)
        run_check(c, CHECKS[cid])
        return c.lines[n]
    return go


@pytest.fixture(scope="module", autouse=True)
def chromium(base):
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            p.chromium.launch(headless=True).close()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"chromium cannot launch: {str(e).splitlines()[0][:100]}")


def test_good_page_passes_every_check(run):
    for cid, _ in EXPECT:
        ln = run("good", cid)
        assert ln.level == "OK", ln.text()


@pytest.mark.parametrize("cid,name", EXPECT)
def test_bad_page_fails(run, cid, name):
    ln = run(name, cid)
    assert ln.level == "FAIL", ln.text()


def test_messages_name_fold_and_numbers(run):
    assert "fold 'proof'->'cases': gap 400 px (max 184)" in run("gap", "layout.fold-gap").what
    assert "hero 'hero'" in run("hero", "layout.hero-height").what
    assert "height ratio 2.00" in run("cols", "layout.column-ratio").what
    assert "last row has 1" in run("cards", "layout.card-orphan").what
    assert "'mech'" not in run("mech", "engage.one-mechanic").what and "flip" in run("mech", "engage.one-mechanic").what


def test_limits_come_from_growth_json(run):
    assert run("gap", "layout.fold-gap", {"layout": {"section_step": 200}}).level == "OK"
    assert run("mech", "engage.one-mechanic", {"layout": {"mechanics_max": 3}}).level == "OK"


def test_legal_pages(run):
    assert run("terms-good", "cta.legal-quiet").level == "OK"
    bad = run("terms-bad", "cta.legal-quiet")
    assert bad.level == "FAIL" and "sticky" in bad.what and "primary button" in bad.what
    assert run("terms-bad", "layout.hero-height").level == "SKIP"
    assert run("terms-bad", "layout.column-ratio").level == "SKIP"
    assert run("good", "cta.legal-quiet").level == "SKIP"


def test_no_browser_blocks_never_passes(run):
    ln = run("good", "layout.fold-gap", no_browser=True)
    assert ln.level == "SKIP" and ln.blocked
