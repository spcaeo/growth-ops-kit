"""Read a page's look in one headless browser: the computed styles of every visible element, summed into a "snapshot" (plain
data: colours by painted area, text colours and fonts by characters, the type scale, spacing, radius, shadows, buttons and
links at rest, hover and focus, the logo and icons, the CSS variables). Everything else in the brand kit works on snapshots,
so the tests feed it recorded ones.

Nothing leaves the preview: with live_site_rule no-crawl the browser is stopped from asking the live host (a page that names
its own live address for a stylesheet or an image would otherwise visit it), and analytics scripts are never loaded."""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import fetch_rule  # noqa: E402

WIDTH, HEIGHT = 1366, 900
ANALYTICS = re.compile(r"(?i)google-analytics|googletagmanager|doubleclick|facebook\.net|connect\.facebook|hotjar|clarity\.ms|segment\.(?:io|com)|"
                       r"mixpanel|hubspot|intercom|drift\.com|linkedin\.com/px|snap\.licdn|plausible\.io|posthog|sentry\.io|fullstory|crisp\.chat|tawk\.to|calendly\.com")

# Everything below runs inside the page. rgba(): any CSS colour as [r, g, b, a]; the computed value is read as text first
# (rgb()/rgba() is what Chromium reports for ordinary colours) and a 1x1 canvas converts the modern syntaxes (lab, oklch, color()).
JS_COMMON = r"""
const _cv = document.createElement('canvas'); _cv.width = _cv.height = 1;
const _cx = _cv.getContext('2d', { willReadFrequently: true });
const _cache = new Map();
const rgba = (v) => {
  if (!v || v === 'transparent') return v === 'transparent' ? [0, 0, 0, 0] : null;
  if (_cache.has(v)) return _cache.get(v);
  let out = null;
  const m = v.match(/^rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)(?:\s*[,/]\s*([\d.]+%?))?\s*\)$/);
  if (m) {
    let a = m[4] === undefined ? 1 : (m[4].endsWith('%') ? parseFloat(m[4]) / 100 : parseFloat(m[4]));
    out = [Math.round(m[1]), Math.round(m[2]), Math.round(m[3]), Math.round(a * 100) / 100];
  } else {
    _cx.fillStyle = '#000'; _cx.fillStyle = v; const f1 = _cx.fillStyle;
    _cx.fillStyle = '#fff'; _cx.fillStyle = v; const f2 = _cx.fillStyle;
    if (f1 === f2) {
      _cx.clearRect(0, 0, 1, 1); _cx.fillRect(0, 0, 1, 1);
      const d = _cx.getImageData(0, 0, 1, 1).data;
      out = [d[0], d[1], d[2], Math.round(d[3] / 255 * 100) / 100];
    }
  }
  _cache.set(v, out);
  return out;
};
const key = (c) => c ? c.join(',') : '';
const px = (v) => { const n = parseFloat(v); return isNaN(n) ? 0 : n; };
const region = (el) => el.closest('header, [role=banner]') ? 'header' : el.closest('footer, [role=contentinfo]') ? 'footer' : el.closest('nav') ? 'nav' : el.closest('main, [role=main]') ? 'main' : 'body';
"""

