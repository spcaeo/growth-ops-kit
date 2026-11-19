#!/usr/bin/env python3
"""Site link graph: every internal link of every page, read from the RENDERED HTML (works for any site).

Why: a page is only as strong as the links that point to it, and you cannot fix what you cannot see. This tool reads
the sitemap, fetches every page once (plain requests, polite, robots.txt respected), and stores each <a href> with its
target, anchor text, rel, ZONE (nav, header, footer, breadcrumb, related, body) and nearest heading. Inbound links are
the reverse index of outbound links, so every page is read once. Standard library only. Nothing here is site-specific:
the site, sitemap, time zone and cluster labels come from growth.json and inventory/inventory.json.

  growth link_graph crawl [--base http://127.0.0.1:3000] [--limit N] [--concurrency 8] [--delay 0.2]
  growth link_graph update /pricing /blog/some-post [--base URL]   # re-read just these pages, keep a before/after
  growth link_graph report [--out research/link-graph-DATE.md] [--json]
  growth link_graph page /pricing [--json]                          # inbound/outbound + Search Console queries
  growth link_graph history /pricing                                # snapshots from crawl/update, with the diff
  growth link_graph export --json [--out inventory/link-graph.json] # for the tracker dashboard

Zones: body = the page's own text (inside main/article); related = a "related/see also" box or <aside>;
breadcrumb; nav (menus); header; footer. Orphan = no BODY link in from another page. Weak = fewer than 2.
A link to a redirecting address counts for the page it ends on. --base crawls a local build of a branch (paths come
from the live sitemap) so a branch can be mapped before release. Output: inventory/link-graph.db (SQLite).
"""
import argparse
import html
import json
import re
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sitemaps  # noqa: E402
from config import CFG, PROJECT, SITE_URL, TZ, UA  # noqa: E402

DB = PROJECT / "inventory" / "link-graph.db"
INV = PROJECT / "inventory" / "inventory.json"
TRACKER = PROJECT / "page-tracker" / "tracker.db"
SITE_HOST = urlparse(SITE_URL).netloc.lower().removeprefix("www.")
ASSET = re.compile(r"\.(png|jpe?g|gif|svg|webp|avif|ico|css|js|mjs|json|xml|pdf|zip|mp4|webm|mp3|woff2?|ttf|txt|map|rss|csv)$", re.I)
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
SKIP_TEXT = {"script", "style", "noscript", "svg", "template"}
RELATED_WORDS = re.compile(r"(^|[\s_-])(related|see-also|seealso|read-next|more-articles|recommended|you-may-also|further-reading)([\s_-]|$)", re.I)
GENERIC_ANCHORS = {"click here", "here", "read more", "learn more", "more", "see more", "view", "view all", "continue", "this",
                   "read the guide", "read article", "read the article", "details", "find out more", "get started", "(no text)",
                   "all articles", "all posts", "view all articles", "book a call", "book a demo", "schedule a call", "contact us", "contact", "next", "previous", "back"}


def now():
    return datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")


