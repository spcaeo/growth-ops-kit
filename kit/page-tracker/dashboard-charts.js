'use strict';
/* Charts for the Page Change Tracker: hand-built SVG, no library. Smooth lines with a soft area, light gridlines, no
   borders, small axis labels, provisional days shaded, change days as thin dashed lines with a small label, and one
   hover crosshair whose tooltip lists every series of the chart group for that day (charts drawn together share a
   group). Uses the helpers of dashboard.js (esc, fmtN, pct, shortDay, longDay, state, range, gSum, METRICS). */

const SERIES_COLOR = { readers: 'var(--s-readers)', clicks: 'var(--s-clicks)', impressions: 'var(--s-impressions)', ctr: 'var(--s-ctr)', position: 'var(--s-position)' };
const METRIC_FMT = { readers: fmtN, clicks: fmtN, impressions: fmtN, ctr: v => pct(v), position: v => v == null ? '–' : (+v).toFixed(1) };
const CHARTS = new Map();  // chart id -> what the crosshair needs
let chartSeq = 0;
const compact = n => { const a = Math.abs(n); return a >= 1e6 ? (n / 1e6).toFixed(1).replace(/\.0$/, '') + 'M' : a >= 1e4 ? Math.round(n / 1e3) + 'k' : a >= 1e3 ? (n / 1e3).toFixed(1).replace(/\.0$/, '') + 'k' : String(Math.round(n * 100) / 100); };

/** Forget charts that are no longer on the screen. */
function chartsPrune() { for (const id of CHARTS.keys()) if (!document.getElementById(id)) CHARTS.delete(id); }

