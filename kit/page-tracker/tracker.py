"""Page tracker for the site in growth.json: what changed on which page, when it went live, and what happened after.

Data lives in tracker.db (SQLite). Read-only towards Skald, Google and the site repo.
  python3 tracker.py sync      # page list (sitemap + site repo), change dates from git, then every switched-on source
  python3 tracker.py report    # write report.html and data.json (the dashboard's data)
With every outside source off (the default) a sync still runs: pages, clusters and change dates need no key.
"""
import json, os, sqlite3, subprocess, sys, datetime as dt

import config

HERE = config.HERE
DB = config.DB
TZ = config.TZ
GSC_START = dt.date.fromisoformat((config.SOURCES.get("search_console") or {}).get("history_start") or (dt.date.today() - dt.timedelta(days=480)).isoformat())

sys.path.insert(0, config.CODE_DIR)
import skald, repo_meta, sitepaths  # noqa: E402


def db():
    c = sqlite3.connect(DB)
    c.executescript("""
    CREATE TABLE IF NOT EXISTS pages(path TEXT PRIMARY KEY, file TEXT, slug TEXT, kind TEXT, title TEXT);
    CREATE TABLE IF NOT EXISTS ships(sha TEXT PRIMARY KEY, live_at TEXT, passed INTEGER);
    CREATE TABLE IF NOT EXISTS changes(path TEXT, sha TEXT, live_at TEXT, title_before TEXT, title_after TEXT,
        words_before INTEGER, words_after INTEGER, commits TEXT, PRIMARY KEY(path, sha));
    CREATE TABLE IF NOT EXISTS daily(path TEXT, day TEXT, state TEXT, readers INTEGER, views INTEGER, search INTEGER,
        ai_asked INTEGER, ai_training INTEGER, sources TEXT, countries TEXT, assistants TEXT, pulled_at TEXT,
        PRIMARY KEY(path, day));
    CREATE TABLE IF NOT EXISTS milestones(path TEXT, kind TEXT, who TEXT, at TEXT, PRIMARY KEY(path, kind, who));
    CREATE TABLE IF NOT EXISTS lastmod_seen(path TEXT, lastmod TEXT, seen TEXT, PRIMARY KEY(path, lastmod, seen));
    CREATE TABLE IF NOT EXISTS search(path TEXT, day TEXT, clicks INTEGER, impressions INTEGER, ctr REAL, position REAL,
        final INTEGER, PRIMARY KEY(path, day));
    CREATE TABLE IF NOT EXISTS search_queries(path TEXT, snapshot TEXT, query TEXT, clicks INTEGER, impressions INTEGER,
        position REAL, PRIMARY KEY(path, snapshot, query));
    CREATE TABLE IF NOT EXISTS search_countries(path TEXT, snapshot TEXT, country TEXT, clicks INTEGER, impressions INTEGER,
        position REAL, PRIMARY KEY(path, snapshot, country));
    CREATE TABLE IF NOT EXISTS search_split(path TEXT, snapshot TEXT, address TEXT, clicks INTEGER, impressions INTEGER,
        frm TEXT, til TEXT, PRIMARY KEY(path, snapshot, address));
    CREATE TABLE IF NOT EXISTS search_index(path TEXT, inspected_at TEXT, status TEXT, verdict TEXT, coverage TEXT,
        last_crawl TEXT, PRIMARY KEY(path, inspected_at));
    CREATE TABLE IF NOT EXISTS bounce(path TEXT, snapshot TEXT, first TEXT, last TEXT, landed INTEGER, went_on INTEGER,
        PRIMARY KEY(path, snapshot));
    CREATE TABLE IF NOT EXISTS bounce_window(path TEXT, change_at TEXT, win INTEGER, side TEXT, frm TEXT, til TEXT,
        visits INTEGER, landed INTEGER, left_site INTEGER, days_missing INTEGER, pulled_at TEXT,
        PRIMARY KEY(path, change_at, win, side));
    CREATE TABLE IF NOT EXISTS search_window_top(scope TEXT, frm TEXT, til TEXT, kind TEXT, name TEXT, clicks INTEGER,
        impressions INTEGER, position REAL, pulled_at TEXT, PRIMARY KEY(scope, frm, til, kind, name));
    CREATE TABLE IF NOT EXISTS site_index(snapshot TEXT PRIMARY KEY, data TEXT);
    CREATE TABLE IF NOT EXISTS journey_window(path TEXT, change_at TEXT, win INTEGER, side TEXT, frm TEXT, til TEXT,
        data TEXT, pulled_at TEXT, PRIMARY KEY(path, change_at, win, side));
    """)
    return c


