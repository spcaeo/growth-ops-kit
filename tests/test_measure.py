"""growth measure and the measure-stage fixes (#50, #53): windows 7/14/28/56 on the release date, the frozen baseline used before
and after, page numbers apart from the site's, re-checks tied to the release, the insights page filter and release choice, and
the snapshot's clicks no longer added across overlapping windows. No network; the tracker database is built in the test."""
import datetime as dt
import json
import os
import sqlite3
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "kit" / "tools"
TRACKER = ROOT / "kit" / "page-tracker"
sys.path.insert(0, str(TOOLS))
import measure  # noqa: E402

REL = dt.date(2026, 6, 1)


def iso(n):
    return (REL + dt.timedelta(days=n)).isoformat()


def make_db(path, page_before=(2, 100), page_after=(3, 150), last_day=70, unsettled_from=None):
    c = sqlite3.connect(path)
    c.executescript("CREATE TABLE search(path TEXT, day TEXT, clicks INTEGER, impressions INTEGER, ctr REAL, position REAL, final INTEGER, PRIMARY KEY(path, day));"
                    "CREATE TABLE search_queries(path TEXT, snapshot TEXT, query TEXT, clicks INTEGER, impressions INTEGER, position REAL);")
    for i in range(-70, last_day + 1):
        cl, im = page_before if i < 0 else page_after
        fin = 0 if unsettled_from is not None and i >= unsettled_from else 1
        if i != 0:
            c.execute("INSERT INTO search VALUES('/pm',?,?,?,0,4.0,?)", (iso(i), cl, im, fin))
            c.execute("INSERT INTO search VALUES('*',?,?,?,0,8.0,?)", (iso(i), 10, 1000, fin))   # the site does not move
    c.execute("INSERT INTO search_queries VALUES('/pm',?,'board tools',3,500,2.0)", (iso(60),))
    c.execute("INSERT INTO search_queries VALUES('/pm',?,'new term',1,50,9.0)", (iso(60),))
    c.commit(); c.close()
    return path


def rec(base=True):
    r = {"baseline": {}}
    if base:
        r["baseline"] = {"frozen_on": "2026-05-31", "window": {"from": iso(-28), "to": iso(-1)}, "definition": "page rows, all countries",
                         "totals": {"clicks": 56, "impressions": 2800, "position": 4.0}, "site_totals": {"clicks": 280, "impressions": 28000, "position": 8.0},
                         "queries": [{"query": "board tools", "clicks": 3, "impressions": 500, "position": 6.0}, {"query": "gone term", "clicks": 0, "impressions": 20, "position": 12.0}]}
    return r


def test_windows_after_the_release_are_measured_against_the_frozen_baseline(tmp_path):
    db = make_db(tmp_path / "t.db")
    res = measure.run_all(db, "/pm", rec(), REL, (7, 14, 28, 56), REL + dt.timedelta(days=70))
    w7 = res["page_numbers"][0]
    assert w7["status"] == "measured" and "frozen baseline" in w7["before_source"]
    rows = {r["metric"]: r for r in w7["rows"]}
    assert rows["impressions"]["before"] == 100.0 and rows["impressions"]["after"] == 150.0 and rows["impressions"]["verdict"] == "better"
    assert rows["clicks"]["before"] == 2.0 and rows["clicks"]["after"] == 3.0
    assert [w["n"] for w in res["page_numbers"]] == [7, 14, 28, 56] and all(w["status"] == "measured" for w in res["page_numbers"])
    # the same baseline numbers at every window
    assert {w["before_source"] for w in res["page_numbers"]} == {w7["before_source"]}


def test_the_site_numbers_are_a_separate_table_and_never_the_pages(tmp_path):
    res = measure.run_all(make_db(tmp_path / "t.db"), "/pm", rec(), REL, (7,), REL + dt.timedelta(days=30))
    page, site = res["page_numbers"][0]["rows"], res["site_numbers"][0]["rows"]
    assert {r["metric"]: r["after"] for r in page}["impressions"] == 150.0
    assert {r["metric"]: r["after"] for r in site}["impressions"] == 1000.0
    assert {r["metric"]: r["verdict"] for r in site}["impressions"] == "no clear change"        # the site did not move
    assert "never the page's own" in res["site_note"]


