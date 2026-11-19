'use strict';
/* Impact tab (page screen) and the Impact summary (Google view). Uses the helpers and the router of
   dashboard.js. The verdict rules match insights.py; keep both in step (README.md, "Verdict rules"). */
const VERDICT_RULES = 'Before vs after use same-length windows (7 or 14 days) and skip the change day. Too early = fewer than 7 whole days after, or provisional Google days in the after window (once 7 final days exist, the window stops at the last final day). No clear change = a move under 20% (or under 1 reader, 1 click or 10 impressions a day; 0.1 point of CTR), average position moving under 1.0, bounce moving under 5 points (and at least 20 landings each side). Lower position and lower bounce are better. Overall: better at least twice as often as worse = mostly positive; the reverse = mostly negative; both = mixed. Google re-ranks pages for 1 to 2 weeks after big changes, so early moves often reverse.';
const FLOOR = { readers: 1, clicks: 1, impressions: 10, ctr: 0.001, leads: 0.3 };

function lastFinal() { const g = DATA.site.gs; if (!g.length) return gBounds()[1]; for (let i = g.length - 1; i >= 0; i--) if (g[i][4]) return g[i][0]; return g[0][0]; }
let NEWEST_OK = null;
function newestOk() {
  if (!NEWEST_OK) NEWEST_OK = DATA.pages.reduce((m, p) => p.days.reduce((mm, d) => d.state === 'ok' && d.day > mm ? d.day : mm, m), '') || gBounds()[1];  // no Skald days yet: the build day
  return NEWEST_OK;
}
const minDay = (a, b) => a < b ? a : b;
/** Google window: up to N days after d0 (change day skipped), same length before. */
function gwinJS(d0, N) {
  const last = gBounds()[1], lf = lastFinal();
  let to = minDay(addDays(d0, N), last);
  if (to > lf && daysBetween(d0, lf) - 1 >= 7) to = minDay(addDays(d0, N), lf);
  const n = daysBetween(d0, to) - 1;
  if (n < 1) return null;
  return { n, bFrom: addDays(d0, -n), bTo: addDays(d0, -1), aFrom: addDays(d0, 1), aTo: to, prov: Math.max(0, daysBetween(lf, to) - 1) };
}
function rwinJS(d0, N) {
  const to = minDay(addDays(d0, N), newestOk()), n = daysBetween(d0, to) - 1;
  return n < 1 ? null : { n, bFrom: addDays(d0, -n), bTo: addDays(d0, -1), aFrom: addDays(d0, 1), aTo: to, prov: 0 };
}
function verdictJS(metric, b, a, n, prov = 0, landings = null) {
  if (NO_DATA || b == null || a == null || n < 7 || prov) return 'too early';
  if (metric === 'bounce' && landings && Math.min(...landings) < 20) return 'too early';
  const diff = a - b;
  let clear;
  if (metric === 'position') clear = Math.abs(diff) >= 1;
  else if (metric === 'bounce') clear = Math.abs(diff) >= 5;
  else { const rel = b ? Math.abs(diff) / b : (diff ? 1 : 0); clear = rel >= 0.2 && Math.abs(diff) >= (FLOOR[metric] || 0); }
  if (!clear) return 'no clear change';
  return (['position', 'bounce'].includes(metric) ? diff < 0 : diff > 0) ? 'better' : 'worse';
}
function overallJS(vs) {
  const v = vs.filter(x => x !== 'too early');
  if (!v.length) return 'Too early to tell';
  const b = v.filter(x => x === 'better').length, w = v.filter(x => x === 'worse').length;
  if (!b && !w) return 'No clear change';
  if (b && b >= 2 * w) return 'Mostly positive';
  if (w && w >= 2 * b) return 'Mostly negative';
  return 'Mixed';
}
const VCLASS = { better: 'v-better', worse: 'v-worse', 'no clear change': 'v-nochange', 'too early': 'v-early' };
const badge = v => `<span class="v ${VCLASS[v] || 'v-nochange'}">${esc(v)}</span>`;
const OCLASS = { 'Mostly positive': 'up', 'Mostly negative': 'down', Mixed: 'flat', 'No clear change': 'na', 'Too early to tell': 'flat' };

