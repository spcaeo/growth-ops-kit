"""Rule 162 (kit/tools/gatelib/c_intl.py): a site with two or more locales tells Google which copy is for whom. Small HTML fixtures:
a good 4-locale site, then one fault at a time, each with its own plain message; a one-locale site skips every check."""
import http.server
import re
import threading
from pathlib import Path

import pytest

from gatelib import CHECKS
from gatelib.core import Ctx, run_check

IDS = ["intl.lang", "intl.copies", "intl.hreflang", "intl.canonical", "intl.no-auto-redirect", "intl.sitemap"]
SITE = "https://example.com"
FOUR = [{"locale": "en-US", "primary": True}, {"locale": "en-CA"}, {"locale": "fr-CA"}, {"locale": "es-US"}]
PREFIX = {"en-US": "", "en-CA": "/en-ca", "fr-CA": "/fr-ca", "es-US": "/es-us"}
BASE = "/pricing/"


def where(loc, base=BASE):
    return PREFIX[loc] + base


def tags(base=BASE, skip=(), xdefault=True, wrong=None, relative=False, extra=""):
    out = []
    for loc in PREFIX:
        if loc in skip:
            continue
        path = (wrong or {}).get(loc, where(loc, base))
        out.append(f'<link rel="alternate" hreflang="{loc}" href="{"" if relative else SITE}{path}">')
    if xdefault:
        out.append(f'<link rel="alternate" hreflang="x-default" href="{SITE}{where("en-US", base)}">')
    return "\n".join(out) + extra


def html(loc="en-US", base=BASE, lang="auto", canonical="auto", alts=None, head="", body="<p>Hello.</p>"):
    lang = loc if lang == "auto" else lang
    canon = f"{SITE}{where(loc, base)}" if canonical == "auto" else canonical
    return (f'<!doctype html><html{f" lang={chr(34)}{lang}{chr(34)}" if lang else ""}><head><title>T</title>'
            f'{f"<link rel={chr(34)}canonical{chr(34)} href={chr(34)}{canon}{chr(34)}>" if canon else ""}'
            f'{tags(base) if alts is None else alts}{head}</head><body><main><h1>Pricing</h1>{body}</main></body></html>')


def sitemap(base=BASE, drop=(), wrong=None, bare=False):
    ns = 'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml"'
    urls = []
    for loc in PREFIX:
        links = "" if bare else "".join(f'<xhtml:link rel="alternate" hreflang="{o}" href="{SITE}{(wrong or {}).get(o, where(o, base))}"/>'
                                         for o in PREFIX if o not in drop)
        urls.append(f"<url><loc>{SITE}{where(loc, base)}</loc>{links}</url>")
    return f'<?xml version="1.0"?><urlset {ns}>{"".join(urls)}</urlset>'


def good_site():
    return {where(loc): html(loc) for loc in PREFIX} | {"/sitemap.xml": sitemap()}


def run(site, path=BASE, cfg_market=None, only=IDS, probe=None, cfg_extra=None):
    """Run the intl checks on `path` of `site` ({path: html}); returns {check id: [lines]}."""
    cfg = {"site_url": SITE, "market": cfg_market if cfg_market is not None else {"primary_country": "US", "locales": FOUR}, **(cfg_extra or {})}
    ctx = Ctx(project=Path("/nonexistent"), path=path, key="pricing", ptype="money", cfg=cfg, html=site.get(path), url="http://127.0.0.1:3999" + path, status=200)
    ctx.cache["intl_fetch"] = lambda url: (200, site[url.split("3999", 1)[1]]) if url.split("3999", 1)[1] in site else (404, "")
    ctx.cache["intl_probe"] = probe or (lambda url, lang: 200)
    out = {}
    for cid in only:
        n = len(ctx.lines)
        run_check(ctx, CHECKS[cid])
        out[cid] = ctx.lines[n:]
    return out


def levels(res, cid):
    return [ln.level for ln in res[cid]]


