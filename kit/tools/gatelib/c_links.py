"""Rule 36c, colour and glow: in-text links and their "+" use one link-blue token, underlined, never the brand or CTA
colour; the open preview card glows in the same blue (a 1-2 px ring plus a blur of 24 px or more).
The CTA colour comes from growth.json cta.color / cta.color_pressed."""
from __future__ import annotations

import re

from .core import Skip, check

LIGHT, DARK = "#1a5fd0", "#6ea8ff"
RULE = re.compile(r"([^{}]+)\{([^{}]*)\}")
DARK_BLOCK = re.compile(r"@media[^{]*prefers-color-scheme\s*:\s*dark[^{]*\{((?:[^{}]*\{[^{}]*\})*)[^{}]*\}", re.I)
NOT_PROSE = re.compile(r"nav|footer|header|button|cta|sticky|crumb|lcx-(card|open|icon|close)|exit|dialog|menu", re.I)


def brandish(ctx):
    """A colour that is the brand's or the CTA's (never allowed on in-text links)."""
    extra = "".join("|" + re.escape(c) for c in ((ctx.cfg.get("cta") or {}).get(k) for k in ("color", "color_pressed")) if c)
    return re.compile(r"var\(--(cta|brand|accent|primary|orange)[\w-]*\)" + extra, re.I)


def need_browser(ctx):
    """These two checks measure the page in a real headless browser. Without one they are SKIP (never a pass)."""
    if ctx.cache.get("no_browser"):
        raise Skip("browser checks are switched off for this run (--no-browser)", blocked=True)
    try:
        import playwright.sync_api  # noqa: F401
    except ImportError:
        raise Skip("playwright is not installed (pip install playwright; python3 -m playwright install chromium)", blocked=True)


def browser_failed(e):
    """A launch failure (no chromium downloaded) is SKIP; any other error is a real problem and stays a crash."""
    return "Executable doesn't exist" in str(e) or "playwright install" in str(e)


def rgb(hexv):
    h = hexv.lstrip("#")
    h = "".join(c * 2 for c in h) if len(h) == 3 else h[:6]
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def contrast(a, b):
    def lum(c):
        r, g, bl = (x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in rgb(c))
        return 0.2126 * r + 0.7152 * g + 0.0722 * bl
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def dark_rules(css):
    out = [r for blk in DARK_BLOCK.findall(css) for r in RULE.findall(blk)]
    out += [(s, b) for s, b in RULE.findall(css) if re.search(r"data-theme\s*=\s*['\"]?dark|\.dark\b", s)]
    return out


def token(css):
    """(name, light value, dark value, dark background) of the link-blue token, or Nones."""
    darks = dark_rules(css)
    dark_bodies = {b for _, b in darks}
    light = {}
    for s, b in RULE.findall(css):
        if b in dark_bodies:
            continue
        for name, val in re.findall(r"(--[\w-]*link[\w-]*)\s*:\s*(#[0-9a-f]{3,6})\b", b, re.I):
            light.setdefault(name, val.lower())
    dark = {}
    bg = None
    for _, b in darks:
        for name, val in re.findall(r"(--[\w-]*link[\w-]*)\s*:\s*(#[0-9a-f]{3,6})\b", b, re.I):
            dark.setdefault(name, val.lower())
        m = re.search(r"--[\w-]*(bg|background|surface|paper|page)[\w-]*\s*:\s*(#[0-9a-f]{3,6})\b", b, re.I)
        if m and not bg:
            bg = m.group(2)
    name = next((n for n, v in light.items() if v == LIGHT), None) or next(iter(light), None)
    return name, light.get(name), dark.get(name), bg or "#121212"