def test_a_window_that_is_not_over_says_not_yet_and_unsettled_days_are_too_early(tmp_path):
    db = make_db(tmp_path / "t.db")
    res = measure.run_all(db, "/pm", rec(), REL, (7, 14, 28, 56), REL + dt.timedelta(days=20))
    assert [w["status"] for w in res["page_numbers"]] == ["measured", "measured", "not yet", "not yet"]
    assert res["page_numbers"][2]["ready_on"] == iso(29)
    db2 = make_db(tmp_path / "u.db", unsettled_from=5)
    w = measure.run_all(db2, "/pm", rec(), REL, (7,), REL + dt.timedelta(days=10))["page_numbers"][0]
    assert w["provisional_days"] == 3 and {r["verdict"] for r in w["rows"]} == {"too early"}


def test_without_a_baseline_the_tracker_rows_before_the_release_are_used(tmp_path):
    w = measure.run_all(make_db(tmp_path / "t.db"), "/pm", rec(False), REL, (7,), REL + dt.timedelta(days=30))["page_numbers"][0]
    assert w["before_source"].startswith("tracker rows") and {r["metric"]: r["before"] for r in w["rows"]}["impressions"] == 100.0


def test_a_baseline_that_reaches_the_release_is_not_a_before(tmp_path):
    r = rec()
    r["baseline"]["window"]["to"] = iso(3)
    w = measure.run_all(make_db(tmp_path / "t.db"), "/pm", r, REL, (7,), REL + dt.timedelta(days=30))["page_numbers"][0]
    assert w["before_source"].startswith("tracker rows") and "not a 'before'" in w["note"]


def test_searches_won_lost_and_moved_come_from_the_baseline_list(tmp_path):
    q = measure.run_all(make_db(tmp_path / "t.db"), "/pm", rec(), REL, (7,), REL + dt.timedelta(days=30))["queries"]
    assert [x["query"] for x in q["won"]] == ["new term"] and [x["query"] for x in q["lost"]] == ["gone term"]
    assert q["moved"] == [{"query": "board tools", "before": 6.0, "after": 2.0}]


def run(project, script, *args):
    env = {**os.environ, "GROWTH_PROJECT": str(project), "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run([sys.executable, str(TOOLS / script), *args], capture_output=True, text=True, env=env, cwd=project)


def test_schedule_files_the_four_rechecks_on_the_release_dates_and_the_gate_reads_them(demo_project):
    p = demo_project
    r = run(p, "measure.py", "schedule", "/pm", "--release", "2026-06-01")
    assert r.returncode == 0, r.stderr
    due = sorted(e["recheck_on"] for e in map(json.loads, (p / "journal" / "entries.jsonl").read_text().splitlines()) if "measure" in e["tags"])
    assert due == ["2026-06-08", "2026-06-15", "2026-06-29", "2026-07-27"]
    assert run(p, "measure.py", "schedule", "/pm", "--release", "June 1").returncode != 0


def gate_line(project, extra_entries):
    from gatelib import CHECKS
    from gatelib.core import Ctx, run_check
    tag = dt.datetime.now().strftime("%Y-%m-%d %H:%M UTC")
    (project / "journal").mkdir(exist_ok=True)
    rel = {"id": "J1", "at": tag, "pages": ["/pm"], "kind": "note", "status": "done", "tags": ["release"], "recheck_on": ""}
    (project / "journal" / "entries.jsonl").write_text("\n".join(json.dumps(e) for e in [rel] + extra_entries) + "\n")
    c = Ctx(project=project, path="/pm", key="pm", cfg={"timezone": "UTC"})
    run_check(c, CHECKS["ev.rechecks-release"])
    return c.lines[-1]


def test_four_unrelated_rechecks_no_longer_pass_ev_rechecks_release(tmp_path):
    today = dt.date.today()
    mk = lambda i, on: {"id": f"J{i}", "at": dt.datetime.now().strftime("%Y-%m-%d %H:%M UTC"), "pages": ["/pm"], "kind": "note", "status": "open", "tags": [], "recheck_on": on}
    wrong = [mk(i + 2, (today + dt.timedelta(days=100 + i)).isoformat()) for i in range(4)]
    assert gate_line(tmp_path, wrong).level == "FAIL"
    right = [mk(i + 2, (today + dt.timedelta(days=n)).isoformat()) for i, n in enumerate((7, 14, 28, 56))]
    assert gate_line(tmp_path, right).level == "OK"
    assert gate_line(tmp_path, right[:3]).level == "FAIL"


def test_snapshot_clicks_are_not_added_across_overlapping_windows(demo_project):
    code = textwrap.dedent("""
        import sys, sqlite3
        sys.path.insert(0, %r)
        import page_snapshot
        c = sqlite3.connect(page_snapshot.ROOT / 'page-tracker' / 'tracker.db')
        c.executescript("CREATE TABLE search_queries(path TEXT, snapshot TEXT, query TEXT, clicks INTEGER, impressions INTEGER, position REAL);"
                        "CREATE TABLE daily(path TEXT, readers INTEGER, views INTEGER, search INTEGER, ai_asked INTEGER);")
        for day in ('2026-06-01', '2026-06-02', '2026-06-03'):      # three syncs, each a rolling 28-day window of the same clicks
            c.execute("INSERT INTO search_queries VALUES('/pm', ?, 'board tools', 10, 400, 3.0)", (day,))
        c.commit(); c.close()
        q = page_snapshot.tracker_rows('/pm')['stored_queries']
        assert q == [{'query': 'board tools', 'clicks': 10, 'impressions': 400, 'position': 3.0}], q
        print('ok')
    """) % str(TOOLS)
    (demo_project / "page-tracker").mkdir(exist_ok=True)
    env = {**os.environ, "GROWTH_PROJECT": str(demo_project), "PYTHONDONTWRITEBYTECODE": "1"}
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, timeout=60)
    assert r.returncode == 0 and "ok" in r.stdout, r.stderr


