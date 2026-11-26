"""Snapshots (see snapshot.py) -> the generated brand: colours with their roles, fonts and the type scale, spacing, radius,
shadows, the button and link looks, the logo, and the words (from brand-scan.json and BRAND.md). Pure functions on plain data."""
from __future__ import annotations

import re
from collections import Counter

from . import colors as C
from .store import leaf

NEUTRAL = 18.0          # Lab chroma below this is a grey (text, borders, surfaces); above 25 is a real colour
STATE_NAMES = {"success": r"success|positive|valid|\bok\b|green", "warning": r"warn|caution|amber|yellow|orange", "error": r"error|danger|negative|critical|invalid|\bred\b"}
ACCENT_NAME = re.compile(r"accent|secondary|highlight|brand-2|alt", re.I)
MONO = re.compile(r"mono|courier|consolas|menlo|monaco", re.I)


def _rgb(c):
    return c[:3] if c else None


def _over(c, under):
    """An [r, g, b, a] colour painted over an opaque colour -> (r, g, b)."""
    a = c[3] if len(c) > 3 else 1
    return C.composite(c, a, under) if a < 1 else tuple(c[:3])


def _page_bg(snaps) -> tuple:
    votes = Counter(C.to_hex(s["pageBg"]) for s in snaps if s.get("pageBg"))
    return C.parse(votes.most_common(1)[0][0]) if votes else (255, 255, 255)


def _weighted(snaps, kind, bg, key="c"):
    """[(colour, share)] summed over the pages; each page counts the same however long it is."""
    out = []
    for s in snaps:
        rows = s.get(kind) or []
        total = sum(r.get("w", 0) for r in rows) or 1
        pg = C.parse(s.get("pageBg") or bg) or bg
        out += [(_over(r[key], pg), r["w"] / total / len(snaps)) for r in rows if r.get("w", 0) > 0 and r.get(key)]
    return out


def _name(font_family: str) -> str:
    first = (font_family or "").split(",")[0].strip().strip("'\"")
    return first or "system-ui"


def _px(n) -> str:
    n = float(n)
    return f"{int(n)}px" if n == int(n) else f"{round(n, 2)}px"


def _pad(p) -> str:
    t, r, b, l = (p + [0, 0, 0, 0])[:4]
    return f"{t}px {r}px" if t == b and r == l else f"{t}px {r}px {b}px {l}px"


# ---- buttons -------------------------------------------------------------------------------------------------------------
def button_groups(snaps, bg, cta_words):
    """Buttons seen on the pages, merged by how they are drawn: [{bg, color, n, pages, main, texts, rest, hover, focus, score}]."""
    groups: dict[tuple, dict] = {}
    for s in snaps:
        for b in s.get("buttons") or []:
            rest = b["rest"]
            pg = C.parse(s.get("pageBg") or bg) or bg
            fill = C.to_hex(_over(rest["bg"], pg)) if rest.get("bg") else ""
            text_c = C.to_hex(rest["color"]) if rest.get("color") else ""
            edge = C.to_hex(rest["border"][0]) if rest.get("border") else ""
            k = (fill, text_c, edge, rest.get("radius"))
            g = groups.setdefault(k, {"bg": fill, "color": text_c, "edge": edge, "n": 0, "pages": set(), "main": False, "texts": [], "rest": rest, "hover": None, "focus": None})
            g["n"] += b["n"]
            g["pages"].add(s["url"])
            g["main"] = g["main"] or b.get("main", False)
            g["texts"] += [t for t in b.get("texts") or [b["text"]] if t not in g["texts"]][:4]
            g["hover"] = g["hover"] or b.get("hover")
            g["focus"] = g["focus"] or b.get("focus")
    words = {w.lower() for w in cta_words if w}
    for g in groups.values():
        score = g["n"] * (2.0 if g["main"] else 1.0)
        if any(t.lower() in words for t in g["texts"]):
            score *= 3
        if g["bg"] and C.chroma(g["bg"]) >= 20:
            score *= 1.5
        g["score"] = score
    return sorted(groups.values(), key=lambda g: (-g["score"], g["bg"], g["color"]))


