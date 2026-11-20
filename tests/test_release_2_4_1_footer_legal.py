"""2.4.1: footer.call-row matches topic links with or without the trailing slash and accepts a secondary footer
button; cta.label-same, cta.reason-line and page.surfaces' act/rhythm rules skip legal pages (rule 49)."""
from pathlib import Path

from gatelib import CHECKS
from gatelib.core import Ctx, run_check

CFG = {"stack": "static", "conversion_path": "/contact-us/", "cta": {"contact_path": "/contact-us/"},
       "features": {"footer_call_row": True}, "silos": {"healthcare-software-development": {}}}


def last(html, cid, path="/x/", cfg=CFG, ptype="core"):
    c = Ctx(project=Path("/nonexistent"), path=path, key="x", ptype=ptype, cfg=cfg, html=html, url="http://127.0.0.1:9" + path, status=200)
    run_check(c, CHECKS[cid])
    return c.lines[-1]


FOOT = ("<footer class='site-footer'><div class='foot__call'><p>Get a plan and a price range in one 30-minute call.</p>"
        "<a class='btn btn--line' href='/contact-us/'>Book a Discovery Call</a></div>"
        "<a href='/healthcare-software-development/'>Healthcare software</a><a href='#top'>Back to top</a></footer>")


def test_footer_slash_and_secondary_button():
    ln = last(f"<html><body><main><p>x</p></main>{FOOT}</body></html>", "footer.call-row")
    assert "topic links missing" not in ln.what and "no booking button" not in ln.what, ln.what


def test_legal_pages_skip_booking_and_act_rules():
    html = ("<html><body><main><section data-fold='terms' data-surface='plain' data-job='read'><p>Terms.</p>"
            "<a href='/contact-us/'>contact us</a></section></main></body></html>").replace("'", '"')
    for cid in ("cta.label-same", "cta.reason-line"):
        assert last(html, cid, path="/terms-of-use/").level == "SKIP"
    ln = last(html, "page.surfaces", path="/terms-of-use/")
    assert ln.level == "OK", ln.what
    assert last(html, "cta.label-same", path="/about-us/").level == "FAIL"
