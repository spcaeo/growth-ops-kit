"""Measured design checks (rule 158a, with 30, 32b and 49): one headless-browser pass over the rendered page at 1440x900 and
390x844 (reduced motion, animations off), shared by every check below through ctx.cache. The numbers are limits, not taste:
a page with too much white space, columns that do not balance or call-to-action buttons that crowd each other fails.
Limits come from growth.json "layout" (defaults in LIMITS). A page that cannot be measured (no Playwright, no chromium, the
server is not reachable) is a BLOCKED-SKIP, never a pass."""
from __future__ import annotations

import fnmatch
from urllib.parse import urlsplit

from .core import ALL, Skip, check

VIEWPORTS = ((1440, 900), (390, 844))
DESKTOP = 1440
LIMITS = {
    "section_step": 80,           # the page's fold padding step in px (the gap between folds is 2 x step)
    "gap_pad": 24,                # slack added to the step limits
    "hero_extra": 66,             # the hero is at most its content + this many px
    "hero_max_mobile": 1100,      # the hero at 390 px wide is at most this tall (1.3 screens)
    "column_ratio": 1.30,         # taller / shorter of two side-by-side columns
    "nearly_empty": 0.25,         # a column under this share of the other's height is nearly empty
    "top_tolerance": 8,           # side-by-side columns start within this many px of each other
    "picture_ratio": 0.60,        # a picture is at least this share of the text block next to it
    "mechanics_max": 2,           # folds one mechanic may appear in
    "legal_paths": ["/terms*", "/privacy*", "/cookie*"],
    "mechanics": ["flip", "tabs", "accordion", "slider"],
    # inside these, rows and grids are a tool's or a menu's own layout, not the page's folds (2.4.2): a reading desk's
    # table of contents beside the text, a calculator's option grid, a form
    "exempt": "nav, form, fieldset, [data-tool], [role=tablist], [role=radiogroup], .toc, [data-layout-exempt]",
}