const IMETRICS = [
  ['readers', 'Readers a day (Skald)', v => fmt(v)], ['clicks', 'Google clicks a day', v => v == null ? '–' : (+v).toFixed(1)],
  ['impressions', 'Google impressions a day', v => fmtN(v)], ['ctr', 'Google CTR', v => pct(v)],
  ['position', 'Average position (lower is better)', v => v == null ? '–' : (+v).toFixed(1)], ['bounce', 'Bounce (estimate)', v => v == null ? '–' : v.toFixed(0) + '%']];
/** Before vs after one change: one row per measure. */
function impactRows(p, changeAt, N) {
  const d0 = day(changeAt), gw = gwinJS(d0, N), rw = rwinJS(d0, N), out = {};
  if (rw) {
    const ok = p.days.filter(d => d.state === 'ok');
    const side = (f, t) => { const xs = ok.filter(d => d.day >= f && d.day <= t); return xs.length ? { v: xs.reduce((s, d) => s + (readersOn(d) || 0), 0) / xs.length, n: xs.length } : null; };
    const b = side(rw.bFrom, rw.bTo), a = side(rw.aFrom, rw.aTo);
    out.readers = { b: b && b.v, a: a && a.v, n: a ? Math.min(a.n, b ? b.n : 0) : 0, prov: 0, win: rw };
  } else out.readers = { b: null, a: null, n: 0, win: null };
  if (gw) {
    const b = gSum(p.gs, gw.bFrom, gw.bTo), a = gSum(p.gs, gw.aFrom, gw.aTo);
    out.clicks = { b: b.c / gw.n, a: a.c / gw.n }; out.impressions = { b: b.i / gw.n, a: a.i / gw.n };
    out.ctr = { b: b.ctr, a: a.ctr }; out.position = { b: b.pos, a: a.pos };
    for (const k of ['clicks', 'impressions', 'ctr', 'position']) Object.assign(out[k], { n: gw.n, prov: gw.prov, win: gw });
  } else for (const k of ['clicks', 'impressions', 'ctr', 'position']) out[k] = { b: null, a: null, n: 0, win: null };
  const bw = s => (p.bw || []).find(x => x.change_at === changeAt && x.win === N && x.side === s);
  const bb = bw('before'), ba = bw('after');
  const est = x => x && x.landed ? 100 * Math.max(0, x.landed - (x.visits - x.left)) / x.landed : null;
  out.bounce = { b: est(bb), a: est(ba), n: ba ? daysBetween(ba.frm, ba.to) : 0, prov: 0, landings: [bb ? bb.landed : 0, ba ? ba.landed : 0],
    win: ba && bb ? { bFrom: bb.frm, bTo: bb.to, aFrom: ba.frm, aTo: ba.to, n: daysBetween(ba.frm, ba.to) } : null };
  for (const [k] of IMETRICS) { const r = out[k]; r.verdict = verdictJS(k, r.b, r.a, r.n, r.prov, r.landings); }
  return out;
}
function changeCell(k, b, a) {
  if (b == null || a == null) return '–';
  if (k === 'position') return (a - b > 0 ? '+' : '') + (a - b).toFixed(1);
  if (k === 'bounce') return (a - b > 0 ? '+' : '') + (a - b).toFixed(0) + ' points';
  if (!b) return a ? 'new' : '0';
  const c = 100 * (a - b) / b; return (c > 0 ? '+' : '') + c.toFixed(0) + '%';
}
const winText = w => w ? `${shortDay(w.bFrom)}–${shortDay(w.bTo)} vs ${shortDay(w.aFrom)}–${shortDay(w.aTo)}` : 'no days yet';
function impactTable(rows, extra = '') {
  return `<div class="box"><table><thead><tr><th>Measure</th><th class="r">Before</th><th class="r">After</th><th class="r">Change</th><th>Verdict</th><th class="hide-sm">Days compared</th></tr></thead><tbody>${
    IMETRICS.map(([k, label, f]) => { const r = rows[k];
      return `<tr><td>${esc(label)}</td><td class="num r">${copyable(f(r.b), { label: label + ' before' })}</td><td class="num r">${copyable(f(r.a), { label: label + ' after' })}</td><td class="num r">${changeCell(k, r.b, r.a)}</td><td>${badge(r.verdict)}${r.prov ? ` <span class="kind">${r.prov} provisional day(s)</span>` : ''}${k === 'bounce' && r.landings ? ` <span class="kind">${r.landings[0]} → ${r.landings[1]} landings</span>` : ''}</td><td class="hide-sm sub">${esc(winText(r.win))}</td></tr>`; }).join('')}${extra}</tbody></table></div>`;
}
function pageOverall(p) {
  if (!p.main) return null;
  const rows = impactRows(p, p.main, +state.win);
  return { rows, verdict: overallJS(IMETRICS.map(([k]) => rows[k].verdict)) };
}

