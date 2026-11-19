"""Crawl and index (IDX), URL and canonical (URL), delivery and security headers (SEC)."""
from __future__ import annotations

import random
import re
import urllib.parse
import urllib.robotparser

from .dom import find_all, parse

STATIC_OK = ("text/html",)


def robots_directives(p):
    """All robots-style directives from meta tags (any bot name) and the X-Robots-Tag header."""
    metas = [m for m in find_all(p.root, "meta") if m.get("name").lower() in ("robots", "googlebot", "bingbot")]
    parts = []
    for m in metas:
        parts += [x.strip().lower() for x in m.get("content").split(",") if x.strip()]
    xr = [x.strip().lower() for x in p.resp.h("x-robots-tag").split(",") if x.strip()]
    return metas, parts, xr


def run_index(p):
    rep, r = p.rep, p.resp
    # IDX-01 status and IDX-02 redirects (source: extension status panel)
    if r.error:
        rep.fail("IDX-01", f"could not fetch the page: {r.error}", "start the dev server or fix the URL")
        return False
    if r.status == 200:
        rep.ok("IDX-01", f"status 200 in {r.seconds:.2f}s")
    else:
        rep.fail("IDX-01", f"status {r.status}", "the page must answer 200 at its final address")
    if 300 <= r.status < 400:
        rep.fail("IDX-02", f"the URL redirects ({r.status}) to {r.h('location')}",
                 "test the final address; internal links must point at the final address")
    else:
        rep.ok("IDX-02", "no redirect on the tested address")
    # IDX-03, 04, 07, 08 robots meta and header
    metas, parts, xr = robots_directives(p)
    names = [m.get("name").lower() for m in metas if m.get("name").lower() == "robots"]
    noindex = "noindex" in parts or "none" in parts or "noindex" in xr
    if len(names) > 1:
        rep.warn("IDX-08", f"{len(names)} robots meta tags", "keep one robots meta; conflicting ones make the strictest win")
    else:
        rep.ok("IDX-08", "at most one robots meta tag")
    if noindex:
        if p.live:
            rep.fail("IDX-03", f"page is noindex ({', '.join(parts) or ', '.join(xr)}) in production mode",
                     "remove noindex from a page that must rank (check the site's preview or noindex switch)")
        else:
            rep.info("IDX-03", f"noindex is ON ({', '.join(parts)}). Expected on a dev or preview build; "
                     "re-run with --mode prod against a production build (preview switch off) to prove the live setting")
    else:
        rep.ok("IDX-03", "indexable: no noindex in meta or header" + ("" if parts else " (no robots meta = index, follow)"))
    if "nofollow" in parts and not noindex:
        rep.warn("IDX-07", "robots meta says nofollow", "a money page should pass link value: use index, follow")
    elif "nofollow" in parts and p.live:
        rep.fail("IDX-07", "robots meta says nofollow in production mode", "use index, follow")
    else:
        rep.ok("IDX-07", "no nofollow in robots meta")
    if xr and ("noindex" in xr) != ("noindex" in parts):
        rep.warn("IDX-04", f"X-Robots-Tag header ({', '.join(xr)}) disagrees with the meta tag",
                 "make header and meta say the same")
    else:
        rep.ok("IDX-04", "X-Robots-Tag header absent or agrees with the meta robots")
    # IDX-11 content type, IDX-12 soft 404
    ct = r.h("content-type").lower()
    if ct.startswith("text/html") and "utf-8" in ct:
        rep.ok("IDX-11", f"content-type {ct}")
    else:
        rep.warn("IDX-11", f"content-type is '{ct}'", "serve text/html; charset=utf-8")
    words = p.words()
    t = (p.title() or "").lower()
    if words < 100 or re.search(r"\b(404|not found|page removed)\b", t):
        rep.fail("IDX-12", f"looks like a soft 404 or empty page ({words} words, title '{t[:40]}')",
                 "a missing page must answer 404 or 410; a real page needs real content")
    else:
        rep.ok("IDX-12", "page has real content and a real title")
    # IDX-13 https and HSTS (prod mode only: local servers are plain http)
    if p.live:
        hsts = r.h("strict-transport-security")
        (rep.ok if "max-age" in hsts else rep.warn)("IDX-13", f"HSTS: {hsts or 'missing'}",
                                                  "send Strict-Transport-Security (most hosts do it on the live site)")
    else:
        rep.skip("IDX-13", "HSTS only checked in --mode prod on https")
    # IDX-14 compression, IDX-15 cache
    enc = r.h("content-encoding")
    if enc in ("gzip", "br"):
        rep.ok("IDX-14", f"HTML compressed ({enc}); {r.wire_len:,} bytes on the wire, {len(r.body):,} unpacked")
    elif p.live:
        rep.warn("IDX-14", "HTML is not compressed", "turn on gzip or brotli at the host")
    else:
        rep.info("IDX-14", "dev server does not compress; measure on a production build or the live host")
    cc = r.h("cache-control")
    if "no-store" in cc and p.live:
        rep.warn("IDX-15", f"Cache-Control '{cc}' on a public page", "let the CDN cache the page (s-maxage / revalidate)")
    elif "no-store" in cc:
        rep.info("IDX-15", "Cache-Control no-store: normal for the dev server only")
    else:
        rep.ok("IDX-15", f"Cache-Control: {cc or 'not set'}")
    # robots.txt (IDX-05, IDX-06)
    rb = p.f.get(p.origin + "/robots.txt")
    if rb.status == 200:
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(rb.text().splitlines())
        body = rb.text()
        blocked = not rp.can_fetch("Googlebot", p.url)
        if blocked and p.live:
            rep.fail("IDX-06", "robots.txt blocks Googlebot from this page", "remove the Disallow rule that covers it")
        elif blocked:
            rep.info("IDX-06", "robots.txt blocks everyone: expected on dev/preview, must flip in production")
        else:
            rep.ok("IDX-06", "robots.txt lets Googlebot fetch this page")
        sm = re.findall(r"(?im)^sitemap:\s*(\S+)", body)
        if sm and p.live:
            rep.ok("IDX-05", f"robots.txt is 200 and names the sitemap ({sm[0]})")
        elif sm:
            rep.ok("IDX-05", "robots.txt is 200 and names the sitemap")
        elif blocked and not p.live:
            rep.info("IDX-05", "robots.txt (preview) has no Sitemap line: expected while everything is blocked")
        else:
            rep.warn("IDX-05", "robots.txt has no Sitemap: line", f"add Sitemap: {p.site_origin}/sitemap.xml")
        res_block = [l for l in body.splitlines() if re.match(r"(?i)disallow:\s*/(_next|static|images|assets)", l.strip())]
        if res_block:
            rep.fail("MAP-06", f"robots.txt blocks site assets: {res_block[0]}", "never block CSS, JS or images that the page needs")
        else:
            rep.ok("MAP-06", "robots.txt does not block CSS, JS or images")
    else:
        rep.fail("IDX-05", f"robots.txt answers {rb.status or rb.error}", "serve /robots.txt (app/robots.ts)")
    return True