def text(res, cid):
    return " || ".join(f"{ln.level}: {ln.what} -> {ln.fix}" for ln in res[cid])


def test_a_good_four_locale_site_passes_every_check():
    res = run(good_site())
    assert {cid: levels(res, cid) for cid in IDS} == {cid: ["OK"] for cid in IDS}, {c: text(res, c) for c in IDS}
    assert "x-default" in res["intl.hreflang"][0].what


def test_every_copy_of_the_good_site_passes_as_its_own_page():
    site = good_site()
    for loc in PREFIX:
        res = run(site, where(loc))
        assert [lv for cid in IDS for lv in levels(res, cid)] == ["OK"] * 6, (loc, {c: text(res, c) for c in IDS})


def test_rule_162_lists_exactly_these_checks_and_each_has_a_plain_message_and_fix():
    assert all(cid in CHECKS and CHECKS[cid].rule == "162" for cid in IDS)
    assert {c for c in CHECKS if c.startswith("intl.")} == set(IDS)


# -- one fault at a time ----------------------------------------------------------------------------------------------------
def test_missing_x_default():
    site = good_site()
    site[BASE] = html("en-US", alts=tags(xdefault=False))
    res = run(site)
    assert levels(res, "intl.hreflang") == ["FAIL"] and "no x-default hreflang" in text(res, "intl.hreflang")
    assert "primary" in text(res, "intl.hreflang") or "/pricing/" in text(res, "intl.hreflang")


def test_x_default_must_be_the_primary_locales_address():
    site = good_site()
    site[BASE] = html("en-US", alts=tags().replace(f'x-default" href="{SITE}/pricing/"', f'x-default" href="{SITE}/fr-ca/pricing/"'))
    res = run(site)
    assert "x-default points at /fr-ca/pricing, not at the primary locale's address /pricing/" in text(res, "intl.hreflang")


@pytest.mark.parametrize("lang,words", [("en", '<html lang="en"> but this page is the en-US copy'), (None, "has no lang attribute"),
                                        ("fr-CA", '<html lang="fr-CA"> but this page is the en-US copy'), ("en_US", "a dash, not an underscore")])
def test_wrong_html_lang(lang, words):
    site = good_site()
    site[BASE] = html("en-US", lang=lang)
    res = run(site)
    assert levels(res, "intl.lang") == ["FAIL"] and words in text(res, "intl.lang")
    assert 'set <html lang="en-US">' in text(res, "intl.lang")


def test_lang_is_judged_against_the_folder_the_page_lives_in():
    site = good_site()
    site["/fr-ca/pricing/"] = html("fr-CA", lang="en-US")                  # an English tag on the French-Canadian copy
    res = run(site, "/fr-ca/pricing/")
    assert levels(res, "intl.lang") == ["FAIL"] and 'this page is the fr-CA copy (folder /fr-ca/)' in text(res, "intl.lang")


def test_a_copy_that_does_not_link_back_is_not_reciprocal():
    site = good_site()
    site["/fr-ca/pricing/"] = html("fr-CA", alts=tags(skip=("en-US",)))     # the French page forgot its link to the English one
    res = run(site)
    assert levels(res, "intl.hreflang") == ["FAIL"]
    assert "not reciprocal: the fr-CA copy (/fr-ca/pricing/) does not link back to this page with hreflang en-US" in text(res, "intl.hreflang")


def test_a_copy_that_links_back_to_another_page_is_not_reciprocal_either():
    site = good_site()
    site["/es-us/pricing/"] = html("es-US", alts=tags(wrong={"en-US": "/other/"}))
    res = run(site)
    assert "not reciprocal: the es-US copy" in text(res, "intl.hreflang") and "it points at /other" in text(res, "intl.hreflang")