def _state(st, under) -> dict:
    """A recorded hover or focus state -> a dict of leaves (only what the state says)."""
    out = {}
    if not st:
        return out
    if st.get("bg") and st["bg"][3] > 0.05:
        out["background"] = leaf(C.to_hex(_over(st["bg"], under)), "site", "read in the browser")
    if st.get("color"):
        out["color"] = leaf(C.to_hex(st["color"]), "site", "read in the browser")
    if st.get("border"):
        out["border_color"] = leaf(C.to_hex(_over(st["border"][0], under)), "site", "read in the browser")
        out["border_width"] = leaf(st["border"][1], "site", "read in the browser")
    if st.get("shadow"):
        out["shadow"] = leaf(st["shadow"], "site", "read in the browser")
    if st.get("deco"):
        out["text_decoration"] = leaf(st["deco"], "site", "read in the browser")
    if st.get("transform"):
        out["transform"] = leaf(st["transform"], "site", "read in the browser")
    if st.get("outline"):
        o = st["outline"]
        out["outline_color"] = leaf(C.to_hex(o[0]), "site", "read in the browser")
        out["outline_width"] = leaf(o[1], "site", "read in the browser")
        out["outline_offset"] = leaf(o[2], "site", "read in the browser")
    return out


def _button(g, bg, role_hexes) -> dict:
    rest = g["rest"]
    pg = bg
    d = {}
    if g["bg"]:
        d["background"] = leaf(g["bg"], "site", "painted behind the button text")
        if g["bg"] == role_hexes.get("primary"):
            d["background"]["ref"] = "colors.primary"
    d["color"] = leaf(g["color"], "site", "button text colour")
    if g["color"] == role_hexes.get("onPrimary"):
        d["color"]["ref"] = "colors.onPrimary"
    if rest.get("border"):
        d["border_color"] = leaf(g["edge"], "site", "button border")
        d["border_width"] = leaf(rest["border"][1], "site", "button border")
    d["radius"] = leaf(rest.get("radius", 0), "site", "corner radius in px")
    d["padding"] = leaf(_pad(rest.get("padding", [12, 24, 12, 24])), "site", "inner space")
    if rest.get("height"):
        d["height"] = leaf(rest["height"], "site", "button height in px")
    d["font_size"] = leaf(_px(rest.get("size", 16)), "site", "button text size")
    d["font_weight"] = leaf(rest.get("weight", 600), "site", "button text weight")
    if rest.get("shadow"):
        d["shadow"] = leaf(rest["shadow"], "site", "shadow at rest")
    if rest.get("transform") and rest["transform"] != "none":
        d["text_transform"] = leaf(rest["transform"], "site", "capitals")
    out = {"rest": d, "text": leaf(g["texts"][0] if g["texts"] else "", "site", f"{g['n']} on {len(g['pages'])} pages")}
    hv, fc = _state(g["hover"], pg), _state(g["focus"], pg)
    if hv:
        out["hover"] = hv
    if fc:
        out["focus"] = fc
    return out


# ---- the whole generated brand ---------------------------------------------------------------------------------------------
def build_generated(snaps: list[dict], scan: dict | None = None, brand_md: str = "", cfg: dict | None = None, base: str = "", read_on: str = "") -> dict:
    """The generated brand from snapshots of 1 or more pages. `scan`: docs/brand-scan.json; `brand_md`: the text of BRAND.md."""
    ok = [s for s in snaps if "error" not in s and s.get("bg") is not None]
    cfg = cfg or {}
    out: dict = {"meta": {"base": base, "read_on": read_on, "pages": [s["url"] for s in ok], "errors": [f"{s['url']}: {s['error']}" for s in snaps if "error" in s]}}
    cta_words = []
    if scan:
        mc = ((scan.get("findings") or {}).get("main_cta") or {}).get("text")
        cta_words = [mc] if mc else []
        cta_words += [c["text"] for c in (scan.get("findings") or {}).get("ctas", [])[:6]]
    out["name"], out["tagline"] = _names(ok, scan, cfg)
    if ok:
        _colors(out, ok, cta_words)
        _typography(out, ok)
        _spacing_radius_shadow(out, ok)
        _logo(out, ok)
    out.update(_words(scan, brand_md, cfg))
    return {k: v for k, v in out.items() if v not in (None, {}, "")}


