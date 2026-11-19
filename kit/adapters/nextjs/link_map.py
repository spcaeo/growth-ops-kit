#!/usr/bin/env python3
"""Internal link map and link planner for the site (read-only on the site; standard library only).

It reads the site repo (Markdown posts and pages, the app routes and the page components), resolves redirects from the
redirect files named in growth.json (nextjs.redirect_files), and builds one link graph: every link with its source, target, anchor (the words clicked) and
WHERE it sits on the page:
  body       written in the page's own text (Markdown body, or a text link in the page's own components)
  hub-list   a hub's guide list or shelves (the files named in growth.json nextjs.hub_files, if any)
  nav        the top menu on every page          footer      the footer on every page
  breadcrumb the trail on a post or feature page  related     the "related stories" box under a post

Search Console (page-tracker/tracker.db, read-only) and the research files add what the page should be found for.

  growth link_map inbound  /lawn-mowing [--repo ../wt-lawn-mowing]
  growth link_map outbound /lawn-mowing
  growth link_map orphans                     # pages with fewer than 2 content links in (rule 88)
  growth link_map suggest  /lawn-mowing [--limit 25] [--research 'research/*lawn*']
  growth link_map check    /lawn-mowing   # one page's link flags; exit 1 on any
  growth link_map check --all                                  # every live page; exit 1 on any flag
  add --json to any command for machine-readable output; --include-scheduled counts future-dated posts as live.

`suggest` ranks the pages that should link to the target, from four signals (scores are printed so a person can check):
  (a) cluster  same silo as the target (growth.json `silos`, tracker `site_pages.cluster`): 3; an old generic post in
               the target's topic (tracker cluster "blog" with query overlap): 1
  (b) gsc      the source's own Search Console queries that overlap the target's search words: log2(1 + impr/5), max 4;
               plus the source's strength, log10(1 + 90-day impressions)/1.5, max 2
  (c) mention  the source's text already uses a target search phrase without a link: 3; a sentence that names a
               product word and a distinctive topic word of the target: 1.5; the topic word alone: 1. The exact
               sentence is printed.
  (d) buyer    buyer questions / AI prompts from the research files (tables with a Prompt, Search or Question column)
               whose distinctive words the source's title and headings answer: 0.5 each, max 2
Anchors come from the target's real search words (its Search Console queries, the queries of pages that 301 into it,
and the dossier's "Own" list), most impressions first; an anchor already used for the target, or used anywhere for a
different page (rule 90), is skipped, so no two sources get the same words.
It also lists anchor fixes for existing links (duplicate words, or words with no search phrase) and outbound
suggestions: a hub to every spoke of its silo, a spoke up to its hub and to its closest siblings.

Where this site's code is laid out differently, growth.json "nextjs" says so (every key is optional):
  posts_dir, pages_dir   the Markdown folders (default content/posts and content/pages; a missing folder is skipped)
  redirect_files         files holding the site's redirects: "/old": "/new" pairs, and a Set named ...GONE... of 410 paths
  retired_paths          address prefixes that answer 410 on purpose (for example "/tag")
  hub_files              files whose entries hold a hub's guide list: "slug": { ... title: "...", href: "/..." }
  template_files         files whose links appear on every page (default components/nav.tsx, header.tsx, footer.tsx)
  related_posts_file     the file that builds a post's "related posts" box; when set, the same ranking is assumed
  related_generic_tags   tags that never decide which posts are related (default blog, guide)
Hubs are the silos of growth.json. The blog's address is growth.json blog_path (default /blog).
"""
import argparse
import datetime as dt
import glob
import json
import math
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "tools"))
from config import CFG, PROJECT, SITE_REPO, TZ  # noqa: E402

DB = PROJECT / "page-tracker" / "tracker.db"
NX = CFG.get("nextjs") or {}
BLOG = "/" + (CFG.get("blog_path") or "/blog").strip("/")
POSTS_DIR = NX.get("posts_dir") or "content/posts"
PAGES_DIR = NX.get("pages_dir") or "content/pages"
REDIRECT_FILES = list(NX.get("redirect_files") or [])
RETIRED = tuple(NX.get("retired_paths") or [])
HUB_FILES = list(NX.get("hub_files") or [])
TEMPLATE_FILES = list(NX.get("template_files") or ["components/nav.tsx", "components/header.tsx", "components/footer.tsx"])
RELATED_FILE = NX.get("related_posts_file") or ""
RELATED_GENERIC = set(NX.get("related_generic_tags") or ["blog", "guide"])
# Words that describe the business's own offer and generic filler words come from growth.json "link_words"
# (product_words, generic, stem, template_components); these defaults suit any site.
LW = CFG.get("link_words") or {}
TEMPLATE_COMPONENTS = set(LW.get("template_components", ["nav", "footer", "breadcrumbs", "link-cards", "sticky-cta", "exit-offer",
                                                         "copy-button", "page-schema", "post-article", "post-card", "article-toc",
                                                         "share-links"]))
BRAND_WORDS = {w.lower() for w in (CFG.get("product"), CFG.get("name")) if w}
PRODUCT_WORDS = set(LW.get("product_words", ["software", "service", "services", "app", "system", "tool", "platform", "company"]))
GENERIC = {"for", "the", "a", "an", "of", "in", "to", "and", "with", "best", "what", "how", "is", "do", "does", "can", "my", "our",
           "your", "on", "that", "it", "or", "vs", "free", "tool", "tools", "platform", "service", "services", "company",
           "companies", "business"} | set(LW.get("generic", []))
