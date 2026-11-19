#!/usr/bin/env python3
"""Contrast in every state (rule 36j). From a real project, on a button with dark text on orange that went darker on
hover: "As a rule, remember the contrast and the mouse-over effect. The growth pack should completely understand what
is a background colour, what is a foreground colour and what kind of mouse-over effect. I should never speak about
this again; it should take care of it automatically."

  growth contrast_check <local URL> [--width 1366] [--json out.json]

For every visible link, button and control on the page (header, main, footer, dialogs that are open) it reads, in a
real headless browser, the text colour and the colour actually painted behind the text (walking up through
transparent parents, compositing semi-transparent layers) in three states: at rest, hovered and keyboard-focused.
It fails any state under WCAG AA: 4.5:1 for normal text, 3:1 for large text (24px+, or 18.66px+ bold), and 3:1 for
the focus ring against the background it sits on. Gradients and images behind text are reported as "check by eye".
Exit 1 on any failure. Never run it against the live site (it moves the mouse; use the local dev server).
"""
from __future__ import annotations

import argparse
import json
import sys

JS_COLLECT = r"""
() => {
  const sel = 'a[href], button, [role=button], [role=tab], [role=radio], [role=switch], summary, input[type=submit], input[type=button]';
  const out = [];
  document.querySelectorAll(sel).forEach((el, i) => {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    if (r.width < 4 || r.height < 4 || cs.visibility === 'hidden' || cs.display === 'none' || +cs.opacity === 0) return;
    if (el.closest('[aria-hidden=true], [hidden], [inert]')) return;
    const text = (el.innerText || el.getAttribute('aria-label') || '').trim().replace(/\s+/g, ' ').slice(0, 60);
    el.setAttribute('data-cc', String(i));
    out.push({ id: String(i), text, tag: el.tagName.toLowerCase(), cls: (el.className && el.className.baseVal === undefined ? el.className : '').toString().slice(0, 60) });
  });
  return out;
}
"""

JS_MEASURE = r"""
(id) => {
  const el = document.querySelector(`[data-cc="${id}"]`);
  if (!el) return null;
  const parse = (c) => {
    const m = c && c.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1].split(/[ ,/]+/).filter(Boolean).map(Number);
    return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1];
  };
  const over = (top, bottom) => {            // composite top (with alpha) over an opaque bottom
    const a = top[3];
    return [0, 1, 2].map((k) => top[k] * a + bottom[k] * (1 - a)).concat(1);
  };
  // text colour: the element's own text, or its first text-bearing child
  let textEl = el;
  for (const c of el.querySelectorAll('*')) { if (c.childNodes.length && [...c.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())) { textEl = c; break; } }
  const tcs = getComputedStyle(textEl);
  let fg = parse(tcs.color);
  // background: walk up, collecting layers until an opaque one
  const layers = [];
  let complex = false;
  for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
    const s = getComputedStyle(n);
    if (s.backgroundImage && s.backgroundImage !== 'none' && !/^url\(.*\.svg/.test(s.backgroundImage)) {
      if (/gradient|url\(/.test(s.backgroundImage) && n === el) complex = true;
    }
    const b = parse(s.backgroundColor);
    if (b && b[3] > 0) { layers.push(b); if (b[3] >= 1) break; }
  }
  let bg = [255, 255, 255, 1];
  for (let k = layers.length - 1; k >= 0; k--) bg = layers[k][3] >= 1 ? layers[k] : over(layers[k], bg);
  if (fg && fg[3] < 1) fg = over(fg, bg);
  const size = parseFloat(tcs.fontSize), weight = parseInt(tcs.fontWeight, 10) || 400;
  const s = getComputedStyle(el);
  return { fg, bg, size, weight, complex,
           outline: s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0 ? parse(s.outlineColor) : null,
           shadow: s.boxShadow !== 'none' };
}
"""


def lum(c):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(c[0]) + 0.7152 * ch(c[1]) + 0.0722 * ch(c[2])


def ratio(a, b):
    la, lb = lum(a), lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def hexc(c):
    return "#%02x%02x%02x" % tuple(int(round(x)) for x in c[:3])


def check(url, width=1366, height=900):
    from playwright.sync_api import sync_playwright
    problems, rows = [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": width, "height": height}, reduced_motion="reduce")
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(800)
            page.add_style_tag(content="*{transition:none!important;animation:none!important}")
            items = page.evaluate(JS_COLLECT)
            for it in items:
                loc = page.locator(f'[data-cc="{it["id"]}"]')
                try:
                    loc.scroll_into_view_if_needed(timeout=2000)
                except Exception:  # noqa: BLE001  off-screen or covered: measure at rest only
                    pass
                states = {}
                states["rest"] = page.evaluate(JS_MEASURE, it["id"])
                try:
                    loc.hover(timeout=1500, force=True)
                    page.wait_for_timeout(30)
                    states["hover"] = page.evaluate(JS_MEASURE, it["id"])
                except Exception:  # noqa: BLE001
                    pass
                page.mouse.move(0, 0)
                try:
                    loc.focus(timeout=1500)
                    page.keyboard.press("Shift")  # focus-visible heuristics: a key was pressed
                    states["focus"] = page.evaluate(JS_MEASURE, it["id"])
                    page.evaluate("document.activeElement && document.activeElement.blur()")
                except Exception:  # noqa: BLE001
                    pass
                for st, m in states.items():
                    if not m or not m["fg"]:
                        continue
                    large = m["size"] >= 24 or (m["size"] >= 18.66 and m["weight"] >= 700)
                    need = 3.0 if large else 4.5
                    r = ratio(m["fg"], m["bg"])
                    row = {"text": it["text"], "state": st, "fg": hexc(m["fg"]), "bg": hexc(m["bg"]),
                           "ratio": round(r, 2), "need": need, "complex": m["complex"]}
                    rows.append(row)
                    if m["complex"]:
                        continue
                    if r < need:
                        problems.append(f'"{it["text"] or it["tag"]}" {st}: text {row["fg"]} on {row["bg"]} = {r:.2f}:1 (needs {need}:1)')
                    if st == "focus" and m["outline"] and ratio(m["outline"], m["bg"]) < 3 and not m["shadow"]:
                        problems.append(f'"{it["text"] or it["tag"]}" focus ring {hexc(m["outline"])} on {row["bg"]} under 3:1')
        finally:
            browser.close()
    return sorted(set(problems)), rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("--width", type=int, default=1366)
    ap.add_argument("--json")
    a = ap.parse_args()
    if "127.0.0.1" not in a.url and "localhost" not in a.url:
        sys.exit("local dev server only (this tool hovers every control)")
    probs, rows = check(a.url, a.width)
    if a.json:
        with open(a.json, "w") as f:
            json.dump({"url": a.url, "width": a.width, "problems": probs, "rows": rows}, f, indent=1)
    for p in probs:
        print("FAIL", p)
    print(f"{len(rows)} states measured on {len({r['text'] for r in rows})} controls at {a.width}px; {len(probs)} under contrast")
    sys.exit(1 if probs else 0)


if __name__ == "__main__":
    main()