def test_canonical_to_another_language_is_named_as_such():
    site = good_site()
    site["/fr-ca/pricing/"] = html("fr-CA", canonical=f"{SITE}/pricing/")
    res = run(site, "/fr-ca/pricing/")
    assert levels(res, "intl.canonical") == ["FAIL"]
    assert "the fr-CA page's canonical points at the en-US copy (/pricing)" in text(res, "intl.canonical") and "its own canonical" in text(res, "intl.canonical")
    site[BASE] = html("en-US", canonical=None)
    assert "has no canonical" in text(run(site), "intl.canonical")
    site[BASE] = html("en-US", canonical="/pricing/")
    assert "not an absolute address" in text(run(site), "intl.canonical")


def test_hreflang_faults_each_have_their_own_message():
    site = good_site()
    cases = [
        (tags(skip=("en-US",)), "no self-referencing hreflang"),
        (tags(skip=("fr-CA",)), "no hreflang for fr-CA, but its copy exists at /fr-ca/pricing/"),
        (tags(relative=True), "is not an absolute address"),
        (tags(wrong={"fr-CA": "/en-ca/pricing/"}), "hreflang fr-CA points at /en-ca/pricing, but the fr-CA copy of this page is /fr-ca/pricing"),
        (tags(wrong={"en-US": "/other/"}), "points at /other, not at this page"),
        (tags(extra='<link rel="alternate" hreflang="de-DE" href="https://example.com/de-de/pricing/">'), "hreflang \"de-de\" is not one of this site's locales"),
        (tags(extra='<link rel="alternate" hreflang="en_GB" href="https://example.com/x/">'), 'hreflang "en_GB" is not a language tag'),
        ("", "no hreflang tags on a page of a site with 4 locales"),
    ]
    for alts, words in cases:
        site[BASE] = html("en-US", alts=alts)
        res = run(site)
        assert "FAIL" in levels(res, "intl.hreflang") and words in text(res, "intl.hreflang"), (words, text(res, "intl.hreflang"))


def test_hreflang_on_another_host_fails():
    site = good_site()
    site[BASE] = html("en-US", alts=tags().replace(f'{SITE}/fr-ca/', "https://staging.example.net/fr-ca/"))
    assert "points at another host (staging.example.net)" in text(run(site), "intl.hreflang")


def test_a_banner_that_reads_the_language_but_never_moves_the_visitor_is_fine():
    site = good_site()
    site[BASE] = html("en-US", head='<script>var l = navigator.language || ""; if (l.startsWith("fr")) { document.getElementById("lang-banner").hidden = false; }</script>')
    res = run(site)
    assert levels(res, "intl.no-auto-redirect") == ["OK"] and "to suggest" in res["intl.no-auto-redirect"][0].what


@pytest.mark.parametrize("script", [
    'if (navigator.language.startsWith("fr")) { window.location.replace("/fr-ca/"); }',
    'var l = navigator.languages[0]; if (l == "es-US") location.href = "/es-us/";',
    'const lang = navigator.language; if (lang !== "en-US") { window.location = "/en-ca/"; }',
    'if (/fr/.test(navigator.userLanguage)) document.location.assign("/fr-ca/")',
])
def test_a_script_that_reads_the_language_and_moves_the_visitor_fails(script):
    site = good_site()
    site[BASE] = html("en-US", head=f"<script>{script}</script>")
    res = run(site)
    assert levels(res, "intl.no-auto-redirect") == ["FAIL"]
    assert "reads the browser's language" in text(res, "intl.no-auto-redirect") and "banner that suggests the other language" in text(res, "intl.no-auto-redirect")


def test_moving_the_visitor_for_another_reason_is_not_a_language_redirect():
    site = good_site()
    site[BASE] = html("en-US", head='<script>if (location.hash === "#top") { location.hash = "#start"; } window.location.href == "x"; </script>'
                                   '<script>window.location.replace("/login/")</script>')
    assert levels(run(site), "intl.no-auto-redirect") == ["OK"]


