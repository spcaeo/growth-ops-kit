"""2.8.3: four gaps an independent reviewer kept finding on pages the gate passed: the same card grid twice on one surface
(layout.folds-distinct), editor notes in the visible text (words.internal-labels), one named phrase in three folds
(words.named-repeats) and a lone pill on its row at 390 px (layout.card-orphan). Each has a failing and a passing fixture."""
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


def run(cid, body, cfg=None, ptype="money", head=""):
    html = f"<html><body>{head}<main>{body}</main><footer>Footer</footer></body></html>"
    c = Ctx(project=Path("/nonexistent"), path="/p/", key="p", ptype=ptype, cfg=cfg or {}, html=html, url="http://127.0.0.1:9/p/", status=200)
    run_check(c, CHECKS[cid])
    return c.lines[-1]


# ---- 1. the same card grid twice on one surface ----------------------------------------------------------------
def cards(cls, n=3):
    return "<div class='grid'>" + "".join(f"<div class='{cls}'><svg></svg><h3>Title {i}</h3><p>Words {i}.</p></div>" for i in range(n)) + "</div>"


def fold(name, inner, surface="plain"):
    return f"<section data-fold='{name}' data-surface='{surface}'>{inner}</section>"


def test_same_card_grid_on_the_same_surface_fails_even_when_the_fold_shapes_differ():
    a = fold("why", "<h2>Why</h2>" + cards("card"))
    b = fold("how", "<h2>How</h2><p>Intro words.</p><p>More words.</p>" + cards("card", 5))
    ln = run("layout.folds-distinct", a + b)
    assert ln.level == "FAIL" and "'why' and 'how'" in ln.what and "plain" in ln.what, ln.text()


def test_same_cards_on_another_surface_and_far_apart_still_fail():
    a = fold("why", "<h2>Why</h2>" + cards("card"))
    mid = fold("mid", "<h2>Mid</h2><p>One.</p><blockquote>Two</blockquote>", "warm") + fold("mid2", "<h2>M2</h2><table><tr><td>x</td></tr></table>", "dark")
    ln = run("layout.folds-distinct", a + mid + fold("how", "<h2>How</h2><p>Intro.</p>" + cards("card"), "tint"))
    assert ln.level == "FAIL" and "'why' and 'how'" in ln.what and "does not change the shape" in ln.what, ln.text()


def test_cards_with_another_class_or_inner_shape_pass():
    a = fold("why", "<h2>Why</h2>" + cards("card"))
    assert run("layout.folds-distinct", a + fold("how", "<h2>How</h2><p>Intro.</p>" + cards("tile"))).level == "OK"


def test_plain_bullet_lists_are_not_card_grids():
    ul = "<ul><li>One</li><li>Two</li><li>Three</li></ul>"
    assert run("layout.folds-distinct", fold("a", "<h2>A</h2>" + ul) + fold("b", "<h2>B</h2><p>x</p>" + ul)).level == "OK"


def test_a_card_pair_may_be_allowed_with_a_reason_only():
    a = fold("why", "<h2>Why</h2>" + cards("card"))
    b = fold("how", "<h2>How</h2><p>Intro.</p>" + cards("card"))
    ok = {"layout": {"card_repeat_ok": [{"folds": ["why", "how"], "reason": "both are the same product grid by design"}]}}
    assert run("layout.folds-distinct", a + b, ok).level == "OK"
    no = {"layout": {"card_repeat_ok": [{"folds": ["why", "how"]}]}}
    assert run("layout.folds-distinct", a + b, no).level == "FAIL"


# ---- 2. editor notes -------------------------------------------------------------------------------------------
@pytest.mark.parametrize("text", [
    "Pricing is set out in the pricing fold above.", "Compare the plans in the process fold below.", "See the proof fold for the numbers.",
    "See this section for our method.", "The rates are listed in this section below.",
    "Rates as of 3 Nov 2026 (internal).",
])
def test_editor_notes_fail(text):
    ln = run("words.internal-labels", f"<section data-fold='a'><p>We build apps. {text} We ship fast.</p></section>")
    assert ln.level == "FAIL", ln.text()


@pytest.mark.parametrize("block", ["<p>Checked 2026-11-10</p>", "<p>Verified on November 3, 2026 by the team.</p>", "<p>Checked 3 Nov 2026.</p>"])
def test_a_stamp_standing_alone_fails(block):
    assert run("words.internal-labels", f"<section data-fold='a'>{block}</section>").level == "FAIL"


@pytest.mark.parametrize("block", ["<p class='source'>Source: our cost pages. Checked November 22, 2026.</p>",
                                   "<p>4.8 on Clutch from 75 reviews, checked November 9, 2026.</p>"])