# ------------------------------------------------------------------ HTML parsing
class PageParser(HTMLParser):
    """Collects title, h1, robots/canonical and every <a href> with zone, anchor text and nearest heading."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.links = [], []
        self.title = self.h1 = self.canonical = ""
        self.noindex = False
        self.skip = 0
        self.heading = ""
        self._cap = None      # ("title"|"h"|"a", tag, parts, extra)
        self._a = None

    @staticmethod
    def _flags(tag, a):
        f = set()
        cls = " ".join([a.get("class") or "", a.get("id") or ""])
        role, label = (a.get("role") or "").lower(), (a.get("aria-label") or "")
        if tag == "nav" and "breadcrumb" in (cls + label).lower() or "breadcrumb" in cls.lower():
            f.add("breadcrumb")
        if tag == "aside" or role == "complementary" or RELATED_WORDS.search(cls) or RELATED_WORDS.search(label):
            f.add("related")
        if tag == "main" or role == "main":
            f.add("main")
        if tag == "article":
            f.add("article")
        if tag in ("header", "footer", "nav"):
            f.add(tag)
        if role == "navigation":
            f.add("nav")
        if role == "banner":
            f.add("header")
        if role == "contentinfo":
            f.add("footer")
        return f

    def _zone(self):
        have = set().union(*self.stack) if self.stack else set()
        if "breadcrumb" in have:
            return "breadcrumb"
        if "related" in have:
            return "related"
        # header/footer/nav inside main or article belong to the content (article footer, table of contents)
        in_content = False
        for f in self.stack:  # outermost first
            if f & {"main", "article"}:
                in_content = True
            if in_content:
                continue
            for z in ("footer", "nav", "header"):
                if z in f:
                    return z
        return "body"

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "base" and a.get("href"):
            self.base_href = a["href"]
        if tag == "meta":
            if (a.get("name") or "").lower() == "robots" and "noindex" in (a.get("content") or "").lower():
                self.noindex = True
        elif tag == "link":
            if (a.get("rel") or "").lower() == "canonical":
                self.canonical = a.get("href") or ""
        if self._a is not None and tag != "a":
            self._a["parts"].append(" ")  # keep words from neighbouring spans apart
        if tag in VOID:
            if tag == "img" and self._a is not None:
                self._a["alts"].append(a.get("alt") or "")
            return
        if tag in SKIP_TEXT:
            self.skip += 1
        self.stack.append(self._flags(tag, a))
        self.stack[-1] = self.stack[-1] | {"_" + tag}
        if tag == "title":
            self._cap = ("title", tag, [])
        elif re.fullmatch(r"h[1-6]", tag):
            self._cap = ("h", tag, [])
        elif tag == "a":
            if self._a is not None:
                self._close_a()
            if a.get("href") is not None:
                self._a = {"href": a["href"], "rel": (a.get("rel") or "").lower(), "label": a.get("aria-label") or a.get("title") or "",
                           "parts": [], "alts": [], "inner": "", "zone": self._zone(), "heading": self.heading}

    def handle_endtag(self, tag):
        if self._a is not None and tag != "a":
            self._a["parts"].append(" ")
        if tag in VOID:
            return
        for i in range(len(self.stack) - 1, -1, -1):
            if "_" + tag in self.stack[i]:
                del self.stack[i:]
                break
        else:
            return
        if tag in SKIP_TEXT and self.skip:
            self.skip -= 1
        if tag == "a" and self._a is not None:
            self._close_a()
        if self._cap and self._cap[1] == tag:
            text = re.sub(r"\s+", " ", "".join(self._cap[2])).strip()
            if self._cap[0] == "title" and not self.title:
                self.title = text
            elif self._cap[0] == "h":
                if self._a is not None:
                    self._a["inner"] = self._a["inner"] or text  # a card link: its own heading is the anchor
                else:
                    self.heading = text[:120]  # card titles inside a link do not become the section heading
                if tag == "h1" and not self.h1:
                    self.h1 = text
            self._cap = None

    def handle_data(self, data):
        if self.skip:
            return
        if self._cap:
            self._cap[2].append(data)
        if self._a is not None:
            self._a["parts"].append(data)

    def _close_a(self):
        a, self._a = self._a, None
        clean = lambda x: re.sub(r"\s+", " ", x).strip()
        text = a["inner"] or clean("".join(a["parts"])) or clean(a["label"]) or clean(" ".join(a["alts"])) or "(no text)"
        self.links.append({"href": a["href"], "anchor": text[:300], "rel": a["rel"], "zone": a["zone"], "heading": a["heading"]})


def parse_page(doc):
    p = PageParser()
    p.feed(doc)
    p.close()
    return p


def norm_target(href, page_url, hosts):
    """A link's address as an internal site path (no query, fragment or trailing slash), or None if external/not a page."""
    h = html.unescape(href).strip()
    if not h or h.startswith("#") or re.match(r"(mailto|tel|javascript|data|sms):", h, re.I):
        return None
    u = urlparse(urljoin(page_url, h))
    if u.scheme not in ("http", "https") or u.netloc.lower().removeprefix("www.") not in hosts:
        return None
    path = re.sub(r"/{2,}", "/", u.path or "/")
    if path != "/":
        path = path.rstrip("/")
    if ASSET.search(path) or path.startswith(("/_next", "/cdn-cgi")):
        return None
    return path


# ------------------------------------------------------------------ fetching
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


OPENER = urllib.request.build_opener(NoRedirect)
PACE = threading.Lock()


def fetch(url, method="GET", delay=0.0, timeout=25):
    """(status, headers, body_text). Status 0 = network error. Never follows redirects. One retry on 429/503/network."""
    for attempt in range(2):
        req = urllib.request.Request(url, method=method, headers={**UA, "Accept": "text/html,*/*;q=0.5"})
        try:
            with OPENER.open(req, timeout=timeout) as r:
                ctype = r.headers.get("Content-Type", "")
                body = r.read(6_000_000).decode("utf-8", "replace") if method == "GET" and re.search(r"html|xml|text", ctype) else ""
                res = (r.status, r.headers, body)
        except urllib.error.HTTPError as e:
            res = (e.code, e.headers, "")
        except Exception:  # noqa: BLE001  (timeouts, DNS, TLS: reported as status 0)
            res = (0, {}, "")
        if delay:
            time.sleep(delay)
        if res[0] in (0, 429, 503) and attempt == 0:
            try:
                wait = min(float(res[1].get("Retry-After", 2)), 10) if res[1] else 2
            except ValueError:
                wait = 2
            time.sleep(wait + delay)
            continue
        return res
    return res


def resolve_target(origin, path, hosts, delay):
    """Follow redirects by HEAD (GET if HEAD is refused). Returns (first_status, final_path_or_url, final_status)."""
    first, cur, status = None, path, 0
    for _ in range(6):
        status, hdr, _ = fetch(origin + cur, "HEAD", delay)
        if status in (403, 405, 501):
            status, hdr, _ = fetch(origin + cur, "GET", delay)
        first = first or status
        if status in (301, 302, 303, 307, 308) and hdr.get("Location"):
            nxt = norm_target(hdr["Location"], origin + cur, hosts)
            if nxt is None:
                return first, urljoin(origin + cur, hdr["Location"]), 0
            cur = nxt
            continue
        break
    return first, cur, status


def read_sitemap(url):
    """Every page address in the sitemap (an index is followed), through the shared reader."""
    try:
        return [loc for loc, _ in sitemaps.read(url, get=lambda u: fetch(u, "GET")[::2])]
    except sitemaps.SitemapError as e:
        raise SystemExit(str(e))


def robots_for(origin):
    rp = RobotFileParser()
    status, _, body = fetch(origin + "/robots.txt", "GET")
    rp.parse(body.splitlines() if status == 200 else [])
    return rp


