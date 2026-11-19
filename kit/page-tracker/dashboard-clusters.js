'use strict';
/* Clusters (?view=clusters, and ?view=clusters&cluster=<id> for one cluster): the site's own sitemap clusters
   (clusters.py reads the site's sitemap and groups it by the rules in growth.json), every page in them, not only the ones we changed.
   Before vs after each cluster's first change (same-length windows, change day skipped, same verdict rules as the
   Impact tab); a cluster we have not changed is compared around the site's first change, and says so. */

const pagesOf = c => DATA.pages.filter(p => p.cluster === c.id);
/** Before vs after for one cluster: rows like impactRows (readers, clicks, impressions, ctr, position), plus d0. */
function clusterImpact(c, N) {
  const ps = pagesOf(c), changed = ps.filter(p => p.main);
  const d0 = changed.length ? changed.map(p => day(p.main)).sort()[0] : DATA.insights ? DATA.insights.split : day(DATA.start);
  const gw = gwinJS(d0, N), rw = rwinJS(d0, N), out = { d0, changed: changed.length, pages: ps.length };
  const rd = clusterReaders(ps);
  if (rw) {
    const side = (f, t) => { const xs = [...rd].filter(([d]) => d >= f && d <= t); return xs.length ? { v: xs.reduce((s, [, v]) => s + v, 0) / xs.length, n: xs.length } : null; };
    const b = side(rw.bFrom, rw.bTo), a = side(rw.aFrom, rw.aTo);
    out.readers = { b: b && b.v, a: a && a.v, n: a ? Math.min(a.n, b ? b.n : 0) : 0, prov: 0, win: rw };
  } else out.readers = { b: null, a: null, n: 0, win: null };
  if (gw) {
    const b = gSum(c.gs, gw.bFrom, gw.bTo), a = gSum(c.gs, gw.aFrom, gw.aTo);
    out.clicks = { b: b.c / gw.n, a: a.c / gw.n }; out.impressions = { b: b.i / gw.n, a: a.i / gw.n };
    out.ctr = { b: b.ctr, a: a.ctr }; out.position = { b: b.pos, a: a.pos };
    for (const k of ['clicks', 'impressions', 'ctr', 'position']) Object.assign(out[k], { n: gw.n, prov: gw.prov, win: gw });
  } else for (const k of ['clicks', 'impressions', 'ctr', 'position']) out[k] = { b: null, a: null, n: 0, win: null };
  const keys = ['readers', 'clicks', 'impressions', 'ctr', 'position'];
  for (const k of keys) out[k].verdict = verdictJS(k, out[k].b, out[k].a, out[k].n, out[k].prov);
  out.verdict = overallJS(keys.map(k => out[k].verdict));
  return out;
}
/** Readers a day over a cluster's pages: Map(day -> readers), whole verified days only. */
function clusterReaders(ps) {
  const m = new Map();
  for (const p of ps) for (const d of p.days) { const v = readersOn(d); if (v != null) m.set(d.day, (m.get(d.day) || 0) + v); }
  return new Map([...m].sort());
}
const CL_HEAD = { 'Mostly positive': 'Winning.', 'Mostly negative': 'Losing ground.', Mixed: 'Mixed.', 'No clear change': 'No clear change.', 'Too early to tell': 'Too early to call.' };
const baTxt = (r, f) => `${f(r.b)} → ${f(r.a)}`;
const F1 = v => v == null ? '–' : (+v).toFixed(1);
function impSpark(c, w = 110, h = 26) {
  const [, last] = gBounds(), from = addDays(last, -89), by = new Map(c.gs.map(r => [r[0], r[2]]));
  const vals = []; for (let d = from; d <= last; d = addDays(d, 1)) vals.push(by.get(d) || 0);
  const max = Math.max(1, ...vals), n = vals.length, pts = vals.map((v, i) => [1 + i * (w - 2) / (n - 1), h - 2 - v / max * (h - 6)]);
  const d = smoothPath(pts);
  return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" role="img" aria-label="Google impressions a day, last 90 days"><title>Google impressions a day, ${esc(spanText(from, last))}</title><path d="${d}L${w - 1} ${h}L1 ${h}Z" fill="var(--s-impressions)" opacity=".12"/><path d="${d}" fill="none" stroke="var(--s-impressions)" stroke-width="1.3"/></svg>`;
}

