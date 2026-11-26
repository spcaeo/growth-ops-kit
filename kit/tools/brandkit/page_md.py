"""brand.json -> BRAND-GUIDELINES.md: the same guidelines as the page, in words. Pure function."""
from __future__ import annotations

from . import colors as C
from .store import SCALE_LEVELS, is_leaf, val
from .tokens import contrast_table, css_stack, model


def _src(node) -> str:
    return node.get("source", "") if isinstance(node, dict) else ""


def render(tree: dict, stamp: str = "") -> str:
    m = model(tree)
    name = val(tree, "name") or "Brand"
    meta = tree.get("meta") or {}
    L = [f"# {name} brand guidelines", ""]
    if val(tree, "tagline"):
        L += [val(tree, "tagline"), ""]
    L += [f"Built by `growth brand-kit build` from `brand/brand.json`{(' (read from ' + meta['base'] + ' on ' + meta['read_on'] + ')') if meta.get('base') and meta.get('read_on') else ''}. "
          "Change a value with `growth brand-kit set <path> <value>`, then `growth brand-kit build`. The `source` column says where each value came from: "
          "`site` (read from the website), `override` (set by the owner) or `default` (nothing was found, so a standard choice was made).", ""]
    L += ["## Colour", "", "| Role | Hex | RGB | HSL | Source |", "| --- | --- | --- | --- | --- |"]
    for r, h in m["colors"].items():
        L.append(f"| {r} | `{h}` | {C.rgb_str(h)} | {C.hsl_str(h)} | {_src((tree.get('colors') or {}).get(r))} |")
    for r, steps in m["scales"].items():
        L += ["", f"**{r} scale** (500 is the colour itself): " + ", ".join(f"{s} `{h}`" for s, h in steps.items())]
    L += ["", "### Contrast (WCAG 2.2)", "", "| Use | Pair | Ratio | Normal text | Large text |", "| --- | --- | ---: | --- | --- |"]
    for r in contrast_table(tree):
        L.append(f"| {r['label']} | `{r['fg']}` on `{r['bg']}` | {r['ratio']}:1 | {r['grade'] if r['grade'] != 'fail' else 'fails AA'} | {r['large'] if r['large'] != 'fail' else 'fails'} |")
    L += ["", "## Typography", ""]
    for role in ("heading", "body", "mono"):
        n = (tree.get("typography") or {}).get("families", {}).get(role)
        if is_leaf(n):
            w = ", ".join(str(x) for x in n.get("weights") or [])
            L.append(f"- **{role}**: {n['value']} (`{css_stack(m['families'][role])}`{', weights ' + w if w else ''}), source {_src(n)}")
    L += ["", "| Level | Size | Line height | Weight | Source |", "| --- | ---: | ---: | ---: | --- |"]
    for lvl in SCALE_LEVELS:
        t = m["scale"].get(lvl)
        if t:
            L.append(f"| {lvl} | {t['size']:g}px | {t['line_height']} | {t['weight']} | {_src(tree['typography']['scale'][lvl])} |")
    L += ["", "## Buttons and links", ""]
    node = ((tree.get("components") or {}).get("button") or {})
    for variant in ("primary", "secondary"):
        if variant not in node:
            continue
        for state in ("rest", "hover", "focus"):
            st = node[variant].get(state) or {}
            bits = [f"{k.replace('_', ' ')} {v['value']}" for k, v in sorted(st.items()) if is_leaf(v) and v["value"] not in (None, "")]
            if bits:
                L.append(f"- **{variant}, {state}**: " + "; ".join(bits))
    if not node:
        L.append("- No button was found on the pages read.")
    cta = (tree.get("cta") or {}).get("main")
    if is_leaf(cta):
        L += ["", f"The one call to action: **{cta['value']}**."]
    L += ["", "## Spacing, radius and shadow", "", f"- Grid unit: {m['unit']}px; steps: " + ", ".join(f"{s}px" for s in m["steps"])]
    L += [f"- Radius {k}: {'fully round' if v >= 999 else str(v) + 'px'}" for k, v in m["radius"].items()]
    L += [f"- Shadow {k}: `{v}`" for k, v in m["shadows"].items()]
    L += ["", "## Logo", ""]
    lg = tree.get("logo") or {}
    if is_leaf(lg.get("primary")):
        p = lg["primary"]
        L.append(f"- Logo ({p.get('kind', '')}, {p.get('width', '?')} x {p.get('height', '?')}px on the site): `{p['value'] if p['value'] != 'inline svg' else 'inline SVG in the page header'}`")
    else:
        L.append("- No logo was found in the page header.")
    L += [f"- {k}: `{v['value']}`" for k, v in sorted(lg.items()) if is_leaf(v) and k != "primary"]
    L += [f"- Clear space: {val(tree, 'logo.clearSpace')} on every side; smallest height {val(tree, 'logo.minHeight')}px.",
          "- Do not stretch, squash or recolour it, and do not put it on a busy or low-contrast background."]
    v = tree.get("voice") or {}
    L += ["", "## Voice and words", ""]
    if is_leaf(v.get("principles")):
        L += [f"- {x}" for x in v["principles"]["value"]]
    if is_leaf(v.get("avoid")):
        L += ["", "Words never to use: " + ", ".join(v["avoid"]["value"])]
    c = tree.get("cta") or {}
    if c:
        L.append("")
        if is_leaf(c.get("main")):
            L.append(f"- Main call to action: {c['main']['value']}")
        if is_leaf(c.get("others")):
            L.append("- Other wordings on the site: " + ", ".join(c["others"]["value"]))
        if is_leaf(c.get("booking")):
            L.append(f"- Booking link: {c['booking']['value']}")
    if len(L) and L[-1] == "":
        L.pop()
    ct = tree.get("contact") or {}
    L += ["", "## Contact facts", ""]
    for label, key in (("Legal name", "legal_name"), ("Address", "address"), ("Emails", "emails"), ("Phones", "phones")):
        n = ct.get(key)
        if is_leaf(n):
            L.append(f"- {label}: " + (", ".join(n["value"]) if isinstance(n["value"], list) else str(n["value"])))
    if is_leaf(ct.get("social")):
        L.append("- Social: " + ", ".join(f"{s['network']} {s['url']}" for s in ct["social"]["value"]))
    if not ct:
        L.append("- Nothing yet: run `growth brand-scan`, then `growth brand-kit learn` again.")
    L += ["", f"<!-- brand.json {stamp[:12]} -->"]
    return "\n".join(L) + "\n"
