"""brand.json -> brand-guidelines.html: one self-contained page (inline CSS, no script, no external file) a person can open, share or
print. Pure function: the same brand.json and assets give the same bytes."""
from __future__ import annotations

import html
import re

from . import colors as C
from .store import SCALE_LEVELS, is_leaf, val
from .tokens import contrast_table, css_stack, model

CSS = """
:root{--bg:#fff;--fg:#14171a;--mut:#5b6670;--line:#dfe3e8;--card:#f6f7f9;--ok:#0a7d45;--warn:#9a5b00;--bad:#b3261e}
@media (prefers-color-scheme:dark){:root{--bg:#101316;--fg:#eceff1;--mut:#9aa6b0;--line:#2a3138;--card:#171b1f}}
*{box-sizing:border-box}html{scroll-padding-top:64px}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
a{color:inherit}main{max-width:1040px;margin:0 auto;padding:0 20px 80px}
nav.top{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);padding:10px 20px;display:flex;gap:16px;flex-wrap:wrap;font-size:14px;z-index:5}
nav.top a{color:var(--mut);text-decoration:none}nav.top a:hover{color:var(--fg)}
header.hero{padding:56px 0 24px}header.hero h1{font-size:40px;line-height:1.1;margin:0 0 8px}header.hero p{color:var(--mut);margin:0;max-width:62ch}
section{padding:36px 0;border-top:1px solid var(--line)}h2{font-size:26px;margin:0 0 6px}h3{font-size:17px;margin:28px 0 10px}p.lead{color:var(--mut);margin:0 0 18px;max-width:70ch}
.grid{display:grid;gap:14px;grid-template-columns:repeat(auto-fill,minmax(220px,1fr))}
.sw{border:1px solid var(--line);border-radius:10px;overflow:hidden;background:var(--card)}.sw .chip{height:92px;display:flex;align-items:flex-end;padding:8px 10px;font-weight:600}
.sw dl{margin:0;padding:10px 12px;font-size:13px}.sw dt{font-weight:600;font-size:14px}.sw dd{margin:2px 0 0;color:var(--mut);font-family:ui-monospace,Menlo,Consolas,monospace}
.badge{display:inline-block;font-size:11px;border:1px solid var(--line);border-radius:999px;padding:0 7px;margin-left:6px;color:var(--mut);font-weight:500}
.badge.override{border-color:var(--ok);color:var(--ok)}.badge.default{border-color:var(--warn);color:var(--warn)}
.scale{display:flex;border-radius:10px;overflow:hidden;border:1px solid var(--line);margin:6px 0 14px}.scale div{flex:1;min-width:0;padding:22px 4px 6px;font-size:11px;text-align:center;font-family:ui-monospace,Menlo,monospace}
table{border-collapse:collapse;width:100%;font-size:14px}th,td{border-bottom:1px solid var(--line);padding:8px 10px;text-align:left;vertical-align:middle}th{color:var(--mut);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.04em}
.pair{display:inline-block;padding:3px 10px;border-radius:6px;border:1px solid var(--line);font-weight:600}.g-AAA,.g-AA{color:var(--ok);font-weight:600}.g-fail{color:var(--bad);font-weight:600}
.spec{border:1px solid var(--line);border-radius:10px;padding:16px 18px;margin:10px 0;background:var(--card)}.spec small{color:var(--mut);font-family:ui-monospace,Menlo,monospace;font-size:12px}
.states{display:grid;gap:16px;grid-template-columns:repeat(auto-fill,minmax(210px,1fr))}.states>div{border:1px solid var(--line);border-radius:10px;padding:16px;background:var(--card)}.states small{display:block;color:var(--mut);margin-bottom:10px;font-size:12px;text-transform:uppercase;letter-spacing:.04em}
.bar{background:var(--mut);height:14px;border-radius:3px;margin:5px 0}.box{display:inline-block;background:var(--card);border:1px solid var(--line);padding:18px 22px;margin:0 14px 14px 0;font-size:13px}
.logo-stage{display:flex;gap:18px;flex-wrap:wrap}.logo-card{border:1px solid var(--line);border-radius:10px;padding:18px;background:var(--stage,#fff);color:var(--stage-fg,#14171a);min-width:200px;overflow:hidden}.logo-card small{display:block;color:var(--stage-fg,#5b6670);opacity:.8;margin-top:10px;font-size:12px}
.svgbox svg{display:block;width:100%;height:100%}.clear{display:inline-block;outline:1px dashed #d64045;position:relative}.clear>span{display:block;outline:1px solid #b9c0c7}
.dd{display:grid;gap:14px;grid-template-columns:repeat(auto-fill,minmax(200px,1fr))}.dd .do small{color:var(--ok)}.dd .dont small{color:var(--bad)}
ul.words{padding-left:20px}code,.mono{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:13px}.tag{display:inline-block;background:var(--card);border:1px solid var(--line);border-radius:6px;padding:2px 8px;margin:0 6px 6px 0;font-size:13px}
footer{padding:28px 0;color:var(--mut);font-size:13px;border-top:1px solid var(--line)}
@media print{nav.top{display:none}section{break-inside:avoid}}
@media (max-width:640px){header.hero h1{font-size:30px}}
"""