def _names(ok, scan, cfg):
    f = (scan or {}).get("findings") or {}
    home = (f.get("company") or {}).get("home") or {}
    meta = (ok[0].get("meta") if ok else {}) or {}
    name = home.get("site_name") or meta.get("og:site_name") or cfg.get("name") or ""
    where = "docs/brand-scan.json" if home.get("site_name") else ("the page's og:site_name" if meta.get("og:site_name") else "growth.json name")
    desc = home.get("description") or meta.get("description") or ""
    return (leaf(name, "site", where) if name else None), (leaf(desc, "site", "the home page's description") if desc else None)


def _colors(out, ok, cta_words):
    bg = _page_bg(ok)
    pages = len(ok)
    bg_hex = C.to_hex(bg)
    colors: dict = {}
    bgc = C.cluster(_weighted(ok, "bg", bg))
    textc = C.cluster(_weighted(ok, "text", bg))
    linkc = C.cluster(_weighted(ok, "link", bg))
    edgec = C.cluster(_weighted(ok, "border", bg))
    varnames: dict[str, str] = {}
    for s in ok:
        for name, c in (s.get("varColors") or {}).items():
            varnames.setdefault(name, C.to_hex(_over(c, bg)))
    by_hex: dict[str, str] = {}
    for name, h in varnames.items():
        by_hex.setdefault(h, name)

    def role(name, hexv, why, **extra):
        node = leaf(hexv, "site", why, **extra)
        if hexv in by_hex:
            node["var"] = by_hex[hexv]
        colors[name] = node

    role("background", bg_hex, f"the page's own background on {pages} page{'s' if pages != 1 else ''}")
    text = next((c for c in textc if C.contrast(c["hex"], bg) >= 3), textc[0] if textc else None)
    if text:
        role("text", text["hex"], f"the most text on the pages ({round(text['weight'] * 100)}% of it)")
    tx = text["hex"] if text else None
    surf = next((c for c in bgc if C.delta_e(c["hex"], bg_hex) > 2.5 and C.chroma(c["hex"]) < 25 and (not tx or C.contrast(tx, c["hex"]) >= 3)), None)
    if surf:
        role("surface", surf["hex"], "the biggest panel colour that is not the page colour")
    if tx:
        muted = next((c for c in textc if C.delta_e(c["hex"], tx) > 8 and C.chroma(c["hex"]) < 30 and 3.0 <= C.contrast(c["hex"], bg) < C.contrast(tx, bg) - 0.3), None)
        if muted:
            role("muted", muted["hex"], "the most common softer text colour")
    groups = button_groups(ok, bg, cta_words)
    fills = [g for g in groups if g["bg"]]
    prim_g = fills[0] if fills else None
    prim_hex = None
    if prim_g:
        prim_hex = prim_g["bg"]
        what = f"main call to action button \"{prim_g['texts'][0] if prim_g['texts'] else ''}\" ({prim_g['n']} on {len(prim_g['pages'])} pages)"
        role("primary", prim_hex, what)
        role("onPrimary", prim_g["color"], "the text colour on that button")
    else:
        sat = next((c for c in bgc + linkc if C.chroma(c["hex"]) >= 25), None)
        if sat:
            prim_hex = sat["hex"]
            role("primary", prim_hex, "no button was found: the most used strong colour")
    if linkc:
        role("link", linkc[0]["hex"], "the colour of links inside text")
    brd = next((c for c in edgec if C.chroma(c["hex"]) < 30 and (not prim_hex or C.delta_e(c["hex"], prim_hex) > 10)), None)
    if brd:
        role("border", brd["hex"], "the most common border colour")
    pool = [(c["hex"], "a panel colour", c["weight"]) for c in bgc] + [(c["hex"], "a text colour", c["weight"]) for c in textc] + \
           [(c["hex"], "a border colour", c["weight"]) for c in edgec] + [(h, f"CSS variable {n}", 0.001) for n, h in varnames.items() if ACCENT_NAME.search(n)]
    pool = [p for p in pool if C.chroma(p[0]) >= 25 and (not prim_hex or C.delta_e(p[0], prim_hex) > 20)]
    named = [p for p in pool if p[1].startswith("CSS variable")]
    acc = (named or sorted(pool, key=lambda p: -p[2]) or [None])[0]
    if acc:
        role("accent", acc[0], f"the strongest second colour ({acc[1]})")
    for state, rx in STATE_NAMES.items():
        for name, h in sorted(varnames.items()):
            if re.search(rx, name, re.I) and C.chroma(h) >= 25:
                role(state, h, f"CSS variable {name}")
                break
    used = {v["value"] for v in colors.values()}
    rest = [c for c in C.cluster(_weighted(ok, "bg", bg) + _weighted(ok, "text", bg) + _weighted(ok, "border", bg) + _weighted(ok, "link", bg)) if c["hex"] not in used][:8]
    if rest:
        colors["palette"] = leaf([{"hex": c["hex"], "share": round(c["weight"] * 100, 1)} for c in rest if c["weight"] >= 0.002] or [], "site", "other colours on the pages, by share of what is painted")
        if not colors["palette"]["value"]:
            del colors["palette"]
    out["colors"] = colors
    hexes = {k: v["value"] for k, v in colors.items() if isinstance(v, dict) and isinstance(v.get("value"), str)}
    comps: dict = {}
    if prim_g:
        comps["primary"] = _button(prim_g, bg, hexes)
        sec = next((g for g in groups if g is not prim_g and (not g["bg"] or not prim_g["bg"] or C.delta_e(g["bg"], prim_g["bg"]) > 12)), None)
        if sec:
            comps["secondary"] = _button(sec, bg, hexes)
    if comps:
        out["components"] = {"button": comps}
    links = [ln for s in ok for ln in s.get("links") or []]
    if links:
        top = max(links, key=lambda x: x["n"])
        lk = {"rest": {"color": leaf(C.to_hex(_over(top["color"], bg)), "site", "links inside text"),
                       "text_decoration": leaf(top.get("deco") or "none", "site", "links inside text")}}
        if "link" in hexes and lk["rest"]["color"]["value"] == hexes["link"]:
            lk["rest"]["color"]["ref"] = "colors.link"
        if top.get("hover"):
            lk["hover"] = _state(top["hover"], bg)
        out.setdefault("components", {})["link"] = lk
    out["_prim"] = prim_g["rest"].get("radius") if prim_g else None     # used by radius below, removed there


