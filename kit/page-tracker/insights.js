'use strict';
/* Insights view (view=insights, the first screen). dashboard.js calls window.renderInsights(container, state, DATA) on
   every render. The figures come from DATA.insights (insights.py, via export.py); the AI summary from insights.json
   (ai_summary.py). Uses the shared helpers of dashboard.js: esc, fmt, fmtN, pct, copyable, pageLink, lineChart,
   shortDay, longDay, $.
   Sub-choices live in the address bar as ins_ keys (back and forward work):
     ins_m     measure in the "changed vs rest vs whole site" chart: impressions | clicks | position | ctr
     ins_q     searches list: new | gone | moved
     ins_wk    weekly chart: impressions | clicks | changed_impressions | changed_clicks
     ins_span  weekly chart range: all | 12 (last 12 weeks)
     ins_shut  comma list of collapsed sections (groups, pages, queries, countries, ai, bounce, index, trend) */
(function () {
  const OPTS = {
    ins_m: ['impressions', 'clicks', 'position', 'ctr'],
    ins_q: ['new', 'gone', 'moved'],
    ins_wk: ['impressions', 'clicks', 'changed_impressions', 'changed_clicks'],
    ins_span: ['all', '12'],
  };
  const SECTIONS = ['clusters', 'competing', 'ctr', 'experiments', 'groups', 'pages', 'queries', 'countries', 'ai', 'bounce', 'index', 'trend'];
  const ML = { clicks: 'Clicks a day', impressions: 'Impressions a day', ctr: 'Click rate (CTR)', position: 'Average position', readers: 'Readers a day (Skald)' };
  const WL = { impressions: 'Impressions, whole site', clicks: 'Clicks, whole site', changed_impressions: 'Impressions, changed pages', changed_clicks: 'Clicks, changed pages' };
  const CN = { usa: 'United States', can: 'Canada', gbr: 'United Kingdom', ind: 'India', aus: 'Australia', deu: 'Germany', fra: 'France',
    pol: 'Poland', esp: 'Spain', nld: 'Netherlands', bra: 'Brazil', phl: 'Philippines', pak: 'Pakistan', nga: 'Nigeria', zaf: 'South Africa',
    ita: 'Italy', mex: 'Mexico', irl: 'Ireland', nzl: 'New Zealand', sgp: 'Singapore', are: 'United Arab Emirates', isr: 'Israel', tur: 'Turkey' };
  const VC = { better: 'v-better', worse: 'v-worse', 'no clear change': 'v-nochange', 'too early': 'v-early' };
  const vb = v => v ? `<span class="v ${VC[v] || 'v-nochange'}">${esc(v)}</span>` : '';
  const sign = n => n == null ? '–' : (n > 0 ? '+' : '') + (Math.round(n * 10) / 10) + '%';
  const f1 = v => v == null ? '–' : (+v).toFixed(1);
  const MF = { clicks: f1, impressions: fmtN, ctr: v => pct(v), position: f1, readers: f1 };
  const pairF = (a, f = fmt) => `${f(a[0])} → ${f(a[1])}`;
  const country = c => CN[c] || String(c).toUpperCase();
  const cut = (s, n) => (s = String(s ?? '')).length > n ? s.slice(0, n - 1) + '…' : s;
  let AIJ = null, fetching = false, last = null;

  /* ---------- the address bar (ins_ keys only) ---------- */
  function ins() {
    const u = new URLSearchParams(location.search), o = {};
    for (const [k, list] of Object.entries(OPTS)) o[k] = list.includes(u.get(k)) ? u.get(k) : list[0];
    o.ins_shut = (u.get('ins_shut') || '').split(',').filter(x => SECTIONS.includes(x));
    return o;
  }
  function writeIns(patch) {
    const u = new URLSearchParams(location.search), cur = { ...ins(), ...patch };
    for (const k of Object.keys(OPTS)) cur[k] === OPTS[k][0] ? u.delete(k) : u.set(k, cur[k]);
    cur.ins_shut.length ? u.set('ins_shut', [...new Set(cur.ins_shut)].join(',')) : u.delete('ins_shut');
    const q = u.toString().replace(/%2C/g, ','), url = location.pathname + (q ? '?' + q : '');
    if (url !== location.pathname + location.search) history.pushState(history.state, '', url);
    if (last) draw(...last);
  }

  /* ---------- small inline SVG charts ---------- */
  /** Before and after bars per row: rows [{label, b, a, verdict}]. */
  function pairBars(rows, W, f, label, lowerBetter = false) {
    const ok = rows.filter(r => r.b != null || r.a != null); if (!ok.length) return '<div class="empty">No figures yet.</div>';
    const max = Math.max(...ok.flatMap(r => [r.b || 0, r.a || 0])) || 1, LW = 92, iw = Math.max(60, W - LW - 100), rowH = 36;
    let s = `<svg width="${W}" height="${ok.length * rowH + 4}" viewBox="0 0 ${W} ${ok.length * rowH + 4}" role="img" aria-label="${esc(label)}: ${esc(ok.map(r => `${r.label} ${f(r.b)} before, ${f(r.a)} after`).join('; '))}">`;
    ok.forEach((r, i) => {
      const y = i * rowH + 4, wb = (r.b || 0) / max * iw, wa = (r.a || 0) / max * iw;
      const col = r.verdict === 'better' ? 'var(--up)' : r.verdict === 'worse' ? 'var(--down)' : 'var(--accent)';
      s += `<text x="0" y="${y + 12}" style="fill:var(--fg)">${esc(cut(r.label, 14))}<title>${esc(r.label)}</title></text>`;
      s += `<rect x="${LW}" y="${y}" width="${Math.max(1, wb)}" height="12" rx="3" fill="var(--line)"><title>${esc(r.label)} before: ${esc(f(r.b))}</title></rect>`;
      s += `<text x="${LW + wb + 4}" y="${y + 10}">${esc(f(r.b))} before</text>`;
      s += `<rect x="${LW}" y="${y + 15}" width="${Math.max(1, wa)}" height="12" rx="3" fill="${col}"><title>${esc(r.label)} after: ${esc(f(r.a))}</title></rect>`;
      s += `<text x="${LW + wa + 4}" y="${y + 25}">${esc(f(r.a))} after</text>`;
    });
    return s + `</svg>${lowerBetter ? '<p class="sub">Shorter is better here: position 1 is the top of Google.</p>' : ''}`;
  }
  /** Bars left (down) or right (up) of a middle line: rows [{label, v, text, good}]. */
  function divBars(rows, W, label) {
    if (!rows.length) return '<div class="empty">None yet.</div>';
    const LW = Math.min(170, Math.round(W * 0.38)), iw = Math.max(80, W - LW - 6), mid = LW + iw / 2, max = Math.max(...rows.map(r => Math.abs(r.v))) || 1, rowH = 22;
    const chars = Math.max(10, Math.floor(LW / 6.6));
    let s = `<svg width="${W}" height="${rows.length * rowH + 6}" viewBox="0 0 ${W} ${rows.length * rowH + 6}" role="img" aria-label="${esc(label)}: ${esc(rows.map(r => r.label + ' ' + r.text).join('; '))}">`;
    s += `<line x1="${mid}" x2="${mid}" y1="0" y2="${rows.length * rowH + 6}" stroke="var(--line)"/>`;
    rows.forEach((r, i) => {
      const y = i * rowH + 4, w = Math.abs(r.v) / max * (iw / 2 - 4), x = r.v >= 0 ? mid : mid - w;
      const col = r.good == null ? 'var(--bar2)' : r.good ? 'var(--up)' : 'var(--down)';
      s += `<text x="0" y="${y + 11}" style="fill:var(--fg)">${esc(cut(r.label, chars))}<title>${esc(r.label)}</title></text>`;
      s += `<rect x="${x}" y="${y}" width="${Math.max(1, w)}" height="14" rx="2" fill="${col}" opacity=".85"><title>${esc(r.label)}: ${esc(r.text)}</title></rect>`;
      s += `<text x="${r.v >= 0 ? mid - 4 : mid + 4}" y="${y + 11}" text-anchor="${r.v >= 0 ? 'end' : 'start'}">${esc(r.text)}</text>`;
    });
    return s + '</svg>';
  }
  /** One stacked bar: parts [{label, n, color}]. */
  function stack(parts, W, label) {
    const tot = parts.reduce((a, p) => a + p.n, 0); if (!tot) return '<div class="empty">No figures yet.</div>';
    let x = 0, s = `<svg width="${W}" height="22" viewBox="0 0 ${W} 22" role="img" aria-label="${esc(label)}: ${esc(parts.map(p => `${p.n} ${p.label}`).join(', '))}">`;
    for (const p of parts) { const w = p.n / tot * W; s += `<rect x="${x}" y="2" width="${Math.max(0, w - 1)}" height="18" rx="3" fill="${p.color}"><title>${esc(p.label)}: ${p.n}</title></rect>`; x += w; }
    return s + `</svg><div class="legend">${parts.map(p => `<span><i class="sw" style="background:${p.color}"></i>${esc(p.label)} ${p.n} (${Math.round(100 * p.n / tot)}%)</span>`).join('')}</div>`;
  }
  const seg = (key, cur, opts) => `<div class="bar" role="group" aria-label="${esc(opts.label)}"><span class="lbl">${esc(opts.label)}:</span>${
    opts.items.map(([v, t]) => `<button type="button" class="chip" data-ins-k="${key}" data-ins-v="${v}" data-fk="ins-${key}-${v}" aria-pressed="${cur === v}">${esc(t)}</button>`).join('')}</div>`;

  /* ---------- the AI summary ---------- */
  /** The AI summary, split by its headings: { why: [li html], next: [li html], note: html }. ai_summary.py writes
      "## Why" and "## What to do next"; anything else is shown under "why". */
  function aiParts(I) {
    const A = (typeof AI !== 'undefined' && AI) || AIJ;
    if (!A) {
      if (!fetching) { fetching = true; fetch('insights.json?' + Date.now()).then(r => r.ok ? r.json() : null).catch(() => null).then(j => { AIJ = j || { error: 'No AI summary file yet.' }; if (last) draw(...last); }); }
      return { why: [], next: [], note: '<p class="sub">AI notes loading…</p>' };
    }
    if (A.error || !A.text) return { why: [], next: [], note: `<p class="sub">AI notes: ${esc(A.error || 'not written yet (ai_summary.py runs after the 09:15 sync).')}</p>` };
    const out = { why: [], next: [] }; let cur = 'why';
    for (const raw of String(A.text).split('\n')) {
      const line = esc(raw.trim()).replace(/\*\*(.+?)\*\*/g, '$1');
      if (/^#{1,4} /.test(line)) { cur = /next|do\b/i.test(line) ? 'next' : 'why'; continue; }
      if (/^[-*] /.test(line)) out[cur].push(line.slice(2) + '<span class="ai-tag">AI</span>');
      else if (line) out[cur].push(line + '<span class="ai-tag">AI</span>');
    }
    out.note = `<p class="sub">Lines marked AI: written ${esc(longDay(A.date))} by Claude from the figures on this page; check them against the numbers.${
      A.unverified_numbers && A.unverified_numbers.length ? ` <span class="down">Numbers not found in the data: ${esc(A.unverified_numbers.join(', '))}</span>` : ''}${
      I && A.date !== String(I.built).slice(0, 10) ? ` <span class="flat">These notes are from ${esc(longDay(A.date))}; the figures are newer.</span>` : ''}</p>`;
    return out;
  }

  /* ---------- sections ---------- */
  function section(id, title, head, body, rule, shut) {
    return `<details class="ins-sec" id="ins-${id}" data-ins-sec="${id}"${shut.includes(id) ? '' : ' open'}><summary data-fk="ins-sum-${id}"><span class="ins-t">${esc(title)}</span> ${head || ''}</summary><div class="ins-b">${body}${rule ? `<p class="rules">Rule used: ${esc(rule)}</p>` : ''}</div></details>`;
  }
  const winTxt = w => w ? `${shortDay(w.b_from)}–${shortDay(w.b_to)} vs ${shortDay(w.a_from)}–${shortDay(w.a_to)} (${w.n} day${w.n === 1 ? '' : 's'} each side${w.prov ? `, ${w.prov} after day${w.prov === 1 ? '' : 's'} still provisional` : ''})` : 'no days yet';
  function pagesTable(list, data) {
    if (!list || !list.length) return '<div class="empty">None.</div>';
    const link = (path, slug) => { const p = data.pages.find(x => x.path === path); return p ? pageLink(p, 'ins') : esc(slug); };
    return `<div class="box"><table><thead><tr><th>Page</th><th>Change</th><th class="r">Impressions/day</th><th class="r">Clicks/day</th><th class="r">Position</th><th class="r hide-sm">Readers/day</th><th>Verdict</th></tr></thead><tbody>${
      list.map(m => `<tr><td class="pg">${link(m.path, m.slug)}</td><td class="num">${esc(shortDay(m.change))} <span class="kind">${m.days} d</span></td><td class="num r">${pairF(m.impressions_per_day, fmtN)}</td><td class="num r">${pairF(m.clicks_per_day)}</td><td class="num r">${pairF(m.position)}</td><td class="num r hide-sm">${pairF(m.readers_per_day)}</td><td>${vb(m.verdict)}</td></tr>`).join('')}</tbody></table></div>`;
  }
  function qTable(list, kind) {
    if (!list || !list.length) return '<div class="empty">None.</div>';
    const cols = kind === 'moved' ? [['Position before → after', q => `${f1(q.before)} → ${f1(q.after)}`], ['Impressions', q => pairF(q.impressions, fmtN)]]
      : [['Impressions', q => fmtN(q.impressions)], ['Clicks', q => fmtN(q.clicks)], ['Position', q => f1(q.position)]];
    return `<div class="box"><table><thead><tr><th>Search</th>${cols.map(c => `<th class="r">${c[0]}</th>`).join('')}</tr></thead><tbody>${
      list.map(q => `<tr><td>${copyable(q.query, { label: 'search' })}</td>${cols.map(c => `<td class="num r">${c[1](q)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  }

  function draw(container, st, data) {
    const I = data && data.insights, o = ins(), SR = (I && I.section_rules) || {};
    if (!I) { container.innerHTML = '<div class="empty">No insights in data.json yet: run python3 tracker.py report.</div>'; return; }
    const W = Math.max(240, (container.clientWidth || ($('main') ? $('main').clientWidth - (innerWidth <= 720 ? 32 : 48) : 600)));
    const half = innerWidth <= 720 ? W : Math.floor((W - 16) / 2);
    const G = I.groups || {}, gw = G.window, groups = G.groups || [];

    // (a) the answer, (b) the proof, (c) why, (d) what next; the sections below are the detail
    const row = (g, m) => (g.rows || []).find(r => r.metric === m) || {};
    const ch = groups.find(g => /^Changed/.test(g.name)) || groups[0] || {}, rest = groups.find(g => /^Rest/.test(g.name)) || {};
    const word = (r, more = 'more', fewer = 'fewer') => r.change_pct == null ? 'no figures' : Math.abs(r.change_pct) < 10 ? 'about the same' : r.change_pct > 0 ? more : fewer;
    const vs = ['clicks', 'impressions', 'position'].map(m => row(ch, m).verdict);
    const ov = overallJS(vs.map(v => v || 'too early'));
    const head = { 'Mostly positive': 'Winning.', 'Mostly negative': 'Losing ground.', Mixed: 'Mixed.', 'No clear change': 'No clear change yet.', 'Too early to tell': 'Too early to call.' }[ov];
    const answer = `<b>${head}</b> Since our changes started on ${esc(longDay(I.split))}, the ${I.changed_pages} changed pages get ${word(row(ch, 'impressions'))} Google impressions than in the same number of days before${rest.rows ? `, while the rest of the site gets ${word(row(rest, 'impressions'))}` : ''}. Compared: ${gw ? esc(spanText(gw.b_from, gw.b_to)) + ' vs ' + esc(spanText(gw.a_from, gw.a_to)) : 'no days yet'}.`;
    const pc = (label, r, f, sub) => `<div class="card"><span>${esc(label)}</span><b>${copyable(r.metric === 'position' ? `${f1(r.before)} → ${f1(r.after)}` : sign(r.change_pct), { label })}</b><span class="cmp">${vb(r.verdict)} ${r.metric === 'position' ? 'lower is better' : `${f(r.before)} → ${f(r.after)} a day`}</span></div>`;
    const proof = `<div class="cards">${pc('Changed pages: impressions', row(ch, 'impressions'), fmtN)}${pc('Changed pages: clicks', row(ch, 'clicks'), f1)}${pc('Changed pages: avg position', row(ch, 'position'), f1)}${(() => { const K = I.conversions && I.conversions.site; return K ? `<div class="card"><span>Leads a day, whole site</span><b>${copyable(`${f1(K.before_per_day)} → ${f1(K.after_per_day)}`, { label: 'leads a day' })}</b><span class="cmp">${vb(K.verdict)} Skald conversions, ${K.window.n} days each side</span></div>` : ''; })()}</div>`;
    const ctx = typeof whyContext === 'function' && gw ? whyContext(gw.b_from, gw.a_to, null) : { why: [], next: [], note: '' };
    const T0 = I.trend;
    if (T0) ctx.why.push(`<b>Long-term:</b> the whole site's weekly impressions were already ${T0.impressions_change_pct > 0 ? 'rising' : 'falling'} before our changes (last 4 full weeks vs the 4 before: ${sign(T0.impressions_change_pct)}), so part of any move is the trend, not the change.`);
    const KV = I.conversions;
    if (KV) ctx.why.push(`<b>Leads:</b> ${KV.total_leads} forms on the whole site since Skald was switched on; Skald tied ${KV.leads_tied_to_a_page} of them to a page, and the changed pages' own windows show ${KV.changed_pages_proven_leads.before} → ${KV.changed_pages_proven_leads.after} visits proven to have sent a form, so leads cannot be credited to a page yet.${KV.leads_db_available ? '' : " Skald's lead database is not set up for this site."}`);
    const AIp = aiParts(I);
    const top = answerBlock({ answer, proof, why: ctx.why.concat(AIp.why), next: ctx.next.concat(AIp.next), whyNote: ctx.note + AIp.note });

    // 0. by sitemap cluster: which clusters win or lose
    const CLS = I.clusters || [], cr = (x, m) => (x.rows || []).find(r => r.metric === m) || {};
    const clHead = CLS.filter(x => x.changed).map(x => x.overall).filter(Boolean);
    const sClusters = section('clusters', 'By cluster (the site\'s sitemap clusters)', `<span class="sub">${CLS.filter(x => x.changed).length} of ${CLS.length} changed by us${clHead.length ? ' · ' + clHead.filter(v => v !== 'Too early to tell').length + ' judged' : ''}</span>`,
      CLS.length ? `<div class="box"><table><thead><tr><th>Cluster</th><th>Our changes</th><th>Impact</th><th class="r">Impressions/day</th><th class="r">Change</th><th class="r">Clicks/day</th><th class="r">Position</th></tr></thead><tbody>${
        CLS.map(x => `<tr class="row crow" data-cluster="${esc(x.cluster)}"><td><a class="linkbtn" href="?view=clusters&amp;cluster=${encodeURIComponent(x.cluster)}" data-cluster="${esc(x.cluster)}" data-fk="ins-cl-${esc(x.cluster)}">${esc(x.name)}</a><div class="kind">${x.pages} pages</div></td><td class="num">${x.changed ? `${x.changed} changed<div class="kind">first ${esc(shortDay(x.first_change))}</div>` : '<span class="na">not changed</span>'}</td><td>${x.overall ? opill(x.overall) : '–'}${x.changed ? '' : '<div class="kind">for comparison</div>'}</td><td class="num r">${pairF([cr(x, 'impressions').before, cr(x, 'impressions').after], fmtN)}</td><td class="num r">${sign(cr(x, 'impressions').change_pct)}</td><td class="num r">${pairF([cr(x, 'clicks').before, cr(x, 'clicks').after])}</td><td class="num r">${pairF([cr(x, 'position').before, cr(x, 'position').after])}</td></tr>`).join('')}</tbody></table></div>
        <p class="sub">Each cluster against its own first change, same-length windows; clusters we did not change are compared around our first change (${esc(longDay(I.split))}) as a yardstick for what Google did on its own. Open a cluster for its pages and timeline.</p>` : '<div class="empty">No clusters yet (run tracker.py sync).</div>', 'Google per cluster: all pages in the cluster\'s sitemap, page copies together; the same verdict rules as above.', o.ins_shut);

    // competing pages, click-rate check, experiment log (dashboard-more.js draws them)
    const CP = (I.competing || {}).searches || [], CT = (I.ctr_check || {}).pages || [], EX = (I.experiments || {}).rows || [];
    const sCompeting = section('competing', 'Our pages competing for the same search', `<span class="sub">${CP.filter(x => x.owner && x.owner !== x.google_prefers).length} where Google shows the wrong page · ${CP.length} shared searches</span>`,
      competingSection(null, { bare: true }), '', o.ins_shut);
    const sCtr = section('ctr', 'Pages clicked far less than their position usually gets', `<span class="sub">${CT.length} title and description rewrite candidates</span>`, ctrSection(), '', o.ins_shut);
    const sExp = section('experiments', 'Experiment log: what each change aimed at, and what happened', `<span class="sub">${EX.filter(x => x.r7).length} of ${EX.length} with a 7-day result</span>`, expSection(null), '', o.ins_shut);

    // 1. changed vs rest vs whole site
    const m = o.ins_m, mrows = groups.map(g => { const r = row(g, m); return { label: /^Changed/.test(g.name) ? 'Changed pages' : /^Rest/.test(g.name) ? 'Rest of site' : g.name, b: r.before, a: r.after, verdict: r.verdict }; });
    const rd = groups[0] && groups[0].readers;
    const gTable = `<div class="box"><table><thead><tr><th>Group</th><th>Measure</th><th class="r">Before</th><th class="r">After</th><th class="r">Change</th><th>Verdict</th></tr></thead><tbody>${
      groups.flatMap(g => [...(g.rows || []), ...(g.readers ? [g.readers] : [])].map((r, i, all) => `<tr>${i ? '' : `<th scope="rowgroup" rowspan="${all.length}" class="grp">${esc(g.name)}</th>`}<td>${ML[r.metric]}</td><td class="num r">${MF[r.metric](r.before)}</td><td class="num r">${MF[r.metric](r.after)}</td><td class="num r">${r.metric === 'position' ? (r.before != null && r.after != null ? (r.after - r.before > 0 ? '+' : '') + (r.after - r.before).toFixed(1) : '–') : sign(r.change_pct)}</td><td>${vb(r.verdict)}</td></tr>`)).join('')}</tbody></table></div>`;
    const sGroups = section('groups', 'Changed pages vs the rest of the site vs the whole site', vb(row(groups[0] || {}, 'impressions').verdict),
      `<p class="sub">Google, split at the first change (${esc(longDay(I.split))}): ${esc(winTxt(gw))}. "Rest of the site" is the whole site minus the changed pages, so it is approximate.${rd ? ` Readers (Skald, changed pages): ${f1(rd.before)} → ${f1(rd.after)} a day ${vb(rd.verdict)}.` : ''}</p>
      ${seg('ins_m', m, { label: 'Chart shows', items: [['impressions', 'Impressions'], ['clicks', 'Clicks'], ['position', 'Position'], ['ctr', 'CTR']] })}
      <div class="chart">${pairBars(mrows, W, MF[m], ML[m] + ' before and after', m === 'position')}</div>${gTable}`, SR.groups || I.rules, o.ins_shut);

    // 2. winners and losers
    const moves = [...(I.winners || []), ...(I.losers || []).slice().reverse()];
    const vcount = Object.entries(I.verdict_counts || {}).filter(([, v]) => v).map(([k, v]) => `${v} ${esc(k)}`).join(', ');
    const sPages = section('pages', 'Winners and losers since each page’s change', `<span class="sub">${vcount}</span>`,
      `<p class="sub">Each page against its own same-length windows. Bars: change in Google impressions a day.</p>
      <div class="chart">${divBars(moves.map(x => { const d = x.impressions_per_day[1] - x.impressions_per_day[0]; return { label: x.slug, v: d, text: (d > 0 ? '+' : '') + fmtN(d) + '/day', good: x.verdict === 'too early' ? null : d > 0 }; }), W, 'Change in impressions a day per page')}</div>
      <div class="grid2"><div><h3>Biggest gains</h3>${pagesTable(I.winners, data)}</div><div><h3>Biggest drops</h3>${pagesTable(I.losers, data)}</div></div>`, SR.pages, o.ins_shut);

    // 3. searches gained and lost
    const Q = I.queries || {}, qk = o.ins_q;
    const sQueries = section('queries', 'Searches gained and lost', `<span class="sub">${(Q.new || []).length} new · ${(Q.gone || []).length} gone</span>`,
      `<p class="sub">${esc(Q.note || '')}</p>${seg('ins_q', qk, { label: 'Show', items: [['new', `New (${(Q.new || []).length})`], ['gone', `Gone (${(Q.gone || []).length})`], ['moved', `Position moves (${(Q.moved || []).length})`]] })}
      ${qk === 'moved' ? `<div class="chart">${divBars((Q.moved || []).map(q => { const d = (q.before || 0) - (q.after || 0); return { label: q.query, v: d, text: `${f1(q.before)} → ${f1(q.after)}`, good: d > 0 }; }), W, 'Position moves, up is better')}</div>` : ''}
      ${qTable(Q[qk], qk)}`, SR.queries, o.ins_shut);

    // 4. countries
    const C = I.countries || [];
    const sCountries = section('countries', 'Countries moving (Google, whole site)', '',
      `<p class="sub">${esc(I.countries_note || '')}</p><div class="chart">${divBars(C.map(c => ({ label: country(c.country), v: c.change_pct || 0, text: sign(c.change_pct), good: c.verdict === 'too early' || c.verdict === 'no clear change' ? null : c.verdict === 'better' })), W, 'Change in impressions by country')}</div>
      ${C.length ? `<div class="box"><table><thead><tr><th>Country</th><th class="r">Impressions/day</th><th class="r">Change</th><th class="r">Clicks</th><th>Verdict</th></tr></thead><tbody>${C.map(c => `<tr><td>${copyable(country(c.country), { label: 'country' })}</td><td class="num r">${pairF(c.impressions_per_day, fmtN)}</td><td class="num r">${sign(c.change_pct)}</td><td class="num r">${pairF(c.clicks, fmtN)}</td><td>${vb(c.verdict)}</td></tr>`).join('')}</tbody></table></div>` : ''}`, SR.countries, o.ins_shut);

    // 5. AI assistants
    const A = I.ai || {}, who = x => Object.entries(x || {}).map(([k, v]) => `${esc(k)} ${v}`).join(', ') || 'none';
    const sAI = section('ai', 'AI assistants reading our pages', vb(A.verdict),
      `<p class="sub">Visits where an AI assistant (ChatGPT, Perplexity, Claude, Gemini...) fetched a tracked page to answer someone, per day, from Skald.${A.window ? ` ${esc(winTxt(A.window))}: <b>${f1(A.before_per_day)} → ${f1(A.after_per_day)}</b> a day. Before: ${who(A.assistants_before)}. After: ${who(A.assistants_after)}.` : ''}</p>
      <div class="chart"><div class="chart-h"><b>AI assistant visits a day</b><span class="sub">${(A.daily || []).length ? esc(spanText(A.daily[0][0], A.daily[A.daily.length - 1][0])) + `, ${A.daily.length} days` : ''}</span></div>${lineChart({ points: (A.daily || []).map(([d, a]) => ({ d, v: a, prov: false })), width: W, height: 110, label: 'AI assistant visits', notes: chartNotes(null), int: true })}</div>`, SR.ai, o.ins_shut);

    // 6. bounce
    const B = I.bounce || {};
    const sBounce = section('bounce', 'Bounce before vs after', vb(B.verdict),
      B.pages ? `<p class="sub">${B.pages} changed pages with days on both sides: share of landings that left without reading another page (${fmtN(B.landed[0])} → ${fmtN(B.landed[1])} landings)${B.min_after_days != null ? `; shortest after window ${B.min_after_days} day(s)` : ''}. ${esc(B.note || '')}</p>
        <div class="chart">${pairBars([{ label: 'Bounce', b: B.bounce[0], a: B.bounce[1], verdict: B.verdict }], Math.min(W, 520), v => v == null ? '–' : v + '%', 'Bounce before and after', true)}</div>` : '<div class="empty">No after days yet.</div>', SR.bounce, o.ins_shut);

    // 7. index
    const X = I.index || {}, COL = { indexed: 'var(--up)', excluded: 'var(--flat)', unknown_to_google: 'var(--down)', 'not checked': 'var(--line)' };
    const parts = obj => Object.entries(obj || {}).map(([k, n]) => ({ label: k.replace(/_/g, ' '), n, color: COL[k] || 'var(--bar)' }));
    const sIndex = section('index', 'Is Google indexing the pages?', `<span class="sub">${(X.tracked || {}).indexed || 0} of ${Object.values(X.tracked || {}).reduce((a, b) => a + b, 0)} tracked indexed</span>`,
      `<div class="grid2"><div><h3>Tracked pages</h3>${stack(parts(X.tracked), half, 'Tracked pages by Google index status')}</div>
      <div><h3>Whole site${X.site ? ` (${X.site.pages} pages checked ${esc(X.site_snapshot ? longDay(X.site_snapshot) : '')})` : ''}</h3>${X.site ? stack(parts(X.site.by_status), half, 'Whole site by Google index status') : '<div class="empty">Not checked yet.</div>'}</div></div>
      ${X.unknown && X.unknown.length ? `<p class="sub">Not yet known to Google: ${X.unknown.map(s => copyable(s, { label: 'page slug' })).join(', ')}. "Unknown to Google" means Google has not crawled the address yet, so it cannot rank it.</p>` : ''}`, SR.index, o.ins_shut);

    // 8. weekly trend
    const T = I.trend, wk = I.weekly || [], wsel = o.ins_span === '12' ? wk.slice(-12) : wk, key = o.ins_wk;
    const sTrend = section('trend', 'The long-term trend (weekly)', T ? `${vb(T.impressions_verdict)}` : '',
      `<p class="sub">${T ? `Last 4 full weeks (from ${esc(longDay(T.weeks[0]))}) vs the 4 before: impressions ${fmtN(T.prev4_impressions)} → ${fmtN(T.last4_impressions)}, clicks ${fmtN(T.prev4_clicks)} → ${fmtN(T.last4_clicks)} (${sign(T.clicks_change_pct)}) ${vb(T.clicks_verdict)}. ` : ''}Shaded weeks are not complete or still provisional. Letters on the axis: our changes and Google's updates (hover them).</p>
      ${seg('ins_wk', key, { label: 'Measure', items: Object.entries(WL) })}${seg('ins_span', o.ins_span, { label: 'Range', items: [['all', 'Since May'], ['12', 'Last 12 weeks']] })}
      ${typeof annChips === 'function' ? annChips() : ''}<div class="chart"><div class="chart-h"><b>${esc(WL[key])}, per week</b><span class="sub">${wsel.length ? `weeks of ${esc(spanText(wsel[0].week, wsel[wsel.length - 1].week))}, ${wsel.length} weeks` : ''}</span></div>${lineChart({ points: wsel.map((x, i) => ({ d: x.week, v: x[key], prov: x.provisional_days > 0 || (i === wsel.length - 1 && x.days < 7) })), width: W, label: WL[key] + ' per week', notes: chartNotes(null), weekly: true, int: true })}</div>`, SR.trend, o.ins_shut);

    container.innerHTML = `${typeof findingsBox === 'function' ? findingsBox((data.findings || {}).site) : ''}${top}<h2 class="sec">The detail</h2>
      ${sClusters}${sCompeting}${sCtr}${sExp}${sGroups}${sPages}${sQueries}${sCountries}${sAI}${sBounce}${sIndex}${sTrend}
      <p class="rules">How the verdicts work: ${esc(I.rules || '')}</p>`;
  }

  function style() {
    if (document.getElementById('ins-style')) return;
    const s = document.createElement('style'); s.id = 'ins-style';
    s.textContent = `details.ins-sec{border:1px solid var(--line);border-radius:8px;margin:8px 0;background:var(--surface);min-width:0;box-shadow:var(--shadow)}
details.ins-sec>summary{cursor:pointer;padding:8px 12px;display:flex;flex-wrap:wrap;gap:8px;align-items:center;list-style:none}
details.ins-sec>summary::-webkit-details-marker{display:none}
.ins-t::before{content:"\\25B8";display:inline-block;color:var(--mute);margin-right:6px;transition:transform .15s}details.ins-sec[open] .ins-t::before{transform:rotate(90deg)}\n.ins-b th.grp{color:var(--fg);font-size:13px;vertical-align:top;white-space:normal;min-width:90px}.ins-b td.pg{min-width:150px;overflow-wrap:anywhere}
.ins-t{font-weight:650;font-size:13px}.ins-b{padding:0 12px 12px;min-width:0}
@media(max-width:720px){.ins-b{padding:0 10px 10px}details.ins-sec>summary{padding:10px}}`;
    document.head.append(s);
  }
  function bind(container) {
    if (container._insBound) return; container._insBound = true;
    container.addEventListener('click', e => {
      const b = e.target.closest('[data-ins-k]'); if (!b) return;
      e.stopPropagation(); writeIns({ [b.dataset.insK]: b.dataset.insV });
      const again = container.querySelector(`[data-fk="${CSS.escape(b.dataset.fk)}"]`); if (again) again.focus();
    });
    container.addEventListener('toggle', e => {
      const d = e.target; if (!d.matches || !d.matches('details[data-ins-sec]')) return;
      const id = d.dataset.insSec, shut = ins().ins_shut.filter(x => x !== id);
      if (!d.open) shut.push(id);
      if (shut.join() !== ins().ins_shut.join()) writeIns({ ins_shut: shut });
    }, true);
  }

  window.renderInsights = function (container, st, data) {
    container = container || document.getElementById('v-insights');
    data = data || (typeof DATA !== 'undefined' ? DATA : null);
    if (!container) return;
    style(); bind(container);
    last = [container, st, data];
    if (container.hidden) return;  // drawn when the view is shown
    draw(container, st, data);
  };
})();
