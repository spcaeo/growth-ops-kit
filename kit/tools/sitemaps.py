"""One sitemap reader for every tool (inventory, link_graph, the page tracker).

A sitemap is either a list of pages (<urlset>) or an INDEX of other sitemaps (<sitemapindex>). An index is followed,
child by child (up to two levels), so a site whose /sitemap.xml is an index gives its pages, never its child sitemap
files as if they were pages.

  read(source)            -> [(loc, lastmod or None)], in sitemap order, no duplicates
  read(source, get=fn)    -> fn(url) returns (status, body); the default is one plain GET
  source may be a URL or a saved file. For a saved index, each child is looked up first as a file of the same name in
  the index's folder (a local build's dist/ holds them all), then fetched.

Only sitemap files are read here; no page is fetched.

  growth sitemaps <url-or-file>     # how many pages, then each address with its lastmod
"""
from __future__ import annotations

import html
import re
import urllib.error
import urllib.request
from pathlib import Path

MAX_DEPTH = 2
UA = {"User-Agent": "growth-ops-kit (sitemap reader)", "Accept": "application/xml,text/xml,*/*"}


class SitemapError(Exception):
    pass


def default_get(url: str):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:  # noqa: BLE001  (DNS, TLS, timeouts)
        return 0, ""


def parse(xml: str):
    """(is_index, [(loc, lastmod)]) of one sitemap document."""
    is_index = "<sitemapindex" in xml
    out = []
    for block in re.findall(r"<(?:url|sitemap)\b[^>]*>(.*?)</(?:url|sitemap)>", xml, flags=re.S):
        loc = re.search(r"<loc>\s*(?:<!\[CDATA\[)?\s*([^<\]]+?)\s*(?:\]\]>)?\s*</loc>", block)
        lm = re.search(r"<lastmod>\s*([^<]+?)\s*</lastmod>", block)
        if loc:
            out.append((html.unescape(loc.group(1)), lm.group(1) if lm else None))
    return is_index, out


def _load(source: str, get, folder: Path | None):
    """(body, folder of a saved file or None)."""
    if folder is not None:
        local = folder / source.rstrip("/").rsplit("/", 1)[-1]
        if local.is_file():
            return local.read_text(errors="replace"), folder
    p = Path(source).expanduser()
    if "://" not in source and p.is_file():
        return p.read_text(errors="replace"), p.parent
    status, body = get(source)
    if status != 200:
        raise SitemapError(f"cannot read sitemap {source}: http {status}")
    return body, folder


def read(source: str, get=None, _depth: int = 0, _folder: Path | None = None):
    get = get or default_get
    body, folder = _load(str(source), get, _folder)
    is_index, entries = parse(body)
    if not is_index:
        return entries
    if _depth >= MAX_DEPTH:
        raise SitemapError(f"sitemap index nested deeper than {MAX_DEPTH} levels at {source}")
    out, seen = [], set()
    for child, _lm in entries:
        for loc, lm in read(child, get, _depth + 1, folder):
            if loc not in seen:
                seen.add(loc)
                out.append((loc, lm))
    return out


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0 if len(sys.argv) == 2 else 2)
    try:
        rows = read(sys.argv[1])
    except SitemapError as e:
        sys.exit(str(e))
    print(f"{len(rows)} pages")
    for loc, lm in rows:
        print(f"{loc}\t{lm or ''}")
