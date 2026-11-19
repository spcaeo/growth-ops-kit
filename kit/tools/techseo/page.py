"""The page under test: one fetch, parsed once, with helpers every check module shares."""
from __future__ import annotations

import json
import re
import urllib.parse

from .dom import find, find_all, parse


class Page:
    def __init__(self, fetcher, rep, url, mode="dev", site_origin="https://example.com",
                 keyword="", build_dir=None, offline=False, old_hosts=()):
        self.f, self.rep, self.url, self.mode = fetcher, rep, url, mode
        self.site_origin = site_origin.rstrip("/")
        self.site_host = urllib.parse.urlsplit(self.site_origin).netloc.lower()
        self.keyword = keyword.lower().strip()
        self.old_hosts = [h.lower() for h in old_hosts if h]      # retired hosts and old server addresses (growth.json old_hosts)
        self.build_dir = build_dir
        self.path = urllib.parse.urlsplit(url).path or "/"
        self.origin = "{0.scheme}://{0.netloc}".format(urllib.parse.urlsplit(url))
        self.host = urllib.parse.urlsplit(url).netloc.lower()
        self.resp = fetcher.get(url)
        self.html = self.resp.text()
        self.root = parse(self.html)
        self.head = find(self.root, "head")
        self.body = find(self.root, "body") or self.root
        self.main = find(self.root, "main") or self.body
        self.live = mode == "prod"

    # ---- small lookups -------------------------------------------------------------
    def metas(self, key, value):
        return [m for m in find_all(self.root, "meta") if m.get(key).lower() == value.lower()]

    def meta_content(self, name=None, prop=None):
        ms = self.metas("name", name) if name else self.metas("property", prop)
        return ms[0].get("content") if ms else None

    def title_nodes(self):
        return [t for t in find_all(self.root, "title") if not t.in_tag("svg")]

    def title(self):
        t = self.title_nodes()
        return t[0].all_text().strip() if t else None

    def canonicals(self):
        return [l for l in find_all(self.root, "link") if "canonical" in l.get("rel").lower().split()]

    def in_head(self, node):
        return node.in_tag("head")

    def headings(self):
        return [n for n in self.root.iter() if re.fullmatch(r"h[1-6]", n.tag)]

    def visible_text(self):
        return self.main.all_text(visible=True)

    def words(self, text=None):
        t = self.visible_text() if text is None else text
        return len(re.findall(r"\b[\w'’-]+\b", t))

    def links(self):
        return [a for a in find_all(self.root, "a")]

    def imgs(self):
        return find_all(self.root, "img")

    def abs(self, href):
        return urllib.parse.urljoin(self.url, href)

    def is_internal(self, href):
        h = urllib.parse.urlsplit(self.abs(href)).netloc.lower()
        return h in (self.host, self.site_host, "www." + self.site_host)

    def site_path(self, href):
        """Path (and query) of an internal URL, whatever host it names."""
        p = urllib.parse.urlsplit(self.abs(href))
        return p.path or "/"

    # ---- JSON-LD ---------------------------------------------------------------------
    def jsonld_scripts(self):
        return [s for s in find_all(self.root, "script") if s.get("type").lower() == "application/ld+json"]

    def jsonld_nodes(self):
        """(flat list of nodes, list of parse errors). Handles arrays and @graph."""
        nodes, errors = [], []
        for s in self.jsonld_scripts():
            raw = s.own_text().strip()
            try:
                data = json.loads(raw)
            except Exception as e:
                errors.append(str(e)[:80])
                continue
            stack = data if isinstance(data, list) else [data]
            for d in stack:
                if isinstance(d, dict) and "@graph" in d:
                    nodes.extend(x for x in d["@graph"] if isinstance(x, dict))
                elif isinstance(d, dict):
                    nodes.append(d)
        return nodes, errors

    @staticmethod
    def types(node):
        t = node.get("@type", [])
        t = [t] if isinstance(t, str) else list(t)
        return [x.replace("https://schema.org/", "").replace("http://schema.org/", "") for x in t]
