'use strict';
/* Google vs Skald cross-check, and time on page (added 13 Nov 2026).
   Cross-check: Google clicks next to Skald's search-engine visits (sources "Search engine", page copies together) and all Skald
   readers, over whole days both have final: the 7 days ending at the older of Google's last final day and Skald's
   newest verified day (so Google's 2-3 provisional days are left out), the 7 days before, and day by day.
   Skald's own 'search' field is NOT search visitors; it is not used anywhere.
   Time on page: Skald's median seconds per day and its rolling summary, root copy (medians cannot be added). */

const GAP_NOTE = 'Google clicks and Skald\'s search visits never match exactly: Skald also counts Bing, DuckDuckGo and other engines; Skald counts days in New York time and Google in Pacific time (3 hours apart, so a few visits land on the next day); Google\'s last 2 to 3 days are provisional, so they are left out of the 7-day windows; some visitors block Skald\'s tracking. A gap is flagged when it is 50% or more with at least 20 visits on the bigger side.';
const gapOf = (g, s) => g ? Math.round(100 * (s - g) / g) : null;
const unusual = (g, s) => { const p = gapOf(g, s); return p != null && Math.abs(p) >= 50 && Math.max(g, s) >= 20; };

/** Skald per day over a set of pages: Map(day -> {se, rd}), verified days only. */
function skaldDays(pages) {
  const m = new Map();
  for (const p of pages) for (const d of p.days) {
    if (d.state !== 'ok') continue;
    const x = m.get(d.day) || { se: 0, rd: 0 }; x.se += d.se || 0; x.rd += d.readers || 0; m.set(d.day, x);
  }
  return m;
}
function crossWindows() {
  const end = minDay(lastFinal(), newestOk());
  return [{ from: addDays(end, -6), to: end }, { from: addDays(end, -13), to: addDays(end, -7) }];
}
/** The block: gs = daily Google rows of the scope, pages = its pages (for Skald), what = "this page" etc. */
function crossCheck(gs, pages, what) {
  const sk = skaldDays(pages), [w1, w0] = crossWindows();
  const sum = w => { let se = 0, rd = 0, n = 0; for (const [d, x] of sk) if (d >= w.from && d <= w.to) { se += x.se; rd += x.rd; n++; } const g = gSum(gs, w.from, w.to); return { g: g.c, se, rd, n, gn: g.n }; };
  const a = sum(w1), b = sum(w0), gp = gapOf(a.g, a.se), flag = unusual(a.g, a.se);
  const gapTxt = (g, s) => { const p = gapOf(g, s); return p == null ? (s ? 'Google 0' : '–') : (p > 0 ? '+' : '') + p + '%'; };
  const cards = `<div class="cards">${card('Google clicks', fmtN(a.g), `before: ${fmtN(b.g)}`)}${card('Skald search visits', fmtN(a.se), `before: ${fmtN(b.se)}`)}
    ${card('Gap, Skald vs Google', gapTxt(a.g, a.se), flag ? '<span class="down">unusually large</span>' : `before: ${gapTxt(b.g, b.se)}`)}${card('Skald readers, all sources', fmtN(a.rd), `before: ${fmtN(b.rd)}`)}</div>`;
  const [, last] = gBounds(), byG = new Map((gs || []).map(r => [r[0], r]));
  let rows = '';
  for (let d = last, i = 0; i < 14; i++, d = addDays(d, -1)) {
    const g = byG.get(d), x = sk.get(d), gc = g ? g[1] : (d >= ((gs || [])[0] || [''])[0] ? 0 : null), prov = g && !g[4];
    rows += `<tr><td class="num">${esc(fullDay(d))}</td><td class="num r">${gc == null ? '–' : fmtN(gc)}${prov ? ' <span class="kind">provisional</span>' : ''}</td><td class="num r">${x ? fmtN(x.se) : '<span class="na">not verified</span>'}</td><td class="num r">${x ? fmtN(x.rd) : '–'}</td><td class="num r">${x && gc != null && !prov ? gapTxt(gc, x.se) : '–'}</td></tr>`;
  }
  return `<h2 class="sec">Google vs Skald: do the visits add up?</h2>
    <p class="sub">${esc(what)}, ${esc(spanText(w1.from, w1.to))} (7 whole days both have final; "before" = ${esc(spanText(w0.from, w0.to))}).${flag ? ' <b class="down">The gap is unusually large: check the page in Skald and Search Console.</b>' : ''}</p>
    ${cards}
    <div class="box"><table><thead><tr><th>Day</th><th class="r">Google clicks</th><th class="r">Skald search visits</th><th class="r">Skald readers</th><th class="r">Gap</th></tr></thead><tbody>${rows}</tbody></table></div>
    <p class="rules">${esc(GAP_NOTE)}</p>`;
}

/* ---------- time on page ---------- */
const secs = v => v == null ? '–' : v < 90 ? Math.round(v) + ' s' : (v / 60).toFixed(1) + ' min';
function medianOf(xs) { xs = xs.filter(x => x != null).sort((a, b) => a - b); if (!xs.length) return null; const m = xs.length >> 1; return xs.length % 2 ? xs[m] : (xs[m - 1] + xs[m]) / 2; }
/** Skald's latest rolling time on page for a page, as one short line. */
function topLine(p) {
  const w = p.top && p.top.window;
  if (!w) return '<span class="na">not measured yet</span>';
  if (w.median_s == null) return `<span class="na">too few measured (${w.measured || 0} of ${w.min_measured || '?'} needed)</span>`;
  return `${secs(w.median_s)} <span class="kind">median · ${w.measured} measured · ${w.days} days</span>`;
}
/** Median of the daily medians between two days, and the visits measured (root copy). */
function topBetween(p, from, to) {
  const ds = ((p.top && p.top.days) || []).filter(r => r[0] >= from && r[0] <= to);
  return { med: medianOf(ds.map(r => r[1])), measured: ds.reduce((s, r) => s + (r[2] || 0), 0), days: ds.filter(r => r[1] != null).length };
}
/** A row for the Impact table: time on page before vs after (no verdict rule yet, so no verdict). */
function topRow(p, win) {
  if (!win) return '';
  const b = topBetween(p, win.bFrom, win.bTo), a = topBetween(p, win.aFrom, win.aTo);
  return `<tr><td>Time on page (median of daily medians)</td><td class="num r">${secs(b.med)}<div class="kind">${b.measured} measured</div></td><td class="num r">${secs(a.med)}<div class="kind">${a.measured} measured</div></td><td class="num r">${b.med != null && a.med != null ? (a.med - b.med > 0 ? '+' : '') + Math.round(a.med - b.med) + ' s' : '–'}</td><td><span class="na">shown, not judged</span></td><td class="hide-sm sub">${b.days + a.days ? `${b.days} and ${a.days} days with a median` : 'no day has enough measured visits yet'}</td></tr>`;
}
/** A cluster's time on page: the median of its pages' rolling medians. */
function clusterTop(ps) {
  const ws = ps.map(p => p.top && p.top.window).filter(w => w && w.median_s != null);
  if (!ws.length) return '<span class="na">too few measured</span>';
  return `${secs(medianOf(ws.map(w => w.median_s)))} <span class="kind">median of ${ws.length} pages · ${ws.reduce((s, w) => s + (w.measured || 0), 0)} measured</span>`;
}
