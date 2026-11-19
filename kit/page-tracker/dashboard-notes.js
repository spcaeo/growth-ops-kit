'use strict';
/* Chart notes, Ahrefs style: small lettered circles sitting on the x-axis of every time chart, each with a tooltip on
   hover or focus, for (a) our changes (from the changes table) and (b) Google's own Search updates (core, spam, other;
   from Google's Search Status Dashboard, google_updates.py), whose start-to-end rollout is shaded as a band. Which
   notes show is in the URL (key ann). Also the "why it moved" and "what to do next" facts that every screen shows.
   Uses dashboard.js (esc, state, DATA, day, shortDay, fullDay, spanText, addDays, gBounds) and dashboard-charts.js. */

const NOTE = {
  ours: { letter: 'C', color: 'var(--n-ours)', name: 'Our change' },
  edits: { letter: 'E', color: 'var(--n-edit)', name: 'Editor save' },
  core: { letter: 'G', color: 'var(--n-core)', name: 'Google core update' },
  spam: { letter: 'S', color: 'var(--n-spam)', name: 'Google spam update' },
  other: { letter: 'U', color: 'var(--n-other)', name: 'Other Google update' },
};
const annOn = k => state.ann !== 'none' && state.ann.split(',').includes(k);
const gKind = u => u.kind === 'core' ? 'core' : u.kind === 'spam' ? 'spam' : 'other';
const GU = () => (DATA && DATA.gupdates) || { updates: [], ok: false, error: 'not in data.json yet (run tracker.py report)' };
const updateName = u => u.kind === 'issue' ? `${u.name} (${u.service})` : u.name;
const changeWhat = c => { const s = (c.commits || [])[0]; return s ? s.slice(8, 140) : (c.title_after || 'page change'); };

/** Our changes as notes: one per change for a page, one per day (listing the pages) for a group of pages
    (an array: a cluster) or the whole site (null). */
function ourNotes(p) {
  if (p && !Array.isArray(p)) return p.changes.map(c => ({ kind: 'ours', d: day(c.live_at),
    tip: `<b>${c.live_at === p.main ? 'Our main change' : 'Our change'} · ${esc(fullDay(day(c.live_at)))}</b><div>${esc(p.slug)}</div>`
      + (c.title_before !== c.title_after ? `<div>Title: ${esc(c.title_before || '–')} → ${esc(c.title_after || '–')}</div>` : `<div>${esc(c.title_after || '')}</div>`)
      + `<div>Words: ${c.words_before} → ${c.words_after}</div><div class="p">${esc(changeWhat(c))}</div>`,
    label: `${fullDay(day(c.live_at))}: ${c.live_at === p.main ? 'main ' : ''}change to ${p.slug}, ${c.words_before} to ${c.words_after} words` }));
  const byDay = {};
  (Array.isArray(p) ? p : DATA.pages).forEach(pg => pg.changes.forEach(c => { (byDay[day(c.live_at)] = byDay[day(c.live_at)] || []).push({ pg, c }); }));
  return Object.entries(byDay).sort((a, b) => a[0] < b[0] ? -1 : 1).map(([d, list]) => {
    const slugs = [...new Set(list.map(x => x.pg.slug))];
    return { kind: 'ours', d, label: `${fullDay(d)}: our changes went live on ${plural(slugs.length, 'page')}`,
      tip: `<b>Our changes · ${esc(fullDay(d))}</b><div>${plural(slugs.length, 'page')} changed</div><div class="p">${esc(slugs.slice(0, 6).join(', '))}${slugs.length > 6 ? `, and ${slugs.length - 6} more` : ''}</div>` };
  });
}
function googleNotes() {
  return GU().updates.map(u => {
    const b = day(u.begin), e = u.end ? day(u.end) : null;
    return { kind: gKind(u), d: b, end: e || gBounds()[1], open: !e, name: updateName(u),
      label: `${updateName(u)}: ${shortDay(b)} to ${e ? shortDay(e) : 'still rolling out'}`,
      tip: `<b>${esc(updateName(u))}</b><div>${esc(fullDay(b))} → ${e ? esc(fullDay(e)) : 'still rolling out'}</div>${u.note ? `<div class="p">${esc(u.note.slice(0, 160))}</div>` : ''}<div class="p">Source: Google Search Status Dashboard</div>` };
  });
}
/** The notes a chart shows, given the toggles in the URL. p = a page, an array of pages, or null for the whole site. */
function chartNotes(p) {
  return [...(annOn('ours') ? ourNotes(p) : []), ...(annOn('edits') ? editNotes(p) : []), ...googleNotes().filter(n => annOn(n.kind))];
}