const OPILL = { 'Mostly positive': 'v-better', 'Mostly negative': 'v-worse', Mixed: 'v-mixed', 'No clear change': 'v-nochange', 'Too early to tell': 'v-early' };
const opill = (v, extra = '') => `<span class="v ${OPILL[v] || 'v-nochange'}">${esc(v)}${extra}</span>`;
const SHORT = { readers: 'readers', clicks: 'Google clicks', impressions: 'Google impressions', ctr: 'click rate', position: 'position in Google', bounce: 'bounce' };

/** What to do next for one page, from its verdict and Google's index status. */
function pageNext(p, o) {
  const out = [], ix = p.index, d0 = p.main && day(p.main);
  if (!ix) out.push('Run Google\'s URL Inspection for it (tracker.py sync does this daily), so we know whether Google has it.');
  else if (ix.status === 'unknown_to_google') out.push('Ask Google to index it: Search Console, URL Inspection, "Request indexing". Google cannot rank a page it has not seen.');
  else if (ix.status !== 'indexed') out.push(`Read Google's coverage note ("${esc(ix.coverage || '–')}") in Search Console and fix what it names.`);
  else if (ix.last_crawl && d0 && day(ix.last_crawl) < d0) out.push(`Google last crawled it on ${esc(shortDay(day(ix.last_crawl)))}, before the change: request a recrawl in Search Console so results show the new version.`);
  if (o) {
    if (o.verdict === 'Too early to tell') out.push(`Do not change this page again yet. Look again around ${esc(longDay(addDays(d0, 10)))}, when 7 whole, final Google days exist after the change.`);
    else if (o.verdict === 'Mostly negative') out.push('Before changing it again: compare the old and new version on the Changes tab and check which searches it lost on the Google tab.');
    else if (o.verdict === 'Mostly positive') out.push('Leave it as it is, and reuse what worked here on similar pages.');
    else if (o.verdict === 'Mixed') out.push('Check which measure fell in the table below before touching it; one weak measure is not a reason to undo the change.');
    else out.push('Nothing moved clearly either way. Give it the 14-day window before deciding anything.');
  }
  return out;
}

