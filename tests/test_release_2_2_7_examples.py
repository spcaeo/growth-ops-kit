"""2.2.7: claims.head-figures and claims.box-numbers skip drawn examples (svg, aria-hidden, data-example), like ev.fact-sources."""
from pathlib import Path

from gatelib import CHECKS
from gatelib.core import Ctx, run_check


def line(html, cid):
    c = Ctx(project=Path("/nonexistent"), path="/g/", key="x", ptype="post", cfg={}, html=html, url="http://127.0.0.1:9/g/", status=200)
    run_check(c, CHECKS[cid])
    return c.lines[-1]


def page(body):
    return f"<html><body><main>{body}</main></body></html>"


APP = "<figure aria-label='An example app, drawn'><div data-example><p>Visit summary, 12 Nov</p><p>You owe $42.10</p></div></figure>"


def test_head_figures_skip_a_drawn_example():
    body = "<h2>Detail</h2><p>Portals cost from $40,000.</p>"
    assert line(page(f"<h1>Mobile portals</h1>{APP}<p>Builds start at $40,000.</p>{body}"), "claims.head-figures").level == "OK"
    for wrap in ("<div aria-hidden='true'><p>Balance $99.00</p></div>",):
        assert line(page(f"<h1>X</h1>{wrap}{body}"), "claims.head-figures").level == "OK"
    ln = line(page(f"<h1>X</h1><p>You owe $42.10</p>{body}"), "claims.head-figures")      # a real head figure still counts
    assert ln.level == "FAIL" and "42.10" in ln.what


def test_box_numbers_skip_a_drawn_example():
    assert line(page("<p>No numbers.</p><aside class='stat' data-example><p>$42.10 due</p></aside>"), "claims.box-numbers").level == "OK"
    assert line(page("<p>No numbers.</p><aside class='stat'><p>Seen 7 times <span aria-hidden='true'>99</span></p></aside>"),
                "claims.box-numbers").what.count("'99'") == 0
    assert line(page("<p>No numbers.</p><aside class='stat'><p>$42.10 due</p></aside>"), "claims.box-numbers").level == "FAIL"
