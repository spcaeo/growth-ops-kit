"""2.8.0: words.internal-labels (rule 11): the team's own process words never reach the visible text of <main>."""
from pathlib import Path

import pytest

from gatelib import CHECKS
from gatelib.core import Ctx, run_check


def line(body, cfg=None, outside=""):
    html = f"<html><body><header>{outside}</header><main><section data-fold='a'>{body}</section></main></body></html>"
    c = Ctx(project=Path("/nonexistent"), path="/p/", key="p", ptype="money", cfg=cfg or {}, html=html, url="http://127.0.0.1:9/p/", status=200)
    run_check(c, CHECKS["words.internal-labels"])
    return c.lines[-1]


@pytest.mark.parametrize("text", [
    "Source: our own page as published before this rebuild.", "Taken from the old page and our guide.", "See the dossier for details.",
    "Each section follows the Fold Plan.", "As set in growth.json for this site.", "This is Rule 28 in action.", "Taken from BRAND and checked.",
    "These FACTS are approved.", "Listed in OWNER-RULES for the team.", "Read the research checkpoint file first.", "See checkpoint 3 for the status.",
])
def test_internal_wording_fails_and_prints_its_sentence(text):
    ln = line(f"<p>Intro here. {text} Next thing.</p>")
    assert ln.level == "FAIL" and text.split(".")[0][:20] in ln.what, ln.text()


def test_the_matching_sentence_is_printed_not_the_whole_text():
    ln = line("<p>We build apps. Source: our page as published before this rebuild. We ship fast.</p>")
    assert "before this rebuild" in ln.what and "We build apps" not in ln.what and "We ship fast" not in ln.what, ln.text()


def test_one_line_per_sentence_when_two_defaults_overlap():
    ln = line("<p>Source: as published before this rebuild.</p>")
    assert ln.level == "FAIL" and ln.what.startswith("1 problem(s)"), ln.text()


def test_clean_text_and_real_words_pass():
    assert line("<p>Sprint checkpoints and compliance checkpoints keep each release safe. The brand voice is plain. Facts and rules apply.</p>").level == "OK"
    assert line("<p>Our brand promise. A fact. A rule of thumb. Rules apply to 28 pages.</p>").level == "OK"


def test_case_sensitive_words_pass_in_lower_case():
    assert line("<p>Our brand, the facts and the owner rules.</p>").level == "OK"


def test_text_outside_main_and_hidden_text_are_not_read():
    assert line("<p>Fine text.</p><p hidden>the old page</p><script>var x='growth.json'</script>", outside="<p>this rebuild</p>").level == "OK"


def test_the_project_extends_the_list_and_allows_real_uses():
    assert line("<p>See the style sheet notes.</p>").level == "OK"
    assert line("<p>See the style sheet notes.</p>", {"words": {"internal": ["style sheet"]}}).level == "FAIL"
    assert line("<p>Use the Mockup file.</p>", {"words": {"internal": [{"pattern": "mockup", "case_sensitive": True}]}}).level == "OK"
    assert line("<p>Use the mockup file.</p>", {"words": {"internal": [{"pattern": "mockup", "case_sensitive": True}]}}).level == "FAIL"
    assert line("<p>Our rule 28 days policy.</p>").level == "FAIL"
    assert line("<p>Our rule 28 days policy.</p>", {"words": {"internal_ok": ["rule 28 days"]}}).level == "OK"
    assert line("<p>The bare checkpoint word.</p>").level == "OK"
    assert line("<p>The bare checkpoint word.</p>", {"words": {"internal": ["checkpoints?"]}}).level == "FAIL"