def _typography(out, ok):
    fonts = Counter()
    weights: dict[str, set] = {}
    stacks: dict[str, str] = {}
    for s in ok:
        for f in s.get("fonts") or []:
            n = _name(f["family"])
            fonts[n] += f["w"]
            weights.setdefault(n, set()).add(int(f["weight"]))
            stacks.setdefault(n, f["family"])
    fam: dict = {}

    def family(role, name, why):
        fam[role] = leaf(name, "site", why, stack=stacks.get(name, ""), weights=sorted(weights.get(name, [])))
    if fonts:
        body = fonts.most_common(1)[0][0]
        family("body", body, f"{round(fonts[body] / sum(fonts.values()) * 100)}% of the text is set in it")
        h1s = Counter(_name(s["type"]["h1"]["family"]) for s in ok if (s.get("type") or {}).get("h1"))
        head = h1s.most_common(1)[0][0] if h1s else body
        if head not in stacks:
            stacks[head] = next((s["type"]["h1"]["family"] for s in ok if (s.get("type") or {}).get("h1")), "")
            weights.setdefault(head, set()).add(next((s["type"]["h1"]["weight"] for s in ok if (s.get("type") or {}).get("h1")), 700))
        family("heading", head, "the font of the main heading (h1)" if h1s else "headings use the body font")
        mono = next((n for n, _ in fonts.most_common() if MONO.search(n)), None)
        if mono:
            family("mono", mono, "the code font")
    scale: dict = {}
    for lvl in ("h1", "h2", "h3", "h4", "h5", "h6", "body", "small"):
        seen = [s["type"][lvl] for s in ok if (s.get("type") or {}).get(lvl)]
        if not seen:
            continue
        mode = Counter((t["size"], t["lh"], t["weight"], t["ls"]) for t in seen).most_common(1)[0][0]
        size, lh, weight, ls = mode
        node = leaf(_px(size), "site", f"read from the {lvl if lvl in ('body', 'small') else lvl} on {len(seen)} page{'s' if len(seen) != 1 else ''}",
                    line_height=round(lh / size, 2) if lh and size else 1.2, weight=weight)
        if ls:
            node["letter_spacing"] = _px(ls)
        scale[lvl] = node
    out["typography"] = {k: v for k, v in {"families": fam, "scale": scale}.items() if v}


