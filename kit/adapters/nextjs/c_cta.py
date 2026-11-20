"""Next.js adapter: the checks of gatelib/c_cta.py that read the site's code (CSS, components, sources).
They run only when growth.json "stack" is "nextjs"; on any other stack the gate prints SKIP for each."""
from __future__ import annotations

from gatelib.c_cta import *  # noqa: F401,F403
from gatelib.core import Skip, check  # noqa: F401


def colors(ctx):
    """growth.json cta.color / cta.color_pressed / cta.color_token: the one CTA colour (rule 32b). Skip when not set."""
    c = (ctx.cfg.get("cta") or {})
    if not c.get("color"):
        raise Skip("no CTA colour in growth.json (cta.color)")
    return c["color"], c.get("color_pressed", c["color"]), c.get("color_token", "--color-cta")


@check("cta.one-color", "32b", types=("money", "hub", "core"), what="every primary button is painted with the one CTA colour token", needs="nextjs")
def one_color(ctx):
    CTA_HEX, CTA_PRESSED, TOKEN = colors(ctx)
    root = ctx.root()
    css = ctx.css_text()
    probs = []
    if not re.search(re.escape(TOKEN) + r"\s*:\s*" + CTA_HEX, css, re.I):
        probs.append(f"no {TOKEN}: {CTA_HEX} token")
    if not re.search(re.escape(TOKEN) + r"-pressed\s*:\s*" + CTA_PRESSED, css, re.I):
        probs.append(f"no {TOKEN}-pressed: {CTA_PRESSED} token")
    rules = re.findall(r"([^{}]+)\{([^{}]*)\}", css)
    seen = set()
    for a in primaries(ctx, root):
        cls = [c for c in domx.classes(a) if c != "button"]
        key = " ".join(cls)
        if key in seen:
            continue
        seen.add(key)
        painted = any(any(re.search(r"\." + re.escape(c) + r"(?![\w-])", sel) for c in cls)
                      and re.search(r"background(-color)?\s*:\s*(var\(" + re.escape(TOKEN) + r"\b|" + CTA_HEX + ")", body, re.I)
                      for sel, body in rules)
        if not painted:
            probs.append(f"button '.{'.'.join(cls)}' has no rule painting it var({TOKEN})")
    ctx.verdict(probs, f"{len(seen)} primary button style(s), all painted var({TOKEN}) {CTA_HEX}",
                f"paint every primary booking button (header, sticky bar, sections, dialogs) with background: var({TOKEN}) (rule 32b)")


@check("sticky.present", "35", types=("money",), what="sticky call bar: shared component, replaces the header, close x, progress line, text <= 70, button <= 30", needs="nextjs")
def sticky(ctx):
    f = ctx.feature("sticky_cta")
    comp, src_file = f.get("component", "StickyCta"), f.get("source", "components/sticky-cta.tsx")
    max_text, max_btn = int(f.get("max_text", 70)), int(f.get("max_button", 30))
    root = ctx.root()
    bars = [n for n in root.iter() if domx.has_cls(n, r"sticky-cta")]
    if ctx.need_path() in not_on(ctx, f):
        ctx.verdict([f"{len(bars)} sticky bar(s) on {ctx.path}"] if bars else [], "no sticky bar on this page (correct)",
                    "remove the sticky bar from this page (rule 35)")
        return
    if not bars:
        ctx.fail("no sticky call bar (.sticky-cta) in the page", f"render the shared <{comp}> on the page (rule 35)")
        return
    bar = bars[0]
    probs = []
    btn = [a for a in domx.booking_links(ctx, bar)]
    if not btn:
        probs.append("no booking button in the bar")
    if not any(b.get("aria-label") and re.search(r"(?i)dismiss|close", b.get("aria-label")) for b in find_all(bar, "button")):
        probs.append("no close x with an aria-label")
    if not any(domx.has_cls(n, r".*progress.*") for n in bar.iter()):
        probs.append("no reading-progress line")
    txt = next((n for n in bar.iter() if domx.has_cls(n, r"sticky-cta-text")), None)
    line = domx.label(txt) if txt is not None else ""
    if not line:
        probs.append("no bar text")
    elif len(line) > max_text:
        probs.append(f"bar text is {len(line)} chars (max {max_text}): '{short(line, 60)}'")
    if btn and len(domx.label(btn[0])) > max_btn:
        probs.append(f"button label is {len(domx.label(btn[0]))} chars (max {max_btn})")
    css = ctx.css_text()
    if not re.search(r"\[data-sticky-cta\][^{]*\.site-header[^{]*\{[^}]*(display\s*:\s*none|visibility\s*:\s*hidden|transform)", css):
        probs.append("no CSS rule hides .site-header under html[data-sticky-cta] (the bar must replace the header)")
    src = "\n".join(ctx.tree_sources().values())
    sticky_src = ctx.need_repo() / src_file
    if f"<{comp}" not in src or not sticky_src.exists() or "data-sticky-cta" not in sticky_src.read_text():
        probs.append(f"the page does not render the shared {comp} that sets data-sticky-cta")
    ctx.verdict(probs, f"sticky bar ok: '{short(line, 50)}' ({len(line)} chars)",
                f"fix the sticky bar as listed: text from the page's offer, at most {max_text} chars; button at most {max_btn} (rule 35)")


