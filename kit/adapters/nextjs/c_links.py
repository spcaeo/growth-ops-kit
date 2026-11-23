"""Next.js adapter: the checks of gatelib/c_links.py that read the site's code (CSS, components, sources).
They run only when growth.json "stack" is "nextjs"; on any other stack the gate prints SKIP for each."""
from __future__ import annotations

from gatelib import components
from gatelib.c_links import *  # noqa: F401,F403
from gatelib.core import check  # noqa: F401

# A "+" drawn by CSS on the link itself (a ::after on a text link) is a marker too (an Astro / static site has no -plus class)
JOINER = re.compile(r"content\s*:\s*['\"](\\2060|\\u2060|\u2060)['\"]|white-space\s*:\s*nowrap", re.I)


def css_plus(css):
    """[(selector, body)] of rules that draw a marker after a text link: `<...> a<...>::after { content: ...; border or background }`."""
    return [(sel.strip(), b) for sel, b in RULE.findall(css)
            if re.search(r"(?:^|[\s>)])a(?![\w-])[^{}]*::?after\s*$", sel.strip()) and re.search(r"(?<![\w-])content\s*:", b)
            and re.search(r"border|background", b)]


@check("links.blue", "36c", what="in-text links and their '+' use one link-blue token (#1a5fd0 / #6ea8ff), underlined, never the brand or CTA colour, contrast 4.5:1 or more", needs="repo")
def blue(ctx):
    from .c_page import prose_links
    from gatelib import domx
    root = ctx.root()
    main = domx.main(root)
    links = prose_links(ctx, main) if main is not None else []
    css = ctx.css_text()
    probs = []
    if not links:
        probs.append("no in-text links in <main> to check")
    styled = [a.get("href") for a in links if re.search(r"color\s*:", a.get("style") or "")]
    if styled:
        probs.append(f"inline colour on {len(styled)} link(s), e.g. {styled[0]}")
    name, lv, dv, bg = token(css)
    if not name:
        probs.append(f"no link-blue token (a --*link* custom property set to {LIGHT})")
    else:
        if lv != LIGHT:
            probs.append(f"{name} is {lv} in light mode ({LIGHT} required)")
        dark_theme = re.search(r"prefers-color-scheme\s*:\s*dark|\[data-theme=[\"']?dark|\.dark\b|\.theme-dark", css)
        if dark_theme and dv != DARK:            # a site with no dark theme has no dark background to set a link colour for (2.6.1)
            probs.append(f"{name} is {dv or 'not set'} in dark mode ({DARK} required)")
        if lv and contrast(lv, "#ffffff") < 4.5:
            probs.append(f"{name} {lv} on white is {contrast(lv, '#ffffff'):.1f}:1 (4.5:1 needed)")
        if dv and contrast(dv, bg) < 4.5:
            probs.append(f"{name} {dv} on the dark background {bg} is {contrast(dv, bg):.1f}:1 (4.5:1 needed)")
    rules = prose_link_rules(css, "|".join((ctx.cfg.get("links") or {}).get("not_text") or []))
    if not rules:
        probs.append("no CSS rule styles in-text links (e.g. '.article-body a', 'main p a')")
    use = f"var({name})" if name else "var(--link-blue)"
    colours = [(s, c.strip()) for s, b in rules for c in re.findall(r"(?<![\w-])color\s*:\s*([^;]+)", b)]
    if rules and not any(use in c for _, c in colours):
        probs.append(f"no in-text link rule sets color: {use}")
    # a hover or focus state may change the colour (rule 36j: a hover changes one thing the reader can see)
    # a link on a dark surface may use a light link token (any --*link* custom property): the link blue would fail
    # contrast there (2.6.2); it still may not be the brand or CTA colour
    on_dark = re.compile(r"(?i)dark|ink|night|\[data-theme=[\"']?dark")
    bad = [f"{s[-40:]} color: {c}" for s, c in colours if not re.search(r":(hover|focus)", s)
           and (brandish(ctx).search(c) or (use not in c and c not in ("inherit", "currentColor")
                                            and not (on_dark.search(s) and re.search(r"var\(--[\w-]*link[\w-]*\)", c))))]
    probs += [f"in-text link in another colour: {b}" for b in bad[:3]]
    if rules and not any(re.search(r"text-decoration(-line)?\s*:[^;]*underline", b) for _, b in rules):
        probs.append("in-text links are not underlined")
    off = [s[-40:] for s, b in rules if ":hover" not in s and ":focus" not in s and re.search(r"text-decoration(-line)?\s*:\s*none", b)]
    if off:
        probs.append(f"underline removed: {off[0]}")
    plus = [(s, b) for s, b in RULE.findall(css) if re.search(r"\.[\w-]*-plus(?![\w-])", s)]
    marker = css_plus(css) if not plus else []
    if not plus and not marker:
        probs.append("no CSS for the '+' marker")
    elif marker:
        # a ::after on the link itself takes the link's colour (currentColor), which the in-text link rules above already check
        if any(brandish(ctx).search(b) for s, b in marker):
            probs.append("the '+' marker is painted in the brand or CTA colour")
    elif not any(use in b for s, b in plus if re.search(r"(?<![\w-])color\s*:", b)):
        probs.append(f"the '+' marker does not use color: {use}")
    ctx.verdict(probs, f"{len(links)} in-text links in {use} ({lv} / {dv}), underlined; the '+' matches",
                f"define {name or '--link-blue'}: {LIGHT} (dark {DARK}); give in-text links and the '+' color: {use} and an underline (rule 36c)")


