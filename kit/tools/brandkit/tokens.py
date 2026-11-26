"""brand.json -> one neutral model of the design tokens, the contrast table, and every export format (CSS, DTCG JSON, Tailwind, SCSS).
Pure functions that return text: the same brand.json always gives the same bytes."""
from __future__ import annotations

import json
import re

from . import colors as C
from .store import ROLES, SCALE_LEVELS, is_leaf, val

SCALED = ("primary", "accent", "success", "warning", "error")
GENERIC = {"serif", "sans-serif", "monospace", "system-ui", "cursive", "fantasy", "ui-sans-serif", "ui-serif", "ui-monospace", "-apple-system"}


def extra_colors(tree: dict) -> list[str]:
    """Colours the owner added beyond the standard roles (colors.partner): a hex value that is not a role or the palette list."""
    return sorted(k for k, v in (tree.get("colors") or {}).items() if k not in ROLES and k != "palette" and is_leaf(v) and C.valid_hex(v.get("value")))


def role_colors(tree: dict) -> dict[str, str]:
    """{role: hex} for every colour that exists, roles first, then added colours, each in a fixed order."""
    out = {}
    for r in ROLES + extra_colors(tree):
        v = val(tree, f"colors.{r}")
        if C.valid_hex(v):
            out[r] = v.upper()
    return out


def font_stack(node) -> list[str]:
    """["Inter", "system-ui", "sans-serif"] from a font leaf: its stack when it has one, else the name and a generic fallback."""
    name = node["value"]
    stack = node.get("stack") or ""
    names = [p.strip().strip("'\"") for p in re.findall(r"""(?:[^,'"]|'[^']*'|"[^"]*")+""", stack) if p.strip()] if stack else []
    if not names or names[0] != name:
        names = [name] + [n for n in names if n != name]
    if not any(n in GENERIC for n in names):
        names.append("monospace" if re.search(r"(?i)mono|code|courier", name) else "sans-serif")
    return names


def css_stack(names: list[str]) -> str:
    return ", ".join(n if (n in GENERIC or re.fullmatch(r"[A-Za-z][\w-]*", n)) else f'"{n}"' for n in names)


def px_num(v) -> float:
    m = re.match(r"^\s*(-?[\d.]+)", str(v))
    return float(m.group(1)) if m else 0.0


def model(tree: dict) -> dict:
    """The tokens in one shape every exporter reads."""
    cols = role_colors(tree)
    scales = {}
    for r in SCALED:
        if r in cols:
            scales[r] = C.scale(cols[r])
    if "text" in cols:
        scales["neutral"] = C.scale(cols["text"])
    fams = {}
    for role in ("heading", "body", "mono"):
        n = (tree.get("typography") or {}).get("families", {}).get(role)
        if is_leaf(n):
            fams[role] = font_stack(n)
    scale = {}
    for lvl in SCALE_LEVELS:
        n = (tree.get("typography") or {}).get("scale", {}).get(lvl)
        if is_leaf(n):
            scale[lvl] = {"size": px_num(n["value"]), "line_height": float(n.get("line_height") or 1.5), "weight": int(n.get("weight") or 400),
                          "letter_spacing": px_num(n.get("letter_spacing") or 0), "family": "heading" if lvl.startswith("h") else "body"}
    steps = val(tree, "spacing.steps") or []
    radius = {k: val(tree, f"radius.{k}") for k in ("control", "card", "pill") if val(tree, f"radius.{k}") is not None}
    shadows = {k: val(tree, f"shadows.{k}") for k in ("sm", "md", "lg") if val(tree, f"shadows.{k}")}
    return {"colors": cols, "scales": scales, "families": fams, "scale": scale, "unit": val(tree, "spacing.unit") or 8,
            "steps": [int(s) for s in steps if isinstance(s, (int, float))], "radius": radius, "shadows": shadows,
            "button": _button_tokens(tree)}