/** SVG for the notes of one chart: Google rollout bands, faint dashed lines for our changes, lettered markers on the axis. */
function notesSVG(notes, points, { x, step, L, T, ih, iw, weekly }) {
  if (!notes || !notes.length || !points.length) return '';
  const first = points[0].d, lastP = points[points.length - 1].d, lastD = weekly ? addDays(lastP, 6) : lastP;
  const idx = d => { if (d < first || d > lastD) return null; let i = 0; while (i + 1 < points.length && points[i + 1].d <= d) i++; return i; };
  let bands = '', lines = '';
  const marks = [];
  for (const n of notes) {
    if (n.end) {  // a Google rollout: band from its start to its end (or to the newest day while still rolling out)
      const a = n.d < first ? 0 : idx(n.d), b = n.end > lastD ? points.length - 1 : idx(n.end);
      if (a == null || b == null || n.end < first) continue;
      const x0 = Math.max(L, x(a) - step / 2), x1 = Math.min(L + iw, x(b) + step / 2);
      bands += `<rect x="${x0.toFixed(1)}" y="${T}" width="${Math.max(2, x1 - x0).toFixed(1)}" height="${ih}" fill="${NOTE[n.kind].color}" opacity=".07"/>`;
      if (n.d >= first) marks.push({ n, x: x(a) });
    } else {
      const i = idx(n.d); if (i == null) continue;
      lines += `<line x1="${x(i)}" x2="${x(i)}" y1="${T}" y2="${T + ih}" stroke="var(--n-ours)" stroke-dasharray="2 3" opacity=".45"/>`;
      marks.push({ n, x: x(i) });
    }
  }
  marks.sort((a, b) => a.x - b.x);
  const groups = [];
  for (const m of marks) { const g = groups[groups.length - 1]; if (g && m.x - g.x0 < 14) g.items.push(m); else groups.push({ x0: m.x, items: [m] }); }
  const cy = T + ih + 9;
  let out = '';
  for (const g of groups) {
    const cx = g.items.reduce((s, m) => s + m.x, 0) / g.items.length, kinds = [...new Set(g.items.map(m => m.n.kind))];
    const one = g.items.length === 1 || kinds.length === 1 && g.items.length < 10;
    const col = kinds.length === 1 ? NOTE[kinds[0]].color : 'var(--fg2)';
    const txt = kinds.length === 1 ? (g.items.length === 1 ? NOTE[kinds[0]].letter : NOTE[kinds[0]].letter + (one ? '' : g.items.length)) : String(g.items.length);
    const tip = g.items.map(m => m.n.tip).join('<hr>');
    const label = g.items.map(m => m.n.label).join('; ');
    out += `<g class="mk" tabindex="0" role="img" aria-label="${esc(label)}" data-tip="${esc(tip)}"><line x1="${cx}" x2="${cx}" y1="${T + ih}" y2="${cy - 6}" stroke="${col}" opacity=".6"/><circle cx="${cx.toFixed(1)}" cy="${cy}" r="6.5" fill="${col}"/><text x="${cx.toFixed(1)}" y="${cy + 3}" text-anchor="middle" class="mkt">${esc(txt.length > 2 ? txt.slice(0, 2) : txt)}</text>${g.items.length > 1 && kinds.length === 1 && txt.length === 1 ? `<circle cx="${(cx + 5).toFixed(1)}" cy="${cy - 5}" r="3" fill="var(--surface)" stroke="${col}"/>` : ''}</g>`;
  }
  return bands + lines + out;
}

