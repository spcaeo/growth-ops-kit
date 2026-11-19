#!/usr/bin/env python3
"""Before-and-after archive of a page (rule 36i). From a real project: "for future demos I want a full copy of the page
before, stored like one full image, and keep that as a rule for all new pages: store the old vs the new that will be
live on the website, because I speak in many SEO talks and this is important for me to show."

  growth page_archive capture <path> --stage before   # the live page before any change ships
  growth page_archive capture <path> --stage after    # the live page after release
  growth page_archive list <path>                      # what is archived for a page

Each capture writes archive/pages/<slug>/<YYYY-MM-DD>-<stage>/:
  desktop-1366.png and mobile-390.png (one full-page image each), page.html (the HTML served), meta.json.

The live site is read by a headless browser with every analytics and tag request blocked (Google tag, GA4, Clarity,
Vercel insights, ad pixels), so the capture is never counted as a visit. Motion is reduced and the page is scrolled
end to end first, so every lazy and reveal-on-scroll part is drawn. The browser always closes.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402
from config import PROJECT, SITE_URL, TZ  # noqa: E402

BLOCK = re.compile(
    r"googletagmanager\.com|google-analytics\.com|analytics\.google\.com|doubleclick\.net|googleadservices\.com|"
    r"clarity\.ms|/_vercel/(insights|speed-insights)|vitals\.vercel|facebook\.(net|com)/tr|connect\.facebook|"
    r"hotjar|posthog|plausible|segment\.(io|com)|linkedin\.com/(px|li)|snap\.licdn|bat\.bing|tiktok|cal\.com/embed",
    re.I)
WIDTHS = {"desktop-1366.png": (1366, 900, False), "mobile-390.png": (390, 844, True)}


def slug_of(path):
    return paths.snapshot_slug(path)   # the one folder name per page (the same as inventory/pages/<slug>/)
    import paths
    return paths.snapshot_slug(path)


def folder(path, stage, day=None):
    day = day or dt.datetime.now(TZ).strftime("%Y-%m-%d")
    return PROJECT / "archive" / "pages" / slug_of(path) / f"{day}-{stage}"


def capture(path, stage, base):
    from playwright.sync_api import sync_playwright
    url = base.rstrip("/") + "/" + path.lstrip("/")
    out = folder(path, stage)
    out.mkdir(parents=True, exist_ok=True)
    blocked, meta = [], {"url": url, "stage": stage, "captured": dt.datetime.now(TZ).isoformat(timespec="seconds")}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for name, (w, h, mobile) in WIDTHS.items():
                ctx = browser.new_context(viewport={"width": w, "height": h}, is_mobile=mobile, has_touch=mobile,
                                          device_scale_factor=2 if mobile else 1, reduced_motion="reduce")
                ctx.route("**/*", lambda r: (blocked.append(urlparse(r.request.url).netloc), r.abort())
                          if BLOCK.search(r.request.url) else r.continue_())
                page = ctx.new_page()
                resp = page.goto(url, wait_until="domcontentloaded", timeout=60000)
                meta.setdefault("status", resp.status if resp else None)
                if resp and name.startswith("desktop"):
                    (out / "page.html").write_text(resp.text())
                    meta["headers"] = {k: v for k, v in resp.headers.items() if k in ("x-vercel-id", "age", "last-modified", "etag", "date")}
                # scroll end to end so lazy images and reveal-on-scroll folds are drawn
                total = page.evaluate("document.documentElement.scrollHeight")
                y = 0
                while y < total:
                    y += h // 2
                    page.evaluate(f"window.scrollTo(0, {y})")
                    page.wait_for_timeout(120)
                    total = page.evaluate("document.documentElement.scrollHeight")
                page.evaluate("window.scrollTo(0, 0)")
                page.wait_for_timeout(600)
                page.screenshot(path=str(out / name), full_page=True)
                if name.startswith("desktop"):
                    meta["title"] = page.title()
                    meta["h1"] = page.evaluate("document.querySelector('h1')?.innerText || ''")
                    meta["height_px"] = total
                ctx.close()
        finally:
            browser.close()
    meta["blocked_hosts"] = sorted(set(blocked))
    (out / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")
    print(f"archived {url} -> {out.relative_to(PROJECT)}")
    print(f"  {', '.join(sorted(WIDTHS))}, page.html; blocked {len(blocked)} analytics requests ({', '.join(meta['blocked_hosts']) or 'none'})")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["capture", "list"])
    ap.add_argument("path")
    ap.add_argument("--stage", choices=["before", "after"])
    ap.add_argument("--base", default=SITE_URL, help="site address (default: the live site from growth.json)")
    a = ap.parse_args()
    if a.cmd == "capture":
        if not a.stage:
            sys.exit("--stage before|after is required")
        capture(a.path, a.stage, a.base)
    else:
        d = PROJECT / "archive" / "pages" / slug_of(a.path)
        for f in sorted(d.glob("*")) if d.exists() else []:
            print(f.name, " ".join(sorted(x.name for x in f.iterdir())))


if __name__ == "__main__":
    main()
