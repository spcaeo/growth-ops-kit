#!/usr/bin/env python3
"""Contrast in every state (rule 36j). From a real project, on a button with dark text on orange that went darker on
hover: "As a rule, remember the contrast and the mouse-over effect. The growth pack should completely understand what
is a background colour, what is a foreground colour and what kind of mouse-over effect. I should never speak about
this again; it should take care of it automatically."

  growth contrast_check <local URL> [--width 1366 [--width 390]] [--json out.json] [--no-cache] [--no-dedupe]

For every visible link, button and control on the page (header, main, footer, dialogs that are open) it reads, in a
real headless browser, the text colour and the colour actually painted behind the text (walking up through
transparent parents, compositing semi-transparent layers) in three states: at rest, hovered and keyboard-focused.
It fails any state under WCAG AA: 4.5:1 for normal text, 3:1 for large text (24px+, or 18.66px+ bold), and 3:1 for
the focus ring against the background it sits on. Gradients and images behind text are reported as "check by eye".
Exit 1 on any failure. Never run it against the live site (it moves the mouse; use the local dev server).

Speed without weaker checks (2.8.0). A page repeats its controls: the header menu, the footer links and the pills look the
same on every page. So:
  - one browser per run covers every width (a fresh page per width, so nothing leaks from one width to the next);
  - controls with the same signature are measured once. The signature is what the page's CSS can tell apart: the control's
    tag, class, style attribute, role / type / disabled / aria-current / -expanded / -pressed / -selected, first or last
    child and text-bearing child; for every ancestor its tag, class, style attribute and data-* attributes; and which of
    the page's attribute selectors, ids and position or sibling selectors (:nth-child, :has, + and ~) apply to each of
    them. The colours read at rest are part of it too, so two controls that look different at rest never share a
    measurement. Every control still gets its own rows, and a failing signature names every control that has it;
  - a hover that did not take (the mouse missed the control, or something covers it) is retried at each line of the control
    and then on the next control of the group, and the hover is let go before focus is read;
  - each measurement is kept under <project>/.cache/contrast/, keyed by sha256(signature + colours at rest + width + a hash
    of the page's CSS and JavaScript (every stylesheet, linked, inline or imported) + browser version + this tool's own code). Any CSS change
    gives new keys. Only a measurement where :hover really applied and focus was read is kept.
    `--no-cache` skips it, `--no-dedupe` measures every control (the old way), growth.json "contrast_cache": false
    switches the cache off for the gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

CACHE_VERSION = 1          # bump when the cache entry format changes
WIDTHS = (1366, 390)

# The page's CSS: every stylesheet's text (linked, inline, @import-ed, adopted), plus the "probes": the selectors whose answer
# a class list cannot give (an attribute selector, a position among siblings, a + or ~ combinator, :has). Each probe is asked
# of the page once (querySelectorAll), so a control's signature holds which of them apply to it and to each ancestor.
JS_CSS = r"""
async () => {
  const probes = new Set();
  const STRUCT = /:(nth-|first-child|last-child|only-|first-of-type|last-of-type|empty\b|has\()|[+~]/;
  const note = (sel) => {
    for (const m of sel.matchAll(/(?<!\\)\[[^\]\\]+\]/g)) probes.add(m[0]);
    if (STRUCT.test(sel.replace(/\\./g, '').replace(/\[[^\]]*\]/g, '[]'))) {
      // ask it the way it applies at rest: a state that needs the mouse or the keyboard is treated as always true, pseudo-elements are dropped
      probes.add(sel.replace(/:(hover|active|focus-visible|focus-within|focus)\b/g, ':not(.__none__)')
                    .replace(/::[\w-]+(\([^)]*\))?|:(before|after|first-line|first-letter)\b/g, ''));
    }
  };
  const scan = (rules) => {
    for (const r of rules) {
      if (r.selectorText) note(r.selectorText);
      if (r.styleSheet) { try { scan(r.styleSheet.cssRules); } catch (e) { /* cross-origin */ } }
      if (r.cssRules) scan(r.cssRules);
    }
  };
  const dump = (rules) => {
    let out = '';
    for (const r of rules) {
      if (r.styleSheet) { try { out += '@import{' + dump(r.styleSheet.cssRules) + '}'; continue; } catch (e) { /* cross-origin */ } }
      out += r.cssText + '\n';
    }
    return out;
  };
  const texts = [];
  const unreadable = [];
  for (const s of [...document.styleSheets, ...(document.adoptedStyleSheets || [])]) {
    let body = '';
    try {
      const rules = s.cssRules;
      body = dump(rules);
      scan(rules);
    } catch (e) {                                  // a cross-origin sheet (web fonts): read its text the way the page did
      try {
        const ac = new AbortController();
        setTimeout(() => ac.abort(), 4000);
        body = await (await fetch(s.href, { signal: ac.signal })).text();
        for (const m of body.matchAll(/([^{}]+)\{/g)) note(m[1]);
      } catch (e2) { body = 'unreadable ' + (s.href || ''); unreadable.push(s.href || '(sheet)'); }
    }
    texts.push(((s.media && s.media.mediaText) || '') + (s.disabled ? ' disabled' : '') + '\n' + body);
  }
  const ids = new Set();
  for (const t of texts) for (const m of t.matchAll(/#(-?[_a-zA-Z][\w-]*)/g)) ids.add(m[1]);
  // the page's JavaScript is part of what can change a state (a class added on mouseenter or focus): inline text, and each
  // external script's source read the way the page got it
  const js = [];
  for (const sc of document.scripts) {
    if (!sc.src) { js.push('inline\n' + sc.text); continue; }
    try {
      const ac = new AbortController();
      setTimeout(() => ac.abort(), 4000);
      const resp = await fetch(sc.src, { signal: ac.signal });
      js.push(sc.src + '\n' + await resp.text());
    } catch (e) { js.push('unreadable ' + sc.src); unreadable.push(sc.src); }
  }
  const all = [...probes].sort();
  return { text: texts.join('\n/*sheet*/\n'), js: js.join('\n/*script*/\n'), unreadable, probes: all.slice(0, 4000), probeTotal: all.length, ids: [...ids].sort() };
}
"""

JS_COLLECT = r"""
({ probes, ids }) => {
  const sel = 'a[href], button, [role=button], [role=tab], [role=radio], [role=switch], summary, input[type=submit], input[type=button]';
  const idSet = new Set(ids);
  const hits = new Map();                            // element -> the probes that apply to it
  probes.forEach((p, i) => {
    try { for (const e of document.querySelectorAll(p)) { const a = hits.get(e); if (a) a.push(i); else hits.set(e, [i]); } } catch (e) { /* not a selector */ }
  });
  const tagCls = (n) => n.tagName.toLowerCase() + '.' + (n.getAttribute('class') || '');
  // what the page's CSS can tell one element from another: tag, class, style attribute, the ids and probes the CSS uses.
  // A control also says whether it is the first or last child; an ancestor also gives its data-* attributes.
  const look = (n, isControl) => {
    const data = [];
    if (!isControl) for (const a of n.attributes) if (a.name.startsWith('data-') && a.name !== 'data-cc') data.push(a.name + '=' + a.value);
    return [tagCls(n), n.getAttribute('style') || '', data.sort().join(';'), n.id && idSet.has(n.id) ? '#' + n.id : '', (hits.get(n) || []).join(','),
            isControl ? (n.previousElementSibling ? '' : 'first') + (n.nextElementSibling ? '' : 'last') : ''].join('|');
  };
  const memo = new Map();
  const chain = (n) => {                             // an ancestor and everything above it, up to <html>
    if (!n || n.nodeType !== 1) return '';
    let v = memo.get(n);
    if (v === undefined) { v = look(n, false) + '<' + chain(n.parentElement); memo.set(n, v); }
    return v;
  };
  const hasText = (n) => [...n.childNodes].some((x) => x.nodeType === 3 && x.textContent.trim());
  const hiddenKid = (c) => { if (c.closest('[aria-hidden=true]')) return true; const r = c.getBoundingClientRect(); const k = getComputedStyle(c); return r.width <= 1 || r.height <= 1 || k.clip === 'rect(0px, 0px, 0px, 0px)'; };
  const textPath = (el) => {                         // from the control down to the child whose colour is read (same rule as the measure)
    if (hasText(el)) return '';
    for (const c of el.querySelectorAll('*')) {
      if (hasText(c) && !hiddenKid(c)) { const path = []; for (let n = c; n && n !== el; n = n.parentElement) path.push(look(n, true)); return path.join('<'); }
    }
    return '';
  };
  const out = [];
  document.querySelectorAll(sel).forEach((el, i) => {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    if (r.width < 4 || r.height < 4 || cs.visibility === 'hidden' || cs.display === 'none' || +cs.opacity === 0) return;
    if (el.closest('[aria-hidden=true], [hidden], [inert]')) return;
    const text = (el.innerText || el.getAttribute('aria-label') || '').trim().replace(/\s+/g, ' ').slice(0, 60);
    el.setAttribute('data-cc', String(i));
    const own = ['role', 'type', 'aria-current', 'aria-expanded', 'aria-pressed', 'aria-selected'].map((a) => a + '=' + (el.getAttribute(a) || '')).join(';') + ';disabled=' + el.hasAttribute('disabled');
    const sig = [look(el, true), own, textPath(el), chain(el.parentElement)].join('\n');
    out.push({ id: String(i), text, tag: el.tagName.toLowerCase(), cls: (el.className && el.className.baseVal === undefined ? el.className : '').toString().slice(0, 60), sig });
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
  // text colour: the link's OWN text when it has any ("Move <b>offer</b>" reads the link's colour, not the <b>'s), else its first
  // visible text-bearing child (a label inside an icon button); screen-reader-only and aria-hidden children are skipped
  const hasText = (n) => [...n.childNodes].some((x) => x.nodeType === 3 && x.textContent.trim());
  const hiddenKid = (c) => { if (c.closest('[aria-hidden=true]')) return true; const r = c.getBoundingClientRect(); const k = getComputedStyle(c); return r.width <= 1 || r.height <= 1 || k.clip === 'rect(0px, 0px, 0px, 0px)'; };
  let textEl = el;
  if (!hasText(el)) { for (const c of el.querySelectorAll('*')) { if (hasText(c) && !hiddenKid(c)) { textEl = c; break; } } }
  const tcs = getComputedStyle(textEl);
  let fg = parse(tcs.color);
  // background: walk up from `start`, collecting layers until an opaque one
  const paint = (start, own) => {
    const layers = [];
    let complex = false;
    for (let n = start; n && n.nodeType === 1; n = n.parentElement) {
      const s = getComputedStyle(n);
      if (s.backgroundImage && s.backgroundImage !== 'none' && !/^url\(.*\.svg/.test(s.backgroundImage)) {
        if (/gradient|url\(/.test(s.backgroundImage) && n === own) complex = true;
      }
      const b = parse(s.backgroundColor);
      if (b && b[3] > 0) { layers.push(b); if (b[3] >= 1) break; }
    }
    let bg = [255, 255, 255, 1];
    for (let k = layers.length - 1; k >= 0; k--) bg = layers[k][3] >= 1 ? layers[k] : over(layers[k], bg);
    return { bg, complex };
  };
  const own = paint(el, el);
  const bg = own.bg, complex = own.complex;
  const outerBg = paint(el.parentElement, null).bg;   // what is painted OUTSIDE the element: where a focus ring sits
  if (fg && fg[3] < 1) fg = over(fg, bg);
  const size = parseFloat(tcs.fontSize), weight = parseInt(tcs.fontWeight, 10) || 400;
  const s = getComputedStyle(el);
  return { fg, bg, outerBg, size, weight, complex, offset: parseFloat(s.outlineOffset) || 0,
           outline: s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0 ? parse(s.outlineColor) : null,
           shadow: s.boxShadow !== 'none' };
}
"""


# The same measure for a list of ids in one call (the rest state, before anything is scrolled or hovered).
JS_MEASURE_ALL = "(ids) => { const m = " + JS_MEASURE + "; return ids.map((id) => m(id)); }"
# This tool's own measuring code is part of every cache key: change it and the old entries are simply not found.
CODE_HASH = hashlib.sha256((JS_CSS + JS_COLLECT + JS_MEASURE).encode()).hexdigest()[:16]


PROBE_LIMIT = 4000


def _page_hash(css):
    """One hash for what can change a control's look: the page's CSS and its JavaScript (inline and external)."""
    return hashlib.sha256((css["text"] + "\0js\0" + css["js"]).encode("utf-8", "replace")).hexdigest()


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


def ring_ratio(m):
    """(ratio, colour it sits on) of a focus ring. The ring is drawn outside the element (outline-offset 0 or more), so it is
    compared with the colour painted outside the element, never with the button's own fill. A ring pulled inside (a negative
    offset) sits on the element's fill."""
    on = m["bg"] if m.get("offset", 0) < 0 else m.get("outerBg") or m["bg"]
    return ratio(m["outline"], on), on


STATES = ("rest", "hover", "focus")


class Cache:
    """The measurements kept between pages and runs: one small file per key under <project>/.cache/contrast/<2 hex>/<key>.json.
    A file is written in one step (tools/atomic.py), so a reader never sees half of one and parallel runs never clash.
    The folder keeps itself out of git (a .gitignore holding *), and an entry nobody used for 30 days is removed."""
    KEEP_DAYS = 30

    def __init__(self, root):
        self.root = Path(root)
        self.wrote = False

    def _path(self, key):
        return self.root / key[:2] / f"{key}.json"

    def get(self, key):
        path = self._path(key)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(data, dict) or data.get("v") != CACHE_VERSION or not isinstance(data.get("states"), dict):
            return None
        try:
            os.utime(path)                      # used today: keeps it out of the 30-day clean-up
        except OSError:
            pass
        return data["states"]

    def put(self, key, states):
        from atomic import write_json
        try:
            write_json(self._path(key), {"v": CACHE_VERSION, "states": states}, indent=None)
            gi = self.root / ".gitignore"
            if not gi.exists():
                from atomic import write_text
                write_text(gi, "*\n")
            self.wrote = True
        except OSError:
            pass                                # a cache that cannot be written is only slower, never wrong

    def prune(self):
        """Remove entries nobody used for KEEP_DAYS (at most once a day)."""
        marker = self.root / ".pruned"
        now = time.time()
        try:
            if now - marker.stat().st_mtime < 86400:
                return
        except OSError:
            pass
        cut = now - self.KEEP_DAYS * 86400
        try:
            for shard in self.root.iterdir():
                if not shard.is_dir():
                    continue
                for f in shard.iterdir():
                    try:
                        if f.suffix == ".json" and f.stat().st_mtime < cut:
                            f.unlink()
                    except OSError:
                        pass
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.touch()
        except OSError:
            pass


def _key(sig, rest, width, css_hash, browser_version):
    """sha256 of the control's signature, its colours at rest, the width, the page's CSS, the browser and this tool's code."""
    raw = "\0".join([str(CACHE_VERSION), CODE_HASH, browser_version, str(width), css_hash, sig, json.dumps(rest, sort_keys=True)])
    return hashlib.sha256(raw.encode()).hexdigest()


IS_HOVER = "(id) => { const e = document.querySelector(`[data-cc=\"${id}\"]`); return !!e && e.matches(':hover'); }"
NOT_HOVER = "(id) => { const e = document.querySelector(`[data-cc=\"${id}\"]`); return !e || !e.matches(':hover'); }"
# the middle of each line box of a control (a link wrapped over two lines has a box whose middle can fall between its words)
LINE_POINTS = ("(id) => { const e = document.querySelector(`[data-cc=\"${id}\"]`); if (!e) return []; "
               "return [...e.getClientRects()].filter((r) => r.width > 1 && r.height > 1).map((r) => [r.x + r.width / 2, r.y + r.height / 2])"
               ".filter(([x, y]) => x >= 0 && y >= 0 && x < innerWidth && y < innerHeight); }")
TRIES = 4        # a look-alike group lends up to this many controls to one state that did not take on the first


# The same scroll Playwright's scroll_into_view_if_needed makes (the browser's own scrollIntoViewIfNeeded, centred), without its
# 15 to 20 ms of round trips per control: the page ends up at the same scroll position (checked on real pages).
SCROLL = "(id) => { const e = document.querySelector(`[data-cc=\"${id}\"]`); if (!e || !e.scrollIntoViewIfNeeded) return false; e.scrollIntoViewIfNeeded(true); return true; }"


def _scroll(page, it):
    try:
        if page.evaluate(SCROLL, it["id"]):
            return
        page.locator(f'[data-cc="{it["id"]}"]').scroll_into_view_if_needed(timeout=2000)
    except Exception:  # noqa: BLE001  off-screen or covered: measure at rest only
        pass


CENTRE = "(id) => { const e = document.querySelector(`[data-cc=\"${id}\"]`); if (e) e.scrollIntoView({ block: 'center', inline: 'nearest' }); }"


def _hover(page, it):
    """Hover one control and say whether :hover really applies to it. The mouse can miss: over the middle of a link wrapped
    onto two lines, or where a sticky bar covers the control. Then it is pointed at each line of the control, and last the
    control is brought to the middle of the screen, away from sticky bars, and tried again."""
    loc = page.locator(f'[data-cc="{it["id"]}"]')

    def took():
        page.wait_for_timeout(30)
        return page.evaluate(IS_HOVER, it["id"])

    loc.hover(timeout=1500, force=True)
    if took():
        return True
    for centred in (False, True):
        if centred:
            page.evaluate(CENTRE, it["id"])
            page.mouse.move(0, 0)
            loc.hover(timeout=1500, force=True)
            if took():
                return True
        for x, y in page.evaluate(LINE_POINTS, it["id"])[:3]:
            page.mouse.move(x, y)
            if took():
                return True
    return False


def _measure_states(page, members):
    """Read one look-alike group at rest, hovered and keyboard-focused (a group of one is just a control). The states that
    exist: a control that cannot be hovered or focused has no row for that state. A hover that did not take (the mouse missed
    the control) or a focus that failed is tried on the next control of the group. Returns (states, reliable): reliable only
    when :hover really applied and the focus was read, and only a reliable measurement is kept for later runs (a control that
    something covers today may not be covered tomorrow, with the same CSS)."""
    first = members[0]
    _scroll(page, first)
    states = {"rest": page.evaluate(JS_MEASURE, first["id"])}
    hovered, fallback, took = first, None, False
    for m in members[:TRIES]:
        try:
            if m is not first:
                _scroll(page, m)
            applied = _hover(page, m)
            got = page.evaluate(JS_MEASURE, m["id"])
        except Exception:  # noqa: BLE001
            continue
        hovered = m
        if applied:
            states["hover"] = got
            fallback, took = None, True
            break
        if fallback is None:
            fallback = got
    if fallback is not None:
        states["hover"] = fallback          # no control could be reached by the mouse: what was measured, as before
    page.mouse.move(0, 0)
    try:                                    # let the hover go before the focus is read, so focus never shows a leftover hover
        page.wait_for_function(NOT_HOVER, arg=hovered["id"], timeout=400)
    except Exception:  # noqa: BLE001
        pass
    for m in members[:TRIES]:
        try:
            page.locator(f'[data-cc="{m["id"]}"]').focus(timeout=1500)
            page.keyboard.press("Shift")  # focus-visible heuristics: a key was pressed
            states["focus"] = page.evaluate(JS_MEASURE, m["id"])
            page.evaluate("document.activeElement && document.activeElement.blur()")
            break
        except Exception:  # noqa: BLE001
            continue
    return states, took and "focus" in states


def _judge(it, states, problems, rows):
    """The verdict on one control's measured states: its rows, and a problem line for each state under AA (naming the control)."""
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
        ring = ring_ratio(m) if st == "focus" and m["outline"] and not m["shadow"] else None
        if ring is not None and ring[0] < 3:
            problems.append(f'"{it["text"] or it["tag"]}" focus ring {hexc(m["outline"])} on {hexc(ring[1])} under 3:1')


def _page_width(browser, url, width, height, cache, dedupe, stats):
    """One width, in a fresh page of the shared browser. Returns (problems, rows)."""
    ctx = browser.new_context(viewport={"width": width, "height": height}, reduced_motion="reduce")
    try:
        page = ctx.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(800)
        page.add_style_tag(content="*{transition:none!important;animation:none!important}")
        css = page.evaluate(JS_CSS)
        css_hash = _page_hash(css)
        if css["unreadable"]:
            # a sheet or script we cannot read could change without the key changing: measure live, keep nothing
            print(f"contrast_check: cannot read {len(css['unreadable'])} stylesheet/script file(s) (e.g. {css['unreadable'][0]}); "
                  "measuring live, cache off for this page", file=sys.stderr)
            cache = None
        if css["probeTotal"] > PROBE_LIMIT:
            print(f"contrast_check: {css['probeTotal']} selector probes (limit {PROBE_LIMIT}); grouping of look-alike controls is off for this page",
                  file=sys.stderr)
            dedupe = False
        items = page.evaluate(JS_COLLECT, {"probes": css["probes"], "ids": css["ids"]})
        rest = page.evaluate(JS_MEASURE_ALL, [it["id"] for it in items]) if items else []
        groups, order = {}, []
        for n, (it, r0) in enumerate(zip(items, rest)):
            # without dedupe every control is its own group and nothing is cached: exactly the old way
            key = _key(it["sig"], r0, width, css_hash, browser.version) if dedupe else f"solo-{n}"
            if key not in groups:
                groups[key] = []
                order.append(key)
            groups[key].append(it)
        measured, keep = {}, []
        for key in order:
            states = cache.get(key) if (cache and dedupe) else None
            if states is None:
                states, reliable = _measure_states(page, groups[key])
                stats["measured"] += 1
                if not reliable:
                    stats["unsure"] += 1
                if cache and dedupe and reliable:
                    keep.append((key, states))
            else:
                stats["cached"] += 1
            measured[key] = states
        # keep the new measurements only if the page's CSS is still what it was when the keys were made (a sheet that finished
        # loading half way through would give a key that does not match what was measured)
        if keep and _page_hash(page.evaluate(JS_CSS)) == css_hash:
            for key, states in keep:
                cache.put(key, states)
        stats["controls"] += len(items)
        stats["groups"] += len(order)
        problems, rows = [], []
        by_id = {}
        for key in order:
            for it in groups[key]:
                by_id[it["id"]] = measured[key]
        for it in items:
            _judge(it, by_id[it["id"]], problems, rows)
        return sorted(set(problems)), rows
    finally:
        ctx.close()


def check_widths(url, widths=WIDTHS, height=900, cache_dir=None, dedupe=True, stats=None):
    """Measure the page at every width in ONE browser: {width: (problems, rows)}.
    cache_dir: where measurements are kept between pages and runs (None = no cache). dedupe=False measures every control
    itself (and keeps nothing). `stats`, when given, is filled in: controls, groups, measured, cached, unsure (groups whose hover or focus could not be read, never kept)."""
    from playwright.sync_api import sync_playwright
    st = stats if stats is not None else {}
    for k in ("controls", "groups", "measured", "cached", "unsure"):
        st.setdefault(k, 0)
    cache = Cache(cache_dir) if cache_dir else None
    out = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for w in widths:
                out[w] = _page_width(browser, url, w, height, cache, dedupe, st)
        finally:
            browser.close()
    if cache and cache.wrote:
        cache.prune()
    return out


def check(url, width=1366, height=900, cache_dir=None, dedupe=True, stats=None):
    """One width: (problems, rows). The same as check_widths for a single width."""
    return check_widths(url, (width,), height, cache_dir, dedupe, stats)[width]


def cache_dir_for(project, cfg=None):
    """<project>/.cache/contrast, or None when growth.json switches the cache off ("contrast_cache": false)."""
    if cfg is not None and cfg.get("contrast_cache") is False:
        return None
    return Path(project) / ".cache" / "contrast"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("--width", type=int, action="append", help="a viewport width; repeat it for more (default 1366). One browser covers all")
    ap.add_argument("--json")
    ap.add_argument("--no-cache", action="store_true", help="do not read or write the kept measurements (.cache/contrast)")
    ap.add_argument("--no-dedupe", action="store_true", help="measure every control itself (the slow, old way; keeps nothing)")
    a = ap.parse_args()
    if "127.0.0.1" not in a.url and "localhost" not in a.url:
        sys.exit("local dev server only (this tool hovers every control)")
    widths = a.width or [1366]
    cache_dir = None
    if not a.no_cache and not a.no_dedupe:
        try:
            from config import find_project, load_cfg
            proj = find_project()
            cache_dir = cache_dir_for(proj, load_cfg(proj)) if proj else None
        except Exception:  # noqa: BLE001  no project here: no cache
            cache_dir = None
    stats = {}
    res = check_widths(a.url, widths, cache_dir=cache_dir, dedupe=not a.no_dedupe, stats=stats)
    if a.json:
        first = widths[0]
        doc = {"url": a.url, "width": first, "problems": res[first][0], "rows": res[first][1]}
        if len(widths) > 1:
            doc["widths"] = list(widths)
            doc["by_width"] = {str(w): {"problems": res[w][0], "rows": res[w][1]} for w in widths}
        with open(a.json, "w") as f:
            json.dump(doc, f, indent=1)
    n = 0
    for w in widths:
        probs, rows = res[w]
        for p in probs:
            print("FAIL", p if len(widths) == 1 else f"{w}px {p}")
        print(f"{len(rows)} states measured on {len({r['text'] for r in rows})} controls at {w}px; {len(probs)} under contrast")
        n += len(probs)
    print(f"({stats['controls']} controls in {stats['groups']} look-alike groups: {stats['measured']} measured now, {stats['cached']} kept from before"
          + (f"; {stats['unsure']} could not be hovered or focused, so they are not kept" if stats["unsure"] else "") + ")")
    sys.exit(1 if n else 0)


if __name__ == "__main__":
    main()