MEASURE_JS = r"""
(args) => {
  const sy = window.scrollY, sx = window.scrollX;
  const cache = new WeakMap();
  const cs = e => { let v = cache.get(e); if (!v) { v = getComputedStyle(e); cache.set(e, v); } return v; };
  const R = e => e.getBoundingClientRect();
  const abs = r => ({top: r.top + sy, bottom: r.bottom + sy, left: r.left + sx, width: r.width, height: r.height});
  const shown = e => { const s = cs(e); if (s.display === 'none' || s.visibility === 'hidden') return false;
    const r = R(e); return r.width > 2 && r.height > 2; };
  const flow = e => { const p = cs(e).position; return p !== 'absolute' && p !== 'fixed'; };
  const MEDIA = new Set(['IMG', 'PICTURE', 'CANVAS', 'VIDEO', 'IFRAME']);
  const isSvg = e => e instanceof SVGElement;
  const FORM = new Set(['INPUT', 'SELECT', 'TEXTAREA', 'HR']);
  const walk = (root, fn) => { for (const c of root.children) {
    const s = cs(c);
    if (s.display === 'none' || s.visibility === 'hidden') continue;
    if (c.getAttribute('aria-hidden') === 'true' || !flow(c)) continue;
    if (s.display === 'contents') { walk(c, fn); continue; }
    if (!shown(c)) continue;
    if (isSvg(c) || MEDIA.has(c.tagName)) { fn(c); continue; }
    // only children walk() would itself measure count as content: aria-hidden icons and positioned decoration do not
    // make an element a container, so its own text is still measured (friction 56)
    const kids = [...c.children].filter(k => k.getAttribute('aria-hidden') !== 'true' && flow(k) && cs(k).display !== 'none'
                                             && (shown(k) || cs(k).display === 'contents'));
    const ownText = [...c.childNodes].some(n => n.nodeType === 3 && n.textContent.trim().length > 0);
    if (kids.length) { walk(c, fn); if (ownText) fn(c); continue; }
    if (FORM.has(c.tagName) || (c.textContent || '').trim().length > 0 || cs(c).backgroundImage !== 'none') fn(c);
  } };
  const extent = root => { let t = null, b = null; walk(root, e => { const r = abs(R(e));
    t = t === null ? r.top : Math.min(t, r.top); b = b === null ? r.bottom : Math.max(b, r.bottom); });
    const r = abs(R(root)); return t === null ? {cTop: r.top, cBottom: r.bottom} : {cTop: t, cBottom: b}; };
  const main = document.querySelector('main') || document.body;
  let secs = [...main.querySelectorAll('section[data-fold]')];
  if (!secs.length) secs = [...main.querySelectorAll(':scope > section')];
  secs = secs.filter(shown);
  const name = (s, i) => s.dataset.fold || s.id || s.getAttribute('aria-label') || ('#' + (i + 1));
  const names = secs.map(name);
  const foldOf = e => { let k = -1; secs.forEach((s, i) => { if (s.contains(e)) k = i; }); return k; };
  const folds = secs.map((s, i) => { const r = abs(R(s)), x = extent(s), st = cs(s);
    return {name: names[i], top: r.top, bottom: r.bottom, cTop: x.cTop, cBottom: x.cBottom,
            padTop: parseFloat(st.paddingTop) || 0, padBottom: parseFloat(st.paddingBottom) || 0}; });
  const mediaIn = c => [...c.querySelectorAll('img,svg,picture,canvas,video')].filter(shown);
  const colInfo = c => { const r = abs(R(c)), x = extent(c), txt = ((c.innerText || '')).trim().length;
    const own = (MEDIA.has(c.tagName) || isSvg(c) || c.tagName === 'FIGURE');
    const m = mediaIn(c), isMedia = own || (txt < 20 && m.length > 0);
    let mArea = 0; if (isMedia) { const els = own && !m.length ? [c] : m; els.forEach(e => { const q = R(e); mArea = Math.max(mArea, q.width * q.height); });
      if (own && !m.length) mArea = r.width * r.height; }
    return {cls: (c.className && c.className.baseVal === undefined ? String(c.className) : c.tagName.toLowerCase()).slice(0, 30) || c.tagName.toLowerCase(),
            top: r.top, height: r.height, cHeight: x.cBottom - x.cTop, width: r.width, text: txt, isMedia, mArea,
            tArea: r.width * (x.cBottom - x.cTop)}; };
  const rows = [], grids = [];
  for (const e of main.querySelectorAll('*')) {
    if (isSvg(e) || !shown(e)) continue;
    const kids = [...e.children].filter(k => !isSvg(k) && shown(k) && flow(k));
    if (e.closest(args.exempt)) continue;
    if (kids.length === 2 && !kids.some(k => k.matches(args.exempt) || cs(k).position === 'sticky' || k.querySelector('.toc, nav'))) {
      const [a, b] = kids.map(k => R(k));
      if (a.width >= 200 && b.width >= 200 && Math.abs(a.top - b.top) <= 60 && (a.right <= b.left + 1 || b.right <= a.left + 1))
        rows.push({fold: names[foldOf(e)] || '', cols: kids.map(colInfo)});
    }
    const s = cs(e);
    // A wrapping flex row of plain text (a post's author / date / read-time line) is not a card grid: skip it when no
    // child draws a box (border, background or shadow). Real grids (display:grid) are always measured.
    const boxed = k => { const t = cs(k); return parseFloat(t.borderTopWidth) > 0 || parseFloat(t.borderLeftWidth) > 0 || t.boxShadow !== 'none'
                         || (t.backgroundColor !== 'rgba(0, 0, 0, 0)' && t.backgroundColor !== 'transparent') || t.backgroundImage !== 'none'; };
    const isFlexWrap = s.display.includes('flex') && s.flexWrap !== 'nowrap';
    if (isFlexWrap && !s.display.includes('grid') && !kids.some(boxed)) continue;
    // Cards are alike: most children share one tag and first class. A layout grid of unlike parts (a hero's heading,
    // picture and answer box) is not a card grid (2.6.2).
    const sig = k => k.tagName + '.' + ((k.classList && k.classList[0]) || '');
    const sigs = kids.map(sig), top = Math.max(...sigs.map(x => sigs.filter(y => y === x).length));
    const alike = top >= Math.max(3, Math.ceil(kids.length * 2 / 3));
    if (kids.length >= 3 && alike && (s.display.includes('grid') || isFlexWrap)) {
      const rs = kids.map(k => ({r: R(k)})).sort((p, q) => p.r.top - q.r.top || p.r.left - q.r.left), lines = [];
      rs.forEach(k => { const l = lines[lines.length - 1]; if (l && Math.abs(l[0].r.top - k.r.top) <= 10) l.push(k); else lines.push([k]); });
      if (lines.length >= 2) {
        const last = lines[lines.length - 1], per = Math.max(...lines.map(l => l.length));
        const others = rs.filter(k => !last.includes(k)).map(k => k.r.width).sort((p, q) => p - q);
        const med = others[Math.floor(others.length / 2)] || 0, pr = R(e);
        const lc = (Math.min(...last.map(k => k.r.left)) + Math.max(...last.map(k => k.r.right))) / 2;
        grids.push({fold: names[foldOf(e)] || '', n: kids.length, per, lastCount: last.length, rows: lines.length,
                    centred: Math.abs(lc - (pr.left + pr.right) / 2) <= 12, wide: last.length === 1 && med > 0 && last[0].r.width >= 1.5 * med});
      }
    }
  }
  let rgb = null; const token = args.token;
  try { const p = document.createElement('i'); p.style.cssText = 'position:absolute;background-color:var(' + token + ',transparent)';
    document.body.appendChild(p); const v = getComputedStyle(p).backgroundColor; p.remove(); if (v && v !== 'rgba(0, 0, 0, 0)') rgb = v; } catch (_) {}
  const ctas = [];
  for (const e of document.querySelectorAll('.book-cta, .btn')) {
    if (!shown(e) || !(e.matches('.book-cta') || (rgb && cs(e).backgroundColor === rgb))) continue;
    const r = abs(R(e)), k = foldOf(e); let fixed = false;
    for (let p = e; p && p.nodeType === 1; p = p.parentElement) if (cs(p).position === 'fixed') fixed = true;
    ctas.push({top: r.top, bottom: r.bottom, left: r.left, fold: k, foldName: k >= 0 ? names[k] : '',
               dialog: !!e.closest('dialog,[role=dialog],.call-dialog,[aria-modal=true]'), sticky: !!e.closest('.sticky-cta'),
               footer: !!e.closest('footer'), fixed, label: (e.innerText || '').trim().slice(0, 30)});
  }
  const mech = {};
  for (const m of args.mechanics) { const re = new RegExp('(^|[-_])' + m + '($|[-_])', 'i'), set = new Set();
    for (const e of main.querySelectorAll('[class]')) { if (isSvg(e)) continue; const k = foldOf(e);
      if (k >= 0 && [...e.classList].some(c => re.test(c))) set.add(names[k]); }
    mech[m] = [...set]; }
  return {vh: window.innerHeight, pageH: document.documentElement.scrollHeight, folds, rows, grids, ctas, mech,
          sticky: document.querySelectorAll('.sticky-cta').length, tokenFound: !!rgb};
}
"""


