"""Sitemap, robots, llms.txt, feeds, icons (MAP), hreflang (INT), the static build (BLD)."""
from __future__ import annotations

import os
import re
import sys
import urllib.parse
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

from .dom import find_all, parse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sitemaps  # noqa: E402  (the kit's one sitemap reader)

NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
ISO_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}")


def read_sitemap(p):
    r = p.f.get(p.origin + "/sitemap.xml")
    if r.status != 200:
        return r, []
    try:
        root = ET.fromstring(r.body)
    except ET.ParseError:
        return r, None
    if root.tag == NS + "sitemapindex":
        # an index: read each child sitemap from the same origin as this check (a preview reads its own build's files)
        def get(u):
            c = p.f.get(p.origin + (urllib.parse.urlsplit(u).path or "/"))
            return c.status, c.text() if c.status == 200 else ""
        try:
            return r, [(loc, lm or "") for loc, lm in sitemaps.read(p.origin + "/sitemap.xml", get=get)]
        except sitemaps.SitemapError:
            return r, None
    out = []
    for u in root.iter(NS + "url"):
        loc = u.find(NS + "loc")
        lm = u.find(NS + "lastmod")
        out.append((loc.text.strip() if loc is not None and loc.text else "", lm.text.strip() if lm is not None and lm.text else ""))
    return r, out


def run_map(p, site_scan=False, max_scan=100):
    rep = p.rep
    r, entries = read_sitemap(p)
    if r.status != 200:
        rep.fail("MAP-01", f"/sitemap.xml answers {r.status or r.error}", "serve a sitemap at /sitemap.xml")
        return
    if entries is None:
        rep.fail("MAP-01", "/sitemap.xml is not valid XML", "fix the generator")
        return
    ct = r.h("content-type")
    (rep.ok if "xml" in ct else rep.warn)("MAP-01", f"sitemap.xml is valid XML, {len(entries)} URLs ({ct})", "serve application/xml")
    locs = [e[0] for e in entries]
    c = (p.canonicals() or [None])[0]
    cu = c.get("href").rstrip("/") if c else ""
    robots_noindex = any("noindex" in (m.get("content").lower()) for m in find_all(p.root, "meta") if m.get("name").lower() == "robots")
    inmap = cu in {l.rstrip("/") for l in locs}
    if inmap and not (robots_noindex and p.live):
        rep.ok("MAP-02", "this page's canonical is listed in the sitemap")
    elif inmap:
        rep.fail("MAP-02", "page is noindex but listed in the sitemap", "list only indexable pages")
    elif robots_noindex:
        rep.ok("MAP-02", "noindex page is not in the sitemap")
    else:
        rep.fail("MAP-02", f"indexable page {cu} is not in the sitemap", "add it to the sitemap")
    bad = []
    parsed = [urllib.parse.urlsplit(l) for l in locs]
    if any(x.scheme != "https" for x in parsed):
        bad.append("non-https URL")
    if any(x.netloc.lower() != p.site_host for x in parsed):
        bad.append("wrong host")
    if len(set(locs)) != len(locs):
        bad.append("duplicate URLs")
    if any(x.query for x in parsed) or any(re.search(r"\.(md|json|xml)$", x.path) for x in parsed):
        bad.append("query, .md or .json URL")
    if len(locs) > 50000:
        bad.append("over 50,000 URLs")
    (rep.fail if bad else rep.ok)("MAP-03", "; ".join(bad) if bad else f"all {len(locs)} sitemap URLs are absolute https on {p.site_host}, unique, clean", "fix the sitemap")
    lm = [e[1] for e in entries if e[1]]
    mine = next((e[1] for e in entries if e[0].rstrip("/") == cu), None)
    if not mine:
        rep.warn("MAP-05", "this page has no lastmod in the sitemap", "set lastModified (the day the page really changed)")
    elif not ISO_DAY.match(mine):
        rep.fail("MAP-05", f"lastmod '{mine}' is not a date", "use ISO 8601")
    elif len(set(lm)) == 1 and len(lm) > 5:
        rep.warn("MAP-05", f"every lastmod is {lm[0]}: Google learns to ignore it", "set it per page from the real change date")
    else:
        rep.ok("MAP-05", f"lastmod {mine} (priority and changefreq are ignored by Google; do not tune them)")
    rep.info("MAP-14", f"{len(locs)} URLs in the sitemap (compare before and after a change; 78 on 17 Nov 2026 per rule 87)")
    # llms.txt
    ll = p.f.get(p.origin + "/llms.txt")
    if ll.status == 200:
        t = ll.text()
        (rep.ok if t.lstrip().startswith("# ") else rep.warn)("MAP-08", f"llms.txt exists ({len(t)} bytes)" + ("" if t.lstrip().startswith("# ") else "; it should start with '# Site name' then a '>' summary"), "follow the llms.txt layout")
    else:
        rep.info("MAP-08", "no /llms.txt (open owner question: decide if we want one; it is not a ranking factor)")
    # RSS, icons
    for l in find_all(p.root, "link"):
        if l.get("type") == "application/rss+xml":
            if p.f.allow_live:
                rep.skip("MAP-10", "live: feed not fetched")
            else:
                f = p.f.get(l.get("href"))
                (rep.ok if f.status == 200 else rep.warn)("MAP-10", f"RSS feed link answers {f.status}", "fix or remove the feed link")
            break
    icons = [l for l in find_all(p.root, "link") if "icon" in l.get("rel")]
    if icons and not p.f.allow_live:
        bad = [i.get("href") for i in icons if p.f.head_or_get(p.abs(i.get("href"))).status != 200]
        (rep.fail if bad else rep.ok)("MAP-11", f"icon file(s) not found: {bad}" if bad else f"{len(icons)} icon link(s) all answer 200", "add the icon files")
    elif not icons:
        rep.warn("MAP-11", "no icon links", "add favicon and apple-touch-icon")
    if site_scan:
        scan(p, locs[:max_scan])
    else:
        rep.skip("TTL-04", "title/description uniqueness across the site needs --site-scan (fetches every sitemap page from the local server)")


