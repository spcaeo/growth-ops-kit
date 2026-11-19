"""Leads and conversions from Skald (read-only, added 13 Nov 2026). Counts only: Skald's tools are anonymous and
nothing personal (no name, email or address) is asked for or stored.
- `conversions`: per day, every action that counts (contact forms, demos, sign-ups...): started, completed, abandoned,
  the leads among them, and how many Skald could tie to the page they happened on. Table conversions_daily.
- `leads`: the site's own lead database. Its availability is recorded in conversions_status; when it is not set up,
  the dashboard says so and never shows 0.
Per page, leads come from page_journeys (visits proven to have sent a form; tracker.py, table journey_window).
  python3 conversions.py
"""
import json, os, sqlite3, datetime as dt

import config
HERE = config.HERE      # the project's page-tracker data folder
import config
FIRST = dt.date.fromisoformat(config.TRACKING_START) if config.TRACKING_START else dt.date.today() - dt.timedelta(days=90)  # first day to pull (growth.json search_console_history_start; default: 90 days back)


def schema(c):
    c.executescript("""
    CREATE TABLE IF NOT EXISTS conversions_daily(day TEXT PRIMARY KEY, started INTEGER, completed INTEGER, abandoned INTEGER,
        leads INTEGER, demos INTEGER, by_action TEXT, by_page TEXT, page_links TEXT, withheld INTEGER, pulled_at TEXT);
    CREATE TABLE IF NOT EXISTS conversions_status(at TEXT PRIMARY KEY, leads_available INTEGER, leads_note TEXT);
    """)


def pull(c):
    import skald
    schema(c)
    if not skald.enabled():
        print("conversions: Skald is off"); return
    now = dt.datetime.now().astimezone().isoformat(timespec="minutes")
    last = dt.date.today() - dt.timedelta(days=1)
    have = {r[0] for r in c.execute("SELECT day FROM conversions_daily WHERE day < ?", ((last - dt.timedelta(days=14)).isoformat(),))}
    d, n = FIRST, 0
    while d <= last:
        day = d.isoformat(); d += dt.timedelta(days=1)
        if day in have:  # older days settle; the last 14 are pulled again (Skald changes a day when a lead is marked later)
            continue
        try:
            s = skald.call("conversions", **{"from": day, "to": day, "by": "page"}).get("structuredContent") or {}
        except Exception as e:
            print("conversions:", day, str(e)[:120]); continue
        acts = s.get("actions") or {}
        tot = lambda k: sum((a.get(k) or 0) for a in acts.values())
        withheld = int(day in (s.get("withheld") or []) or day in (s.get("not_recorded") or []))
        c.execute("INSERT OR REPLACE INTO conversions_daily VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                  (day, tot("started"), tot("completed"), tot("abandoned"), s.get("leads") or 0, s.get("demos_booked") or 0,
                   json.dumps({k: v.get("completed") or 0 for k, v in acts.items()}), json.dumps(s.get("leads_by") or {}),
                   json.dumps(s.get("page_links") or {}), withheld, now))
        n += 1
    try:
        l = skald.call("leads").get("structuredContent") or {}
        c.execute("INSERT OR REPLACE INTO conversions_status VALUES(?,?,?)", (now, int(bool(l.get("available"))), l.get("error") or ""))
    except Exception as e:
        c.execute("INSERT OR REPLACE INTO conversions_status VALUES(?,?,?)", (now, 0, str(e)[:200]))
    c.commit()
    print(f"conversions: {n} days pulled")


def export(c):
    """For data.json: {days: [[day, completed, leads, demos, page_known]], by_action (totals), leads_available, leads_note}."""
    schema(c)
    days, acts = [], {}
    for day, comp, leads, demos, by_action, by_page in c.execute(
            "SELECT day, completed, leads, demos, by_action, by_page FROM conversions_daily WHERE withheld=0 ORDER BY day"):
        known = sum(v for k, v in json.loads(by_page or "{}").items() if k not in ("page not known", "Not recorded"))
        days.append([day, comp or 0, leads or 0, demos or 0, known])
        for k, v in json.loads(by_action or "{}").items():
            acts[k] = acts.get(k, 0) + v
    st = c.execute("SELECT at, leads_available, leads_note FROM conversions_status ORDER BY at DESC LIMIT 1").fetchone()
    return dict(days=days, by_action=acts, leads_available=bool(st and st[1]), leads_note=st[2] if st else "not checked yet")


if __name__ == "__main__":
    con = sqlite3.connect(config.DB)
    pull(con)
