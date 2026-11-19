"""Google Search updates (core, spam, helpful content, reviews, Discover...) and Search incidents, from Google's own
Search Status Dashboard JSON feed (https://status.search.google.com/incidents.json; the same list the dashboard's
history pages show). Stored in tracker.db, table google_updates; each fetch logged in google_updates_fetch.
Read-only towards Google: one plain GET, no bot check, no scraping. If the feed cannot be read, nothing is changed and
the error is recorded, so the dashboard says so; dates are never guessed.
  python3 google_updates.py     # fetch now (tracker.py sync runs it every day)
"""
import json, os, re, sqlite3, urllib.request, datetime as dt

import config
HERE = config.HERE      # the project's page-tracker data folder
FEED = "https://status.search.google.com/incidents.json"
PAGE = "https://status.search.google.com/"


def kind_of(service, name):
    n = (name or "").lower()
    if service != "Ranking":
        return "issue"  # crawling, indexing or serving problems
    for k in ("core", "spam", "helpful", "review", "discover"):
        if k in n:
            return k
    return "other"


def schema(c):
    c.executescript("""
    CREATE TABLE IF NOT EXISTS google_updates(id TEXT PRIMARY KEY, service TEXT, kind TEXT, name TEXT, begin TEXT,
        end TEXT, status TEXT, note TEXT, link TEXT, fetched_at TEXT);
    CREATE TABLE IF NOT EXISTS google_updates_fetch(at TEXT PRIMARY KEY, ok INTEGER, rows INTEGER, error TEXT);
    """)


def fetch(c):
    import config
    schema(c)
    if not config.source_on("google_updates"):
        print("google updates: off"); return
    now = dt.datetime.now().astimezone().isoformat(timespec="minutes")
    try:
        req = urllib.request.Request(FEED, headers={"User-Agent": "page-tracker/1.0 (local dashboard)", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            items = json.loads(r.read().decode("utf-8"))
        if not isinstance(items, list):
            raise ValueError("the feed is not a list")
        n = 0
        for i in items:
            if not i.get("id") or not i.get("begin"):
                continue
            last = (i.get("most_recent_update") or {})
            note = re.sub(r"\s*<https?://[^>]+>", "", last.get("text") or "")[:400]
            c.execute("INSERT OR REPLACE INTO google_updates VALUES(?,?,?,?,?,?,?,?,?,?)",
                      (i["id"], i.get("service_name"), kind_of(i.get("service_name"), i.get("external_desc")),
                       i.get("external_desc"), i["begin"], i.get("end"), i.get("status_impact"), note,
                       PAGE + (i.get("uri") or ""), now))
            n += 1
        c.execute("INSERT OR REPLACE INTO google_updates_fetch VALUES(?,?,?,?)", (now, 1, n, None))
        print(f"google updates: {n} from the Search Status Dashboard")
    except Exception as e:  # keep what we had; record why
        c.execute("INSERT OR REPLACE INTO google_updates_fetch VALUES(?,?,?,?)", (now, 0, 0, f"{type(e).__name__}: {e}"[:300]))
        print("google updates: could not read the feed:", e)
    c.commit()


def export(c):
    """For data.json: {updates: [...], fetched, ok, error, source}."""
    schema(c)
    last = c.execute("SELECT at, ok, error FROM google_updates_fetch ORDER BY at DESC LIMIT 1").fetchone()
    ok_at = c.execute("SELECT max(at) FROM google_updates_fetch WHERE ok=1").fetchone()[0]
    rows = [dict(id=r[0], service=r[1], kind=r[2], name=r[3], begin=r[4], end=r[5], note=r[6], link=r[7])
            for r in c.execute("SELECT id, service, kind, name, begin, end, note, link FROM google_updates ORDER BY begin")]
    return dict(updates=rows, fetched=ok_at, last_try=last and last[0], ok=bool(last and last[1]),
                error=last and last[2], source=PAGE)


if __name__ == "__main__":
    con = sqlite3.connect(__import__("config").DB)
    fetch(con)
