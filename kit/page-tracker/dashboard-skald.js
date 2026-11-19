'use strict';
/* More from Skald (added 13 Nov 2026), per page and per cluster, before vs after our changes. Counts only: nothing
   personal is in data.json (no name, email or address).
   - Leads: visits proven to have sent a form (page_journeys, each page's own windows around its main change); the
     whole site's contact forms and other actions a day (conversions). Skald's lead database (leads) is not set up for
     this site, so no figure from it is shown.
   - AI assistants that sent visitors (daily assistants), AI crawlers that read the page (daily ai_training: fetches to
     train or index; ai_asked: fetched because someone asked an assistant).
   - Countries (Skald readers) before vs after, next to Google's countries.
   - Where readers went next (page_journeys), grouped by the kind of page. */

/** Before/after windows of whole verified Skald days around day d0, N days each side (like rwinJS). */
const skaldWin = (d0, N) => rwinJS(d0, N);
function sumDays(pages, from, to, f) {
  let n = 0; const days = new Set();
  for (const p of pages) for (const d of p.days) if (d.state === 'ok' && d.day >= from && d.day <= to) { n += f(d) || 0; days.add(d.day); }
  return { n, days: days.size };
}
function sumObj(pages, from, to, key) {
  const o = {};
  for (const p of pages) for (const d of p.days) if (d.state === 'ok' && d.day >= from && d.day <= to) for (const [k, v] of Object.entries(d[key] || {})) o[k] = (o[k] || 0) + v;
  return o;
}
/** Journey windows of the pages, summed: their own main-change windows, N days. */
function journeys(pages, N) {
  const out = { before: { visits: 0, lead: 0, next: {} }, after: { visits: 0, lead: 0, next: {} }, pages: 0 };
  for (const p of pages) {
    if (!p.main) continue;
    const ws = (p.jw || []).filter(w => w.change_at === p.main && w.win === N);
    if (ws.length) out.pages++;
    for (const w of ws) {
      const o = out[w.side]; if (!o) continue;
      o.visits += w.visits || 0; o.lead += w.lead || 0;
      for (const [k, v] of Object.entries(w.next || {})) o.next[k] = (o.next[k] || 0) + v;
    }
  }
  return out;
}
/* Google names countries with 3-letter codes, Skald with 2-letter ones. */
const ISO3 = { usa: 'US', can: 'CA', gbr: 'GB', ind: 'IN', aus: 'AU', deu: 'DE', fra: 'FR', pol: 'PL', esp: 'ES', nld: 'NL', bra: 'BR', phl: 'PH',
  pak: 'PK', nga: 'NG', zaf: 'ZA', ita: 'IT', mex: 'MX', irl: 'IE', nzl: 'NZ', sgp: 'SG', are: 'AE', isr: 'IL', tur: 'TR', nor: 'NO', swe: 'SE',
  dnk: 'DK', fin: 'FI', che: 'CH', aut: 'AT', bel: 'BE', prt: 'PT', idn: 'ID', mys: 'MY', tha: 'TH', vnm: 'VN', jpn: 'JP', kor: 'KR', chn: 'CN',
  hkg: 'HK', twn: 'TW', egy: 'EG', ken: 'KE', mar: 'MA', sau: 'SA', arg: 'AR', col: 'CO', chl: 'CL', per: 'PE', rou: 'RO', cze: 'CZ', hun: 'HU',
  ukr: 'UA', rus: 'RU', grc: 'GR', bgd: 'BD', lka: 'LK', npl: 'NP', ecu: 'EC', uzb: 'UZ', civ: 'CI' };
const pageKind = path => {
  if (path === '(left the site)') return 'Left the site';
  const p = DATA.pages.find(x => x.path === path);
  const conv = (DATA.config && DATA.config.conversion_path) || '';
  if ((conv && path.replace(/\/$/, '') === conv.replace(/\/$/, '')) || /thank-you/.test(path)) return 'Contact page';
  if (p) return { review: 'Reviews', comparison: 'Comparisons', alternatives: 'Alternatives', migration: 'Migration pages', guide: 'Guides', page: 'Main pages' }[p.kind] || 'Other pages';
  return 'Other pages';
};

/* ---------- one-line facts for headers ---------- */
function leadsFact(pages, N) {
  const j = journeys(pages, N);
  if (!j.pages) return '<span class="na">no change to compare</span>';
  return `${j.before.lead} → ${j.after.lead} <span class="kind">visits that sent a form, ${N} days each side</span>`;
}
function aiCrawlFact(pages) {
  let lastDay = '', n7 = 0; const [, newest] = [null, newestOk()], from = addDays(newest, -6);
  for (const p of pages) for (const d of p.days) { if ((d.ai_training || 0) + (d.ai_asked || 0) > 0 && d.day > lastDay) lastDay = d.day; if (d.day >= from && d.day <= newest) n7 += (d.ai_training || 0) + (d.ai_asked || 0); }
  return lastDay ? `last ${esc(shortDay(lastDay))} <span class="kind">· ${n7} fetches in 7 days</span>` : '<span class="na">none seen</span>';
}