function niceTicks(lo, hi, count, int) {
  if (hi === lo) hi = lo + (int ? 1 : Math.abs(lo) * 0.1 || 1);
  const raw = (hi - lo) / count, mag = 10 ** Math.floor(Math.log10(raw)), norm = raw / mag;
  let step = (norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10) * mag;
  if (int) step = Math.max(1, Math.round(step));
  const a = Math.floor(lo / step + 1e-9) * step, b = Math.ceil(hi / step - 1e-9) * step, ticks = [];
  for (let v = a; v <= b + step / 2; v += step) ticks.push(+v.toFixed(10));
  return { lo: a, hi: b, ticks };
}
/** Smooth path through points without overshoot (monotone cubic). */
function smoothPath(pts) {
  const n = pts.length; if (!n) return '';
  if (n < 3) return 'M' + pts.map(p => p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join('L');
  const dx = [], m = [], t = [];
  for (let i = 0; i < n - 1; i++) { dx[i] = pts[i + 1][0] - pts[i][0]; m[i] = (pts[i + 1][1] - pts[i][1]) / (dx[i] || 1); }
  t[0] = m[0]; t[n - 1] = m[n - 2];
  for (let i = 1; i < n - 1; i++) t[i] = m[i - 1] * m[i] <= 0 ? 0 : 3 * (dx[i - 1] + dx[i]) / ((2 * dx[i] + dx[i - 1]) / m[i - 1] + (dx[i] + 2 * dx[i - 1]) / m[i]);
  let d = `M${pts[0][0].toFixed(1)} ${pts[0][1].toFixed(1)}`;
  for (let i = 0; i < n - 1; i++) {
    const h = dx[i] / 3;
    d += `C${(pts[i][0] + h).toFixed(1)} ${(pts[i][1] + t[i] * h).toFixed(1)} ${(pts[i + 1][0] - h).toFixed(1)} ${(pts[i + 1][1] - t[i + 1] * h).toFixed(1)} ${pts[i + 1][0].toFixed(1)} ${pts[i + 1][1].toFixed(1)}`;
  }
  return d;
}

/** points: [{d, v, prov}] for every day (or week, weekly: true) of the range; notes: chartNotes(). Lower-is-better
    measures (position) draw upside down. group: charts with the same group share the crosshair and tooltip. */
function lineChart({ points, width, height = 120, label, valueFmt = fmtN, invert = false, notes = null, color = 'var(--accent)', group, int = false, weekly = false }) {
  height += 14;  // room for the note markers on the x-axis
  const L = 36, R = 8, T = 10, B = 32, w = Math.max(240, Math.floor(width)), iw = w - L - R, ih = height - T - B;
  const vals = points.map(p => p.v).filter(v => v != null);
  if (!vals.length) return `<div class="empty">No ${esc(label.toLowerCase())} in this range.</div>`;
  const nt = niceTicks(invert ? Math.min(...vals) : Math.min(0, ...vals), Math.max(...vals), ih < 80 ? 2 : 3, int);
  const lo = nt.lo, hi = nt.hi;
  const n = points.length, step = n > 1 ? iw / (n - 1) : 0, x = i => L + (n === 1 ? iw / 2 : i * step);
  const y = v => invert ? T + (v - lo) / (hi - lo) * ih : T + ih - (v - lo) / (hi - lo) * ih;
  const id = 'lc' + (++chartSeq), gid = id + 'g';
  CHARTS.set(id, { group: group || id, label, color, fmt: valueFmt, points, L, step, n, y, T, ih, weekly });
  let s = `<svg id="${id}" class="lc" data-group="${esc(group || id)}" width="${w}" height="${height}" viewBox="0 0 ${w} ${height}" role="img" tabindex="0" aria-label="${esc(label)} per day, ${esc(shortDay(points[0].d))} to ${esc(shortDay(points[n - 1].d))}. Hover, or use the arrow keys, for each day's figures.">`;
  s += `<defs><linearGradient id="${gid}" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="${color}" stop-opacity=".22"/><stop offset="1" stop-color="${color}" stop-opacity="0"/></linearGradient></defs>`;
  const pi = points.findIndex(p => p.prov);
  if (pi >= 0) { const x0 = Math.max(L, x(pi) - step / 2); s += `<rect x="${x0}" y="${T}" width="${L + iw - x0}" height="${ih}" fill="var(--prov)"><title>Provisional: Google is still adding to these days</title></rect>${L + iw - x0 > 52 ? `<text x="${L + iw - 2}" y="${T + 9}" text-anchor="end" class="provt">provisional</text>` : ''}`; }
  for (const t of nt.ticks) s += `<line x1="${L}" x2="${L + iw}" y1="${y(t).toFixed(1)}" y2="${y(t).toFixed(1)}" stroke="var(--hair)"/><text x="${L - 6}" y="${(y(t) + 3).toFixed(1)}" text-anchor="end">${esc(valueFmt === METRIC_FMT.ctr ? pct(t, 1) : compact(t))}</text>`;
  const nx = Math.max(2, Math.min(6, Math.floor(iw / 90))), xt = n <= 1 ? [0] : [...new Set(Array.from({ length: nx }, (_, k) => Math.round(k * (n - 1) / (nx - 1))))];
  xt.forEach((i, k) => { s += `<text x="${x(i)}" y="${height - 4}" text-anchor="${k === 0 ? 'start' : k === xt.length - 1 ? 'end' : 'middle'}">${shortDay(points[i].d)}</text>`; });
  let path = '', area = '', run = [];
  const flush = () => {
    if (!run.length) return;
    const d = smoothPath(run); path += d;
    if (!invert) area += `${d}L${run[run.length - 1][0].toFixed(1)} ${T + ih}L${run[0][0].toFixed(1)} ${T + ih}Z`;
    run = [];
  };
  points.forEach((p, i) => { if (p.v == null) flush(); else run.push([x(i), y(p.v)]); }); flush();
  if (area) s += `<path d="${area}" fill="url(#${gid})"/>`;
  s += `<path d="${path}" fill="none" stroke="${color}" stroke-width="1.75" stroke-linejoin="round" stroke-linecap="round"/>`;
  s += notesSVG(notes, points, { x, step, L, T, ih, iw, weekly });
  s += `<line class="xh" x1="0" x2="0" y1="${T}" y2="${T + ih}"/><circle class="hd" r="3.5" cx="-10" cy="-10" fill="var(--surface)" stroke="${color}" stroke-width="2"/>`;
  return s + '</svg>';
}

/** Small multiples: one chart per chosen measure, sharing one crosshair. `readersByDay` is a Map(day -> readers),
    or null when readers do not apply. */
function googleCharts(gs, readersByDay, notes, width) {
  const r = range(), byDay = new Map((gs || []).map(x => [x[0], x]));
  const chosen = state.m.split(','), group = 'g' + (++chartSeq);
  let out = '';
  for (const k of chosen) {
    if (k === 'readers' && !readersByDay) continue;
    const points = r.days.map(d => {
      const g = byDay.get(d), prov = g ? !g[4] : false;
      let v = null;
      if (k === 'readers') v = readersByDay.has(d) ? readersByDay.get(d) : null;
      else if (g) v = k === 'clicks' ? g[1] : k === 'impressions' ? g[2] : k === 'ctr' ? (g[2] ? g[1] / g[2] : null) : (g[2] ? g[3] : null);
      else if ((k === 'clicks' || k === 'impressions') && gs && gs.length && d >= gs[0][0] && d <= gBounds()[1]) v = 0;  // Google sends no row for a day with no impressions
      return { d, v, prov: k === 'readers' ? false : prov };
    });
    const vals = points.map(p => p.v).filter(v => v != null);
    let summary;
    if (k === 'position') { const t = gSum(gs, r.from, r.to); summary = 'average ' + METRIC_FMT.position(t.pos) + ' · lower is better'; }
    else if (k === 'ctr') { const t = gSum(gs, r.from, r.to); summary = 'overall ' + pct(t.ctr); }
    else summary = 'total ' + fmtN(vals.reduce((a, b) => a + b, 0));
    out += `<div class="chart"><div class="chart-h"><b><i style="background:${SERIES_COLOR[k]}"></i>${METRICS[k]}</b><span class="sub">${esc(r.span)} · ${summary}</span></div>${lineChart({ points, width, height: 104, label: METRICS[k], valueFmt: METRIC_FMT[k], invert: k === 'position', notes, color: SERIES_COLOR[k], group, int: !['ctr', 'position'].includes(k) })}</div>`;
  }
  return out ? `<div class="charts">${out}</div>` : '<div class="empty">Pick at least one measure above.</div>';
}
/** The measures as small legend toggles (state in the URL, key m). */
function metricChips(withReaders) {
  const chosen = state.m.split(',');
  return `<div class="bar" role="group" aria-label="Chart measures"><span class="lbl">Show</span>${Object.entries(METRICS).map(([k, v]) => {
    const dis = k === 'readers' && !withReaders;
    return `<button type="button" class="chip" data-metric="${k}" data-fk="metric-${k}" style="--c:${SERIES_COLOR[k]}" aria-pressed="${chosen.includes(k) && !dis}"${dis ? ' disabled title="Readers are per page: open a page"' : ''}><i class="dot" aria-hidden="true"></i>${v}</button>`;
  }).join('')}</div>`;
}
const chartLegend = what => `<div class="legend"><span><i class="sw" style="background:var(--prov);box-shadow:inset 0 0 0 1px var(--flat)"></i>provisional days (Google still counting)</span><span>dashed line = ${what}</span><span>hover a day for every figure</span></div>`;

/** Daily readers as a sparkline (table cells): smooth line, soft area, dashed line at the main change. */
function spark(p, w = 120, h = 28) {
  const ds = p.days; if (!ds.length) return '';
  const vals = ds.map(readersOn), max = Math.max(1, ...vals.filter(v => v != null)), n = ds.length;
  const x = i => n === 1 ? w / 2 : 1 + i * (w - 2) / (n - 1), y = v => h - 2 - v / max * (h - 6);
  let path = '', area = '', run = [];
  const flush = () => { if (run.length) { const d = smoothPath(run); path += d; area += `${d}L${run[run.length - 1][0]} ${h}L${run[0][0]} ${h}Z`; } run = []; };
  vals.forEach((v, i) => { if (v == null) flush(); else run.push([x(i), y(v)]); }); flush();
  const tot = vals.reduce((a, b) => a + (b || 0), 0);
  let s = `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" role="img" aria-label="Daily readers of ${esc(p.slug)}: ${tot} in ${n} days"><title>Readers per day, ${esc(shortDay(ds[0].day))} to ${esc(shortDay(ds[n - 1].day))}: ${tot} in all</title>`;
  if (area) s += `<path d="${area}" fill="var(--accent)" opacity=".12"/><path d="${path}" fill="none" stroke="var(--accent)" stroke-width="1.4" stroke-linejoin="round"/>`;
  if (p.main) { const i = ds.findIndex(d => d.day >= day(p.main)); if (i >= 0) s += `<line x1="${x(i)}" x2="${x(i)}" y1="0" y2="${h}" stroke="var(--fg)" stroke-dasharray="2 2" opacity=".5"/>`; }
  return s + '</svg>';
}

/* ---------- crosshair and tooltip, shared by every line chart ---------- */
const tipEl = () => document.getElementById('tip');
function showDay(svg, i, cx, cy) {
  const me = CHARTS.get(svg.id); if (!me) return;
  i = Math.max(0, Math.min(me.n - 1, i));
  svg._i = i;
  const members = [...document.querySelectorAll(`svg.lc[data-group="${CSS.escape(svg.dataset.group)}"]`)];
  let rows = '';
  for (const el of members) {
    const c = CHARTS.get(el.id); if (!c) continue;
    const p = c.points[i]; if (!p) continue;
    const xx = c.L + (c.n === 1 ? 0 : i * c.step);
    el.classList.add('hot');
    const xh = el.querySelector('.xh'); xh.setAttribute('x1', xx); xh.setAttribute('x2', xx);
    const dot = el.querySelector('.hd');
    if (p.v == null) { dot.setAttribute('cx', -10); dot.setAttribute('cy', -10); } else { dot.setAttribute('cx', xx); dot.setAttribute('cy', c.y(p.v)); }
    rows += `<div><span><i style="background:${c.color}"></i>${esc(c.label)}</span><b>${p.v == null ? 'no data' : esc(c.fmt(p.v))}</b></div>`;
  }
  const p = me.points[i];
  const t = tipEl();
  t.innerHTML = `<b>${esc(me.weekly ? "Week of " + fullDay(p.d) : fullDay(p.d))}</b>${rows}${p.prov ? '<div class="p">provisional: Google still counting</div>' : ''}`;
  t.classList.add('on');
  const r = t.getBoundingClientRect();
  let left = cx + 14, top = cy - r.height - 10;
  if (left + r.width > innerWidth - 8) left = cx - r.width - 14;
  if (left < 8) left = 8;
  if (top < 56) top = cy + 16;
  t.style.left = left + 'px'; t.style.top = top + 'px';
}
function hideDay() {
  document.querySelectorAll('svg.lc.hot').forEach(el => el.classList.remove('hot'));
  const t = tipEl(); if (t) t.classList.remove('on');
}
function idxAt(svg, clientX) {
  const c = CHARTS.get(svg.id), r = svg.getBoundingClientRect();
  if (!c || !r.width) return null;
  const xs = (clientX - r.left) * (svg.viewBox.baseVal.width / r.width);
  return c.n === 1 ? 0 : Math.round((xs - c.L) / c.step);
}
function showNote(g, cx, cy) {
  const t = tipEl(); t.innerHTML = g.dataset.tip; t.classList.add('on');
  document.querySelectorAll('svg.lc.hot').forEach(el => el.classList.remove('hot'));
  const r = t.getBoundingClientRect();
  let left = cx - r.width / 2, top = cy - r.height - 12;
  left = Math.max(8, Math.min(innerWidth - r.width - 8, left)); if (top < 56) top = cy + 16;
  t.style.left = left + 'px'; t.style.top = top + 'px';
}
document.addEventListener('focusin', e => { const g = e.target.closest && e.target.closest('g.mk[data-tip]'); if (g) { const r = g.getBoundingClientRect(); showNote(g, r.left + r.width / 2, r.top); } });
document.addEventListener('pointermove', e => {
  const mk = e.target.closest && e.target.closest('g.mk[data-tip]');
  if (mk) { const r = mk.getBoundingClientRect(); return showNote(mk, r.left + r.width / 2, r.top); }
  const svg = e.target.closest && e.target.closest('svg.lc');
  if (!svg) { if (document.querySelector('svg.lc.hot') && !(document.activeElement && document.activeElement.matches && document.activeElement.matches('svg.lc'))) hideDay(); return; }
  const i = idxAt(svg, e.clientX); if (i != null) showDay(svg, i, e.clientX, e.clientY);
});
document.addEventListener('pointerleave', hideDay);
addEventListener('scroll', () => { if (!(document.activeElement && document.activeElement.matches && document.activeElement.matches('svg.lc'))) hideDay(); }, { passive: true });
document.addEventListener('keydown', e => {
  const svg = e.target.closest && e.target.closest('svg.lc'); if (!svg || !['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) return;
  const c = CHARTS.get(svg.id); if (!c) return;
  e.preventDefault();
  let i = svg._i ?? c.n - 1;
  i = e.key === 'Home' ? 0 : e.key === 'End' ? c.n - 1 : i + (e.key === 'ArrowRight' ? 1 : -1);
  const r = svg.getBoundingClientRect(), scale = r.width / svg.viewBox.baseVal.width;
  showDay(svg, i, r.left + (c.L + Math.max(0, Math.min(c.n - 1, i)) * c.step) * scale, r.top + 20);
});
document.addEventListener('focusout', e => { if (e.target.matches && e.target.matches('svg.lc, g.mk')) hideDay(); });
