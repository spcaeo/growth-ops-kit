"""report.html: one row per changed page, before vs after its main rebuild (the change with the biggest word swing)."""
import json, os, datetime as dt, html
import config
from collections import Counter

import config
HERE = config.HERE      # the project's page-tracker data folder


def _main_change(c, path):
    rows = c.execute("SELECT sha, live_at, title_before, title_after, words_before, words_after FROM changes WHERE path=? ORDER BY live_at", (path,)).fetchall()
    if not rows:
        return None, []
    main = max(rows, key=lambda r: abs((r[5] or 0) - (r[4] or 0)))
    return main, rows


def _window(c, path, start_day, end_day):
    q = c.execute("SELECT day, readers, search, countries, sources FROM daily WHERE path=? AND state='ok' AND day>=? AND day<=?",
                  (path, start_day, end_day)).fetchall()
    days = len(q)
    # search = visits from a search engine (Skald sources["Search engine"]); Skald's 'search' field is not that (13 Nov 2026)
    readers = sum(r[1] or 0 for r in q); search = sum((json.loads(r[4] or "{}")).get("Search engine", 0) for r in q)
    countries, sources = Counter(), Counter()
    for r in q:
        countries.update(json.loads(r[3] or "{}")); sources.update(json.loads(r[4] or "{}"))
    return days, readers, search, countries, sources


def write(c):
    today = dt.date.today()
    rows_html, summary = [], []
    for path, slug, kind, title in c.execute("SELECT path, slug, kind, title FROM pages ORDER BY kind, slug").fetchall():
        main, all_changes = _main_change(c, path)
        if not main:
            continue
        live = dt.datetime.fromisoformat(main[1]); day0 = live.date()
        n_after = max(0, (today - day0).days - 1)
        win = max(1, min(14, n_after)) if n_after else 7
        b = _window(c, path, str(day0 - dt.timedelta(days=win)), str(day0 - dt.timedelta(days=1)))
        a = _window(c, path, str(day0 + dt.timedelta(days=1)), str(day0 + dt.timedelta(days=win)))
        per = lambda w: (w[1] / w[0]) if w[0] else None
        pb, pa = per(b), per(a)
        trend = "–" if pb is None or pa is None else ("up" if pa > pb * 1.2 and pa - pb >= 0.5 else "down" if pa < pb * 0.8 and pb - pa >= 0.5 else "same")
        g = c.execute("SELECT at FROM milestones WHERE path=? AND kind='googlebot'", (path,)).fetchone()
        top_c = ", ".join(f"{k} {v}" for k, v in (b[3] + a[3]).most_common(4))
        rows_html.append(f"<tr><td><a href='{html.escape(config.SITE + path)}'>{html.escape(slug)}</a><div class=sm>{html.escape(kind)}</div></td>"
                         f"<td>{live.strftime('%b %d %H:%M')}<div class=sm>{len(all_changes)} change(s)</div></td>"
                         f"<td class=sm>{html.escape(main[2] or '')}<br>→ <b>{html.escape(main[3] or '')}</b></td>"
                         f"<td>{main[4]}→{main[5]}</td>"
                         f"<td>{b[1]} / {b[0]}d<div class=sm>{'' if pb is None else f'{pb:.1f}/day'}</div></td>"
                         f"<td>{a[1]} / {a[0]}d<div class=sm>{'' if pa is None else f'{pa:.1f}/day'}</div></td>"
                         f"<td class='t-{trend}'>{trend}</td><td>{b[2]} → {a[2]}</td><td class=sm>{html.escape(top_c)}</td>"
                         f"<td class=sm>{(g[0][:10] if g else 'not yet')}</td></tr>")
        summary.append((slug, b[1], a[1], b[0], a[0], trend))
    css = """body{font:14px/1.45 system-ui,sans-serif;margin:24px;color:#111;background:#fff}h1{font-size:20px}table{border-collapse:collapse;width:100%}
    td,th{border-bottom:1px solid #e5e5e5;padding:6px 8px;vertical-align:top;text-align:left}th{background:#f6f6f8;position:sticky;top:0}
    .sm{font-size:12px;color:#666}.t-up{color:#0a7a33;font-weight:600}.t-down{color:#b42318;font-weight:600}.note{background:#fffbe6;padding:10px;border-radius:6px}
    @media (prefers-color-scheme:dark){body{background:#111;color:#eee}th{background:#222}td{border-color:#333}.note{background:#332b00}.sm{color:#aaa}}"""
    page = f"""<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>Page change tracker</title><style>{css}</style>
    <h1>{html.escape(config.PRODUCT)} page change tracker</h1><p class=sm>Built {dt.datetime.now().strftime('%b %d %Y %H:%M')} from the site's git history{' and Skald (server logs)' if config.source_on('skald') else ' (Skald is off, so there are no reader counts yet)'}. Readers = visits that read the page (an upper bound on people), whole verified days only.</p>
    <p class=note>Early days: most pages changed 0-2 days ago, so 'after' is tiny. Skald itself calls a change only after 14 whole days. Bounce and time on page are not in this table. Search Console is {'connected' if config.source_on('search_console') else 'not connected yet'}.</p>
    <table><tr><th>Page</th><th>Main change live</th><th>Title before → after</th><th>Words</th><th>Readers before</th><th>Readers after</th><th>Trend</th><th>Search visits b→a</th><th>Top countries</th><th>Googlebot first fetch</th></tr>{''.join(rows_html)}</table>"""
    open(os.path.join(HERE, "report.html"), "w", encoding="utf-8").write(page)
    tot_b = sum(s[1] for s in summary); tot_a = sum(s[2] for s in summary)
    print(f"report.html: {len(summary)} pages; readers before {tot_b}, after {tot_a} (same-length windows per page)")