git = repo_meta.git


def front(text, key):
    fm, _ = repo_meta.split_md(text)
    v = fm.get(key)
    return None if v is None else str(v)


def words(text):
    _, body = repo_meta.split_md(text)
    return len(body.split())


def tracked_files():
    """Every page in the sitemap (or the repo's own list): (path, content file, slug, kind). A page with no content
    file in the repo is listed with file None: it has no change history."""
    import clusters
    fmap = repo_meta.files()
    out = []
    for pg in sitepaths.fetch()["pages"]:
        path = pg["path"]
        slug = path.strip("/").rsplit("/", 1)[-1] or "home"
        out.append((path, fmap.get(path), slug, clusters.kind_of(path)))
    return out


def sync_ships(c):
    """Every commit on the site's branch (time = when it landed there; the site deploys on push to that branch)."""
    if not repo_meta.repo_ok():
        print(f"git: no site repo at {config.REPO}; change dates skipped")
        return
    ref = repo_meta.branch_ref()
    for line in git("log", ref, "--format=%H\x1f%cI").splitlines():
        sha, at = line.split("\x1f")
        live = dt.datetime.fromisoformat(at).astimezone(TZ).isoformat(timespec="minutes")
        c.execute("INSERT OR REPLACE INTO ships VALUES(?,?,?)", (sha, live, 1))
    c.commit()


def sync_changes(c):
    """Change dates from git: each commit that changed a page's content file is one change (the commit that created the
    file is not a change). A change is 'live' when its commit landed on the site's branch."""
    import clusters
    t = clusters.titles()
    c.execute("DELETE FROM changes")
    c.execute("DELETE FROM pages")
    since = config.CHANGES_SINCE
    ref = repo_meta.branch_ref() if repo_meta.repo_ok() else None
    n_changes = 0
    for path, f, slug, kind in tracked_files():
        srcs = repo_meta.sources(path)
        title = t.get(path)
        if f and f.endswith(".md"):
            try:
                title = front(open(os.path.join(config.REPO, f), encoding="utf-8").read(), "title") or title
            except OSError:
                pass
        c.execute("INSERT OR REPLACE INTO pages VALUES(?,?,?,?,?)", (path, f, slug, kind, title or clusters._name(path)))
        if not srcs or not ref:
            continue
        log = git("log", ref, "--reverse", "--format=%H\x1f%cI\x1f%s", "--", *srcs).splitlines()
        prev = None
        for line in log:
            sha, at, subj = (line.split("\x1f") + ["", ""])[:3]
            try:
                text = "\n".join(git("show", f"{sha}:{x}") if _exists(sha, x) else "" for x in srcs)
            except subprocess.CalledProcessError:
                continue
            live = dt.datetime.fromisoformat(at).astimezone(TZ).isoformat(timespec="minutes")
            if prev is not None and text != prev and (not since or live[:10] >= since):
                c.execute("INSERT OR REPLACE INTO changes VALUES(?,?,?,?,?,?,?,?)",
                          (path, sha, live, front(prev, "title"), front(text, "title"), words(prev), words(text),
                           json.dumps([f"{sha[:7]} {subj}"[:160]])))
                n_changes += 1
            prev = text
    c.commit()
    print(f"changes: {n_changes} from git history of {config.REPO}")


def _exists(sha, rel):
    return subprocess.run(["git", "-C", config.REPO, "cat-file", "-e", f"{sha}:{rel}"], capture_output=True).returncode == 0


