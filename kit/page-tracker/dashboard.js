'use strict';
/* Page Change Tracker dashboard: helpers, the URL router, the shared copy component, the Pages and Google views.
   Every state lives in the address bar (README.md, "URL parameters"): one state object <-> query string; user actions
   pushState, typing replaceState; parsed on load and on Back/Forward. Other files: dashboard-charts.js (charts and
   chart notes), dashboard-page.js (the page screen), dashboard-impact.js (Impact tab, verdicts), insights.js. */
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
let SITE = '';  // the site's address, set from data.json (growth.json: site_url)
let TZ_NAME = 'UTC';  // set from data.json (growth.json: timezone)
const fmt = n => n == null ? '–' : (Math.round(n * 10) / 10).toString();
const fmtN = n => n == null ? '–' : Math.round(n).toLocaleString('en-CA');
const pct = (n, d = 2) => n == null ? '–' : (n * 100).toFixed(d) + '%';
const day = s => s.slice(0, 10);

/* ---------- router ---------- */
const KINDS = ['all', 'hub', 'post', 'feature', 'page'];  // hub = a topic hub page, post = blog post, feature = other page inside a topic
const SORTS = ['slug', 'live', 'impact', 'before', 'after', 'trend', 'bounce', 'gsc', 'search', 'google'];
const RANGES = { '7d': '7 days', '28d': '28 days', '90d': '90 days', '6m': '6 months', custom: 'Custom' };
const TABS = { impact: 'Impact', readers: 'Readers', google: 'Google', changes: 'Changes', milestones: 'Milestones' };
const METRICS = { readers: 'Readers', clicks: 'Clicks', impressions: 'Impressions', ctr: 'CTR', position: 'Avg position' };
const ANNS = { ours: 'Our changes', core: 'Core updates', spam: 'Spam updates', other: 'Other Google updates' };
const VIEWS = ['insights', 'clusters', 'pages', 'google'];
const VIEW_NAMES = { insights: 'Insights', clusters: 'Clusters', pages: 'Pages', google: 'Google' };
const DEFAULTS = { view: 'insights', cluster: '', cl: '', kind: 'all', country: '', q: '', sort: 'live', dir: 'desc', range: '28d', from: '', to: '',
  m: 'readers,clicks,impressions,position', ann: 'ours,core,spam,other', page: '', tab: 'impact', diff: '', win: '7', about: '', theme: 'light' };
const isDay = s => /^\d{4}-\d{2}-\d{2}$/.test(s) && !isNaN(Date.parse(s + 'T00:00:00Z'));
let DATA, state, AI = null, COUNTRIES = new Set(), NO_DATA = false;  // NO_DATA: no readers and no Google figures yet, so every verdict is 'too early'