def prose_link_rules(css):
    out = []
    for s, b in RULE.findall(css):
        parts = [p.strip() for p in s.split(",")]
        if any(re.search(r"(^|[\s>])a(\[[^\]]*\]|:{1,2}[\w-]+(\([^)]*\))?)*$", p) and re.search(r"\S\s*[\s>]\s*a\b", p)
               and not NOT_PROSE.search(p) for p in parts):
            out.append((s.strip(), b))
    return out


def shadows(value):
    out, depth, cur = [], 0, ""
    for ch in value:
        depth += ch == "("
        depth -= ch == ")"
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    return [s for s in out + [cur.strip()] if s]


def px(n, unit):
    return float(n) * (16 if unit in ("rem", "em") else 1)


GLUE_BEFORE = re.compile(r"([A-Za-z0-9,;:’”)])<a\s")
GLUE_AFTER = re.compile(r"</a>([A-Za-z0-9(“‘])")
SRC_TEXT_END = re.compile(r"[A-Za-z0-9,;:’”)]\s*$")
SRC_LINK_START = re.compile(r"^\s*<(Link|a)\b")
SRC_LINK_END = re.compile(r"</(Link|a)>\s*$")
SRC_TEXT_START = re.compile(r"^\s*[A-Za-z0-9(“‘]")


PUNCT_HANDLING = re.compile(r"[\[(]\s*[,.;:!?)’”\\]{3,}|\\p\{P\}|punctuation", re.I)


TICK_OK = ("copy-button.tsx",)


SURFACES = {"plain", "tint", "warm", "geo-grid", "geo-lines", "geo-contour", "geo-hatch", "dark"}
JOBS = {"hook", "show", "compare", "reassure", "prove", "relief", "act", "read", "answer"}


@check("ui.contrast-states", "36j", what="every link, button and control reads at AA contrast at rest, on hover and on keyboard focus, at 1366 and 390 (measured in a real browser)", needs="live")
def contrast_states(ctx):
    """Runs growth contrast_check against the local page: text colour vs the colour actually painted behind it."""
    need_browser(ctx)
    import sys as _sys
    _sys.path.insert(0, str(ctx.kit_dir / "tools"))
    from contrast_check import check as _cc  # noqa: E402
    if not ctx.url or not ("127.0.0.1" in ctx.url or "localhost" in ctx.url):
        from .core import NeedsPage
        raise NeedsPage("local page URL", "pass --url http://127.0.0.1:<port><path> (the check hovers every control)")
    probs, n = [], 0
    try:
        for w in (1366, 390):
            p, rows = _cc(ctx.url, w)
            probs += [f"{w}px {x}" for x in p]
            n += len(rows)
    except Exception as e:  # noqa: BLE001
        if browser_failed(e):
            raise Skip("no headless browser installed (python3 -m playwright install chromium)", blocked=True)
        raise
    ctx.verdict(probs, f"{n} control states at AA contrast (rest, hover, focus; 1366 and 390)",
                "give the state its own text colour token that reads on its background, e.g. a filled button keeps light text on hover; re-run growth contrast_check (rule 36j)")


@check("ui.phone", "70", what="on phones no text draws under 12 px and every header, menu and footer control is a 24 x 24 px target; nothing scrolls or clips sideways at 360, 390, 820 and 1024 (measured in a real browser)", needs="live")
def phone(ctx):
    """Runs growth phone_check against the local page (rules 68 and 70)."""
    import sys as _sys
    _sys.path.insert(0, str(ctx.kit_dir / "tools"))
    need_browser(ctx)
    from phone_check import WIDTHS, check as _pc  # noqa: E402
    if not ctx.url or not ("127.0.0.1" in ctx.url or "localhost" in ctx.url):
        from .core import NeedsPage
        raise NeedsPage("local page URL", "pass --url http://127.0.0.1:<port><path> (the check loads the page at four widths)")
    try:
        probs = [f"{w}px {x}" for w in WIDTHS for x in _pc(ctx.url, w)]
    except Exception as e:  # noqa: BLE001
        if browser_failed(e):
            raise Skip("no headless browser installed (python3 -m playwright install chromium)", blocked=True)
        raise
    ctx.verdict(probs[:12] + ([f"+{len(probs) - 12} more"] if len(probs) > 12 else []),
                "no small text, small tap targets, clipped text or sideways scroll at 360, 390, 820 and 1024",
                "labels 12 px or more on screen (SVG text scales with its drawing: give phones their own larger labels); "
                "footer and menu links 24 px tall (padding or min-height); a wide table stacks as cards on phones or "
                "carries a visible scroll cue; re-run growth phone_check (rules 68, 70)")


