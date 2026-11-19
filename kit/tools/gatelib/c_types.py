"""House features of posts and hubs (rules 26, 53, 54, 61, 136-138, 142-145)."""
from __future__ import annotations

import re

from techseo.dom import find, find_all

from . import design, domx
from .core import check


def article(root):
    m = domx.main(root)
    return next((n for n in m.iter() if domx.has_cls(n, r"article-body|editorial-content|prose")), m)


@check("post.cover", "61", ("post",), "an article shows its own cover image above the text, with alt text", needs="live")
def cover(ctx):
    root = ctx.root()
    h1 = find(root, "h1")
    body = article(root)
    # the cover is the image the page's structured data names (or itemprop=image), else growth.json design.cover_image;
    # only then the first image outside the article text
    imgs = design.find(ctx, "cover_image") or [i for i in find_all(domx.main(root), "img") if not any(a is body for a in i.ancestors())]
    if h1 is None or not imgs:
        ctx.fail("no cover image outside the article text", "render the post's own cover (rule 61)")
    elif not imgs[0].get("alt"):
        ctx.fail("the cover has no alt text", "use the post title as the cover's alt (rule 62)")
    else:
        ctx.ok("cover present with alt text")


@check("post.reading-aids", "138", ("post",), "progress line, 'x min left', contents list, a copy-link button on every H2/H3", needs="live")
def reading_aids(ctx):
    root = ctx.root()
    m = domx.main(root)
    cls = " ".join(n.get("class") for n in root.iter())
    probs = []
    if not re.search(r"progress", cls):
        probs.append("no reading-progress line")
    if not design.find(ctx, "reading_aid"):          # 'N min left' anywhere on the page (a side rail too)
        probs.append("no 'x min left'")
    if not re.search(r"\btoc\b|-toc", cls):
        probs.append("no contents list")
    # a heading that is a disclosure toggle (inside <summary>, e.g. an FAQ question) carries no copy-link button
    heads = [h for h in find_all(article(root), "h2") + find_all(article(root), "h3") if not h.in_tag("summary")]
    bare = [domx.text(h)[:30] for h in heads if not any(re.search(r"(?i)copy", b.get("aria-label")) for b in find_all(h.parent, "button"))]
    if bare:
        probs.append(f"{len(bare)} of {len(heads)} headings without a copy-link button")
    ctx.verdict(probs, "all reading aids present", "use the shared post layout's reading aids (rule 138)")


@check("post.toc-h2", "53", ("post",), "the contents list is built from the article's H2s", needs="live")
def toc(ctx):
    root = ctx.root()
    t = next((n for n in root.iter() if domx.has_cls(n, r".*toc-links.*|toc")), None)
    h2 = [domx.text(h).strip() for h in find_all(article(root), "h2")]
    if t is None:
        ctx.fail("no contents list", "render the contents list from the H2s (rule 53)") if len(h2) >= 4 else ctx.ok("short article: no list needed")
        return
    links = [domx.text(a).strip() for a in find_all(t, "a")]
    miss = [h for h in h2 if h not in links]
    ctx.verdict(miss, f"contents list = {len(h2)} H2s", "build the list from the H2s only (rule 53)")


@check("post.read-next", "54", ("post",), "exactly one 'Read next' section under the post", needs="live")
def read_next(ctx):
    m = domx.main(ctx.root())
    n = [h for h in find_all(m, "h2") + find_all(m, "h3") if re.search(r"(?i)^(read next|related)", domx.text(h))]
    ctx.verdict([] if len(n) == 1 else [f"{len(n)} read-next sections"], "one Read next section", "keep exactly one 'Read next' section (rule 54)")


@check("post.ask-card", "136", ("post",), "exactly one shared ask card in the post", needs="live")
def ask(ctx):
    m = domx.main(ctx.root())
    cards = [n for n in m.iter() if domx.has_cls(n, r".*ask(-card)?|.*next-step")]
    ctx.verdict([] if len(cards) == 1 else [f"{len(cards)} ask cards"], "one ask card", "place one shared ask card where the reader wants help (rule 136)")


@check("post.takeaways", "137", ("post",), "a Key takeaways box holds 3 to 5 points", needs="live")
def takeaways(ctx):
    m = domx.main(ctx.root())
    box = next((n for n in m.iter() if re.search(r"(?i)key takeaways", domx.text(n)) and n.tag in ("section", "aside", "div")
                and len(find_all(n, "li")) > 0), None)
    if box is None:
        ctx.ok("no takeaways box (only drawn when the frontmatter has takeaways)")
        return
    n = len(find_all(box, "li"))
    ctx.verdict([] if 3 <= n <= 5 else [f"{n} takeaways"], f"{n} takeaways", "keep 3 to 5 one-line takeaways (rule 137)")


@check("post.shapes", "142", ("post",), "a numbered how-to is drawn as a steps timeline; one mid-article read-next card", needs="live")
def shapes(ctx):
    body = article(ctx.root())
    ols = [o for o in find_all(body, "ol") if len(find_all(o, "li")) >= 3]
    cls = " ".join(n.get("class") for n in body.iter())
    probs = []
    if ols and not re.search(r"steps|timeline", cls):
        probs.append(f"{len(ols)} numbered list(s) not drawn as a steps timeline")
    if not re.search(r"read-next|mid-card|inline-related", cls):
        probs.append("no mid-article read-next card")
    ctx.verdict(probs, "post shapes present", "use the shared Markdown shapes (rule 142)")


@check("post.logos", "143", ("post", "hub"), "every tool named in a list shows its own logo, never a letter tile", needs="live")
def logos(ctx):
    m = domx.main(ctx.root())
    tiles = [n for n in m.iter() if domx.has_cls(n, r".*letter-tile.*|.*logo-fallback.*")]
    ctx.verdict([f"{len(tiles)} letter tile(s)"] if tiles else [], "no letter tiles", "add the tool's logo to lib/tools.ts (rule 143)")


@check("hub.cards", "144", ("hub",), "every post card on a hub shows the post's cover", needs="live")
def hub_cards(ctx):
    m = domx.main(ctx.root())
    cards = [n for n in m.iter() if domx.has_cls(n, r".*card") and find(n, "a") is not None]
    bare = [c for c in cards if find(c, "img") is None]
    if not cards:
        ctx.fail("no post cards on the hub", "list the cluster's posts as cards with covers (rule 144)")
        return
    ctx.verdict([f"{len(bare)} of {len(cards)} cards without a cover"] if bare else [], f"{len(cards)} cards with covers",
                "show the post's cover as the card thumbnail (rule 144)")


@check("hub.map", "26", ("hub",), "a hub opens with its stages and closes with one call for the cluster's offer", needs="live")
def hub_map(ctx):
    root = ctx.root()
    m = domx.main(root)
    probs = []
    if len(find_all(m, "h2")) < 2:
        probs.append("fewer than two stage headings")
    bk = [a for a in domx.booking_links(ctx, m) if domx.is_primary(a)]
    if len(bk) < 1:
        probs.append("no closing call")
    ctx.verdict(probs, "hub map with stages and a closing call", "build the hub as a map of stages with one closing call (rule 26)")