/* ---------- the Skald section (page Readers tab, cluster screen) ---------- */
function skaldSection(pages, d0, what) {
  const N = +state.win, w = d0 && skaldWin(d0, N), j = journeys(pages, N);
  const ba = (b, a) => `${b} → ${a}`;
  let html = `<h2 class="sec">More from Skald: leads, AI, countries, next pages</h2><p class="sub">${esc(what)}${w ? `; before ${esc(spanText(w.bFrom, w.bTo))}, after ${esc(spanText(w.aFrom, w.aTo))} (whole verified days, change day left out)` : d0 ? '; the change is too new for a whole day after it, so the last 7 days are set against the 7 before' : '; no change to compare, so the last 7 days are set against the 7 before'}. Counts only, nothing personal.</p>`;
  const conv = DATA.conversions || {};
  // leads
  html += `<div class="cards">${card('Visits that sent a form', j.pages ? ba(j.before.lead, j.after.lead) : '–', j.pages ? `of ${j.before.visits} → ${j.after.visits} visits, ${N} days each side` : 'no change to compare')}`;
  // AI crawlers and assistants
  const [fb, tb, fa, ta] = w ? [w.bFrom, w.bTo, w.aFrom, w.aTo] : [addDays(newestOk(), -13), addDays(newestOk(), -7), addDays(newestOk(), -6), newestOk()];
  const cb = sumDays(pages, fb, tb, d => d.ai_training), ca = sumDays(pages, fa, ta, d => d.ai_training);
  const kb = sumDays(pages, fb, tb, d => d.ai_asked), ka = sumDays(pages, fa, ta, d => d.ai_asked);
  html += `${card('AI crawler fetches', ba(cb.n, ca.n), `to train or index · ${aiCrawlFact(pages).replace(/<[^>]+>/g, '')}`)}${card('Fetched for someone\'s question', ba(kb.n, ka.n), 'an assistant read it to answer')}`;
  const ab = sumObj(pages, fb, tb, 'assistants'), aa = sumObj(pages, fa, ta, 'assistants');
  const an = (o) => Object.values(o).reduce((s, v) => s + v, 0);
  html += `${card('Visitors sent by AI assistants', ba(an(ab), an(aa)), Object.keys({ ...ab, ...aa }).map(k => `${esc(k)} ${ab[k] || 0}→${aa[k] || 0}`).join(', ') || 'none yet')}</div>`;
  html += `<p class="sub">Whole site: ${(conv.days || []).reduce((s, d) => s + d[1], 0)} completed actions (${Object.entries(conv.by_action || {}).map(([k, v]) => `${esc(k)} ${v}`).join(', ') || 'none'}) since ${conv.days && conv.days.length ? esc(shortDay(conv.days[0][0])) : '–'}; Skald tied ${(conv.days || []).reduce((s, d) => s + d[4], 0)} of them to the page they happened on. ${conv.leads_available ? '' : 'Skald\'s lead database is not set up for this site, so no figure from it is shown.'}</p>`;
  // countries next to Google's
  const rb = sumObj(pages, fb, tb, 'countries'), ra = sumObj(pages, fa, ta, 'countries');
  const gc = new Map(); for (const p of pages) for (const r of p.gc || []) { const k = ISO3[r[0].toLowerCase()] || r[0].toUpperCase(); gc.set(k, (gc.get(k) || 0) + r[1]); }
  const cs = [...new Set([...Object.keys(rb), ...Object.keys(ra)])].sort((x, y) => ((ra[y] || 0) + (rb[y] || 0)) - ((ra[x] || 0) + (rb[x] || 0))).slice(0, 10);
  const nx = (o) => { const g = {}; for (const [k, v] of Object.entries(o)) { const kk = pageKind(k); g[kk] = (g[kk] || 0) + v; } return g; };
  const nb = nx(j.before.next), na = nx(j.after.next), kinds = [...new Set([...Object.keys(nb), ...Object.keys(na)])].sort((x, y) => (na[y] || 0) + (nb[y] || 0) - (na[x] || 0) - (nb[x] || 0));
  const share = (o, k) => { const t = Object.values(o).reduce((s, v) => s + v, 0); return t ? Math.round(100 * (o[k] || 0) / t) + '%' : '–'; };
  html += `<div class="grid2"><div><h3>Countries: Skald readers before → after${gc.size ? ', Google clicks (28 days)' : ''}</h3>${cs.length ? `<div class="box"><table><thead><tr><th>Country</th><th class="r">Readers</th>${gc.size ? '<th class="r">Google clicks</th>' : ''}</tr></thead><tbody>${cs.map(k => `<tr><td>${copyable(k, { label: 'country' })}</td><td class="num r">${rb[k] || 0} → ${ra[k] || 0}</td>${gc.size ? `<td class="num r">${gc.has(k) ? fmtN(gc.get(k)) : '–'}</td>` : ''}</tr>`).join('')}</tbody></table></div>` : '<div class="empty">No verified days yet.</div>'}</div>
    <div><h3>Where readers went next (share of visits)</h3>${kinds.length ? `<div class="box"><table><thead><tr><th>Next</th><th class="r">Before</th><th class="r">After</th></tr></thead><tbody>${kinds.map(k => `<tr><td>${esc(k)}</td><td class="num r">${share(nb, k)}</td><td class="num r">${share(na, k)}</td></tr>`).join('')}</tbody></table></div>
      <p class="sub">Top next pages after: ${Object.entries(j.after.next).filter(([k]) => k !== '(left the site)').sort((a, b) => b[1] - a[1]).slice(0, 5).map(([k, v]) => `${pathCopy(k)} ${v}`).join(', ') || 'none yet'}.</p>` : '<div class="empty">No change windows yet (page_journeys).</div>'}</div></div>`;
  return html;
}