def pull(c):
    now = dt.datetime.now(TZ).isoformat(timespec="minutes")
    # growth.json page_tracker.path_variants: copies of a page that are added together per day (just the page itself by default)
    if not skald.enabled():
        print("skald: off, readers not pulled"); return
    for (path,) in c.execute("SELECT path FROM pages").fetchall():
        merged = {}
        for variant in config.variants(path):
            try:
                s = skald.call("page_story", path=variant).get("structuredContent") or {}
            except Exception as e:  # a page Skald has never seen
                print("skald:", variant, str(e)[:120]); continue
            import timeonpage; timeonpage.store(c, path, "root" if variant == path else "us", s)
            for d in s.get("days", []):
                m = merged.setdefault(d["day"], {"state": d.get("state"), "sources": {}, "countries": {}, "assistants": {}})
                for k in ("readers", "views", "search", "ai_asked", "ai_training"):
                    if d.get(k) is not None: m[k] = (m.get(k) or 0) + d[k]
                for k in ("sources", "countries", "assistants"):
                    for kk, vv in (d.get(k) or {}).items():
                        if isinstance(vv, (int, float)): m[k][kk] = m[k].get(kk, 0) + vv
                if variant == path: m["state"] = d.get("state")
            if variant == path:
                m0 = s.get("milestones") or {}
                for kind, v in m0.items():
                    for item in (v if isinstance(v, list) else [v] if v else []):
                        if isinstance(item, dict) and item.get("at"):
                            c.execute("INSERT OR REPLACE INTO milestones VALUES(?,?,?,?)", (path, kind, item.get("who") or "", item["at"]))
                for lm, seen in s.get("lastmod_seen") or []:
                    c.execute("INSERT OR REPLACE INTO lastmod_seen VALUES(?,?,?)", (path, lm, seen))
        for day, d in merged.items():
            c.execute("INSERT OR REPLACE INTO daily VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                      (path, day, d.get("state"), d.get("readers"), d.get("views"), d.get("search"), d.get("ai_asked"),
                       d.get("ai_training"), json.dumps(d["sources"]), json.dumps(d["countries"]),
                       json.dumps(d["assistants"]), now))
    c.commit()
    return


def pull_bounce(c):
    """Skald's funnel over the last 7 days and today: visits that landed on the page, and how many reached any other page.
    Saved once a day, so the rolling 7-day figure builds a history."""
    if not skald.enabled():
        return
    allp = sitepaths.all_paths(); snap = dt.date.today().isoformat()
    for (path,) in c.execute("SELECT path FROM pages").fetchall():
        steps = [{"label": "Landed", "kind": "path", "match": "equals", "paths": [path]},
                 {"label": "Another page", "kind": "path", "match": "equals", "paths": [p for p in allp if p != path]}]
        try:
            r = (skald.call("funnel", steps=steps).get("structuredContent") or {}).get("funnel", {}).get("result", {})
        except Exception as e:
            print("funnel:", path, str(e)[:120]); continue
        st = r.get("steps") or []
        if len(st) == 2:
            c.execute("INSERT OR REPLACE INTO bounce VALUES(?,?,?,?,?,?)", (path, snap, r.get("first"), r.get("last"), st[0]["n"], st[1]["n"]))
    c.commit()





def gsc_windows(full):
    """(from, to) windows of at most 93 days (Skald's limit): the whole history on a full pull, else the last 28 days."""
    end = dt.date.today()
    start = GSC_START if full else end - dt.timedelta(days=27)
    out = []
    while start <= end:
        stop = min(end, start + dt.timedelta(days=92))
        out.append((start.isoformat(), stop.isoformat()))
        start = stop + dt.timedelta(days=1)
    return out