# ------------------------------------------------------------------ database
SCHEMA = """
CREATE TABLE IF NOT EXISTS pages(url TEXT PRIMARY KEY, status INT, title TEXT, h1 TEXT, cluster TEXT, hub TEXT, type TEXT,
  noindex INT, canonical TEXT, in_sitemap INT, crawled_at TEXT);
CREATE TABLE IF NOT EXISTS links(src TEXT, dst TEXT, anchor TEXT, zone TEXT, rel TEXT, heading TEXT, crawled_at TEXT);
CREATE INDEX IF NOT EXISTS links_src ON links(src);
CREATE INDEX IF NOT EXISTS links_dst ON links(dst);
CREATE TABLE IF NOT EXISTS targets(path TEXT PRIMARY KEY, status INT, final TEXT, final_status INT, checked_at TEXT);
CREATE TABLE IF NOT EXISTS links_history(id INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT, taken_at TEXT, label TEXT,
  in_body INT, in_total INT, out_body INT, out_total INT, inbound TEXT, outbound TEXT);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
"""


def connect(create=True):
    if not DB.exists() and not create:
        raise SystemExit(f"{DB} not found: run `growth link_graph crawl` first")
    DB.parent.mkdir(exist_ok=True)
    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    return c


def inventory_labels():
    """path -> (cluster label, hub path, type) from inventory/inventory.json (the page list and cluster labels)."""
    try:
        pages = json.loads(INV.read_text())["pages"]
    except Exception:  # noqa: BLE001
        return {}
    out = {}
    for p in pages:
        if p.get("status") != "live":
            continue
        silo = p.get("silo") or ""
        out[p["path"]] = ("Other" if silo in ("-", "?", "") else silo, p.get("pillar") or "", p.get("type") or "")
    return out


def label_for(path, labels, sitemap_paths):
    if path in labels:
        return labels[path]
    seg = path.strip("/").split("/")[0]
    return (seg or "Core", f"/{seg}" if seg and f"/{seg}" in sitemap_paths else "", "")


def save_page(c, path, status, parsed, labels, sitemap_paths, origin, hosts, stamp):
    cluster, hub, kind = label_for(path, labels, sitemap_paths)
    c.execute("DELETE FROM links WHERE src=?", (path,))
    c.execute("INSERT OR REPLACE INTO pages VALUES (?,?,?,?,?,?,?,?,?,?,?)",
              (path, status, parsed.title if parsed else "", parsed.h1 if parsed else "", cluster, hub, kind,
               int(bool(parsed and parsed.noindex)), parsed.canonical if parsed else "", int(path in sitemap_paths), stamp))
    n = 0
    for l in (parsed.links if parsed else []):
        dst = norm_target(l["href"], origin + path, hosts)
        if dst is None:
            continue
        c.execute("INSERT INTO links VALUES (?,?,?,?,?,?,?)", (path, dst, l["anchor"], l["zone"], l["rel"], l["heading"], stamp))
        n += 1
    return n


def crawl_one(origin, path, delay, rp):
    url = origin + path
    if rp is not None and not rp.can_fetch(UA["User-Agent"], url):
        return path, -1, None, ""
    status, hdr, body = fetch(url, "GET", delay)
    loc = hdr.get("Location", "") if hdr else ""
    return path, status, (parse_page(body) if status == 200 and body else None), loc


def check_targets(c, origin, hosts, delay, workers, only_new=True):
    """HEAD every linked address that is not a crawled 200 page (redirects, broken links, pages outside the sitemap)."""
    seen = {r[0] for r in c.execute("SELECT url FROM pages WHERE status=200")}
    if only_new:
        seen |= {r[0] for r in c.execute("SELECT path FROM targets")}
    todo = sorted({r[0] for r in c.execute("SELECT DISTINCT dst FROM links")} - seen)
    with ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(resolve_target, origin, p, hosts, delay): p for p in todo}
        for f in as_completed(futs):
            first, final, fstatus = f.result()
            c.execute("INSERT OR REPLACE INTO targets VALUES (?,?,?,?,?)", (futs[f], first, final, fstatus, now()))
    return len(todo)


def run_pages(c, origin, hosts, paths, sitemap_paths, delay, workers, rp):
    labels = inventory_labels()
    stamp = now()
    total, bad = 0, []
    with ThreadPoolExecutor(workers) as ex:
        futs = [ex.submit(crawl_one, origin, p, delay, rp) for p in paths]
        for i, f in enumerate(as_completed(futs), 1):
            path, status, parsed, loc = f.result()
            total += save_page(c, path, status, parsed, labels, sitemap_paths, origin, hosts, stamp)
            if 300 <= status < 400 and loc:
                final = norm_target(loc, origin + path, hosts)
                c.execute("INSERT OR REPLACE INTO targets VALUES (?,?,?,?,?)", (path, status, final or loc, 0, stamp))
            if status != 200:
                bad.append((path, status))
            if i % 25 == 0:
                print(f"  {i}/{len(paths)} pages", file=sys.stderr)
                c.commit()
    c.commit()
    return total, bad


def site_origin(base):
    return (base or SITE_URL).rstrip("/")


def hosts_for(origin):
    return {SITE_HOST, urlparse(origin).netloc.lower().removeprefix("www.")}


# ------------------------------------------------------------------ snapshots
def snapshot(c, path, label):
    inb = c.execute("""SELECT l.src, l.anchor, l.zone FROM links l LEFT JOIN targets t ON t.path=l.dst
                       WHERE l.src!=? AND (l.dst=? OR (t.final=? AND t.status BETWEEN 300 AND 399))""", (path, path, path)).fetchall()
    out = c.execute("SELECT dst, anchor, zone FROM links WHERE src=?", (path,)).fetchall()
    c.execute("INSERT INTO links_history(path,taken_at,label,in_body,in_total,out_body,out_total,inbound,outbound) VALUES (?,?,?,?,?,?,?,?,?)",
              (path, now(), label, len({r["src"] for r in inb if r["zone"] == "body"}), len({r["src"] for r in inb}),
               sum(1 for r in out if r["zone"] == "body"), len(out),
               json.dumps([[r["src"], r["anchor"], r["zone"]] for r in inb]), json.dumps([[r["dst"], r["anchor"], r["zone"]] for r in out])))


