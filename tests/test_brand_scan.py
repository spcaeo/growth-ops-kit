"""growth brand-scan (3.0.2): the facts a site states about itself, read into a draft for BRAND.md. A made-up site (Brightwave
Studio, example.* addresses), no network: the readers get strings, the scanner gets a dict of pages, the command talks to a
local http.server."""
import http.server
import json
import os
import re
import subprocess
import sys
import threading
from pathlib import Path

import pytest

import brand_scan
import fetch_rule
from brandscan import contacts, ctas, legal, llms, pick
from brandscan.page import Page

import brand_scan_site as site

ROOT = Path(__file__).resolve().parent.parent
BASE = "http://127.0.0.1:9"
CFG = {"site_url": site.LIVE, "live_site_rule": "no-crawl", "preview_url": BASE}


def run_scan(pages=None, cfg=None, max_pages=25, seen=None):
    pages = pages if pages is not None else site.pages()

    def fetch(url):
        if seen is not None:
            seen.append(url)
        return pages.get(url.replace(BASE, ""), (404, ""))
    return brand_scan.scan(BASE, cfg or CFG, max_pages=max_pages, fetch=fetch, today="2026-11-26")


@pytest.fixture(scope="module")
def result():
    return run_scan()


# ---- emails ------------------------------------------------------------------------------------------------------------
def test_emails_from_links_text_written_out_and_hidden_forms():
    p = Page(site.CONTACT.replace("CFEMAIL", site.cf_email("billing@brightwave.example")).replace("LOGO2X", "logo" + "@2x.png"), "x")
    found = contacts.find_emails(p.raw, p.text, [l["href"] for l in p.links])
    assert {"support@brightwave.example", "sales@brightwave.example", "jobs@brightwave.example", "billing@brightwave.example",
            "press@partner-news.example"} <= set(found)
    assert not any("2x" in e or e.endswith(".png") for e in found)           # an image name, not an address


def test_a_mailto_with_a_subject_and_several_addresses():
    assert contacts.find_emails("", "", ["mailto:Sales@Brightwave.example?subject=Hi&body=x", "mailto:a@brightwave.example,b@brightwave.example"]) == \
        ["sales@brightwave.example", "a@brightwave.example", "b@brightwave.example"]


def test_written_out_forms():
    text = "Mail name [at] brightwave [dot] example or name2 (at) brightwave.example or name3 AT brightwave DOT example."
    assert contacts.find_emails("", text, []) == ["name@brightwave.example", "name2@brightwave.example", "name3@brightwave.example"]


def test_emails_are_grouped_on_the_company_domain_or_not_and_labelled():
    assert contacts.group_of("a@brightwave.example", "brightwave.example") == "company"
    assert contacts.group_of("a@mail.brightwave.example", "brightwave.example") == "company"
    assert contacts.group_of("a@notbrightwave.example", "brightwave.example") == "other"
    labels = {e: contacts.label_of(e) for e in ["support@x.example", "help@x.example", "sales@x.example", "privacy@x.example", "dpo@x.example",
                                              "legal@x.example", "careers@x.example", "jobs@x.example", "info@x.example", "hello@x.example", "billing@x.example"]}
    assert labels == {"support@x.example": "support", "help@x.example": "support", "sales@x.example": "sales", "privacy@x.example": "privacy",
                      "dpo@x.example": "privacy", "legal@x.example": "legal", "careers@x.example": "careers", "jobs@x.example": "careers",
                      "info@x.example": "info", "hello@x.example": "info", "billing@x.example": "other"}


def test_cloudflare_hidden_address_decodes():
    assert contacts.decode_cloudflare(site.cf_email("team@brightwave.example")) == "team@brightwave.example"
    assert contacts.decode_cloudflare("zz") == ""


# ---- phones ------------------------------------------------------------------------------------------------------------
def test_phones_from_tel_links_and_text_but_not_dates_or_fax():
    text = "Call us: +1 (202) 555-0143. Fax: +1 202-555-0188. Updated 2026-11-02. Version 1.2.3.4 build 20261102."
    phones = contacts.find_phones(text, ["tel:+1-202-555-0143"])
    assert [contacts.phone_key(p) for p in phones] == ["+12025550143"]       # the same number once; the fax and the date are left out


