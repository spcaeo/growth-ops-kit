"""Design-agnostic page concepts for the gate: one place that knows how to FIND a part of a page on any site design.

Each concept first tries semantic signals that any well-built site carries (HTML landmarks, ARIA roles, schema.org
JSON-LD, <time datetime>, rel/itemprop), then the project's own map in growth.json "design" ({concept: CSS selector}),
so a site whose markup the signals miss is described once, in the project, never in the kit.

  find(ctx, concept)        -> [nodes]   (first the semantic signals, then the project's selector)
  select(root, selector)    -> [nodes]   a small CSS subset: tag, .class, #id, [attr], [attr=v], [attr^=v], [attr*=v],
                                         descendant combinator (space) and lists (comma)
  exception(ctx, cid)       -> ("ok"|"refused", why) for an owner-approved growth.json design exception, else None

Concepts: site_header, site_footer, main, cover_image, byline, updated_date, reading_aid, faq_section, faq_question,
table_source, calculator, read_next, disclosure.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from urllib.parse import unquote

from techseo.dom import find_all

from . import domx

CONCEPTS = ("site_header", "site_footer", "main", "cover_image", "byline", "updated_date", "reading_aid", "faq_section",
            "faq_question", "table_source", "calculator", "read_next", "disclosure")
FAQ_HEADING = re.compile(r"(?i)\b(faqs?|frequently asked|questions)\b")
MIN_LEFT = re.compile(r"(?i)\b\d+\s*(min|minutes?)\s+(left|to go|remaining)\b")
DATED = re.compile(r"(?i)\b(checked|as of|updated|read|retrieved)\b[^.]{0,40}\b20\d\d\b|\b20\d\d-\d\d-\d\d\b")
SOURCE = re.compile(r"(?i)\b(sources?|according to|pricing pages?|from (each|the) \w+ (page|site))\b")


# ---- a small CSS selector subset ---------------------------------------------------------------------------------
_SIMPLE = re.compile(r"([a-zA-Z][\w-]*)?((?:[.#][\w-]+|\[[^\]]+\])*)")


def _parts(simple):
    m = _SIMPLE.fullmatch(simple.strip())
    if not m:
        raise ValueError(f"unsupported selector '{simple}'")
    tag, rest = m.group(1), m.group(2) or ""
    conds = re.findall(r"\.[\w-]+|#[\w-]+|\[[^\]]+\]", rest)
    return (tag or "").lower(), conds


def _match(n, simple):
    tag, conds = _parts(simple)
    if tag and n.tag != tag:
        return False
    for c in conds:
        if c[0] == ".":
            if c[1:] not in domx.classes(n):
                return False
        elif c[0] == "#":
            if n.get("id") != c[1:]:
                return False
        else:
            m = re.fullmatch(r"\[\s*([\w:-]+)\s*(?:([~^$*]?=)\s*['\"]?(.*?)['\"]?)?\s*\]", c)
            if not m:
                raise ValueError(f"unsupported attribute selector '{c}'")
            k, op, v = m.groups()
            if k not in n.attrs:
                return False
            val = n.get(k)
            if op == "=" and val != v or op == "^=" and not val.startswith(v) or op == "*=" and v not in val \
                    or op == "$=" and not val.endswith(v) or op == "~=" and v not in val.split():
                return False
    return True


def select(root, selector):
    """Nodes under root matching a CSS selector (subset), in document order, without duplicates."""
    out, seen = [], set()
    for alt in (s.strip() for s in (selector or "").split(",") if s.strip()):
        steps = alt.split()
        for n in root.iter():
            if n.tag in (None, "") or id(n) in seen or not _match(n, steps[-1]):
                continue
            anc, i = list(n.ancestors()), len(steps) - 2
            for a in anc:
                if i < 0:
                    break
                if _match(a, steps[i]):
                    i -= 1
            if i < 0:
                seen.add(id(n))
                out.append(n)
    order = {id(n): k for k, n in enumerate(root.iter())}
    return sorted(out, key=lambda n: order.get(id(n), 0))


# ---- concepts -------------------------------------------------------------------------------------------------------
def design_map(ctx):
    """The project's design map: design.json "map" (written by `growth design learn`) under growth.json "design"
    (the hand-written entries win)."""
    if "design_map" not in ctx.cache:
        learned = {}
        try:
            d = json.loads((ctx.project / "design.json").read_text())
            learned = d.get("map") or {} if isinstance(d, dict) else {}
        except (OSError, ValueError, TypeError):
            pass
        ctx.cache["design_map"] = {**learned, **(ctx.cfg.get("design") or {})}
    return ctx.cache["design_map"]


def _mapped(ctx, root, concept):
    sel = design_map(ctx).get(concept)
    return select(root, sel) if sel else []


def _outside_main(root, tag, role):
    hits = [n for n in root.iter() if n.tag == tag and not n.in_tag("main", "article")]
    return hits or [n for n in root.iter() if n.get("role") == role]


PAGE_TYPES = ("Article", "BlogPosting", "NewsArticle", "TechArticle", "WebPage", "Product", "Service", "Recipe", "HowTo")


def _jsonld_image(root):
    """The file stem of the page's own image in the structured data (an Article/WebPage/Product node's image or
    primaryImageOfPage; never a Person's or an Organization's), e.g. 'cover-photo' for /_astro/cover-photo.Ab12.jpg."""
    for node in domx.jsonld(root):
        for x in domx.walk_json(node):
            if not isinstance(x, dict) or not set(domx.types_of(x)) & set(PAGE_TYPES):
                continue
            img = x.get("image") or x.get("primaryImageOfPage")
            for cand in ([img] if not isinstance(img, list) else img):
                url = (cand.get("url") or cand.get("@id")) if isinstance(cand, dict) else cand
                if isinstance(url, str) and url:
                    base = unquote(unquote(url)).split("?")[0].split("#")[0]
                    base = re.split(r"[/=&]", base)[-1].split(".")[0]   # the name before its first dot
                    if len(base) >= 4:
                        return base
    return ""


def _modified(root):
    for n in domx.jsonld(root):
        for x in domx.walk_json(n):
            if isinstance(x, dict) and x.get("dateModified"):
                return str(x["dateModified"])
    return ""


def _semantic(ctx, root, concept):
    m = domx.main(root)
    if concept == "site_header":
        return _outside_main(root, "header", "banner")
    if concept == "site_footer":
        return _outside_main(root, "footer", "contentinfo")
    if concept == "main":
        return find_all(root, "main") or [n for n in root.iter() if n.get("role") == "main"]
    if concept == "cover_image":
        hits = [n for n in m.iter() if n.tag == "img" and n.get("itemprop") == "image"]
        stem = _jsonld_image(root)
        if not hits and stem:   # the image the structured data names as the page's image
            hits = [n for n in m.iter() if n.tag == "img" and stem in unquote(unquote(n.get("src") + " " + n.get("srcset")))]
            if not hits:        # a <picture> whose <source> names it: its <img>
                pics = [p for p in m.iter() if p.tag == "picture"
                        and any(stem in unquote(unquote(s.get("srcset"))) for s in find_all(p, "source"))]
                hits = [i for p in pics for i in find_all(p, "img")][:1]
        return hits
    if concept == "byline":
        a = (ctx.cfg.get("default_author") or {}).get("path")
        import paths
        return [n for n in root.iter() if n.tag == "a" and ("author" in n.get("rel").split() or n.get("itemprop") == "author"
                or (a and paths.key(ctx.internal_path(n.get("href")) or "") == paths.key(a)))]
    if concept == "updated_date":
        times = [t for t in find_all(m, "time") if t.get("datetime")]
        mod = _modified(root)[:10]
        exact = [t for t in times if t.get("itemprop") == "dateModified" or (mod and t.get("datetime")[:10] == mod)]
        worded = [t for t in times if re.search(r"(?i)\bupdated\b\W*$", _before(t))]
        return exact or worded
    if concept == "reading_aid":
        return [n for n in domx.body(root).iter() if n.own_text() and MIN_LEFT.search(n.own_text())]
    if concept in ("faq_section", "faq_question"):
        typed = [n for n in root.iter() if "FAQPage" in n.get("itemtype")]
        qs = [d for t in typed for d in find_all(t, "details")] or _faq_from_markup(m, root) or _faq_after_heading(m) \
            or [d for n in m.iter() if n.get("id") == "faq" or "faq" in domx.classes(n) for d in find_all(n, "details")]
        if concept == "faq_question":
            return qs
        return typed or ([qs[0].parent] if qs else [])
    if concept == "calculator":
        return [n for n in root.iter() if "data-calculator" in n.attrs or n.get("role") == "application"]
    if concept == "read_next":
        return [n for n in root.iter() if n.tag in ("aside", "nav", "section") and (
            re.match(r"(?i)\s*(read next|related|you may also)", domx.text(n) if n.tag == "aside" else "")
            or re.match(r"(?i)\s*(read next|related|you may also|more (posts|articles))", n.get("aria-label")))]
    if concept == "disclosure":
        pat = ctx.cfg.get("disclosure_pattern")
        rx = re.compile(pat, re.I) if pat else None
        return [p for p in find_all(m, "p")[:6] if rx and rx.search(domx.text(p))]
    return []


def _before(t):
    """The words just before a <time> inside its parent (to read 'Updated' / 'Published')."""
    p = t.parent
    if p is None:
        return ""
    txt = []
    for c in p.children:
        if c is t:
            break
        txt.append(c if isinstance(c, str) else domx.text(c))
    return " ".join(txt)[-40:]


def _q(d):
    s = find_all(d, "summary")
    return re.sub(r"[^a-z0-9]+", "", domx.text(s[0]).lower()) if s else ""


def _faq_from_markup(m, root):
    """The FAQ is the heading block holding the <details> whose question the FAQPage structured data names: every
    <details> of that block (so a question that drifted from its markup still counts as visible)."""
    names = {re.sub(r"[^a-z0-9]+", "", str(x.get("name", "")).lower()) for n in domx.jsonld(root) for x in domx.walk_json(n)
             if isinstance(x, dict) and "Question" in domx.types_of(x)}
    first = next((d for d in m.iter() if d.tag == "details" and _q(d) in names), None) if names else None
    if first is None:
        return []
    flat = [n for n in m.iter()]
    i = flat.index(first)
    head = next((k for k in range(i, -1, -1) if flat[k].tag in ("h1", "h2") and not flat[k].in_tag("summary")), 0)
    out = []
    for n in flat[head + 1:]:
        if n.tag in ("h1", "h2") and not n.in_tag("summary"):
            break
        if n.tag == "details" and not n.in_tag("details") and find_all(n, "summary"):
            out.append(n)
    return out


def _faq_after_heading(m):
    """<details> that follow a heading saying FAQ / Frequently asked, until the next heading of that level or higher."""
    out, level = [], None
    for n in m.iter():
        if n.tag in ("h1", "h2", "h3") and not n.in_tag("summary"):
            lv = int(n.tag[1])
            if level is not None and lv <= level:
                break
            if level is None and FAQ_HEADING.search(domx.text(n)):
                level = lv
        elif level is not None and n.tag == "details":
            out.append(n)
    return out


def find(ctx, concept, root=None):
    """Nodes for a page concept: semantic signals first, then the project's design map."""
    assert concept in CONCEPTS, concept
    root = root if root is not None else ctx.root()
    return _semantic(ctx, root, concept) or _mapped(ctx, root, concept)