STEM = {"optimisation": "optimization", "optimise": "optimize"} | dict(LW.get("stem", {}))


# ---------------------------------------------------------------- text helpers
def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", re.sub(r"['\u2019]", "", s.lower()))).strip()


def toks(s):
    return [STEM.get(w, w) for w in norm(s).split()]


def strip_md(s):
    s = re.sub(r"(?<!!)\[([^\]]+)\]\([^)]+\)", r"\1", s)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"[*_`]+", "", s).strip()


def split_doc(text):
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)$", text, re.S)
    if not m:
        return {}, text
    fm, key = {}, None
    for line in m.group(1).splitlines():
        km = re.match(r"^([A-Za-z]\w*):\s*(.*)$", line)
        if km:
            key, val = km.group(1), km.group(2).strip()
            if val in (">", ">-", "|", "|-", ""):
                fm[key] = [] if val == "" else ""
            elif val.startswith("["):
                fm[key] = [x.strip().strip("'\"") for x in val.strip("[]").split(",") if x.strip()]
            else:
                fm[key] = val.strip("'\"")
        elif key and line.startswith((" ", "\t")):
            s = line.strip()
            if isinstance(fm[key], list) and s.startswith("- "):
                fm[key].append(s[2:].strip().strip("'\""))
            elif isinstance(fm[key], list) and not fm[key]:
                fm[key] = s
            elif isinstance(fm[key], str):
                fm[key] = (fm[key] + " " + s).strip()
    return fm, m.group(2)


def md_links(text):
    """[(href, words)] from Markdown and HTML links in a Markdown body."""
    out = [(m.group(2), m.group(1)) for m in
           re.finditer(r"(?<!!)\[((?:[^\[\]]|\[[^\]]*\])+)\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)", text)]
    out += [(m.group(1) or m.group(2), re.sub(r"<[^>]+>", "", m.group(3))) for m in
            re.finditer(r"<a\b[^>]*?\shref\s*=\s*(?:\"([^\"]*)\"|'([^']*)')[^>]*>(.*?)</a>", text, re.S | re.I)]
    return out


def site_path(href):
    h = href.strip()
    h = re.sub(r"^https?://(www\.)?" + re.escape(CFG["site_url"].split("://", 1)[1]) + r"(?=/|$)", "", h, flags=re.I)
    if not h.startswith("/") or h.startswith("//"):
        return None
    h = re.split(r"[?#]", h)[0].rstrip("/") or "/"
    if re.search(r"\.[a-z0-9]{2,5}$", h, re.I) and h != "/rss.xml":
        return None
    if h.startswith(("/images/", "/brand/", "/videos/", "/_next/")):
        return None
    return h


def sentences(body):
    """Body sentences outside headings, tables, code and existing links (a linked phrase is not a free mention)."""
    out, code = [], False
    for para in re.split(r"\n\s*\n", body):
        p = para.strip()
        if p.startswith("```"):
            code = not code if p.count("```") % 2 else code
            continue
        if code or not p or p.startswith(("#", "|", "<", "!", ">")) or re.match(r"^[-*] \[", p):
            continue
        for s in re.split(r"(?<=[.!?])\s+(?=[A-Z\"(])", p.replace("\n", " ")):
            if len(s) > 30:
                out.append(s.strip())
    return out