# ---- booking links -----------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("url,provider", [
    ("https://calendly.com/brightwave/intro", "Calendly"), ("https://cal.com/brightwave/30min", "Cal.com"),
    ("https://meetings.hubspot.com/jane-doe", "HubSpot meetings"), ("https://savvycal.com/jane/chat", "SavvyCal"),
    ("https://tidycal.com/jane/chat", "TidyCal"), ("https://brightwave.as.me/", "Acuity Scheduling"),
    ("https://app.acuityscheduling.com/schedule.php?owner=1", "Acuity Scheduling"), ("https://brightwave.youcanbook.me", "YouCanBook.me"),
    ("https://zcal.co/i/abc", "Zcal"), ("https://brightwave.chilipiper.com/book/me", "Chili Piper"),
    ("https://calendar.google.com/calendar/appointments/schedules/abc", "Google Calendar appointments"),
    ("https://outlook.office365.com/owa/calendar/Brightwave@brightwave.example/bookings/", "Microsoft Bookings"),
])
def test_booking_providers_are_matched_by_host(url, provider):
    assert contacts.booking_provider(url) == provider


@pytest.mark.parametrize("url", ["https://calendly.com/", "https://calendly.com/pricing", "https://cal.com/features", "https://www.google.com/calendar",
                                 "https://example.com/calendly", "https://notcalendly.com/x/y"])
def test_a_providers_own_pages_and_other_hosts_are_not_booking_links(url):
    assert contacts.booking_provider(url) == ""


def test_booking_links_from_links_iframes_and_scripts_without_tracking_codes():
    html = ('<a href="https://calendly.com/brightwave/intro-call?utm_source=site&a=1">Book</a><iframe src="https://calendly.com/brightwave/intro-call"></iframe>'
            "<script>Calendly.initPopupWidget({url: 'https://cal.com/brightwave/30min'}); var j = \"https:\\/\\/savvycal.com\\/jane\\/chat\";</script>"
            '<a href="https://calendly.com/pricing">x</a>')
    links = contacts.find_booking(html, ["https://calendly.com/brightwave/intro-call?utm_source=site&a=1"])
    assert {(b["provider"], b["url"]) for b in links} == {("Calendly", "https://calendly.com/brightwave/intro-call"), ("Cal.com", "https://cal.com/brightwave/30min"),
                                                          ("SavvyCal", "https://savvycal.com/jane/chat")}


# ---- social ------------------------------------------------------------------------------------------------------------
def test_social_profiles_but_not_share_buttons():
    assert contacts.social_of("https://www.linkedin.com/company/brightwave-studio/") == ("LinkedIn", "https://linkedin.com/company/brightwave-studio")
    assert contacts.social_of("https://twitter.com/brightwave_hq")[0] == "X"
    assert contacts.social_of("https://www.youtube.com/@brightwavestudio") == ("YouTube", "https://youtube.com/@brightwavestudio")
    assert contacts.social_of("https://clutch.co/profile/brightwave")[0] == "Clutch"
    assert contacts.social_of("https://www.g2.com/products/brightwave/reviews")[0] == "G2"
    for bad in ["https://www.facebook.com/sharer/sharer.php?u=x", "https://twitter.com/intent/tweet?text=hi", "https://www.linkedin.com/sharing/share-offsite/?url=x",
                "https://github.com/features", "https://www.instagram.com/p/abc/"]:
        assert contacts.social_of(bad) == ("", ""), bad


# ---- calls to action ---------------------------------------------------------------------------------------------------
def test_which_wordings_are_calls_to_action():
    assert [ctas.is_cta(t) for t in ["Book a demo", "Get a quote", "Start free trial →", "Hire Healthcare Developers", "Contact us", "Our story", "Skip to content",
                                     "Appointment reminder app for clinics", "Read more about booking"]] == \
        ["strong", "strong", "strong", "medium", "weak", "", "", "", ""]