def _shadow_blur(v: str) -> float:
    nums = re.findall(r"(-?\d+(?:\.\d+)?)px", re.sub(r"rgba?\([^)]*\)", "", v))
    return float(nums[2]) if len(nums) >= 3 else (float(nums[1]) if len(nums) > 1 else 0.0)


def _spacing_radius_shadow(out, ok):
    sp = Counter()
    rad, big = Counter(), Counter()
    sh = Counter()
    for s in ok:
        for r in s.get("space") or []:
            sp[int(r["px"])] += r["n"]
        for r in s.get("radius") or []:
            rad[int(r["px"])] += r["n"]
            big[int(r["px"])] += r.get("big", 0)
        for r in s.get("shadow") or []:
            sh[r["v"]] += r["n"]
    total = sum(sp.values())
    if total >= 40:
        fit = lambda u: sum(n for v, n in sp.items() if v % u == 0) / total  # noqa: E731
        unit = 8 if fit(8) >= 0.7 else 4 if fit(4) >= 0.7 else 0
        spacing: dict = {}
        if unit:
            spacing["unit"] = leaf(unit, "site", f"{round(fit(unit) * 100)}% of the paddings and margins are multiples of {unit}px")
        steps = sorted(v for v, n in sp.most_common(10) if n / total >= 0.02 and 4 <= v <= 160)
        if len(steps) >= 4:
            spacing["steps"] = leaf(steps, "site", "the paddings, margins and gaps used most" + ("" if unit else " (the site does not follow one grid)"))
        if spacing:
            out["spacing"] = spacing
    prim = out.pop("_prim", None)
    r: dict = {}
    if prim is not None and prim >= 0:
        r["control"] = leaf(int(prim), "site", "the primary button's corner radius")
    cards = [(n, px) for px, n in big.items() if n and px < 100]
    if cards:
        r["card"] = leaf(max(cards)[1], "site", "the corner radius most often used on large panels")
    if any(px >= 100 for px in rad):
        r["pill"] = leaf(999, "site", "fully round corners are used")
    vals = sorted({px for px, n in rad.most_common(8) if px < 100})
    if vals:
        r["values"] = leaf(vals, "site", "every corner radius used by more than a few elements")
    if r:
        out["radius"] = r
    top = sorted((v for v, _ in sh.most_common(3)), key=_shadow_blur)
    if top:
        out["shadows"] = {name: leaf(v, "site", f"used {sh[v]} times") for name, v in zip(("sm", "md", "lg"), top)}


def _logo(out, ok):
    cand = next((s["logo"] for s in ok if s.get("logo")), None)
    logo: dict = {}
    if cand:
        src = cand.get("src") or ""
        node = leaf(src or "inline svg", "site", f"the {cand['kind']} in the page header", kind=cand["kind"], width=cand["width"], height=cand["height"], alt=cand.get("alt", ""),
                    stage=C.to_hex(cand["bg"]) if cand.get("bg") else "")
        if cand.get("svg"):
            node["svg"] = cand["svg"]
        logo["primary"] = node
    icons = [i for s in ok for i in s.get("icons") or []]
    for key, pick in (("favicon", lambda i: i["rel"] in ("icon", "shortcut icon", "alternate icon") or "icon" in i["rel"].split()),
                      ("appleTouchIcon", lambda i: i["rel"] == "apple-touch-icon"), ("manifest", lambda i: i["rel"] == "manifest")):
        hit = [i for i in icons if pick(i)]
        if key == "favicon":
            hit.sort(key=lambda i: (not i["href"].endswith(".svg"), i["href"]))
        if hit:
            logo[key] = leaf(hit[0]["href"], "site", f"<link rel=\"{hit[0]['rel']}\">", sizes=hit[0].get("sizes", ""))
    meta = (ok[0].get("meta") or {}) if ok else {}
    if meta.get("og:image"):
        logo["shareImage"] = leaf(meta["og:image"], "site", "og:image")
    if meta.get("theme-color"):
        logo["themeColor"] = leaf(meta["theme-color"], "site", "the theme-color meta tag")
    if logo:
        out["logo"] = logo


