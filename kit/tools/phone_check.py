#!/usr/bin/env python3
"""Phone readability in a real browser (rules 68 and 70). Built 17 Nov 2026 after the final look at five pages found,
by eye, chart labels drawn at 5.5 px, a time box clipped at 360 px, tables whose key column sat off screen and footer
links 19 px tall. Each of these is measurable, so it is measured, not left to a screenshot.

  growth phone_check <local URL> [--width 390] [--json out.json]

At each width (default 360, 390, 820 and 1024) it loads the page in headless Chromium with analytics hosts blocked,
scrolls to the end and back so in-view parts settle, then reports:
  - assets:   any /_next/static file that answers 400 or more (a broken build serves an unstyled page)
  - overflow: the page scrolls sideways, or a box clips its content sideways with no visible scroll cue (rule 68)
  - text:     visible text drawn under 12 px on screen, SVG text included (font size x the drawing's scale) (rule 70)
  - taps:     a header, nav, menu or footer link or button under 24 x 24 px (rule 70; WCAG 2.2 target size). A link inline in a
              sentence is exempt (WCAG 2.5.8); a list of links with only separators between them is not
Text and tap sizes are judged at phone widths (under 640 px); overflow and assets at every width.
Exit 1 on any problem. Local dev server only.
"""
from __future__ import annotations

import argparse
import json
import sys

BLOCK = ("googletagmanager.com", "google-analytics.com", "clarity.ms", "ahrefs.com", "analytics.ahrefs.com")
WIDTHS = (360, 390, 820, 1024)

JS_MEASURE = r"""
(phone) => {
  const out = { overflow: [], text: [], taps: [] };
  const de = document.documentElement;
  if (de.scrollWidth > window.innerWidth + 1) out.overflow.push(`page is ${de.scrollWidth}px wide in a ${window.innerWidth}px screen`);
  const vis = (el) => el && el.checkVisibility && el.checkVisibility({ opacityProperty: true, visibilityProperty: true });
  const label = (el) => {
    const t = (el.innerText || el.textContent || el.getAttribute('aria-label') || '').trim().replace(/\s+/g, ' ');
    const c = (el.getAttribute('class') || '').toString().split(/\s+/)[0];
    return `${el.tagName.toLowerCase()}${c ? '.' + c : ''} "${t.slice(0, 50)}"`;
  };
  // boxes that clip sideways: overflow-x auto/scroll/hidden with more content than room
  document.querySelectorAll('body *').forEach((el) => {
    const cs = getComputedStyle(el);
    if (!['auto', 'scroll', 'hidden', 'clip'].includes(cs.overflowX)) return;
    if (el.scrollWidth <= el.clientWidth + 2 || !vis(el) || el.clientWidth < 40) return;
    if (el.closest('svg')) return;
    const r = el.getBoundingClientRect();
    if (r.height < 16) return;  // a one-line ellipsis box is a design choice, not lost content
    if (cs.textOverflow === 'ellipsis') return;
    const hidden = el.scrollWidth - el.clientWidth;
    const scrolls = cs.overflowX === 'auto' || cs.overflowX === 'scroll';
    if (!scrolls) {
      // a clipping box (a page wrapper that trims decoration, a card) is only a problem when TEXT is cut off
      const box = el.getBoundingClientRect();
      const tw = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
      let t, cut = 0, first = '';
      while ((t = tw.nextNode())) {
        if (!t.nodeValue.trim() || !vis(t.parentElement)) continue;
        // text inside an inner box that clips or scrolls is that box's own report
        let a = t.parentElement, inner = false;
        while (a && a !== el) { if (['auto', 'scroll', 'hidden', 'clip'].includes(getComputedStyle(a).overflowX)) { inner = true; break; } a = a.parentElement; }
        if (inner) continue;
        const rg = document.createRange(); rg.selectNodeContents(t);
        const rr = rg.getBoundingClientRect();
        if (rr.width > 1 && (rr.right > box.right + 1 || rr.left < box.left - 1)) { cut++; if (!first) first = t.nodeValue.trim().slice(0, 40); }
      }
      if (cut) out.overflow.push(`${label(el)} cuts off ${cut} text run(s) sideways, e.g. "${first}"`);
      return;
    }
    // a scroll box is fine when it says so (a role=region with a name, or a visible hint inside or next to it)
    const cue = el.matches('[role=region][aria-label], [data-scroll-cue]') || el.parentElement?.querySelector('[data-scroll-cue]');
    if (cue) return;
    out.overflow.push(`${label(el)} hides ${hidden}px of its content sideways (scrolls, no cue)`);
  });
  if (phone) {
    const seen = new Set();
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
      acceptNode: (n) => (n.nodeValue.trim().length > 0 ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT),
    });
    let n;
    while ((n = walker.nextNode())) {
      const el = n.parentElement;
      if (!el || seen.has(el) || !vis(el) || el.closest('script, style, noscript, title')) continue;
      seen.add(el);
      const range = document.createRange();
      range.selectNodeContents(n);
      const rr = range.getBoundingClientRect();
      if (rr.width <= 1 || rr.height <= 1) continue;               // screen-reader-only text
      if (rr.bottom < -50 && el.closest('a[href^="#"]')) continue;  // the skip link, parked above the page
      let px = parseFloat(getComputedStyle(el).fontSize);
      const svgEl = el.closest('svg') ? el : null;
      if (svgEl && svgEl.getScreenCTM) {
        const m = svgEl.getScreenCTM();
        if (m) px = px * Math.hypot(m.a, m.b);
      }
      if (px < 11.95) out.text.push(`${label(el)} draws at ${px.toFixed(1)}px`);
    }
    // WCAG 2.5.8 exempts a target that sits inline in a sentence or block of text (its size is set by the line height of the text
    // around it). A link is "in a sentence" when it is inline and the text around it, inside its nearest block, holds real words:
    // a list of links with only separators ("|", a dot) between them is NOT a sentence.
    // "inline" includes inline-flex / inline-block / inline-grid: a link laid out as inline-flex to sit next to its icon
    // ("Space-O Technologies ↗" in a footer sentence) still sits in the line of the sentence (friction 44, 19 Nov 2026)
    const inSentence = (el) => {
      if (!/^inline(-flex|-block|-grid)?$/.test(getComputedStyle(el).display)) return false;
      let box = el.parentElement;
      while (box && getComputedStyle(box).display === 'inline') box = box.parentElement;
      if (!box) return false;
      let around = '';
      const walk = (n) => {
        for (const c of n.childNodes) {
          if (c === el) continue;
          if (c.nodeType === 3) around += ' ' + c.textContent;
          else if (c.nodeType === 1 && !c.matches('a[href], button') && getComputedStyle(c).display === 'inline') walk(c);
        }
      };
      walk(box);
      return /[\p{L}]{2,}/u.test(around);
    };
    const tapSel = ':is(header, footer, nav):not(main *) :is(a[href], button), [role=menu] :is(a, button), [role=menuitem]';
    document.querySelectorAll(tapSel).forEach((el) => {
      if (!vis(el)) return;
      const r = el.getBoundingClientRect();
      if (r.width < 1 || r.height < 1) return;
      if (r.bottom < -50) return;  // the skip link, parked above the page until it gets focus
      if (inSentence(el)) return;
      if (r.width < 23.5 || r.height < 23.5) out.taps.push(`${label(el)} is ${Math.round(r.width)}x${Math.round(r.height)}px`);
    });
  }
  return out;
}
"""