function normalise(s) {
  const o = { ...DEFAULTS };
  for (const k of Object.keys(DEFAULTS)) if (typeof s[k] === 'string') o[k] = s[k];
  if (!VIEWS.includes(o.view)) o.view = DEFAULTS.view;
  if (!KINDS.includes(o.kind)) o.kind = 'all';
  const cids = DATA ? (DATA.clusters || []).map(c => c.id) : null;
  if (o.cl && cids && !cids.includes(o.cl)) o.cl = '';
  if (o.cluster && cids && !cids.includes(o.cluster)) o.cluster = '';
  if (o.view !== 'clusters') o.cluster = '';
  if (o.country && DATA && !COUNTRIES.has(o.country)) o.country = '';
  o.q = o.q.slice(0, 100);
  if (!SORTS.includes(o.sort)) o.sort = DEFAULTS.sort;
  if (!['asc', 'desc'].includes(o.dir)) o.dir = 'desc';
  if (!(o.range in RANGES)) o.range = DEFAULTS.range;
  if ((o.from || o.to) && o.range !== 'custom' && s.range == null) o.range = 'custom';
  if (o.range === 'custom') {
    const [first, last] = gBounds();
    let f = isDay(o.from) ? o.from : '', t = isDay(o.to) ? o.to : '';
    if (!f && !t) { o.range = DEFAULTS.range; f = t = ''; }
    else {
      f = f || first; t = t || last;
      if (first) { const clamp = d => d < first ? first : d > last ? last : d; f = clamp(f); t = clamp(t); }
      if (f > t) [f, t] = [t, f];
    }
    o.from = f; o.to = t;
  } else { o.from = ''; o.to = ''; }
  const ms = o.m.split(',').filter(x => x in METRICS);
  o.m = Object.keys(METRICS).filter(x => ms.includes(x)).join(',') || DEFAULTS.m;
  const an = o.ann.split(',').filter(x => x in ANNS);
  o.ann = an.length ? Object.keys(ANNS).filter(x => an.includes(x)).join(',') : o.ann === 'none' ? 'none' : DEFAULTS.ann;
  if (o.page && DATA && !DATA.pages.some(p => p.path === o.page)) o.page = '';
  if (!(o.tab in TABS) || !o.page) o.tab = 'impact';
  o.diff = o.tab === 'changes' ? [...new Set(o.diff.split(',').filter(x => /^[0-9a-f]{7,40}$/.test(x)))].slice(0, 20).join(',') : '';
  if (!['7', '14'].includes(o.win)) o.win = '7';
  o.about = o.about === '1' ? '1' : '';
  if (!['light', 'dark'].includes(o.theme)) o.theme = 'light';
  return o;
}
function readURL() { const u = new URLSearchParams(location.search); const s = {}; for (const [k, v] of u) if (k in DEFAULTS) s[k] = v; return normalise(s); }
function urlFor(s) {
  const u = new URLSearchParams();
  for (const k of Object.keys(DEFAULTS)) if (s[k] !== DEFAULTS[k] && s[k] !== '') u.set(k, s[k]);
  if (s.range === 'custom') u.delete('range');  // from/to say it already
  for (const [k, v] of new URLSearchParams(location.search)) if (k.startsWith('ins_')) u.set(k, v);  // the Insights view's own keys (insights.js)
  const q = u.toString().replace(/%2C/g, ',').replace(/%2F/g, '/');
  return location.pathname + (q ? '?' + q : '');
}
const hrefFor = patch => urlFor(normalise({ ...state, ...patch }));
/* Where each list was scrolled to when a page was opened from it, so going back lands on the same row. */
const SCROLL = {};
function settleScroll(prev, next, saved) {
  if (next.page && (!prev.page || prev.page !== next.page)) scrollTo(0, 0);
  else if (prev.page && !next.page) scrollTo(0, saved ?? SCROLL[next.view + next.cluster] ?? 0);
  else if (!next.page && (prev.view !== next.view || prev.cluster !== next.cluster)) scrollTo(0, saved ?? 0);
  else if (next.page && prev.tab !== next.tab && scrollY > 300) scrollTo(0, 0);
}
/** Change state. User actions push a history entry; typing replaces it. */
function go(patch, replace = false) {
  const prev = state, next = normalise({ ...state, ...patch });
  const url = urlFor(next);
  if (!prev.page && next.page) { SCROLL[prev.view + prev.cluster] = scrollY; history.replaceState({ y: scrollY }, '', location.href); }
  state = next;
  if (url !== location.pathname + location.search) history[replace ? 'replaceState' : 'pushState'](null, '', url);
  render();
  settleScroll(prev, next);
  if (prev.page && !next.page) focusOpener(prev.page);
  else if (prev.cluster && !next.cluster) { const el = document.querySelector(`[data-cluster="${CSS.escape(prev.cluster)}"]`); if (el) el.focus({ preventScroll: true }); }
}
addEventListener('popstate', e => {
  if (!DATA) return;
  const prev = state; state = readURL(); render();
  settleScroll(prev, state, e.state && typeof e.state.y === 'number' ? e.state.y : undefined);
});
if ('scrollRestoration' in history) history.scrollRestoration = 'manual';
function focusOpener(path) {
  const el = [...document.querySelectorAll('[data-open]')].find(b => b.dataset.open === path && b.offsetParent);
  if (el) el.focus({ preventScroll: true });
}

/* ---------- Google date range ---------- */
/* With no Google figures yet (Search Console off) the range is just the build day, so every screen still draws. */
function gBounds() { const g = DATA && DATA.site && DATA.site.gs; if (g && g.length) return [g[0][0], g[g.length - 1][0]]; const t = DATA && DATA.built ? DATA.built.slice(0, 10) : new Date().toISOString().slice(0, 10); return [t, t]; }
const addDays = (d, n) => { const x = new Date(d + 'T00:00:00Z'); x.setUTCDate(x.getUTCDate() + n); return x.toISOString().slice(0, 10); };
const daysBetween = (a, b) => Math.round((Date.parse(b + 'T00:00:00Z') - Date.parse(a + 'T00:00:00Z')) / 864e5) + 1;
const shortDay = d => new Date(d + 'T00:00:00Z').toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' });
const longDay = d => new Date(d + 'T00:00:00Z').toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' });
const fullDay = d => new Date(d + 'T00:00:00Z').toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' });
/** "Oct 17 – Nov 13, 2026" (the year once when both days share it). */
function spanText(a, b) {
  if (a.slice(0, 4) === b.slice(0, 4)) return `${shortDay(a)} – ${shortDay(b)}, ${a.slice(0, 4)}`;
  return `${longDay(a)} – ${longDay(b)}`;
}
function range() {
  const [first, last] = gBounds();
  let from, to = last;
  if (state.range === 'custom') { from = state.from; to = state.to; }
  else if (state.range === '6m') { const x = new Date(last + 'T00:00:00Z'); x.setUTCMonth(x.getUTCMonth() - 6); from = addDays(x.toISOString().slice(0, 10), 1); }
  else from = addDays(last, -(parseInt(state.range, 10) - 1));
  if (from < first) from = first;
  const n = daysBetween(from, to);
  const days = []; for (let i = 0; i < n; i++) days.push(addDays(from, i));
  return { from, to, n, days, label: state.range === 'custom' ? spanText(from, to) : 'last ' + RANGES[state.range], span: `${spanText(from, to)}, ${n} days` };
}
/** Totals of Google rows [day, clicks, impressions, position, final] between two days. */
function gSum(gs, from, to) {
  let c = 0, i = 0, pw = 0, prov = 0, n = 0;
  for (const [d, cl, im, po, fin] of gs || []) {
    if (d < from || d > to) continue;
    n++; c += cl; i += im; pw += (po || 0) * im; if (!fin) prov++;
  }
  return { c, i, ctr: i ? c / i : null, pos: i ? Math.round(10 * pw / i) / 10 : null, prov, n };
}

