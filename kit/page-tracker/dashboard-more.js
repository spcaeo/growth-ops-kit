'use strict';
/* Competing pages, click-rate check, experiment log, "what changed" diffs, Google Analytics and editor saves
   (added 13 Nov 2026). Data from insights_more.py, diffs.py and ga4.py through data.json (diffs are fetched per page
   from diffs/<page>.json only when its Changes tab opens). */

const slugOf = p => (p || '').replace(/\/$/, '').split('/').pop() || 'home';
const pageBy = path => DATA.pages.find(p => p.path === path);
const linkTo = (path, fk) => { const p = pageBy(path); return p ? pageLink(p, fk) : pathCopy(path); };

/* ---------- competing pages ---------- */
/** Searches where 2+ of our pages compete; only those touching one of `paths` when given. */
function competingSection(paths, opts = {}) {
  const C = (DATA.insights && DATA.insights.competing) || { searches: [] };
  let list = C.searches || [];
  if (paths) list = list.filter(x => x.pages.some(p => paths.includes(p.path)));
  const head = opts.h || 'Our pages competing for the same search';
  const h2 = opts.bare ? '' : `<h2 class="sec">${head}</h2>`;
  if (!list.length) return opts.quiet ? '' : `${h2}<div class="empty">None found in Google's top searches.</div>`;
  const rows = list.slice(0, opts.max || 15).map(x => {
    const ps = x.pages.map(p => {
      const w = (p.windows || [])[0], tags = [p.path === x.google_prefers ? '<span class="v v-nochange">Google shows most</span>' : '', p.path === x.owner ? '<span class="v v-better">should own it</span>' : ''].join(' ');
      return `<div class="cp-row">${linkTo(p.path, 'comp-' + x.query)} ${tags}<div class="kind">${fmtN(p.impressions)} impr. · ${p.clicks} clicks · pos ${p.position == null ? '–' : p.position}${w ? ` · was pos ${w[3] == null ? '–' : (+w[3]).toFixed(1)} (${esc(shortDay(w[0]))}–${esc(shortDay(w[1]))})` : ''}${(p.history || []).length > 1 ? ` · ${p.history.length} daily snapshots` : ''}</div></div>`;
    }).join('');
    return `<tr><td>${copyable(x.query, { label: 'search' })}<div class="kind">${fmtN(x.impressions)} impressions in all</div></td><td>${ps}</td><td class="sugg">${esc(x.suggestion)}</td></tr>`;
  }).join('');
  return `${h2}<div class="box"><table><thead><tr><th>Search</th><th>Our pages (Google's top 10 per page)</th><th>Suggestion</th></tr></thead><tbody>${rows}</tbody></table></div><p class="rules">${esc(C.note || '')}</p>`;
}

/* ---------- click-rate check ---------- */
function ctrSection() {
  const X = (DATA.insights && DATA.insights.ctr_check) || null;
  if (!X) return '';
  const curve = X.curve.filter(b => b.ctr != null).map(b => `pos ${b.frm}${b.to > 50 ? '+' : `–${b.to}`}: ${(b.ctr * 100).toFixed(2)}%`).join(' · ');
  const rows = X.pages.map(r => `<tr><td>${linkTo(r.path, 'ctr')}</td><td class="num r">${fmtN(r.impressions)}</td><td class="num r">${r.clicks}<div class="kind">usual: ${r.expected_clicks}</div></td><td class="num r">${(r.ctr * 100).toFixed(2)}%</td><td class="num r">${r.position}</td>
    <td class="meta"><b>${r.title ? copyable(r.title, { label: 'current title' }) : '<span class="na">no title found</span>'}</b><div>${r.description ? copyable(r.description, { label: 'current description' }) : '<span class="na">no description found</span>'}</div><div class="kind">${esc(r.file || '')}</div></td></tr>`).join('');
  return `<p class="sub">${esc(spanText(X.window.frm, X.window.to))}, final Google days. This site's own click rate by position (${esc(spanText(X.curve_window.frm, X.curve_window.to))}): ${esc(curve)}.</p>
    ${X.pages.length ? `<div class="box"><table><thead><tr><th>Page</th><th class="r">Impressions</th><th class="r">Clicks</th><th class="r">CTR</th><th class="r">Position</th><th>Current title and description (rewrite candidates)</th></tr></thead><tbody>${rows}</tbody></table></div>` : '<div class="empty">No page is far below the usual click rate.</div>'}
    <p class="rules">${esc(X.rule)}</p>`;
}