/* ---------- the Clusters list ---------- */
function renderClusters() {
  if (state.cluster) return renderCluster((DATA.clusters || []).find(c => c.id === state.cluster));
  const N = +state.win, list = (DATA.clusters || []).map(c => ({ c, x: clusterImpact(c, N) }));
  const box = $('#v-clusters');
  if (!list.length) { box.innerHTML = '<div class="empty">No clusters in data.json yet: run python3 tracker.py sync and report.</div>'; return; }
  const ch = list.filter(r => r.x.changed), un = list.filter(r => !r.x.changed);
  const count = v => ch.filter(r => r.x.verdict === v).length;
  const imp = rs => { const g = rs.reduce((s, r) => ({ b: s.b + (r.x.impressions.b || 0), a: s.a + (r.x.impressions.a || 0) }), { b: 0, a: 0 }); return g; };
  const gi = imp(ch), ui = imp(un), pc = g => g.b ? Math.round(100 * (g.a - g.b) / g.b) : null;
  const sgn = v => v == null ? '–' : (v > 0 ? '+' : '') + v + '%';
  const judged = ch.filter(r => r.x.verdict !== 'Too early to tell');
  const answer = `<b>${judged.length ? `${count('Mostly positive')} winning, ${count('Mostly negative')} losing.` : 'Too early to call.'}</b> We changed pages in ${ch.length} of ${list.length} clusters; ${judged.length ? `${ch.length - judged.length} are still too early to judge` : 'none has 7 whole, final days after its first change yet'}. The clusters we did not touch moved ${pc(ui) == null ? 'no measurable amount' : pc(ui) > 0 ? 'up' : 'down'} in Google impressions over the same days, which shows how much of any move is Google, not us.`;
  const proof = `<div class="cards">${card('Changed clusters: impressions a day', sgn(pc(gi)), `${fmtN(gi.b)} → ${fmtN(gi.a)}`)}${card('Untouched clusters: impressions a day', sgn(pc(ui)), `${fmtN(ui.b)} → ${fmtN(ui.a)}`)}${card('Clusters changed', `${ch.length} / ${list.length}`)}${card('Clusters judged', `${judged.length} / ${ch.length}`, judged.length ? '' : 'needs 7 whole, final days')}</div>`;
  const [, last] = gBounds(), ctx = whyContext(addDays(last, -13), last, null);
  const rows = list.map(({ c, x }) => `<tr class="row crow" data-cluster="${esc(c.id)}"><td><a class="linkbtn" href="${esc(hrefFor({ view: 'clusters', cluster: c.id }))}" data-cluster="${esc(c.id)}" data-fk="cl-${esc(c.id)}">${esc(c.name)}</a><div class="kind">${plural(x.pages, 'page')}</div></td>
    <td class="num">${x.changed ? `${x.changed} changed<div class="kind">first ${esc(shortDay(x.d0))}</div>` : '<span class="na">not changed</span>'}</td>
    <td>${x.changed ? opill(x.verdict) : `${opill(x.verdict)}<div class="kind">around the first change, for comparison</div>`}</td>
    <td class="num r">${baTxt(x.impressions, fmtN)}<div class="kind">${changeCell('impressions', x.impressions.b, x.impressions.a)}</div></td><td class="num r">${baTxt(x.clicks, F1)}</td><td class="num r">${baTxt(x.position, F1)}</td><td class="num r hide-sm">${baTxt(x.readers, F1)}</td><td class="hide-sm num">${clusterTop(pagesOf(c))}</td><td class="hide-sm">${impSpark(c)}</td></tr>`).join('');
  box.innerHTML = answerBlock({ answer, proof, why: ctx.why, next: ctx.next.concat(['Open a cluster to see its pages and timeline; compare a changed cluster with an untouched one before deciding anything.']), whyNote: ctx.note })
    + `<h2 class="sec">Every sitemap cluster, before vs after its first change</h2>
    <div class="bar" role="group" aria-label="Window length"><span class="lbl">Window</span><span class="chips-seg">${['7', '14'].map(w => `<button type="button" class="chip" data-win="${w}" data-fk="cwin-${w}" aria-pressed="${state.win === w}">${w} days each side</button>`).join('')}</span></div>
    <div class="box"><table><thead><tr><th>Cluster</th><th>Our changes</th><th>Impact</th><th class="r">Impressions/day</th><th class="r">Clicks/day</th><th class="r">Position</th><th class="r hide-sm">Readers/day</th><th class="hide-sm">Time on page</th><th class="hide-sm">Impressions, 90 days</th></tr></thead><tbody>${rows}</tbody></table></div>
    <p class="rules">Clusters and their pages come from the site's sitemap, grouped by the rules in growth.json. ${esc(VERDICT_RULES)}</p>`;
}