function tabImpact(p) {
  const N = +state.win;
  const winChips = `<div class="bar" role="group" aria-label="Window length"><span class="lbl">Window</span><span class="chips-seg">${['7', '14'].map(w => `<button type="button" class="chip" data-win="${w}" data-fk="win-${w}" aria-pressed="${state.win === w}">${w} days each side</button>`).join('')}</span></div>`;
  const readers = new Map(p.days.filter(d => d.state === 'ok').map(d => [d.day, readersOn(d)]));
  const timeline = `<h2 class="sec">Timeline</h2>${rangeBar('d')}${chartControls(true)}${googleCharts(p.gs, readers, chartNotes(p), mainWidth() - 26)}`;
  if (!p.main) {
    const r = range(), ctx = whyContext(r.from, r.to, p);
    return answerBlock({ answer: '<b>Nothing to judge.</b> No change went live on this page in the git history, so there is no before and after.', why: ctx.why, next: pageNext(p, null), whyNote: ctx.note }) + timeline;
  }
  const o = pageOverall(p), rows = o.rows, d0 = day(p.main);
  const judged = IMETRICS.filter(([k]) => !['too early'].includes(rows[k].verdict));
  const better = IMETRICS.filter(([k]) => rows[k].verdict === 'better').map(([k]) => SHORT[k]);
  const worse = IMETRICS.filter(([k]) => rows[k].verdict === 'worse').map(([k]) => SHORT[k]);
  const head = { 'Mostly positive': 'Working.', 'Mostly negative': 'Not working yet.', Mixed: 'Mixed.', 'No clear change': 'No clear change.', 'Too early to tell': 'Too early to judge.' }[o.verdict];
  let answer = `<b>${head}</b> Since its main change on ${esc(longDay(d0))}, against the ${N} days before: `;
  if (!judged.length) answer += `no measure has 7 whole, final days after the change yet.`;
  else answer += [better.length ? `${better.join(', ')} better` : '', worse.length ? `${worse.join(', ')} worse` : '', `${judged.length - better.length - worse.length} with no clear change`].filter(Boolean).join('; ') + (judged.length < IMETRICS.length ? `; ${IMETRICS.length - judged.length} still too early` : '') + '.';
  const pc = (k, label) => { const [, , f] = IMETRICS.find(x => x[0] === k), r = rows[k]; return `<div class="card"><span>${esc(label)}</span><b>${copyable(`${f(r.b)} → ${f(r.a)}`, { label })}</b><span class="cmp">${badge(r.verdict)} ${changeCell(k, r.b, r.a)}</span></div>`; };
  const jl = journeys([p], N), leadCard = jl.pages && (jl.before.lead || jl.after.lead) ? card('Visits that sent a form', `${jl.before.lead} → ${jl.after.lead}`, `of ${jl.before.visits} → ${jl.after.visits} visits (Skald, proven)`) : '';
  const proof = !judged.length && IMETRICS.every(([k]) => rows[k].a == null) && !leadCard ? '' : `<div class="cards">${leadCard}${pc('readers', 'Readers a day')}${pc('clicks', 'Google clicks a day')}${pc('impressions', 'Google impressions a day')}${pc('position', 'Average position')}</div>`;
  const w = rows.clicks.win || rows.readers.win, ctx = whyContext(w ? w.bFrom : addDays(d0, -N), w ? w.aTo : gBounds()[1], p);
  const latest = p.changes[p.changes.length - 1];
  let blocks = `<h3>Main change, ${esc(longDay(d0))}${latest.live_at === p.main ? ' (also the latest)' : ''}</h3>${impactTable(rows, leadRows(p, p.main, rows.readers.win) + topRow(p, rows.readers.win || rows.clicks.win))}`;
  if (latest.live_at !== p.main) blocks += `<h3>Latest change, ${esc(longDay(day(latest.live_at)))}</h3>${(() => { const lr = impactRows(p, latest.live_at, N); return impactTable(lr, topRow(p, lr.readers.win || lr.clicks.win)); })()}`;
  const snaps = (p.bounce || []).map(b => `<tr><td class="num">${esc(longDay(b.snapshot))}</td><td class="num r">${b.landed}</td><td class="num r">${b.landed ? Math.round(100 * (b.landed - b.went_on) / b.landed) + '%' : '–'}</td><td class="sub">${esc((b.first || '').slice(0, 10))} to ${esc((b.last || '').slice(0, 10))}</td></tr>`).join('');
  return `${answerBlock({ answer, proof, why: ctx.why, next: ctx.next.concat(pageNext(p, o)), whyNote: ctx.note })}${winChips}
    ${timeline}
    <h2 class="sec">Before vs after, every measure</h2>${blocks}
    ${expSection(p.path)}
    <h3>Bounce over time</h3>
    <p class="sub">Skald's funnel tool only covers the last 7 days, so the daily snapshots below start on the day Skald is switched on. The before/after bounce above comes from Skald's page journeys instead, which take dates: landed visits that read nothing after this page, estimated as landings minus visits that went on (exact when every visit landed here). Page copies together.</p>
    ${snaps ? `<div class="box"><table><thead><tr><th>Snapshot</th><th class="r">Landings</th><th class="r">Bounce</th><th>Covers</th></tr></thead><tbody>${snaps}</tbody></table></div>` : '<div class="empty">No snapshot yet.</div>'}
    <p class="rules">How the verdicts work: ${esc(VERDICT_RULES)}</p>`;
}

