"""2.6.4: a date in a <time> inside a box is not a box number."""
from pathlib import Path

from gatelib import CHECKS
from gatelib.core import Ctx, run_check


def test_byline_date_in_a_box_is_no_number():
    html = ("<html><body><main><p>Prices start at $40,000.</p><aside class='author'><p>By Rakesh, published "
            "<time datetime='2026-11-13'>November 13, 2026</time></p></aside></main></body></html>")
    c = Ctx(project=Path("/nonexistent"), path="/g/", key="g", ptype="post", cfg={}, html=html, url="http://127.0.0.1:9/g/", status=200)
    run_check(c, CHECKS["claims.box-numbers"])
    assert c.lines[-1].level == "OK", c.lines[-1].what