/* ---------- one cluster ---------- */
function clusterNext(c, x) {
  const out = [];
  if (!x.changed) out.push('Nothing to judge: we have not changed this cluster. Use it as the yardstick for the changed ones.');
  else if (x.verdict === 'Too early to tell') out.push(`Do not change this cluster's pages again yet. Look again around ${esc(longDay(addDays(x.d0, 10)))}, when 7 whole, final Google days exist after its first change.`);
  else if (x.verdict === 'Mostly negative') out.push('Open the pages that lost most (sort the table by Google) and check their Changes and Google tabs before changing anything.');
  else if (x.verdict === 'Mostly positive') out.push('Keep the pattern: apply what worked here to the next cluster.');
  else out.push('Check which pages moved most in the table below before deciding.');
  const unknown = pagesOf(c).filter(p => p.index && p.index.status === 'unknown_to_google');
  if (unknown.length) out.push(`Ask Google to index ${unknown.length === 1 ? 'this page' : 'these pages'}: ${unknown.map(p => esc(p.slug)).join(', ')} (Search Console, URL Inspection, "Request indexing").`);
  return out;
}
function renderCluster(c) {
  const box = $('#v-clusters'); if (!c) { box.innerHTML = ''; return; }
  const N = +state.win, x = clusterImpact(c, N), ps = pagesOf(c);
  const judged = ['readers', 'clicks', 'impressions', 'position'].filter(k => x[k].verdict !== 'too early');
  const better = judged.filter(k => x[k].verdict === 'better').map(k => SHORT[k]), worse = judged.filter(k => x[k].verdict === 'worse').map(k => SHORT[k]);
  let answer;
  if (!x.changed) answer = `<b>No changes yet.</b> We have not changed any of its ${ps.length} pages. Over the same days as our first changes elsewhere (around ${esc(longDay(x.d0))}) it moved like this, which is what Google alone did:`;
  else answer = `<b>${CL_HEAD[x.verdict]}</b> Since our first change here on ${esc(longDay(x.d0))} (${x.changed} of ${ps.length} pages changed), against the ${N} days before: ` + (judged.length
    ? [better.length ? `${better.join(', ')} better` : '', worse.length ? `${worse.join(', ')} worse` : '', `${judged.length - better.length - worse.length} with no clear change`].filter(Boolean).join('; ') + '.'
    : 'no measure has 7 whole, final days after it yet.');
  const pc = (k, label, f) => `<div class="card"><span>${esc(label)}</span><b>${copyable(baTxt(x[k], f), { label })}</b><span class="cmp">${badge(x[k].verdict)} ${changeCell(k, x[k].b, x[k].a)}</span></div>`;
  const proof = `<div class="cards">${pc('readers', 'Readers a day', F1)}${pc('clicks', 'Google clicks a day', F1)}${pc('impressions', 'Google impressions a day', fmtN)}${pc('position', 'Average position', F1)}</div>`;
  const w = x.clicks.win || x.readers.win, ctx = whyContext(w ? w.bFrom : addDays(x.d0, -N), w ? w.aTo : gBounds()[1], ps, c.gs);
  const rd = clusterReaders(ps);
  const rows = pageRows(c.id);
  const groups = [{ rows: rows.filter(r => r.p.main), title: `Changed by us <span class="kind">${rows.filter(r => r.p.main).length}</span>` },
    { rows: rows.filter(r => !r.p.main), title: `Not changed <span class="kind">${rows.filter(r => !r.p.main).length}</span>` }];
  const hub = c.hub || '/';
  box.innerHTML = `<div class="phead"><div class="phead-top"><div style="min-width:0"><div class="ktag">Sitemap cluster</div><h1 id="cluster-title" tabindex="-1">${esc(c.name)}</h1>
      <div class="path">${copyable(c.sitemap, { label: 'sitemap', url: c.sitemap })} · hub ${pathCopy(hub, 'cluster hub')}</div></div>
      <a class="backlink" href="${esc(hrefFor({ view: 'clusters', cluster: '' }))}" data-nav="clusters" data-fk="cl-back">← All clusters</a></div>
    <div class="facts">${[['Pages', ps.length], ['Changed by us', x.changed ? `${x.changed} · first ${esc(shortDay(x.d0))}` : '<span class="na">none</span>'], [`Impact (${N}-day windows)`, opill(x.verdict)],
      ['Time on page (Skald)', clusterTop(ps)], ['Leads (proven, Skald)', leadsFact(ps, N)], ['AI crawlers', aiCrawlFact(ps)], ['Google, ' + range().label, (() => { const g = gSum(c.gs, range().from, range().to); return `${fmtN(g.c)} clicks · ${fmtN(g.i)} impr. · pos ${g.pos == null ? '–' : g.pos.toFixed(1)}`; })()]].map(([k, v]) => `<div class="fact"><span>${esc(k)}</span><b>${v}</b></div>`).join('')}</div></div>
    ${findingsBox(((DATA.findings || {}).clusters || {})[c.id], clusterNote(c.id))}
    ${answerBlock({ answer, proof, why: ctx.why, next: ctx.next.concat(clusterNext(c, x)), whyNote: ctx.note })}
    <div class="bar" role="group" aria-label="Window length"><span class="lbl">Window</span><span class="chips-seg">${['7', '14'].map(v => `<button type="button" class="chip" data-win="${v}" data-fk="clwin-${v}" aria-pressed="${state.win === v}">${v} days each side</button>`).join('')}</span></div>
    <h2 class="sec">Timeline</h2>${rangeBar('c')}${chartControls(true)}${googleCharts(c.gs, rd, chartNotes(ps), mainWidth() - 26)}
    ${crossCheck(c.gs, ps, 'This cluster, all its pages')}
    ${skaldSection(ps, x.changed ? x.d0 : null, 'This cluster, all its pages (leads and next pages: its changed pages, each around its own main change)')}
    ${competingSection(ps.map(p => p.path), { h: 'Its pages competing for the same search', max: 12 })}
    <h2 class="sec">Its pages</h2>
    <div class="bar"><span class="sub">Sorted by the column you pick; the same sort as the Pages list.</span></div>
    <div class="box"><table><thead><tr>${theadHTML()}</tr></thead><tbody>${groupedRows(groups, 'copen')}</tbody></table></div>
    <p class="rules">${esc(VERDICT_RULES)}</p>`;
  if (box.dataset.shown !== c.id) { box.dataset.shown = c.id; const t = $('#cluster-title'); if (t && !box.contains(document.activeElement)) t.focus({ preventScroll: true }); }
}
