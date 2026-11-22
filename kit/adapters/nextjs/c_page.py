"""Next.js adapter: the checks of gatelib/c_page.py that read the site's code (CSS, components, sources).
They run only when growth.json "stack" is "nextjs"; on any other stack the gate prints SKIP for each."""
from __future__ import annotations

from gatelib.c_page import *  # noqa: F401,F403
from gatelib.core import check  # noqa: F401


@check("layout.table-scroll", "48", what="every wide table sits in its own scroll box", needs="repo")
def table_scroll(ctx):
    m = domx.main(ctx.root())
    probs = []
    css = ctx.css_text()
    for t in find_all(m, "table"):
        box = t.parent
        cls = domx.classes(box) if box is not None else []
        scroll = box is not None and (box.get("tabindex") == "0" or box.get("role") == "region" or
                                      any(re.search(r"\." + re.escape(c) + r"\s*\{[^}]*overflow(-x)?\s*:\s*auto", css) for c in cls))
        if not scroll:
            probs.append(f"table .{'.'.join(domx.classes(t)) or 'table'} not in a scroll box")
    ctx.verdict(probs, f"{len(find_all(m, 'table'))} table(s) scroll in their own box", "wrap the table in a box with overflow-x: auto, tabindex=0, role=region (rule 48)")