@check("links.card-glow", "36c", what="the open link preview card glows in link blue: a 1-2 px blue ring plus a blue blur of 24 px or more", needs="repo")
def card_glow(ctx):
    css = ctx.css_text()
    name = token(css)[0] or "--link-blue"
    blue_re = re.compile(r"var\(" + re.escape(name) + r"|" + LIGHT + "|" + DARK + r"|rgba?\(\s*(26[\s,]+95[\s,]+208|110[\s,]+168[\s,]+255)", re.I)
    pre = components.css_prefix(ctx)
    own = f"|{re.escape(pre)}" if ctx.stack() != "nextjs" else ""      # the site's own card class (.lc), not only .lcx-card
    cards = [(s.strip(), b) for s, b in RULE.findall(css)
             if re.search(r"\.(lcx-card|[\w-]*link-?card" + own + r")(?![\w-])", s.split(",")[-1]) and "box-shadow" in b]
    if not cards:
        ctx.fail("no box-shadow on the link preview card (.lcx-card, .link-card or the class of growth.json components.link_cards_css_class)", "add the blue ring and glow to the card (rule 36c)")
        return
    ring = glow = False
    for _, b in cards:
        for val in re.findall(r"box-shadow\s*:\s*([^;]+)", b):
            for sh in shadows(val):
                if not blue_re.search(sh):
                    continue
                flat = sh
                while re.search(r"\([^()]*\)", flat):
                    flat = re.sub(r"\([^()]*\)", "", flat)
                nums = [px(n, u) for n, u in re.findall(r"(?<![\w.(-])(-?\d*\.?\d+)(px|rem|em)?(?![\w.%])", flat)]
                if len(nums) >= 4 and nums[2] == 0 and 1 <= nums[3] <= 2:
                    ring = True
                if len(nums) >= 3 and nums[2] >= 24:
                    glow = True
    probs = ([] if ring else ["no 1-2 px blue ring (box-shadow: 0 0 0 1px var(--link-blue))"]) + \
            ([] if glow else ["no blue blur of 24 px or more"])
    ctx.verdict(probs, "the preview card has a blue ring and a soft blue glow",
                f"box-shadow: 0 0 0 1px var({name}), 0 12px 32px -8px color-mix(in srgb, var({name}) 35%, transparent) (rule 36c)")


@check("links.spacing", "36c", what="no word is glued to an in-text link: a space before and after every link in the rendered page and in the JSX source", needs="repo")
def spacing(ctx):
    """From a real project: 'your new "+" logic removes the space, which is required sometimes; it should be properly
    checked internally'. JSX drops a line break between text and a <Link>, so 'and\\n<Link>not in' renders 'andnot in'."""
    probs = []
    html = ctx.need_html()
    m = re.search(r"<main\b.*?</main>", html, re.S)
    body = m.group(0) if m else html
    for rx, side in ((GLUE_BEFORE, "before"), (GLUE_AFTER, "after")):
        for hit in rx.finditer(body):
            pre = re.sub(r"^[^<]*>|<[^>]*>", "", body[max(0, hit.start() - 80):hit.start() + 1])
            post = re.sub(r"<[^>]*>|<[^>]*$", "", re.sub(r"^[^>]*>", "", body[hit.start() + 1:hit.end() + 160]))
            probs.append(f"page: no space {side} a link: '…{pre[-30:]}|{post[:30]}…'")
    if ctx.repo:
        for f in ctx.repo_files(("app/**/*.tsx", "components/**/*.tsx")):
            lines = f.read_text(errors="replace").splitlines()
            for i in range(len(lines) - 1):
                a, b = lines[i], lines[i + 1]
                if a.strip().startswith(("//", "*", "{/*", "import")):
                    continue
                if (SRC_TEXT_END.search(a) and SRC_LINK_START.search(b) and "=" not in a.split()[-1]) or \
                   (SRC_LINK_END.search(a) and SRC_TEXT_START.search(b)):
                    probs.append(f"{f.relative_to(ctx.repo)}:{i + 2}: JSX line break next to a link drops the space (add {{\" \"}})")
    ctx.verdict(probs, "every in-text link has a space before and after it",
                "put {\" \"} between text and a <Link> that sit on separate JSX lines (rule 36c)")


