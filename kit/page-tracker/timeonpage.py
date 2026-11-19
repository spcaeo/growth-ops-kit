"""Time on page from Skald's page_story (added 13 Nov 2026): per day (median seconds, how many visits were measured,
how many were not because the page was the visit's last) and Skald's rolling summary (median over its last N days,
with the minimum number of measured visits it needs). Stored per copy: variant 'root' (the page) or 'us' (a second copy, unused when config path_variants has one entry), because
medians cannot be added together. Read-only towards Skald; called from tracker.pull and clusters.pull."""
import datetime as dt


def schema(c):
    c.executescript("""
    CREATE TABLE IF NOT EXISTS time_on_page(path TEXT, variant TEXT, day TEXT, median_s REAL, measured INTEGER,
        not_measured INTEGER, PRIMARY KEY(path, variant, day));
    CREATE TABLE IF NOT EXISTS time_on_page_window(path TEXT, variant TEXT, snapshot TEXT, median_s REAL, measured INTEGER,
        not_measured INTEGER, min_measured INTEGER, days INTEGER, PRIMARY KEY(path, variant, snapshot));
    """)


def store(c, path, variant, story):
    """story: page_story's structuredContent for one copy of the page."""
    schema(c)
    for d in story.get("days", []):
        t = d.get("time_on_page")
        if isinstance(t, dict):
            c.execute("INSERT OR REPLACE INTO time_on_page VALUES(?,?,?,?,?,?)",
                      (path, variant, d["day"], t.get("median_s"), t.get("measured"), t.get("not_measured_last_page")))
    w = story.get("time_on_page")
    if isinstance(w, dict):
        c.execute("INSERT OR REPLACE INTO time_on_page_window VALUES(?,?,?,?,?,?,?,?)",
                  (path, variant, dt.date.today().isoformat(), w.get("median_s"), w.get("measured"),
                   w.get("not_measured_last_page"), w.get("min_measured"), w.get("days")))


def export(c, path):
    """For data.json: {days: [[day, median_s, measured, not_measured]] (root copy, plus the US copy's counts),
    window: Skald's latest rolling summary of the root copy, window_us: the same for the second copy}."""
    schema(c)
    us = {r[0]: r[1:] for r in c.execute("SELECT day, median_s, measured, not_measured FROM time_on_page WHERE path=? AND variant='us'", (path,))}
    days = []
    for day, med, m, nm in c.execute("SELECT day, median_s, measured, not_measured FROM time_on_page WHERE path=? AND variant='root' ORDER BY day", (path,)):
        u = us.get(day, (None, 0, 0))
        days.append([day, med, (m or 0), (nm or 0), u[0], (u[1] or 0)])
    def win(v):
        r = c.execute("SELECT snapshot, median_s, measured, not_measured, min_measured, days FROM time_on_page_window WHERE path=? AND variant=? "
                      "ORDER BY snapshot DESC LIMIT 1", (path, v)).fetchone()
        return dict(snapshot=r[0], median_s=r[1], measured=r[2], not_measured=r[3], min_measured=r[4], days=r[5]) if r else None
    return dict(days=days, window=win("root"), window_us=win("us"))
