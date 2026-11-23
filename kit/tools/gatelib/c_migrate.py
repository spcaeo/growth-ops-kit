"""A rebuilt page keeps the old site's wording for what it lists (2.8.0, rule 36).

migrate.old-terms: every item of a short list on a rebuilt page (technology tags, segments, platforms) must already be on the
old site: on the archived "before" copy of any page of the site (growth page_archive capture <path> --stage before), or in
BRAND.md. A claim that any page of the live site makes is approved for the whole site; an item that no old page and no BRAND.md
line has is a new claim the owner never saw. A page with no archived old version is SKIP (a new page has nothing to compare)."""
from __future__ import annotations

import html as htmllib
import re

import paths
from techseo.dom import find_all

from . import domx
from .c_words import wcfg
from .core import Skip, check, short

SENTENCE_END = re.compile(r"[.!?;:](?:\s|$)")
TOKEN = re.compile(r"[a-z0-9+#]+(?:\.[a-z0-9+#]+)*")


def norm(s):
    """Words of a text in one form for matching: lower case, '&' as 'and', every other mark (hyphen, slash, quote, comma) a space,
    except the dots, '+' and '#' inside names (node.js, c++, c#)."""
    s = htmllib.unescape(s or "").lower().replace("&", " and ")
    return " " + " ".join(TOKEN.findall(s)) + " "


def page_words(raw):
    """The words an old page shows: its visible text, picture and link descriptions (alt, title, aria-label, meta content) and
    its structured data. Scripts and styles are left out."""
    ld = " ".join(re.findall(r"(?is)<script[^>]*ld\+json[^>]*>(.*?)</script>", raw))
    attrs = " ".join(re.findall(r'(?i)\b(?:alt|title|aria-label|content|placeholder)\s*=\s*"([^"]*)"', raw))
    body = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", raw)
    return re.sub(r"<[^>]+>", " ", body) + " " + attrs + " " + ld


def archived(ctx, slug=None):
    base = ctx.project / "archive" / "pages"
    return sorted(base.glob(f"{slug or '*'}/*-before/page.html")) if base.is_dir() else []


def old_words(ctx):
    """The normalised words of every archived old page of the site plus BRAND.md (read once per run)."""
    if "old_words" not in ctx.cache:
        parts = []
        for f in archived(ctx):
            try:
                parts.append(page_words(f.read_text(errors="replace")))
            except OSError:
                continue
        try:
            parts.append((ctx.project / "BRAND.md").read_text(errors="replace"))
        except OSError:
            pass
        ctx.cache["old_words"] = norm(" ".join(parts))
    return ctx.cache["old_words"]


def own_words(ctx, files):
    """The normalised words of this page's own archived old version(s) plus BRAND.md."""
    if "own_words" not in ctx.cache:
        parts = []
        for f in files:
            try:
                parts.append(page_words(f.read_text(errors="replace")))
            except OSError:
                continue
        try:
            parts.append((ctx.project / "BRAND.md").read_text(errors="replace"))
        except OSError:
            pass
        ctx.cache["own_words"] = norm(" ".join(parts))
    return ctx.cache["own_words"]


def _skip_list(n):
    return domx.in_example(n) or any(a.tag in ("nav", "dialog", "form") or domx.has_cls(a, r"toc|breadcrumbs?") for a in [n, *n.ancestors()])


def list_items(ctx):
    """[(list name, item text)]: the items of every short list of <main> (a ul or ol of 5 or more li, each of 5 words or fewer with
    no sentence punctuation), and of anything marked data-tags (any size)."""
    m = domx.main(ctx.root())
    out = []
    for n in m.iter():
        marked = "data-tags" in n.attrs
        if (n.tag not in ("ul", "ol") and not marked) or _skip_list(n):
            continue
        kids = [c for c in n.children if hasattr(c, "tag")]
        lis = [c for c in kids if c.tag == "li"]
        texts = [domx.text(c) for c in ((lis or kids) if marked else lis)]
        name = n.get("data-tags") or n.get("class") or n.tag
        if marked:
            out += [(name, t) for t in texts if t]
        elif len(lis) >= 5 and all(t and len(t.split()) <= 5 and not SENTENCE_END.search(t) for t in texts):
            out += [(name, t) for t in texts]
    return out


def item_form(t):
    """The item as a reader sees it: a step number glued to its label ("1Discovery") loses the number."""
    return re.sub(r"^\d{1,2}(?=[A-Z][a-z])", "", t).strip()


@check("migrate.old-terms", "36", what="every item of a short list (tags, segments) is on an archived old page of the site or in BRAND.md", needs="live")
def old_terms(ctx):
    """FAIL for an item that no archived old page of the site and no BRAND.md line shows. An item that only OTHER old pages show
    is approved site-wide (the owner's rule), so it only prints a WARN naming it; growth.json words.old_terms_scope "page"
    makes it a FAIL (the item must be on this page's own old version). words.old_terms_ok lists items that are fine as they are."""
    slug = paths.snapshot_slug(ctx.need_path())
    mine = archived(ctx, slug)
    if not mine:
        raise Skip("this page has no archived old version (growth page_archive capture <path> --stage before), so it has no old wording to compare")
    items = [(n, item_form(t)) for n, t in list_items(ctx)]
    items = [(n, t) for n, t in items if re.search(r"[A-Za-z]", t)]
    if not items:
        ctx.ok("no short list (5 or more items of 5 words or fewer, or data-tags) to compare with the old site")
        return
    okay = {norm(str(x)).strip() for x in wcfg(ctx, "old_terms_ok", []) or []}
    site, own = old_words(ctx), own_words(ctx, mine)
    page_only = wcfg(ctx, "old_terms_scope", "site") == "page"
    nowhere, elsewhere = [], []
    for _, t in dict.fromkeys(items):
        w = norm(t).strip()
        if not w or w in okay or t in nowhere or t in elsewhere:
            continue
        if f" {w} " not in site:
            nowhere.append(t)
        elif f" {w} " not in own:
            elsewhere.append(t)
    fix = ("drop the item, or put it in BRAND.md with the owner's yes (permission log); any wording the live site already shows is approved "
           "for the whole site (archive/pages holds the old pages) (rule 36)")
    bad = nowhere + (elsewhere if page_only else [])
    ctx.verdict([f"'{short(t, 40)}'" for t in bad],
                f"all {len(items)} short-list item(s) are on an archived old page of the site or in BRAND.md", fix)
    if elsewhere and not page_only:
        ctx.warn(f"{len(elsewhere)} short-list item(s) are not on this page's own old version, only on other old pages of the site "
                 f"(approved site-wide): {'; '.join(short(t, 30) for t in elsewhere[:8])}{'; ...' if len(elsewhere) > 8 else ''}",
                 "keep them if the page needs them; growth.json words.old_terms_scope \"page\" makes this a FAIL (rule 36)")
