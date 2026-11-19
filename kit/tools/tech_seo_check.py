#!/usr/bin/env python3
"""Technical SEO checker (read-only, standard library only).

The checks and their pass thresholds are written in
book/playbooks/technical-seo.md (same IDs: IDX-, URL-, TTL-, CNT-, LNK-, IMG-,
SCH-, SOC-, PERF-, MOB-, MAP-, INT-, JSR-, SEC-, BLD-).

Examples
  growth tech_seo_check http://127.0.0.1:3801/pricing
  growth tech_seo_check URL --mode prod --build-dir ../wt-x/.next --keyword "lawn care quote"
  growth tech_seo_check https://example.com/pricing --allow-live     # only that page + robots + sitemap

Exit code: 1 when any FAIL, else 0.
"""
import argparse
import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from techseo import c_images, c_index, c_links, c_map, c_meta, c_perf, c_schema, c_social  # noqa: E402
from techseo.net import GOOGLEBOT, UA, Fetcher  # noqa: E402
from techseo.page import Page  # noqa: E402
from techseo.report import Report  # noqa: E402

def default_old_hosts():
    try:
        from config import find_project, load_cfg
        p = find_project()
        return list(load_cfg(p).get("old_hosts") or []) if p else []
    except Exception:  # noqa: BLE001
        return []


def default_origin():
    """The project's site_url when run inside a project; otherwise a placeholder (pass --site-origin)."""
    try:
        from config import find_project, load_cfg
        p = find_project()
        return load_cfg(p).get("site_url", "https://example.com") if p else "https://example.com"
    except Exception:  # noqa: BLE001
        return "https://example.com"


UAS = {"googlebot": GOOGLEBOT,
       "facebook": "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
       "twitterbot": "Twitterbot/1.0", "linkedinbot": "LinkedInBot/1.0 (compatible; Mozilla/5.0)"}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url", help="page to check, for example http://127.0.0.1:3801/pricing")
    ap.add_argument("--mode", choices=["dev", "prod"], default="dev",
                    help="dev = local dev/preview server (noindex and Disallow are expected). prod = a production build or the live site (they are failures)")
    ap.add_argument("--build-dir", help="a production build folder (.next or export) to check the built static HTML")
    ap.add_argument("--site-origin", default=default_origin(), help="the real site address that canonical and sitemap must use (default: growth.json site_url)")
    ap.add_argument("--keyword", default="", help="main search phrase: checked in the title and H1")
    ap.add_argument("--type", choices=["money", "article", "hub", "other"], default="money", help="page type (decides expected structured data)")
    ap.add_argument("--ua", default="", help="send a bot user agent: googlebot, facebook, twitterbot, linkedinbot (or any string)")
    ap.add_argument("--old-host", action="append", default=default_old_hosts(), help="a retired host or old server address that must not appear (repeat; default: growth.json old_hosts)")
    ap.add_argument("--allow-live", action="store_true", help="allow fetching the real site: ONLY the page, robots.txt and sitemap.xml")
    ap.add_argument("--no-link-status", action="store_true", help="skip the status check of internal links")
    ap.add_argument("--max-links", type=int, default=80)
    ap.add_argument("--site-scan", action="store_true", help="fetch every sitemap page from the local server (title/description uniqueness; slow on a dev server)")
    ap.add_argument("--md", help="also write the result as a Markdown file")
    ap.add_argument("--quiet-ok", action="store_true", help="hide OK lines")
    a = ap.parse_args(argv)

    u = urllib.parse.urlsplit(a.url)
    if u.scheme not in ("http", "https"):
        ap.error("url must start with http:// or https://")
    local_origin = f"{u.scheme}://{u.netloc}"
    real = urllib.parse.urlsplit(a.site_origin).netloc.lower().removeprefix("www.")
    live_host = u.netloc.lower() in (real, "www." + real)
    if live_host and not a.allow_live:
        print("Refusing to fetch the real site without --allow-live (rule: only robots.txt, sitemap.xml and one page's HTML).", file=sys.stderr)
        return 2
    f = Fetcher(local_origin, a.site_origin, allow_live=a.allow_live, ua=UAS.get(a.ua, a.ua or UA))
    rep = Report(url=a.url, mode=a.mode)
    p = Page(f, rep, a.url, mode=a.mode, site_origin=a.site_origin, keyword=a.keyword, build_dir=a.build_dir, old_hosts=a.old_host)
    if not c_index.run_index(p):
        print(rep.to_text())
        return 1
    if p.resp.status == 200:
        c_index.run_url(p)
        c_meta.run_meta(p)
        c_meta.run_content(p)
        c_links.run_links(p, a.max_links, not a.no_link_status)
        c_images.run_images(p)
        c_schema.run_schema(p, a.type)
        c_social.run_social(p)
        c_perf.run_perf(p)
        c_perf.run_mobile(p)
        c_map.run_map(p, a.site_scan)
        c_map.run_intl(p)
        c_map.run_js(p)
        c_index.run_security(p)
        if a.build_dir:
            c_map.run_build(p, a.build_dir)
        else:
            rep.skip("BLD-01", "pass --build-dir <.next or export folder> to check the built static HTML")
    # stable order: by group then id
    rep.results.sort(key=lambda r: (r.cid.split("-")[0], r.cid))
    print(rep.to_text(show_ok=not a.quiet_ok))
    print(f"\nRequests made: {len(f.log)} (read-only GET/HEAD)")
    if a.md:
        with open(a.md, "w", encoding="utf-8") as fh:
            fh.write(rep.to_markdown() + "\n")
    return rep.exit_code()


if __name__ == "__main__":
    sys.exit(main())