/* ---------- the one shared copy / open component ---------- */
const ICON_COPY = '<svg viewBox="0 0 16 16" aria-hidden="true"><rect x="5" y="5" width="9" height="9" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M3 11V3a1 1 0 0 1 1-1h7" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>';
const ICON_TICK = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 8.5l3 3 7-7" fill="none" stroke="currentColor" stroke-width="2"/></svg>';
const ICON_OPEN = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M9 2h5v5M14 2L7 9M12 10v3a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h3" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>';
/** Text with a copy icon (and an open icon when `url` is given) shown on hover or focus, always on touch screens. */
function copyable(text, { value, label = 'value', url, html } = {}) {
  const v = value ?? text;
  const open = url ? `<a class="cp cp-open" href="${esc(url)}" target="_blank" rel="noopener" aria-label="Open ${esc(label)} in a new tab">${ICON_OPEN}</a>` : '';
  return `<span class="cp-wrap">${html ?? esc(text)}<span class="cp-tools"><button type="button" class="cp cp-copy" data-copy="${esc(v)}" aria-label="Copy ${esc(label)}">${ICON_COPY}</button>${open}</span></span>`;
}
const pathCopy = (path, label = 'page path') => copyable(path, { label, url: SITE + path });
/** A page's name as a link to its own screen, with the page path's copy and open icons. */
const pageLink = (p, fk) => copyable(p.path, { label: 'page path', url: SITE + p.path,
  html: `<a class="linkbtn" href="${esc(hrefFor({ page: p.path, tab: 'impact' }))}" data-open="${esc(p.path)}" data-fk="${fk}-${esc(p.path)}" aria-label="Open the page screen for ${esc(p.slug)}">${esc(p.slug)}</a>` });
async function doCopy(btn) {
  const text = btn.dataset.copy, wrap = btn.closest('.cp-wrap');
  try { await navigator.clipboard.writeText(text); }
  catch (e) { const t = document.createElement('textarea'); t.value = text; t.style.position = 'fixed'; t.style.opacity = '0'; document.body.append(t); t.select(); try { document.execCommand('copy'); } catch (e2) { /* nothing more to try */ } t.remove(); }
  btn.innerHTML = ICON_TICK; wrap.classList.add('done');
  clearTimeout(btn._t);
  btn._t = setTimeout(() => { btn.innerHTML = ICON_COPY; wrap.classList.remove('done'); if (document.activeElement === btn) btn.blur(); }, 1500);
}

/* ---------- readers (Skald) ---------- */
function readersOn(d) { if (d.state !== 'ok') return null; if (!state.country) return d.readers; return d.countries[state.country] || 0; }
function windows(p) {
  const r = range();
  const gsc = { ...gSum(p.gs, r.from, r.to), ix: p.index ? p.index.status : null };
  const bl = (p.bounce || []).slice(-1)[0];
  const bounce = bl && bl.landed ? { pct: Math.round(100 * (bl.landed - bl.went_on) / bl.landed), landed: bl.landed, went: bl.went_on } : null;
  const gm = p.milestones.find(m => m.kind === 'googlebot'); const google = gm ? gm.at.slice(0, 10) : 'not yet';
  if (!p.main) return { gsc, bounce, google, trend: 'na' };
  const d0 = day(p.main); const ok = p.days.filter(d => d.state === 'ok');
  const after = ok.filter(d => d.day > d0), before = ok.filter(d => d.day < d0);
  const n = Math.min(14, Math.max(after.length, 7)); const b = before.slice(-n), a = after.slice(0, n);
  const sum = (arr, f) => arr.reduce((s, x) => s + (f(x) || 0), 0);
  const pb = b.length ? sum(b, readersOn) / b.length : null, pa = a.length ? sum(a, readersOn) / a.length : null;
  let trend = 'na'; if (pb != null && pa != null) trend = pa > pb * 1.2 && pa - pb >= .5 ? 'up' : pa < pb * .8 && pb - pa >= .5 ? 'down' : 'flat';
  return { gsc, bounce, pb, pa, trend, sb: sum(b, x => x.se), sa: sum(a, x => x.se), nb: b.length, na: a.length, google };
}
const mainWidth = () => Math.max(240, ($('main').clientWidth || innerWidth) - (innerWidth <= 720 ? 32 : 48));
/** A screen's opening: (a) the answer in one line, (b) the numbers that prove it, (c) why, (d) what to do next. */
function answerBlock({ answer, proof = '', why = [], next = [], whyNote = '' }) {
  const list = (h, items, cls) => items.length ? `<div class="${cls}"><h3>${h}</h3><ul>${items.map(x => `<li>${x}</li>`).join('')}</ul>${cls === 'why' ? whyNote : ''}</div>` : '';
  return `<div class="answer"><p class="answer-line">${answer}</p></div>${proof}${why.length || next.length ? `<div class="wn">${list('Why it moved', why, 'why')}${list('What to do next', next, 'next')}</div>` : ''}`;
}
const plural = (n, w) => `${n} ${w}${n === 1 ? '' : 's'}`;
const card = (label, value, sub = '', copyLabel) => `<div class="card"><span>${esc(label)}</span><b>${copyable(String(value), { label: copyLabel || label })}</b>${sub ? `<span class="cmp">${sub}</span>` : ''}</div>`;

