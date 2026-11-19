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