# ---- fold surfaces (36f): read from the served page on every stack (2.3.0; was Next.js only) ----
def _reading_pair(ctx, ja, jb):
    """A post is one reading column (rule 49): its body folds (job 'read', one per heading) may share the plain surface.
    The header, the closing call and anything else still stand apart from their neighbours (2.4.4)."""
    return ctx.ptype == "post" and ja == "read" and jb == "read"


@check("page.surfaces", "36f", what="every fold has its own surface (plain, tint, warm, light geometry, dark) chosen by its job in the reader's journey; no two folds in a row share one", needs="live")
def surfaces(ctx):
    html = ctx.need_html()
    m = re.search(r"<main\b.*?</main>", html, re.S)
    tags = re.findall(r"<section\b[^>]*\bdata-fold=[^>]*>", m.group(0) if m else html)
    probs = []
    from .c_layout import is_legal
    legal = is_legal(ctx)                 # a legal page stays plain (rule 49): no act fold and no surface rhythm needed (2.4.1)
    if len(tags) < 3 and not legal:
        probs.append(f"only {len(tags)} folds found (sections with data-fold)")
    seq = []
    for t in tags:
        stop = (re.search(r'data-fold="([^"]*)"', t) or [None, "?"])[1]
        sf = (re.search(r'data-surface="([^"]*)"', t) or [None, ""])[1]
        job = (re.search(r'data-job="([^"]*)"', t) or [None, ""])[1]
        if sf not in SURFACES:
            probs.append(f"fold '{stop}': data-surface '{sf or 'missing'}' (one of {', '.join(sorted(SURFACES))})")
        if job not in JOBS:
            probs.append(f"fold '{stop}': data-job '{job or 'missing'}' (one of {', '.join(sorted(JOBS))})")
        seq.append((stop, sf, job))
    for (a, sa, ja), (b, sb, jb) in zip(seq, seq[1:]):
        if sa and sa == sb and not legal and not _reading_pair(ctx, ja, jb):     # a legal page is plain by design (rule 49): plain next to plain is honest there
            probs.append(f"folds '{a}' and '{b}' share the surface '{sa}'")
    kinds = {s for _, s, _ in seq if s}
    need_kinds = 2 if ctx.ptype == "post" else 3      # a post: the plain reading body plus a set-apart header or close
    if seq and len(kinds) < need_kinds and not legal:
        probs.append(f"only {len(kinds)} surface kinds on the page ({need_kinds} or more)")
    darks = [i for i, (_, s, _) in enumerate(seq) if s == "dark"]
    if len(darks) > 2:
        probs.append(f"{len(darks)} dark folds (2 at most)")
    if seq and not legal and not any(j == "act" for _, _, j in seq):
        probs.append("no fold has the job 'act' (the call to action)")
    from .c_cta import page_css
    try:
        css = page_css(ctx)
    except Exception:
        css = ""
    geo = [s for s in kinds if s.startswith("geo-")]
    for g in geo:
        if not re.search(rf'\[data-surface="{g}"\]', css):
            probs.append(f"no CSS for data-surface=\"{g}\"")
    for sel, body in RULE.findall(css):
        if "data-surface" in sel and "geo-" in sel:
            for o in re.findall(r"opacity\s*:\s*([0-9.]+)", body):
                if float(o) > 0.08:
                    probs.append(f"{sel.strip()[-40:]}: pattern opacity {o} (0.08 at most, keep it faint)")
    ctx.verdict(probs, f"{len(seq)} folds, {len(kinds)} surface kinds, no repeats in a row: " + " / ".join(f"{s}:{j}" for _, s, j in seq),
                "give each fold data-surface and data-job from the shared set, alternate them, keep patterns faint (rule 36f)")