def faq_items(ctx, root=None):
    """[(question, answer)] of the page's FAQ: only the FAQ's own questions (never a contents list or a fold)."""
    out = []
    for d in find(ctx, "faq_question", root):
        s = find_all(d, "summary")
        if not s:
            continue
        h = find_all(s[0], "h3") or find_all(s[0], "h2") or find_all(s[0], "h4")
        q = domx.text(h[0] if h else s[0]).strip()
        a = " ".join(domx.text(c) for c in d.elements() if c.tag != "summary").strip()
        out.append((q, a))
    return out


def table_sourced(ctx, table, root=None):
    """(has a source, has a date) for a table: inside its own box, on the component around it (data-source and
    data-checked, or data-checked with a linked source in it), or as a dated source sentence in the same section."""
    box = table                                   # the table and the wrappers that exist only for it
    while box.parent is not None and len(box.parent.elements()) == 1 and box.parent.tag not in ("main", "article", "body"):
        box = box.parent
    txt = domx.text(box)
    src, date = bool(find_all(box, "a")) or bool(SOURCE.search(txt)), bool(DATED.search(txt))
    for a in table.ancestors():
        if "data-checked" in a.attrs:
            date = True
            src = src or "data-source" in a.attrs or bool(find_all(a, "a"))
    if not (src and date):
        sec = _section_text(root if root is not None else ctx.root(), table)
        src = src or bool(SOURCE.search(sec))
        date = date or bool(DATED.search(sec))
    return src, date