def scan(p, locs):
    rep = p.rep
    def get(u):
        return u, p.f.get(u)
    with ThreadPoolExecutor(max_workers=2) as ex:
        res = list(ex.map(get, locs))
    titles, descs, bad = {}, {}, []
    for u, r in res:
        if r.status != 200:
            bad.append(f"{urllib.parse.urlsplit(u).path} -> {r.status or r.error[:20]}")
            continue
        root = parse(r.text())
        t = next((n.all_text() for n in find_all(root, "title")), "")
        d = next((m.get("content") for m in find_all(root, "meta") if m.get("name") == "description"), "")
        titles.setdefault(t.lower(), []).append(u)
        descs.setdefault(d.lower(), []).append(u)
    dt = {k: v for k, v in titles.items() if len(v) > 1 and k}
    dd = {k: v for k, v in descs.items() if len(v) > 1 and k}
    (rep.fail if bad else rep.ok)("MAP-04", f"{len(bad)} sitemap URL(s) not 200: {bad[:3]}" if bad else f"all {len(res)} sitemap URLs answer 200", "remove or fix the URL")
    (rep.warn if dt or dd else rep.ok)("TTL-04", f"duplicate titles: {len(dt)}, duplicate descriptions: {len(dd)}" + (f" (e.g. {list(dt.values())[0][:2]})" if dt else "") if dt or dd else
                                       f"titles and descriptions are unique across {len(res)} pages", "each page gets its own title and description")


def run_intl(p):
    rep = p.rep
    alts = [l for l in find_all(p.root, "link") if l.get("rel") == "alternate" and l.get("hreflang")]
    if not alts:
        rep.ok("INT-01", "no hreflang: right for a one-language site (adding a single hreflang would be wrong)")
        return
    codes = [a.get("hreflang") for a in alts]
    bad = [c for c in codes if not re.fullmatch(r"x-default|[a-z]{2,3}(-[A-Za-z]{2,4})?", c)]
    selfref = any(urllib.parse.urlsplit(a.get("href")).path.rstrip("/") == p.path.rstrip("/") for a in alts)
    probs = ([f"bad codes {bad}"] if bad else []) + ([] if selfref else ["no self-reference"]) + ([] if "x-default" in codes else ["no x-default"])
    (rep.warn if probs else rep.ok)("INT-01", f"hreflang {codes}: " + ("; ".join(probs) or "valid"), "hreflang must be reciprocal, absolute, with a self entry")