# ---- words ---------------------------------------------------------------------------------------------------------------
def parse_brand_md(text: str) -> dict:
    """{"voice": [lines of section 8], "never": [words never to use, from section 7]} from BRAND.md; placeholders are dropped."""
    voice, never = [], []
    sec = ""
    for line in (text or "").splitlines():
        m = re.match(r"^##\s+(\d+a?)\.", line)
        if m:
            sec = m.group(1)
            continue
        clean = re.sub(r"<fill in[^>]*>", "", line).strip()
        if sec == "8" and clean.startswith("- ") and len(clean) > 4:
            voice.append(clean[2:].strip())
        if sec == "7" and re.search(r"(?i)words never to use", clean):
            tail = clean.split(":", 1)[-1] if ":" in clean else ""
            never += [w.strip(" .\"'") for w in re.split(r"[,;]", tail) if w.strip(" .\"'")]
    return {"voice": [v for v in voice if v.strip(" .")], "never": never}


def _plain_regex(rx: str) -> str:
    s = re.sub(r"\\w\*|\\b|\\s\*?", "", rx)
    s = re.sub(r"\[-\s\]", "-", s).replace("?", "").replace("\\", "")
    return re.sub(r"\(([^)|]+)\|([^)]+)\)", r"\1/\2", s).strip()


def _words(scan, brand_md, cfg) -> dict:
    out: dict = {}
    md = parse_brand_md(brand_md)
    voice: dict = {}
    if md["voice"]:
        voice["principles"] = leaf(md["voice"], "site", "BRAND.md section 8")
    never = list(md["never"])
    words = cfg.get("words") or {}
    for key in ("hype", "banned_cta", "banned_offer"):
        never += [_plain_regex(x) for x in words.get(key) or [] if isinstance(x, str)]
    never = sorted({n for n in never if n and len(n) < 60}, key=str.lower)
    if never:
        voice["avoid"] = leaf(never, "site", "BRAND.md section 7 and growth.json words")
    if voice:
        out["voice"] = voice
    f = (scan or {}).get("findings") or {}
    if f:
        cta: dict = {}
        mc = f.get("main_cta")
        if mc:
            cta["main"] = leaf(mc["text"], "site", f"docs/brand-scan.json: on {len(mc.get('pages', []))} pages")
        others = [c["text"] for c in f.get("ctas", []) if not mc or c["text"] != mc["text"]][:6]
        if others:
            cta["others"] = leaf(others, "site", "docs/brand-scan.json")
        if f.get("booking_links"):
            cta["booking"] = leaf(f["booking_links"][0]["url"], "site", "docs/brand-scan.json", provider=f["booking_links"][0].get("provider", ""))
        if cta:
            out["cta"] = cta
        contact: dict = {}
        co = f.get("company") or {}
        if co.get("legal_names"):
            contact["legal_name"] = leaf(co["legal_names"][0]["name"], "site", "docs/brand-scan.json")
        if co.get("addresses"):
            contact["address"] = leaf(co["addresses"][0]["address"], "site", "docs/brand-scan.json")
        em = [e["email"] for e in f.get("emails", []) if e.get("group") == "company"]
        if em:
            contact["emails"] = leaf(em, "site", "docs/brand-scan.json")
        if f.get("phones"):
            contact["phones"] = leaf([p["phone"] for p in f["phones"]], "site", "docs/brand-scan.json")
        if f.get("social"):
            contact["social"] = leaf([{"network": s["network"], "url": s["url"]} for s in f["social"]], "site", "docs/brand-scan.json")
        if contact:
            out["contact"] = contact
    return out