@check("links.punct", "36c", what="punctuation right after a link sits after the '+' with no space, and link words + '+' + punctuation never split across lines", needs="repo")
def punct(ctx):
    """From a real project: 'how should that "," be handled, before the + or after the +?' Answer: words, then '+', then
    the comma, one unbreakable group. Checked in the shared link-card code (it must pull a leading punctuation mark of
    the next text node into the '+' slot) and by a site test that names this case."""
    repo = ctx.need_repo()
    probs = []
    if ctx.stack() != "nextjs":
        return punct_any_stack(ctx)
    comp = [f for f in ctx.repo_files(("components/**/*.tsx",)) if "lcx-plus" in f.read_text(errors="replace")]
    if not comp:
        probs.append("no shared link-card component (class lcx-plus) found")
    for f in comp:
        if not PUNCT_HANDLING.search(f.read_text(errors="replace")):
            probs.append(f"{f.relative_to(repo)} adds the '+' but does not move trailing punctuation into its slot")
    tests = [f for g in ("tests/**/*.ts", "tests/**/*.tsx", "**/*.test.ts", "**/*.test.tsx")
             for f in repo.glob(g) if "node_modules" not in f.parts]
    if not any("lcx" in (t := f.read_text(errors="replace")) and re.search(r"punctuation|comma", t, re.I) for f in tests):
        probs.append("no site test covers a link followed by a comma or full stop")
    css = ctx.css_text()
    if not re.search(r"\.lcx-slot[^{]*\{[^}]*white-space\s*:\s*nowrap", css):
        probs.append(".lcx-slot is not white-space: nowrap")
    ctx.verdict(probs, "the '+' keeps the following punctuation with it, no space, no line break",
                "in the link-card code move a leading , . ; : ! ? ) of the next text node into .lcx-slot after the '+'; nowrap the slot; add a test (rule 36c)")


def punct_any_stack(ctx):
    """Any other stack: the link-preview component exists, the '+' is glued to the link's last word (a word joiner U+2060 or a
    nowrap box in the marker's CSS) so the punctuation after the link follows it and a line never starts with a lone '+',
    and a site test names the glue."""
    probs = []
    comp = ctx.component("link_cards")
    if not (comp and comp.is_file()):
        probs.append("no shared link-card component found (set growth.json components.link_cards)")
    css = ctx.css_text()
    pre = components.css_prefix(ctx)
    slot = re.search(r"\." + re.escape(pre) + r"-slot[^{]*\{[^}]*white-space\s*:\s*nowrap", css)
    marker = css_plus(css)
    if not slot and not any(JOINER.search(b) for _, b in marker):
        probs.append("the '+' marker is not glued to the link's last word (a word joiner U+2060 in its ::after content, or a nowrap slot)")
    tests = [t.read_text(errors="replace") for t in ctx.test_files()]
    if not any(re.search(r"glued|joiner|2060|punctuation|comma|full stop", t, re.I) and re.search(r"marker|link.?card|\+", t, re.I) for t in tests):
        probs.append("no site test covers the '+' staying with the link's last word and its punctuation")
    ctx.verdict(probs, "the '+' keeps the following punctuation with it, no space, no line break",
                "glue the marker to the link's last word (U+2060 in the ::after content or a nowrap slot) and add a test (rule 36c)")


@check("icons.check-circle", "36e", what="list ticks are a tick inside a circle, one shared component, in the green 'yes' colour", needs="repo")
def check_circle(ctx):
    repo = ctx.need_repo()
    probs = []
    if ctx.stack() == "nextjs":
        shared = [f for f in ctx.repo_files(("components/**/*.tsx",)) if re.search(r"export\s+(default\s+)?function\s+Tick\b", f.read_text(errors="replace"))]
        if not shared:
            probs.append("no shared Tick component (export function Tick) in components/")
        scan = ctx.repo_files(("app/**/*.tsx", "components/**/*.tsx"))
    else:       # Tick.astro, Tick.vue, tick.svelte, tick.tsx ...: the component file found by name, any source extension
        tick = ctx.component("tick")
        shared = [tick] if tick and tick.is_file() else []
        if not shared:
            probs.append("no shared Tick component found (a Tick file under src/, or growth.json components.tick)")
        scan = ctx.repo_files()
    for f in scan:
        if f.name in TICK_OK or f in shared:
            continue
        t = f.read_text(errors="replace")
        if re.search(r"import\s*\{[^}]*\b(Check|CheckIcon)\b[^}]*\}\s*from\s*[\"']lucide-react", t) or re.search(r"[✓✔]", t):
            probs.append(f"{f.relative_to(repo)}: bare tick (use the shared Tick)")
    for f in shared:
        t = f.read_text(errors="replace")
        if not re.search(r"Circle|<circle|border-radius\s*:\s*50%", t, 0 if ctx.stack() == "nextjs" else re.I):
            probs.append(f"{f.relative_to(repo)}: Tick has no circle (CircleCheck / CircleCheckBig or an SVG circle)")
    css = ctx.css_text()
    if not re.search(r"--[\w-]*(yes|tick|success|ok)[\w-]*\s*:\s*#", css):
        probs.append("no green 'yes' colour token (e.g. --color-yes)")
    ctx.verdict(probs, "every list tick is the shared circled Tick in the 'yes' colour",
                "make the one shared Tick component (components/tick.tsx on Next.js, Tick.astro on Astro: a tick inside a circle, var(--color-yes)) and use it for every list tick (rule 36e)")


