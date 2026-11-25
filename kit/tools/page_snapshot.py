#!/usr/bin/env python3
"""Snapshot ONE page before (and after) we touch it: the page's own elements + all its Search Console and
Skald data + its inventory row, and log the touch in the inventory work log (owner rules, 17 Nov 2026).

  growth page_snapshot /pricing --task T10 --action "audit start"
  growth page_snapshot /pricing --base http://127.0.0.1:4321   # read the page from a preview or local build, not live

Writes inventory/pages/<slug>/<YYYY-MM-DD>.md (readable) and .json (raw), and appends to
inventory/work-log.json. Read-only on the site and on Skald. The Skald token is read from
the keys_file in growth.json and never printed.

Search Console data = everything Skald stores for the page: totals, clicks, impressions, CTR, position per day,
every query Skald returns (its top 10 per page) with clicks/impressions/position, countries, Google and Bing,
plus the query rows the page tracker has kept. A complete query list needs direct Search Console access.
"""
import argparse
import html
import json
import re
import sqlite3
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_rule  # noqa: E402
import paths  # noqa: E402
from config import CFG, PROJECT as ROOT, SITE_URL, HOST, TZ, UA, connector_on, keys, note_missing_key  # noqa: E402

# links that count as a call to action: the conversion path, the contact path and any raw booking host
CTA_RX = "|".join(re.escape(p.strip("/")) for p in (CFG.get("conversion_path"), (CFG.get("cta") or {}).get("contact_path")) if p) or r"\Z\A"
CTA_RX += r"|calendly|neetocal|cal\.com"   # well-known booking hosts
CTA_RX += "".join("|" + re.escape(h) for h in (CFG.get("booking_hosts") or []))

INV = ROOT / "inventory"


def skald(name, args):
    if not connector_on("skald"):
        return "(the Skald connector is off: growth.json connectors.skald.on)"
    if note_missing_key("skald", "SKALD_MCP_URL", "SKALD_MCP_TOKEN"):
        return "(Skald keys missing)"
    env = keys()
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": name, "arguments": args}}).encode()
    req = urllib.request.Request(env["SKALD_MCP_URL"], data=body, headers={
        "Authorization": "Bearer " + env["SKALD_MCP_TOKEN"], "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"})
    try:
        t = urllib.request.urlopen(req, timeout=90).read().decode()
        d = json.loads(re.search(r"\{.*\}", t, re.S).group(0))
        r = d.get("result", d)
        return "\n".join(c.get("text", "") for c in r.get("content", [])) if "content" in r else json.dumps(r)
    except Exception as e:  # report, don't hide
        return f"(Skald {name} failed: {e})"


def elements(path, base=""):
    """The page's own elements, read from `base` (a preview or a local build of the live release) or the live site."""
    url = (base or SITE_URL).rstrip("/") + path
    fetch_rule.assert_may_fetch(url)         # growth.json live_site_rule: no-crawl keeps every tool off the live host
    raw = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read().decode()
    clean = lambda x: re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", x))).strip()
    body = re.search(r"<body[^>]*>(.*)</body>", raw, re.S).group(1)
    main = re.sub(r"<script.*?</script>|<style.*?</style>|<svg.*?</svg>|<nav.*?</nav>|<footer.*?</footer>|<header class=.site-header.*?</header>",
                  " ", body, flags=re.S)
    links = re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', main, re.S)
    faq = re.findall(r'"@type":"Question","name":"([^"]+)"', raw)
    imgs = re.findall(r"<img[^>]*>", main)
    return {
        "title": clean((re.search(r"<title>(.*?)</title>", raw, re.S) or [None, ""])[1]),
        "meta_description": (re.search(r'<meta name="description" content="([^"]*)"', raw) or [None, ""])[1],
        "canonical": (re.search(r'<link rel="canonical" href="([^"]*)"', raw) or [None, ""])[1],
        "h1": [clean(x) for x in re.findall(r"<h1[^>]*>(.*?)</h1>", main, re.S)],
        "outline": [f"{lvl.upper()}: {clean(t)}" for lvl, t in re.findall(r"<(h[23])[^>]*>(.*?)</h[23]>", main, re.S)],
        "words": len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'’-]*", clean(main))),
        "schema_types": sorted(set(re.findall(r'"@type":"([A-Za-z]+)"', raw)) - {"Question", "Answer", "ListItem"}),
        "faq_questions": faq,
        "cta_links": sorted({h for h, _ in links if re.search(CTA_RX, h)}),
        "internal_links_out": sorted({h for h, _ in links if h.startswith("/") and not h.startswith("/#")}),
        "external_links_out": sorted({h for h, _ in links if h.startswith("http") and HOST not in h}),
        "images": len(imgs), "images_missing_alt": sum(1 for i in imgs if not re.search(r'alt="[^"]+"', i)),
    }