/* ---------- Pages view ---------- */
const COLS = [['slug', 'Page'], ['live', 'Main change'], ['impact', 'Impact'], [null, 'Daily readers', 'hide-sm'], ['before', 'Readers before /day', 'r'], ['after', 'Readers after /day', 'r'],
  ['bounce', 'Bounce (7 days)', 'r'], ['gsc', 'Google', 'r'], ['search', 'Search-engine visits b→a', 'r hide-sm'], ['google', 'Googlebot first fetch', 'hide-sm']];
const IMPACT_ORDER = { 'Mostly positive': 5, Mixed: 3, 'No clear change': 2, 'Mostly negative': 1, 'Too early to tell': 0 };
function pageCards(rows) {
  const changed = rows.filter(r => r.p.main).length, tr = rows.filter(r => r.p.tracked), ix = tr.filter(r => r.p.index && r.p.index.status === 'indexed').length;
  const withG = rows.filter(r => r.w.gsc.i).length;
  $('#cards').innerHTML = card('Pages changed by us', `${changed} / ${rows.length}`) + card('Changes live', rows.reduce((s, r) => s + r.p.changes.length, 0))
    + card('Pages seen in Google, ' + range().label.replace(/^last /, ''), `${withG} / ${rows.length}`) + card('Changed pages indexed', `${ix} / ${tr.length}`);
}
function gscCell(g) {
  if (!g || !g.i) return '–';
  const ix = g.ix && g.ix !== 'indexed' ? ' · ' + g.ix.replace(/_/g, ' ') : '';
  return fmtN(g.c) + ' clicks<div class="kind">' + fmtN(g.i) + ' impr. · pos ' + fmt(g.pos) + esc(ix) + '</div>';
}
/** Pages rows, filtered and sorted by the state (kind, q, sort, dir); `only` = a cluster id. */
function pageRows(only) {
  let rows = DATA.pages.map(p => ({ p, w: windows(p), o: pageOverall(p) }));
  if (only) rows = rows.filter(r => r.p.cluster === only);
  if (state.kind !== 'all') rows = rows.filter(r => r.p.kind === state.kind);
  if (state.q) rows = rows.filter(r => (r.p.slug + ' ' + r.p.path + ' ' + (r.p.title || '')).toLowerCase().includes(state.q.toLowerCase()));
  const key = { slug: r => r.p.slug, live: r => r.p.main || '', impact: r => r.o ? IMPACT_ORDER[r.o.verdict] : -1, before: r => r.w.pb ?? -1, after: r => r.w.pa ?? -1, trend: r => ({ up: 3, flat: 2, down: 1, na: 0 })[r.w.trend || 'na'],
    search: r => (r.w.sa || 0) - (r.w.sb || 0), google: r => r.w.google || '', bounce: r => r.w.bounce ? r.w.bounce.pct : -1, gsc: r => r.w.gsc.c * 1e9 + r.w.gsc.i }[state.sort];
  return rows.sort((a, b) => { const x = key(a), y = key(b); return (x > y ? 1 : x < y ? -1 : 0) * (state.dir === 'asc' ? 1 : -1) || a.p.slug.localeCompare(b.p.slug); });
}
function theadHTML() {
  return COLS.map(([k, label, cls]) => {
    const l = k === 'gsc' ? `Google, ${range().label.replace(/^last /, '')}` : label;
    if (!k) return `<th class="${cls || ''}">${l}</th>`;
    const sort = state.sort === k ? (state.dir === 'asc' ? 'ascending' : 'descending') : 'none';
    return `<th class="${cls || ''}" aria-sort="${sort}"><button type="button" data-sort="${k}" data-fk="sort-${k}" aria-label="Sort by ${esc(l)}">${esc(l)}</button></th>`;
  }).join('');
}
function rowHTML({ p, w, o }, fk) {
  return `<tr class="row" data-path="${esc(p.path)}"><td><div class="ktag">${esc(p.kind)}${p.tracked ? '' : ' · Google and readers only'}</div>${pageLink(p, fk)}</td>
    <td class="num">${p.main ? new Date(p.main).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: TZ_NAME }) + `<div class="kind">${p.changes.length} change${p.changes.length === 1 ? '' : 's'}</div>` : '<span class="na">not changed</span>'}</td>
    <td>${o ? opill(o.verdict) : '<span class="na">–</span>'}</td>
    <td class="hide-sm">${spark(p)}</td><td class="num r">${fmt(w.pb)}</td><td class="num r">${fmt(w.pa)}</td>
    <td class="num r">${w.bounce ? w.bounce.pct + '%<div class="kind">of ' + w.bounce.landed + ' landings</div>' : '–'}</td>
    <td class="num r">${gscCell(w.gsc)}</td><td class="num r hide-sm">${p.main ? `${w.sb ?? '–'} → ${w.sa ?? '–'}` : '–'}</td><td class="hide-sm num">${w.google === 'not yet' || !w.google ? '<span class="na">–</span>' : esc(shortDay(w.google))}</td></tr>`;
}
/** Rows under a header row per group: groups [{key, title, html (extra), rows}]. */
function groupedRows(groups, fk) {
  const out = groups.filter(g => g.rows.length).map(g => `<tr class="grp-row"><th colspan="${COLS.length}" scope="rowgroup">${g.title}</th></tr>${g.rows.map(r => rowHTML(r, fk)).join('')}`).join('');
  return out || `<tr><td colspan="${COLS.length}" class="empty">No page matches these filters.</td></tr>`;
}
function renderPages() {
  const rows = pageRows(state.cl);
  pageCards(rows);
  $('#kinds').innerHTML = KINDS.map(k => `<button type="button" class="chip" aria-pressed="${state.kind === k}" data-kind="${k}">${k === 'all' ? 'All' : k[0].toUpperCase() + k.slice(1)}</button>`).join('');
  $('#cl').innerHTML = `<option value="">All clusters</option>` + (DATA.clusters || []).map(c => `<option value="${esc(c.id)}"${state.cl === c.id ? ' selected' : ''}>${esc(c.name)} (${c.paths.length})</option>`).join('');
  $('#thead').innerHTML = theadHTML();
  if ($('#country').value !== state.country) $('#country').value = state.country;
  if ($('#q').value !== state.q) $('#q').value = state.q;
  const groups = (DATA.clusters || []).filter(c => !state.cl || c.id === state.cl).map(c => {
    const rs = rows.filter(r => r.p.cluster === c.id), ch = rs.filter(r => r.p.main).length;
    return { rows: rs, title: `<a href="${esc(hrefFor({ view: 'clusters', cluster: c.id, page: '' }))}" data-cluster="${esc(c.id)}">${esc(c.name)}</a> <span class="kind">${plural(rs.length, 'page')}${ch ? `, ${ch} changed by us` : ', none changed by us'}</span>` };
  });
  $('#rows').innerHTML = groupedRows(groups, 'open');
  $('#about').open = state.about === '1';
}