def pull_search(c, full=False):
    """Google Search Console's own figures per page (Skald search_performance, read-only, since 13 Nov 2026):
    clicks, impressions, CTR and position per day for the page copies added together (the whole history
    since 5 May 2026 on a full pull), the page's top queries and countries (a snapshot per day), its URL Inspection
    result, and the whole site's daily figures (path '*')."""
    if not config.source_on("search_console"):
        print("search console: off, Google figures not pulled"); return
    snap = dt.date.today().isoformat()
    paths = [p for (p,) in c.execute("SELECT path FROM pages").fetchall()] + ["*"]
    for path in paths:
        merged = {}
        variants = [None] if path == "*" else config.variants(path) + [a for a in config.aliases(path) if a not in config.variants(path)]
        for variant in variants:
          for frm, to in gsc_windows(full):
            args = {"from": frm, "to": to}
            if variant: args["path"] = variant
            try:
                s = skald.call("search_performance", **args).get("structuredContent") or {}
            except Exception as e:
                print(f"search: no Search Console data for {variant or path} from {frm}: {str(e)[:120]}"); continue
            if to == snap or to == gsc_windows(False)[-1][1]:
                tag = "" if variant is None or variant.rstrip("/") == path.rstrip("/") else "[us] "   # the page itself, with or without its slash
                for q in (s.get("top_queries") or [])[:10]:
                    c.execute("INSERT OR REPLACE INTO search_queries VALUES(?,?,?,?,?,?)",
                              (path, snap, tag + q.get("query", ""), q.get("clicks"), q.get("impressions"), q.get("position")))
                for k in (s.get("countries") or [])[:10]:
                    c.execute("INSERT OR REPLACE INTO search_countries VALUES(?,?,?,?,?,?)",
                              (path, snap, tag + (k.get("country") or ""), k.get("clicks"), k.get("impressions"), k.get("position")))
            if variant and to == gsc_windows(False)[-1][1]:   # the split by address, for the page view
                days = s.get("days", [])
                c.execute("INSERT OR REPLACE INTO search_split VALUES(?,?,?,?,?,?,?)",
                          (path, snap, variant, sum(d.get("clicks") or 0 for d in days), sum(d.get("impressions") or 0 for d in days), frm, to))
            for d in s.get("days", []):
                m = merged.setdefault(d["day"], {"clicks": 0, "impressions": 0, "pw": 0.0, "final": d.get("final")})
                m["clicks"] += d.get("clicks") or 0
                imp = d.get("impressions") or 0
                m["impressions"] += imp
                m["pw"] += (d.get("position") or 0) * imp
            ix = s.get("index") or {}
            if ix.get("inspected_at") and variant == path:
                c.execute("INSERT OR REPLACE INTO search_index VALUES(?,?,?,?,?,?)",
                          (path, ix["inspected_at"], ix.get("status"), ix.get("verdict"), ix.get("coverage"), ix.get("last_crawl") or ix.get("lastCrawlTime")))
        for day, m in merged.items():
            pos = round(m["pw"] / m["impressions"], 2) if m["impressions"] else None
            ctr = round(m["clicks"] / m["impressions"], 4) if m["impressions"] else None
            c.execute("INSERT OR REPLACE INTO search VALUES(?,?,?,?,?,?,?)", (path, day, m["clicks"], m["impressions"], ctr, pos, int(bool(m["final"]))))
    c.commit()

def bounce_plan(c, newest):
    """The 7- and 14-day windows before and after each page's main and latest change (the change day itself skipped).
    The after window stops at Skald's newest whole day; the before window has the same length (all N days while
    nothing after exists yet). Returns [(path, change_at, win, side, from, to, complete)]."""
    out = []
    for (path,) in c.execute("SELECT path FROM pages").fetchall():
        ch = c.execute("SELECT live_at, words_before, words_after FROM changes WHERE path=? ORDER BY live_at", (path,)).fetchall()
        if not ch:
            continue
        main = max(ch, key=lambda r: abs((r[2] or 0) - (r[1] or 0)))[0]
        for change_at in sorted({main, ch[-1][0]}):
            d0 = dt.date.fromisoformat(change_at[:10])
            for win in (7, 14):
                a_from, a_to = d0 + dt.timedelta(days=1), min(d0 + dt.timedelta(days=win), newest)
                n = (a_to - a_from).days + 1
                if n > 0:
                    out.append((path, change_at, win, "after", a_from.isoformat(), a_to.isoformat(), n == win))
                nb = n if n > 0 else win
                out.append((path, change_at, win, "before", (d0 - dt.timedelta(days=nb)).isoformat(),
                            (d0 - dt.timedelta(days=1)).isoformat(), True))
    return out