def tracker_rows(path):
    db = ROOT / "page-tracker" / "tracker.db"
    if not db.exists():
        return {}
    c = sqlite3.connect(db).cursor()
    # Each snapshot is a rolling 28-day window of Google's top queries, so snapshots overlap: adding clicks across them
    # (as this once did) counted the same click again at every sync. One window, the newest, is the page's figure.
    q = c.execute("select query,clicks,impressions,round(position,1) from search_queries where path=? and snapshot="
                  "(select max(snapshot) from search_queries where path=?) order by impressions desc", (path, path)).fetchall()
    v = c.execute("select sum(readers),sum(views),sum(search),sum(ai_asked) from daily where path=?", (path,)).fetchone()
    return {"stored_queries": [{"query": a, "clicks": b, "impressions": i, "position": p} for a, b, i, p in q],
            "skald_daily_totals": dict(zip(["visitors", "views", "from_search", "ai_asked"], v or []))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--task", default="")
    ap.add_argument("--action", default="snapshot")
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--base", default="", help="read the page from this address (a preview or a local build) instead of the live site")
    a = ap.parse_args()
    key = a.path.rstrip("/") or "/"   # one form for matching; the site's own form comes from its inventory row
    today = date.today()
    frm = (today - timedelta(days=a.days)).isoformat()
    if not (INV / "inventory.json").is_file():
        raise SystemExit("No page list yet. Run growth inventory first (on a site being rebuilt: growth inventory --no-pages, "
                         "which reads only the sitemap).")
    inv = json.loads((INV / "inventory.json").read_text())["pages"]
    row = next((r for r in inv if (r["path"].rstrip("/") or "/") == key and r["status"] == "live"), None)
    if not row:
        raise SystemExit(f"{a.path} is not a live page in the inventory. Run growth inventory first.")
    path = row["path"]   # the address as the site serves it (with its trailing slash, if the site uses one)
    snap = {
        "path": path, "taken": datetime.now(TZ).strftime("%Y-%m-%d %H:%M %Z"), "task": a.task, "action": a.action,
        "base": a.base or SITE_URL,
        "inventory": row,
        "elements": elements(path, a.base),
        "search_console_google": skald("search_performance", {"path": path, "from": frm, "to": today.isoformat()}),
        "search_console_google_28d": skald("search_performance", {"path": path}),
        "bing": skald("search_performance", {"path": path, "from": frm, "to": today.isoformat(), "engine": "bing"}),
        "skald_page_story": skald("page_story", {"path": path}),
        "skald_journeys": skald("page_journeys", {"paths": [path]}),
        "skald_marked_changes": skald("page_changes", {"path": path}),
        **tracker_rows(key),
    }
    slug = paths.snapshot_slug(key)
    out = INV / "pages" / slug
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{today}.json").write_text(json.dumps(snap, indent=1, ensure_ascii=False) + "\n")
    e = snap["elements"]
    md = [f"# Page snapshot: {path}", "", f"Taken {snap['taken']} · task {a.task or '-'} · {a.action}", "",
          "## Where it sits (inventory)", "",
          f"Silo **{row['silo']}** · type **{row['type']}** · pillar `{row['pillar'] or '-'}` · stage **{row['stage']}** · "
          f"links in {row.get('links_in')} / out {row.get('links_out')} {row.get('link_flags') or ''}", "",
          f"## Page elements (read from {snap['base']})", "", f"- Title: {e['title']}", f"- Meta description: {e['meta_description']}",
          f"- Canonical: {e['canonical']}", f"- H1: {' | '.join(e['h1'])}", f"- Words: {e['words']}",
          f"- Schema: {', '.join(e['schema_types'])}", f"- FAQs ({len(e['faq_questions'])}): " + "; ".join(e['faq_questions']),
          f"- Calls to action: {', '.join(e['cta_links'])}",
          f"- Internal links out ({len(e['internal_links_out'])}), external ({len(e['external_links_out'])})",
          f"- Images {e['images']}, missing alt {e['images_missing_alt']}", "", "Outline:", ""]
    md += [f"- {h}" for h in e["outline"]]
    md += ["", f"## Search Console, Google, last {a.days} days", "", "```", snap["search_console_google"], "```",
           "", "## Search Console, Google, last 28 days", "", "```", snap["search_console_google_28d"], "```",
           "", "## Bing", "", "```", snap["bing"], "```",
           "", "## Skald: page story (crawlers, AI, first visits, time on page)", "", "```", snap["skald_page_story"], "```",
           "", "## Skald: how visitors arrive and where they go", "", "```", snap["skald_journeys"], "```",
           "", "## Skald: marked changes", "", "```", snap["skald_marked_changes"], "```",
           "", "## Queries kept by the page tracker", ""]
    md += [f"- {q['query']}: {q['impressions']} impressions, {q['clicks']} clicks, position {q['position']}"
           for q in snap.get("stored_queries", [])] or ["- none stored"]
    (out / f"{today}.md").write_text("\n".join(md) + "\n")
    log = INV / "work-log.json"
    entries = json.loads(log.read_text()) if log.exists() else []
    entries.append({"path": path, "at": snap["taken"], "task": a.task, "action": a.action,
                    "snapshot": f"inventory/pages/{slug}/{today}.md"})
    log.write_text(json.dumps(entries, indent=1, ensure_ascii=False) + "\n")
    print(f"Snapshot: inventory/pages/{slug}/{today}.md")


if __name__ == "__main__":
    main()