def e(x) -> str:
    return html.escape(str(x), quote=True)


def _badge(node) -> str:
    s = node.get("source", "") if isinstance(node, dict) else ""
    return f'<span class="badge {e(s)}">{e(s)}</span>' if s else ""


def _on(hex_color: str) -> str:
    return "#000000" if C.contrast("#000000", hex_color) >= C.contrast("#FFFFFF", hex_color) else "#FFFFFF"


def safe_svg(markup: str) -> str:
    """Inline SVG without scripts, event handlers or external references."""
    s = re.sub(r"(?is)<script.*?</script>|<foreignObject.*?</foreignObject>", "", markup or "")
    s = re.sub(r"(?i)\son[a-z]+\s*=\s*(\"[^\"]*\"|'[^']*')", "", s)
    return re.sub(r"(?i)(href|xlink:href)\s*=\s*(\"(?!#|data:image/)[^\"]*\"|'(?!#|data:image/)[^']*')", "", s)


def logo_markup(tree: dict, assets: dict, style: str = "") -> str:
    node = (tree.get("logo") or {}).get("primary")
    if not is_leaf(node):
        return ""
    st = f' style="{e(style)}"' if style else ""
    h = int(node.get("height") or 40)
    if node.get("svg"):
        w = int(node.get("width") or h)
        return f'<span class="svgbox" style="display:inline-block;width:{w}px;height:{h}px;{e(style)}">{safe_svg(node["svg"])}</span>'
    src = assets.get("logo") or node["value"]
    if not src or src == "inline svg":
        return ""
    return f'<img src="{e(src)}" alt="{e(node.get("alt") or "logo")}" height="{h}"{st}>'


def _btn_style(tree: dict, variant: str, state: str, mod=None) -> str:
    node = (((tree.get("components") or {}).get("button") or {}).get(variant) or {})
    rest = node.get("rest") or {}
    st = node.get(state) or {}
    g = lambda k: val(st, k) if val(st, k) not in (None, "") else val(rest, k)  # noqa: E731
    parts = []
    bgc = g("background")
    if bgc:
        parts.append(f"background:{bgc}")
    else:
        parts.append("background:transparent")
    if g("color"):
        parts.append(f"color:{g('color')}")
    if g("border_color"):
        parts.append(f"border:{g('border_width') or 1}px solid {g('border_color')}")
    else:
        parts.append("border:0")
    parts.append(f"border-radius:{g('radius') if g('radius') is not None else 8}px")
    parts.append(f"padding:{g('padding') or '12px 24px'}")
    parts.append(f"min-height:{g('height') or 44}px;display:inline-flex;align-items:center;white-space:nowrap;box-sizing:border-box")
    parts.append(f"font:{g('font_weight') or 600} {g('font_size') or '16px'}/1.2 var(--bk-body)")
    if g("shadow"):
        parts.append(f"box-shadow:{g('shadow')}")
    if g("text_transform"):
        parts.append(f"text-transform:{g('text_transform')}")
    if state == "focus" and val(st, "outline_color"):
        parts.append(f"outline:{val(st, 'outline_width') or 2}px solid {val(st, 'outline_color')};outline-offset:{val(st, 'outline_offset') or 2}px")
    if state == "hover" and val(st, "transform"):
        parts.append(f"transform:{val(st, 'transform')}")
    return ";".join(parts)