@check("cta.events", "133", what="every CTA event of growth.json cta.events exists in the site code and the page renders the CTA components", needs="nextjs")
def events(ctx):
    events = (ctx.cfg.get("cta") or {}).get("events") or []
    if not events:
        raise Skip("no CTA events in growth.json (cta.events)")
    comps = (ctx.cfg.get("cta") or {}).get("components") or []
    files = ctx.repo_files(("components/**/*.tsx", "components/**/*.ts", "lib/**/*.ts"))
    src = "\n".join(f.read_text(errors="replace") for f in files if ".test." not in f.name)
    missing = [e for e in events if e not in src]
    tree = "\n".join(ctx.tree_sources().values())
    if ctx.ptype == "money":
        missing += [f"component {c} not on the page" for c in comps if c not in tree]
    ctx.verdict(missing, f"all {len(events)} CTA events are pushed by the components the page renders",
                "push the missing dataLayer event from the shared component (rule 133); GTM needs a trigger for each")


@check("dialog.backdrop", "134", types=("money", "hub", "core"), what="every dialog opens on a dimmed ::backdrop with a solid panel", needs="nextjs")
def backdrop(ctx):
    root = ctx.root()
    css = ctx.css_text()
    probs = []
    for d in find_all(root, "dialog"):
        cls = domx.classes(d)
        if not any(re.search(r"\." + re.escape(c) + r"[^{,]*::backdrop[^{]*\{[^}]*background", css) for c in cls) \
                and not re.search(r"(^|[\s,}])dialog::backdrop[^{]*\{[^}]*background", css):
            probs.append(f"dialog .{'.'.join(cls)} has no ::backdrop background")
    if not find_all(root, "dialog"):
        probs.append("no dialog on the page (the call dialog is required, rule 132)")
    ctx.verdict(probs, "every dialog has a dimmed backdrop", "add .<dialog>::backdrop { background: <token> } (rule 134)")


@check("cta.glow", "32c", types=("money", "hub", "core"), what="the primary CTA glows in its own colour; pulses at most twice, never endlessly", needs="nextjs")
def glow(ctx):
    CTA_HEX, _pressed, _token = colors(ctx)
    r, g, b = (int(CTA_HEX.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    root = ctx.root()
    css = ctx.css_text()
    rules = re.findall(r"([^{}]+)\{([^{}]*)\}", css)
    cls = {c for a in primaries(ctx, root) for c in domx.classes(a) if c != "button"}
    if not cls:
        ctx.fail("no primary booking button", "add the page's primary button (rule 32a)")
        return
    mine = [(s, b) for s, b in rules if any(re.search(r"\." + re.escape(c) + r"(?![\w-])", s) for c in cls)]
    glow_re = rf"box-shadow\s*:[^;]*(var\(--cta-(shadow|glow)|rgba?\(\s*{r}[\s,]+{g}[\s,]+{b}|" + CTA_HEX + ")"
    probs = []
    if not any(re.search(glow_re, b, re.I) for s, b in mine if ":hover" not in s and ":focus" not in s):
        probs.append("no CTA-coloured box-shadow at rest")
    if not any(re.search(r"box-shadow", b) for s, b in mine if ":hover" in s or ":focus" in s):
        probs.append("no stronger glow on hover/focus")
    if any(re.search(r"animation[^;]*infinite|animation-iteration-count\s*:\s*infinite", b) for s, b in mine):
        probs.append("an endless pulse on the CTA")
    if not any(re.search(r"animation[^;]*\b2\b|animation-iteration-count\s*:\s*2\b", b) for s, b in mine):
        probs.append("no two-beat pulse for the moment of intent")
    reduced = "".join(re.findall(r"@media[^{]*prefers-reduced-motion\s*:\s*reduce[^{]*\{((?:[^{}]*\{[^{}]*\})*)[^{}]*\}", css))
    if not any(any(re.search(r"\." + re.escape(c) + r"(?![\w-])", sel) for c in cls) and re.search(r"animation(-name)?\s*:\s*none", body)
               for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", reduced)):
        probs.append("no prefers-reduced-motion block stops the CTA pulse (animation: none)")
    sec = [sel.strip()[-60:] for sel, body in rules if re.search(r"\.(button-light|button-outline|button-secondary)(?![\w-])", sel)
           and re.search(glow_re, body, re.I)]
    if sec:
        probs.append(f"a secondary button glows: {sec[0]}")
    ctx.verdict(probs, "CTA glow in its own colour, two-beat pulse, no endless loop",
                "add box-shadow: var(--cta-glow) at rest, stronger on :hover/:focus-visible, and a 2-iteration pulse on intent (rule 32c)")