# ------------------------------------------------------------------ commands: crawl / update
def cmd_crawl(a):
    origin = site_origin(a.base)
    hosts = hosts_for(origin)
    locs = read_sitemap(CFG["sitemap_url"])
    paths = []
    for u in locs:
        p = norm_target(u, SITE_URL + "/", {SITE_HOST})
        if p and p not in paths:
            paths.append(p)
    if a.limit:
        paths = paths[:a.limit]
    sitemap_paths = set(paths)
    rp = None if a.base else robots_for(origin)
    delay = a.delay
    if rp and rp.crawl_delay("*"):
        delay = max(delay, float(rp.crawl_delay("*")))
    c = connect()
    t0 = time.time()
    print(f"crawling {len(paths)} pages from {origin} (concurrency {a.concurrency}, delay {delay}s)", file=sys.stderr)
    if not a.limit:
        c.execute("DELETE FROM pages")
        c.execute("DELETE FROM links")
    c.execute("DELETE FROM targets")
    n_links, bad = run_pages(c, origin, hosts, paths, sitemap_paths, delay, a.concurrency, rp)
    n_targets = check_targets(c, origin, hosts, delay, a.concurrency, only_new=False)
    for p in paths:
        snapshot(c, p, "crawl")
    c.execute("INSERT OR REPLACE INTO meta VALUES ('last_crawl', ?)", (json.dumps(
        {"at": now(), "origin": origin, "pages": len(paths), "links": n_links, "seconds": round(time.time() - t0, 1)}),))
    c.commit()
    print(f"pages {len(paths)}, internal links {n_links}, extra targets checked {n_targets}, "
          f"non-200 pages {len(bad)}, {time.time() - t0:.1f}s -> {DB}")
    for p, s in sorted(bad):
        print(f"  {s}  {p}")


def to_path(x):
    p = norm_target(x, SITE_URL + "/", {SITE_HOST})
    if p is None:
        raise SystemExit(f"not an internal page address: {x}")
    return p


def cmd_update(a):
    origin = site_origin(a.base)
    hosts = hosts_for(origin)
    c = connect(create=False)
    paths = [to_path(p) for p in a.paths]
    sitemap_paths = {r[0] for r in c.execute("SELECT url FROM pages WHERE in_sitemap=1")} | set(paths)
    for p in paths:
        snapshot(c, p, "before")
    n_links, bad = run_pages(c, origin, hosts, paths, sitemap_paths, a.delay, min(a.concurrency, len(paths)), None)
    new = check_targets(c, origin, hosts, a.delay, a.concurrency, only_new=True)
    for p in paths:
        snapshot(c, p, "after")
    c.commit()
    print(f"re-read {len(paths)} page(s): {n_links} internal links, {new} new targets checked, {len(bad)} not 200")
    for p in paths:
        print_diff(c, p)


def print_diff(c, path):
    rows = c.execute("SELECT * FROM links_history WHERE path=? ORDER BY id DESC LIMIT 2", (path,)).fetchall()
    if len(rows) < 2:
        print(f"{path}: only one snapshot so far")
        return
    new, old = rows[0], rows[1]
    ko = {(d, z) for d, _, z in json.loads(old["outbound"])}
    kn = {(d, z) for d, _, z in json.loads(new["outbound"])}
    print(f"{path}: {old['label']} {old['taken_at']} -> {new['label']} {new['taken_at']}")
    print(f"  outbound body {old['out_body']} -> {new['out_body']}, all {old['out_total']} -> {new['out_total']}; "
          f"inbound body {old['in_body']} -> {new['in_body']}, all {old['in_total']} -> {new['in_total']}")
    for d, z in sorted(kn - ko):
        print(f"  + out {z:10} {d}")
    for d, z in sorted(ko - kn):
        print(f"  - out {z:10} {d}")
    io = {(s, z) for s, _, z in json.loads(old["inbound"])}
    inn = {(s, z) for s, _, z in json.loads(new["inbound"])}
    for s, z in sorted(inn - io):
        print(f"  + in  {z:10} {s}")
    for s, z in sorted(io - inn):
        print(f"  - in  {z:10} {s}")


def cmd_history(a):
    c = connect(create=False)
    p = to_path(a.path)
    for r in c.execute("SELECT * FROM links_history WHERE path=? ORDER BY id", (p,)):
        print(f"{r['taken_at']}  {r['label']:7} in body {r['in_body']:3} all {r['in_total']:3} | out body {r['out_body']:3} all {r['out_total']:3}")
    print()
    print_diff(c, p)


# ------------------------------------------------------------------ the graph in memory
CONTENT = ("body", "related")
REDIRECT = range(300, 400)


