"""2.4.11: words.h1-clean fails an H1 with a phrase glued on or shown twice."""
from pathlib import Path

from gatelib import CHECKS
from gatelib.core import Ctx, run_check


def lvl(h1):
    html = f"<html><body><main><h1>{h1}</h1></main></body></html>"
    c = Ctx(project=Path("/nonexistent"), path="/g/", key="g", ptype="post", cfg={}, html=html, url="http://127.0.0.1:9/g/", status=200)
    run_check(c, CHECKS["words.h1-clean"])
    return c.lines[-1].level


def test_glued_highlight_fails():
    assert lvl("Teledentistry App Development: Features, Compliance and Cost<span class='hl'>Features, Compliance, Cost</span>") == "FAIL"
    assert lvl("How Testing Reduced Production Defects by 79%<span>Production Defects Cut 79%</span>") == "FAIL"


def test_clean_titles_pass():
    assert lvl("Teledentistry App Development: Features, <span class='hl'>Compliance</span> and Cost") == "OK"
    assert lvl("What Is an mHealth App? Types and Cost") == "OK"
    assert lvl("Build with PayPal and YouTube <span aria-hidden='true'>Decor label</span>") == "OK"
