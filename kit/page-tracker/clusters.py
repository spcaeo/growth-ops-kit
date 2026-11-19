"""Clusters: every public page of the site, grouped by the rules in growth.json (`page_tracker.clusters`, else one cluster per silo). The page list comes from
the site's sitemap (sitepaths.py), else the site repo. Read-only towards the site repo.

Tables in tracker.db:
  site_pages(path, cluster, title, source, seen)  every page in the sitemap, with its cluster
  site_daily(path, day, state, readers, search, se)  Skald readers per day for pages the tracker does not follow in
                                                     full (all pages are followed in full by default, so it stays empty)
Google figures go into the `search` table, one row per page per day, when Search Console is switched on.
  python3 clusters.py            # read the sitemap, then pull Google and readers if those sources are on
"""
import json, os, re, sqlite3, datetime as dt
import config, repo_meta, sitepaths

HERE = config.HERE
ORDER = config.cluster_order()


def schema(c):
    c.executescript("""
    CREATE TABLE IF NOT EXISTS site_pages(path TEXT PRIMARY KEY, cluster TEXT, title TEXT, source TEXT, seen TEXT);
    CREATE TABLE IF NOT EXISTS site_daily(path TEXT, day TEXT, state TEXT, readers INTEGER, search INTEGER, pulled_at TEXT,
        PRIMARY KEY(path, day));
    """)
    have = [r[1] for r in c.execute("PRAGMA table_info(site_daily)")]
    for col, typ in (("se", "INTEGER"), ("ai_training", "INTEGER"), ("ai_asked", "INTEGER"), ("assistants", "TEXT"), ("countries", "TEXT")):
        if col not in have:
            c.execute(f"ALTER TABLE site_daily ADD COLUMN {col} {typ}")  # se = visits from a search engine (Skald sources)


def cluster_names():
    return config.cluster_names()


def titles():
    """path -> title, from the content files' frontmatter (pages without a file get a readable name)."""
    out = {}
    for d in repo_meta.docs():
        if d["fm"].get("title"):
            out[d["url"]] = str(d["fm"]["title"])
    return out


def _name(path):
    if path == "/":
        return "Home"
    return path.rstrip("/").rsplit("/", 1)[-1].replace("-", " ").capitalize()


def read_sitemaps(c):
    schema(c)
    r = sitepaths.fetch()
    today = dt.date.today().isoformat()
    t, n = titles(), 0
    for pg in r["pages"]:
        path = pg["path"]
        c.execute("INSERT OR REPLACE INTO site_pages VALUES(?,?,?,?,?)",
                  (path, config.cluster_of(path), t.get(path) or _name(path), r["source"], today))
        n += 1
    c.commit()
    note = f" (sitemap not read: {r['error']}; used the {r['source']} list)" if r.get("error") else ""
    note += f" (stale copy: {r['stale']})" if r.get("stale") else ""
    print(f"clusters: {n} pages from the {r['source']}{note}")
    return n


def current(c):
    """(path, cluster, title) of the pages in the newest sitemap read."""
    schema(c)
    last = c.execute("SELECT max(seen) FROM site_pages").fetchone()[0]
    return c.execute("SELECT path, cluster, title FROM site_pages WHERE seen=? ORDER BY cluster, path", (last,)).fetchall()


def pull(c, readers_only=False):
    """Google (search_performance) and readers (page_story) for the cluster pages the tracker does not already follow,
    page copies added together. The first pull of a page takes its whole Google history (config: search_console.history_start).
    readers_only: skip Google (a quick refresh of readers, search-engine visits and time on page)."""
    import skald, tracker, timeonpage
    if not skald.enabled():
        print("clusters: Skald is off, no Google or readers pulled")
        return
    tracked = {p for (p,) in c.execute("SELECT path FROM pages")}
    now = dt.datetime.now().astimezone().isoformat(timespec="minutes")
    todo = [p for p, _cl, _t in current(c) if p not in tracked]
    for path in todo:
        if not readers_only:
            pull_google(c, path, skald, tracker)
        days = {}
        for variant in config.variants(path):
            try:
                s = skald.call("page_story", path=variant).get("structuredContent") or {}
            except Exception:
                continue  # a page Skald has never seen
            timeonpage.store(c, path, "root" if variant == path else "us", s)
            for d in s.get("days", []):
                m = days.setdefault(d["day"], {"state": d.get("state"), "readers": 0, "search": 0, "se": 0, "ai_training": 0, "ai_asked": 0,
                                               "assistants": {}, "countries": {}})
                m["readers"] += d.get("readers") or 0; m["search"] += d.get("search") or 0
                m["se"] += (d.get("sources") or {}).get("Search engine") or 0
                m["ai_training"] += d.get("ai_training") or 0; m["ai_asked"] += d.get("ai_asked") or 0
                for key in ("assistants", "countries"):
                    for k, v in (d.get(key) or {}).items():
                        if isinstance(v, (int, float)):
                            m[key][k] = m[key].get(k, 0) + v
                if variant == path:
                    m["state"] = d.get("state")
        for day, m in days.items():
            c.execute("INSERT OR REPLACE INTO site_daily(path, day, state, readers, search, pulled_at, se, ai_training, ai_asked, assistants, countries) "
                      "VALUES(?,?,?,?,?,?,?,?,?,?,?)", (path, day, m["state"], m["readers"], m["search"], now, m["se"], m["ai_training"],
                                                      m["ai_asked"], json.dumps(m["assistants"]), json.dumps(m["countries"])))
        c.commit()
    print(f"clusters: {'readers' if readers_only else 'Google and readers'} pulled for {len(todo)} untracked pages")


def pull_google(c, path, skald, tracker):
    full = not c.execute("SELECT 1 FROM search WHERE path=? LIMIT 1", (path,)).fetchone()
    merged = {}
    for variant in config.variants(path):
        for frm, to in tracker.gsc_windows(full):
            try:
                s = skald.call("search_performance", **{"from": frm, "to": to, "path": variant}).get("structuredContent") or {}
            except Exception as e:
                print("cluster search:", variant, str(e)[:100]); continue
            for d in s.get("days", []):
                m = merged.setdefault(d["day"], {"clicks": 0, "impressions": 0, "pw": 0.0, "final": d.get("final")})
                m["clicks"] += d.get("clicks") or 0
                imp = d.get("impressions") or 0
                m["impressions"] += imp; m["pw"] += (d.get("position") or 0) * imp
    for day, m in merged.items():
        pos = round(m["pw"] / m["impressions"], 2) if m["impressions"] else None
        ctr = round(m["clicks"] / m["impressions"], 4) if m["impressions"] else None
        c.execute("INSERT OR REPLACE INTO search VALUES(?,?,?,?,?,?,?)", (path, day, m["clicks"], m["impressions"], ctr, pos, int(bool(m["final"]))))


def kind_of(path):
    """hub = a topic hub page (/<silo>), post = a blog post, feature = another page inside a topic,
    page = everything else (home, pricing, about, legal, blog index)."""
    parts = [x for x in path.strip("/").split("/") if x]
    cl = config.cluster_of(path)
    if len(parts) >= 2 and parts[-2] == "blog" or (len(parts) == 2 and parts[0] == "blog"):
        return "post"
    if len(parts) == 1 and cl not in ("core", "blog") and parts[0] == cl:
        return "hub"
    if len(parts) == 2 and cl not in ("core", "blog"):
        return "feature"
    return "page"


if __name__ == "__main__":
    con = sqlite3.connect(config.DB)
    read_sitemaps(con); pull(con)