/* ---------- Google view (whole site) ---------- */
function topTable(rows, nameLabel, kind) {
  if (!rows || !rows.length) return '<div class="empty">None yet.</div>';
  const name = r => kind === 'country' ? r[0].toUpperCase() : r[0];
  return `<div class="box"><table><thead><tr><th>${nameLabel}</th><th class="r">Clicks</th><th class="r">Impressions</th><th class="r">Position</th></tr></thead><tbody>${
    rows.map(r => `<tr><td>${copyable(name(r), { label: nameLabel.toLowerCase() })}${r[4] === 'us' ? ' <span class="kind">US copy</span>' : ''}</td><td class="num r">${fmtN(r[1])}</td><td class="num r">${fmtN(r[2])}</td><td class="num r">${r[3] == null ? '–' : r[3].toFixed(1)}</td></tr>`).join('')}</tbody></table></div>`;
}
function cmpLine(now, prev, better = 'up', f = fmtN) {
  if (now == null || prev == null) return '';
  if (prev === 0) return `<span class="na">was ${f(prev)}</span>`;
  const ch = (now - prev) / prev, good = better === 'up' ? ch > 0 : ch < 0;
  return `<span class="${Math.abs(ch) < .02 ? 'flat' : good ? 'up' : 'down'}">${ch > 0 ? '+' : ''}${(ch * 100).toFixed(0)}%</span> vs ${f(prev)} before`;
}
/** Up, down or flat in words, the way a person would say it. */
function moveWord(now, prev, better = 'up') {
  if (now == null || prev == null || !prev) return 'about the same';
  const ch = (now - prev) / prev; if (Math.abs(ch) < .1) return 'about the same';
  return (better === 'up' ? ch > 0 : ch < 0) ? 'better' : 'worse';
}
function renderGoogle() {
  const r = range(), gs = DATA.site.gs, t = gSum(gs, r.from, r.to);
  const pf = addDays(r.from, -r.n), pt = addDays(r.from, -1), prev = gSum(gs, pf, pt), hasPrev = pf >= gBounds()[0];
  const width = mainWidth() - 26;
  const c = (k, v, cmp) => card(k, v, hasPrev ? cmp : '');
  const pages = DATA.pages.map(p => ({ p, g: gSum(p.gs, r.from, r.to) })).filter(x => x.g.i).sort((a, b) => b.g.c - a.g.c || b.g.i - a.g.i).slice(0, 15);
  const mi = moveWord(t.i / r.n, prev.i / r.n), mc = moveWord(t.c / r.n, prev.c / r.n), mp = moveWord(t.pos, prev.pos, 'down');
  const verdictWord = !hasPrev ? 'No earlier period to compare' : mi === 'better' && mc !== 'worse' ? 'Growing in Google' : mi === 'worse' && mc !== 'better' ? 'Shrinking in Google' : mi === 'about the same' && mc === 'about the same' ? 'Steady in Google' : 'Mixed in Google';
  const answer = `<b>${verdictWord}.</b> ${hasPrev ? `Whole site, ${esc(r.span)}, against the ${r.n} days before: impressions ${mi}, clicks ${mc}, average position ${mp}.` : esc(r.span) + '.'}`;
  const proof = `<div class="cards">${c('Clicks', fmtN(t.c), cmpLine(t.c, prev.c))}${c('Impressions', fmtN(t.i), cmpLine(t.i, prev.i))}
    ${c('CTR', pct(t.ctr), cmpLine(t.ctr, prev.ctr, 'up', v => pct(v)))}${c('Average position', t.pos == null ? '–' : t.pos.toFixed(1), cmpLine(t.pos, prev.pos, 'down', v => v.toFixed(1)))}</div>`;
  const ctx = whyContext(r.from, r.to, null);
  $('#v-google').innerHTML = answerBlock({ answer, proof, why: ctx.why, next: ctx.next, whyNote: ctx.note })
    + `<h2 class="sec">Google Search, whole site, day by day</h2>
    ${chartControls(false)}${googleCharts(gs, null, chartNotes(null), width)}
    <p class="sub">Page copies counted together, as Google reports the whole site.${t.prov ? ` The last ${t.prov} days are provisional.` : ''}${hasPrev ? ` "Before" is the ${r.n} days before (${esc(spanText(pf, pt))}).` : ''}</p>
    ${crossCheck(gs, DATA.pages, 'Whole site in Google against every sitemap page in Skald')}
    ${impactSummary()}
    <h2 class="sec">Top pages in Google, ${esc(r.span)}</h2>
    ${pages.length ? `<div class="box"><table><thead><tr><th>Page</th><th class="r">Clicks</th><th class="r">Impressions</th><th class="r">Position</th><th class="hide-sm">Main change</th></tr></thead><tbody>${pages.map(({ p, g }) =>
      `<tr class="row" data-path="${esc(p.path)}"><td>${pageLink(p, 'gopen')}</td><td class="num r">${fmtN(g.c)}</td><td class="num r">${fmtN(g.i)}</td><td class="num r">${fmt(g.pos)}</td><td class="hide-sm num">${p.main ? esc(longDay(day(p.main))) : '–'}</td></tr>`).join('')}</tbody></table></div>` : '<div class="empty">No tracked page had impressions in this range.</div>'}
    <div class="grid2"><div><h2 class="sec">Top searches</h2>${topTable(DATA.site.gq, 'Search', 'query')}</div><div><h2 class="sec">Top countries</h2>${topTable(DATA.site.gc, 'Country', 'country')}</div></div>
    <p class="sub">Top searches and countries are Google's last 28 days as of ${DATA.site.gsnap ? esc(longDay(DATA.site.gsnap)) : '–'}; they do not follow the date range above.</p>`;
}