# ---------------------------------------------------------------------------------------
def norm_path(path):
    path = urllib.parse.unquote(path or "/")
    return path if path == "/" else path.rstrip("/")


def run_url(p):
    rep = p.rep
    u = urllib.parse.urlsplit(p.url)
    path = u.path
    # URL-01 shape of the address
    problems = []
    if path != path.lower():
        problems.append("capital letters")
    if "_" in path or " " in path or "%20" in path:
        problems.append("underscores or spaces")
    if u.query:
        problems.append("query string")
    if re.search(r"\.(html?|php|aspx?)$", path):
        problems.append("file extension")
    if len(p.site_origin + path) > 115:
        problems.append("longer than 115 characters")
    if problems:
        rep.warn("URL-01", "address has " + ", ".join(problems), "use lowercase words joined by hyphens, no query or extension, under 115 characters")
    else:
        rep.ok("URL-01", f"clean address {path}")
    # URL-02..06 canonical
    cans = p.canonicals()
    if not cans:
        rep.fail("URL-02", "no rel=canonical", "add <link rel=canonical> with the page's own address in <head>")
        return
    if len(cans) > 1 and len({c.get("href") for c in cans}) > 1:
        rep.fail("URL-02", f"{len(cans)} different canonicals", "keep exactly one")
    else:
        rep.ok("URL-02", "exactly one canonical" if len(cans) == 1 else "duplicate tags agree")
    c = cans[0]
    href = c.get("href")
    cu = urllib.parse.urlsplit(href)
    if cu.scheme == "https" and cu.netloc.lower() == p.site_host:
        rep.ok("URL-03", f"canonical is absolute https on the site host: {href}")
    else:
        rep.fail("URL-03", f"canonical '{href}' is not an absolute https URL on {p.site_host}",
                 f"use https://{p.site_host}{path}")
    if norm_path(cu.path) == norm_path(path) and not cu.query:
        rep.ok("URL-04", "canonical points at itself")
    else:
        rep.fail("URL-04", f"canonical path '{cu.path}' differs from the page path '{path}'",
                 "a page that should rank names itself as canonical")
    if c.in_tag("head"):
        rep.ok("URL-06", "canonical sits in <head>")
    elif p.live:
        rep.fail("URL-06", "canonical is not inside <head> in the served HTML", "the title, description and canonical must be in <head> on a production build")
    else:
        rep.warn("URL-06", "canonical is streamed into <body> (Next dev behaviour); a script moves it to <head>",
                 "confirm on a production build with --mode prod; Google renders JS, but other crawlers may not")
    # URL-05 trailing slash style: same style as the sitemap
    from .c_map import read_sitemap   # follows a sitemap index (the shared reader), same origin as this check
    try:
        locs = [loc for loc, _ in (read_sitemap(p)[1] or [])]
    except Exception:  # noqa: BLE001
        locs = []
    inner = [urllib.parse.urlsplit(x).path for x in locs if urllib.parse.urlsplit(x).path not in ("", "/")]
    if inner:
        slash = sum(1 for x in inner if x.endswith("/"))
        style_slash = slash > len(inner) / 2
        if (href.endswith("/") and cu.path != "/") == style_slash:
            rep.ok("URL-05", f"canonical trailing-slash style matches the sitemap ({'with' if style_slash else 'no'} slash)")
        else:
            rep.fail("URL-05", "canonical slash style differs from the sitemap's", "use one style everywhere")
    else:
        rep.skip("URL-05", "no sitemap entries to compare the slash style with")
    # URL-07 variants
    if path != "/":
        v = p.f.get(p.origin + path.rstrip("/") + "/")
        loc = v.h("location")
        if v.status in (301, 308) and norm_path(urllib.parse.urlsplit(loc).path) == norm_path(path):
            rep.ok("URL-07", f"trailing-slash variant redirects {v.status} to the clean address")
        elif v.status in (302, 307):
            rep.warn("URL-07", f"trailing-slash variant uses a temporary redirect ({v.status})", "use a permanent redirect (301/308)")
        elif v.status == 200:
            rep.warn("URL-07", "trailing-slash variant answers 200 (a duplicate address)", "redirect it to the canonical or set the canonical on it")
        else:
            rep.ok("URL-07", f"trailing-slash variant answers {v.status}")
    else:
        rep.skip("URL-07", "home page: no slash variant")
    # URL-09 tracking parameters
    t = p.f.get(p.url + ("&" if u.query else "?") + "utm_source=techseo&utm_medium=check")
    tc = [l for l in find_all(parse(t.text()), "link") if "canonical" in l.get("rel").lower()] if t.status == 200 else []
    if t.status == 200 and tc and urllib.parse.urlsplit(tc[0].get("href")).query == "":
        rep.ok("URL-09", "a ?utm_ variant keeps the clean canonical")
    elif t.status == 200:
        rep.fail("URL-09", "a ?utm_ variant has no clean canonical", "canonical must drop tracking parameters")
    else:
        rep.warn("URL-09", f"a ?utm_ variant answers {t.status}", "campaign links must still load the page")
    # URL-10 real 404
    junk = f"/zz-techseo-404-{random.randint(1000, 9999)}"
    n = p.f.get(p.origin + junk)
    if n.status in (404, 410):
        rep.ok("URL-10", f"an unknown address answers a real {n.status}")
    else:
        rep.fail("URL-10", f"an unknown address answers {n.status}", "unknown pages must answer 404 (or 410), never 200")
    # URL-11 old hosts in the page
    old = [x for x in ("localhost:", "127.0.0.1") if x in p.html.lower() and x not in p.origin]
    leak = [h for h in p.old_hosts if h in p.html.lower()]
    if leak:
        rep.fail("URL-11", f"page mentions a retired host: {', '.join(leak)}", "remove every old-host address (growth.json old_hosts lists them)")
    else:
        rep.ok("URL-11", "no local or retired host in the page")


