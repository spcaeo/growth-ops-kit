"""Colour maths: parsing, hex/RGB/HSL, mixing, WCAG contrast, clustering, tint and shade scales. Pure Python, no browser."""
from __future__ import annotations

import colorsys
import math
import re

SCALE_STEPS = (50, 100, 200, 300, 400, 500, 600, 700, 800, 900)
# share of white mixed in for the tints, share of black mixed in for the shades; 500 is the colour itself
TINTS = {50: 0.92, 100: 0.84, 200: 0.68, 300: 0.50, 400: 0.28}
SHADES = {600: 0.14, 700: 0.28, 800: 0.42, 900: 0.58}
HEX = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
FUNC = re.compile(r"^rgba?\(\s*([\d.]+%?)[\s,]+([\d.]+%?)[\s,]+([\d.]+%?)(?:\s*[,/]\s*([\d.]+%?))?\s*\)$", re.I)


def _chan(v: str) -> float:
    return float(v[:-1]) * 2.55 if v.endswith("%") else float(v)


def parse(value) -> tuple[int, int, int] | None:
    """(r, g, b) from "#0B6E4F", "#fff", "rgb(11, 110, 79)" or a [r, g, b(, a)] list; None when it is not a colour. Alpha is ignored."""
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        try:
            return tuple(max(0, min(255, int(round(float(x))))) for x in value[:3])
        except (TypeError, ValueError):
            return None
    if not isinstance(value, str):
        return None
    s = value.strip()
    m = HEX.match(s)
    if m:
        h = m.group(1)
        h = "".join(c * 2 for c in h) if len(h) == 3 else h
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    m = FUNC.match(s)
    if m:
        try:
            return tuple(max(0, min(255, int(round(_chan(m.group(i)))))) for i in (1, 2, 3))
        except ValueError:
            return None
    return None


def to_hex(c) -> str:
    """Upper-case #RRGGBB: the one spelling of a colour in a brand kit."""
    r, g, b = parse(c) or (0, 0, 0)
    return f"#{r:02X}{g:02X}{b:02X}"


def valid_hex(value) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"#[0-9A-Fa-f]{6}", value))


def rgb_str(c) -> str:
    r, g, b = parse(c)
    return f"rgb({r}, {g}, {b})"


def hsl(c) -> tuple[int, int, int]:
    r, g, b = parse(c)
    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    return int(round(h * 360)) % 360, int(round(s * 100)), int(round(l * 100))


def hsl_str(c) -> str:
    h, s, l = hsl(c)
    return f"hsl({h}, {s}%, {l}%)"


def composite(top, alpha: float, under) -> tuple[int, int, int]:
    """`top` at `alpha` painted over the opaque `under`."""
    t, u = parse(top), parse(under)
    return tuple(int(round(t[i] * alpha + u[i] * (1 - alpha))) for i in range(3))


def mix(a, b, share_b: float) -> str:
    """Hex of a mixed with b: share_b of b."""
    pa, pb = parse(a), parse(b)
    return to_hex([pa[i] * (1 - share_b) + pb[i] * share_b for i in range(3)])


def luminance(c) -> float:
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = parse(c)
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a, b) -> float:
    """WCAG contrast ratio (the same maths as contrast_check.ratio, which this agrees with: a test compares them)."""
    la, lb = luminance(a), luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def grade(ratio: float, large: bool = False) -> str:
    """"AAA", "AA" or "fail" for normal text (4.5 AA, 7 AAA); large text needs 3 and 4.5."""
    aa, aaa = (3.0, 4.5) if large else (4.5, 7.0)
    return "AAA" if ratio >= aaa else "AA" if ratio >= aa else "fail"


def lab(c) -> tuple[float, float, float]:
    def lin(v):
        v /= 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(x) for x in parse(c))
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t):
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    return 116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z))


def delta_e(a, b) -> float:
    la, lb = lab(a), lab(b)
    return math.sqrt(sum((la[i] - lb[i]) ** 2 for i in range(3)))


def chroma(c) -> float:
    """How colourful (0 for a grey): the distance from the grey axis in Lab."""
    _, a, b = lab(c)
    return math.hypot(a, b)


def cluster(items, threshold: float = 2.5):
    """Merge near-duplicate colours. items: [(colour, weight)]. Returns [{"hex", "weight", "members"}] heaviest first; each cluster
    takes the colour of its heaviest member, and a colour joins the nearest cluster within `threshold` (delta E; about 2.3 is the smallest difference an eye sees)."""
    merged: dict[str, float] = {}
    for c, w in items:
        if parse(c) is None or w <= 0:
            continue
        h = to_hex(c)
        merged[h] = merged.get(h, 0.0) + float(w)
    out: list[dict] = []
    for h, w in sorted(merged.items(), key=lambda kv: (-kv[1], kv[0])):
        near = min(out, key=lambda k: delta_e(k["hex"], h), default=None)
        if near is not None and delta_e(near["hex"], h) <= threshold:
            near["weight"] += w
            near["members"].append(h)
        else:
            out.append({"hex": h, "weight": w, "members": [h]})
    out.sort(key=lambda k: (-k["weight"], k["hex"]))
    return out


def scale(c) -> dict[int, str]:
    """{50: hex ... 900: hex}: tints toward white, the colour itself at 500, shades toward black."""
    out = {}
    for step in SCALE_STEPS:
        if step in TINTS:
            out[step] = mix(c, "#FFFFFF", TINTS[step])
        elif step in SHADES:
            out[step] = mix(c, "#000000", SHADES[step])
        else:
            out[step] = to_hex(c)
    return out
