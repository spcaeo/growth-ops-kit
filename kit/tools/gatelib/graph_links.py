"""Internal-link flags from the RENDERED site, for every stack that is not Next.js (2.6.0).

adapters/nextjs/link_map.py reads a Next.js repo (app/, content/) to know every link. Any other stack has no such
folder, so the same flags are computed from inventory/link-graph.db, which `growth link_graph crawl --base <preview>`
fills from the rendered pages (zones body / related / nav / header / footer / breadcrumb). The answers have the same shape
as link_map.py --json, so the checks (links.inbound 88, links.plan 88a, links.up-across 89, links.anchor-unique 90,
links.no-redirect 75) read either source the same way.

A graph that is missing or stale is never a pass: the check prints a blocked SKIP that names the command to run.
The graph is "fresh" when its last crawl is newer than the site's last commit and no older than growth.json
link_graph.max_age_hours (default 24). This module only reads the database; it never writes into the project."""
from __future__ import annotations

import datetime as dt
import json
import re
import sqlite3
import urllib.parse
from collections import defaultdict
from pathlib import Path

from .core import Skip, run

CONTENT = ("body", "related")                      # zones that count as content links (the same as link_graph.CONTENT)
WHERE = {"body": "body", "related": "hub-list"}    # the link_map names for them
# anchors that are meant to repeat (the same words as link_graph.GENERIC_ANCHORS, the whole-site anchor report)
GENERIC = {"click here", "here", "read more", "learn more", "more", "see more", "view", "view all", "continue", "this",
           "read the guide", "read article", "read the article", "details", "find out more", "get started", "(no text)",
           "all articles", "all posts", "view all articles", "book a call", "book a demo", "schedule a call", "contact us",
           "contact", "next", "previous", "back"}
PAGER = {"older", "newer", "next", "previous", "prev", "older posts", "newer posts", "load more"}


def nrm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", (s or "").lower().replace("'", "").replace("’", ""))).strip()


def key(path):
    return (path or "").split("#")[0].split("?")[0].rstrip("/") or "/"


def origin(ctx):
    u = urllib.parse.urlsplit(ctx.url or "")
    return f"{u.scheme}://{u.netloc}" if u.netloc else "<the preview URL>"


def crawl_command(ctx):
    return f"growth link_graph crawl --base {origin(ctx)}"


def db_path(ctx):
    return ctx.project / "inventory" / "link-graph.db"


def blocked(ctx, why):
    return Skip(f"{why}: run `{crawl_command(ctx)}` (it fills inventory/link-graph.db from the rendered site), then run the gate again", blocked=True)


def fresh_enough(ctx, c):
    row = c.execute("SELECT value FROM meta WHERE key='last_crawl'").fetchone()
    try:
        at = json.loads(row[0])["at"] if row else ""
        when = dt.datetime.strptime(at, "%Y-%m-%d %H:%M:%S")
    except (ValueError, KeyError, TypeError):
        return "its last crawl has no date"
    try:
        from zoneinfo import ZoneInfo
        zone = ZoneInfo(ctx.cfg.get("timezone") or "UTC")
    except Exception:  # noqa: BLE001
        zone = dt.timezone.utc
    stamp = when.replace(tzinfo=zone)
    max_h = float((ctx.cfg.get("link_graph") or {}).get("max_age_hours") or 24)
    age = (dt.datetime.now(zone) - stamp).total_seconds() / 3600
    if age > max_h:
        return f"its last crawl ({at}) is {age:.0f} hours old (limit {max_h:g})"
    if ctx.repo and (ctx.repo / ".git").exists():
        code, out = run(["git", "-C", str(ctx.repo), "log", "-1", "--format=%ct"], timeout=30)
        if code == 0 and out.strip().isdigit() and int(out.strip()) > stamp.timestamp():
            return f"the site changed after its last crawl ({at})"
    return ""


POST_TYPES = ("post", "article", "guide", "blog", "blog post")


def inventory_types(ctx):
    """{page key: type} from inventory/inventory.json (the page list), {} when there is none."""
    try:
        rows = json.loads((ctx.project / "inventory" / "inventory.json").read_text())["pages"]
    except (OSError, ValueError, KeyError, TypeError):
        return {}
    return {key(r["path"]): str(r.get("type") or "").lower() for r in rows if isinstance(r, dict) and r.get("path")}


