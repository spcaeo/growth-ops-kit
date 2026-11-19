"""Performance signals visible in HTML and headers (PERF), mobile and accessibility basics (MOB)."""
from __future__ import annotations

import re
import urllib.parse

from .dom import find_all


def run_perf(p):
    rep = p.rep
    size = len(p.resp.body)
    # PERF-05 HTML weight
    if p.live:
        lvl = rep.fail if size > 500_000 else rep.warn if size > 250_000 else rep.ok
        lvl("PERF-05", f"HTML is {size:,} bytes unpacked ({p.resp.wire_len:,} on the wire)", "keep HTML under about 250 KB: trim inline SVG and repeated markup")
    else:
        rep.info("PERF-05", f"HTML is {size:,} bytes in dev (includes dev-only data). Measure the real weight on a production build (--mode prod or --build-dir)")
    head = p.head
    # PERF-06 render-blocking: stylesheets and sync scripts
    sheets = [l for l in find_all(p.root, "link") if "stylesheet" in l.get("rel") and not l.get("media") ]
    sync = [s for s in find_all(p.root, "script") if s.get("src") and "async" not in s.attrs and "defer" not in s.attrs and s.get("type") != "module" and "nomodule" not in s.attrs and s.in_tag("head")]
    msg = f"{len(sheets)} blocking stylesheet(s), {len(sync)} synchronous script(s) in <head>"
    (rep.warn if sync or len(sheets) > 3 else rep.ok)("PERF-06", msg, "defer or inline critical CSS; load scripts async/defer")
    # PERF-07 fonts
    pre_fonts = [l for l in find_all(p.root, "link") if l.get("rel") == "preload" and l.get("as") == "font"]
    hdr_fonts = len(re.findall(r"as=\"font\"", p.resp.h("link")))
    ext_font_css = [l.get("href") for l in find_all(p.root, "link") if "fonts.googleapis.com" in l.get("href")]
    n = max(len(pre_fonts), hdr_fonts)
    if ext_font_css:
        rep.warn("PERF-07", "fonts load from fonts.googleapis.com at run time", "self-host fonts (Next.js: next/font does this)")
    elif n > 3:
        rep.warn("PERF-07", f"{n} fonts preloaded", "preload at most 2 or 3 font files")
    else:
        rep.ok("PERF-07", f"fonts are self-hosted; {n} preloaded")
    # PERF-08 third parties and PERF-09 hints
    hosts = set()
    for tag, attr in (("script", "src"), ("link", "href"), ("img", "src"), ("iframe", "src")):
        for n_ in find_all(p.root, tag):
            u = n_.get(attr)
            if u.startswith("http"):
                h = urllib.parse.urlsplit(u).netloc.lower()
                if h not in (p.host, p.site_host):
                    hosts.add(h)
    hosts -= {"schema.org"}
    early_3p = [s.get("src") for s in find_all(p.root, "script") if s.get("src", "").startswith("http") and urllib.parse.urlsplit(s.get("src")).netloc not in (p.host, p.site_host) and s.in_tag("head") and "async" not in s.attrs and "defer" not in s.attrs]
    (rep.warn if early_3p else rep.ok)("PERF-08", f"third-party host(s) in the HTML: {sorted(hosts) or 'none'}" + (f"; blocking in head: {early_3p[0]}" if early_3p else ""),
                                       "load tags after the page is idle (GTM lazyOnload) and never as a blocking head script")
    pre = [l for l in find_all(p.root, "link") if l.get("rel") in ("preconnect", "dns-prefetch")]
    (rep.warn if len(pre) > 3 else rep.ok)("PERF-09", f"{len(pre)} preconnect/dns-prefetch hint(s)", "keep to the few origins that matter")
    # PERF-12 asset caching (production only)
    asset = next((s.get("src") for s in find_all(p.root, "script") if s.get("src", "").startswith("/_next/static/")), None)
    if asset and p.live:
        cc = p.f.head_or_get(p.abs(asset)).h("cache-control")
        (rep.ok if "immutable" in cc or "31536000" in cc else rep.warn)("PERF-12", f"static asset Cache-Control: {cc or 'none'}", "static files should cache for a year (immutable)")
    else:
        rep.skip("PERF-12", "asset cache headers are checked in --mode prod")
    rep.skip("PERF-01", "LCP, INP, CLS and Lighthouse need a browser and a production build (manual: see the SOP, section 8)")


def run_mobile(p):
    rep = p.rep
    vp = p.meta_content(name="viewport")
    if not vp:
        rep.fail("MOB-01", "no viewport meta tag", "add <meta name='viewport' content='width=device-width, initial-scale=1'>")
    else:
        bad = []
        if "width=device-width" not in vp.replace(" ", ""):
            bad.append("width=device-width missing")
        if re.search(r"user-scalable\s*=\s*(no|0)|maximum-scale\s*=\s*1(\.0)?\b", vp):
            bad.append("zoom is blocked")
        (rep.fail if bad else rep.ok)("MOB-01", f"viewport '{vp}'" + (": " + ", ".join(bad) if bad else ""), "use width=device-width, initial-scale=1 and never block zoom")
    # MOB-05 landmarks
    mains = find_all(p.root, "main")
    skip = [a for a in p.links() if a.get("href").startswith("#") and re.search(r"(?i)skip", a.all_text())]
    probs = []
    if len(mains) != 1:
        probs.append(f"{len(mains)} <main> landmarks")
    if not find_all(p.root, "header") and not find_all(p.root, "nav"):
        probs.append("no <header>/<nav>")
    if not find_all(p.root, "footer"):
        probs.append("no <footer>")
    if not skip:
        probs.append("no skip link")
    (rep.warn if probs else rep.ok)("MOB-05", "; ".join(probs) if probs else "one <main>, header/nav, footer and a skip link", "use the landmarks and a skip link")
    # MOB-06 form controls and buttons have names
    btn = [b for b in find_all(p.root, "button") if not (b.all_text() or b.get("aria-label") or b.get("title") or any(i.get("alt") for i in b.iter() if i.tag == "img"))]
    labels = {l.get("for") for l in find_all(p.root, "label")}
    inputs = [i for i in find_all(p.root, "input") + find_all(p.root, "textarea") + find_all(p.root, "select")
              if i.get("type") not in ("hidden", "submit", "button", "image") and not (i.get("aria-label") or i.get("aria-labelledby") or i.get("id") in labels or i.in_tag("label"))]
    (rep.warn if btn or inputs else rep.ok)("MOB-06", f"{len(btn)} nameless button(s), {len(inputs)} unlabeled form field(s)" if btn or inputs else "buttons and form fields have names",
                                            "add visible text, aria-label or a <label>")
    # MOB-04 mobile vs desktop content parity
    mobile = "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Mobile Safari/537.36"
    m = p.f.get(p.url, ua=mobile)
    if m.status == 200:
        from .dom import parse
        mr = parse(m.text())
        mw = len(re.findall(r"\b[\w'’-]+\b", (find_all(mr, "main") or [mr])[0].all_text(visible=True)))
        dw = p.words()
        mh1 = len([h for h in find_all(mr, "h1")])
        (rep.ok if abs(mw - dw) <= max(30, dw * 0.03) and mh1 == 1 else rep.warn)("MOB-04", f"mobile user agent sees {mw} words, desktop {dw}; {mh1} H1",
                                                                                 "same content and links for phones and desktops (Google indexes the mobile page)")
    rep.skip("MOB-02", "tap size, overflow at 360/390/820/1024px, contrast: manual (Playwright overflow sweep, Lighthouse)")