def test_a_meta_refresh_and_a_server_redirect_by_language_fail():
    site = good_site()
    site[BASE] = html("en-US", head='<meta http-equiv="refresh" content="0; url=/fr-ca/pricing/">')
    res = run(site)
    assert levels(res, "intl.no-auto-redirect") == ["FAIL"] and "a meta refresh" in text(res, "intl.no-auto-redirect")
    res = run(good_site(), probe=lambda url, lang: 302 if lang.startswith("fr-CA") else 200)
    assert levels(res, "intl.no-auto-redirect") == ["FAIL"] and "answers 302 (a redirect) when the browser asks for fr-CA" in text(res, "intl.no-auto-redirect")


def test_a_missing_copy_is_a_missing_translation_not_a_wrong_tag():
    site = good_site()
    del site["/es-us/pricing/"]
    site[BASE] = html("en-US", alts=tags(skip=("es-US",)))                  # no tag for a copy that is not written: right
    for loc in ("en-CA", "fr-CA"):
        site[where(loc)] = html(loc, alts=tags(skip=("es-US",)))
    res = run(site)
    assert levels(res, "intl.copies") == ["WARN"]
    assert "missing translation: the es-US copy of /pricing/ does not exist yet" in text(res, "intl.copies") and "/es-us/pricing/" in text(res, "intl.copies")
    assert levels(res, "intl.hreflang") == ["OK"]                            # the tags are right; only the copy is missing
    assert levels(res, "intl.lang") == ["OK"] and levels(res, "intl.canonical") == ["OK"]


def test_a_tag_to_a_copy_that_is_missing_still_says_missing_translation_and_a_project_can_make_it_a_fail():
    site = good_site()
    del site["/fr-ca/pricing/"]
    res = run(site)
    assert levels(res, "intl.copies") == ["WARN"] and "missing translation: the fr-CA copy" in text(res, "intl.copies")
    res = run(site, cfg_market={"primary_country": "US", "locales": FOUR, "missing_copy": "fail"})
    assert levels(res, "intl.copies") == ["FAIL"] and "missing translation" in text(res, "intl.copies")


def test_every_missing_copy_gets_its_own_line():
    site = {BASE: html("en-US"), "/sitemap.xml": sitemap()}
    res = run(site)
    assert levels(res, "intl.copies") == ["WARN"] * 3
    assert [m for m in re.findall(r"the (\S+) copy", text(res, "intl.copies"))] == ["en-CA", "fr-CA", "es-US"]


def test_a_copy_the_server_cannot_answer_is_could_not_read_not_missing():
    site = good_site()
    ctx = Ctx(project=Path("/nonexistent"), path=BASE, ptype="money", cfg={"site_url": SITE, "market": {"locales": FOUR}}, html=site[BASE],
              url="http://127.0.0.1:3999" + BASE, status=200)
    ctx.cache["intl_fetch"] = lambda url: (500, "")
    run_check(ctx, CHECKS["intl.copies"])
    assert [ln.level for ln in ctx.lines] == ["WARN"] * 3 and "could not read the en-CA copy" in ctx.lines[0].what


# -- the sitemap ------------------------------------------------------------------------------------------------------------
def test_the_sitemap_must_list_alternates_for_the_page():
    site = good_site()
    site["/sitemap.xml"] = sitemap(bare=True)
    res = run(site)
    assert levels(res, "intl.sitemap") == ["FAIL"] and "lists /pricing with no xhtml:link alternates" in text(res, "intl.sitemap")
    site["/sitemap.xml"] = sitemap(drop=("fr-CA", "es-US"))
    assert "lacks xhtml:link alternates for fr-CA, es-US" in text(run(site), "intl.sitemap")
    site["/sitemap.xml"] = sitemap(wrong={"fr-CA": "/en-ca/pricing/"})
    assert "the sitemap's alternate fr-CA points at /en-ca/pricing, not at /fr-ca/pricing" in text(run(site), "intl.sitemap")


