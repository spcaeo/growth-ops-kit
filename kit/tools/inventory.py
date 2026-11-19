#!/usr/bin/env python3
"""Full page inventory for the site in growth.json: every URL in the sitemap, its section, type, buyer stage, size and
what it says (title, description, H1), plus Search Console numbers when the page tracker has them.

  growth inventory                  # reads the live sitemap and each page; writes inventory/inventory.{json,csv} + INVENTORY.md
  growth inventory --base <url>     # read the pages from another address (a preview or a local server)
  growth inventory --offline FILE   # read a saved sitemap.xml file instead of the network (used by the tests)

Works on any site: it reads the sitemap and each page's HTML. Nothing about the site's code is needed. A page's section
(silo) is the first folder of its address when growth.json "silos" names it ({"lawn-care": "Lawn care"}); core pages come
from growth.json "core_pages"; money pages are growth.json "money_core" plus every silo's top page. Output goes to the
project's inventory/ folder. Read-only on the site.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sqlite3
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sitemaps  # noqa: E402
import fetch_rule  # noqa: E402
from config import CFG, PROJECT as ROOT, SITE_URL, TZ, UA  # noqa: E402

OUT = ROOT / "inventory"
SILOS = CFG.get("silos", {})                                  # {slug: label}
def key(path):
    """One form of a site path for matching: no trailing slash, "/" for the home page. The sitemap may say /x/ while the
    page tracker and growth.json say /x; every lookup goes through this."""
    return path.rstrip("/") or "/"


MONEY_CORE = {key(p) for p in CFG.get("money_core", [])}                  # money pages = these + every silo's top page
CORE = {key(k): tuple(v) for k, v in CFG.get("core_pages", {}).items()}   # {path: [type, buyer stage]}
BLOG = CFG.get("blog_path", "/blog").rstrip("/")
NEW_PAGES = {key(p) for p in CFG.get("new_pages", [])}
GSC_NONE = "none yet (no Search Console rows in page-tracker/tracker.db: run `growth page-tracker sync`, then this again)"


def now():
    return datetime.now(TZ).strftime("%Y-%m-%d %H:%M %Z")


def paths_of(entries, site_url: str):
    """{path: lastmod} from the sitemap's (loc, lastmod) entries."""
    return {u.strip().replace(site_url, "", 1) or "/": lm for u, lm in entries}


def fetch(url):
    fetch_rule.assert_may_fetch(url)   # never the live host when live_site_rule is no-crawl
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:  # noqa: BLE001
        return 0, ""


def page_facts(doc):
    """Title, description, H1, word count, structured-data types and FAQ count of one page's HTML."""
    if not doc:
        return {}
    title = re.search(r"<title>(.*?)</title>", doc, re.S)
    desc = re.search(r'<meta[^>]+name="description"[^>]+content="([^"]*)"', doc) or \
        re.search(r'<meta[^>]+content="([^"]*)"[^>]+name="description"', doc)
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", doc, re.S)
    body = re.search(r"<body[^>]*>(.*)</body>", doc, re.S)
    text = re.sub(r"<script.*?</script>|<style.*?</style>|<svg.*?</svg>|<nav.*?</nav>|<footer.*?</footer>|<header.*?</header>",
                  " ", body.group(1) if body else doc, flags=re.S)
    words = len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'’-]*", html.unescape(re.sub(r"<[^>]+>", " ", text))))
    types = sorted(set(re.findall(r'"@type"\s*:\s*"([A-Za-z]+)"', doc)))
    clean = lambda x: html.unescape(re.sub(r"<[^>]+>", "", x)).strip() if x else ""  # noqa: E731
    return {"title": clean(title.group(1) if title else ""), "meta_description": html.unescape(desc.group(1)) if desc else "",
            "h1": re.sub(r"\s+", " ", clean(h1.group(1) if h1 else "")), "words": words,
            "noindex": bool(re.search(r'<meta[^>]+name="robots"[^>]+noindex', doc)),
            "faqs": len(re.findall(r'"@type"\s*:\s*"Question"', doc)),
            "schema": ",".join(t for t in types if t not in {"Question", "Answer", "ListItem"})}