def _button_tokens(tree: dict) -> dict:
    out = {}
    for variant in ("primary", "secondary"):
        node = ((tree.get("components") or {}).get("button") or {}).get(variant)
        if not isinstance(node, dict):
            continue
        for state in ("rest", "hover", "focus"):
            for k, v in (node.get(state) or {}).items():
                if is_leaf(v) and v["value"] not in (None, ""):
                    out[f"{variant}-{state}-{k.replace('_', '-')}"] = v["value"]
    return dict(sorted(out.items()))


# ---- contrast ------------------------------------------------------------------------------------------------------------
PAIRS = [("text", "background", "Body text on the page", "body"), ("text", "surface", "Body text on panels", "body"),
         ("muted", "background", "Muted text on the page", "body"), ("muted", "surface", "Muted text on panels", "body"),
         ("link", "background", "Links on the page", "body"), ("link", "surface", "Links on panels", "body"),
         ("onPrimary", "primary", "Button text on the primary colour", "button"), ("primary", "background", "Primary colour used as text or an icon", "accent"),
         ("accent", "background", "Accent colour used as text or an icon", "accent"), ("success", "background", "Success message", "status"),
         ("warning", "background", "Warning message", "status"), ("error", "background", "Error message", "status")]


def contrast_table(tree: dict) -> list[dict]:
    """The usable text and background pairs with their WCAG ratio and grade. `use` says what the pair is for: body and button pairs
    are the ones `growth brand-kit check` insists on."""
    cols = role_colors(tree)
    rows = []
    for fg, bg, label, use in PAIRS:
        if fg in cols and bg in cols:
            rows.append(_row(label, use, cols[fg], cols[bg], fg, bg))
    btn = ((tree.get("components") or {}).get("button") or {})
    for variant in ("primary", "secondary"):
        node = btn.get(variant) or {}
        for state in ("hover", "focus"):
            st, rest = node.get(state) or {}, node.get("rest") or {}
            fgv = val(st, "color") or val(rest, "color")
            bgv = val(st, "background") or val(rest, "background")
            if C.valid_hex(fgv) and C.valid_hex(bgv) and state in node and (val(st, "color") or val(st, "background")):
                rows.append(_row(f"{variant.capitalize()} button text, {state}", "button", fgv.upper(), bgv.upper(), f"button.{variant}.{state}.color", f"button.{variant}.{state}.background"))
    sec = btn.get("secondary") or {}
    rest = sec.get("rest") or {}
    if C.valid_hex(val(rest, "color")) and not C.valid_hex(val(rest, "background")) and "background" in cols:
        rows.append(_row("Secondary button text (outlined) on the page", "button", val(rest, "color").upper(), cols["background"], "button.secondary.rest.color", "background"))
    elif C.valid_hex(val(rest, "color")) and C.valid_hex(val(rest, "background")):
        rows.append(_row("Secondary button text on its fill", "button", val(rest, "color").upper(), val(rest, "background").upper(), "button.secondary.rest.color", "button.secondary.rest.background"))
    return rows


def _row(label, use, fg, bg, fg_name, bg_name) -> dict:
    r = C.contrast(fg, bg)
    return {"label": label, "use": use, "fg": fg, "bg": bg, "fg_name": fg_name, "bg_name": bg_name, "ratio": round(r, 2), "grade": C.grade(r),
            "large": C.grade(r, large=True)}


def failures(tree: dict) -> list[dict]:
    return [r for r in contrast_table(tree) if r["use"] in ("body", "button") and r["grade"] == "fail"]


# ---- exports -------------------------------------------------------------------------------------------------------------
def _kebab(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "-", name).lower()


def _num(n) -> str:
    return str(int(n)) if float(n) == int(n) else str(round(float(n), 3))