def render(tree: dict, assets: dict | None = None, stamp: str = "") -> str:
    assets = assets or {}
    m = model(tree)
    name = val(tree, "name") or "Brand"
    tagline = val(tree, "tagline") or ""
    fam = {r: css_stack(n) for r, n in m["families"].items()}
    root = f"--bk-body:{fam.get('body', 'system-ui, sans-serif')};--bk-head:{fam.get('heading', fam.get('body', 'system-ui, sans-serif'))};--bk-mono:{fam.get('mono', 'ui-monospace, Menlo, monospace')}"
    out = [f'<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
           f"<title>{e(name)} brand guidelines</title><style>{CSS}:root{{{root}}}</style></head><body>",
           '<nav class="top"><strong>' + e(name) + '</strong><a href="#colour">Colour</a><a href="#type">Type</a><a href="#buttons">Buttons</a><a href="#shape">Spacing and shape</a>'
           '<a href="#logo">Logo</a><a href="#voice">Voice and words</a><a href="#contact">Contact</a></nav><main>',
           f'<header class="hero"><h1>{e(name)} brand guidelines</h1><p>{e(tagline) or "How the brand looks and sounds, read from the site and fine-tuned by its owner."}</p></header>']
    out.append(_colour(tree, m))
    out.append(_type(tree, m))
    out.append(_buttons(tree))
    out.append(_shape(m))
    out.append(_logo(tree, assets))
    out.append(_voice(tree))
    out.append(_contact(tree))
    meta = tree.get("meta") or {}
    out.append(f'</main><footer><div style="max-width:1040px;margin:0 auto;padding:0 20px">Built by <code>growth brand-kit build</code>'
               f"{(' from ' + e(meta.get('base'))) if meta.get('base') else ''}{(', read on ' + e(meta.get('read_on'))) if meta.get('read_on') else ''}. "
               f"Change a value with <code>growth brand-kit set &lt;path&gt; &lt;value&gt;</code>; then <code>growth brand-kit build</code>. brand.json {e(stamp[:12])}</div></footer></body></html>\n")
    return "\n".join(out)


def _colour(tree, m) -> str:
    sw = []
    for r, h in m["colors"].items():
        node = (tree.get("colors") or {}).get(r) or {}
        rgb = C.rgb_str(h)
        why = node.get("evidence") or ""
        sw.append(f'<div class="sw"><div class="chip" style="background:{h};color:{_on(h)}">{e(r)}</div><dl><dt>{e(r)}{_badge(node)}</dt>'
                  f"<dd>{h}</dd><dd>{rgb}</dd><dd>{C.hsl_str(h)}</dd>" + (f'<dd style="font-family:inherit">{e(why)}</dd>' if why else "") + "</dl></div>")
    scales = []
    for r, steps in m["scales"].items():
        cells = "".join(f'<div style="background:{h};color:{_on(h)}">{s}<br>{h[1:]}</div>' for s, h in steps.items())
        scales.append(f"<h3>{e(r)} scale</h3><div class=\"scale\">{cells}</div>")
    rows = []
    for r in contrast_table(tree):
        rows.append(f'<tr><td>{e(r["label"])}</td><td><span class="pair" style="background:{r["bg"]};color:{r["fg"]}">Aa</span></td>'
                    f'<td class="mono">{r["fg"]} on {r["bg"]}</td><td>{r["ratio"]}:1</td><td class="g-{r["grade"]}">{r["grade"] if r["grade"] != "fail" else "fails AA"}</td>'
                    f'<td class="g-{r["large"]}">{r["large"] if r["large"] != "fail" else "fails"}</td></tr>')
    pal = (tree.get("colors") or {}).get("palette")
    extra = ""
    if is_leaf(pal) and pal["value"]:
        extra = '<h3>Other colours on the site</h3><div class="grid">' + "".join(
            f'<div class="sw"><div class="chip" style="background:{p["hex"]};color:{_on(p["hex"])}"></div><dl><dt>{p["hex"]}</dt><dd>{p["share"]}% of what is painted</dd></dl></div>' for p in pal["value"]) + "</div>"
    return ('<section id="colour"><h2>Colour</h2><p class="lead">Every colour has a job. Use the role, not the hex, so a change here changes everywhere.</p>'
            f'<div class="grid">{"".join(sw)}</div>{"".join(scales)}{extra}'
            '<h3>Contrast (WCAG 2.2)</h3><p class="lead">AA needs 4.5:1 for normal text and 3:1 for large text (24px, or 19px bold). AAA needs 7:1 and 4.5:1.</p>'
            '<table><tr><th>Use</th><th>Sample</th><th>Pair</th><th>Ratio</th><th>Normal text</th><th>Large text</th></tr>' + "".join(rows) + "</table></section>")


