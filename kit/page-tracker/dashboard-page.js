'use strict';
/* The page screen (?page=<path>&tab=<tab>): a full page, not a dialog. Breadcrumbs (dashboard.js), an "All pages"
   link, a slim header with the page's key facts, then the tabs full width: Impact (dashboard-impact.js), Readers,
   Google, Changes, Milestones. Esc or "All pages" return to the list with its filters and scroll position. */

function bars(obj, label) {
  const e = Object.entries(obj).sort((a, b) => b[1] - a[1]).slice(0, 8), max = Math.max(1, ...e.map(x => x[1]));
  return `<h3>${label}</h3>` + (e.length ? `<div class="hbars">${e.map(([k, v]) => `<div><span>${copyable(k, { label: label.toLowerCase().replace('readers by ', '') })}</span><i style="width:${Math.max(2, v / max * 100)}%"></i><span class="num">${v}</span></div>`).join('')}</div>` : '<div class="na">No data yet</div>');
}
function tabReaders(p, w) {
  const sum = f => { const o = {}; p.days.filter(d => d.state === 'ok').forEach(d => { for (const [k, v] of Object.entries(f(d))) o[k] = (o[k] || 0) + v; }); return o; };
  const c = (k, v, sub = '') => card(k, v, sub);
  const points = p.days.map(d => ({ d: d.day, v: readersOn(d), prov: false }));
  const n = points.length;
  return `<div class="cards">${c('Readers a day before', fmt(w.pb), w.nb ? w.nb + ' days' : '')}${c('Readers a day after', fmt(w.pa), w.na ? w.na + ' days' : '')}${c('Search-engine visits, before → after', `${w.sb ?? '–'} → ${w.sa ?? '–'}`, 'Skald, all engines')}
   ${c('Bounce, last 7 days', w.bounce ? w.bounce.pct + '%' : '–', w.bounce ? w.bounce.went + ' of ' + w.bounce.landed + ' went on to another page' : 'no landings yet')}${c('Googlebot first fetch', w.google === 'not yet' ? 'not yet' : shortDay(w.google))}</div>
   ${annChips()}
   <div class="charts"><div class="chart"><div class="chart-h"><b><i style="background:${SERIES_COLOR.readers}"></i>Readers a day (Skald)</b><span class="sub">${n ? esc(spanText(points[0].d, points[n - 1].d)) + `, ${n} days` : ''}${state.country ? ` · readers from ${esc(state.country)} only` : ''} · gaps = days Skald has not verified</span></div>
   ${lineChart({ points, width: mainWidth() - 26, height: 130, label: 'Readers', valueFmt: fmtN, notes: chartNotes(p), color: SERIES_COLOR.readers, int: true })}</div></div>
   ${bars(sum(d => d.sources), 'Readers by source')}
   ${skaldSection([p], p.main && day(p.main), 'This page')}`;
}
function indexBox(p) {
  const ix = p.index;
  if (!ix) return `<div class="status warn"><b>Index status: not checked yet.</b> Google's URL Inspection has not been run for this page.</div>`;
  const when = ix.at ? longDay(ix.at.slice(0, 10)) : '–';
  const crawl = ix.last_crawl ? ix.last_crawl.slice(0, 10) : null;
  let words, cls;
  if (ix.status === 'indexed') {
    cls = 'good';
    words = 'Google has this page in its index, so it can show it in search results.';
    if (crawl && p.main) words += day(crawl) < day(p.main)
      ? ` Google last crawled it on ${longDay(crawl)}, before the main change went live (${longDay(day(p.main))}), so results still reflect the old version until it crawls again.`
      : ` Google last crawled it on ${longDay(crawl)}, after the main change went live, so it has seen the new version.`;
    else if (crawl) words += ` Google last crawled it on ${longDay(crawl)}.`;
  } else if (ix.status === 'unknown_to_google') {
    cls = 'bad';
    words = 'Google has not seen this address yet, so it cannot show it in results. New or renamed pages often take days to a few weeks; being in the sitemap and linked from other pages helps Google find it.';
  } else { cls = 'warn'; words = 'Google knows the page but it is not in the index right now. See the coverage note for the reason.'; }
  return `<div class="status ${cls}"><b>Index status: ${esc((ix.status || '').replace(/_/g, ' '))}</b> (Google: "${copyable(ix.coverage || '–', { label: 'coverage note' })}", checked ${esc(when)}).<br>${esc(words)}</div>`;
}
function tabGoogle(p) {
  let ba = '';
  if (p.main) {
    const d0 = day(p.main), [, last] = gBounds();
    const n = Math.max(0, Math.min(28, daysBetween(d0, last) - 1));
    if (n >= 1) {
      const a = gSum(p.gs, addDays(d0, 1), addDays(d0, n)), b = gSum(p.gs, addDays(d0, -n), addDays(d0, -1));
      const per = (x, k) => x.n ? x[k] / x.n : null;
      const c = (k, bv, av, f, better = 'up') => card(k, `${f(bv)} → ${f(av)}`, cmpLine(av, bv, better, f));
      ba = `<h3>Before vs after the main change (${n} day${n > 1 ? 's' : ''} each side)</h3>
        <p class="sub">Before: ${esc(spanText(addDays(d0, -n), addDays(d0, -1)))}. After: ${esc(spanText(addDays(d0, 1), addDays(d0, n)))}. The change day itself (${esc(longDay(d0))}) is left out.${a.prov ? ` ${a.prov} of the after days are provisional, so read this as early.` : ''}</p>
        <div class="cards">${c('Clicks a day', per(b, 'c'), per(a, 'c'), fmt)}${c('Impressions a day', per(b, 'i'), per(a, 'i'), fmt)}${c('CTR', b.ctr, a.ctr, v => pct(v))}${c('Average position', b.pos, a.pos, v => v == null ? '–' : v.toFixed(1), 'down')}</div>`;
    } else ba = `<p class="sub">The main change went live on ${esc(longDay(d0))}; Google has no whole day after it yet, so there is no before and after.</p>`;
  } else ba = '<p class="sub">No change recorded for this page, so there is no before and after.</p>';
  const readers = new Map(p.days.filter(d => d.state === 'ok').map(d => [d.day, readersOn(d)]));
  return `${indexBox(p)}${ba}
    <h2 class="sec">Day by day</h2>${rangeBar('d')}${chartControls(true)}${googleCharts(p.gs, readers, chartNotes(p), mainWidth() - 26)}
    ${crossCheck(p.gs, [p], 'This page')}
    ${competingSection([p.path], { h: 'Searches this page shares with our other pages' })}
    <div class="grid2"><div><h3>Top searches</h3>${topTable(p.gq, 'Search', 'query')}</div><div><h3>Top countries</h3>${topTable(p.gc, 'Country', 'country')}</div></div>
    <p class="sub">Searches and countries: Google's last 28 days as of ${p.gsnap ? esc(longDay(p.gsnap)) : '–'}, page copies added together. Readers in the chart are Skald's.</p>${splitBox(p)}`;
}
/** Google's figures per address when a page has old addresses (growth.json page_aliases / redirects_file). */
function splitBox(p) {
  if (!p.split || !p.split.length) return '';
  return `<h3>Which address Google shows</h3><div class="box"><table><thead><tr><th>Address</th><th class="r">Clicks</th><th class="r">Impressions</th></tr></thead><tbody>${
    p.split.map(r => `<tr><td>${copyable(r[0], { label: 'address' })}</td><td class="num r">${fmtN(r[1])}</td><td class="num r">${fmtN(r[2])}</td></tr>`).join('')}</tbody></table></div><p class="sub">All addresses are added together in the numbers above.</p>`;
}
function tabMilestones(p) {
  const ms = p.milestones.map(m => `<div><span>${esc(m.kind.replace(/_/g, ' '))}${m.who ? ' · ' + copyable(m.who, { label: 'crawler name' }) : ''}</span><span class="num">${esc(m.at.slice(0, 16).replace('T', ' '))}</span></div>`).join('');
  return `<h3>Crawler and first-visit milestones</h3><div class="kv">${ms || '<div class="na">None yet</div>'}</div>`;
}

