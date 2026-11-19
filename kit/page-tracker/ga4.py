"""Google Analytics 4 through Skald's your_tools (read-only, added 13 Nov 2026): the property's landing-page report
(sessions and key events per landing page over GA's own last 28 days, in the property's own time zone), kept as one
snapshot a day in ga4_landing. These are Google Analytics' own counts: never added to Skald's figures. GA's report
holds only its top landing pages, so a page not in it is "not in GA's top list", never 0. The landing report has no
engaged sessions; the site-wide total (sessions, engaged sessions if given) is kept in ga4_totals.
  python3 ga4.py
"""
import json, os, sqlite3, datetime as dt

import config
HERE = config.HERE      # the project's page-tracker data folder


def schema(c):
    c.executescript("""
    CREATE TABLE IF NOT EXISTS ga4_landing(snapshot TEXT, start TEXT, end TEXT, dim TEXT, sessions INTEGER, key_events INTEGER,
        engaged INTEGER, PRIMARY KEY(snapshot, dim));
    CREATE TABLE IF NOT EXISTS ga4_totals(snapshot TEXT PRIMARY KEY, start TEXT, end TEXT, state TEXT, counted_from TEXT, note TEXT,
        figures TEXT);
    """)


def pull(c):
    import skald, config
    schema(c)
    if not config.source_on("ga4") or not skald.enabled():
        print("ga4: off"); return
    snap = dt.date.today().isoformat()
    try:
        tools = (skald.call("your_tools").get("structuredContent") or {}).get("tools") or []
    except Exception as e:
        print("ga4: your_tools failed:", str(e)[:120]); return
    ga = next((t for t in tools if t.get("id") == "ga4"), None)
    if not ga:
        print("ga4: not connected"); return
    rep = (ga.get("reports") or {}).get("landing") or {}
    rows = {}
    for f in rep.get("figures") or []:
        dim = f.get("dim")
        key = "*" if dim is None else dim
        r = rows.setdefault(key, {"sessions": None, "keyEvents": None, "engagedSessions": None})
        if f.get("name") in r:
            r[f["name"]] = f.get("value")
    for dim, r in rows.items():
        c.execute("INSERT OR REPLACE INTO ga4_landing VALUES(?,?,?,?,?,?,?)",
                  (snap, rep.get("start"), rep.get("end"), dim, r["sessions"], r["keyEvents"], r["engagedSessions"]))
    c.execute("INSERT OR REPLACE INTO ga4_totals VALUES(?,?,?,?,?,?,?)",
              (snap, rep.get("start"), rep.get("end"), ga.get("state"), ga.get("counted_from"), rep.get("note"),
               json.dumps(rows.get("*") or {})))
    c.commit()
    print(f"ga4: {len(rows) - 1} landing pages, state {ga.get('state')}")


def export(c):
    """{state, counted_from, note, start, end, total: {...}, pages: {path: {sessions, key_events, engaged, legacy}}}."""
    schema(c)
    t = c.execute("SELECT snapshot, start, end, state, counted_from, note, figures FROM ga4_totals ORDER BY snapshot DESC LIMIT 1").fetchone()
    if not t:
        return None
    pages = {}
    for dim, s, k, e in c.execute("SELECT dim, sessions, key_events, engaged FROM ga4_landing WHERE snapshot=? AND dim!='*'", (t[0],)):
        path = (dim.rstrip("/") or "/")
        pages[path] = dict(sessions=s, key_events=k, engaged=e)
    return dict(snapshot=t[0], start=t[1], end=t[2], state=t[3], counted_from=t[4], note=t[5], total=json.loads(t[6] or "{}"), pages=pages)


if __name__ == "__main__":
    con = sqlite3.connect(__import__("config").DB)
    pull(con)