def test_the_sitemap_is_skipped_when_the_build_has_none_or_does_not_list_the_page():
    site = good_site()
    del site["/sitemap.xml"]
    res = run(site)
    assert levels(res, "intl.sitemap") == ["SKIP"] and "the build has no sitemap" in res["intl.sitemap"][0].what and not res["intl.sitemap"][0].blocked
    site["/sitemap.xml"] = sitemap(base="/other/")
    assert "is not in the sitemap" in text(run(site), "intl.sitemap")


def test_a_sitemap_index_is_followed():
    site = good_site()
    inner = site["/sitemap.xml"]
    site["/sitemap.xml"] = f'<?xml version="1.0"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><sitemap><loc>{SITE}/sitemap-0.xml</loc></sitemap></sitemapindex>'
    site["/sitemap-0.xml"] = inner
    assert levels(run(site), "intl.sitemap") == ["OK"]


def test_the_sitemap_only_asks_for_alternates_of_copies_that_exist():
    site = good_site()
    del site["/es-us/pricing/"]
    site["/sitemap.xml"] = sitemap(drop=("es-US",))
    assert levels(run(site), "intl.sitemap") == ["OK"]


# -- one locale, and a bad list -------------------------------------------------------------------------------------------
def test_a_one_locale_project_skips_every_check():
    for market in ({"primary_country": "US", "language": "en-US", "google_params": "gl=us&hl=en&pws=0"}, {"locales": ["en-US"]}, {}):
        res = run(good_site(), cfg_market=market)
        for cid in IDS:
            assert levels(res, cid) == ["SKIP"] and "one locale" in res[cid][0].what and not res[cid][0].blocked, (market, cid)


def test_a_bad_locale_list_fails_with_the_fix_instead_of_guessing():
    res = run(good_site(), cfg_market={"locales": ["en-US", {"locale": "fr-CA", "prefix": "/"}]})
    assert all(levels(res, cid) == ["FAIL"] and "market.locales" in text(res, cid) for cid in IDS)


def test_static_mode_without_a_page_does_not_fail():
    ctx = Ctx(project=Path("/nonexistent"), path=BASE, ptype="money", cfg={"site_url": SITE, "market": {"locales": FOUR}}, static=True)
    for cid in IDS:
        run_check(ctx, CHECKS[cid])
    assert ctx.skipped == IDS and ctx.lines == []


# -- the real network functions, against a small local server -------------------------------------------------------------
class Handler(http.server.BaseHTTPRequestHandler):
    pages = {}
    redirect_for = ""

    def log_message(self, *a):
        pass

    def do_GET(self):
        lang = self.headers.get("Accept-Language", "")
        if self.redirect_for and self.path == BASE and lang.startswith(self.redirect_for):
            self.send_response(302)
            self.send_header("Location", "/fr-ca/pricing/")
            self.end_headers()
            return
        body = self.pages.get(self.path)
        self.send_response(200 if body is not None else 404)
        self.send_header("Content-Type", "application/xml" if self.path.endswith(".xml") else "text/html")
        self.end_headers()
        self.wfile.write((body or "").encode())


@pytest.fixture
def server():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv
    srv.shutdown()
    srv.server_close()
    Handler.redirect_for = ""


def real_run(srv, site):
    Handler.pages = site
    ctx = Ctx(project=Path("/nonexistent"), path=BASE, ptype="money", cfg={"site_url": SITE, "market": {"locales": FOUR}}, html=site[BASE],
              url=f"http://127.0.0.1:{srv.server_address[1]}{BASE}", status=200)
    for cid in IDS:
        run_check(ctx, CHECKS[cid])
    return ctx.lines


def test_the_real_fetch_reads_the_copies_the_sitemap_and_sees_a_server_redirect(server):
    lines = real_run(server, good_site())
    assert [ln.level for ln in lines] == ["OK"] * 6, [ln.text() for ln in lines]
    Handler.redirect_for = "fr-CA"
    lines = real_run(server, good_site())
    bad = [ln for ln in lines if ln.level == "FAIL"]
    assert [ln.cid for ln in bad] == ["intl.no-auto-redirect"] and "answers 302" in bad[0].what