JS_SNAPSHOT = "() => {" + JS_COMMON + r"""
  const bgMap = new Map(), textMap = new Map(), linkMap = new Map(), borderMap = new Map(), fontMap = new Map();
  const radiusMap = new Map(), shadowMap = new Map(), spaceMap = new Map(), sizeMap = new Map();
  const add = (m, k, w, init) => { const e = m.get(k) || init(); e.w += w; m.set(k, e); return e; };
  const els = [...document.querySelectorAll('body *')].slice(0, 7000);
  const html = document.documentElement, body = document.body;
  const pageBg = (() => { for (const e of [body, html]) { const c = rgba(getComputedStyle(e).backgroundColor); if (c && c[3] > 0.05) return c; } return [255, 255, 255, 1]; })();
  const bgOf = (el) => {                       // the colour painted behind an element: layers composited down to the page
    let layers = [];
    for (let e = el; e && e.nodeType === 1; e = e.parentElement) {
      const c = rgba(getComputedStyle(e).backgroundColor);
      if (c && c[3] > 0) { layers.push(c); if (c[3] >= 0.99) break; }
    }
    let out = pageBg.slice(0, 3);
    for (const c of layers.reverse()) out = out.map((v, i) => Math.round(c[i] * c[3] + v * (1 - c[3])));
    return out;
  };
  const bgEntries = new Map();                 // element -> its bg entry, so a child's area is taken off its parent's
  for (const el of els) {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity) === 0) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) continue;
    const w = Math.min(r.width, 3000), h = Math.min(r.height, 3000), area = w * h;
    const bg = rgba(cs.backgroundColor);
    if (bg && bg[3] > 0.05) {
      const e = add(bgMap, key(bg), 0, () => ({ c: bg, w: 0, tags: {} }));
      let take = area * bg[3];
      for (let p = el.parentElement; p; p = p.parentElement) { const pe = bgEntries.get(p); if (pe) { pe.rem = Math.max(0, pe.rem - take); break; } }
      bgEntries.set(el, { e, rem: area * bg[3] });
      e.tags[el.tagName.toLowerCase()] = (e.tags[el.tagName.toLowerCase()] || 0) + 1;
    }
    if (cs.backgroundImage && cs.backgroundImage.includes('gradient')) {
      for (const m of cs.backgroundImage.matchAll(/rgba?\([^)]+\)/g)) { const c = rgba(m[0]); if (c && c[3] > 0.05) add(bgMap, key(c), area * 0.1 * c[3], () => ({ c, w: 0, tags: { gradient: 1 } })); }
    }
    let chars = 0;
    for (const n of el.childNodes) if (n.nodeType === 3) chars += n.data.trim().length;
    const fs = px(cs.fontSize);
    if (chars > 0) {
      const tc = rgba(cs.color), wt = chars * fs;
      if (tc) {
        const e = add(textMap, key(tc), wt, () => ({ c: tc, w: 0, on: {} }));
        const under = bgOf(el), k = key(under);
        e.on[k] = (e.on[k] || 0) + wt;
        const an = el.closest('a');
        if (an && !el.closest('button, [role=button]')) {          // a link, unless it is drawn as a button (a fill or an edge)
          const acs = getComputedStyle(an), abg = rgba(acs.backgroundColor);
          const buttonish = (abg && abg[3] >= 0.5) || (px(acs.borderTopWidth) > 0 && acs.borderTopStyle !== 'none');
          if (!buttonish) add(linkMap, key(tc), wt, () => ({ c: tc, w: 0 }));
        }
      }
      add(fontMap, cs.fontFamily + '|' + cs.fontWeight, chars, () => ({ family: cs.fontFamily, weight: parseInt(cs.fontWeight) || 400, w: 0 }));
      sizeMap.set(fs, (sizeMap.get(fs) || 0) + chars);
    }
    for (const side of ['Top', 'Right', 'Bottom', 'Left']) {
      const bw = px(cs['border' + side + 'Width']), bs = cs['border' + side + 'Style'];
      if (bw > 0 && bs !== 'none' && bs !== 'hidden') {
        const bc = rgba(cs['border' + side + 'Color']);
        if (bc && bc[3] > 0.05) add(borderMap, key(bc), (side === 'Top' || side === 'Bottom') ? w : h, () => ({ c: bc, w: 0 }));
      }
    }
    const rad = px(cs.borderTopLeftRadius);
    if (rad > 0) { const e = add(radiusMap, Math.min(Math.round(rad), 999), 1, () => ({ n: 0, big: 0, w: 0 })); e.n += 1; if (area > 15000) e.big += 1; }
    if (cs.boxShadow && cs.boxShadow !== 'none') add(shadowMap, cs.boxShadow, 1, () => ({ v: cs.boxShadow, w: 0 }));
    for (const p of ['paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft', 'marginTop', 'marginBottom', 'rowGap', 'columnGap']) {
      const v = Math.round(px(cs[p])); if (v > 0 && v <= 400) spaceMap.set(v, (spaceMap.get(v) || 0) + 1);
    }
  }
  const bg = [...bgMap.values()].map(e => ({ c: e.c, w: Math.round(e.w), tags: e.tags }));
  for (const [el, b] of bgEntries) { const o = bg.find(x => key(x.c) === key(b.e.c)); if (o) o.w += Math.round(b.rem); }
  // type: the first heading of each level, the body copy, the small print
  const styleOf = (el) => { const cs = getComputedStyle(el); const lh = px(cs.lineHeight);
    return { size: px(cs.fontSize), lh: cs.lineHeight === 'normal' ? null : lh, weight: parseInt(cs.fontWeight) || 400, family: cs.fontFamily,
             ls: cs.letterSpacing === 'normal' ? 0 : px(cs.letterSpacing), color: rgba(cs.color), transform: cs.textTransform }; };
  const type = {};
  for (const t of ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']) { const el = [...document.querySelectorAll(t)].find(e => e.getBoundingClientRect().width > 0 && e.textContent.trim()); if (el) type[t] = styleOf(el); }
  const para = [...document.querySelectorAll('main p, article p, p')].filter(e => e.textContent.trim().length > 40 && e.getBoundingClientRect().width > 0);
  const sizes = {}; for (const p of para) { const s = px(getComputedStyle(p).fontSize); sizes[s] = (sizes[s] || 0) + p.textContent.length; }
  const top = Object.entries(sizes).sort((a, b) => b[1] - a[1])[0];
  const bodyEl = top ? para.find(p => px(getComputedStyle(p).fontSize) === parseFloat(top[0])) : body;
  type.body = styleOf(bodyEl || body);
  const smallEl = [...document.querySelectorAll('small, figcaption, .small, .caption, footer p')].find(e => e.textContent.trim().length > 3 && e.getBoundingClientRect().width > 0);
  if (smallEl) type.small = styleOf(smallEl);
  // buttons: anything that looks pressed-for-action, grouped by how it is drawn
  const groups = new Map();
  let idx = 0;
  const cands = document.querySelectorAll('button, [role=button], a[href], input[type=submit], input[type=button]');
  for (const el of cands) {
    const cs = getComputedStyle(el), r = el.getBoundingClientRect();
    if (cs.display === 'none' || cs.visibility === 'hidden' || r.width < 20 || r.height < 16 || r.width > 520 || r.height > 120) continue;
    const bgc = rgba(cs.backgroundColor), solid = bgc && bgc[3] >= 0.9;
    const bw = px(cs.borderTopWidth), bc = rgba(cs.borderTopColor), edged = bw > 0 && cs.borderTopStyle !== 'none' && bc && bc[3] > 0.2;
    const pad = px(cs.paddingLeft) + px(cs.paddingRight);
    const isBtn = el.matches('button, [role=button], input[type=submit], input[type=button]');
    if (!(solid || edged) || pad < 16) continue;                // a real button has a fill or an edge and room around its text
    if (el.closest('nav') && !solid && !isBtn) continue;
    const text = (el.value || el.textContent || el.getAttribute('aria-label') || '').replace(/\s+/g, ' ').trim().slice(0, 60);
    if (!text || text.length > 40) continue;
    const st = { bg: solid ? bgc : (bgc && bgc[3] > 0 ? bgc : null), color: rgba(cs.color), border: edged ? [bc, bw, cs.borderTopStyle] : null, radius: Math.round(px(cs.borderTopLeftRadius)),
                 padding: [px(cs.paddingTop), px(cs.paddingRight), px(cs.paddingBottom), px(cs.paddingLeft)].map(Math.round), size: px(cs.fontSize), weight: parseInt(cs.fontWeight) || 400,
                 shadow: cs.boxShadow === 'none' ? '' : cs.boxShadow, family: cs.fontFamily, transform: cs.textTransform, height: Math.round(r.height) };
    if (!st.bg && !st.border) continue;
    const gk = JSON.stringify([st.bg, st.color, st.border, st.radius, st.padding, st.size, st.weight]);
    let g = groups.get(gk);
    if (!g) { g = { idx: idx++, text, tag: el.tagName.toLowerCase(), region: region(el), n: 0, main: false, rest: st, texts: [] }; groups.set(gk, g); el.setAttribute('data-bk-btn', g.idx); }
    g.n += 1; g.main = g.main || region(el) === 'main' || region(el) === 'header';
    if (g.texts.length < 4 && !g.texts.includes(text)) g.texts.push(text);
  }
  const buttons = [...groups.values()].sort((a, b) => b.n - a.n).slice(0, 12);
  // links: running text links that are not buttons
  const lgroups = new Map(); let lidx = 0;
  for (const el of document.querySelectorAll('main a[href], article a[href], p a[href]')) {
    if (el.matches('[data-bk-btn]') || el.closest('button, [role=button]') || el.getBoundingClientRect().width < 4) continue;
    const cs = getComputedStyle(el), c = rgba(cs.color); if (!c) continue;
    const gk = key(c) + '|' + cs.textDecorationLine + '|' + cs.fontWeight;
    let g = lgroups.get(gk);
    if (!g) { g = { idx: lidx++, color: c, deco: cs.textDecorationLine, weight: parseInt(cs.fontWeight) || 400, n: 0 }; lgroups.set(gk, g); el.setAttribute('data-bk-link', g.idx); }
    g.n += 1;
  }
  const links = [...lgroups.values()].sort((a, b) => b.n - a.n).slice(0, 3);
  // logo, icons, meta, CSS variables
  const logoEl = [...document.querySelectorAll('header a img, header a svg, header img, header svg, [class*=logo i] img, [class*=logo i] svg, img[src*=logo i], img[alt*=logo i]')]
    .find(e => { const r = e.getBoundingClientRect(); return r.width >= 16 && r.height >= 12 && r.width < 700; });
  let logo = null;
  if (logoEl) {
    const r = logoEl.getBoundingClientRect(), a = logoEl.closest('a');
    logo = { kind: logoEl.tagName.toLowerCase() === 'svg' ? 'svg' : 'img', src: logoEl.currentSrc || logoEl.src || '', alt: logoEl.getAttribute('alt') || logoEl.getAttribute('aria-label') || '',
             width: Math.round(r.width), height: Math.round(r.height), href: a ? a.getAttribute('href') : '', bg: bgOf(logoEl),
             svg: logoEl.tagName.toLowerCase() === 'svg' && logoEl.outerHTML.length < 30000 ? logoEl.outerHTML : '' };
  }
  const icons = [...document.querySelectorAll('link[rel~=icon], link[rel=apple-touch-icon], link[rel=mask-icon], link[rel=manifest], link[rel=shortcut\\ icon]')]
    .map(l => ({ rel: l.getAttribute('rel'), href: l.href, sizes: l.getAttribute('sizes') || '', type: l.getAttribute('type') || '' }));
  const meta = {};
  for (const m of document.querySelectorAll('meta[name=theme-color], meta[property="og:image"], meta[property="og:site_name"], meta[name=description]')) meta[m.getAttribute('name') || m.getAttribute('property')] = m.content;
  const vars = {}, varColors = {};
  const cs0 = getComputedStyle(html);
  for (const sheet of document.styleSheets) {
    let rules; try { rules = sheet.cssRules; } catch (e) { continue; }
    for (const r of rules) {
      if (!r.style || !r.selectorText || !/(^|,\s*)(:root|html|body)\b/.test(r.selectorText)) continue;
      for (const name of r.style) if (name.startsWith('--') && Object.keys(vars).length < 400) {
        const v = cs0.getPropertyValue(name).trim(); if (!v) continue;
        vars[name] = v.slice(0, 200);
        const c = rgba(v); if (c) varColors[name] = c;
      }
    }
  }
  const docH = Math.max(html.scrollHeight, body.scrollHeight);
  return { title: document.title, width: innerWidth, height: docH, pageBg, bg, text: [...textMap.values()].map(e => ({ c: e.c, w: Math.round(e.w), on: Object.entries(e.on).map(([k, v]) => ({ c: k.split(',').map(Number), w: Math.round(v) })) })),
           link: [...linkMap.values()].map(e => ({ c: e.c, w: Math.round(e.w) })), border: [...borderMap.values()].map(e => ({ c: e.c, w: Math.round(e.w) })),
           fonts: [...fontMap.values()].map(e => ({ family: e.family, weight: e.weight, w: e.w })), type,
           radius: [...radiusMap.entries()].map(([p, e]) => ({ px: p, n: e.n, big: e.big })), shadow: [...shadowMap.values()].map(e => ({ v: e.v, n: e.w })).sort((a, b) => b.n - a.n).slice(0, 8),
           space: [...spaceMap.entries()].map(([p, n]) => ({ px: p, n })), sizes: [...sizeMap.entries()].map(([s, n]) => ({ px: s, n })),
           buttons, links, logo, icons, meta, vars, varColors };
}"""

