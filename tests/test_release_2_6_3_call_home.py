"""2.6.3: words.call-length reads each text element on its own; the home page needs no BreadcrumbList."""
from pathlib import Path

from gatelib import CHECKS
from gatelib.core import Ctx, run_check

CFG = {"words": {"call_minutes": 30}, "schema_types": {"money": ["Service"]}}


def line(html, cid, path="/x/", ptype="money"):
    c = Ctx(project=Path("/nonexistent"), path=path, key="x", ptype=ptype, cfg=CFG, html=html,
            url="http://127.0.0.1:9" + path, status=200)
    run_check(c, CHECKS[cid])
    return c.lines[-1]


def page(body, head=""):
    return f"<html><head>{head}</head><body><main>{body}</main></body></html>"


def test_tool_minutes_next_to_the_call_line_are_not_joined():
    html = page("<div class='tool'><span>Takes 2 minutes</span></div><div class='cta'><span>Free 30-minute call</span></div>")
    assert line(html, "words.call-length").level == "OK"


def test_a_wrong_call_length_in_one_element_still_fails():
    ln = line(page("<p>Book a free 20-minute call with us.</p>"), "words.call-length")
    assert ln.level == "FAIL" and "20-minute call" in ln.what


def ld(*types):
    import json
    return "".join(f'<script type="application/ld+json">{json.dumps({"@context": "https://schema.org", "@type": t})}</script>' for t in types)


def test_home_needs_no_breadcrumb_markup():
    assert line(page("<h1>Home</h1>", ld("Service")), "schema.house-types", path="/").level == "OK"


def test_other_money_pages_still_need_breadcrumb_markup():
    ln = line(page("<h1>Service</h1>", ld("Service")), "schema.house-types", path="/service/")
    assert ln.level == "FAIL" and "BreadcrumbList" in ln.what