def test_ctas_are_counted_by_page_and_the_most_common_strong_one_leads():
    pages = [{"url": f"http://x/{i}", "links": [{"text": "Contact", "href_abs": "http://x/contact", "region": "nav"}, {"text": "Hire Developers", "href_abs": "", "region": "nav"}],
              "buttons": []} for i in range(5)]
    pages[0]["links"].append({"text": "Book a demo", "href_abs": "http://x/book", "region": "main"})
    pages[1]["buttons"].append({"text": "  Book   a demo ", "region": "main", "href": ""})
    pages[2]["links"].append({"text": "Get a quote", "href_abs": "", "region": "main"})
    out = ctas.collect(pages)
    assert out[0]["text"] == "Book a demo" and out[0]["count"] == 2 and len(out[0]["pages"]) == 2 and out[0]["kinds"] == ["button", "link"]
    assert out[0]["targets"] == ["http://x/book"]
    assert [c["strength"] for c in out][:3] == ["strong", "strong", "medium"]      # a nav link on every page does not outrank the strong wording
    assert next(c for c in out if c["text"] == "Contact")["count"] == 5


# ---- terms and privacy -------------------------------------------------------------------------------------------------
def terms_text():
    return Page(site.TERMS, "x").text


def test_legal_name_address_law_date_and_laws_from_a_terms_page():
    t = terms_text()
    names = legal.legal_names(t)
    assert names[0]["name"] == "Brightwave Studio Pvt. Ltd." and names[0]["strong"]              # "Pvt. Ltd." does not end the sentence
    assert legal.postal_addresses(t) == ["12 Harbour Road, Suite 4, Ahmedabad 380015, India"]
    gl = legal.governing_law(t)
    assert gl["law"] == ["State of Delaware"] and gl["jurisdiction"] == ["Wilmington, Delaware"]
    assert legal.last_updated(t) == "November 3, 2025"
    assert legal.named_laws(t) == ["GDPR", "CCPA"]


def test_other_wordings_of_the_same_facts():
    assert legal.legal_names("© 2026 Acme Widgets LLC. All rights reserved.")[0]["name"] == "Acme Widgets LLC"
    assert legal.legal_names("Operated by Nordlicht GmbH in Berlin.")[0]["name"] == "Nordlicht GmbH"
    assert legal.legal_names("Welcome to Fieldstone Labs Inc.")[0]["name"] == "Fieldstone Labs Inc."
    assert legal.governing_law("in accordance with and subject to, prevailing law of Canada")["law"] == ["Canada"]
    assert legal.governing_law("This Agreement is governed by and construed in accordance with the laws of England and Wales.")["law"] == ["England and Wales"]
    assert legal.last_updated("Effective date: 1 March 2026") == "1 March 2026"
    assert legal.last_updated("Last Updated 2025-12-01") == "2025-12-01"
    assert legal.copyright_holder("© 2026 Brightwave Studio. All rights reserved.") == "Brightwave Studio"


def test_no_made_up_facts_from_ordinary_text():
    t = "We build sites in 5 weeks. Call 2026-11-02 something. Page 12 of 40, section 3.2. Our team of 25 people."
    assert legal.legal_names(t) == [] and legal.postal_addresses(t) == [] and legal.governing_law(t)["law"] == [] and legal.last_updated(t) == ""


def test_privacy_contact_names_the_officer_and_the_address_beside_it():
    d = legal.dpo(Page(site.PRIVACY, "x").text, ["privacy@brightwave.example", "other@brightwave.example"])
    assert d["emails"] == ["privacy@brightwave.example"] and "Data Protection Officer" in d["sentence"]


# ---- llms.txt and JSON-LD ----------------------------------------------------------------------------------------------
def test_llms_txt_title_summary_sections_and_links():
    d = llms.parse_llms(site.LLMS)
    assert d["title"] == "Brightwave Studio" and d["summary"].startswith("Brightwave builds fast websites")
    assert [s["heading"] for s in d["sections"]] == ["Services", "Company"] and d["links"] == 3
    assert d["sections"][0]["links"][0] == {"text": "Website build", "url": "https://www.brightwave.example/services/build", "note": "A new site in four weeks"}
    full = llms.parse_llms_full(site.LLMS_FULL)
    assert full["title"] == "Brightwave Studio" and full["headings"] == ["Brightwave Studio", "Services", "Company"] and full["chars"] == len(site.LLMS_FULL)