class Graph:
    def __init__(self, c, types=None, me="", me_is_post=False):
        self.types = types or {}
        self.me, self.me_is_post = me, me_is_post
        self.pages = {r[0]: dict(status=r[1], cluster=r[2] or "", hub=r[3] or "", type=(r[4] or "").lower())
                      for r in c.execute("SELECT url, status, cluster, hub, type FROM pages")}
        self.targets = {r[0]: dict(status=r[1], final=r[2] or r[0], fstatus=r[3]) for r in c.execute("SELECT path, status, final, final_status FROM targets")}
        self.rel = defaultdict(set)
        self.links = []
        for src, dst, anchor, zone, rel in c.execute("SELECT src, dst, anchor, zone, rel FROM links"):
            t = self.targets.get(dst)
            final = key(t["final"]) if t and 300 <= (t["status"] or 0) < 400 else dst
            moved = ""
            if t and (t["status"] == 410 or t["fstatus"] == 410):
                moved = "gone"
            elif t and 300 <= (t["status"] or 0) < 400 and final != dst:
                moved = "redirect"
            self.links.append(dict(src=src, to=dst, final=final, moved=moved, words=nrm(anchor), zone=zone, where=WHERE.get(zone, zone),
                                   rel=rel or "", file=""))

    def live(self, p):
        return p in self.pages and self.pages[p]["status"] == 200

    def hub_of(self, p):
        return self.pages[p]["hub"] if p in self.pages else ""

    def kind(self, p):
        """hub: the top page of its cluster. post: a page the page list types as a post (or the page the gate was told is a
        post). page: anything else. Hub-list flags (no-hub, not-on-hub, siblings<2) belong to posts only, as in link_map."""
        h = self.hub_of(p)
        if h == p:
            return "hub"
        t = self.pages.get(p, {}).get("type") or self.types.get(p, "")
        if h and (t in POST_TYPES or (self.me_is_post and p == self.me)):
            return "post"
        return "page"

    def content_in(self, p):
        return [l for l in self.links if l["final"] == p and l["zone"] in CONTENT and l["src"] != p and self.live(l["src"])]

    def content_out(self, p):
        return [l for l in self.links if l["src"] == p and l["zone"] in CONTENT]

    def is_pager(self, l):
        return bool(set(l["rel"].split()) & {"next", "prev"} or l["words"].isdigit() or l["words"] in PAGER
                    or re.search(r"/page/\d+$", l["to"]))

    def anchors(self, brand):
        out = defaultdict(set)
        for l in self.links:
            if l["zone"] in CONTENT and l["words"] and self.live(l["src"]) and l["moved"] != "gone" and not self.is_pager(l) \
                    and l["words"] not in GENERIC and l["words"] not in brand and l["final"] != l["src"]:
                out[l["words"]].add(l["final"])
        return out

    def flags(self, p, anchors, explicit):
        out = [l for l in self.content_out(p) if not self.is_pager(l)]
        flags = []
        kind = self.kind(p)
        srcs = {l["src"] for l in self.content_in(p)}
        ranks = bool(self.hub_of(p)) or (explicit and p != "/")      # a page of a cluster is ranked by its inbound links
        if ranks and not srcs:
            flags.append(("orphan", "0 content links in"))
        elif ranks and len(srcs) == 1:
            flags.append(("weak", f"1 content link in, from {next(iter(srcs))}"))
        hub = self.hub_of(p)
        if kind == "post" and self.live(hub):
            if not any(l["final"] == hub and l["zone"] == "body" for l in out):
                flags.append(("no-hub", f"no body link up to {hub}"))
            if not any(l["src"] == hub and l["final"] == p for l in self.content_in(p)):
                flags.append(("not-on-hub", f"{hub}'s content does not link to it"))
            mates = [q for q in self.pages if q != p and self.live(q) and self.hub_of(q) == hub and self.kind(q) == "post"]
            if self.me_is_post and p == self.me:
                mates = [q for q in self.pages if q != p and self.live(q) and self.hub_of(q) == hub and q != hub]
            hit = len({l["final"] for l in out} & set(mates))
            if len(mates) >= 2 and hit < 2:
                flags.append(("siblings<2", f"links to {hit} of {len(mates)} sibling posts"))
        for l in out:
            t = self.targets.get(l["to"])
            if l["moved"] == "gone":
                flags.append(("to-gone", f"\"{l['words']}\" -> {l['to']} (410)"))
            elif l["moved"]:
                flags.append(("to-redirect", f"\"{l['words']}\" -> {l['to']} redirects to {l['final']}"))
            elif l["to"] not in self.pages and ((t and (t["status"] or 0) >= 400) or (t and not t["status"])):
                flags.append(("to-unknown", f"\"{l['words']}\" -> {l['to']} (answers {t['status'] or 'nothing'})"))
            elif l["words"] and len(anchors.get(l["words"], ())) > 1:
                others = sorted(anchors[l["words"]] - {l["final"]})
                flags.append(("dup-anchor", f"\"{l['words']}\" -> {l['final']}; the same words also go to {', '.join(others[:3])}"))
        return list(dict.fromkeys(flags))


def load(ctx):
    """The link graph of the project, as a Graph. Raises a blocked Skip naming the crawl command when there is none or it is stale."""
    if "graph" in ctx.cache:
        return ctx.cache["graph"]
    db = db_path(ctx)
    if not db.exists():
        raise blocked(ctx, "no link graph for this site (inventory/link-graph.db)")
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        why = fresh_enough(ctx, c)
        if why:
            raise blocked(ctx, f"the link graph is stale: {why}")
        g = Graph(c, inventory_types(ctx), ctx.key_path() if ctx.path else "", ctx.ptype == "post")
    except sqlite3.DatabaseError as e:
        raise blocked(ctx, f"the link graph cannot be read ({e})")
    finally:
        c.close()
    ctx.cache["graph"] = g
    return g


def page_in(ctx, g, p=None):
    p = p or ctx.key_path()
    if not g.live(p):
        raise blocked(ctx, f"{p} is not in the link graph (a new page, or one that did not answer 200)")
    return p


def link_map(ctx, cmd):
    """Same answers as link_map.py <cmd> --json: inbound / outbound links of the page, and {} for suggest."""
    g = load(ctx)
    p = page_in(ctx, g)
    if cmd == "inbound":
        return {"target": p, "links": g.content_in(p)}
    if cmd == "outbound":
        return {"source": p, "links": g.content_out(p)}
    return {}


def link_check(ctx, whole_site=False):
    """Same as c_repo.link_check for link_map.py check: {path: [(flag, detail)]}."""
    g = load(ctx)
    brand = {nrm(ctx.cfg.get("name", "")), nrm(ctx.cfg.get("product", ""))}
    anchors = g.anchors(brand)
    pages = sorted(q for q in g.pages if g.live(q)) if whole_site else [page_in(ctx, g)]
    return {q: g.flags(q, anchors, not whole_site) for q in pages}