/** The Google date range picker (in the sub bar, and on the page screen's chart tabs). */
function rangeBar(where) {
  const r = range(), [first, last] = gBounds();
  const dates = state.range === 'custom' ? ` <span><input type="date" data-date="from" data-fk="${where}-from" min="${first}" max="${last}" value="${r.from}" aria-label="From date"> to <input type="date" data-date="to" data-fk="${where}-to" min="${first}" max="${last}" value="${r.to}" aria-label="To date"></span>` : '';
  return `<div class="bar rangebar" role="group" aria-label="Chart date range"><span class="chips-seg">${Object.entries(RANGES).map(([k, v]) => `<button type="button" class="chip" data-range="${k}" data-fk="${where}-range-${k}" aria-pressed="${state.range === k}">${v}</button>`).join('')}</span>${dates} <span class="sub">${esc(r.span)}</span></div>`;
}

/* ---------- breadcrumbs ---------- */
function crumbs() {
  const home = `<li><a href="${esc(hrefFor({ view: 'insights', page: '', tab: 'impact' }))}" data-nav="insights">Dashboard</a></li>`;
  const clusterCrumb = c => `<li><a href="${esc(hrefFor({ view: 'clusters', cluster: '', page: '', tab: 'impact' }))}" data-nav="clusters">Clusters</a></li>` + (c ? `<li><a href="${esc(hrefFor({ view: 'clusters', cluster: c.id, page: '', tab: 'impact' }))}" data-cluster="${esc(c.id)}">${esc(c.name)}</a></li>` : '');
  const cl = state.cluster && (DATA.clusters || []).find(c => c.id === state.cluster);
  if (state.page) {
    const p = DATA.pages.find(x => x.path === state.page);
    return `<ol>${home}${cl ? clusterCrumb(cl) : `<li><a href="${esc(hrefFor({ view: 'pages', page: '', tab: 'impact' }))}" data-nav="pages" data-fk="crumb-pages">Pages</a></li>`}<li><span aria-current="page">${esc(p.title || p.slug)}</span></li><li class="crumb-path">${pathCopy(p.path)}</li></ol>`;
  }
  if (cl) return `<ol>${home}${clusterCrumb(null)}<li><span aria-current="page">${esc(cl.name)}</span></li></ol>`;
  return `<ol>${home}<li><span aria-current="page">${VIEW_NAMES[state.view]}</span></li></ol>`;
}