def test_an_html_page_where_llms_txt_should_be_is_not_an_llms_txt():
    assert not llms.looks_like_text("<!DOCTYPE html><html><body>Home</body></html>")
    assert llms.looks_like_text(site.LLMS)


def test_json_ld_organization_data():
    org = llms.organizations(Page(site.HOME, "x").jsonld)[0]
    assert org["legalName"] == "Brightwave Studio Pvt. Ltd." and org["email"] == "hello@brightwave.example" and org["telephone"] == "+1 202-555-0143"
    assert org["address"] == "12 Harbour Road, Ahmedabad, 380015, IN"
    assert org["sameAs"] == ["https://www.linkedin.com/company/brightwave-studio", "https://x.com/brightwave_hq"]
    assert org["contactPoints"] == [{"contactType": "sales", "email": "sales@brightwave.example"}]
    assert llms.organizations(["{not json", '{"@type": "Product", "name": "x"}']) == []


# ---- page choice -------------------------------------------------------------------------------------------------------
def test_page_categories():
    cat = pick.category_of
    assert cat("https://x.example/legal/terms-of-service") == "terms" and cat("https://x.example/privacy-policy/") == "privacy"
    assert cat("https://x.example/impressum") == "imprint" and cat("https://x.example/book-a-demo") == "demo"
    assert cat("https://x.example/legal/p", "Privacy Policy") == "privacy" and cat("https://x.example/", "") == "" and cat("https://x.example/blog/hello") == ""
    assert not pick.worth_reading("https://x.example/blog/privacy-tips") and pick.worth_reading("https://x.example/blog/privacy-tips", "footer")
    assert not pick.worth_reading("https://x.example/a/b/privacy-tips") and not pick.worth_reading("https://x.example/policy.pdf", "footer")


# ---- the whole scan ----------------------------------------------------------------------------------------------------
def test_the_scan_reads_the_right_pages_once_each_and_never_a_blog_post(result):
    paths = [p["path"] for p in result["pages"]]
    assert paths[0] == "/" and {"/legal/terms-of-service", "/privacy-policy", "/contact", "/about", "/book", "/pricing", "/llms.txt", "/llms-full.txt"} <= set(paths)
    assert len(paths) == len(set(paths)) and not any(p.startswith("/blog") for p in paths)
    assert result["not_read"] == []                                                      # llms.txt was at /llms.txt, so /.well-known/ was not asked


def test_the_scan_finds_company_facts_with_sources(result):
    c = result["findings"]["company"]
    assert c["legal_names"][0]["name"] == "Brightwave Studio Pvt. Ltd." and BASE + "/legal/terms-of-service" in c["legal_names"][0]["sources"]
    assert c["addresses"][0]["address"] == "12 Harbour Road, Suite 4, Ahmedabad 380015, India"
    assert [g["place"] for g in c["governing_law"]] == ["State of Delaware"] and c["governing_law"][0]["sources"] == [BASE + "/legal/terms-of-service"]
    assert {(u["document"], u["date"]) for u in c["last_updated"]} == {("terms", "November 3, 2025"), ("privacy", "1 March 2026")}
    assert {x["law"] for x in c["laws"]} == {"GDPR", "CCPA", "HIPAA"}
    assert [x["email"] for x in c["privacy_contacts"]] == ["privacy@brightwave.example"]
    assert c["home"]["site_name"] == "Brightwave Studio" and c["home"]["title"].startswith("Brightwave Studio")
    assert c["organization_data"][0]["legalName"] == "Brightwave Studio Pvt. Ltd."


def test_the_scan_groups_emails_and_labels_them(result):
    by = {e["email"]: e for e in result["findings"]["emails"]}
    assert by["support@brightwave.example"]["group"] == "company" and by["support@brightwave.example"]["label"] == "support"
    assert by["sales@brightwave.example"]["sources"] and by["jobs@brightwave.example"]["label"] == "careers"
    assert by["billing@brightwave.example"]["label"] == "other"                      # the hidden (Cloudflare) one, decoded
    assert by["press@partner-news.example"]["group"] == "other"
    assert by["hello@brightwave.example"]["sources"] == [BASE + "/ (JSON-LD)"]
    assert all(e["read_on"] == "2026-11-26" for e in by.values())
    phones = result["findings"]["phones"]
    assert len(phones) == 1 and phones[0]["pages"] == 2                               # the contact page and the JSON-LD say the same number


