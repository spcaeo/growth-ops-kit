"""2.8.3: Key takeaways, a contents list and FAQ answers are not second statements of a fact (rules 137, 96); a language
switch to the page's own copy is not an anchor to another page (rule 90)."""
import sys
from pathlib import Path

from gatelib import CHECKS
from gatelib.core import Ctx, run_check

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "kit" / "tools"))


def fold(name, inner):
    return f'<section data-fold="{name}"><div><h2>{name}</h2>{inner}</div></section>'


def line(body):
    html = f"<html><body><main>{body}</main></body></html>"
    c = Ctx(project=Path("/nonexistent"), path="/p/", key="p", ptype="post", cfg={}, html=html, url="http://127.0.0.1:9/p/", status=200)
    run_check(c, CHECKS["words.fact-repeats"])
    return c.lines[-1]


def test_takeaways_toc_and_faq_do_not_count_as_repeats():
    body = (fold("top", '<div class="takeaways"><p>Pro keeps up to 1 year of history.</p></div>')
            + fold("log", "<p>Pro keeps up to 1 year of history.</p>")
            + fold("check", "<p>Export first: Pro holds 1 year.</p>")
            + fold("faq", '<div class="faq"><p>How far back? Pro holds 1 year.</p></div>'))
    assert line(body).level == "OK"


def test_the_same_fact_in_three_body_folds_still_fails():
    body = fold("a", "<p>Pro keeps 1 year.</p>") + fold("b", "<p>Pro holds 1 year.</p>") + fold("c", "<p>Up to 1 year on Pro.</p>")
    assert line(body).level == "FAIL"


def test_language_switch_is_not_a_cross_page_anchor():
    from gatelib.graph_links import same_page
    assert same_page("/en-us/data-migration/x/") == same_page("/data-migration/x/")
