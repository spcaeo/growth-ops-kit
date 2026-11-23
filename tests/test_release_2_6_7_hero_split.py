"""2.6.7: hero.split ignores a script, style or aria-hidden hint next to the hero's grid."""
from pathlib import Path

from gatelib import CHECKS
from gatelib.core import Ctx, run_check


def line(html):
    c = Ctx(project=Path("/nonexistent"), path="/s/", key="x", ptype="money", cfg={}, html=html, url="http://127.0.0.1:9/s/", status=200)
    run_check(c, CHECKS["hero.split"])
    return c.lines[-1]


GRID = "<div class='grid'><div><h1>Title</h1><p>Answer.</p></div><div><form><input name='q'></form></div></div>"


def test_script_and_hint_beside_the_grid_do_not_count_as_columns():
    html = ("<html><body><main><section data-fold='hero'>" + GRID
            + "<script>window.x=1</script><span aria-hidden='true' class='hint'>tap</span></section></main></body></html>")
    assert line(html).level == "OK"


def test_a_hero_without_a_tool_still_fails():
    html = "<html><body><main><section data-fold='hero'><div><h1>Title</h1><p>Answer.</p></div><script>1</script></section></main></body></html>"
    assert line(html).level == "FAIL"
