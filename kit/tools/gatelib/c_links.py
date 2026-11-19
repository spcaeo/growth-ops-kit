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
        raise Skip("browser checks are switched off for this run (--no-browser)")
    try:
        import playwright.sync_api  # noqa: F401
    except ImportError:
        raise Skip("playwright is not installed (pip install playwright; python3 -m playwright install chromium)")


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
            raise Skip("no headless browser installed (python3 -m playwright install chromium)")
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
            raise Skip("no headless browser installed (python3 -m playwright install chromium)")
        raise
    ctx.verdict(probs[:12] + ([f"+{len(probs) - 12} more"] if len(probs) > 12 else []),
                "no small text, small tap targets, clipped text or sideways scroll at 360, 390, 820 and 1024",
                "labels 12 px or more on screen (SVG text scales with its drawing: give phones their own larger labels); "
                "footer and menu links 24 px tall (padding or min-height); a wide table stacks as cards on phones or "
                "carries a visible scroll cue; re-run growth phone_check (rules 68, 70)")