def tokens_css(tree: dict) -> str:
    m = model(tree)
    L = ["/* Brand tokens. Built by `growth brand-kit build` from brand/brand.json: change brand/brand.overrides.json, not this file. */", ":root {"]
    for r, h in m["colors"].items():
        L.append(f"  --color-{_kebab(r)}: {h};")
    for r, steps in m["scales"].items():
        L += [f"  --color-{r}-{s}: {h};" for s, h in steps.items()]
    for role, names in m["families"].items():
        L.append(f"  --font-{role}: {css_stack(names)};")
    for lvl, t in m["scale"].items():
        L.append(f"  --text-{lvl}: {_num(t['size'])}px;")
        L.append(f"  --leading-{lvl}: {_num(t['line_height'])};")
        L.append(f"  --weight-{lvl}: {t['weight']};")
        if t["letter_spacing"]:
            L.append(f"  --tracking-{lvl}: {_num(t['letter_spacing'])}px;")
    L.append(f"  --space-unit: {_num(m['unit'])}px;")
    L += [f"  --space-{i}: {s}px;" for i, s in enumerate(m["steps"], start=1)]
    for k, v in m["radius"].items():
        L.append(f"  --radius-{k}: {_num(v)}px;")
    for k, v in m["shadows"].items():
        L.append(f"  --shadow-{k}: {v};")
    for k, v in m["button"].items():
        if "padding" in k or "color" in k or "background" in k or "radius" in k or "font" in k or "outline" in k or "shadow" in k:
            L.append(f"  --button-{k}: {_num(v) + 'px' if isinstance(v, (int, float)) and ('radius' in k or 'outline-width' in k or 'outline-offset' in k) else v};")
    L.append("}")
    return "\n".join(L) + "\n"


SHADOW = re.compile(r"^(inset\s+)?(rgba?\([^)]*\)|#[0-9a-fA-F]{3,8})\s+(-?[\d.]+)px\s+(-?[\d.]+)px\s+(-?[\d.]+)px(?:\s+(-?[\d.]+)px)?$")


def _shadow_token(v: str):
    m = SHADOW.match(v.strip()) or re.match(r"^(inset\s+)?(-?[\d.]+)px\s+(-?[\d.]+)px\s+(-?[\d.]+)px(?:\s+(-?[\d.]+)px)?\s+(rgba?\([^)]*\)|#[0-9a-fA-F]{3,8})$", v.strip())
    if not m:
        return None
    g = m.groups()
    color, x, y, blur, spread = (g[1], g[2], g[3], g[4], g[5]) if g[1].startswith(("rgb", "#")) else (g[5], g[1], g[2], g[3], g[4])
    if g[0] or color is None:
        return None
    rgb = re.match(r"rgba?\(\s*(\d+)[\s,]+(\d+)[\s,]+(\d+)(?:[\s,/]+([\d.]+))?", color)
    if rgb:
        a = float(rgb.group(4)) if rgb.group(4) else 1.0
        color = C.to_hex([int(rgb.group(i)) for i in (1, 2, 3)]) + (f"{int(round(a * 255)):02X}" if a < 1 else "")
    return {"color": color, "offsetX": f"{_num(x)}px", "offsetY": f"{_num(y)}px", "blur": f"{_num(blur)}px", "spread": f"{_num(spread or 0)}px"}