# ---------------------------------------------------------------- the site
class Site:
    def __init__(self, repo, include_scheduled=False):
        self.repo = Path(repo).resolve()
        if not (self.repo / "app").is_dir():
            sys.exit(f"link_map: no app/ folder in {self.repo}; pass --repo <site checkout or worktree>")
        self.today = dt.datetime.now(TZ).date().isoformat()
        self.include_scheduled = include_scheduled
        self.hubs = [k.strip("/") for k in (CFG.get("silos") or {})]       # the hubs are the silos of growth.json
        self._redirects()
        self.lib_consts = self._lib_consts()
        self.docs, self.links = {}, []
        self._content()
        self.routes = {"/"} | {f"/{v}" for v in self.hubs}
        # Every static route that has a page.tsx, nested ones too (/author/<name>); dynamic folders ([slug]) and
        # route groups are posts or templates, read from content/ instead.
        for f in (self.repo / "app").rglob("page.tsx"):
            parts = f.parent.relative_to(self.repo / "app").parts
            if parts and parts[0] != "api" and not any(x[0] in "[(" for x in parts):
                self.routes.add("/" + "/".join(parts))
        self._code_pages()
        self._templates()

    def _lib_consts(self):
        """Path constants the page code imports from lib/ (`export const NAME = "/x"`), so href={NAME} is a real link."""
        out = {}
        for f in (self.repo / "lib").glob("*.ts"):
            out.update(re.findall(r'export const ([A-Z_][A-Z0-9_]*)\s*=\s*"(/[^"]*)"', f.read_text()))
        return out

    def read(self, rel):
        p = self.repo / rel
        return p.read_text() if p.exists() else ""

    # -------- redirects (the files named in growth.json nextjs.redirect_files)
    def _redirects(self):
        """"/old": "/new" pairs and the 410 paths of a Set named ...GONE..., from every redirect file."""
        self.path_redirects, self.gone_paths = {}, set()
        for rel in REDIRECT_FILES:
            src = self.read(rel)
            self.path_redirects.update(dict(re.findall(r'"(/[^"]*)"\s*:\s*"(/[^"]*)"', src)))
            for m in re.finditer(r"(\w*GONE\w*)\s*=\s*new Set(?:<[^>]*>)?\(\[(.*?)\]\)", src, re.S):
                self.gone_paths |= set(re.findall(r'"(/[^"]*)"', m.group(2)))

    def moved_to(self, p):
        """Where an old address goes now ('gone' for 410), or None for a normal address."""
        if p in self.path_redirects:
            return self.path_redirects[p]
        if p in self.gone_paths:
            return "gone"
        if RETIRED and any(p == r.rstrip("/") or p.startswith(r.rstrip("/") + "/") for r in RETIRED):
            return "gone"
        return None

    def final(self, p, hops=0):
        nxt = self.moved_to(p)
        return p if nxt is None or nxt == "gone" or hops > 5 else self.final(nxt, hops + 1)

    # -------- Markdown content
    def _content(self):
        for kind, folder in (("post", POSTS_DIR), ("page", PAGES_DIR)):
            d = self.repo / folder
            if not d.is_dir():
                continue
            for f in sorted(d.glob("*.md")):
                fm, body = split_doc(f.read_text())
                if not fm.get("slug"):
                    continue
                v = fm.get("vertical") or None
                if kind == "post":
                    url = f"/{v}{BLOG}/{fm['slug']}" if v else f"{BLOG}/{fm['slug']}"
                else:
                    url = f"/{v}/{fm['slug']}" if v else f"/{fm['slug']}"
                date = str(fm.get("date", ""))
                if str(fm.get("draft", "")).lower() == "true":
                    state = "draft"
                elif date > self.today and not self.include_scheduled:
                    state = "scheduled"
                else:
                    state = "live"
                if state == "live" and self.moved_to(url):
                    state = "redirected"
                tags = fm.get("tags") if isinstance(fm.get("tags"), list) else []
                self.docs[url] = dict(path=url, kind=kind, vertical=v, title=str(fm.get("title", "")), date=date,
                                      state=state, body=body, tags=tags, file=str(f.relative_to(self.repo)),
                                      editable="content")
        for url, d in self.docs.items():
            if d["state"] != "live":
                continue
            for href, words in md_links(d["body"]):
                self.add(url, href, words, "body", d["file"])

    def add(self, src, href, words, where, file=""):
        to = site_path(href)
        if not to or to == src:
            return
        self.links.append(dict(src=src, to=to, final=self.final(to), moved=self.moved_to(to),
                               words=norm(strip_md(words)) if words else "", where=where, file=file))

    # -------- pages written in code (home, pricing, hubs, other routes)
    def _imports(self, f):
        out = []
        for spec in re.findall(r'^import[^;]*?from\s+"([^"]+)"', f.read_text(), re.M):
            if spec.startswith("@/"):
                base = self.repo / spec[2:]
            elif spec.startswith("."):
                base = (f.parent / spec).resolve()
            else:
                continue
            for ext in (".tsx", ".ts", "/index.tsx"):
                p = Path(str(base) + ext)
                if p.exists():
                    out.append(p)
                    break
        return out

    def _code_files(self, route):
        start = self.repo / "app" / (route.strip("/") or "") / "page.tsx"
        if not start.exists():
            return []
        seen, todo = [], [start]
        while todo:
            f = todo.pop()
            if f in seen:
                continue
            rel = f.relative_to(self.repo).as_posix()
            if rel.startswith("components/") and f.stem in TEMPLATE_COMPONENTS:
                continue
            if rel.startswith("lib/") and rel not in HUB_FILES:
                continue
            seen.append(f)
            if len(seen) < 60:
                todo.extend(self._imports(f))
        return seen

    def _tsx_links(self, src, f):
        text = f.read_text()
        consts = dict(self.lib_consts)
        consts.update(re.findall(r'const\s+([A-Z_][A-Z0-9_]*)\s*=\s*"([^"]+)"', text))

        def resolve(h):
            if re.fullmatch(r"[A-Z_][A-Z0-9_]*", h):  # href={SOME_PATH}
                return consts.get(h, "")
            return re.sub(r"\$\{([A-Z_][A-Z0-9_]*)\}", lambda m: consts.get(m.group(1), m.group(0)), h)

        rel = f.relative_to(self.repo).as_posix()
        where = "hub-list" if rel in HUB_FILES else "body"
        for m in re.finditer(r'<(Link|a)\b(?:=>|[^>])*?\bhref=(?:"([^"]+)"|\{"([^"]+)"\}|\{`([^`]+)`\}|\{([A-Z_][A-Z0-9_]*)\})(?:=>|[^>])*>(.*?)</\1>',
                             text, re.S):
            words = re.sub(r"\{\"\s*\"\}|\{[^}]*\}", " ", re.sub(r"<[^>]+>", " ", m.group(6)))
            href = resolve(m.group(2) or m.group(3) or m.group(4) or m.group(5))
            if "${" in href:  # a link built at run time from data (a loop over hubs): the real target is not known here
                continue
            self.add(src, href, words, where, rel)
        for m in re.finditer(r'title:\s*"([^"]+)",\s*href:\s*(?:"([^"]+)"|`([^`]+)`)', text):
            self.add(src, resolve(m.group(2) or m.group(3)), m.group(1), "hub-list", rel)

    def _code_pages(self):
        for r in sorted(self.routes):
            if r in self.docs:
                continue
            self.docs[r] = dict(path=r, kind="hub" if r.strip("/") in self.hubs else "route",
                                vertical=r.strip("/") if r.strip("/") in self.hubs else None, title=r, date="",
                                state="live", body="", tags=[], file="", editable="code")
            for f in self._code_files(r):
                self._tsx_links(r, f)
        # Every hub file named in growth.json nextjs.hub_files: a hub's cards may live in any of them, and a card counts once.
        have = {(l["src"], l["to"], l["where"]) for l in self.links}
        for fname in HUB_FILES:
            src = self.read(fname)
            keys = list(re.finditer(r'^ {2}"([a-z0-9-]+)":\s*\{', src, re.M))
            for i, k in enumerate(keys):
                block = src[k.start(): keys[i + 1].start() if i + 1 < len(keys) else len(src)]
                for m in re.finditer(r'\{\s*(?:label:\s*"[^"]*",\s*)?title:\s*"([^"]+)",(?:\s*body:\s*"[^"]*",)?\s*'
                                     r'href:\s*"([^"]+)"', block):
                    if (f"/{k.group(1)}", site_path(m.group(2)), "hub-list") in have:
                        continue
                    have.add((f"/{k.group(1)}", site_path(m.group(2)), "hub-list"))
                    self.add(f"/{k.group(1)}", m.group(2), m.group(1), "hub-list", fname)
                if fname == HUB_FILES[0] and f"/{k.group(1)}" in self.docs:
                    # the hub's readable text: its string literals, one paragraph each
                    self.docs[f"/{k.group(1)}"]["body"] = "\n\n".join(
                        x for x in re.findall(r'"((?:[^"\\]|\\.){40,})"', block) if " " in x and not x.startswith("/"))

    # -------- links every page gets from the templates
    def _templates(self):
        live = [d for d in self.docs.values() if d["state"] == "live"]
        for f in TEMPLATE_FILES:
            where = "footer" if "footer" in f.lower() else "nav"
            text = self.read(f)
            hrefs = set(re.findall(r'href="(/[^"#?]*)', text)) | set(re.findall(r'\[\s*"[^"]+",\s*"(/[^"]*)"\s*\]', text))
            for h in hrefs:
                self.add("*every page*", h, "", where, f)
        for d in live:
            if d["vertical"] and d["kind"] in ("post", "page"):
                self.add(d["path"], f"/{d['vertical']}", "", "breadcrumb", "components/breadcrumbs.tsx")
        posts = [d for d in live if d["kind"] == "post"]
        def topic(p):
            return p["vertical"] or (p["tags"][0] if p["tags"] else "")

        def days(s):
            try:
                return dt.date.fromisoformat(s[:10]).toordinal()
            except ValueError:
                return 0

        if not RELATED_FILE:
            return                                    # the site has no "related posts" box to count
        for d in posts:  # the related-posts box under a post: same topic first, then shared tags, then nearest date
            spec = set(d["tags"]) - RELATED_GENERIC
            ranked = sorted((p for p in posts if p["path"] != d["path"]),
                            key=lambda p: (-(topic(p) == topic(d)), -len(spec & set(p["tags"])),
                                           abs(days(p["date"]) - days(d["date"])), p["path"].rsplit("/", 1)[-1]))
            for p in ranked[:3]:
                self.add(d["path"], p["path"], p["title"], "related", RELATED_FILE)

    # -------- queries on the graph
    def live(self, p):
        d = self.docs.get(p)
        return bool(d) and d["state"] == "live"

    def inbound(self, target):
        return [l for l in self.links if l["final"] == target and l["moved"] is None
                and (l["src"] == "*every page*" or self.live(l["src"]))]

    def outbound(self, src):
        return [l for l in self.links if l["src"] == src]

    def silo_of(self, p):
        d = self.docs.get(p) or {}
        if d.get("vertical"):
            return d["vertical"]
        seg = p.strip("/").split("/")[0]
        return seg if seg in self.hubs else None


