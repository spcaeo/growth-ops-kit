"""2.8.0: layout.box-fill (rule 158a): a card or panel is filled by its content. Small pages are served from a temp folder on a free
127.0.0.1 port (started and stopped here); skipped when Playwright's chromium cannot launch."""
import functools
import http.server
import socket
import tempfile
import threading
from pathlib import Path
from urllib.request import urlopen

import pytest

from gatelib import CHECKS
from gatelib.c_layout import box_problems, covered, limits
from gatelib.core import Ctx, run_check

CSS = ("body{margin:0;font:16px/20px sans-serif}p{margin:0}.card{border:1px solid #333;padding:20px;box-sizing:border-box;width:300px}"
       ".row{display:flex;flex-wrap:wrap;gap:20px;align-items:stretch}.wide{border:1px solid #333;padding:20px;box-sizing:border-box;width:100%;max-width:1000px}")


def lines(n, width=260):
    return f'<p style="width:{width}px">' + "Line of text here<br>" * n + "</p>"


def sec(name, inner):
    return f'<section data-fold="{name}" style="padding:40px">{inner}</section>'


def page(inner, extra_css=""):
    return f"<!doctype html><html><head><style>{CSS}{extra_css}</style></head><body><main>{inner}</main></body></html>"


PAGES = {
    "good": page(sec("a", f'<div class="row"><div class="card">{lines(10)}</div><div class="card">{lines(10)}</div></div>'
                    f'<div class="wide"><div style="display:flex;gap:20px"><div style="width:48%">{lines(8)}</div><div style="width:48%">{lines(8)}</div></div></div>')),
    "stretch": page(sec("cards", f'<div class="row"><div class="card"><h3 style="margin:0">Tall card</h3>{lines(12)}</div>'
                      f'<div class="card"><h3 style="margin:0">Short card</h3>{lines(2)}</div></div>')),
    "wide": page(sec("panel", f'<div class="wide"><h3 style="margin:0">Narrow text</h3><p style="width:300px">' + "Line of text here<br>" * 8 + "</p></div>")),
    "table": page(sec("panel", f'<div class="wide"><table><tr><td>One</td><td>Two</td></tr></table>{lines(8, 300)}</div>')),
    "form": page(sec("ask", f'<div class="card"><form><input type="text"><label>Name</label></form>{lines(1)}{lines(1)}{lines(1)}{lines(1)}{lines(1)}</div>')),
    "exempt": page(sec("cards", f'<div class="row"><div class="card" data-layout-exempt>{lines(12)}</div><div class="card" data-layout-exempt>{lines(2)}</div></div>')),
    "bg": page(sec("cards", f'<div class="row"><div style="background:#eef;padding:20px;width:300px;box-sizing:border-box">{lines(12)}</div>'
                   f'<div style="background:#eef;padding:20px;width:300px;box-sizing:border-box">{lines(2)}</div></div>')),
    "picture": page(sec("pics", '<div class="card"><svg width="200" height="200"><rect width="200" height="200" fill="#369"/></svg></div>')),
    "layer": page(sec("cards", '<div class="row"><div style="position:relative;width:300px;padding:20px;box-sizing:border-box;min-height:260px">'
                      '<span aria-hidden="true" style="position:absolute;inset:0;border:2px solid #333"></span>'
                      f'<h3 style="margin:0">Front</h3>{lines(2)}</div></div>')),
    "gap": page(sec("cards", '<div class="row"><div class="card" style="display:flex;flex-direction:column;height:320px">'
                    '<h3 style="margin:0">Pinned</h3><a href="/x" style="margin-top:auto">Read more</a></div></div>')),
    "small": page(sec("cards", '<div class="card" style="width:200px">' + lines(1, 150) + "</div>")),
}


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
    def go(name, cfg=None, no_browser=False):
        url = f"{base}/{name}.html"
        c = Ctx(project=Path("/nonexistent"), path=f"/{name}.html", key="x", ptype="money", cfg=cfg or {}, html=urlopen(url).read().decode(), url=url, status=200)
        c.cache["no_browser"] = no_browser
        run_check(c, CHECKS["layout.box-fill"])
        return c.lines[-1]
    return go


@pytest.fixture(scope="module", autouse=True)
def chromium(base):
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            p.chromium.launch(headless=True).close()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"chromium cannot launch: {str(e).splitlines()[0][:100]}")


def test_filled_boxes_pass(run):
    assert run("good").level == "OK"


def test_a_card_stretched_by_a_taller_neighbour_fails_and_is_named(run):
    ln = run("stretch")
    assert ln.level == "FAIL" and "box 'Short card' in fold 'cards'" in ln.what and "at 1440" in ln.what, ln.text()
    assert "Tall card" not in ln.what and "at 390" not in ln.what      # the full card passes; on a phone the cards stack and none is stretched


def test_a_background_alone_makes_a_box(run):
    assert run("bg").level == "FAIL"


def test_a_hand_drawn_layer_over_the_card_makes_a_box(run):
    ln = run("layer")
    assert ln.level == "FAIL" and "'Front'" in ln.what, ln.text()


def test_a_pinned_button_does_not_hide_an_empty_middle(run):
    ln = run("gap")
    assert ln.level == "FAIL" and "'Pinned" in ln.what, ln.text()


def test_one_narrow_column_in_a_wide_box_fails_on_a_wide_screen_only(run):
    ln = run("wide")
    assert ln.level == "FAIL" and "'Narrow text' in fold 'panel'" in ln.what and "empty on the right" in ln.what and "at 1440" in ln.what, ln.text()
    assert "at 390" not in ln.what


def test_pictures_tables_forms_tools_and_small_boxes_are_not_judged(run):
    for name in ("picture", "table", "form", "exempt", "small"):
        assert run(name).level == "OK", name


def test_limits_come_from_growth_json(run):
    assert run("stretch", {"layout": {"box_fill_min": 0.1}}).level == "OK"
    assert run("wide", {"layout": {"box_empty_right": 0.9}}).level == "OK"
    assert run("wide", {"layout": {"box_empty_px": 2000}}).level == "OK"
    assert run("stretch", {"layout": {"box_min_h": 900}}).level == "OK"
    assert run("gap", {"layout": {"box_gap_merge": 400}}).level == "OK"


def test_no_browser_blocks_never_passes(run):
    ln = run("good", no_browser=True)
    assert ln.level == "SKIP" and ln.blocked


def test_covered_counts_pieces_and_closes_small_gaps():
    assert covered([[0, 100], [200, 300]], 32) == 200
    assert covered([[0, 100], [120, 200]], 32) == 200
    assert covered([[0, 100], [50, 150]], 0) == 150
    assert covered([], 32) == 0


def test_box_problems_unit():
    L = limits(type("C", (), {"cfg": {}})())
    box = {"name": "X", "fold": "f", "w": 400, "h": 300, "innerH": 200, "innerW": 360, "ivs": [[0, 100]], "left": 0, "right": 300}
    assert box_problems([box], L, 1440) and "50%" in box_problems([box], L, 1440)[0]
    assert not box_problems([{**box, "ivs": [[0, 120]]}], L, 1440)
    wide = {**box, "w": 900, "innerW": 860, "ivs": [[0, 200]], "right": 300}
    assert "empty on the right" in box_problems([wide], L, 1440)[0]
    assert not box_problems([{**wide, "left": 300}], L, 1440)           # centred or right-hand content is not a left column
    assert not box_problems([{**wide, "right": 700}], L, 1440)