def test_a_source_line_keeps_its_date(block):
    assert run("words.internal-labels", f"<section data-fold='a'>{block}</section>").level == "OK"


@pytest.mark.parametrize("text", [
    "Updated 3 November 2026", "Last updated November 3, 2026.", "Published 2026-11-03 by our editors.", "Reviewed May 2026 by a clinician.",
    "We checked the claim with our clients. The section below covers rates?".replace("below", "") + " Verified by our clients.",
])
def test_a_visible_byline_and_plain_prose_pass(text):
    assert run("words.internal-labels", f"<section data-fold='a'><p>{text}</p></section>").level == "OK"


def test_the_byline_pattern_and_notes_are_configurable():
    body = "<section data-fold='a'><p>Rates as of 3 Nov 2026 (internal).</p></section>"
    assert run("words.internal-labels", body).level == "FAIL"
    assert run("words.internal-labels", body, {"words": {"byline": [r"rates as of 3 nov 2026 \(internal\)"]}}).level == "OK"
    extra = "<section data-fold='a'><p>Look at the annex.</p></section>"
    assert run("words.internal-labels", extra, {"words": {"internal": ["the annex"]}}).level == "FAIL"


# ---- 3. a named phrase in three folds --------------------------------------------------------------------------
NAME = "We build on HL7 FHIR R4 and SMART on FHIR for every client."


def three(a, b, c):
    return "".join(f"<section data-fold='{n}'><p>{t}</p></section>" for n, t in zip("abc", (a, b, c)))


def test_a_named_phrase_in_three_folds_fails_and_names_the_longest_form():
    ln = run("words.named-repeats", three(NAME, "Our team knows HL7 FHIR R4 and SMART on FHIR well.", "Expect HL7 FHIR R4 and SMART on FHIR support."))
    assert ln.level == "FAIL" and "HL7 FHIR R4 and SMART on FHIR" in ln.what and "3 folds" in ln.what and ln.what.startswith("1 problem"), ln.text()


def test_two_folds_different_phrases_and_plain_text_pass():
    assert run("words.named-repeats", three(NAME, "Our team knows HL7 FHIR R4 and SMART on FHIR well.", "We write plain words here.")).level == "OK"
    assert run("words.named-repeats", three("Epic and Cerner are covered.", "Work with Epic Systems today.", "We know Epic well.")).level == "OK"


def test_repeat_ok_cta_reason_and_limit_are_respected():
    body = three(NAME, "Teams know HL7 FHIR R4 and SMART on FHIR.", "Use HL7 FHIR R4 and SMART on FHIR.")
    assert run("words.named-repeats", body, {"words": {"repeat_ok": ["HL7 FHIR R4", "SMART on FHIR"]}}).level == "OK"
    assert run("words.named-repeats", body, {"words": {"repeat_folds": 4}}).level == "OK"
    reason = "<a class='btn' href='/c'>Book</a><p class='cta-reason'>Built on HL7 FHIR R4 and SMART on FHIR.</p>"
    sec = lambda n, t: f"<section data-fold='{n}'><p>{t}</p>{reason}</section>"  # noqa: E731
    assert run("words.named-repeats", sec("a", "Plain words.") + sec("b", "More words.") + sec("c", "Other words.")).level == "OK"


def test_title_case_headings_and_months_are_not_names():
    h = lambda n: f"<section data-fold='{n}'><h2>Our Healthcare Software Services</h2><p>Updated November 2026.</p></section>"  # noqa: E731
    assert run("words.named-repeats", h("a") + h("b") + h("c")).level == "OK"


# ---- 4. a pill alone on its row at 390 px ----------------------------------------------------------------------
CSS = "body{margin:0;font:16px/20px sans-serif}.pills{display:flex;flex-wrap:wrap;gap:8px;padding:0 20px}.pills span{width:90px;height:30px;border:1px solid #333;border-radius:15px}"


def pillpage(n):
    pills = "".join(f"<span>Pill {i}</span>" for i in range(n))
    hero = f"<section data-fold='hero' style='padding:20px'><h1>Title</h1><div class='pills'>{pills}</div></section>"
    more = "<section data-fold='b' style='padding:20px'><p>Body words.</p></section>"
    return f"<!doctype html><html><head><style>{CSS}</style></head><body><main>{hero}{more}</main></body></html>"


@pytest.fixture(scope="module")
def serve():
    with tempfile.TemporaryDirectory() as d:
        for n in (4, 7, 6):                     # 390 px fits 3 pills of 92 px a row: 4 leaves one alone, 7 leaves one alone, 6 is full
            (Path(d) / f"p{n}.html").write_text(pillpage(n))
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