/* ---------- experiment log ---------- */
function expTable(rows, withPage) {
  const res = (r, due) => r ? `${opill(r.overall)}<div class="kind">${Object.entries(r.rows).map(([k, v]) => `${k} ${v.verdict}`).join(' · ')}</div>` : `<span class="na">fills in on ${esc(shortDay(due))}+</span>`;
  if (!rows.length) return '<div class="empty">No change logged yet.</div>';
  return `<div class="box"><table><thead><tr><th>Live</th>${withPage ? '<th>Page</th>' : ''}<th>Aim (from the commit)</th><th>Expectation</th><th>Result, 7 final days</th><th class="hide-sm">Result, 14 final days</th></tr></thead><tbody>${
    rows.map(x => `<tr><td class="num">${esc(shortDay(x.live_at.slice(0, 10)))}${x.main ? '<div class="kind">main change</div>' : ''}</td>${withPage ? `<td>${linkTo(x.path, 'exp')}</td>` : ''}<td>${esc(x.aim)}</td><td>${x.expectation ? esc(x.expectation) : '<span class="na">to be added</span>'}</td><td>${res(x.r7, x.due7)}</td><td class="hide-sm">${res(x.r14, x.due14)}</td></tr>`).join('')}</tbody></table></div>`;
}
const expOf = path => ((DATA.insights && DATA.insights.experiments) || { rows: [] }).rows.filter(x => !path || x.path === path);
function expSection(path) {
  const E = (DATA.insights && DATA.insights.experiments) || { rows: [] }, rows = expOf(path);
  return `<h2 class="sec">Experiment log</h2>${expTable(path ? rows : rows.slice(0, 40), !path)}<p class="rules">${esc(E.rule || '')}${!path && rows.length > 40 ? ` Showing the newest 40 of ${rows.length}; each page lists its own.` : ''}</p>`;
}