/** Rows for the Impact table from Skald's extras: proven leads, AI crawler fetches, visitors sent by AI assistants
    (shown, not judged: the counts are too small for the 20% rule yet). */
function leadRows(p, changeAt, win) {
  const N = +state.win, ws = (p.jw || []).filter(w => w.change_at === changeAt && w.win === N), b = ws.find(w => w.side === 'before'), a = ws.find(w => w.side === 'after');
  const row = (label, bv, av, note) => `<tr><td>${esc(label)}</td><td class="num r">${bv}</td><td class="num r">${av}</td><td class="num r">–</td><td><span class="na">shown, not judged</span></td><td class="hide-sm sub">${esc(note)}</td></tr>`;
  let out = row('Visits that sent a form (Skald, proven)', b ? b.lead : '–', a ? a.lead : '–', b && a ? `${b.visits} → ${a.visits} visits; ${shortDay(b.frm)}–${shortDay(b.to)} vs ${shortDay(a.frm)}–${shortDay(a.to)}` : 'no journey window yet');
  if (win) {
    const per = (f, from, to) => { const s = sumDays([p], from, to, f); return s.days ? (s.n / s.days).toFixed(1) : '–'; };
    out += row('AI crawler fetches a day', per(d => d.ai_training, win.bFrom, win.bTo), per(d => d.ai_training, win.aFrom, win.aTo), 'crawlers that train or index');
    out += row('Visitors from AI assistants a day', per(d => Object.values(d.assistants || {}).reduce((s, v) => s + v, 0), win.bFrom, win.bTo), per(d => Object.values(d.assistants || {}).reduce((s, v) => s + v, 0), win.aFrom, win.aTo), 'ChatGPT, Perplexity, Gemini...');
  }
  return out;
}

/* ---------- Impact summary across all changed pages (Google view, detail part) ---------- */
function impactSummary() {
  const rows = DATA.pages.filter(p => p.main).map(p => ({ p, o: pageOverall(p) }));
  const counts = {}; rows.forEach(r => counts[r.o.verdict] = (counts[r.o.verdict] || 0) + 1);
  const order = { 'Mostly negative': 0, Mixed: 1, 'Mostly positive': 2, 'No clear change': 3, 'Too early to tell': 4 };
  rows.sort((a, b) => order[a.o.verdict] - order[b.o.verdict] || (a.p.main < b.p.main ? -1 : 1));
  const ba = (r, k, f) => `${f(r[k].b)} → ${f(r[k].a)}`;
  const F = Object.fromEntries(IMETRICS.map(([k, , f]) => [k, f]));
  return `<h2 class="sec">Impact of our changes, page by page (${rows.length} changed pages)</h2>
    <div class="bar" role="group" aria-label="Window length"><span class="lbl">Window</span><span class="chips-seg">${['7', '14'].map(w => `<button type="button" class="chip" data-win="${w}" data-fk="gwin-${w}" aria-pressed="${state.win === w}">${w} days each side</button>`).join('')}</span>
    <span class="vcounts">${Object.keys(order).filter(k => counts[k]).map(k => opill(k, ` · ${counts[k]}`)).join(' ')}</span></div>
    <div class="box"><table><thead><tr><th>Page</th><th>Main change</th><th>Impact</th><th class="r">Readers/day</th><th class="r">Clicks/day</th><th class="r">Position</th><th class="r hide-sm">Bounce</th></tr></thead><tbody>${
      rows.map(({ p, o }) => `<tr class="row" data-path="${esc(p.path)}"><td>${pageLink(p, 'iopen')}</td><td class="num">${esc(shortDay(day(p.main)))}</td><td>${opill(o.verdict)}</td><td class="num r">${ba(o.rows, 'readers', F.readers)}</td><td class="num r">${ba(o.rows, 'clicks', F.clicks)}</td><td class="num r">${ba(o.rows, 'position', F.position)}</td><td class="num r hide-sm">${ba(o.rows, 'bounce', F.bounce)}</td></tr>`).join('')}</tbody></table></div>
    <p class="rules">Open a page for its Impact tab. ${esc(VERDICT_RULES)}</p>`;
}

document.addEventListener('click', e => { const w = e.target.closest('[data-win]'); if (w) go({ win: w.dataset.win }); });