def classify(path):
    """(silo label, pillar path, type, buyer stage) from the address and growth.json."""
    if key(path) in CORE:
        kind, st = CORE[key(path)]
        return "Core", "", kind, st
    first = path.strip("/").split("/")[0]
    if first in SILOS:
        if path.strip("/") == first:
            return SILOS[first], path, "pillar", "BOFU"
        is_post = f"{BLOG}/" in path or "/blog/" in path
        return SILOS[first], f"/{first}", "post" if is_post else "feature page", "TOFU" if is_post else "MOFU"
    if path.startswith(BLOG + "/"):
        return "No silo", "", "post", "TOFU"
    return "No silo", "", "page", "-"


def google():
    db = ROOT / "page-tracker" / "tracker.db"
    if not db.exists():
        return {}, {}, ""
    try:
        c = sqlite3.connect(f"file:{db}?mode=ro", uri=True).cursor()
        rng = c.execute("select min(day),max(day) from search where path!='*'").fetchone()
        s = {key(p): (cl, im, pos) for p, cl, im, pos in c.execute(
            "select path,sum(clicks),sum(impressions),round(sum(position*impressions)/nullif(sum(impressions),0),1) "
            "from search where path!='*' group by path")}
        r = {key(p): v for p, v in c.execute("select path,sum(readers) from daily group by path")}
        return s, r, f"{rng[0]} to {rng[1]}"
    except sqlite3.Error:
        return {}, {}, ""