def test_insights_judge_the_latest_release_per_page_count_only_changed_pages_readers_and_give_all_four_windows(demo_project):
    code = textwrap.dedent("""
        import sys, datetime as dt
        sys.path.insert(0, %r)
        import tracker, insights
        c = tracker.db()
        t = dt.date.today()
        d = lambda n: (t - dt.timedelta(days=n)).isoformat()
        c.execute("INSERT INTO pages VALUES('/pm','','pm','page','PM')")
        c.execute("INSERT INTO pages VALUES('/other','','other','page','Other')")
        c.execute("INSERT INTO changes VALUES('/pm','a',?, '', '', 100, 900, '[]')", (d(80) + 'T09:00',))     # the BIG word change, long ago
        c.execute("INSERT INTO changes VALUES('/pm','b',?, '', '', 900, 905, '[]')", (d(40) + 'T09:00',))     # this release
        for n in range(1, 120):
            c.execute("INSERT INTO search VALUES('/pm',?,1,100,0,4,1)", (d(n),))
            c.execute("INSERT INTO search VALUES('*',?,10,1000,0,8,1)", (d(n),))
            c.execute("INSERT INTO daily(path, day, state, readers) VALUES('/pm',?,'ok',2)", (d(n),))
            c.execute("INSERT INTO daily(path, day, state, readers) VALUES('/other',?,'ok',500)", (d(n),))   # not a changed page
        c.commit()
        ins = insights.compute(c)
        m = ins['winners'] + ins['losers'] or []
        pm = [x for x in (ins.get('winners', []) + ins.get('losers', [])) if x['path'] == '/pm']
        assert ins['split'] == d(40), ins['split']                               # the release, not the biggest change
        rd = ins['groups']['groups'][0]['readers']
        assert rd['before'] == 2.0 and rd['after'] == 2.0, rd                    # the changed page's readers, not the site's 502
        print('ok')
    """) % str(TRACKER)
    env = {**os.environ, "GROWTH_PROJECT": str(demo_project), "PYTHONDONTWRITEBYTECODE": "1"}
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, timeout=120)
    assert r.returncode == 0 and "ok" in r.stdout, r.stderr[-1500:]


def test_day_windows_give_a_verdict_per_window_and_not_yet_for_an_open_one():
    sys.path.insert(0, str(TRACKER))
    import insights
    rel = dt.date(2026, 6, 1)
    rows = {(rel + dt.timedelta(days=i)).isoformat(): (1, 100 if i < 0 else 200, 400 if i < 0 else 800, 1) for i in range(-60, 30)}
    out = insights.day_windows(rows, rel, rel + dt.timedelta(days=29), rel + dt.timedelta(days=29))
    assert [w["status"] for w in out] == ["measured", "measured", "measured", "not yet"]
    assert out[0]["impressions_per_day"] == [100.0, 200.0] and out[0]["verdict"] == "better"
