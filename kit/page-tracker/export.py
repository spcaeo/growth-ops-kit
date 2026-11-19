"""Write data.json for the dashboard (dashboard.html + dashboard.js) from tracker.db."""
import json, os, datetime as dt
import config, timeonpage, conversions, diffs, ga4, findings

import config
HERE = config.HERE      # the project's page-tracker data folder


def _merge_top(rows):
    """Top queries or countries: the page copies ('[us] ' tag marks a second copy) added together.
    rows: (name, clicks, impressions, position). Returns [name, clicks, impressions, position, copies]."""
    out = {}
    for name, clicks, imp, pos in rows:
        us = name.startswith("[us] ")
        key = name[5:] if us else name
        m = out.setdefault(key, {"c": 0, "i": 0, "pw": 0.0, "copies": set()})
        m["c"] += clicks or 0
        m["i"] += imp or 0
        m["pw"] += (pos or 0) * (imp or 0)
        m["copies"].add("us" if us else "root")
    res = [[k, m["c"], m["i"], round(m["pw"] / m["i"], 1) if m["i"] else None,
            "both" if len(m["copies"]) > 1 else next(iter(m["copies"]))] for k, m in out.items()]
    return sorted(res, key=lambda r: (-r[2], -r[1], r[0]))


def _search(c, path):
    """Daily Google figures: [day, clicks, impressions, position, final(0/1)]."""
    return [[r[0], r[1] or 0, r[2] or 0, r[3], r[4] or 0]
            for r in c.execute("SELECT day, clicks, impressions, position, final FROM search WHERE path=? ORDER BY day", (path,))]


def _top(c, table, col, path):
    snap = c.execute(f"SELECT max(snapshot) FROM {table} WHERE path=?", (path,)).fetchone()[0]
    if not snap:
        return None, []
    rows = c.execute(f"SELECT {col}, clicks, impressions, position FROM {table} WHERE path=? AND snapshot=?", (path, snap)).fetchall()
    return snap, _merge_top(rows)


