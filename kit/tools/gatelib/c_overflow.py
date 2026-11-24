"""Text that leaves its box, content under the sticky header, a clipped breadcrumb (2.8.5; rule 158a).
Measured in a real headless browser at 1024, 1440 and 390 px, scrollY 0. One pass per URL; the three checks read the cache."""
from __future__ import annotations

from .c_layout import is_legal  # noqa: F401  (kept for symmetry with the layout checks)
from .core import Skip, check

WIDTHS = ((1024, 768), (1440, 900), (390, 844))

PROBE_JS = r"""
() => {
  const cs = e => getComputedStyle(e), R = e => e.getBoundingClientRect();
  const vis = e => { const s = cs(e); if (s.display === 'none' || s.visibility === 'hidden' || parseFloat(s.opacity) === 0) return false;
    const r = R(e); return r.width > 1 && r.height > 1; };
  const lbl = t => t.replace(/\s+/g, ' ').trim().slice(0, 50);
  const main = document.querySelector('main') || document.body;
  const out = {overflow: [], hidden: [], crumbs: [], header: null, vw: innerWidth};
  // (a) text past its own bordered box. HTML: a text node whose line box crosses the border box of the nearest bordered ancestor.
  const bordered = e => { const s = cs(e); return ['Top', 'Right', 'Bottom', 'Left'].filter(k => parseFloat(s['border' + k + 'Width']) > 0
                          && s['border' + k + 'Style'] !== 'none').length >= 3; };
  const walker = document.createTreeWalker(main, NodeFilter.SHOW_TEXT);
  for (let n; (n = walker.nextNode());) {
    const t = lbl(n.textContent); if (!t || !n.parentElement || n.parentElement.closest('svg, script, style, [aria-hidden=true]')) continue;
    if (!vis(n.parentElement)) continue;
    const rg = document.createRange(); rg.selectNodeContents(n); const q = rg.getBoundingClientRect(); if (q.width < 2) continue;
    let a = n.parentElement; while (a && a !== main && !bordered(a)) a = a.parentElement;
    if (!a || a === main || !vis(a)) continue;
    const s = cs(a);
    const r = R(a), bl = parseFloat(s.borderLeftWidth) || 0, br = parseFloat(s.borderRightWidth) || 0;
    const over = Math.max(r.left + bl - q.left, q.right - (r.right - br));
    if (over > 1.5 && q.right > 0 && q.left < innerWidth) out.overflow.push({text: t, by: Math.round(over), kind: 'html', box: (a.className && a.className.baseVal === undefined ? String(a.className) : a.tagName.toLowerCase()).slice(0, 30)});
  }
  // SVG drawings: a <text> against the smallest stroked <rect> that holds its centre
  for (const svg of main.querySelectorAll('svg')) {
    if (!vis(svg)) continue;
    const rects = [...svg.querySelectorAll('rect')].filter(r => { const s = cs(r); return s.stroke && s.stroke !== 'none' && parseFloat(s.strokeWidth) > 0 && R(r).width > 20; });
    for (const tx of svg.querySelectorAll('text')) {
      const t = lbl(tx.textContent); if (!t || !vis(tx)) continue;
      const q = R(tx), cx = q.left + 2, cy = (q.top + q.bottom) / 2;   // the line starts inside its card: follow it from its left edge
      const hold = rects.map(r => ({r, b: R(r)})).filter(x => x.b.left <= cx && cx <= x.b.right && x.b.top <= cy && cy <= x.b.bottom && x.b.height >= q.height)
                        .sort((p, w) => p.b.width * p.b.height - w.b.width * w.b.height)[0];
      if (!hold) continue;
      const over = Math.max(hold.b.left - q.left, q.right - hold.b.right);
      if (over > 1.5) out.overflow.push({text: t, by: Math.round(over), kind: 'svg', box: 'svg rect'});
    }
  }
  // (b) the sticky header, and whatever shows beneath it at scrollY 0
  window.scrollTo(0, 0);
  const hs = [...document.querySelectorAll('header, nav, [role=banner], .site-header')].filter(e => ['sticky', 'fixed'].includes(cs(e).position)
              && vis(e) && R(e).top <= 1 && R(e).width >= innerWidth * 0.6 && !e.closest('main'));
  const h = hs.sort((p, w) => R(w).bottom - R(p).bottom)[0];
  if (h) {
    const hb = R(h).bottom; out.header = {bottom: Math.round(hb), tag: h.tagName.toLowerCase()};
    const w2 = document.createTreeWalker(main, NodeFilter.SHOW_TEXT);
    for (let n; (n = w2.nextNode());) {
      const t = lbl(n.textContent); const p = n.parentElement; if (!t || !p || p.closest('script, style, svg, [aria-hidden=true]') || h.contains(p) || !vis(p)) continue;
      const rg = document.createRange(); rg.selectNodeContents(n); const q = rg.getBoundingClientRect();
      if (q.width < 2 || q.bottom <= 0 || q.top >= hb - 1 || q.left >= innerWidth || q.right <= 0) continue;
      const el = document.elementFromPoint(Math.min(Math.max((q.left + q.right) / 2, 1), innerWidth - 1), Math.max(q.top + q.height / 2, 1));
      if (el && h.contains(el)) out.hidden.push({text: t, top: Math.round(q.top), under: Math.round(hb - q.top)});
    }
  }
  // breadcrumb: the first items must be inside their box and the screen
  for (const c of document.querySelectorAll('nav[aria-label*=readcrumb i], .breadcrumb, .breadcrumbs, [class*=breadcrumb]')) {
    if (!vis(c) || c.closest('script')) continue;
    const items = [...c.querySelectorAll('li, a')].filter(i => lbl(i.textContent) && vis(i));
    if (!items.length) continue;
    const box = [c, ...c.querySelectorAll('ol, ul')].find(e => cs(e).overflowX !== 'visible') || c;
    const br = R(box), first = items[0], fr = R(first);
    out.crumbs.push({first: lbl(first.textContent).slice(0, 30), left: Math.round(fr.left), boxLeft: Math.round(br.left), scrollLeft: Math.round(box.scrollLeft),
                     clipped: fr.left < Math.max(br.left, 0) - 1 || fr.right <= Math.max(br.left, 0) || box.scrollLeft > 1, n: items.length});
  }
  return out;
}
"""