/* ---------- render ---------- */
function render() {
  const keep = document.activeElement && document.activeElement.dataset ? document.activeElement.dataset.fk : null;
  document.documentElement.dataset.theme = state.theme;
  const dark = state.theme === 'dark';
  $('#theme').innerHTML = dark ? '<svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="3" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M8 1v2M8 13v2M1 8h2M13 8h2M3 3l1.4 1.4M11.6 11.6L13 13M3 13l1.4-1.4M11.6 4.4L13 3" stroke="currentColor" stroke-width="1.5"/></svg>'
    : '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M13.5 9.5A5.5 5.5 0 0 1 6.5 2.5a5.5 5.5 0 1 0 7 7z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/></svg>';
  $('#theme').setAttribute('aria-label', dark ? 'Light mode' : 'Dark mode');
  $('#theme').title = dark ? 'Light mode' : 'Dark mode';
  $('#theme').setAttribute('aria-pressed', String(dark));
  for (const v of VIEWS) {
    const b = $('#tab-' + v), on = state.view === v && !state.page;
    b.setAttribute('aria-selected', String(on)); b.tabIndex = on || (state.page && v === state.view) ? 0 : -1;
    $('#v-' + v).hidden = state.view !== v || !!state.page;
  }
  $('#v-page').hidden = !state.page;
  $('#crumbs').innerHTML = crumbs();
  $('#rangebar').innerHTML = rangeBar('h');
  $('#rangebar').hidden = state.view === 'insights' || state.view === 'clusters' || !!state.page;  // Insights uses fixed windows; the page screen has its own
  chartsPrune();
  if (!state.page) {
    if (state.view === 'pages') renderPages();
    if (state.view === 'google') renderGoogle();
    if (state.view === 'clusters') renderClusters();
  }
  const ri = window.renderInsights;  // insights.js draws the Insights view (only while it is shown)
  if (typeof ri === 'function') ri($('#v-insights'), state, DATA); else $('#v-insights').innerHTML = '<div class="empty">The Insights view (insights.js) is not loaded.</div>';
  const p = state.page && DATA.pages.find(x => x.path === state.page);
  const clT = state.cluster && (DATA.clusters || []).find(c => c.id === state.cluster);
  document.title = p ? `${p.title || p.slug} · Page Change Tracker` : clT ? `${clT.name} · Clusters · Page Change Tracker` : `${VIEW_NAMES[state.view]} · Page Change Tracker`;
  if (p) renderPage(p); else { $('#v-page').innerHTML = ''; delete $('#v-page').dataset.path; }
  if (keep) { const el = document.querySelector(`[data-fk="${CSS.escape(keep)}"]`); if (el && el !== document.activeElement) el.focus({ preventScroll: true }); }
}