def write(c):
    pages = []
    for path, slug, kind, title in c.execute("SELECT path, slug, kind, title FROM pages ORDER BY slug").fetchall():
        changes = [dict(sha=r[0], live_at=r[1], title_before=r[2], title_after=r[3], words_before=r[4], words_after=r[5],
                        commits=json.loads(r[6] or "[]"))
                   for r in c.execute("SELECT sha, live_at, title_before, title_after, words_before, words_after, commits FROM changes "
                                      "WHERE path=? ORDER BY live_at", (path,))]
        main = max(changes, key=lambda x: abs((x["words_after"] or 0) - (x["words_before"] or 0)), default=None)
        # se = visits from a search engine (Skald sources["Search engine"]); Skald's own 'search' field is not that
        days = [dict(day=r[0], state=r[1], readers=r[2], views=r[3], ai_asked=r[5], ai_training=r[6],
                     se=(json.loads(r[7] or "{}")).get("Search engine", 0), sources=json.loads(r[7] or "{}"), countries=json.loads(r[8] or "{}"),
                     assistants=json.loads(r[9] or "{}"))
                for r in c.execute("SELECT day, state, readers, views, search, ai_asked, ai_training, sources, countries, assistants FROM daily "
                                   "WHERE path=? ORDER BY day", (path,))]
        ms = [dict(kind=r[0], who=r[1], at=r[2]) for r in c.execute("SELECT kind, who, at FROM milestones WHERE path=? ORDER BY at", (path,))]
        bounce = [dict(snapshot=r[0], first=r[1], last=r[2], landed=r[3], went_on=r[4])
                  for r in c.execute("SELECT snapshot, first, last, landed, went_on FROM bounce WHERE path=? ORDER BY snapshot", (path,))]
        ix = c.execute("SELECT status, verdict, coverage, inspected_at, last_crawl FROM search_index WHERE path=? "
                       "ORDER BY inspected_at DESC LIMIT 1", (path,)).fetchone()
        qsnap, queries = _top(c, "search_queries", "query", path)
        csnap, countries = _top(c, "search_countries", "country", path)
        bw = [dict(change_at=r[0], win=r[1], side=r[2], frm=r[3], to=r[4], visits=r[5], landed=r[6], left=r[7], missing=r[8])
              for r in c.execute("SELECT change_at, win, side, frm, til, visits, landed, left_site, days_missing FROM bounce_window WHERE path=?", (path,))]
        pages.append(dict(path=path, slug=slug, kind=kind, title=title, main=main and main["live_at"], changes=changes,
                          days=days, milestones=ms, bounce=bounce, bw=bw, gs=_search(c, path), gq=queries[:15], gc=countries[:15],
                          gsnap=qsnap or csnap, top=timeonpage.export(c, path), edits=diffs.export_saves(c, path),
                          diff_file="diffs/" + diffs.page_file_name(path),
                          jw=[dict(change_at=r[0], win=r[1], side=r[2], frm=r[3], to=r[4], **json.loads(r[5] or "{}"))
                              for r in c.execute("SELECT change_at, win, side, frm, til, data FROM journey_window WHERE path=?", (path,))],
                          index=dict(status=ix[0], verdict=ix[1], coverage=ix[2], at=ix[3], last_crawl=ix[4]) if ix else None))
    # every page of the site's sitemap clusters (clusters.py): cluster per page, and the pages the tracker does not
    # follow in full as light entries (Google and readers only), so untouched clusters show too
    import clusters as cmod
    cur = cmod.current(c)
    cluster_of = {path: cl for path, cl, _t in cur}
    for p in pages:
        p["cluster"] = cluster_of.get(p["path"], "page")
        p["tracked"] = True
    have = {p["path"] for p in pages}
    for path, cl, title in cur:
        if path in have:
            continue
        days = [dict(day=r[0], state=r[1], readers=r[2], se=r[3] or 0, views=None, ai_training=r[4], ai_asked=r[5],
                     assistants=json.loads(r[6] or "{}"), countries=json.loads(r[7] or "{}"), sources={})
                for r in c.execute("SELECT day, state, readers, se, ai_training, ai_asked, assistants, countries FROM site_daily WHERE path=? ORDER BY day", (path,))]
        slug = path.strip("/").rsplit("/", 1)[-1] or "home"
        pages.append(dict(path=path, slug=slug, kind=cmod.kind_of(path), title=title, main=None, changes=[], days=days,
                          milestones=[], bounce=[], bw=[], gs=_search(c, path), gq=[], gc=[],
                          gsnap=None, index=None, cluster=cl, tracked=False, top=timeonpage.export(c, path), jw=[],
                          edits=diffs.export_saves(c, path)))
    names = cmod.cluster_names()
    clusters = []
    for cl in sorted({x[1] for x in cur}, key=lambda k: cmod.ORDER.index(k) if k in cmod.ORDER else 99):
        paths = [x[0] for x in cur if x[1] == cl]
        tot = {}
        for path in paths:
            for d, cl_, im, po, fi in _search(c, path):
                t = tot.setdefault(d, [0, 0, 0.0, 1])
                t[0] += cl_; t[1] += im; t[2] += (po or 0) * im; t[3] = min(t[3], fi)
        gs = [[d, t[0], t[1], round(t[2] / t[1], 2) if t[1] else None, t[3]] for d, t in sorted(tot.items())]
        rule = next((x for x in config.CLUSTERS if x["id"] == cl), {})
        hub = (rule.get("prefix") or "/").rstrip("/") or "/"
        clusters.append(dict(id=cl, name=names.get(cl) or cl, sitemap=config.SITEMAP_URL, hub=hub, paths=paths, gs=gs))
    qsnap, queries = _top(c, "search_queries", "query", "*")
    csnap, countries = _top(c, "search_countries", "country", "*")
    site = dict(gs=_search(c, "*"), gq=queries[:25], gc=countries[:25], gsnap=qsnap or csnap)
    import insights, google_updates
    gu = google_updates.export(c)
    ins = insights.compute(c)
    open(os.path.join(HERE, "insights-digest.json"), "w", encoding="utf-8").write(json.dumps(insights.digest(ins, gu), indent=1))
    conv = conversions.export(c)
    gday = lambda d: dt.date.fromisoformat(d)
    # no Google figures yet (Search Console off): the "newest Google day" is today, so findings stay empty and honest
    g_last = gday(max(site["gs"])[0]) if site["gs"] else dt.date.today()
    g_final = gday(max((r[0] for r in site["gs"] if r[4]), default=max(site["gs"])[0])) if site["gs"] else dt.date.today()
    first_change = c.execute("SELECT min(live_at) FROM changes").fetchone()[0]
    # release line : version = the kit version (or growth.json page_tracker.version) (bumped on purpose), build = a counter that only goes up,
    # stamped here on every report, time = when this data.json was built (shown in the owner's zone by the dashboard)
    c.execute("CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT)")
    build = int((c.execute("SELECT v FROM meta WHERE k='build'").fetchone() or ["0"])[0]) + 1
    c.execute("INSERT OR REPLACE INTO meta VALUES('build', ?)", (str(build),)); c.commit()
    out = dict(built=dt.datetime.now().astimezone().isoformat(timespec="minutes"),
               release=dict(version=config.CFG.get("version", "0.0.0"), build=build,
                            built=dt.datetime.now(config.TZ).isoformat(timespec="minutes")),
               start=first_change or (config.TRACKING_START and config.TRACKING_START + "T00:00:00"), config=config.public(),
               site=site, insights=ins, pages=pages, gupdates=gu, clusters=clusters, conversions=conv, ga4=ga4.export(c),
               findings=findings.build(ins, pages, clusters, gu, g_last, g_final, conv["days"]))
    open(os.path.join(HERE, "cluster-digests.json"), "w", encoding="utf-8").write(json.dumps(out["findings"].pop("cluster_digests"), indent=1))
    open(os.path.join(HERE, "data.json"), "w", encoding="utf-8").write(json.dumps(out, separators=(",", ":")))
    print(f"data.json: {len(pages)} pages, {len(site['gs'])} site days")