def pill(serve, n):
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            p.chromium.launch(headless=True).close()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"chromium cannot launch: {str(e).splitlines()[0][:100]}")
    url = f"{serve}/p{n}.html"
    c = Ctx(project=Path("/nonexistent"), path=f"/p{n}.html", key="x", ptype="money", cfg={}, html=urlopen(url).read().decode(), url=url, status=200)
    run_check(c, CHECKS["layout.card-orphan"])
    return c.lines[-1]


def test_a_lone_pill_on_the_last_row_fails_at_390(serve):
    for n in (4, 7):
        ln = pill(serve, n)
        assert ln.level == "FAIL" and "one alone on the last row" in ln.what and "at 390" in ln.what, ln.text()


def test_a_full_last_row_of_pills_passes(serve):
    ln = pill(serve, 6)
    assert ln.level == "OK" and "1 pill row(s)" in ln.what, ln.text()


# ---- 2.8.5 review fixes ----------------------------------------------------------------------------------------
def test_this_section_in_ordinary_prose_passes():
    body = "<section data-fold='a'><p>The terms in this section apply to every order. Nothing else in this section changes them.</p></section>"
    assert run("words.internal-labels", body).level == "OK"


def test_a_review_cards_lone_verified_stamp_passes_a_bare_one_fails():
    card = "<section data-fold='a'><blockquote><p>Great team.</p><p>Verified Mar 2026</p></blockquote></section>"
    assert run("words.internal-labels", card).level == "OK"
    rc = "<section data-fold='a'><div class='rcard'><p>Great team.</p><p>Verified Mar 2026</p></div></section>"
    assert run("words.internal-labels", rc).level == "OK"
    assert run("words.internal-labels", "<section data-fold='a'><p>Verified Mar 2026</p></section>").level == "FAIL"


def test_topic_words_and_all_caps_pairs_are_not_named_repeats():
    t = lambda n, x: f"<section data-fold='{n}'><p>{x}</p></section>"  # noqa: E731
    body = t("a", "We build HL7 and FHIR links.") + t("b", "Our HL7 and FHIR work is deep.") + t("c", "Teams use HL7 and FHIR daily.")
    head = "<h1>EHR software with HL7 and FHIR</h1>"
    assert run("words.named-repeats", head + body).level == "OK"
    assert run("words.named-repeats", body, {"words": {"topic_terms": ["HL7 and FHIR"]}}).level == "OK"
    assert run("words.named-repeats", body).level == "OK"             # a joined list of two names is no pair
    r4 = t("a", "We build FHIR R4 links.") + t("b", "Our FHIR R4 work is deep.") + t("c", "Teams use FHIR R4 daily.")
    assert run("words.named-repeats", r4).level == "FAIL"             # an adjacent pair with a digit still counts
    assert run("words.named-repeats", "<h1>FHIR R4 software</h1>" + r4).level == "OK"   # unless it is the page's topic
    ai = t("a", "Use AI ML here.") + t("b", "We ship AI ML daily.") + t("c", "Expect AI ML tools.")
    assert run("words.named-repeats", ai).level == "OK"


def test_a_real_repeat_still_fails_on_a_page_with_a_topic():
    ln = run("words.named-repeats", "<h1>EHR software development</h1>" + three(NAME, "Our team knows HL7 FHIR R4 and SMART on FHIR well.",
                                                                           "Expect HL7 FHIR R4 and SMART on FHIR support."))
    assert ln.level == "FAIL" and "HL7 FHIR R4 and SMART on FHIR" in ln.what, ln.text()


def test_no_text_runs_is_a_skip_not_an_ok():
    assert run("words.named-repeats", "").level == "SKIP"


def test_a_plain_checklist_is_not_a_card_grid_but_boxed_grids_still_fail():
    ck = "<ul>" + "".join(f"<li><svg></svg><span>Item {i}</span></li>" for i in range(4)) + "</ul>"
    assert run("layout.folds-distinct", fold("a", "<h2>A</h2>" + ck) + fold("b", "<h2>B</h2><p>x</p>" + ck)).level == "OK"
    box = "<div>" + "".join(f"<div class='tile'><svg></svg><span>Item {i}</span></div>" for i in range(3)) + "</div>"
    ln = run("layout.folds-distinct", fold("a", "<h2>A</h2>" + box) + fold("b", "<h2>B</h2><p>x</p>" + box))
    assert ln.level == "FAIL" and "card grid" in ln.what, ln.text()
    styled = "<ul>" + "".join(f"<li style='border:1px solid #000'><svg></svg><span>Item {i}</span></li>" for i in range(3)) + "</ul>"
    assert run("layout.folds-distinct", fold("a", "<h2>A</h2>" + styled) + fold("b", "<h2>B</h2><p>x</p>" + styled)).level == "FAIL"
