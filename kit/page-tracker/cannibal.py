"""Cannibalization check: Google searches where two or more of our pages are shown (Search Console, through Skald,
latest snapshot per page). Read-only.

  python3 cannibal.py                       # every shared search on the site, biggest first
  python3 cannibal.py /lawn-care/blog/best-mowing-height   # only searches this page shares

For each shared search: each of our pages with its impressions, clicks and average position; the page Google prefers
(most impressions) first. A page that should own a search but loses it is the cannibalization to fix (a clearer title
and H1, one page answering, the other linking to it).
"""
import os, sqlite3, sys
from collections import defaultdict

import config
HERE = config.HERE      # the project's page-tracker data folder


def shared(c, only=None, min_imp=10):
    rows = c.execute(
        "SELECT q.path, q.query, q.clicks, q.impressions, q.position FROM search_queries q "
        "JOIN (SELECT path, max(snapshot) s FROM search_queries GROUP BY path) m ON m.path=q.path AND m.s=q.snapshot "
        "WHERE q.path != '*'").fetchall()
    by = defaultdict(dict)
    for path, query, clicks, imp, pos in rows:
        key = query[5:] if query.startswith('[us] ') else query
        cur = by[key].get(path, [0, 0, 0.0])
        cur[0] += clicks or 0; cur[1] += imp or 0; cur[2] += (pos or 0) * (imp or 0)
        by[key][path] = cur
    out = []
    for query, pages in by.items():
        if len(pages) < 2 or (only and only not in pages):
            continue
        tot = sum(v[1] for v in pages.values())
        if tot < min_imp:
            continue
        ranked = sorted(([p, v[0], v[1], round(v[2] / v[1], 1) if v[1] else None] for p, v in pages.items()), key=lambda r: -r[2])
        out.append((tot, query, ranked))
    return sorted(out, reverse=True)


if __name__ == "__main__":
    only = sys.argv[1] if len(sys.argv) > 1 else None
    c = sqlite3.connect(__import__("config").DB)
    res = shared(c, only)
    if not res:
        print("No shared searches" + (f" for {only}" if only else "") + " (at 10+ impressions).")
    for tot, query, ranked in res[:60]:
        print(f"\n{query!r}  ({tot} impressions in all)")
        for p, cl, imp, pos in ranked:
            print(f"   {imp:>7} imp  {cl:>4} clicks  pos {pos}  {p}")
