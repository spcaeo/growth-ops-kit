"""Small DOM helpers the page checks share (on top of techseo.dom)."""
from __future__ import annotations

import re

from techseo.dom import find, find_all

SECONDARY = ("button-light", "button-outline", "button-secondary", "outline", "secondary", "text-link")
CHROME = ("header", "nav", "footer", "dialog")


def classes(n):
    return n.get("class").split()


def has_cls(n, pattern):
    """True when one class token matches the regex pattern (full match)."""
    return any(re.fullmatch(pattern, c) for c in classes(n))


def up(n, pred):
    """The nearest ancestor (or the node itself) for which pred is true, else None."""
    cur = n
    while cur is not None:
        if getattr(cur, "tag", None) and pred(cur):
            return cur
        cur = cur.parent
    return None


def in_chrome(n, ctx_root=None):
    """Inside the site header, nav, footer or a dialog (not the page's own content). A <header> or <footer> inside
    <main> is a fold's own heading block, not site chrome."""
    anc = list(n.ancestors())
    in_main = any(a.tag == "main" for a in anc)
    for a in anc:
        if a.tag in ("nav", "dialog") or has_cls(a, r"site-(header|footer)|sticky-cta"):
            return True
        if a.tag in ("header", "footer") and not in_main:
            return True
    return False


INLINE = {"a", "span", "b", "strong", "em", "i", "small", "sup", "sub", "abbr", "code", "time", "mark", "q", "s", "u", "kbd", "wbr", "br"}
SKIP = {"script", "style", "noscript", "template", "head", "title", "svg"}


def text(n):
    """Visible text; block elements are separated by a space so words of two blocks never run together."""
    if n is None:
        return ""
    parts = []

    def walk(x):
        if x.tag in SKIP and x is not n or "hidden" in x.attrs or re.search(r"display\s*:\s*none", x.get("style")):
            return
        block = x.tag not in INLINE
        if block:
            parts.append(" ")
        for c in x.children:
            if isinstance(c, str):
                parts.append(c)
            else:
                walk(c)
        if block:
            parts.append(" ")
    if n.tag == "title":
        return re.sub(r"\s+", " ", n.own_text()).strip()
    walk(n)
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def main(root):
    return find(root, "main") or find(root, "body") or root


def body(root):
    return find(root, "body") or root


def label(a):
    """A link's visible label; a long/short pair (sc-long / sc-short) counts once, by its long form."""
    for c in a.iter():
        if c is not a and has_cls(c, r".*-long|sc-long"):
            return text(c).strip()
    return re.sub(r"\s*[→↗]\s*$", "", text(a)).strip()


def booking_links(ctx, root):
    """Every link that goes to the booking path (the conversion path or the contact path in growth.json)."""
    out = []
    for a in find_all(root, "a"):
        p = ctx.internal_path(a.get("href"))
        if p and p.rstrip("/") in ctx.booking_paths():
            out.append(a)
    return out


def is_primary(a):
    """A booking link drawn as a solid button (not an outline, not a text link)."""
    cl = classes(a)
    looks_button = any(c in ("button", "btn") or c.endswith("-button") or c.endswith("-cta") or c.startswith(("button-", "btn-"))
                       for c in cl)
    # a secondary variant in any naming: "button-outline", "btn--ghost", "btn-secondary", "btn--link" ...
    second = any(c in SECONDARY or re.search(r"(?:^|-)(secondary|ghost|outline|light|link|text|tertiary|quiet)$", c) for c in cl)
    return looks_button and not second


def in_call_dialog(n, cls="call-dialog"):
    """Inside the site's call dialog: the kit's class, or the project's own (growth.json features.call_dialog.class)."""
    return any(has_cls(a, re.escape(cls)) for a in n.ancestors())


def first_section(root):
    """The first screen: the first section (or block) inside <main> that holds the H1."""
    m = main(root)
    h1 = find(m, "h1")
    if h1 is None:
        return None
    sec = up(h1, lambda x: x.tag in ("section", "header", "article") and x is not m)
    return sec or h1.parent


def top_sections(root):
    """The page's folds: the outermost <section> elements inside main (not in chrome)."""
    m = main(root)
    out = []
    for s in find_all(m, "section"):
        if not any(a.tag == "section" for a in s.ancestors()) and not in_chrome(s):
            out.append(s)
    return out


def jsonld(root):
    import json
    nodes = []
    for s in find_all(root, "script"):
        if s.get("type").lower() != "application/ld+json":
            continue
        try:
            d = json.loads(s.own_text())
        except ValueError:
            continue
        stack = d if isinstance(d, list) else [d]
        for x in stack:
            if isinstance(x, dict) and "@graph" in x:
                nodes += [g for g in x["@graph"] if isinstance(g, dict)]
            elif isinstance(x, dict):
                nodes.append(x)
    return nodes


def types_of(node):
    t = node.get("@type", [])
    return [t] if isinstance(t, str) else list(t)


def walk_json(x):
    if isinstance(x, dict):
        yield x
        for v in x.values():
            yield from walk_json(v)
    elif isinstance(x, list):
        for v in x:
            yield from walk_json(v)


def page_title(root):
    """The document's <title>, never an inline SVG's <title> (an accessible name for a drawing). On the dev server Next
    streams the head's <title> after the body, so the first <title> in the HTML can be an SVG's (seen on a real site)."""
    from techseo.dom import find_all
    inside = {id(n) for svg in find_all(root, "svg") for n in svg.iter() if n.tag == "title"}
    return next((n for n in find_all(root, "title") if id(n) not in inside), None)
