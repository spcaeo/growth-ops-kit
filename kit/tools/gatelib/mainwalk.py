"""Read the text of <main> fold by fold (2.8.0): one place for the checks that compare folds (words.fact-repeats) or read every
visible sentence (words.internal-labels). A fold is a section[data-fold]; a page with none uses its top-level sections."""
from __future__ import annotations

import re

from techseo.dom import find_all

from . import domx

HARD_SKIP = {"script", "style", "noscript", "template", "head", "title", "svg", "canvas", "math", "iframe"}
OUTSIDE = "(outside the folds)"
SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"“‘'(])")


def hidden(n) -> bool:
    return "hidden" in n.attrs or bool(re.search(r"display\s*:\s*none", n.get("style")))


def fold_name(s, i):
    return s.get("data-fold") or s.get("id") or s.get("aria-label") or f"#{i + 1}"


def fold_nodes(m):
    """{id(section): name} for every fold of <main>: sections with data-fold, else the top-level sections."""
    secs = [s for s in find_all(m, "section") if "data-fold" in s.attrs]
    if not secs:
        secs = [s for s in find_all(m, "section") if not any(a.tag == "section" for a in s.ancestors() if a is not m)]
    return {id(s): fold_name(s, i) for i, s in enumerate(secs)}


def units(ctx, drop=None):
    """[(fold name, text)]: one entry per run of text of <main>, in reading order, each tied to its fold. `drop(node)` true
    cuts that element (and what is inside it) out. Hidden parts, scripts and drawings are never read."""
    return units_of(ctx.root(), drop)


def units_of(root, drop=None):
    """The same for any parsed page (2.8.2: words.own-copy reads the site's other built pages)."""
    m = domx.main(root)
    folds = fold_nodes(m)
    out = []

    def flush(buf, fold):
        t = re.sub(r"\s+", " ", "".join(buf)).strip()
        if t:
            out.append((fold, t))
        buf.clear()

    def walk(n, fold, buf):
        for c in n.children:
            if isinstance(c, str):
                buf.append(c)
                continue
            if c.tag in HARD_SKIP or hidden(c) or (drop and drop(c)):
                continue
            f2 = folds.get(id(c), fold)
            if c.tag in domx.INLINE and f2 == fold:
                if c.tag == "br":
                    buf.append(" ")
                walk(c, fold, buf)
                continue
            flush(buf, fold)
            inner = []
            walk(c, f2, inner)
            flush(inner, f2)

    first = []
    walk(m, OUTSIDE, first)
    flush(first, OUTSIDE)
    return out


def sentences(text):
    return [s.strip() for s in SENTENCE.split(text) if s.strip()]

