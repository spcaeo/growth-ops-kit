"""Checks that READY must not pass without: the page was read from a production build (not a dev server), the head's
money figures are backed by the body, and held-field proposals are not stale."""
from __future__ import annotations

import re

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