def limits(ctx):
    cfg = ctx.cfg.get("layout") or {}
    return {k: cfg.get(k, v) for k, v in LIMITS.items()}


def is_legal(ctx):
    p = ctx.path or urlsplit(ctx.url).path or "/"
    return any(fnmatch.fnmatch(x, g) for g in limits(ctx)["legal_paths"] for x in (p, p.rstrip("/") or "/"))


def measure(ctx):
    """{1440: data, 390: data}: the boxes of the rendered page. Measured once per URL; every check reads the cache."""
    key = ("layout", ctx.url)
    if key in ctx.cache:
        return ctx.cache[key]
    ctx.need_html()
    from .c_links import need_browser
    need_browser(ctx)
    if not ctx.url:
        raise Skip("no page URL to open in a browser", blocked=True)
    args = {"token": (ctx.cfg.get("cta") or {}).get("color_token", "--color-cta"), "mechanics": limits(ctx)["mechanics"],
            "exempt": limits(ctx)["exempt"]}
    from playwright.sync_api import sync_playwright
    out = {}
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            try:
                for w, h in VIEWPORTS:
                    c = b.new_context(viewport={"width": w, "height": h}, reduced_motion="reduce")
                    try:
                        pg = c.new_page()
                        pg.goto(ctx.url, wait_until="load", timeout=60000)
                        pg.add_style_tag(content="*,*::before,*::after{animation:none!important;transition:none!important;scroll-behavior:auto!important}")
                        pg.wait_for_timeout(300)
                        out[w] = pg.evaluate(MEASURE_JS, args)
                    finally:
                        c.close()
            finally:
                b.close()
    except Exception as e:  # noqa: BLE001
        raise Skip(f"could not measure the page in a headless browser ({type(e).__name__}: {str(e).splitlines()[0][:100] if str(e) else ''})", blocked=True)
    ctx.cache[key] = out
    return out


def _n(x):
    return int(round(x))


def _folds(d, w, probs):
    if not d["folds"]:
        probs.append(f"no folds found at {w}: put each fold in main > section[data-fold]")
        return False
    return True