# ---------------------------------------------------------------- Search Console and research
class Search:
    def __init__(self, today):
        self.ok = DB.exists()
        self.queries, self.totals = {}, {}
        if not self.ok:
            return
        c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        for path, q, cl, im, pos in c.execute(
                "SELECT path, query, clicks, impressions, position FROM search_queries s WHERE snapshot ="
                " (SELECT max(snapshot) FROM search_queries t WHERE t.path = s.path)"):
            self.queries.setdefault(path, []).append(dict(query=q, clicks=cl, impr=im, pos=pos))
        since90 = (dt.date.fromisoformat(today) - dt.timedelta(days=90)).isoformat()
        since28 = (dt.date.fromisoformat(today) - dt.timedelta(days=28)).isoformat()
        for path, i90, c90, i28, c28 in c.execute(
                "SELECT path, sum(impressions), sum(clicks), sum(CASE WHEN day >= ? THEN impressions END),"
                " sum(CASE WHEN day >= ? THEN clicks END) FROM search WHERE day >= ? GROUP BY path",
                (since28, since28, since90)):
            self.totals[path] = dict(impr90=i90 or 0, clicks90=c90 or 0, impr28=i28 or 0, clicks28=c28 or 0)
        self.clusters = dict(c.execute("SELECT path, cluster FROM site_pages"))
        c.close()

    def total(self, p):
        return self.totals.get(p, dict(impr90=0, clicks90=0, impr28=0, clicks28=0))