class Graph:
    def __init__(self, c):
        self.pages = {r["url"]: dict(r) for r in c.execute("SELECT * FROM pages")}
        self.targets = {r["path"]: dict(r) for r in c.execute("SELECT * FROM targets")}
        self.links = [dict(r) for r in c.execute("SELECT * FROM links")]
        for l in self.links:
            l["final"] = self.final(l["dst"])
        self.live = {u for u, p in self.pages.items() if p["status"] == 200 and not p["noindex"]}
        self.inb, self.outb = defaultdict(list), defaultdict(list)
        for l in self.links:
            self.outb[l["src"]].append(l)
            if l["final"] != l["src"]:
                self.inb[l["final"]].append(l)
        try:
            self.last = json.loads(c.execute("SELECT value FROM meta WHERE key='last_crawl'").fetchone()[0])
        except Exception:  # noqa: BLE001
            self.last = {}

    def final(self, dst):
        t = self.targets.get(dst)
        return t["final"] if t and t["status"] in REDIRECT and t["final"] else dst

    def status(self, dst):
        """HTTP status of the address a link points at, after redirects (0 unknown)."""
        t = self.targets.get(dst)
        if t and t["status"] in REDIRECT:
            f = self.final(dst)
            return self.pages[f]["status"] if f in self.pages else t["final_status"]
        if dst in self.pages:
            return self.pages[dst]["status"]
        return t["status"] if t else 0

    def srcs(self, path, zones=("body",)):
        return {l["src"] for l in self.inb.get(path, []) if l["zone"] in zones}

    def cluster(self, path):
        return self.pages.get(path, {}).get("cluster", "?")

    def gsc_queries(self, path, n=12):
        if not TRACKER.exists():
            return []
        try:
            c = sqlite3.connect(f"file:{TRACKER}?mode=ro", uri=True)
            return c.execute("SELECT query, impressions, clicks, position FROM search_queries s WHERE path=? AND snapshot="
                             "(SELECT max(snapshot) FROM search_queries t WHERE t.path=s.path) ORDER BY impressions DESC LIMIT ?",
                             (path, n)).fetchall()
        except Exception:  # noqa: BLE001
            return []


def nrm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", s.lower().replace("'", "").replace("’", ""))).strip()


# ------------------------------------------------------------------ analysis
def analyse(g):
    A = {}
    live = sorted(g.live)
    body_in = {p: g.srcs(p) for p in live}
    A["orphans"] = [p for p in live if not body_in[p]]
    A["orphans_none"] = [p for p in A["orphans"] if not g.inb.get(p)]
    A["orphans_chrome_only"] = [p for p in A["orphans"] if g.inb.get(p)]
    A["weak"] = [p for p in live if len(body_in[p]) == 1]
    A["no_body_out"] = [p for p in live if not any(l["zone"] == "body" and l["final"] != p for l in g.outb.get(p, []))]
    # redirects and broken links
    red, brk = defaultdict(list), defaultdict(list)
    for l in g.links:
        t = g.targets.get(l["dst"])
        if t and t["status"] in REDIRECT:
            red[(l["dst"], l["final"])].append(l)
        st = g.status(l["dst"])
        if st >= 400 or st == 0:
            brk[(l["dst"], st)].append(l)
    A["redirects"], A["broken"] = red, brk
    A["non200"] = [(u, p["status"]) for u, p in sorted(g.pages.items()) if p["status"] != 200]
    # anchors
    by_anchor = defaultdict(lambda: defaultdict(set))
    for l in g.links:
        if l["zone"] in CONTENT and l["final"] != l["src"]:
            by_anchor[nrm(l["anchor"])][l["final"]].add(l["src"])
    brand = {nrm(CFG.get("name", "")), nrm(CFG.get("product", ""))}
    A["anchor_multi"] = {a: t for a, t in by_anchor.items() if len(t) >= 2 and a and a not in GENERIC_ANCHORS and a not in brand}
    A["anchor_generic"] = {a: t for a, t in by_anchor.items() if len(t) >= 2 and a in GENERIC_ANCHORS}
    over = []
    for p in live:
        cnt = defaultdict(set)
        for l in g.inb.get(p, []):
            if l["zone"] in CONTENT:
                cnt[nrm(l["anchor"])].add(l["src"])
        total = sum(len(v) for v in cnt.values())
        if not total:
            continue
        if p == CFG.get("conversion_path") or g.pages[p]["type"] in ("legal", "conversion", "blog index"):
            continue  # call-to-action, legal and index pages are meant to repeat one anchor
        top, srcs = max(cnt.items(), key=lambda kv: len(kv[1]))
        qs = g.gsc_queries(p, 1)
        if len(srcs) >= 3 and len(srcs) / total >= 0.6 and top not in GENERIC_ANCHORS and len(top.split()) <= 6:
            over.append(dict(page=p, anchor=top, count=len(srcs), total=total, top_query=bool(qs and nrm(qs[0][0]) == top)))
    A["exact_overuse"] = sorted(over, key=lambda x: -x["count"])
    # clusters
    cl = defaultdict(list)
    for p in live:
        cl[g.cluster(p)].append(p)
    health = {}
    for name, members in sorted(cl.items()):
        hubs = {g.pages[p]["hub"] for p in members if g.pages[p]["hub"]}
        hub = hubs.pop() if len(hubs) == 1 else (g.pages[members[0]]["hub"] if hubs else "")
        h = dict(pages=len(members), hub=hub, orphans=sum(1 for p in members if p in A["orphans"]),
                 weak=sum(1 for p in members if p in A["weak"]),
                 avg_body_in=round(sum(len(body_in[p]) for p in members) / len(members), 1))
        if hub and hub in g.live:
            spokes = [p for p in members if p != hub]
            h["spokes"] = len(spokes)
            tohub = {s for s in spokes if any(l["final"] == hub and l["zone"] in CONTENT for l in g.outb.get(s, []))}
            tohub_any = {s for s in spokes if any(l["final"] == hub for l in g.outb.get(s, []))}
            hubto = {s for s in spokes if any(l["final"] == s and l["zone"] in CONTENT for l in g.outb.get(hub, []))}
            sib = {s: len({l["final"] for l in g.outb.get(s, []) if l["zone"] in CONTENT and l["final"] in spokes and l["final"] != s})
                   for s in spokes}
            h.update(spoke_to_hub=len(tohub), spoke_to_hub_any=len(tohub_any), hub_to_spokes=len(hubto),
                     missing_to_hub=sorted(set(spokes) - tohub), missing_from_hub=sorted(set(spokes) - hubto),
                     siblings_ok=sum(1 for v in sib.values() if v >= 2), siblings_none=sorted(s for s, v in sib.items() if v == 0),
                     siblings_avg=round(sum(sib.values()) / len(sib), 1) if sib else 0,
                     cross_out=sum(1 for s in spokes for l in g.outb.get(s, [])
                                   if l["zone"] in CONTENT and l["final"] in g.live and g.cluster(l["final"]) != name))
        health[name] = h
    A["clusters"] = health
    A["top_inbound"] = sorted(((p, len(body_in[p])) for p in live), key=lambda x: -x[1])[:15]
    A["fixes"] = fix_list(g, A)
    return A