/** The slim header: what the page is and its key facts. */
function pageHead(p) {
  const r = range(), g = gSum(p.gs, r.from, r.to), o = pageOverall(p), ix = p.index;
  const fact = (label, html) => `<div class="fact"><span>${esc(label)}</span><b>${html}</b></div>`;
  const ixTxt = !ix ? '<span class="na">not checked</span>' : ix.status === 'indexed' ? '<span class="up">indexed</span>' : `<span class="down">${esc(ix.status.replace(/_/g, ' '))}</span>`;
  return `<div class="phead"><div class="phead-top"><div style="min-width:0"><div class="ktag">${esc(p.kind)}</div>
      <h1 id="page-title" tabindex="-1">${esc(p.title || p.slug)}</h1><div class="path">${pathCopy(p.path)}</div></div>
      <a class="backlink" href="${esc(hrefFor({ page: '', tab: 'impact', view: 'pages' }))}" data-back data-fk="back">← All pages</a></div>
    <div class="facts">
      ${fact('Main change live', p.main ? esc(new Date(p.main).toLocaleString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: TZ_NAME })) : '<span class="na">no change</span>')}
      ${fact(`Impact (${state.win}-day windows)`, o ? opill(o.verdict) : '<span class="na">nothing to judge</span>')}
      ${fact(`Google, ${r.label.replace(/^last /, 'last ')}`, `${fmtN(g.c)} clicks · ${fmtN(g.i)} impr. · pos ${g.pos == null ? '–' : g.pos.toFixed(1)}`)}
      ${fact('Index status', ixTxt)}
      ${fact('Time on page (Skald)', topLine(p))}
      ${fact('Leads (proven, Skald)', leadsFact([p], +state.win))}
      ${fact('AI crawlers', aiCrawlFact([p]))}
      ${fact('Google Analytics (its own count)', gaFact(p))}
      ${fact('Live page', `<a href="${esc(SITE + p.path)}" target="_blank" rel="noopener">${esc(SITE.replace(/^https?:\/\//, ''))}${esc(p.path)} ↗</a>`)}
    </div></div>`;
}
function renderPage(p) {
  const box = $('#v-page'), fresh = box.dataset.path !== p.path;
  box.dataset.path = p.path;
  const body = { impact: () => tabImpact(p), readers: () => tabReaders(p, windows(p)) + gaNote(), google: () => tabGoogle(p), changes: () => tabChangesDiff(p), milestones: () => tabMilestones(p) }[state.tab]();
  box.innerHTML = `${pageHead(p)}${findingsBox(((DATA.findings || {}).pages || {})[p.path])}
    <div class="ptabs" role="tablist" aria-label="Page sections">${Object.entries(TABS).map(([k, v]) => `<button type="button" class="tab" role="tab" id="ptab-${k}" data-tab="${k}" data-fk="tab-${k}" aria-selected="${state.tab === k}" aria-controls="page-body" tabindex="${state.tab === k ? 0 : -1}">${v}</button>`).join('')}</div>
    <div id="page-body" role="tabpanel" aria-labelledby="ptab-${state.tab}">${body}</div>`;
  if (fresh && !(document.activeElement && document.activeElement.dataset && document.activeElement.dataset.fk && box.contains(document.activeElement))) $('#page-title').focus({ preventScroll: true });
}