def research_phrases(files):
    """(own, prompts): the dossier's "Own" search list, and every Prompt/Search/Question cell of the research tables."""
    own, prompts = [], []
    for f in files:
        text = Path(f).read_text()
        for m in re.finditer(r"\*\*Own[^*]*\*\*:?\s*(.+)", text):
            own += [strip_md(x).strip(" .") for x in m.group(1).split("·") if strip_md(x).strip(" .")]
        lines = text.splitlines()
        for i, line in enumerate(lines[:-1]):
            if not line.startswith("|") or not re.match(r"^\|[\s:|-]+\|$", lines[i + 1].strip()):
                continue
            head = [norm(strip_md(c)) for c in line.strip().strip("|").split("|")]
            col = next((j for j, h in enumerate(head) if h in ("prompt", "search", "question", "searches")), None)
            if col is None:
                continue
            for row in lines[i + 2:]:
                if not row.startswith("|"):
                    break
                cells = row.strip().strip("|").split("|")
                if col < len(cells):
                    cell = strip_md(cells[col]).strip(" \"'“”")
                    if len(cell.split()) >= 2 and not cell.startswith(("**", "Total")):
                        prompts.append(cell)
    dedupe = lambda xs: list(dict.fromkeys(x for x in xs if x))
    return dedupe(own), dedupe(prompts)


# ---------------------------------------------------------------- the planner
def jaccard(a, b):
    a, b = set(a) - {"for", "the", "a", "of", "in", "to", "and"}, set(b) - {"for", "the", "a", "of", "in", "to", "and"}
    return len(a & b) / len(a | b) if a and b else 0.0