def _type(tree, m) -> str:
    fams = []
    for role in ("heading", "body", "mono"):
        n = (tree.get("typography") or {}).get("families", {}).get(role)
        if is_leaf(n):
            w = ", ".join(str(x) for x in n.get("weights") or [])
            fams.append(f'<div class="spec"><small>{e(role)}{_badge(n)}</small><div style="font:400 28px/1.3 {css_stack(m["families"][role])}">{e(n["value"])}: The quick brown fox jumps over the lazy dog</div>'
                        f'<small>{e(css_stack(m["families"][role]))}{(" · weights " + e(w)) if w else ""}</small></div>')
    rows = []
    for lvl in SCALE_LEVELS:
        t = m["scale"].get(lvl)
        if not t:
            continue
        node = tree["typography"]["scale"][lvl]
        famcss = css_stack(m["families"].get(t["family"]) or m["families"].get("body") or ["sans-serif"])
        sample = {"small": "Small print and captions", "body": "Body copy is set for easy reading at this size and line height."}.get(lvl, f"Heading level {lvl[1:]}")
        rows.append(f'<div class="spec"><div style="font:{t["weight"]} {t["size"]}px/{t["line_height"]} {famcss};letter-spacing:{t["letter_spacing"]}px">{e(sample)}</div>'
                    f'<small>{lvl} · {int(t["size"]) if t["size"] == int(t["size"]) else t["size"]}px · line height {t["line_height"]} · weight {t["weight"]}{_badge(node)}</small></div>')
    return f'<section id="type"><h2>Typography</h2><p class="lead">Two voices at most: a heading font and a body font.</p>{"".join(fams)}<h3>Type scale</h3>{"".join(rows)}</section>'


def _buttons(tree) -> str:
    blocks = []
    node = ((tree.get("components") or {}).get("button") or {})
    for variant in ("primary", "secondary"):
        if variant not in node:
            continue
        label = val(node[variant], "text") or ("Book a call" if variant == "primary" else "Learn more")
        cells = "".join(f'<div><small>{s}</small><span style="display:inline-block;{_btn_style(tree, variant, s)}">{e(label)}</span></div>' for s in ("rest", "hover", "focus"))
        blocks.append(f"<h3>{variant.capitalize()} button</h3><div class=\"states\">{cells}</div>")
    link = (tree.get("components") or {}).get("link") or {}
    if link:
        lr, lh = link.get("rest") or {}, link.get("hover") or {}
        blocks.append('<h3>Links in text</h3><div class="states"><div><small>rest</small>'
                      f'<a style="color:{val(lr, "color") or val(tree, "colors.link")};text-decoration:{val(lr, "text_decoration") or "underline"}" href="#buttons">A link inside a sentence</a></div>'
                      f'<div><small>hover</small><a style="color:{val(lh, "color") or val(lr, "color") or val(tree, "colors.link")};text-decoration:{val(lh, "text_decoration") or "underline"}" href="#buttons">A link inside a sentence</a></div></div>')
    cta = (tree.get("cta") or {}).get("main")
    note = f'<p class="lead">The one call to action: <strong>{e(cta["value"])}</strong>. Use this wording on the primary button everywhere.</p>' if is_leaf(cta) else ""
    return f'<section id="buttons"><h2>Buttons and links</h2>{note}{"".join(blocks) or "<p class=lead>No button was found on the pages read; the primary colour drives the defaults.</p>"}</section>'


def _shape(m) -> str:
    sp = "".join(f'<div style="display:flex;align-items:center;gap:12px;margin:4px 0"><span class="mono" style="width:70px">space-{i}</span><span style="display:block;height:14px;width:{s}px;background:var(--mut);border-radius:2px"></span><span class="mono">{s}px</span></div>'
                  for i, s in enumerate(m["steps"], start=1))
    rad = "".join(f'<div class="box" style="border-radius:{min(int(v), 40)}px">{e(k)}<br><span class="mono">{"fully round" if v >= 999 else str(int(v)) + "px"}</span></div>' for k, v in m["radius"].items())
    sh = "".join(f'<div class="box" style="box-shadow:{v};background:#fff;color:#14171a">{e(k)}</div>' for k, v in m["shadows"].items())
    return (f'<section id="shape"><h2>Spacing, radius and shadow</h2><p class="lead">Spacing follows a {int(m["unit"])}px grid.</p>{sp}'
            f'<h3>Corner radius</h3>{rad}' + (f"<h3>Shadows</h3><div style=\"padding:8px\">{sh}</div>" if sh else "") + "</section>")