def check(url, width):
    from playwright.sync_api import sync_playwright
    probs = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            ctx = browser.new_context(viewport={"width": width, "height": 800}, reduced_motion="reduce",
                                      device_scale_factor=1, is_mobile=width < 640, has_touch=width < 640)
            ctx.route("**/*", lambda r: r.abort() if any(h in r.request.url for h in BLOCK) else r.continue_())
            page = ctx.new_page()
            bad = []
            page.on("response", lambda resp: bad.append(f"{resp.status} {resp.url.split('/_next/', 1)[-1]}")
                    if "/_next/static/" in resp.url and resp.status >= 400 else None)
            page.goto(url, wait_until="load", timeout=120000)
            page.wait_for_timeout(1000)
            h = page.evaluate("document.documentElement.scrollHeight")
            for y in range(0, h, 600):
                page.evaluate(f"window.scrollTo(0, {y})")
                page.wait_for_timeout(60)
            page.evaluate("window.scrollTo(0, 0)")
            page.add_style_tag(content="*{transition:none!important;animation:none!important}")
            page.wait_for_timeout(400)
            m = page.evaluate(JS_MEASURE, width < 640)
            probs += [f"assets: {b}" for b in sorted(set(bad))]
            probs += [f"overflow: {x}" for x in m["overflow"]]
            probs += [f"text: {x}" for x in sorted(set(m["text"]))]
            probs += [f"taps: {x}" for x in sorted(set(m["taps"]))]
        finally:
            browser.close()
    return probs


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("--width", type=int, action="append")
    ap.add_argument("--json")
    a = ap.parse_args()
    if "127.0.0.1" not in a.url and "localhost" not in a.url:
        sys.exit("local dev server only")
    res = {w: check(a.url, w) for w in (a.width or WIDTHS)}
    if a.json:
        with open(a.json, "w") as f:
            json.dump({"url": a.url, "problems": res}, f, indent=1)
    n = 0
    for w, probs in res.items():
        for p in probs:
            print(f"FAIL {w}px {p}")
        n += len(probs)
    print(f"{n} phone problems at {', '.join(str(w) for w in res)}px")
    sys.exit(1 if n else 0)


if __name__ == "__main__":
    main()