def plan(site, gsc, target, research_files, limit):
    tdoc = site.docs.get(target)
    if not tdoc:
        sys.exit(f"link_map: {target} is no page of the site")
    silo = site.silo_of(target)
    own, prompts = research_phrases(research_files)
    # the target's search words: its own queries, plus the queries of pages that now 301 into it
    feeders = [target] + [p for p in gsc.queries if p != target and site.final(p) == target]
    tq = {}
    for p in feeders:
        for q in gsc.queries.get(p, []):
            if any(b and (b in q["query"].lower()) for b in BRAND_WORDS):
                continue                              # a search for the brand's own name says nothing about a topic
            tq[q["query"]] = tq.get(q["query"], 0) + q["impr"]
    buying = {q: i for q, i in tq.items() if set(toks(q)) & PRODUCT_WORDS}
    pool = sorted(set(own) | set(buying), key=lambda q: (-(tq.get(q, 0)), q))
    # distinctive topic words: in the phrases the page should own, rare across the site's live pages. A word followed
    # by a non-generic word keeps it ("zero turn"), so "zero" alone never counts.
    live = [d for d in site.docs.values() if d["state"] == "live" and d["body"]]
    df = {}
    for d in live:
        for w in set(toks(d["title"] + " " + strip_md(d["body"]))):
            df[w] = df.get(w, 0) + 1
    topic = set()
    for ph in (own or pool):
        pt = toks(ph)
        for i, w in enumerate(pt):
            if w not in GENERIC and len(w) > 3 and df.get(w, 0) / max(1, len(live)) < 0.3:
                nxt = pt[i + 1] if i + 1 < len(pt) and pt[i + 1] not in GENERIC else None
                topic.add(f"{w} {nxt}" if nxt else w)
    rare = {w for w, n in df.items() if n / max(1, len(live)) < 0.3 and w not in GENERIC and len(w) > 3}

    def has_topic(text):
        n = " " + " ".join(toks(text)) + " "
        return any(f" {t} " in n for t in topic)

    inb = site.inbound(target)
    body_in = [l for l in inb if l["where"] in ("body", "hub-list")]
    linked_from = {l["src"] for l in body_in}
    anchors_to = {}  # rule 90: words -> set of targets, site-wide (body links only)
    for l in site.links:
        if l["where"] == "body" and l["words"] and l["moved"] is None:
            anchors_to.setdefault(l["words"], set()).add(l["final"])
    used = {l["words"] for l in body_in}

    def free(a):
        return norm(a) not in used and anchors_to.get(norm(a), {target}) <= {target}

    cands = []
    for d in live:
        p = d["path"]
        if p == target or p in linked_from or d["kind"] in ("route",) and p not in ("/", "/pricing"):
            continue
        sc = dict(cluster=0.0, gsc=0.0, strength=0.0, mention=0.0, buyer=0.0)
        why = []
        same = silo and (site.silo_of(p) == silo or gsc.clusters.get(p) == silo)
        if same:
            sc["cluster"] = 3
            why.append(f"same silo ({silo})")
        overlap = [q for q in gsc.queries.get(p, []) if any(q["query"] == t or jaccard(toks(q["query"]), toks(t)) >= 0.6
                                                            for t in tq)]
        oimp = sum(q["impr"] for q in overlap)
        if oimp:
            sc["gsc"] = round(min(4, math.log2(1 + oimp / 5)), 2)
            why.append(f"ranks for the target's words: " + "; ".join(
                f"'{q['query']}' {q['impr']} impr, pos {q['pos']:.1f}" for q in sorted(overlap, key=lambda q: -q['impr'])[:3]))
            if not same and gsc.clusters.get(p) == "blog":
                sc["cluster"] = 1
                why.append("old generic post in the topic")
        t = gsc.total(p)
        if t["impr90"]:
            sc["strength"] = round(min(2, math.log10(1 + t["impr90"]) / 1.5), 2)
            why.append(f"90 d: {t['impr90']} impr, {t['clicks90']} clicks")
        best, kind = None, None
        for s in sentences(d["body"]):
            plain = s
            for m in re.finditer(r"(?<!!)\[([^\]]+)\]\([^)]+\)", s):
                plain = plain.replace(m.group(0), "⟦" + "x" * len(m.group(1)) + "⟧")
            ns, st, tp = norm(plain), set(toks(plain)), has_topic(plain)
            hit = next((ph for ph in pool if re.search(r"\b" + re.escape(norm(ph)) + r"\b", ns)), None)
            if hit:
                best, kind = (s, hit), 3
                break
            if tp and st & PRODUCT_WORDS and (kind or 0) < 1.5:
                best, kind = (s, None), 1.5
            elif tp and not kind:
                best, kind = (s, None), 1
        if kind:
            sc["mention"] = kind
            why.append({3: f"text already says '{best[1]}' (unlinked)", 1.5: "a sentence names the product and topic",
                        1: "a sentence names the topic"}[kind])
        head = toks(d["title"] + " " + " ".join(re.findall(r"^#{2,3} (.+)$", d["body"], re.M)))
        hits = [q for q in prompts if has_topic(q) and len((set(toks(q)) & rare) & set(head)) >= 2]
        if hits:
            sc["buyer"] = min(2, 0.5 * len(hits))
            why.append(f"answers buyer questions: '{hits[0]}'" + (f" (+{len(hits) - 1})" if len(hits) > 1 else ""))
        total = round(sum(sc.values()), 2)
        if total >= 1.5 and (sc["mention"] or sc["gsc"] or sc["cluster"] >= 3):
            cands.append(dict(source=p, title=d["title"], file=d["file"], editable=d["editable"], score=total,
                              scores=sc, why=why, sentence=best[0] if best else None,
                              phrase=best[1] if best else None))
    cands.sort(key=lambda c: (-c["score"], c["source"]))
    cands = cands[:limit]

    taken = set()

    brand = CFG.get("product", "")
    branded = [f"{brand}'s {a}" for a in pool] if brand else []

    def pick(prefer=None):
        # exact search words first; once each is used, the brand + search words ("<Brand>'s <search words>")
        for a in ([prefer] if prefer else []) + pool + branded:
            if a and free(a) and norm(a) not in taken:
                taken.add(norm(a))
                return a
        return None

    for c in cands:
        c["anchor"] = pick(c["phrase"])
        if c["sentence"]:
            c["where"] = "link the words in this sentence" if c["phrase"] else "reword this sentence to carry the anchor"
        else:
            c["where"] = (f"add one sentence where the post names the problem: \"... with [{c['anchor']}]({target}), "
                          "and say what the reader gets.\"")

    # anchor fixes on links already there: duplicate words, or words that carry no search phrase
    seen, fixes = {}, []
    for l in sorted(body_in, key=lambda l: -gsc.total(l["src"])["impr90"]):
        if l["where"] != "body":
            continue
        first = seen.get(l["words"])
        searchy = any(norm(ph) in l["words"] for ph in pool)
        seen.setdefault(l["words"], l["src"])
        if first or not searchy:
            fixes.append(dict(source=l["src"], file=l["file"], editable=site.docs[l["src"]]["editable"], now=l["words"],
                              anchor=pick(), why=f"same words as {first}" if first else "no search phrase in the words"))
    # outbound: hub -> every spoke, spoke -> hub and closest siblings
    out = site.outbound(target)
    have = {l["final"] for l in out if l["where"] in ("body", "hub-list")}
    spokes = sorted(p for p, d in site.docs.items() if d["state"] == "live" and p != target and site.silo_of(p) == silo
                    and d["kind"] in ("post", "page"))
    want = spokes if tdoc["kind"] == "hub" else [f"/{silo}"] + spokes if silo else []
    outs = []
    for p in want:
        if p in have or p == target:
            continue
        qs = sorted(gsc.queries.get(p, []), key=lambda q: -q["impr"])
        words = next((q["query"] for q in qs if anchors_to.get(norm(q["query"]), {p}) <= {p}), None)
        outs.append(dict(target=p, title=site.docs[p]["title"], anchor=words or site.docs[p]["title"],
                         impr90=gsc.total(p)["impr90"]))
    if tdoc["kind"] != "hub":
        outs = outs[:4]
    return dict(target=target, silo=silo, pool=pool, own=own, prompts=prompts[:40], topic=sorted(topic),
                target_queries=sorted(tq.items(), key=lambda x: -x[1]), suggestions=cands, anchor_fixes=fixes,
                outbound_missing=outs, outbound_have=sorted(have), inbound_counts=counts(inb))


def counts(inb):
    out = {}
    for l in inb:
        out.setdefault(l["where"], set()).add(l["src"])
    return {k: len(v) for k, v in sorted(out.items())}


# ---------------------------------------------------------------- flags (rules 75, 88, 89, 90)
FLAGS = {
    "orphan": "no other live page links to it from its content (body text or a hub list)",
    "weak": "only one other page links to it from its content",
    "no-hub": "a post under a vertical whose text does not link to its silo's top page",
    "not-on-hub": "a post under a vertical that its silo's guide list does not hold",
    "siblings<2": "a post in a vertical with 2+ other live posts that links to fewer than 2 of them",
    "to-redirect": "a content link to an old address that now redirects",
    "to-gone": "a content link to an address that answers 410",
    "to-not-live": "a content link to a draft or a future-dated post (shown as plain text)",
    "to-unknown": "a content link to a site path that is no live post, page or route",
    "dup-anchor": "the same link words go to two or more different pages (rule 90)",
}
CONTENT = ("body", "hub-list")


