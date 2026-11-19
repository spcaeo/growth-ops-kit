"""2.2.4: four selector bugs found on real guide pages (takeaways wrapper, ask-card class, GET prefill forms, box numbers)."""
from pathlib import Path

from gatelib import CHECKS
from gatelib.core import Ctx, run_check


def line(html, cid, cfg=None, ptype="post", path="/guides/x"):
    c = Ctx(project=Path("/nonexistent"), path=path, key="x", ptype=ptype, cfg=cfg or {"conversion_path": "/contact", "cta": {"contact_path": "/contact"}},
            html=html, url="http://127.0.0.1" + path, status=200)
    run_check(c, CHECKS[cid])
    return c.lines[-1]


def page(body):
    return f"<html><body><main>{body}</main></body></html>"


def test_takeaways_uses_the_innermost_box_not_the_page_wrapper():
    many = "<ul>" + "<li>row</li>" * 30 + "</ul>"
    html = page(f"<section class='desk'><h1>Guide</h1>{many}<aside class='tk'><h2>Key takeaways</h2><ul><li>a</li><li>b</li><li>c</li></ul></aside></section>")
    ln = line(html, "post.takeaways")
    assert ln.level == "OK" and "3 takeaways" in ln.what


def test_ask_card_counts_only_the_card_not_links_with_the_class_ask():
    html = page("<div class='ask-card'><p>Help</p></div>" + "".join("<a class='ask' href='/x'>go</a>" for _ in range(10)))
    assert line(html, "post.ask-card").level == "OK"
    assert line(page("<div class='ask-card'></div><div class='next-step'></div>"), "post.ask-card").level == "FAIL"


FORM = "<form method='get' action='{a}'><input type='email' name='e'><button>Go</button></form>"


def test_get_forms_that_only_prefill_the_lead_form_need_no_bot_guard():
    cfg = {"conversion_path": "/contact", "cta": {"contact_path": "/contact"}}
    for a in ("#quote", "/contact", "/contact/"):
        assert line(page(FORM.format(a=a)), "form.bot-guard", cfg).level == "OK", a
    assert line(page(FORM.format(a="/api/lead")), "form.bot-guard", cfg).level == "FAIL"           # submits to a server
    assert line(page("<form method='post' action='#q'><input name='e'></form>"), "form.bot-guard", cfg).level == "FAIL"


def test_box_numbers_found_in_the_prose_and_a_trailing_full_stop_is_ignored():
    box = "<aside class='stat'><p>Founded in 2026. About 99.</p></aside>"
    assert line(page(f"<p>We started in 2026 and reached 99 sites.</p>{box}"), "claims.box-numbers").level == "OK"
    ln = line(page(f"<p>No numbers here.</p>{box}"), "claims.box-numbers")
    assert ln.level == "FAIL" and "'2026'" in ln.what and "'2026.'" not in ln.what


def test_box_numbers_when_the_box_text_is_repeated_in_the_prose():
    box = "<aside class='stat'><p>We cut 45% of the time.</p></aside>"
    assert line(page(f"<p>We cut 45% of the time.</p>{box}"), "claims.box-numbers").level == "OK"        # the prose holds it too


def test_box_ignore_applies_to_author_and_howwe_asides():
    cfg = {"box_ignore": [{"selector": "aside.author", "why": "shared author card, numbers are the author's"},
                          {"selector": "aside.howwe", "why": "shared how-we-test card, its numbers are fixed"}]}
    html = page("<p>Nothing numeric.</p><aside class='author'><p>20 years in 3 cities.</p></aside><aside class='howwe'><p>We test 40 pages.</p></aside>")
    assert line(html, "claims.box-numbers").level == "FAIL"
    assert line(html, "claims.box-numbers", cfg).level == "OK"
