"""A small, forgiving HTML tree builder (standard library only)."""
from __future__ import annotations

import re
from html.parser import HTMLParser

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
        "source", "track", "wbr", "param"}
RAW = {"script", "style"}
SKIP_TEXT = {"script", "style", "noscript", "template", "head", "title"}


class Node:
    __slots__ = ("tag", "attrs", "parent", "children", "text", "pos", "idx")

    def __init__(self, tag, attrs, parent, pos=0):
        self.tag, self.attrs, self.parent = tag, dict(attrs), parent
        self.children, self.text, self.pos, self.idx = [], [], pos, 0

    def get(self, k, d=""):
        v = self.attrs.get(k)
        return d if v is None else v

    def iter(self):
        yield self
        for c in self.children:
            if isinstance(c, Node):
                yield from c.iter()

    def ancestors(self):
        p = self.parent
        while p is not None:
            yield p
            p = p.parent

    def in_tag(self, *tags):
        return any(a.tag in tags for a in self.ancestors())

    def own_text(self):
        return "".join(c for c in self.children if isinstance(c, str))

    def all_text(self, visible=False):
        parts = []
        def walk(n):
            if visible and (n.tag in SKIP_TEXT or "hidden" in n.attrs
                            or re.search(r"display\s*:\s*none", n.get("style"))):
                return
            for c in n.children:
                if isinstance(c, Node):
                    walk(c)
                else:
                    parts.append(c)
        walk(self)
        return re.sub(r"\s+", " ", "".join(parts)).strip()

    def elements(self):
        return [c for c in self.children if isinstance(c, Node)]


class _Builder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#root", {}, None)
        self.cur = self.root
        self.n = 0
        self.order = 0

    def _new(self, tag, attrs):
        node = Node(tag, {k: (v if v is not None else "") for k, v in attrs}, self.cur,
                    self.getpos()[0] * 100000 + self.getpos()[1])
        self.order += 1
        node.idx = self.order
        self.cur.children.append(node)
        return node

    def handle_starttag(self, tag, attrs):
        node = self._new(tag, attrs)
        if tag not in VOID:
            self.cur = node

    def handle_startendtag(self, tag, attrs):
        self._new(tag, attrs)

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        n = self.cur
        while n is not None and n.tag != tag:
            n = n.parent
        if n is not None and n.parent is not None:
            self.cur = n.parent

    def handle_data(self, data):
        self.cur.children.append(data)


def parse(html: str) -> Node:
    b = _Builder()
    b.feed(html)
    b.close()
    return b.root


def find_all(root: Node, tag=None, **attrs):
    out = []
    for n in root.iter():
        if tag and n.tag != tag:
            continue
        if all(n.attrs.get(k.replace("_", "-")) == v for k, v in attrs.items()):
            out.append(n)
    return out


def find(root, tag=None, **attrs):
    r = find_all(root, tag, **attrs)
    return r[0] if r else None