def anchor_targets(site):
    """{words: {final target}} over every live content link on the site (rule 90: one anchor, one target)."""
    out = {}
    for l in site.links:
        if l["where"] in CONTENT and l["words"] and site.live(l["src"]) and l["moved"] != "gone":
            out.setdefault(l["words"], set()).add(l["final"])
    return out


def page_flags(site, p, anchors, explicit=False):
    """[(flag, detail)] for one page: orphan/weak, the cluster flags, dead-end links and duplicate anchors."""
    d = site.docs[p]
    out_links = [l for l in site.outbound(p) if l["where"] in CONTENT]
    flags = []
    ranks = d["kind"] in ("post", "hub") or (d["kind"] == "page" and d["vertical"]) or (explicit and p != "/")
    srcs = {l["src"] for l in site.inbound(p) if l["where"] in CONTENT and l["src"] != p}
    if ranks and not srcs:
        flags.append(("orphan", "0 content links in"))
    elif ranks and len(srcs) == 1:
        flags.append(("weak", f"1 content link in, from {next(iter(srcs))}"))
    v = d["vertical"]
    if d["kind"] == "post" and v:
        hub = f"/{v}"
        if not any(l["final"] == hub and l["where"] == "body" for l in out_links):
            flags.append(("no-hub", f"no body link up to {hub}"))
        if HUB_FILES and v in site.hubs and not any(l["src"] == hub and l["where"] == "hub-list" for l in site.inbound(p)):
            flags.append(("not-on-hub", f"{hub}'s guide list does not hold it"))
        mates = [q for q, e in site.docs.items() if q != p and e["kind"] == "post" and e["vertical"] == v and e["state"] == "live"]
        hit = len({l["final"] for l in out_links} & set(mates))
        if len(mates) >= 2 and hit < 2:
            flags.append(("siblings<2", f"links to {hit} of {len(mates)} sibling posts"))
    for l in out_links:
        tgt = site.docs.get(l["to"])
        if l["moved"] == "gone":
            flags.append(("to-gone", f"\"{l['words']}\" -> {l['to']} (410)  ({l['file']})"))
        elif l["moved"]:
            flags.append(("to-redirect", f"\"{l['words']}\" -> {l['to']} redirects to {l['final']}  ({l['file']})"))
        elif tgt and tgt["state"] not in ("live", "redirected"):
            flags.append(("to-not-live", f"\"{l['words']}\" -> {l['to']} ({tgt['state']})  ({l['file']})"))
        elif not tgt and not re.match(r"^" + re.escape(BLOG) + r"/page/\d+$", l["to"]) and l["to"] != "/rss.xml":
            flags.append(("to-unknown", f"\"{l['words']}\" -> {l['to']}  ({l['file']})"))
        elif l["words"] and len(anchors.get(l["words"], ())) > 1:
            others = sorted(anchors[l["words"]] - {l["final"]})
            flags.append(("dup-anchor", f"\"{l['words']}\" -> {l['final']}; the same words also go to {', '.join(others[:3])}"))
    return list(dict.fromkeys(flags))


def cmd_check(site, gsc, a):
    anchors = anchor_targets(site)
    if a.all:
        pages = [p for p, d in sorted(site.docs.items()) if d["state"] == "live"]
    else:
        if a.path not in site.docs or site.docs[a.path]["state"] != "live":
            print(f"link_map check: {a.path} is no live post, page or route in {site.repo}", file=sys.stderr)
            return 2
        pages = [a.path]
    rows = [dict(path=p, kind=site.docs[p]["kind"], vertical=site.docs[p]["vertical"] or "",
                 **{"in": len({l["src"] for l in site.inbound(p) if l["where"] in CONTENT and l["src"] != p}),
                    "out": len({l["final"] for l in site.outbound(p) if l["where"] in CONTENT})},
                 flags=[dict(flag=f, detail=t) for f, t in page_flags(site, p, anchors, not a.all)])
            for p in pages]
    bad = [r for r in rows if r["flags"]]
    if a.json:
        print(json.dumps(dict(pages=len(rows), flagged=len(bad), rows=rows, legend=FLAGS), indent=1))
        return 1 if bad else 0
    count = {}
    for r in bad:
        for f in {x["flag"] for x in r["flags"]}:
            count[f] = count.get(f, 0) + 1
    print(f"Link check, {site.repo.name}, {site.today}: {len(rows)} page(s), {len(bad)} flagged")
    print("flags: " + ", ".join(f"{f} {count.get(f, 0)}" for f in FLAGS))
    for r in bad:
        for f in r["flags"]:
            print(f"FAIL {f['flag']:<11} {r['path']}  {f['detail']}")
    print("Legend: " + "; ".join(f"{k} = {v}" for k, v in FLAGS.items()))
    return 1 if bad else 0


# ---------------------------------------------------------------- commands
def cmd_inbound(site, gsc, a):
    inb = sorted(site.inbound(a.path), key=lambda l: (l["where"], l["src"]))
    if a.json:
        return print(json.dumps(dict(target=a.path, counts=counts(inb), links=inb), indent=1))
    print(f"Inbound links to {a.path} ({site.repo.name}, {site.today})")
    print("Distinct source pages by where: " + ", ".join(f"{k} {v}" for k, v in counts(inb).items()))
    for l in inb:
        imp = gsc.total(l["src"])["impr90"]
        print(f"  {l['where']:<10} {l['src']}  \"{l['words']}\"" + (f"  [{imp} impr/90d]" if imp else ""))
    words = [l["words"] for l in inb if l["where"] == "body"]
    dups = sorted({w for w in words if words.count(w) > 1})
    print(f"Body anchors: {len(set(words))} different words over {len(words)} links" +
          (f"; repeated: {', '.join(dups)}" if dups else ""))