def pull_bounce_windows(c):
    """Bounce before and after each change, from Skald's page_journeys (read-only; it takes a date range, the funnel tool
    does not). Per window: visits that read the page, visits that landed on it, visits that left the site after it.
    Bounce estimate = landed visits that read nothing after the page = landed - (visits - left), at least 0; exact when
    every visit to the page landed on it. Page copies added together. Windows already stored in full are
    not pulled again. Skald keeps visits for a limited time: days it no longer holds are counted in days_missing."""
    if not skald.enabled():
        return
    newest = dt.date.today() - dt.timedelta(days=1)
    now = dt.datetime.now(TZ).isoformat(timespec="minutes")
    plan = bounce_plan(c, newest)
    groups = {}
    for path, change_at, win, side, frm, to, complete in plan:
        row = c.execute("SELECT frm, til FROM bounce_window WHERE path=? AND change_at=? AND win=? AND side=?",
                        (path, change_at, win, side)).fetchone()
        jw = c.execute("SELECT frm, til FROM journey_window WHERE path=? AND change_at=? AND win=? AND side=?",
                       (path, change_at, win, side)).fetchone()
        if row and row == (frm, to) and jw == (frm, to) and complete:
            continue
        groups.setdefault((frm, to), []).append((path, change_at, win, side))
    calls = 0
    for (frm, to), items in sorted(groups.items()):
        paths = sorted({p for p, *_ in items})
        variants = [v for p in paths for v in config.variants(p)]
        found, missing = {}, 0
        for i in range(0, len(variants), 20):
            try:
                s = skald.call("page_journeys", paths=variants[i:i + 20], **{"from": frm, "to": to}).get("structuredContent") or {}
                calls += 1
            except Exception as e:
                print("journeys:", frm, to, str(e)[:120]); continue
            missing = max(missing, len(s.get("not_kept") or []) + len(s.get("missing_days") or []))
            for pg in s.get("pages") or []:
                found[pg.get("path")] = pg
        for path, change_at, win, side in items:
            v = l = left = 0
            for variant in config.variants(path):
                pg = found.get(variant) or {}
                v += pg.get("visits") or 0
                l += (pg.get("arrived") or {}).get("landed_here") or 0
                left += pg.get("left") or 0
            c.execute("INSERT OR REPLACE INTO bounce_window VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                      (path, change_at, win, side, frm, to, v, l, left, missing, now))
            c.execute("INSERT OR REPLACE INTO journey_window VALUES(?,?,?,?,?,?,?,?)",
                      (path, change_at, win, side, frm, to, json.dumps(journey_summary(path, found)), now))
    c.commit()
    print(f"bounce windows: {len(plan)} planned, {sum(len(x) for x in groups.values())} pulled in {calls} calls")


def journey_summary(path, found):
    """One window of page_journeys for a page (page copies added together):
    the page read next, visits proven to have sent a form (lead) or be a customer, countries and how they arrived.
    Counts only: page_journeys is anonymous, and nothing personal is stored."""
    out = {"visits": 0, "lead": 0, "customer": 0, "next": {}, "countries": {}, "from": {}}
    add = lambda d, k, n: d.__setitem__(k, d.get(k, 0) + (n or 0))
    for variant in config.variants(path):
        pg = found.get(variant) or {}
        out["visits"] += pg.get("visits") or 0
        who = pg.get("who") or {}
        out["lead"] += who.get("lead") or 0; out["customer"] += who.get("customer") or 0
        for x in pg.get("next") or []:
            v = x.get("value") or ""
            add(out["next"], v, x.get("visits"))
        for x in who.get("countries") or []:
            add(out["countries"], x.get("value"), x.get("visits"))
        for x in (pg.get("arrived") or {}).get("landed_from") or []:
            add(out["from"], (x.get("value") or "").split(":")[0], x.get("visits"))
    return out


def pull_search_windows(c):
    """Top searches and countries before vs after the first change (same-length Google windows, see insights.gwin), for
    the whole site and each changed page's root copy, plus the site's index summary. Read-only; a window already pulled
    in full (no provisional day in it) is not pulled again."""
    if not config.source_on("search_console"):
        return
    import insights
    D = dt.date.fromisoformat
    S = c.execute("SELECT min(substr(live_at,1,10)) FROM changes").fetchone()[0]
    last = c.execute("SELECT max(day) FROM search WHERE path='*'").fetchone()[0]
    lastfinal = c.execute("SELECT max(day) FROM search WHERE path='*' AND final=1").fetchone()[0]
    if not (S and last and lastfinal):
        return
    w = insights.gwin(D(S), D(last), D(lastfinal))
    if not w:
        return
    now = dt.datetime.now(TZ).isoformat(timespec="minutes")
    scopes = ["*"] + [p for (p,) in c.execute("SELECT DISTINCT path FROM changes ORDER BY path")]
    calls = 0
    for frm, to, settled in ((w["b_from"], w["b_to"], True), (w["a_from"], w["a_to"], not w["prov"])):
        for scope in scopes:
            if settled and c.execute("SELECT 1 FROM search_window_top WHERE scope=? AND frm=? AND til=? LIMIT 1", (scope, frm, to)).fetchone():
                continue
            args = {"from": frm, "to": to}
            if scope != "*":
                args["path"] = scope
            try:
                s = skald.call("search_performance", **args).get("structuredContent") or {}
                calls += 1
            except Exception as e:
                print("search window:", scope, frm, str(e)[:120]); continue
            c.execute("DELETE FROM search_window_top WHERE scope=? AND frm=? AND til=?", (scope, frm, to))
            for kind, key, items in (("query", "query", s.get("top_queries")), ("country", "country", s.get("countries"))):
                for q in (items or [])[:10]:
                    c.execute("INSERT OR REPLACE INTO search_window_top VALUES(?,?,?,?,?,?,?,?,?)",
                              (scope, frm, to, kind, q.get(key) or "", q.get("clicks"), q.get("impressions"), q.get("position"), now))
            if scope == "*" and s.get("index"):
                ix = s["index"]
                c.execute("INSERT OR REPLACE INTO site_index VALUES(?,?)", (dt.date.today().isoformat(),
                          json.dumps(dict(pages=ix.get("pages"), by_status=ix.get("by_status")))))
    c.commit()
    print(f"search windows: {calls} calls")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "sync"
    c = db()
    if cmd == "sync":
        import clusters; clusters.read_sitemaps(c)
        sync_ships(c); sync_changes(c); pull(c); pull_bounce(c); pull_bounce_windows(c); pull_search(c); pull_search_windows(c)
        import conversions; conversions.pull(c)
        import ga4, diffs; ga4.pull(c); diffs.write_diffs(c); diffs.editor_saves(c)
        import google_updates; google_updates.fetch(c)
        clusters.pull(c)
        n = lambda q: c.execute(q).fetchone()[0]
        print(f"pages {n('SELECT count(*) FROM pages')}, changes {n('SELECT count(*) FROM changes')}, "
              f"daily rows {n('SELECT count(*) FROM daily')}, milestones {n('SELECT count(*) FROM milestones')}")
    elif cmd == "search-history":
        pull_search(c, full=True); print("search rows", c.execute("SELECT count(*) FROM search").fetchone()[0])
    elif cmd == "clusters":
        import clusters; clusters.read_sitemaps(c); clusters.pull(c)
    elif cmd == "google-updates":
        import google_updates; google_updates.fetch(c)
    elif cmd == "bounce-windows":
        pull_bounce_windows(c); pull_search_windows(c)
    elif cmd == "report":
        import report, export; report.write(c); export.write(c)