/** The note toggles, the measure toggles and a one-line legend, above a set of charts. */
function annChips() {
  const g = GU();
  return `<div class="bar" role="group" aria-label="Chart notes"><span class="lbl">Notes</span>${Object.entries(ANNS).map(([k, v]) =>
    `<button type="button" class="chip" data-ann="${k}" data-fk="ann-${k}" aria-pressed="${annOn(k)}"><i class="nl" style="background:${NOTE[k].color}" aria-hidden="true">${NOTE[k].letter}</i>${v}</button>`).join('')}${
    g.ok ? '' : `<span class="sub down">Google updates: could not read Google's Search Status Dashboard${g.error ? ` (${esc(g.error)})` : ''}, so none are shown.</span>`}</div>`;
}
const chartControls = withReaders => `${metricChips(withReaders)}${annChips()}<div class="legend"><span><i class="sw" style="background:var(--prov);box-shadow:inset 0 0 0 1px var(--flat)"></i>provisional days (Google still counting)</span><span><i class="sw" style="background:var(--n-core);opacity:.25"></i>a Google update rolling out</span><span>hover a day, or a letter on the axis, for details; a number on the axis = several notes on the same day</span></div>`;

/** Why the numbers moved and what to do next, from facts only: our changes, Google's updates, provisional days.
    Between from and to (days); p = a page, an array of pages (a cluster, with its daily Google rows in gsAll), or null
    for the whole site. */
function whyContext(from, to, p, gsAll) {
  const why = [], next = [];
  const [, last] = gBounds();
  const ours = ourNotes(p).filter(n => n.d >= from && n.d <= to);
  if (ours.length) {
    if (p && !Array.isArray(p)) {
      const per = {}; ours.forEach(n => { per[n.d] = (per[n.d] || 0) + 1; });
      const m = p.main && p.changes.find(c => c.live_at === p.main), md = m && day(m.live_at);
      why.push(`<b>Our changes:</b> ${plural(ours.length, 'change')} went live (${Object.entries(per).map(([d, k]) => esc(shortDay(d)) + (k > 1 ? ` ×${k}` : '')).join(', ')})${m && md >= from && md <= to ? `; the main one on ${esc(shortDay(md))} took it from ${m.words_before} to ${m.words_after} words${m.title_before !== m.title_after ? ' and changed the title' : ''}` : ''}. The Changes tab has each one.`);
    }
    else why.push(`<b>Our changes:</b> ${ours.map(n => `${esc(shortDay(n.d))} (${esc(n.label.match(/on (\d+ pages?)/)[1])})`).join(', ')}.`);
  } else why.push(p ? '<b>Our changes:</b> none in this period.' : '<b>Our changes:</b> none went live in this period.');
  const g = GU();
  if (!g.ok) why.push(`<b>Google updates:</b> could not read Google's Search Status Dashboard, so they are not listed.`);
  else {
    const ups = g.updates.filter(u => u.kind !== 'issue' && day(u.begin) <= to && (!u.end || day(u.end) >= from));
    if (ups.length) why.push(`<b>Google updates in this period:</b> ${ups.map(u => `${esc(u.name)}, ${esc(shortDay(day(u.begin)))} → ${u.end ? esc(shortDay(day(u.end))) : '<b>still rolling out</b>'}`).join('; ')}. Rankings move for every site while one rolls out.`);
    else why.push('<b>Google updates:</b> none rolled out in this period.');
    const rolling = g.updates.filter(u => u.kind !== 'issue' && !u.end);
    for (const u of rolling) next.push(`Judge nothing on rankings until Google's ${esc(u.name)} has finished (it started ${esc(shortDay(day(u.begin)))}; Google says such rollouts take up to 2 weeks). Its end date will appear here.`);
  }
  const gs = gsAll || (p && !Array.isArray(p) ? p.gs : DATA.site.gs), prov = (gs || []).filter(r => !r[4] && r[0] >= from && r[0] <= to).length;
  if (prov) why.push(`<b>Provisional days:</b> Google is still counting the last ${plural(prov, 'day')} (to ${esc(shortDay(last))}), so they will rise.`);
  const note = g.ok ? `<p class="sub">Google updates from Google's own Search Status Dashboard, read ${esc(g.fetched ? new Date(g.fetched).toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short', timeZone: TZ_NAME }) : '–')}.</p>` : '';
  return { why, next, note };
}
