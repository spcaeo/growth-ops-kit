"""Rule 32 (cta.one-path) with growth.json booking_allowed: the site's OWN booking link, used on purpose and listed with
a reason, is printed as a WARN that names the exception (never a silent OK); any other booking link still FAILs; an
entry without a reason FAILs. No network."""
import tempfile
from pathlib import Path

from gatelib import CHECKS
from gatelib.core import Ctx, run_check

OWN = "https://calendly.com/example-team/intro-call"
OTHER = "https://calendly.com/someone-else/30min"
ALLOW = [{"match": "calendly.com/example-team/", "why": "the booking dialog's 'Pick a time' button opens it"}]


def gate(links, allowed=None):
    body = '<a href="/contact/">Book a call</a>' + "".join(f'<a href="{h}">Pick a time</a>' for h in links)
    cfg = {"site_url": "https://www.example.com", "conversion_path": "/contact/", "cta": {"contact_path": "/contact/"}}
    if allowed is not None:
        cfg["booking_allowed"] = allowed
    with tempfile.TemporaryDirectory() as tmp:
        ctx = Ctx(project=Path(tmp), path="/services/", url="http://127.0.0.1:3801/services/", ptype="money", cfg=cfg,
                  html=f"<html><body><main><h1>Services</h1>{body}</main></body></html>", status=200)
        run_check(ctx, CHECKS["cta.one-path"])
        return ctx.lines[0]


def test_a_raw_booking_link_fails_without_an_entry():
    line = gate([OWN])
    assert line.level == "FAIL" and "raw booking link" in line.what


def test_the_sites_own_link_with_a_reason_is_a_named_warn():
    line = gate([OWN, OWN], ALLOW)
    assert line.level == "WARN"
    assert "allowed exception" in line.what and "2 link(s) to calendly.com/example-team/" in line.what
    assert "Pick a time" in line.what and "booking_allowed" in line.fix


def test_any_other_booking_link_still_fails():
    line = gate([OWN, OTHER], ALLOW)
    assert line.level == "FAIL" and "someone-else" in line.what and "example-team" not in line.what


def test_an_entry_without_a_reason_fails():
    line = gate([OWN], [{"match": "calendly.com/example-team/"}])
    assert line.level == "FAIL" and "needs a 'match' and a 'why'" in line.what


def test_a_page_with_no_raw_link_is_plain_ok_even_with_an_entry():
    assert gate([], ALLOW).level == "OK"


def test_a_conversion_path_with_a_trailing_slash_is_found():
    line = gate([])
    assert line.level == "OK" and "1 booking links" in line.what and "/contact" in line.what