@check("layout.fold-gap", "158a", what="the white space between folds, and under a fold's last content, stays inside the limit (rule 158)", needs="live")
def fold_gap(ctx):
    L, probs = limits(ctx), []
    gmax, emax = 2 * L["section_step"] + L["gap_pad"], L["section_step"] + L["gap_pad"]
    for w, d in measure(ctx).items():
        if not _folds(d, w, probs):
            continue
        f = d["folds"]
        for a, b in zip(f, f[1:]):
            gap = b["cTop"] - a["cBottom"]
            if gap > gmax:
                probs.append(f"fold '{a['name']}'->'{b['name']}': gap {_n(gap)} px (max {gmax}) at {w}")
        for x in f:
            empty = x["bottom"] - x["cBottom"]
            if empty > emax:
                probs.append(f"fold '{x['name']}': empty bottom {_n(empty)} px (max {emax}) at {w}")
    ctx.verdict(probs, f"gaps between folds at most {gmax} px and empty bottoms at most {emax} px, at 1440 and 390",
                f"cut the fold padding to the step of {L['section_step']} px (clamp(48px, 2.5rem + 2.5vw, {L['section_step']}px)) and remove spacers (rule 158a)")


@check("layout.hero-height", "158a", what="the hero is no taller than its content plus 66 px, and under 1100 px on a phone (rule 158)", needs="live")
def hero_height(ctx):
    if is_legal(ctx):
        raise Skip("legal page: no hero limit (growth.json layout.legal_paths)")
    from .c_cta import conversion_page
    if conversion_page(ctx):
        raise Skip("the conversion page: its form is the first fold (rule 38), so it is as tall as the form")
    L, probs = limits(ctx), []
    for w, d in measure(ctx).items():
        if not _folds(d, w, probs):
            continue
        h = d["folds"][0]
        height, content = h["bottom"] - h["top"], h["cBottom"] - h["cTop"]
        if height > content + L["hero_extra"]:
            probs.append(f"hero '{h['name']}': {_n(height)} px tall, content {_n(content)} px (max {_n(content + L['hero_extra'])}) at {w}")
        if w < 800 and height > L["hero_max_mobile"]:
            probs.append(f"hero '{h['name']}': {_n(height)} px tall on a phone (max {L['hero_max_mobile']}) at {w}")
    ctx.verdict(probs, f"hero within its content + {L['hero_extra']} px and {L['hero_max_mobile']} px on a phone",
                "tighten the hero: drop the min-height, trim the padding and stack the picture under the words on a phone (rule 158a)")


@check("layout.column-ratio", "158a", what="two columns side by side are balanced: height ratio, nearly empty, top edges (rule 158)", needs="live")
def column_ratio(ctx):
    if is_legal(ctx):
        raise Skip("legal page: one reading column (growth.json layout.legal_paths)")
    L, probs = limits(ctx), []
    rows = measure(ctx)[DESKTOP]["rows"]
    for r in rows:
        a, b = r["cols"]
        ha, hb = max(a["cHeight"], 1), max(b["cHeight"], 1)
        tall, short = max(ha, hb), min(ha, hb)
        where = f"fold '{r['fold'] or '?'}' columns '{a['cls']}'/'{b['cls']}'"
        if short / tall < L["nearly_empty"]:
            probs.append(f"{where}: nearly empty column, {_n(short)} px against {_n(tall)} px")
        elif tall / short > L["column_ratio"]:
            probs.append(f"{where}: height ratio {tall / short:.2f} ({_n(tall)} vs {_n(short)} px, max {L['column_ratio']:.2f})")
        if abs(a["top"] - b["top"]) > L["top_tolerance"]:
            probs.append(f"{where}: tops {_n(abs(a['top'] - b['top']))} px apart (max {L['top_tolerance']})")
    ctx.verdict(probs, f"{len(rows)} two-column row(s) at 1440, all balanced",
                "give the shorter column more content or centre both on one line; align the tops (rule 158a)")


