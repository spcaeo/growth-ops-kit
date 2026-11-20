"""Gate checks read the site's own component names (friction 49, a real site: 4 false FAILs on every money page)."""
from gatelib import CHECKS
from gatelib.core import Ctx, run_check


def line(ctx, cid):
    run_check(ctx, CHECKS[cid])
    return ctx.lines[-1]


CFG = {"conversion_path": "/contact-us", "cta": {"contact_path": "/contact-us"},
       "features": {"call_dialog": {"class": "ctad"}}}


def ctx(html, cfg=CFG, ptype="money"):
    from pathlib import Path
    return Ctx(project=Path("/nonexistent"), path="/x", key="x", ptype=ptype, cfg=cfg, html=html, url="http://127.0.0.1/x", status=200)


BODY = """<html><body><header><a class="btn btn--primary" href="/contact-us/?cta=head">Book a free call</a></header><main>
<section><h1>Move</h1><p>x</p></section>
<section><div data-reveal><p>Leave with clear next steps, whatever you decide, in a free 30-minute call with us.</p>
<a class="btn btn--primary" data-cta href="/contact-us/?cta=hero">Book a free call</a>
<a class="btn btn--ghost" href="/contact-us/?cta=g">Book a free call</a></div></section>
<section data-reveal><form class="kscope__form" data-kscope-form><input type="number" name="items"></form></section>
</main><dialog class="ctad"><a class="btn btn--primary" href="/contact-us/?cta=dlg">Pick a time</a></dialog></body></html>"""


def test_bem_primary_buttons_are_found_and_the_dialog_by_its_own_class():
    assert line(ctx(BODY), "cta.label-same").level == "OK"           # btn btn--primary; ghost and dialog buttons left out
    assert line(ctx(BODY), "cta.reason-line").level == "OK"
    assert line(ctx(BODY), "dialog.call").level != "FAIL"


def test_an_empty_data_reveal_attribute_is_a_reveal_marker():
    assert line(ctx(BODY), "motion.reveal").level == "OK"


def test_a_calculator_form_is_not_a_lead_form_but_a_contact_form_is():
    assert line(ctx(BODY), "form.bot-guard").level == "OK"
    lead = BODY.replace("<input type=\"number\" name=\"items\">", "<input type=\"email\" name=\"email\">")
    assert line(ctx(lead), "form.bot-guard").level == "FAIL"
    guarded = lead.replace("<input type=\"email\" name=\"email\">",
                           "<input type=\"email\" name=\"email\"><input name=\"hp_website\" tabindex=\"-1\">")
    assert line(ctx(guarded), "form.bot-guard").level == "OK"


def test_named_author_can_be_limited_to_some_page_types():
    cfg = {**CFG, "default_author": {"name": "Ann Lee", "path": "/author/ann/", "slug": "ann", "types": ["post"]}}
    assert line(ctx(BODY, cfg), "words.named-author").level == "SKIP"
    assert line(ctx(BODY, cfg, ptype="post"), "words.named-author").level == "FAIL"


def test_a_fold_with_no_reveal_marker_still_fails():
    assert line(ctx(BODY.replace("<section data-reveal>", "<section>")), "motion.reveal").level == "FAIL"


def test_reveal_from_lets_a_site_keep_its_first_folds_still():
    still = BODY.replace("<section><div data-reveal>", "<section><div>")             # fold 2 has no marker
    assert line(ctx(still), "motion.reveal").level == "FAIL"
    cfg = {**CFG, "features": {**CFG["features"], "reveal_from": 3}}
    assert line(ctx(still, cfg), "motion.reveal").level == "OK"


def test_the_header_label_exception_is_honoured_only_with_a_reason():
    page = BODY.replace('href="/contact-us/?cta=head">Book a free call', 'href="/contact-us/?cta=head">Book a call')
    assert line(ctx(page), "cta.label-same").level == "FAIL"
    cfg = {**CFG, "cta": {**CFG["cta"], "header_label": {"label": "Book a call", "why": "owner rule 536c: fits beside the logo"}}}
    assert line(ctx(page, cfg), "cta.label-same").level == "OK"
    cfg2 = {**CFG, "cta": {**CFG["cta"], "header_label": {"label": "Book a call"}}}       # no reason: not honoured
    assert line(ctx(page, cfg2), "cta.label-same").level == "FAIL"


def test_an_allowed_phrase_keeps_its_word_caught_elsewhere():
    from gatelib import spelling
    t = "monday.com Trust Center lists it. Our help center answers."
    probs = spelling.problems(t, "en-CA", {"trust center"})
    assert probs and "x1" in probs[0]                      # only "help center" is still flagged
    assert not spelling.problems("monday.com Trust Center", "en-CA", {"trust center"})


def test_the_exit_offer_is_judged_from_the_served_page_on_a_static_site():
    import gatelib  # noqa: F401
    import adapters.nextjs.c_cta  # noqa: F401  (registers the check)
    cfg = {**CFG, "stack": "static", "features": {**CFG["features"], "exit_offer": {"class": "exit"}}}
    page = BODY.replace("</main>", '</main><dialog class="exit"><button aria-label="Close">x</button>'
                        '<p>Leave with clear next steps on a free 30-minute call with us, whatever you decide.</p>'
                        '<a class="btn btn--primary" href="/contact-us/?cta=exit">Book a free call</a></dialog>')
    assert line(ctx(page, cfg), "exit.present").level == "OK"
    assert line(ctx(BODY, cfg), "exit.present").level == "FAIL"          # no exit dialog at all