def _section_text(root, node):
    """The text of the heading block that holds node: from the nearest H2/H3 before it to the next one."""
    flat = list(domx.main(root).iter())
    idx = next((i for i, n in enumerate(flat) if n is node), None)
    if idx is None:
        return ""
    start = next((i for i in range(idx, -1, -1) if flat[i].tag in ("h2", "h3")), 0)
    end = next((i for i in range(idx, len(flat)) if flat[i].tag in ("h2", "h3")), len(flat))
    return " ".join(n.own_text() for n in flat[start:end] if n.own_text())


def ignored(ctx, n):
    """True when a node sits in a component whose numbers are computed or shared: data-calculator anywhere, or one of
    growth.json box_ignore's selectors (each entry needs a reason)."""
    if any("data-calculator" in a.attrs for a in [n, *n.ancestors()]):
        return True
    root = ctx.root()
    for e in ctx.cfg.get("box_ignore") or []:
        if isinstance(e, dict) and e.get("selector") and len((e.get("why") or "").strip()) >= 10:
            hits = {id(x) for x in select(root, e["selector"])}
            if id(n) in hits or any(id(a) in hits for a in n.ancestors()):
                return True
    return False


def exception(ctx, cid):
    """(state, why) for growth.json design_exceptions and check `cid` (approvals.exception_state):
    ("ok", why) the owner approved an entry that excuses it today; ("refused", why) an entry exists but does not count
    (no owner approval, changed since, an evidence or process check, no 'until' within 30 days, expired, task done);
    None when no entry names it."""
    import approvals
    state, _e, why = approvals.exception_state(ctx.docs or (ctx.project / "docs"), ctx.cfg, cid, ctx.today,
                                               lambda t: _task_done(ctx, t))
    return None if state == "none" else (state, why)


def _task_done(ctx, tid):
    try:
        import records
        return any(t.get("id") == tid and t.get("status") == "done" for t in records.tasks_doc(ctx.docs.parent if ctx.docs else ctx.project)["tasks"])
    except (OSError, ValueError, KeyError):
        return False