def build(sm: dict, pages: dict, gsc=None, readers=None, work=None):
    """Rows for inventory.json. `pages` is {path: (status, html)} (the page as the site serves it)."""
    gsc, readers, work = gsc or {}, readers or {}, work or []
    rows = []
    for path, lastmod in sm.items():
        status, doc = pages.get(path, (0, ""))
        silo, pillar, kind, stage = classify(path)
        g = gsc.get(key(path), (0, 0, None))
        row = {"path": path, "in_sitemap": True, "lastmod": lastmod, "status": "live" if status == 200 else f"http {status}",
               "type": kind, "silo": silo, "pillar": pillar, "stage": stage,
               "gsc_clicks": g[0] or 0, "gsc_impressions": g[1] or 0, "gsc_position": g[2], "visitors": readers.get(key(path), 0),
               **page_facts(doc)}
        row["money_page"] = row["status"] == "live" and (kind == "pillar" or key(path) in MONEY_CORE)
        mine = [w for w in work if key(w["path"]) == key(path)]
        row["touched"] = f'{mine[-1]["at"]} {mine[-1]["task"]} {mine[-1]["action"]}' if mine else ""
        rows.append(row)
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="", help="read the pages from this address instead of the site's (default: growth.json site_url; refused when live_site_rule is no-crawl)")
    ap.add_argument("--offline", help="a saved sitemap.xml to read instead of the network")
    ap.add_argument("--no-pages", action="store_true", help="the sitemap only: do not fetch each page")
    a = ap.parse_args(argv)
    base = (a.base or SITE_URL).rstrip("/")
    if not a.offline:
        fetch_rule.assert_may_fetch(base + "/")
        if not a.base:
            fetch_rule.assert_may_fetch(CFG.get("sitemap_url") or base + "/sitemap.xml")
    sitemap_path = urllib.parse.urlsplit(CFG.get("sitemap_url") or "/sitemap.xml").path or "/sitemap.xml"
    if a.offline:
        source, get = a.offline, None
    elif a.base:   # a preview: its own sitemap, and every child sitemap from it too (a new page exists only there)
        source, get = base + sitemap_path, sitemaps.on_origin(base)
    else:
        source, get = CFG.get("sitemap_url") or base + sitemap_path, None
    try:
        entries = sitemaps.read(source, get=get)   # follows a sitemap index; only sitemap files are read here
    except sitemaps.SitemapError as e:
        sys.exit(f"could not read the sitemap: {e}")
    sm = paths_of(entries, SITE_URL)
    pages = {}
    if not a.no_pages:
        for p in sm:
            pages[p] = fetch(base + p)
    gsc, readers, gsc_range = google()
    work_f = OUT / "work-log.json"
    work = json.loads(work_f.read_text()) if work_f.exists() else []
    rows = build(sm, pages, gsc, readers, work)
    OUT.mkdir(exist_ok=True)
    meta = {"generated": now(), "base": base, "sitemap_source": str(source), "search_console_range": gsc_range,
            "sitemap_urls": len(sm), "rows": len(rows)}
    (OUT / "inventory.json").write_text(json.dumps({"meta": meta, "pages": rows}, indent=1, ensure_ascii=False) + "\n")
    cols = ["path", "money_page", "touched", "status", "type", "silo", "pillar", "stage", "in_sitemap", "lastmod", "words", "faqs",
            "schema", "noindex", "gsc_impressions", "gsc_clicks", "gsc_position", "visitors", "title", "h1", "meta_description"]
    with open(OUT / "inventory.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    write_md(rows, meta)
    print(f"{len(rows)} rows; sitemap {len(sm)}; written to {OUT}")
    return 0


def write_md(rows, meta):
    live = [r for r in rows if r["status"] == "live"]
    L = [f"# {SITE_URL.split('://')[-1]} page inventory", "",
         f"Generated {meta['generated']} by `growth inventory`. Pages read from {meta.get('base') or SITE_URL}; sitemap: "
         f"{meta.get('sitemap_source') or 'the site'}. Search Console: {meta['search_console_range'] or GSC_NONE} "
         "(impressions = times shown in Google). Full rows: `inventory.csv` / `inventory.json`.", "",
         "## Totals", "", "| What | Count |", "| --- | ---: |"]
    count = lambda f: sum(1 for r in rows if f(r))  # noqa: E731
    for label, f in [("Live URLs in the sitemap", lambda r: r["in_sitemap"]),
                     ("Live pages", lambda r: r["status"] == "live"),
                     ("Pages that do not answer 200", lambda r: r["status"] != "live"),
                     ("Money pages", lambda r: r.get("money_page")),
                     ("Posts (live)", lambda r: r["type"] == "post" and r["status"] == "live"),
                     ("Live pages with 0 Google impressions", lambda r: r["status"] == "live" and not r["gsc_impressions"]),
                     ("Live pages with 1+ Google click", lambda r: r["status"] == "live" and r["gsc_clicks"])]:
        L.append(f"| {label} | {count(f)} |")
    L += ["", "## Money pages (work these first)", "",
          "| Page | Type | Impressions | Clicks | Position | Words | Last touched |", "| --- | --- | ---: | ---: | ---: | ---: | --- |"]
    for r in sorted((r for r in rows if r.get("money_page")), key=lambda r: -r["gsc_impressions"]):
        L.append(f"| `{r['path']}` | {r['type']} | {r['gsc_impressions']} | {r['gsc_clicks']} | {r['gsc_position'] or '-'} | "
                 f"{r.get('words', '')} | {r.get('touched') or '-'} |")
    L += ["", "## Pages by section", "", "| Section | Pages | Words (avg) |", "| --- | ---: | ---: |"]
    for s in sorted({r["silo"] for r in live}):
        grp = [r for r in live if r["silo"] == s]
        L.append(f"| {s} | {len(grp)} | {round(sum(r.get('words') or 0 for r in grp) / len(grp))} |")
    L += ["", "## Buyer stage of live pages", "", "| Stage | Pages |", "| --- | ---: |"]
    for st in ["BOFU", "MOFU", "TOFU", "-"]:
        L.append(f"| {st} | {count(lambda r, st=st: r['status'] == 'live' and r['stage'] == st)} |")
    L += ["", "BOFU = ready to buy, MOFU = comparing options, TOFU = learning. Auto-labelled from the address.", "",
          "## Top 15 live pages by Google impressions", "", "| Page | Section | Impressions | Clicks | Position | Words |",
          "| --- | --- | ---: | ---: | ---: | ---: |"]
    for r in sorted(live, key=lambda r: -r["gsc_impressions"])[:15]:
        L.append(f"| `{r['path']}` | {r['silo']} | {r['gsc_impressions']} | {r['gsc_clicks']} | {r['gsc_position'] or '-'} | {r.get('words', '')} |")
    (OUT / "INVENTORY.md").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    sys.exit(main())