def fix_list(g, A):
    """{source page: [what to change]}: every fix is an edit on the page that SENDS the link."""
    fx = defaultdict(list)
    for (dst, final), ls in A["redirects"].items():
        for l in ls:
            fx[l["src"]].append(f"link to {dst} redirects to {final}: link {final} directly (anchor '{l['anchor']}', {l['zone']})")
    for (dst, st), ls in A["broken"].items():
        for l in ls:
            fx[l["src"]].append(f"link to {dst} is broken (status {st or 'no answer'}): fix or remove (anchor '{l['anchor']}', {l['zone']})")
    for a, tg in A["anchor_multi"].items():
        for t, srcs in tg.items():
            others = ", ".join(x for x in tg if x != t)
            for s in srcs:
                fx[s].append(f"anchor '{a}' goes to {t} here and to {others} elsewhere (rule 90): give each page its own words")
    for name, h in A["clusters"].items():
        for s in h.get("missing_to_hub", []):
            fx[s].append(f"{name}: add a body link up to its hub {h['hub']}")
        if h.get("missing_from_hub"):
            fx[h["hub"]].append(f"{name}: hub does not link {len(h['missing_from_hub'])} spoke(s) in its content: "
                                + ", ".join(h["missing_from_hub"][:12]))
    for p in A["orphans"]:
        fx[p].append("orphan: no body link points here; needs links from the pages named by `page` (inbound plan) or `link_map.py suggest`")
    return {k: v for k, v in fx.items()}


# ------------------------------------------------------------------ report
def md_table(head, rows):
    num = [all(re.fullmatch(r"[\d./-]+", str(r[i])) for r in rows) if rows else False for i in range(len(head))]
    return ["| " + " | ".join(head) + " |", "| " + " | ".join("---:" if num[i] else "---" for i in range(len(head))) + " |"] + \
           ["| " + " | ".join(str(x) for x in r) + " |" for r in rows]