def _logo(tree, assets) -> str:
    lg = tree.get("logo") or {}
    mark = logo_markup(tree, assets)
    if not mark:
        icons = "".join(f'<li>{e(k)}: <code>{e(v["value"])}</code></li>' for k, v in sorted(lg.items()) if is_leaf(v) and k != "primary")
        return f'<section id="logo"><h2>Logo</h2><p class="lead">No logo was found in the page header. Add its address with <code>growth brand-kit set logo.primary https://…</code>.</p><ul>{icons}</ul></section>'
    h = int((lg.get("primary") or {}).get("height") or 40)
    cs = val(tree, "logo.clearSpace") or "0.5 x the logo height"
    pad = max(8, int(h * 0.5))
    prim = val(tree, "colors.primary") or "#2563EB"
    do = (f'<div class="logo-card do">{mark}<small>Do: use the supplied file, at least {val(tree, "logo.minHeight") or 24}px high.</small></div>'
          f'<div class="logo-card"><span class="clear" style="padding:{pad}px"><span>{mark}</span></span><small>Clear space: {e(cs)} on every side (dashed).</small></div>')
    dont = (f'<div class="logo-card dont"><span style="display:inline-block;transform:scaleX(1.3);transform-origin:left">{mark}</span><small>Do not stretch or squash it.</small></div>'
            f'<div class="logo-card dont"><span style="display:inline-block;filter:hue-rotate(140deg) saturate(2)">{mark}</span><small>Do not recolour it.</small></div>'
            f'<div class="logo-card dont" style="background:{C.mix(prim, "#FFFFFF", 0.15)}">{mark}<small>Do not put it on a busy or low-contrast background.</small></div>')
    icons = "".join(f'<li>{e(k)}: <code>{e(v["value"])}</code></li>' for k, v in sorted(lg.items()) if is_leaf(v) and k != "primary")
    stage = (lg.get("primary") or {}).get("stage") or "#FFFFFF"
    fg = _on(stage) if C.valid_hex(stage) else "#14171A"
    return (f'<section id="logo" style="--stage:{stage};--stage-fg:{fg}"><h2>Logo</h2><p class="lead">Shown on {"the colour it sits on in the site header" if stage != "#FFFFFF" else "white"}.</p><div class="logo-stage">{do}</div><h3>Do not</h3><div class="logo-stage">{dont}</div>'
            f"<h3>Files and icons</h3><ul>{icons}</ul></section>")


def _voice(tree) -> str:
    v = tree.get("voice") or {}
    prin = v.get("principles")
    avoid = v.get("avoid")
    cta = tree.get("cta") or {}
    out = ['<section id="voice"><h2>Voice and words</h2>']
    if is_leaf(prin):
        out.append("<h3>How we sound</h3><ul class=\"words\">" + "".join(f"<li>{e(x)}</li>" for x in prin["value"]) + "</ul>")
    if is_leaf(avoid):
        out.append("<h3>Words never to use</h3><p>" + "".join(f'<span class="tag">{e(x)}</span>' for x in avoid["value"]) + "</p>")
    if cta:
        out.append("<h3>Calls to action</h3>")
        if is_leaf(cta.get("main")):
            out.append(f'<p>Main: <span class="tag"><strong>{e(cta["main"]["value"])}</strong></span></p>')
        if is_leaf(cta.get("others")):
            out.append("<p>Also on the site: " + "".join(f'<span class="tag">{e(x)}</span>' for x in cta["others"]["value"]) + "</p>")
        if is_leaf(cta.get("booking")):
            out.append(f'<p>Booking link: <a href="{e(cta["booking"]["value"])}">{e(cta["booking"]["value"])}</a></p>')
    if len(out) == 1:
        out.append("<p class=\"lead\">Nothing recorded yet. Fill BRAND.md section 8 (voice) and section 7 (words never to use), then run <code>growth brand-kit learn</code> again.</p>")
    out.append("</section>")
    return "".join(out)


def _contact(tree) -> str:
    c = tree.get("contact") or {}
    if not c:
        return '<section id="contact"><h2>Contact facts</h2><p class="lead">Run <code>growth brand-scan</code> first; its findings appear here after the next <code>growth brand-kit learn</code>.</p></section>'
    rows = []
    for label, key in (("Legal name", "legal_name"), ("Address", "address"), ("Emails", "emails"), ("Phones", "phones")):
        n = c.get(key)
        if is_leaf(n):
            rows.append(f"<tr><th>{label}</th><td>{e(', '.join(n['value']) if isinstance(n['value'], list) else n['value'])}</td></tr>")
    soc = c.get("social")
    if is_leaf(soc):
        rows.append("<tr><th>Social</th><td>" + ", ".join(f'<a href="{e(s["url"])}">{e(s["network"])}</a>' for s in soc["value"]) + "</td></tr>")
    return f'<section id="contact"><h2>Contact facts</h2><table>{"".join(rows)}</table></section>'