def test_the_scan_finds_booking_links_cta_social_and_ai_files(result):
    f = result["findings"]
    assert {b["url"] for b in f["booking_links"]} == {"https://calendly.com/brightwave/intro-call", "https://cal.com/brightwave/30min"}
    assert f["main_cta"]["text"] == "Book a demo" and len(f["main_cta"]["pages"]) >= 4
    assert f["main_cta"]["targets"] == ["https://calendly.com/brightwave/intro-call", site.LIVE + "/book"]       # own links as live addresses, not the preview's
    assert {c["text"] for c in f["ctas"]} >= {"Book a demo", "Get a quote", "Contact us"}
    assert {s["network"] for s in f["social"]} == {"LinkedIn", "X", "GitHub", "Instagram", "YouTube"}         # no Facebook share, no tweet button
    assert f["llms_txt"]["found"] and f["llms_txt"]["title"] == "Brightwave Studio" and f["llms_full_txt"]["found"] and f["llms_full_txt"]["heading_count"] == 3
    assert f["robots"]["found"]


def test_the_scan_says_when_the_site_says_two_things(result):
    assert [c["what"] for c in result["conflicts"]] == ["more than one booking link"]
    pages = site.pages()
    pages["/contact"] = (200, site.CONTACT.replace("CFEMAIL", site.cf_email("billing@brightwave.example")).replace("support@brightwave.example", "help@brightwave.example")
                         .replace("Press:", "Also support@brightwave.example. Press:"))
    r = run_scan(pages)
    msgs = {c["what"]: c["values"] for c in r["conflicts"]}
    assert sorted(msgs["2 different support emails on the company domain"]) == ["help@brightwave.example", "support@brightwave.example"]


def test_what_is_not_found_is_listed():
    r = run_scan({"/": (200, "<html><body><main><h1>Hi</h1></main></body></html>")})
    assert r["findings"]["emails"] == [] and r["findings"]["main_cta"] is None
    assert {"legal company name", "postal address", "governing law", "email on the company's own domain", "booking link (Calendly and the like)", "llms.txt"} <= set(r["not_found"])


def test_a_trailing_slash_is_one_page_and_a_404_retries_with_the_slash():
    pages = {"/": (200, '<html><body><footer><a href="/privacy-policy">Privacy</a><a href="/privacy-policy/">Privacy again</a></footer></body></html>'),
             "/privacy-policy/": (200, "<html><body><main>Effective date: 1 March 2026</main></body></html>")}
    seen = []
    r = run_scan(pages, seen=seen)
    assert [p["path"] for p in r["pages"]] == ["/", "/privacy-policy/"]
    assert seen.count(BASE + "/privacy-policy/") == 1 and r["findings"]["company"]["last_updated"][0]["date"] == "1 March 2026"


def test_the_page_limit_holds():
    r = run_scan(max_pages=3)
    assert len([p for p in r["pages"] if p["category"] not in ("llms.txt", "llms.full.txt", "security.txt")]) <= 3


def test_every_request_is_checked_against_the_live_site_rule():
    seen = []
    run_scan(seen=seen)
    assert seen and not any(site.LIVE in u or "brightwave.example" in re.sub(r"^http://127.0.0.1:9", "", u) for u in seen)   # links to the live host are read on the preview
    with pytest.raises(SystemExit) as e:                                                                              # the live host itself is refused
        brand_scan.scan(site.LIVE, CFG, fetch=lambda u: pytest.fail("a request went out"), today="2026-11-26")
    assert "REFUSED" in str(e.value) and "--base" in str(e.value)


def test_the_fetcher_does_not_follow_a_redirect_to_the_live_host():
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(302)
            self.send_header("Location", site.LIVE + "/x")
            self.end_headers()

        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        status, body = brand_scan.HttpFetcher(CFG, delay=0)(f"http://127.0.0.1:{srv.server_address[1]}/")
    finally:
        srv.shutdown()
    assert status == 302 and body == ""