def run_security(p):
    rep, r = p.rep, p.resp
    want = {"x-content-type-options": "nosniff", "referrer-policy": None, "x-frame-options": None, "permissions-policy": None}
    missing = [k for k in want if not r.h(k)]
    (rep.ok if not missing else rep.warn)("SEC-01", "baseline security headers present" if not missing else f"missing headers: {', '.join(missing)}",
                                           "add them in the server or host configuration (Next.js: headers() in next.config)")
    csp = r.h("content-security-policy") or r.h("content-security-policy-report-only")
    (rep.ok if csp else rep.info)("SEC-02", "Content-Security-Policy (or report-only) present" if csp else
                                  "no CSP yet (open item: start with Content-Security-Policy-Report-Only; every analytics, tag and booking host the page uses must be allowed)")
    mixed = re.findall(r'(?:src|href)="(http://(?!127\.0\.0\.1|localhost)[^"]+)"', p.html)
    if mixed:
        rep.fail("SEC-03", f"{len(mixed)} http:// resource(s), first: {mixed[0]}", "load everything over https")
    else:
        rep.ok("SEC-03", "no http:// (mixed content) resources")
    if r.h("x-powered-by") or re.search(r"/\d", r.h("server")):
        rep.warn("SEC-04", f"server names its software ({r.h('x-powered-by') or r.h('server')})",
                 "remove the X-Powered-By header in the server configuration (site-wide, not a page fix; Next.js: poweredByHeader: false)")
    else:
        rep.ok("SEC-04", "no software name or version in headers")
