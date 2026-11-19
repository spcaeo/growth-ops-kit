"""2.2.2 fixes from a real Astro site: approved implied proof, case study and address/phone text in ev.fact-sources, the
booking form as the primary action on the conversion page. Invented names only; no network."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import fact_sources  # noqa: E402
from test_research_record import ctx_for, fact, rec, run  # noqa: E402

from gatelib import CHECKS  # noqa: E402
from gatelib.core import Ctx, run_check  # noqa: E402


def line(ctx, cid):
    run_check(ctx, CHECKS[cid])
    return ctx.lines[-1]


def cctx(html, cfg, path="/x", ptype="money"):
    return Ctx(project=Path("/nonexistent"), path=path, key="x", ptype=ptype, cfg=cfg, html=html, url="http://127.0.0.1" + path, status=200)


# ---- A: words.implied_proof_allow -------------------------------------------------------------------------------------------
PROOF = ("<html><body><main><h1>Home</h1><p>Read the patient portal case study for the full story.</p>"
         "<p>Acme's case studies show how the work goes.</p><p>Trusted by Northwind Clinic and Fabrikam Care.</p></main></body></html>")


def words_cfg(**w):
    return {"words": w}


def test_implied_proof_fails_without_an_allow():
    ln = line(cctx(PROOF, words_cfg()), "words.no-customers")
    assert ln.level == "FAIL" and "case stud" in ln.what.lower() and "trusted by" in ln.what.lower()


def test_an_approved_implied_proof_pattern_passes_with_a_why():
    allow = [{"pattern": "trusted by", "why": "approved in the BRAND.md permission log"},
             {"pattern": "case stud(y|ies)", "why": "approved in the BRAND.md permission log"}]
    assert line(cctx(PROOF, words_cfg(implied_proof_allow=allow)), "words.no-customers").level == "OK"


def test_an_allow_may_be_a_regex_for_the_matched_words():
    allow = [{"pattern": "case stud", "why": "approved in the BRAND.md permission log"}, {"pattern": "trusted", "why": "approved in the log"}]
    assert line(cctx(PROOF, words_cfg(implied_proof_allow=allow)), "words.no-customers").level == "OK"


def test_an_allow_without_a_why_does_not_count_and_fails():
    ln = line(cctx(PROOF, words_cfg(implied_proof_allow=[{"pattern": "trusted by"}])), "words.no-customers")
    assert ln.level == "FAIL" and "needs a 'pattern' and a 'why'" in ln.what


def test_a_hidden_customer_name_still_fails_after_an_allowed_trusted_by():
    allow = [{"pattern": "trusted by", "why": "approved names only"}, {"pattern": "case stud(y|ies)", "why": "approved"}]
    ln = line(cctx(PROOF, words_cfg(implied_proof_allow=allow, hidden_customers=["Fabrikam Care"])), "words.no-customers")
    assert ln.level == "FAIL" and "Fabrikam Care" in ln.what


def test_a_rating_in_structured_data_needs_its_own_allow():
    html = PROOF.replace("</body>", '<script type="application/ld+json">{"@type":"Organization","aggregateRating":{"ratingValue":5}}</script></body>')
    base = [{"pattern": "trusted by", "why": "approved"}, {"pattern": "case stud(y|ies)", "why": "approved"}]
    assert "rating or review" in line(cctx(html, words_cfg(implied_proof_allow=base)), "words.no-customers").what
    more = base + [{"pattern": "aggregateRating", "why": "approved: ratings shown on the live site"}]
    assert line(cctx(html, words_cfg(implied_proof_allow=more)), "words.no-customers").level == "OK"


# ---- B: ev.fact-sources -----------------------------------------------------------------------------------------------------
def stats(text, prose=True):
    return fact_sources.stats_in(text, prose)


def test_case_study_is_a_content_type_not_a_study_claim():
    assert stats("Read the telehealth patient portal case study to see how the team built the whole thing.") == []
    assert stats("Our case studies show how the team built the portal for a clinic last spring.") == []
    assert [s["kind"] for s in stats("A study of case studies found that the reviews were slow in most clinics.")] == ["source"]


def test_address_and_phone_numbers_are_no_stats():
    txt = "USA Office 222 East Main St, Suite B-2, Mesa, AZ 85201 Call +1 (623) 555-0100 or 623-555-0100 or +44 20 555 0100 today."
    assert stats(txt) == []


def test_real_numbers_next_to_an_address_still_count():
    assert any(s["text"].startswith("45") for s in stats("We cut review time by 45% at our Mesa, AZ 85201 office."))


PAGE = "<html><body><main><h1>Contact</h1>{}</main></body></html>"


def test_address_element_and_tel_links_are_skipped(tmp_path):
    html = PAGE.format("<address>222 East Main Street, Mesa, 85201 Arizona</address><p>Phone <a href='tel:+16235550100'>1 623 555 0100 line</a></p>")
    assert not fact_sources.page_stats(__import__("techseo.dom", fromlist=["parse"]).parse(html), __import__("gatelib.domx", fromlist=["x"]))


def test_the_gate_check_passes_on_a_contact_block(tmp_path):
    html = PAGE.format("<p>Read the portal case study.</p><p>USA Office 222 East Main St, Suite B-2, Mesa, AZ 85201 Call +1 (623) 555-0100</p>")
    assert run("ev.fact-sources", ctx_for(tmp_path, rec(vendor_facts=[fact()]), html=html)).level == "OK"


# ---- C: cta.reason-line on the conversion page ------------------------------------------------------------------------------
CFG = {"conversion_path": "/contact", "cta": {"contact_path": "/contact"}}
REASON = "Tell us about your project and get a reply with a price within one working day."


def form_page(reason_before="", reason_after="", head=True):
    h = '<header><a class="btn btn--primary" href="/contact#form">Get my quote</a></header>' if head else ""
    return (f"<html><body>{h}<main><h1>Contact</h1><div><form id='form'><input name='email'><textarea name='m'></textarea>{reason_before}"
            f"<button type='submit'>Send</button></form>{reason_after}</div></main></body></html>")


def test_conversion_page_form_with_reason_after_it_passes():
    assert line(cctx(form_page(reason_after=f"<p>{REASON}</p>"), CFG, "/contact"), "cta.reason-line").level == "OK"


def test_conversion_page_form_with_reason_before_its_submit_passes():
    assert line(cctx(form_page(reason_before=f"<p>{REASON}</p>"), CFG, "/contact"), "cta.reason-line").level == "OK"


def test_conversion_page_form_without_a_reason_fails():
    ln = line(cctx(form_page(), CFG, "/contact"), "cta.reason-line")
    assert ln.level == "FAIL" and "booking form" in ln.what


def test_the_form_is_no_primary_action_on_other_pages():
    ln = line(cctx(form_page(reason_after=f"<p>{REASON}</p>"), CFG, "/other"), "cta.reason-line")
    assert ln.level == "FAIL" and "no primary booking button" in ln.what