def build_report(g, A):
    zones = Counter(l["zone"] for l in g.links)
    L = [f"# Link graph report, {SITE_HOST}", "",
         f"Crawled {g.last.get('at', '?')} from {g.last.get('origin', '?')} by `growth link_graph` ({g.last.get('seconds', '?')} s). "
         "Body = a link inside the page's own text. Orphan = no body link from another page. Weak = only one.", "",
         "## Totals", ""]
    L += md_table(["What", "Count"], [
        ("Pages read (sitemap)", len(g.pages)), ("Pages answering 200", sum(1 for p in g.pages.values() if p["status"] == 200)),
        ("Pages not 200 (see below)", len(A["non200"])), ("Internal links found", len(g.links)),
        *[(f"  in zone: {z}", n) for z, n in sorted(zones.items(), key=lambda x: -x[1])],
        ("Pages with no body link in (orphans)", len(A["orphans"])),
        ("  of them linked by nothing at all", len(A["orphans_none"])),
        ("  of them linked only by menu/footer/breadcrumb/related", len(A["orphans_chrome_only"])),
        ("Pages with exactly 1 body link in (weak)", len(A["weak"])),
        ("Pages with no body link out", len(A["no_body_out"])),
        ("Links to a redirecting address", sum(len(v) for v in A["redirects"].values())),
        ("Broken links (4xx, 5xx, no answer)", sum(len(v) for v in A["broken"].values())),
        ("Anchor words that go to 2+ pages (rule 90)", len(A["anchor_multi"])),
        ("Pages with one anchor overused (exact match)", len(A["exact_overuse"]))])
    L += ["", "## Cluster health", "",
          "Hub = the cluster's pillar page. Spoke = every other page of the cluster. Links counted: body and related boxes "
          "(menus, footer and breadcrumbs are on every page and do not count).", ""]
    rows = []
    for n, h in A["clusters"].items():
        s = h.get("spokes")
        rows.append((n, h["hub"] or "-", h["pages"], h["orphans"], h["weak"], h["avg_body_in"],
                     f"{h['spoke_to_hub']}/{s}" if s else "-", f"{h['hub_to_spokes']}/{s}" if s else "-",
                     f"{h['siblings_ok']}/{s}" if s else "-", h.get("cross_out", "-")))
    L += md_table(["Cluster", "Hub", "Pages", "Orphans", "Weak", "Avg body in", "Spokes link hub", "Hub links spokes",
                   "Spokes with 2+ siblings", "Links out to other clusters"], rows)
    for n, h in A["clusters"].items():
        if h.get("missing_to_hub") or h.get("missing_from_hub") or h.get("siblings_none"):
            L += ["", f"**{n}**:"]
            if h.get("missing_to_hub"):
                L.append(f"- Spokes with no body link to the hub ({len(h['missing_to_hub'])}): " + ", ".join(f"`{p}`" for p in h["missing_to_hub"]))
            if h.get("missing_from_hub"):
                L.append(f"- Spokes the hub does not link in its content ({len(h['missing_from_hub'])}): " + ", ".join(f"`{p}`" for p in h["missing_from_hub"]))
            if h.get("siblings_none"):
                L.append(f"- Spokes with no sibling link at all ({len(h['siblings_none'])}): " + ", ".join(f"`{p}`" for p in h["siblings_none"]))
    L += ["", "## Orphans (no body link in)", ""]
    if A["orphans"]:
        L += md_table(["Page", "Cluster", "Linked only by"], [
            (f"`{p}`", g.cluster(p), ", ".join(sorted({l["zone"] for l in g.inb.get(p, [])})) or "nothing") for p in A["orphans"]])
    else:
        L.append("None.")
    L += ["", "## Weak (1 body link in)", ""]
    L += md_table(["Page", "Cluster", "The one link comes from"], [
        (f"`{p}`", g.cluster(p), ", ".join(f"`{s}`" for s in sorted(g.srcs(p)))) for p in A["weak"]]) if A["weak"] else ["None."]
    L += ["", "## Top pages by body links in", ""]
    L += md_table(["Page", "Cluster", "Body links in"], [(f"`{p}`", g.cluster(p), n) for p, n in A["top_inbound"]])
    L += ["", "## Pages with no body link out (only menu/footer links)", ""]
    L.append(", ".join(f"`{p}`" for p in A["no_body_out"]) or "None.")
    L += ["", "## Links to redirecting addresses", ""]
    if A["redirects"]:
        L += md_table(["Linked address", "Ends on", "Links", "From"], [
            (f"`{d}`", f"`{f}`", len(ls), ", ".join(f"`{s}`" for s in sorted({l['src'] for l in ls})[:6])) for (d, f), ls in
            sorted(A["redirects"].items(), key=lambda x: -len(x[1]))])
    else:
        L.append("None.")
    L += ["", "## Broken links and pages not answering 200", ""]
    for u, st in A["non200"]:
        L.append(f"- Sitemap page `{u}` answers {st}")
    for (d, st), ls in sorted(A["broken"].items(), key=lambda x: -len(x[1])):
        L.append(f"- `{d}` answers {st or 'nothing'}; linked from " + ", ".join(f"`{s}`" for s in sorted({l['src'] for l in ls})[:8]))
    if not A["non200"] and not A["broken"]:
        L.append("None.")
    L += ["", "## Same anchor words, different pages (rule 90)", ""]
    if A["anchor_multi"]:
        L += md_table(["Anchor words", "Goes to (number of pages linking)"], [
            (f"`{a}`", "; ".join(f"`{t}` ({len(s)})" for t, s in sorted(tg.items(), key=lambda x: -len(x[1]))))
            for a, tg in sorted(A["anchor_multi"].items(), key=lambda x: -sum(len(s) for s in x[1].values()))[:40]])
    else:
        L.append("None.")
    if A["anchor_generic"]:
        L += ["", "Generic anchors (say nothing about the target): " + ", ".join(
            f"`{a}` ({sum(len(s) for s in t.values())} links to {len(t)} pages)" for a, t in A["anchor_generic"].items())]
    L += ["", "## Exact-match anchor overuse", "",
          "One short anchor (6 words or fewer, so not a card's full title) makes up 60%+ of a page's content links in, from 3 or more pages.", ""]
    if A["exact_overuse"]:
        L += md_table(["Page", "Anchor", "Pages using it", "Of content links in", "Equals top Search Console query"], [
            (f"`{o['page']}`", f"`{o['anchor']}`", o["count"], o["total"], "yes" if o["top_query"] else "no") for o in A["exact_overuse"]])
    else:
        L.append("None.")
    L += ["", f"## Fix list by source page ({len(A['fixes'])} pages)", "",
          "Every fix is an edit on the page that sends the link. File each in the journal against that page.", ""]
    for src, items in sorted(A["fixes"].items(), key=lambda x: -len(x[1]))[:60]:
        L.append(f"- `{src}` ({len(items)})")
        L += [f"  - {i}" for i in items[:6]]
    return "\n".join(L) + "\n"


def cmd_report(a):
    c = connect(create=False)
    g = Graph(c)
    A = analyse(g)
    if a.json:
        print(json.dumps(jsonable(g, A), indent=1, ensure_ascii=False))
        return
    text = build_report(g, A)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(text)
        print(f"written {a.out}")
    else:
        print(text)