/* ---------- events ---------- */
const plainClick = e => e.button === 0 && !e.metaKey && !e.ctrlKey && !e.shiftKey && !e.altKey;
document.addEventListener('click', e => {
  const t = e.target;
  const cp = t.closest('[data-copy]'); if (cp) { e.stopPropagation(); doCopy(cp); return; }
  const op = t.closest('a.cp-open'); if (op) { setTimeout(() => op.blur(), 0); return; }
  const nav = t.closest('[data-nav]'); if (nav) { if (!plainClick(e)) return; e.preventDefault(); return go({ view: nav.dataset.nav, page: '', cluster: '', tab: 'impact' }); }
  const clk = t.closest('[data-cluster]'); if (clk) { if (!plainClick(e)) return; e.preventDefault(); return go({ view: 'clusters', cluster: clk.dataset.cluster, page: '', tab: 'impact' }); }
  const home = t.closest('[data-home]'); if (home) { if (!plainClick(e)) return; e.preventDefault(); return go({ view: 'insights', page: '', tab: 'impact' }); }
  const v = t.closest('[data-view]'); if (v) return go({ view: v.dataset.view, page: '', cluster: '', tab: 'impact' });
  const k = t.closest('[data-kind]'); if (k) return go({ kind: k.dataset.kind });
  const rg = t.closest('[data-range]'); if (rg) {
    if (rg.dataset.range === 'custom') { const r = range(); return go({ range: 'custom', from: r.from, to: r.to }); }
    return go({ range: rg.dataset.range, from: '', to: '' });
  }
  const mt = t.closest('[data-metric]'); if (mt && !mt.disabled) {
    const set = new Set(state.m.split(',')); set.has(mt.dataset.metric) ? set.delete(mt.dataset.metric) : set.add(mt.dataset.metric);
    if (!set.size) return;  // keep at least one measure
    return go({ m: [...set].join(',') });
  }
  const an = t.closest('[data-ann]'); if (an) {
    const set = new Set(state.ann === 'none' ? [] : state.ann.split(',')); set.has(an.dataset.ann) ? set.delete(an.dataset.ann) : set.add(an.dataset.ann);
    return go({ ann: set.size ? [...set].join(',') : 'none' });
  }
  const th = t.closest('[data-sort]'); if (th) {
    const s = th.dataset.sort;
    return go(state.sort === s ? { dir: state.dir === 'asc' ? 'desc' : 'asc' } : { sort: s, dir: s === 'slug' ? 'asc' : 'desc' });
  }
  const tb = t.closest('[data-tab]'); if (tb) return go({ tab: tb.dataset.tab });
  const o = t.closest('[data-open]'); if (o) { if (!plainClick(e)) return; e.preventDefault(); return go({ page: o.dataset.open, tab: 'impact' }); }
  const back = t.closest('[data-back]'); if (back) { if (!plainClick(e)) return; e.preventDefault(); return go({ page: '', tab: 'impact', view: 'pages', cluster: '' }); }
  if (t.closest('.cp-tools, a, button, input, select, summary')) return;
  const ctr = t.closest('tr.crow'); if (ctr) return go({ view: 'clusters', cluster: ctr.dataset.cluster, page: '', tab: 'impact' });
  const tr = t.closest('tr.row'); if (tr) return go({ page: tr.dataset.path, tab: 'impact' });
});
// arrow keys move between tabs (views and page sections), as a tablist should; Esc leaves the page screen
document.addEventListener('keydown', e => {
  if (e.key === 'Escape' && state && (state.page || state.cluster) && !e.target.closest('input, select, textarea')) { e.preventDefault(); return go(state.page ? { page: '', tab: 'impact' } : { cluster: '' }); }
  const tab = e.target.closest && e.target.closest('[role="tab"]'); if (!tab || !['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) return;
  const all = [...tab.parentElement.querySelectorAll('[role="tab"]')]; let i = all.indexOf(tab);
  i = e.key === 'Home' ? 0 : e.key === 'End' ? all.length - 1 : (i + (e.key === 'ArrowRight' ? 1 : -1) + all.length) % all.length;
  e.preventDefault(); all[i].focus(); all[i].click();
});
$('#theme').addEventListener('click', () => go({ theme: state.theme === 'light' ? 'dark' : 'light' }));
$('#about').addEventListener('toggle', () => { const v = $('#about').open ? '1' : ''; if (v !== state.about) go({ about: v }); });
$('#country').addEventListener('change', e => go({ country: e.target.value }));
$('#cl').addEventListener('change', e => go({ cl: e.target.value }));
$('#q').addEventListener('input', e => go({ q: e.target.value }, true));
document.addEventListener('change', e => {
  const d = e.target.closest('[data-date]'); if (!d || !isDay(d.value)) return;
  const box = d.closest('.rangebar'), f = box.querySelector('[data-date="from"]').value, t = box.querySelector('[data-date="to"]').value;
  go({ range: 'custom', from: f, to: t });
});
let rz, lastW = innerWidth; addEventListener('resize', () => { clearTimeout(rz); rz = setTimeout(() => { if (DATA && innerWidth !== lastW) { lastW = innerWidth; render(); } }, 150); });

addEventListener('DOMContentLoaded', () => fetch('data.json?' + Date.now()).then(r => r.json()).then(d => {
  DATA = d;
  NO_DATA = !d.pages.some(p => p.days.length) && !(d.site.gs || []).length;
  const cs = {}; d.pages.forEach(p => p.days.forEach(x => { for (const [k, v] of Object.entries(x.countries || {})) cs[k] = (cs[k] || 0) + v; }));
  Object.entries(cs).sort((a, b) => b[1] - a[1]).forEach(([k, v]) => { COUNTRIES.add(k); $('#country').insertAdjacentHTML('beforeend', `<option value="${esc(k)}">${esc(k)} (${v})</option>`); });
  SITE = (d.config && d.config.site_url) || ''; TZ_NAME = (d.config && d.config.timezone) || TZ_NAME;
  // the owner's zone (growth.json timezone, shown as EST/EDT style), e.g. "Nov 14, 2026, 9:20 AM EST"
  const bd = new Date(d.built);
  const built = bd.toLocaleString('en-US', { year: 'numeric', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
    timeZone: TZ_NAME, timeZoneName: 'short' });
  $('#built').textContent = 'Updated ' + built;
  const src = d.config ? Object.entries(d.config.sources).filter(([, on]) => on).map(([k]) => ({ sitemap: 'the sitemap', skald: 'Skald (server logs)', search_console: 'Google Search Console (through Skald)', ga4: 'Google Analytics (through Skald)', google_updates: "Google's Search Status Dashboard" }[k] || k)) : [];
  const since = d.start ? ` · first change on record: ${longDay(d.start.slice(0, 10))}` : '';
  $('#foot').textContent = `Updated ${built}${since} · sources on: the site repo's git history${src.length ? ', ' + src.join(', ') : ''}${src.some(x => x.startsWith('Skald')) ? '' : ' · Skald and Search Console are off, so there are no reader or Google figures yet'}`;
  if (d.release) $('#release').textContent = `v${d.release.version} · build ${d.release.build} · ${new Date(d.release.built).toLocaleString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: TZ_NAME, timeZoneName: 'short' })}`;
  state = readURL();
  const clean = urlFor(state); if (clean !== location.pathname + location.search) history.replaceState(null, '', clean);  // drop invalid values
  fetch('insights.json?' + Date.now()).then(r => r.ok ? r.json() : null).catch(() => null).then(ai => { AI = ai; render(); });
}).catch(err => { $('#built').textContent = 'Could not load data.json: ' + err.message; }));