# ---- the command -------------------------------------------------------------------------------------------------------
@pytest.fixture
def preview():
    pages = site.pages()

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            status, body = pages.get(self.path.split("?")[0], (404, ""))
            data = body.encode()
            self.send_response(status)
            self.send_header("Content-Type", "text/plain" if self.path.endswith((".txt", ".xml")) else "text/html")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def project(demo_project, rule="no-crawl"):
    cfg = json.loads((demo_project / "growth.json").read_text())
    cfg.update(site_url=site.LIVE, sitemap_url=site.LIVE + "/sitemap.xml", live_site_rule=rule)
    (demo_project / "growth.json").write_text(json.dumps(cfg))
    return demo_project


def growth(proj, *args):
    env = {**os.environ, "GROWTH_PROJECT": str(proj), "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run([sys.executable, str(ROOT / "growth"), "brand-scan", *args], capture_output=True, text=True, env=env, cwd=proj, timeout=120)


def test_a_no_crawl_project_refuses_the_live_host_in_plain_words(demo_project):
    proj = project(demo_project)
    r = growth(proj)
    assert r.returncode != 0 and "REFUSED" in (r.stdout + r.stderr) and "--base" in (r.stdout + r.stderr)
    assert not (proj / "docs" / "brand-scan.json").exists()


def test_the_command_writes_the_scan_and_the_draft_and_leaves_brand_md_alone(demo_project, preview):
    proj = project(demo_project)
    (proj / "BRAND.md").write_text("# Brand\n\nMine, untouched.\n")
    r = growth(proj, "--base", preview, "--delay", "0")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "Legal name: Brightwave Studio Pvt. Ltd." in r.stdout and "support@brightwave.example (support)" in r.stdout
    assert "Main call to action: \"Book a demo\"" in r.stdout and "BRAND.md was not changed" in r.stdout
    scan = json.loads((proj / "docs" / "brand-scan.json").read_text())
    assert scan["base"] == preview and scan["findings"]["emails"] and scan["read_on"] and scan["company_domain"] == "brightwave.example"
    md = (proj / "docs" / "brand-scan.md").read_text()
    assert "## 1a. Company and contact facts" in md and "## 4. How people buy" in md
    assert "| Legal name | Brightwave Studio Pvt. Ltd. |" in md and "`/legal/terms-of-service`" in md and "Email, support | `support@brightwave.example` | `/contact`" in md
    assert (proj / "BRAND.md").read_text() == "# Brand\n\nMine, untouched.\n"


def test_the_command_is_listed_and_documented():
    r = subprocess.run([sys.executable, str(ROOT / "growth"), "help", "--all"], capture_output=True, text=True, env={**os.environ, "GROWTH_PROJECT": ""})
    assert re.search(r"^\s+brand-scan\s", r.stdout, re.M)
    r = subprocess.run([sys.executable, str(ROOT / "kit" / "tools" / "brand_scan.py"), "--help"], capture_output=True, text=True, env={**os.environ, "GROWTH_PROJECT": ""})
    assert "--base" in r.stdout and "--max-pages" in r.stdout


# ---- doctor A2 ---------------------------------------------------------------------------------------------------------
def a2(project_dir):
    r = subprocess.run([sys.executable, str(ROOT / "kit" / "tools" / "doctor.py")], capture_output=True, text=True, cwd=project_dir,
                       env={**os.environ, "GROWTH_PROJECT": str(project_dir)})
    return next(l for l in r.stdout.splitlines() if "A2 Project adapted" in l)


def write_scan(proj, emails=("support@brightwave.example",), booking=("https://calendly.com/brightwave/intro-call",)):
    (proj / "docs").mkdir(exist_ok=True)
    scan = {"read_on": "2026-11-26", "findings": {"emails": [{"email": e, "group": "company"} for e in emails] + [{"email": "x@partner-news.example", "group": "other"}],
                                                  "booking_links": [{"url": b, "provider": "Calendly"} for b in booking]}}
    (proj / "docs" / "brand-scan.json").write_text(json.dumps(scan))


def test_doctor_without_a_scan_is_unchanged(demo_project):
    line = a2(demo_project)
    assert line.startswith("OK") and "brand scan" not in line


def test_doctor_keeps_a2_open_until_brand_md_names_what_the_scan_found(demo_project):
    write_scan(demo_project)
    (demo_project / "BRAND.md").write_text("# Brand\n\nNothing about contacts yet.\n")
    line = a2(demo_project)
    assert line.startswith("TODO") and "does not name 2 of 2 facts" in line and "support@brightwave.example" in line and "calendly.com/brightwave/intro-call" in line
    (demo_project / "BRAND.md").write_text("# Brand\n\n| Email, support | support@brightwave.example | /contact |\n| Booking link | https://www.calendly.com/brightwave/intro-call?x=1 | /book |\n")
    line = a2(demo_project)
    assert line.startswith("OK") and "BRAND.md names the 2 company emails and booking links" in line      # the partner's address is not the company's


def test_a_line_that_says_why_a_fact_is_left_out_counts(demo_project):
    write_scan(demo_project)
    (demo_project / "BRAND.md").write_text("Not used (old address): support@brightwave.example\nNo booking: calendly.com/brightwave/intro-call is a retired page.\n")
    assert a2(demo_project).startswith("OK")


def test_doctor_never_crashes_on_a_broken_scan_or_a_missing_brand_md(demo_project):
    (demo_project / "docs").mkdir(exist_ok=True)
    (demo_project / "docs" / "brand-scan.json").write_text("{not json")
    assert a2(demo_project).startswith("OK")
    (demo_project / "docs" / "brand-scan.json").write_text('["a list"]')
    assert a2(demo_project).startswith("OK")
    write_scan(demo_project)
    (demo_project / "BRAND.md").unlink(missing_ok=True)
    assert a2(demo_project).startswith("TODO")


def test_a_brand_failure_never_hides_an_old_brand_failure(demo_project):
    cfg = json.loads((demo_project / "growth.json").read_text())
    cfg["old_brand_words"] = "oldbrandxyz"
    (demo_project / "growth.json").write_text(json.dumps(cfg))
    (demo_project / "docs").mkdir(exist_ok=True)
    (demo_project / "docs" / "02-site.md").write_text("Built by oldbrandxyz.\n")
    write_scan(demo_project)
    assert a2(demo_project).startswith("FAIL")


# ---- template, onboarding skill, release -------------------------------------------------------------------------------
def test_the_brand_template_has_the_new_rows_and_keeps_the_numbers():
    t = (ROOT / "templates" / "project" / "BRAND.md").read_text()
    heads = re.findall(r"^## (\d+a?)\.", t, re.M)
    assert heads == ["1", "1a", "2", "3", "4", "5", "6", "7", "8", "8a", "9", "10"]
    sec = t[t.index("## 1a."):t.index("## 2.")]
    for field in ["Legal name", "Governing law", "Email, support", "Email, privacy", "Phone numbers", "Booking link", "Social profiles", "Terms of service last updated",
                  "Privacy policy last updated"]:
        assert field in sec
    assert "| Field | Wording | Source |" in sec
    s4 = t[t.index("## 4."):t.index("## 5.")]
    assert "| Booking link |" in s4 and "| Other CTA wordings found on the site |" in s4


def test_the_onboard_skill_runs_the_scan_in_a1_a2_and_the_drift_check():
    s = (ROOT / "kit" / "skills" / "onboard" / "SKILL.md").read_text()
    a1 = next(l for l in s.splitlines() if l.startswith("| A1 "))
    a2_ = next(l for l in s.splitlines() if l.startswith("| A2 "))
    assert "growth brand-scan" in a1 and "llms-full.txt" in a1 and "terms" in a1 and "contact" in a1
    assert "section 1a" in a2_ and "two different values" in a2_
    assert "Re-run `growth brand-scan`" in s


def test_release_3_0_2():
    log = (ROOT / "CHANGELOG.md").read_text()
    assert re.search(r"^## 3\.0\.2 - 2026-11-26$", log, re.M) and "brand-scan" in log.split("## 3.0.1")[0]
