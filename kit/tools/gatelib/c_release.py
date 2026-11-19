"""Checks that READY must not pass without: the page was read from a production build (not a dev server), the head's
money figures are backed by the body, and held-field proposals are not stale."""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from .core import ALL, check

# What a dev server puts in a page and a production build never does: the hot-reload client, the dev toolbar, the
# source-location attributes. Any one of them means the gate read a dev page, whose missing sitemap, 404 share image and
# tag loader are artifacts of the dev server and not the page (#57).
DEV_MARKERS = (
    "/@vite/client", "/@react-refresh", "__vite_ping", "astro-dev-toolbar", "data-astro-source-file", "data-astro-source-loc",
    "/_next/webpack-hmr", "/_next/static/development", "react-refresh", "[turbopack]", "__nextjs_original-stack",
    "webpack-dev-server", "/sockjs-node", "hot-update.js", "/__webpack_hmr", "livereload.js", "/livereload",
    "browser-sync-client", "___browsersync___", "/_nuxt/@vite", "__nuxt_dev", "data-sveltekit-dev",
)


def dev_markers(html):
    low = html.lower()
    return sorted({m for m in DEV_MARKERS if m.lower() in low})


@check("ev.prod-build", "106", ALL, "the page was read from a production build served locally, not from a dev server", needs="live")
def prod_build(ctx):
    found = dev_markers(ctx.need_html())
    cmd = ctx.cfg.get("preview_cmd")
    how = (f"run the site's production preview ({cmd}) and pass its address" if cmd else
           "build the site for production and serve the output: growth serve <dist> (or record the site's own production "
           "preview command in growth.json preview_cmd)")
    ctx.verdict([f"a dev server answered: the page holds {', '.join(found[:4])}" + (f" and {len(found) - 4} more" if len(found) > 4 else "")]
                if found else [], "no dev-server markers in the page (a production build)", f"{how}; a dev page gives false FAILs (rule 106)")


# ---- the head's money figures must be backed by the body (#60) ------------------------------------------------------
MONEY = re.compile(r"(?:(?:US|CA|AU|NZ|C|A)?\$|€|£)\s?(\d[\d,]*(?:\.\d+)?)(?:\s?(k|m|million|thousand)\b)?", re.I)
NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
MULT = {"k": 1000, "thousand": 1000, "m": 1_000_000, "million": 1_000_000}
VERDICT_CLASS = re.compile(r"(?i)\b(verdict|tldr|tl-dr|quick-answer|bottom-line)\b")


def _value(num, mult=""):
    try:
        return Decimal(num.replace(",", "")) * MULT.get((mult or "").lower(), 1)
    except InvalidOperation:
        return None


def money_figures(text):
    """{canonical value: the text as written} for every money figure in a text ($1,234.50 and $1234.5 are one figure)."""
    out = {}
    for m in MONEY.finditer(text):
        v = _value(m.group(1), m.group(2))
        if v is not None:
            out.setdefault(v.normalize(), m.group(0).strip())
    return out


def number_values(text):
    return {v.normalize() for v in (_value(m.group(0)) for m in NUMBER.finditer(text)) if v is not None}


def head_and_body(ctx):
    """(head text, body text) of the page's main content. The head is everything before the first H2 plus every verdict
    block (growth.json design.verdict, else data-verdict or a class named verdict / tldr / quick-answer / bottom-line);
    the body is the rest."""
    from . import design, domx
    root = ctx.root()
    m = domx.main(root)
    verdicts = design.select(root, (ctx.cfg.get("design") or {}).get("verdict", "") or "") if (ctx.cfg.get("design") or {}).get("verdict") else []
    verdicts += [n for n in m.iter() if n.tag and ("data-verdict" in n.attrs or any(VERDICT_CLASS.fullmatch(c) for c in domx.classes(n)))]
    vid = {id(n) for n in verdicts}
    head, body, seen_h2 = [], [], False
    for n in m.iter():
        if not n.tag:
            continue
        if n.tag == "h2":
            seen_h2 = True
        in_v = id(n) in vid or any(id(a) in vid for a in n.ancestors())
        t = n.own_text()
        if t:
            (head if in_v or not seen_h2 else body).append(t)
    return " ".join(head), " ".join(body)


@check("claims.head-figures", "109", ALL, "every money figure in the first screen and the verdict also appears in the body", needs="live")
def head_figures(ctx):
    head, body = head_and_body(ctx)
    figs = money_figures(head)
    if not figs:
        ctx.ok("no money figure in the first screen or verdict")
        return
    if not body.strip():
        ctx.ok("the page has no body under its head (no H2): nothing to compare the head's figures with")
        return
    have = number_values(body)
    missing = [txt for v, txt in figs.items() if v not in have]
    ctx.verdict([f"{', '.join(missing)} in the first screen or verdict, never stated in the body"] if missing else [],
                f"{len(figs)} money figure(s) in the head, all stated in the body",
                "state each head figure in the body with its source and the sum behind it, or take it out of the head (rule 109)")