@check("layout.picture-text", "158a", types=("money", "core"), what="a picture next to a text block is at least 60% of its area (rule 158)", needs="live")
def picture_text(ctx):
    L, probs, pairs = limits(ctx), [], 0
    for r in measure(ctx)[DESKTOP]["rows"]:
        a, b = r["cols"]
        for pic, txt in ((a, b), (b, a)):
            if pic["isMedia"] and not txt["isMedia"] and txt["text"] >= 40:
                pairs += 1
                if txt["tArea"] > 0 and pic["mArea"] < L["picture_ratio"] * txt["tArea"]:
                    probs.append(f"fold '{r['fold'] or '?'}': picture {_n(pic['mArea'])} px2 is {pic['mArea'] / txt['tArea']:.0%} of the text block "
                                 f"{_n(txt['tArea'])} px2 (min {L['picture_ratio']:.0%})")
    ctx.verdict(probs, f"{pairs} picture and text pair(s) at 1440, every picture at least {L['picture_ratio']:.0%} of its text",
                "make the picture larger, or move the small icon into the text column (rule 158a)")


@check("layout.card-orphan", "158a", what="the last row of a card grid is full, centred or one wide card (rule 158)", needs="live")
def card_orphan(ctx):
    probs, grids = [], 0
    for w, d in measure(ctx).items():
        for g in d["grids"]:
            grids += 1
            if g["lastCount"] < g["per"] and not g["centred"] and not g["wide"]:
                probs.append(f"fold '{g['fold'] or '?'}': {g['n']} cards, {g['per']} per row, last row has {g['lastCount']} and sits left at {w}")
    ctx.verdict(probs, f"{grids} card grid(s) measured, no orphan last row", "pick a column count that divides the cards, centre the last row, or make the last card wide (rule 158a)")


@check("cta.one-per-view", "158a", what="at most one primary button on any screen (rule 32b)", needs="live")
def one_per_view(ctx):
    probs, seen = [], 0
    for w, d in measure(ctx).items():
        vh = d["vh"]
        asks = [c for c in d["ctas"] if not c["dialog"] and not c["sticky"]]
        seen += len(asks)
        for k in range(max(1, -(-d["pageH"] // vh))):
            lo, hi = k * vh, (k + 1) * vh
            here = [c for c in asks if lo <= (c["top"] + c["bottom"]) / 2 < hi]
            if len(here) > 1:
                probs.append(f"screen {k + 1} at {w}: {len(here)} primary buttons ({', '.join(repr(c['foldName'] or 'header') for c in here)}; max 1)")
    ctx.verdict(probs, f"{seen} primary button(s) at both widths, at most one per screen (the sticky bar and dialogs are not counted)",
                "keep the header button out of the first screen's hero ask, or make one of them a plain link (rule 32b)")


@check("cta.spacing", "158a", what="two primary buttons never sit in neighbouring folds (rule 32b)", needs="live")
def spacing(ctx):
    probs = []
    for w, d in measure(ctx).items():
        folds = {c["fold"]: c["foldName"] for c in d["ctas"] if c["fold"] >= 0 and not c["sticky"] and not c["footer"] and not c["dialog"]}
        for k in sorted(folds):
            if k + 1 in folds:
                probs.append(f"folds '{folds[k]}' and '{folds[k + 1]}' both have a primary button at {w}")
    ctx.verdict(probs, "no two primary buttons in neighbouring folds", "leave at least one fold with no primary button between two asks (rule 32b)")


@check("cta.legal-quiet", "158a", what="a legal page has no primary button and no sticky bar (rule 49)", needs="live")
def legal_quiet(ctx):
    if not is_legal(ctx):
        raise Skip("not a legal page (growth.json layout.legal_paths)")
    probs = []
    for w, d in measure(ctx).items():
        probs += [f"primary button '{c['label']}' in fold '{c['foldName'] or 'header'}' at {w}" for c in d["ctas"] if not c["dialog"]]
        if d["sticky"]:
            probs.append(f"{d['sticky']} sticky call bar(s) at {w}")
    ctx.verdict(probs, "no primary button and no sticky bar on this legal page", "drop the button and the bar; one quiet text link to contact is enough (rule 49)")


@check("engage.one-mechanic", "158a", what="one interaction mechanic (flip, tabs, accordion, slider) is used in at most two folds (rule 30)", needs="live")
def one_mechanic(ctx):
    L, probs = limits(ctx), []
    for m, names in measure(ctx)[DESKTOP]["mech"].items():
        if len(names) > L["mechanics_max"]:
            probs.append(f"mechanic '{m}' in {len(names)} folds ({', '.join(repr(n) for n in names)}; max {L['mechanics_max']})")
    ctx.verdict(probs, f"no mechanic of {', '.join(L['mechanics'])} in more than {L['mechanics_max']} folds",
                "give each fold its own shape: swap the repeats for a different mechanic or a plain layout (rule 30)")