PAINT_JS = r"""
() => {
  const cs = (e, p) => getComputedStyle(e, p || null);   // keep the pseudo argument: ::before/::after layers paint surfaces too (#72)
  const solid = c => c && c !== 'transparent' && !/rgba\([^)]*,\s*0\)$/.test(c);
  const painted = e => {                      // the colour the reader sees behind the fold: its own, else the nearest ancestor's
    for (let n = e; n; n = n.parentElement) { const c = cs(n).backgroundColor; if (solid(c)) return c; }
    return 'rgb(255, 255, 255)';
  };
  const image = e => [cs(e), cs(e, '::before'), cs(e, '::after')].some(s => s.backgroundImage && s.backgroundImage !== 'none');
  const main = document.querySelector('main') || document.body;
  const page = painted(main);
  return [...main.querySelectorAll('section[data-fold]')].filter(s => s.getBoundingClientRect().height > 2).map(s => ({
    fold: s.dataset.fold, surface: s.dataset.surface || '', job: s.dataset.job || '', own: cs(s).backgroundColor,
    paint: painted(s), image: image(s), page }));
}
"""


@check("page.surfaces-paint", "36f", what="each fold's surface label matches what the reader sees: a non-plain label paints differently from the page, and no two folds in a row paint the same (issue #68)", needs="live")
def surfaces_paint(ctx):
    """Labels alone can lie (a fold labelled "tint" that paints transparent passed page.surfaces). Read each fold's painted
    background in a real browser at 1366, light theme."""
    ctx.need_html()
    need_browser(ctx)
    if not ctx.url:
        raise Skip("no page URL to open in a browser", blocked=True)
    from .c_layout import is_legal
    legal = is_legal(ctx)
    key = ("surfaces-paint", ctx.url)
    if key not in ctx.cache:
        from playwright.sync_api import sync_playwright
        try:
            with sync_playwright() as p:
                b = p.chromium.launch(headless=True)
                try:
                    c = b.new_context(viewport={"width": 1366, "height": 900}, color_scheme="light", reduced_motion="reduce")
                    pg = c.new_page()
                    pg.goto(ctx.url, wait_until="load", timeout=60000)
                    pg.wait_for_timeout(300)
                    ctx.cache[key] = pg.evaluate(PAINT_JS)
                    c.close()
                finally:
                    b.close()
        except Exception as e:  # noqa: BLE001
            if browser_failed(e):
                raise Skip(f"no headless browser to measure the page ({str(e).splitlines()[0][:80]})", blocked=True)
            raise
    folds = ctx.cache[key]
    if not folds:
        raise Skip("no section[data-fold] on the page (page.surfaces reports it)")
    probs = []
    for f in folds:
        if f["surface"] and f["surface"] != "plain" and f["paint"] == f["page"] and not f["image"]:
            probs.append(f"fold '{f['fold']}' is labelled '{f['surface']}' but paints the page's own colour {f['paint']}")
    if not legal:
        for a, b in zip(folds, folds[1:]):
            if a["paint"] == b["paint"] and a["image"] == b["image"] and not _reading_pair(ctx, a.get("job"), b.get("job")):
                probs.append(f"folds '{a['fold']}' and '{b['fold']}' paint the same background ({a['paint']}) whatever their labels say")
    ctx.verdict(probs, f"{len(folds)} folds: every label matches its paint, and neighbours differ",
                "paint each fold with the surface it is labelled (the shared surfaces CSS), or label it what it paints (rule 36f)")