def jsonable(g, A):
    pages = []
    for p in sorted(g.pages):
        pg = g.pages[p]
        inb = g.inb.get(p, [])
        pages.append(dict(path=p, status=pg["status"], title=pg["title"], cluster=pg["cluster"], hub=pg["hub"], type=pg["type"],
                          in_body=len(g.srcs(p)), in_related=len(g.srcs(p, ("related",))), in_total=len({l["src"] for l in inb}),
                          in_zones=dict(Counter(l["zone"] for l in inb)),
                          out_body=sum(1 for l in g.outb.get(p, []) if l["zone"] == "body"), out_total=len(g.outb.get(p, [])),
                          orphan=p in A["orphans"], weak=p in A["weak"],
                          top_anchors=[[an, n] for an, n in Counter(l["anchor"] for l in inb if l["zone"] in CONTENT).most_common(5)]))
    return dict(meta=dict(g.last, site=SITE_URL, exported=now()), pages=pages,
                clusters=A["clusters"], orphans=A["orphans"], weak=A["weak"], no_body_out=A["no_body_out"],
                redirects=[dict(linked=d, final=f, links=len(ls), sources=sorted({l["src"] for l in ls})) for (d, f), ls in A["redirects"].items()],
                broken=[dict(linked=d, status=s, sources=sorted({l["src"] for l in ls})) for (d, s), ls in A["broken"].items()],
                anchor_multi={k: {t: sorted(s) for t, s in v.items()} for k, v in A["anchor_multi"].items()},
                exact_overuse=A["exact_overuse"], top_inbound=A["top_inbound"], fixes=A["fixes"])


def cmd_export(a):
    c = connect(create=False)
    g = Graph(c)
    out = json.dumps(jsonable(g, analyse(g)), indent=1, ensure_ascii=False)
    if a.stdout:
        print(out)
        return
    path = Path(a.out) if a.out else PROJECT / "inventory" / "link-graph.json"
    path.write_text(out + "\n")
    print(f"written {path}")


# ------------------------------------------------------------------ page
def cmd_page(a):
    c = connect(create=False)
    g = Graph(c)
    p = to_path(a.path)
    if p not in g.pages:
        raise SystemExit(f"{p} is not in the graph (crawl first, or it is not in the sitemap)")
    pg = g.pages[p]
    inb = [l for l in g.inb.get(p, [])]
    qs = g.gsc_queries(p)
    if a.json:
        print(json.dumps(dict(path=p, page=pg, inbound=inb, outbound=g.outb.get(p, []), queries=qs), indent=1, ensure_ascii=False))
        return
    print(f"{p}  status {pg['status']}  cluster '{pg['cluster']}'  hub {pg['hub'] or '-'}  type {pg['type'] or '-'}")
    print(f"title: {pg['title']}\nh1: {pg['h1']}\ncrawled {pg['crawled_at']}\n")
    zc = Counter(l["zone"] for l in inb)
    print(f"INBOUND: {len({l['src'] for l in inb})} pages, body {len(g.srcs(p))}, related {len(g.srcs(p, ('related',)))}; "
          + ", ".join(f"{z} {n}" for z, n in zc.most_common()))
    for z in ("body", "related", "breadcrumb", "nav", "header", "footer"):
        rows = [l for l in inb if l["zone"] == z]
        if not rows:
            continue
        print(f"  [{z}]")
        for l in sorted(rows, key=lambda l: l["src"]):
            via = f" (via redirect {l['dst']})" if l["dst"] != p else ""
            print(f"    {l['src']}  [{g.cluster(l['src'])}]  '{l['anchor']}'  under '{l['heading'] or '-'}'{via}")
    out = g.outb.get(p, [])
    print(f"\nOUTBOUND: {len({l['final'] for l in out})} pages; " + ", ".join(f"{z} {n}" for z, n in Counter(l["zone"] for l in out).most_common()))
    for z in ("body", "related", "breadcrumb"):
        for l in [l for l in out if l["zone"] == z]:
            print(f"  [{z}] -> {l['dst']}{' => ' + l['final'] if l['final'] != l['dst'] else ''}  '{l['anchor']}'  under '{l['heading'] or '-'}'")
    print("\nSEARCH CONSOLE queries for this page vs the anchors that point to it (body + related):")
    anchors = Counter(nrm(l["anchor"]) for l in inb if l["zone"] in CONTENT)
    if not qs:
        print("  (no Search Console queries stored for this page)")
    for q, impr, clk, pos in qs:
        nq = nrm(q)
        used = sum(n for an, n in anchors.items() if an == nq or (nq and nq in an))
        part = sum(n for an, n in anchors.items() if an != nq and nq not in an and set(nq.split()) & set(an.split()) - {"the", "a", "for", "of", "to", "and"} and len(set(nq.split()) & set(an.split())) >= max(2, len(nq.split()) // 2))
        print(f"  {impr:5} impr, pos {pos:5.1f}  '{q}'  exact anchors {used}, partial {part}")
    unmatched = [an for an in anchors if not any(nrm(q[0]) in an or an in nrm(q[0]) for q in qs)]
    if unmatched:
        print("  anchors that match none of those queries: " + ", ".join(f"'{x}'" for x in unmatched[:12]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("crawl", "update"):
        s = sub.add_parser(name)
        s.add_argument("--base", help="crawl this origin (a local build) instead of the live site; paths come from the live sitemap")
        s.add_argument("--concurrency", type=int, default=8)
        s.add_argument("--delay", type=float, default=0.2, help="seconds each worker waits after a request")
        if name == "crawl":
            s.add_argument("--limit", type=int, default=0)
        else:
            s.add_argument("paths", nargs="+")
    s = sub.add_parser("report")
    s.add_argument("--out")
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("page")
    s.add_argument("path")
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("history")
    s.add_argument("path")
    s = sub.add_parser("export")
    s.add_argument("--json", action="store_true", help="(the only format; kept for clarity)")
    s.add_argument("--out")
    s.add_argument("--stdout", action="store_true")
    a = ap.parse_args()
    {"crawl": cmd_crawl, "update": cmd_update, "report": cmd_report, "page": cmd_page, "history": cmd_history, "export": cmd_export}[a.cmd](a)


if __name__ == "__main__":
    main()