/* ---------- what changed (diffs) ---------- */
const DIFFS = {};
function loadDiffs(p) {
  if (!p.diff_file || DIFFS[p.path]) return;
  DIFFS[p.path] = 'loading';
  fetch(p.diff_file + '?' + Date.now()).then(r => r.ok ? r.json() : {}).catch(() => ({})).then(d => { DIFFS[p.path] = d; if (state.page === p.path && state.tab === 'changes') render(); });
}
function mdBlock(t) {  // a block as readable text: headings and list items keep their look, everything escaped
  const h = t.match(/^(#{1,4})\s+(.*)$/);
  if (h) return `<div class="dh">${esc(h[2])}</div>`;
  return `<div>${esc(t.replace(/^[-*]\s+/, '• ').replace(/\*\*(.+?)\*\*/g, '$1'))}</div>`;
}
function diffHTML(d) {
  const val = v => v == null ? '<span class="na">(none)</span>' : esc(String(v).slice(0, 300));
  const fields = d.fields.length ? `<div class="dfields">${d.fields.map(f => `<div><b>${esc(f.key)}</b><div class="del">${val(f.before)}</div><div class="add">${val(f.after)}</div></div>`).join('')}</div>` : '';
  const CAP = 80, big = d.blocks.length > CAP;
  const blocks = (big ? d.blocks.slice(0, CAP) : d.blocks).map(b => b.t === 'same' ? `<div class="dsame">… ${b.n} unchanged block${b.n === 1 ? '' : 's'} …</div>`
    : b.t === 'add' ? `<div class="add">${mdBlock(b.text)}</div>` : b.t === 'del' ? `<div class="del">${mdBlock(b.text)}</div>`
      : `<div class="dmod">${b.words.map(([op, w]) => op === '=' ? esc(w) : `<span class="${op === '+' ? 'add' : 'del'}">${esc(w)}</span>`).join(' ')}</div>`).join('');
  return `${fields}<div class="dbody">${blocks}</div>${big ? `<p class="sub">A large rewrite: the first ${CAP} of ${d.blocks.length} blocks are shown. The full diff is in this page's file under page-tracker/diffs/.</p>` : ''}`;
}
const openDiffs = () => state.diff ? state.diff.split(',') : [];
function tabChangesDiff(p) {
  loadDiffs(p);
  const D = DIFFS[p.path], open = openDiffs();
  if (!p.changes.length) return '<div class="na">No change recorded</div>';
  return `<p class="sub">Each change against the ship before it (the page's content file in the site repo). Fields such as the title and description first, then the text: <span class="add">added</span>, <span class="del">removed</span>.</p>` + p.changes.slice().reverse().map(c => {
    const d = D && D !== 'loading' ? D[c.sha] : null, isOpen = open.includes(c.sha);
    const sum = `${esc(new Date(c.live_at).toLocaleString('en-US', { weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: TZ_NAME }))} · ${c.words_before} → ${c.words_after} words${c.live_at === p.main ? ' · <b>main change</b>' : ''}${d ? ` · <span class="add">+${d.added_words}</span> <span class="del">−${d.removed_words}</span> words${d.fields.length ? ' · ' + d.fields.slice(0, 3).map(f => esc(f.key)).join(', ') : ''}` : ''}`;
    return `<details class="chg" data-diff="${esc(c.sha)}"${isOpen ? ' open' : ''}><summary data-fk="diff-${esc(c.sha)}">${sum}<div class="t">${esc(changeWhat(c))}</div></summary>${isOpen ? (D === 'loading' || !D ? '<p class="sub">Loading…</p>' : d ? diffHTML(d) : '<p class="sub">No diff stored for this change.</p>') : ''}<div class="t">${(c.commits || []).slice(0, 3).map(x => copyable(x.slice(8, 120), { value: x.slice(0, 7), label: 'commit id' })).join('<br>')}</div></details>`;
  }).join('');
}
document.addEventListener('toggle', e => {
  const d = e.target; if (!d.matches || !d.matches('details[data-diff]')) return;
  const set = new Set(openDiffs()); d.open ? set.add(d.dataset.diff) : set.delete(d.dataset.diff);
  const v = [...set].join(','); if (v !== state.diff) go({ diff: v });
}, true);

/* ---------- Google Analytics (its own counts, never added to Skald's) ---------- */
function gaFor(p) {
  const G = DATA.ga4; if (!G) return null;
  const now = G.pages[p.path], legacy = (p.path.startsWith('/blog/') ? null : G.pages['/blog/' + slugOf(p.path)]);
  return { now, legacy, G };
}
function gaFact(p) {
  const g = gaFor(p); if (!g) return '<span class="na">not connected</span>';
  const t = x => `${fmtN(x.sessions)} sessions · ${fmtN(x.key_events)} key events`;
  if (!g.now && !g.legacy) return `<span class="na">not in GA's top landing pages</span>`;
  return `${g.now ? t(g.now) : ''}${g.legacy ? `${g.now ? '<br>' : ''}<span class="kind">old /blog/ address: </span>${t(g.legacy)}` : ''} <span class="kind">· ${esc(spanText(g.G.start, g.G.end))}</span>`;
}
function gaNote() {
  const G = DATA.ga4; if (!G) return '';
  return `<p class="rules">Google Analytics: ${esc(G.counted_from || 'Counted from: Google Analytics')}, ${esc(G.note || '')}, ${esc(spanText(G.start, G.end))} (its own last 28 days). Its landing report holds only its top 10 landing pages and has no engaged sessions; its counts are never added to Skald's. Whole site: ${fmtN((G.total || {}).sessions)} sessions, ${fmtN((G.total || {}).keyEvents)} key events.</p>`;
}

/* ---------- editor saves as chart notes ---------- */
function editNotes(p) {
  const list = p && !Array.isArray(p) ? [p] : Array.isArray(p) ? p : DATA.pages;
  const byDay = {};
  for (const pg of list) for (const e of pg.edits || []) { const d = e.at.slice(0, 10); (byDay[d] = byDay[d] || []).push({ pg, e }); }
  return Object.entries(byDay).sort().map(([d, xs]) => ({ kind: 'edits', d, label: `${fullDay(d)}: ${xs.length} editor save${xs.length === 1 ? '' : 's'}`,
    tip: `<b>Editor saves · ${esc(fullDay(d))}</b>${xs.slice(0, 5).map(({ pg, e }) => `<div>${esc(slugOf(pg.path))}: ${esc((e.fields || []).slice(0, 4).join(', ') || 'content')} <span class="p">by ${esc(e.role)}</span></div>`).join('')}${xs.length > 5 ? `<div class="p">and ${xs.length - 5} more</div>` : ''}` }));
}

/* ---------- Key findings: 2 to 5 plain sentences at the top of Insights, a cluster and a page (findings.py) ---------- */
const FCLASS = { worse: 'v-worse', better: 'v-better', early: 'v-early', watch: 'v-early', fix: 'v-worse', flat: 'v-nochange', info: 'v-nochange', yard: 'v-nochange' };
let CNOTES = null, cnFetching = false;
function clusterNote(id) {
  if (!CNOTES && !cnFetching) { cnFetching = true; fetch('cluster-notes.json?' + Date.now()).then(r => r.ok ? r.json() : {}).catch(() => ({})).then(j => { CNOTES = j || {}; if (state.cluster) render(); }); }
  const n = CNOTES && CNOTES.notes && CNOTES.notes[id];
  if (!n || !n.text) return '';
  return `<p class="kf-ai"><span class="ai-tag">AI</span> ${esc(n.text)}${n.unverified_numbers && n.unverified_numbers.length ? ` <span class="down">(numbers not found in the data: ${esc(n.unverified_numbers.join(', '))})</span>` : ''} <span class="kind">written ${esc(longDay(CNOTES.date))} from this cluster's figures; check them against the numbers</span></p>`;
}
const goPatch = l => l.page ? { page: l.page, tab: l.tab || 'impact' } : { view: l.view || 'insights', cluster: l.cluster || '', page: '', tab: 'impact', ...(l.sort ? { sort: l.sort } : {}) };
function findingsBox(list, extra = '') {
  if (!list || !list.length) return '';
  return `<section class="kf" aria-labelledby="kf-h"><h2 id="kf-h">Key findings</h2><ol>${list.map((x, i) => {
    const patch = goPatch(x.link), same = Object.entries(patch).every(([k, v]) => state[k] === v);
    return `<li><span class="v ${FCLASS[x.verdict] || 'v-nochange'}">${esc(x.word)}</span> <span class="kf-t">${esc(x.text)}</span>${same ? '' : ` <a href="${esc(hrefFor(patch))}" data-go="${esc(JSON.stringify(patch))}" data-fk="kf-${i}">the proof →</a>`}</li>`;
  }).join('')}</ol>${extra}</section>`;
}
document.addEventListener('click', e => {
  const a = e.target.closest && e.target.closest('[data-go]'); if (!a || !plainClick(e)) return;
  e.preventDefault(); e.stopPropagation(); go(JSON.parse(a.dataset.go));
}, true);
