"""2.8.0: words.fact-repeats (rule 28): one fact in one place. A fact in 3 or more folds fails, and so does a long sentence two folds share."""
from pathlib import Path

from gatelib import CHECKS
from gatelib.c_repeats import fact_phrases
from gatelib.core import Ctx, run_check

LONG = "Our healthcare engineers map every compliance rule before the first sprint starts and sign the agreement first."


def fold(name, inner):
    return f'<section data-fold="{name}"><div><h2>{name}</h2>{inner}</div></section>'


def line(body, cfg=None, head=""):
    html = f"<html><body>{head}<main>{body}</main><footer>Up in 24 to 48 hours. From $30 per hour.</footer></body></html>"
    c = Ctx(project=Path("/nonexistent"), path="/p/", key="p", ptype="money", cfg=cfg or {}, html=html, url="http://127.0.0.1:9/p/", status=200)
    run_check(c, CHECKS["words.fact-repeats"])
    return c.lines[-1]


def three(text_a, text_b, text_c):
    return fold("a", f"<p>{text_a}</p>") + fold("b", f"<p>{text_b}</p>") + fold("c", f"<p>{text_c}</p>")


def test_a_price_in_three_folds_fails_and_names_the_folds():
    ln = line(three("Developers start from $30 per hour.", "The rate is $30 an hour.", "Pay $30 per hour, no more."))
    assert ln.level == "FAIL" and "'$30'" in ln.what and "3 folds (a, b, c)" in ln.what, ln.text()


def test_the_same_time_written_three_ways_is_one_fact():
    ln = line(three("Matched in 24 to 48 hours.", "A shortlist in 24-48 h.", "You hear back in 24–48 hours."))
    assert ln.level == "FAIL" and "24-48 hr" not in ln.what and "3 folds" in ln.what, ln.text()


def test_free_replacement_in_three_words_is_one_promise():
    ln = line(three("A developer who does not fit is replaced at no cost.", "Free replacement if the fit is wrong.", "We offer a free replacement."))
    assert ln.level == "FAIL" and "3 folds" in ln.what, ln.text()


def test_a_percent_and_a_plus_are_facts():
    assert line(three("Up to 35% faster.", "That is 35% faster.", "We gain 35% overall.")).level == "FAIL"
    assert line(three("Over 50+ projects.", "More than 50+ launches.", "A record of 50+ builds.")).level == "FAIL"


def test_the_same_fact_in_two_folds_passes():
    assert line(fold("a", "<p>From $30 per hour.</p>") + fold("b", "<p>The rate is $30.</p>") + fold("c", "<p>Other words here.</p>")).level == "OK"


def test_the_same_fact_twice_in_one_fold_counts_once():
    assert line(fold("a", "<p>$30 per hour.</p><p>Yes, $30 per hour.</p><p>$30 again.</p>") + fold("b", "<p>$30.</p>")).level == "OK"


def test_bare_small_numbers_are_not_facts():
    """list counters, step numbers, years and 'N specializations' never count."""
    t = "<p>Step 3. In 2010. 8 questions. 6 specializations. Chapter 12. Version 2.</p>"
    assert line(fold("a", t) + fold("b", t) + fold("c", t)).level == "OK"


def test_chrome_forms_buttons_dialogs_and_reason_lines_are_not_read():
    skip = ('<nav>From $30 per hour</nav><dialog>From $30 per hour</dialog><form><select><option>$30</option></select></form>'
            '<button>Book in 24 to 48 hours for $30</button><a class="btn book-cta" href="/c">From $30</a>'
            '<p class="hz__reason">$30 per hour, 24 to 48 hours</p><div class="sticky-cta">$30</div><span aria-hidden="true">$30</span>')
    assert line(fold("a", skip) + fold("b", skip) + fold("c", skip), head="<header>$30 $30 $30</header>").level == "OK"


def test_a_long_sentence_in_two_folds_fails():
    ln = line(fold("a", f"<p>{LONG}</p>") + fold("b", f"<p>{LONG} Then we start.</p>"))
    assert ln.level == "FAIL" and "the same sentence in 'a' and 'b'" in ln.what, ln.text()


def test_short_or_different_sentences_pass():
    assert line(fold("a", "<p>We reply fast and clearly.</p>") + fold("b", "<p>We reply fast and clearly.</p>")).level == "OK"
    assert line(fold("a", f"<p>{LONG}</p>") + fold("b", "<p>Pricing follows the roles you need, the integrations and the compliance work involved.</p>")).level == "OK"


def test_repeat_ok_allows_a_fact_and_the_call_length_is_allowed():
    body = three("From $30 per hour.", "The rate is $30.", "Pay $30 per hour.")
    assert line(body, {"words": {"repeat_ok": ["$30"]}}).level == "OK"
    call = three("A 30-minute call.", "Book 30 minutes.", "Your 30 min call.")
    assert line(call).level == "FAIL"
    assert line(call, {"words": {"call_minutes": 30}}).level == "OK"


def test_a_fact_may_be_excused_in_the_folds_where_the_same_words_mean_something_else():
    body = fold("a", "<p>We give 60 days of support.</p>") + fold("b", "<p>Support lasts 60 days.</p>") + fold("rules", "<p>Notice within 60 days of discovery.</p>")
    assert line(body).level == "FAIL"
    assert line(body, {"words": {"repeat_ok": [{"fact": "60 days", "folds": ["rules"]}]}}).level == "OK"
    assert line(body, {"words": {"repeat_ok": [{"fact": "60 days", "folds": ["other"]}]}}).level == "FAIL"


def test_a_long_block_named_why_is_content_not_a_reason_line():
    long = "<div class='why'>" + "Developers start from $30 per hour. " * 8 + "</div>"
    assert line(fold("a", long) + fold("b", long) + fold("c", long)).level == "FAIL"


def test_limits_and_terms_come_from_growth_json():
    two = fold("a", "<p>Start within 5 days.</p>") + fold("b", "<p>Work begins in 5 days.</p>")
    assert line(two).level == "OK"
    assert line(two, {"words": {"repeat_folds": 2}}).level == "FAIL"
    terms = three("NDA signed first.", "We sign the NDA first.", "An NDA comes first.")
    assert line(terms).level == "OK"
    assert line(terms, {"words": {"repeat_terms": [{"pattern": r"\bNDA\b", "as": "nda"}]}}).level == "FAIL"


def test_fact_phrases_normalise():
    got = lambda t: [c for c, _ in fact_phrases(t)]                                  # noqa: E731
    assert got("24 to 48 hours / 24-48 h / 24–48 hrs") == ["24-48 hr"] * 3
    assert got("a 30-minute call, 30 minutes") == ["30 min", "30 min"]
    assert got("$50K to $2M+ and $1,200") == ["$50k-$2m+", "$1200"]
    assert got("60 days, 6+ months, 1 to 2 weeks") == ["60 day", "6+ month", "1-2 week"]
    assert got("35% and 30 to 40 percent and 50+ and 10k+ and 3x") == ["35%", "30-40%", "50+", "10k+", "3x"]
    assert got("Step 3, in 2010, 8 questions, TLS 1.3, HL7 v2") == []