def cmd_outbound(site, gsc, a):
    out = site.outbound(a.path)
    if a.json:
        return print(json.dumps(dict(source=a.path, links=out), indent=1))
    print(f"Outbound links from {a.path} ({len(out)}; nav and footer are on every page and not listed)")
    for l in sorted(out, key=lambda l: (l["where"], l["to"])):
        flag = ""
        if l["moved"]:
            flag = "  GONE (410)" if l["moved"] == "gone" else f"  REDIRECT -> {l['final']}"
        elif l["to"] in site.docs and site.docs[l["to"]]["state"] != "live":
            flag = f"  NOT LIVE ({site.docs[l['to']]['state']})"
        elif l["to"] not in site.docs and not re.match(r"^" + re.escape(BLOG) + r"/page/\d+$", l["to"]):
            flag = "  UNKNOWN address"
        print(f"  {l['where']:<10} {l['to']}  \"{l['words']}\"{flag}  ({l['file']})")


def cmd_orphans(site, gsc, a):
    rows = []
    for p, d in sorted(site.docs.items()):
        if d["state"] != "live" or not (d["kind"] == "post" or (d["kind"] == "page" and d["vertical"])
                                        or d["kind"] == "hub"):
            continue
        inb = site.inbound(p)
        content = {l["src"] for l in inb if l["where"] in ("body", "hub-list")}
        if len(content) < 2:
            rows.append(dict(path=p, content_in=len(content), other=counts([l for l in inb if l["src"] not in content]),
                             impr90=gsc.total(p)["impr90"]))
    if a.json:
        return print(json.dumps(rows, indent=1))
    print(f"Pages with fewer than 2 content links in (rule 88), {site.repo.name}, {site.today}")
    for r in rows:
        print(f"  {'ORPHAN' if r['content_in'] == 0 else 'weak  '} {r['path']}  [{r['impr90']} impr/90d]  "
              f"template only: {r['other'] or 'none'}")


def cmd_suggest(site, gsc, a):
    files = sorted({f for g in (a.research or []) for f in glob.glob(str(PROJECT / g))})
    if not a.research:
        stem = "-".join(a.path.strip("/").split("/")[0].split("-")[:2])
        files = sorted(glob.glob(str(PROJECT / "research" / f"*{stem}*.md")))
    r = plan(site, gsc, a.path, files, a.limit)
    if a.json:
        return print(json.dumps(r, indent=1, default=list))
    print(f"Link plan for {r['target']}  (silo {r['silo']}, site {site.repo.name}, {site.today})")
    print(f"Inbound now, distinct sources by where: {r['inbound_counts']}")
    print(f"Research read: {', '.join(Path(f).name for f in files) or 'none'}")
    print("Search words (anchor pool, most impressions first): " + " | ".join(r["pool"][:16]))
    print("Distinctive topic words: " + ", ".join(r["topic"]))
    print(f"\nA. New inbound links ({len(r['suggestions'])})")
    for i, c in enumerate(r["suggestions"], 1):
        print(f"{i:>2}. {c['source']}  score {c['score']}  {c['scores']}  [{c['editable']}: {c['file'] or 'code'}]")
        print(f"    anchor: \"{c['anchor']}\"   where: {c['where']}")
        if c["sentence"]:
            print(f"    sentence: {c['sentence'][:400]}")
        print(f"    why: {'; '.join(c['why'])}")
    print(f"\nB. Anchor fixes on links already there ({len(r['anchor_fixes'])})")
    for f in r["anchor_fixes"]:
        print(f"  {f['source']}: \"{f['now']}\" -> \"{f['anchor']}\"  ({f['why']}; {f['editable']}: {f['file']})")
    print(f"\nC. Outbound from {r['target']}: links it should add ({len(r['outbound_missing'])})")
    for o in r["outbound_missing"]:
        print(f"  {o['target']}  anchor \"{o['anchor']}\"  [{o['impr90']} impr/90d]")
    print(f"   already links (body or hub list): {len(r['outbound_have'])}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["inbound", "outbound", "orphans", "suggest", "check"])
    ap.add_argument("path", nargs="?")
    ap.add_argument("--repo", default=str(SITE_REPO), help="site checkout or worktree (default: growth.json site_repo)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--research", action="append", help="glob of research files, relative to the kit (repeatable)")
    ap.add_argument("--include-scheduled", action="store_true")
    ap.add_argument("--all", action="store_true", help="check: every live page")
    a = ap.parse_args()
    if a.command != "orphans" and not a.path and not (a.command == "check" and a.all):
        ap.error(f"{a.command} needs a path")
    if a.path:
        a.path = site_path(a.path) or a.path
    site = Site(a.repo, a.include_scheduled)
    gsc = Search(site.today)
    return {"inbound": cmd_inbound, "outbound": cmd_outbound, "orphans": cmd_orphans, "suggest": cmd_suggest,
            "check": cmd_check}[a.command](site, gsc, a) or 0


if __name__ == "__main__":
    sys.exit(main())
