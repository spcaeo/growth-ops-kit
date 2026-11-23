"""Rule 157 on the served page, for every stack (2.5.0): no two sibling pages share a hero picture or a hero animation.
hero.unique used to read a Next.js component tree only, so on any other stack it printed SKIP and 128 pages of one site
shipped with 14 hero designs between them. This version reads the first screen of the page and of its siblings (the
same cluster and depth, from inventory/inventory.json) on the same preview server."""
from __future__ import annotations

import hashlib
import json
import re
import urllib.request
from urllib.parse import urlsplit

import paths  # noqa: E402  kit/tools/paths.py

from techseo.dom import parse

from . import domx
from .core import Skip, check

ANIM = re.compile(r"(?i)(^|[-_])(anim\w*|draw\w*|reveal\w*|count\w*|assemble\w*|stagger\w*|pulse\w*|typewriter|morph\w*|float\w*|orbit\w*|slide\w*|zoom\w*)($|[-_])")
MAX_SIBLINGS = 60


def hero_print(html):
    """{"pictures": set of drawing ids / inline-svg shapes, "motion": set of animation markers, "kind": data-hero} of the
    page's first screen, or None when it has no first section."""
    root = parse(html)
    h = domx.first_section(root)
    if h is None:
        return None
    pics, motion = set(), set()
    for n in h.iter():
        if not n.tag:
            continue
        in_button = any(a.tag in ("a", "button") and (domx.has_cls(a, r"(.*[-_])?(btn|button|book-cta|cta)([-_].*)?")) for a in n.ancestors())
        if in_button:
            continue                    # a button's own arrow or icon is not the hero's picture or motion (2.7.2)
        if n.tag == "use":
            ref = n.get("href") or n.get("xlink:href") or ""
            if "#" in ref:
                pics.add("use:" + ref.split("#", 1)[1])
        elif n.tag == "svg":
            shapes = "".join((c.get("d") or "") + (c.get("points") or "") for c in n.iter() if c.tag in ("path", "polygon", "polyline"))
            if len(shapes) > 40:
                pics.add("svg:" + hashlib.sha1(shapes.encode()).hexdigest()[:12])
        elif n.tag == "img" and n.get("src"):
            pics.add("img:" + n.get("src").split("?")[0].rsplit("/", 1)[-1])
        for c in domx.classes(n):
            if ANIM.search(c):
                motion.add(c)
        for k, v in n.attrs.items():
            if k in ("data-anim", "data-animation", "data-motion") and v:
                motion.add(f"{k}={v}")
    tool = any(n.tag in ("input", "select", "textarea", "output") or "data-tool" in n.attrs for n in h.iter() if n.tag)
    return {"pictures": pics, "motion": motion, "kind": h.get("data-hero") or "", "design": design(h), "tool": tool}


def design(h):
    """The hero's composition, not its words or its drawing's id: the tag and class tree four levels down (class names
    with digits or the page's own words dropped) plus the shape list of each drawing (how many lines, boxes, curves).
    Two heroes with the same design look the same to a reader even when each drawing shows a different object."""
    def sig(n, d):
        cls = ".".join(sorted(c for c in domx.classes(n) if not re.search(r"\d", c) and len(c) < 24))
        if n.tag == "svg":
            kinds = [c.tag for c in n.iter() if c.tag in ("path", "rect", "circle", "ellipse", "line", "polyline", "polygon", "use", "text")]
            return "svg[" + ",".join(f"{k}{kinds.count(k)}" for k in sorted(set(kinds))) + "]"
        kids = [c for c in n.elements() if c.tag not in ("script", "style", "template")]
        return n.tag + ("." + cls if cls else "") + ("(" + ",".join(sig(c, d - 1) for c in kids[:8]) + ")" if d and kids else "")
    return hashlib.sha1(sig(h, 4).encode()).hexdigest()[:12]


def siblings(ctx):
    """Sibling paths from the inventory (plus growth.json new_pages): the same depth and either the same first path
    segment (one cluster) or the same last segment (one kind of page across clusters, such as every hire page)."""
    try:
        inv = json.loads((ctx.project / "inventory" / "inventory.json").read_text()).get("pages", [])
    except (OSError, ValueError):
        raise Skip("no inventory to find sibling pages (growth inventory)", blocked=True)
    me = paths.normalize(ctx.need_path())
    segs = [s for s in me.split("/") if s]
    if not segs:
        return []
    out = []
    for p in [x.get("path", "") for x in inv] + list(ctx.cfg.get("new_pages", [])):
        q = paths.normalize(p)
        s = [x for x in q.split("/") if x]
        # same cluster and depth, or the same kind of page in another cluster (every ".../experts", ".../portfolio")
        if q != me and len(s) == len(segs) and (len(segs) == 1 or s[0] == segs[0] or s[-1] == segs[-1]):
            out.append(q)
    return sorted(set(out))[:MAX_SIBLINGS]


def fetch(ctx, path):
    u = urlsplit(ctx.url)
    slash = "/" if (ctx.cfg.get("trailing_slash") and path != "/") else ""
    try:
        with urllib.request.urlopen(f"{u.scheme}://{u.netloc}{path}{slash}", timeout=15) as r:
            return r.read().decode("utf-8", "replace")
    except Exception:  # noqa: BLE001  (a sibling that is not built yet is not compared)
        return None


@check("hero.unique", "157", types=("money", "hub", "post"), what="no sibling page shares this page's hero design, picture or animation", needs="live")
def hero_unique(ctx):
    if not ctx.url:
        raise Skip("no preview URL to read the sibling pages from", blocked=True)
    mine = hero_print(ctx.need_html())
    if mine is None:
        ctx.fail("no first section to read the hero from", "build the first screen as the page's first <section> (rule 147)")
        return
    probs, compared = [], 0
    for sib in siblings(ctx):
        html = fetch(ctx, sib)
        theirs = hero_print(html) if html else None
        if theirs is None:
            continue
        compared += 1
        if mine["design"] == theirs["design"]:
            probs.append(f"the same hero design as {sib}")
        elif mine["pictures"] and mine["pictures"] == theirs["pictures"]:
            probs.append(f"the same hero picture as {sib}")
        elif mine["motion"] and mine["motion"] == theirs["motion"] and mine["kind"] and mine["kind"] == theirs["kind"]:
            probs.append(f"the same hero animation as {sib} ({', '.join(sorted(mine['motion']))[:60]})")
    if not (mine["pictures"] or mine["motion"] or mine["tool"]):
        probs.append("the hero has no picture, tool or motion of its own")
    ctx.verdict(probs[:8] + ([f"+{len(probs) - 8} more"] if len(probs) > 8 else []),
                f"hero picture and animation are its own among {compared} sibling page(s)",
                "give the page its own hero picture (drawn from its subject) and its own entrance animation; the frame may be shared (rule 157)")