def probe(ctx):
    """{width: data}: what the page shows at 1024, 1440 and 390 at scroll position 0. Measured once per URL."""
    key = ("overflow", ctx.url)
    if key in ctx.cache:
        return ctx.cache[key]
    ctx.need_html()
    from .c_links import need_browser
    need_browser(ctx)
    if not ctx.url:
        raise Skip("no page URL to open in a browser", blocked=True)
    from playwright.sync_api import sync_playwright
    out = {}
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            try:
                for w, h in WIDTHS:
                    c = b.new_context(viewport={"width": w, "height": h}, reduced_motion="reduce")
                    try:
                        pg = c.new_page()
                        pg.goto(ctx.url, wait_until="load", timeout=60000)
                        pg.add_style_tag(content="*,*::before,*::after{animation:none!important;transition:none!important;scroll-behavior:auto!important}")
                        pg.wait_for_timeout(300)
                        out[w] = pg.evaluate(PROBE_JS)
                    finally:
                        c.close()
            finally:
                b.close()
    except Exception as e:  # noqa: BLE001
        raise Skip(f"could not measure the page in a headless browser ({type(e).__name__}: {str(e).splitlines()[0][:100] if str(e) else ''})", blocked=True)
    ctx.cache[key] = out
    return out


@check("layout.text-overflow", "158a", what="no text runs past the border of its own card or box at 1024, 1440 and 390 px (rule 158)", needs="live")
def text_overflow(ctx):
    probs, seen = [], set()
    for w, d in probe(ctx).items():
        for o in d["overflow"]:
            if (o["text"], w) not in seen:
                seen.add((o["text"], w))
                probs.append(f"'{o['text']}' crosses its {o['kind']} box '{o['box']}' by {o['by']} px at {w}")
    ctx.verdict(probs[:12], "no text crosses the border of its box at 1024, 1440 or 390",
                "shorten the line, widen the box, or let the text wrap inside it; in a drawing, size the card to its longest line (rule 158a)")


@check("layout.under-header", "158a", what="at scroll position 0 no content sits under the sticky header (rule 158)", needs="live")
def under_header(ctx):
    probs, heads = [], 0
    for w, d in probe(ctx).items():
        if d["header"]:
            heads += 1
        for o in d["hidden"][:3]:
            probs.append(f"'{o['text']}' is {o['under']} px under the sticky header at {w} (header bottom {d['header']['bottom']} px)")
    ctx.verdict(probs, f"{heads} sticky header(s) measured, nothing beneath them at scroll position 0",
                "pad the page's first content by the header's height (or html scroll-padding and a body offset) so the first line starts below it (rule 158a)")


@check("layout.breadcrumb-390", "158a", what="the breadcrumb shows its first item whole at 390 px (not clipped or scrolled out) (rule 158)", needs="live")
def breadcrumb_390(ctx):
    probs, n = [], 0
    for c in (probe(ctx).get(390) or {}).get("crumbs", []):
        n += 1
        if c["clipped"]:
            probs.append(f"breadcrumb of {c['n']} items: first item '{c['first']}' starts at {c['left']} px (box at {c['boxLeft']} px, scrolled {c['scrollLeft']} px) at 390")
    ctx.verdict(probs, f"{n} breadcrumb(s) at 390, the first item is in view",
                "let the breadcrumb wrap, or start it scrolled to the left, so Home and the first level are never cut off (rule 158a)")