def run_js(p):
    rep = p.rep
    # JSR-01 / JSR-05: where do the metadata tags live in the served HTML?
    tags = {"title": p.title_nodes()[:1],
            "meta description": p.metas("name", "description")[:1],
            "canonical": p.canonicals()[:1],
            "og:title": p.metas("property", "og:title")[:1]}
    absent = [k for k, v in tags.items() if not v]
    in_body = [k for k, v in tags.items() if v and not v[0].in_tag("head")]
    if absent:
        rep.fail("JSR-01", f"not in the raw HTML at all: {absent}", "crawlers that do not run JavaScript cannot see them")
    else:
        rep.ok("JSR-01", "title, description, canonical and og:title are all in the raw HTML (no JavaScript needed to read them)")
    if in_body and p.live:
        rep.fail("JSR-05", f"served in <body> instead of <head> in production mode: {in_body}", "write the metadata tags into <head> in the served HTML (static metadata)")
    elif in_body:
        rep.warn("JSR-05", f"{', '.join(in_body)} are streamed into <body> (a script moves them to <head>). This is how Next's dev server streams metadata",
                 "re-run with --mode prod on a production build, and with --ua facebookexternalhit; they must be in <head> there")
    else:
        rep.ok("JSR-05", "metadata is inside <head> in the raw HTML")
    # JSR-02 main copy in raw HTML
    h1 = [h for h in p.headings() if h.tag == "h1"]
    w = p.words()
    (rep.ok if h1 and w >= 300 else rep.fail)("JSR-02", f"raw HTML holds the H1 and {w} words of main copy" if h1 and w >= 300 else f"raw HTML has {w} words and {len(h1)} H1: content depends on JavaScript",
                                              "render the copy on the server")
    # content hidden until JS swaps it in (Next streaming)
    swaps = [d for d in find_all(p.root, "div") if d.get("id", "").startswith("S:") and "hidden" in d.attrs]
    sw = sum(len(d.all_text().split()) for d in swaps)
    (rep.warn if sw > 150 else rep.ok)("JSR-06", f"{sw} words sit in hidden streaming containers that need JavaScript to appear" if sw > 150 else "no large copy waits for JavaScript to be shown",
                                       "static pages should not stream; check on a production build")
    # JSR-03 links that are not links; JSR-10 images set by JS
    fake = [n for n in p.root.iter() if n.get("role") == "link" and n.tag != "a"]
    onclick = [n for n in p.root.iter() if n.tag in ("div", "span", "li") and n.get("onclick")]
    (rep.warn if fake or onclick else rep.ok)("JSR-03", f"{len(fake) + len(onclick)} element(s) act as links without <a href>" if fake or onclick else "navigation uses real <a href> links", "use <a href> so crawlers can follow")
    nosrc = [i for i in p.imgs() if not i.get("src") and i.get("data-src")]
    (rep.warn if nosrc else rep.ok)("JSR-10", f"{len(nosrc)} image(s) have only data-src (filled by JavaScript)" if nosrc else "images carry a real src in the HTML", "put the real src in the HTML")


def run_build(p, build_dir):
    """Checks on the built static HTML (no server). build_dir = the .next folder or an export folder."""
    rep = p.rep
    slug = p.path.strip("/") or "index"
    cands = [f"server/app/{slug}.html", f"{slug}.html", f"{slug}/index.html", f"app/{slug}.html", f"server/pages/{slug}.html"]
    path = next((os.path.join(build_dir, c) for c in cands if os.path.isfile(os.path.join(build_dir, c))), None)
    if not path:
        rep.skip("BLD-01", f"no built HTML for {p.path} under {build_dir} (page may be server-rendered, or the build is not there)")
        return
    html = open(path, encoding="utf-8", errors="replace").read()
    size = len(html.encode())
    rep.info("BLD-01", f"built page {path} = {size:,} bytes")
    root = parse(html)
    head = next(iter(find_all(root, "head")), None)
    need = {"title": find_all(root, "title"), "description": [m for m in find_all(root, "meta") if m.get("name") == "description"],
            "canonical": [l for l in find_all(root, "link") if l.get("rel") == "canonical"],
            "robots": [m for m in find_all(root, "meta") if m.get("name") == "robots"],
            "og:image": [m for m in find_all(root, "meta") if m.get("property") == "og:image"]}
    outside = [k for k, v in need.items() if v and not v[0].in_tag("head")]
    missing = [k for k in ("title", "description", "canonical", "og:image") if not need[k]]
    (rep.fail if outside or missing else rep.ok)("BLD-02", f"built HTML: missing {missing}, outside <head> {outside}" if outside or missing else "built HTML has title, description, canonical, og:image inside <head>", "fix the page metadata")
    noidx = any("noindex" in m.get("content").lower() for m in need["robots"])
    (rep.fail if noidx else rep.ok)("BLD-03", "built page is noindex (is the production switch set for this build?)" if noidx else "built page is indexable", "build the production version of the site (the preview/noindex switch off)")
    (rep.warn if size > 250_000 else rep.ok)("BLD-04", f"built HTML is {size:,} bytes unpacked", "keep under about 250 KB")