JS_STATE = "(sel) => {" + JS_COMMON + r"""
  const el = document.querySelector(sel); if (!el) return null;
  const cs = getComputedStyle(el);
  const bc = rgba(cs.borderTopColor), oc = rgba(cs.outlineColor);
  return { bg: rgba(cs.backgroundColor), color: rgba(cs.color), border: px(cs.borderTopWidth) > 0 && cs.borderTopStyle !== 'none' ? [bc, px(cs.borderTopWidth), cs.borderTopStyle] : null,
           radius: Math.round(px(cs.borderTopLeftRadius)), shadow: cs.boxShadow === 'none' ? '' : cs.boxShadow, deco: cs.textDecorationLine, weight: parseInt(cs.fontWeight) || 400,
           outline: px(cs.outlineWidth) > 0 && cs.outlineStyle !== 'none' ? [oc, px(cs.outlineWidth), px(cs.outlineOffset)] : null, transform: cs.transform === 'none' ? '' : cs.transform };
}"""


def allowed(url: str, cfg: dict) -> bool:
    """Is the browser allowed to ask this address? Never the live host of a no-crawl project, never an analytics script."""
    if not url.startswith(("http://", "https://")):
        return True
    return not fetch_rule.blocked(url, cfg) and not ANALYTICS.search(url)