def tokens_dtcg(tree: dict) -> str:
    """W3C Design Tokens (DTCG) format: groups of {"$type", "$value", "$description"} tokens."""
    m = model(tree)
    tok = lambda t, v, d="": ({"$type": t, "$value": v, **({"$description": d} if d else {})})  # noqa: E731
    out: dict = {"color": {r: tok("color", h, f"colors.{r}") for r, h in m["colors"].items()}}
    out["colorScale"] = {r: {str(s): tok("color", h) for s, h in steps.items()} for r, steps in m["scales"].items()}
    out["font"] = {"family": {role: tok("fontFamily", names) for role, names in m["families"].items()}}
    out["typography"] = {}
    for lvl, t in m["scale"].items():
        fam = m["families"].get(t["family"]) or m["families"].get("body") or ["sans-serif"]
        out["typography"][lvl] = tok("typography", {"fontFamily": fam, "fontSize": f"{_num(t['size'])}px", "fontWeight": t["weight"], "lineHeight": t["line_height"],
                                                    "letterSpacing": f"{_num(t['letter_spacing'])}px"})
    out["spacing"] = {"unit": tok("dimension", f"{_num(m['unit'])}px")}
    out["spacing"].update({str(i): tok("dimension", f"{s}px") for i, s in enumerate(m["steps"], start=1)})
    out["radius"] = {k: tok("dimension", f"{_num(v)}px") for k, v in m["radius"].items()}
    sh = {k: _shadow_token(v) for k, v in m["shadows"].items()}
    out["shadow"] = {k: tok("shadow", v) for k, v in sh.items() if v}
    return json.dumps({k: v for k, v in out.items() if v}, indent=2, ensure_ascii=False) + "\n"


def tailwind_preset(tree: dict) -> str:
    m = model(tree)
    colors: dict = {}
    for r, h in m["colors"].items():
        if r in m["scales"] and r != "neutral":
            colors[r] = {"DEFAULT": h, **{str(s): c for s, c in m["scales"][r].items()}}
        else:
            colors[r] = h
    if "primary" in colors and "onPrimary" in m["colors"]:
        colors["primary"]["foreground"] = m["colors"]["onPrimary"]
        colors.pop("onPrimary", None)
    if "neutral" in m["scales"]:
        colors["neutral"] = {str(s): c for s, c in m["scales"]["neutral"].items()}
    theme = {"colors": colors, "fontFamily": {role: names for role, names in m["families"].items()},
             "fontSize": {lvl: [f"{_num(t['size'])}px", {"lineHeight": _num(t["line_height"]), "fontWeight": str(t["weight"]), **({"letterSpacing": f"{_num(t['letter_spacing'])}px"} if t["letter_spacing"] else {})}]
                          for lvl, t in m["scale"].items()},
             "borderRadius": {k: ("9999px" if v >= 999 else f"{_num(v)}px") for k, v in m["radius"].items()},
             "boxShadow": dict(m["shadows"])}
    theme = {k: v for k, v in theme.items() if v}
    body = json.dumps({"theme": {"extend": theme}}, indent=2, ensure_ascii=False)
    return ("// Tailwind preset. Built by `growth brand-kit build` from brand/brand.json: change brand/brand.overrides.json, not this file.\n"
            "// Use it:  presets: [require('./brand/exports/tailwind.brand.cjs')]\n"
            f"module.exports = {body};\n")


def tokens_scss(tree: dict) -> str:
    m = model(tree)
    L = ["// Brand tokens. Built by `growth brand-kit build` from brand/brand.json: change brand/brand.overrides.json, not this file."]
    L += [f"$color-{_kebab(r)}: {h};" for r, h in m["colors"].items()]
    for r, steps in m["scales"].items():
        L += [f"$color-{r}-{s}: {h};" for s, h in steps.items()]
    L += [f"$font-{role}: {css_stack(names)};" for role, names in m["families"].items()]
    for lvl, t in m["scale"].items():
        L += [f"$text-{lvl}: {_num(t['size'])}px;", f"$leading-{lvl}: {_num(t['line_height'])};", f"$weight-{lvl}: {t['weight']};"]
    L.append(f"$space-unit: {_num(m['unit'])}px;")
    L += [f"$space-{i}: {s}px;" for i, s in enumerate(m["steps"], start=1)]
    L += [f"$radius-{k}: {_num(v)}px;" for k, v in m["radius"].items()]
    L += [f"$shadow-{k}: {v};" for k, v in m["shadows"].items()]
    L.append("$colors: (" + ", ".join(f'"{r}": {h}' for r, h in m["colors"].items()) + ");")
    return "\n".join(L) + "\n"