def snapshot_pages(urls: list[str], cfg: dict, timeout_ms: int = 30000) -> list[dict]:
    """One browser, one fresh page per address: a snapshot for each. Every address was checked against the live-site rule by
    the caller. The browser is closed whatever happens."""
    from playwright.sync_api import sync_playwright
    out = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for url in urls:
                ctx = browser.new_context(viewport={"width": WIDTH, "height": HEIGHT})
                try:
                    ctx.route("**/*", lambda route: route.continue_() if allowed(route.request.url, cfg) else route.abort())
                    page = ctx.new_page()
                    resp = page.goto(url, wait_until="load", timeout=timeout_ms)
                    try:
                        page.wait_for_load_state("networkidle", timeout=4000)
                    except Exception:  # noqa: BLE001  a page that never goes quiet is read as it is
                        pass
                    if resp is not None and resp.status >= 400:
                        out.append({"url": url, "error": f"http {resp.status}"})
                        continue
                    snap = page.evaluate(JS_SNAPSHOT)
                    snap["url"] = url
                    for b in snap["buttons"][:4]:
                        sel = f'[data-bk-btn="{b["idx"]}"]'
                        b["hover"], b["focus"] = _states(page, sel)
                    for ln in snap["links"][:2]:
                        ln["hover"], _ = _states(page, f'[data-bk-link="{ln["idx"]}"]')
                    out.append(snap)
                except Exception as e:  # noqa: BLE001  one page that will not load must not lose the rest
                    out.append({"url": url, "error": f"{type(e).__name__}: {str(e)[:120]}"})
                finally:
                    ctx.close()
        finally:
            browser.close()
    return out


def _states(page, sel):
    """(hover, focus) styles of one element: the mouse over it, then the keyboard on it. Either is None when it could not be read."""
    hover = focus = None
    try:
        page.hover(sel, timeout=3000)
        page.wait_for_timeout(250)                          # a transition on hover has to finish before it is read
        hover = page.evaluate(JS_STATE, sel)
        page.mouse.move(0, 0)
        page.wait_for_timeout(250)
        page.evaluate("(sel) => { const e = document.querySelector(sel); if (e) e.focus({ focusVisible: true }); }", sel)
        page.wait_for_timeout(150)
        focus = page.evaluate(JS_STATE, sel)
        page.evaluate("(sel) => { const e = document.querySelector(sel); if (e) e.blur(); }", sel)
    except Exception:  # noqa: BLE001
        pass
    return hover, focus
