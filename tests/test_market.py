"""The target market is MEASURED from Google's country rows next to the estimate, the estimate states its assumption, and one
definition is recorded with each snapshot. No network: the search tool is replaced by a fake inside the run."""
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "kit" / "tools"))
import market  # noqa: E402


def test_the_target_market_is_measured_and_the_estimate_states_its_assumption():
    rows = [("usa", 11, 27487, 5.2), ("gbr", 5, 20000, 2.0), ("ind", 3, 30000, 1.5)]
    m = market.measure(rows, (88, 295810, 3.2), ["USA"])
    assert m["measured"] == dict(clicks=11, impressions=27487, position=5.2)
    assert m["all"]["position"] == 3.2 and m["all"]["impressions"] == 295810
    assert m["estimate"]["impressions"] == round(295810 * 27487 / 77487)
    assert "upper bound" in m["estimate"]["assumption"] and m["definition"] == market.definition(["usa"])
    assert market.measure(rows, (1, 1, 1), []) is None


def test_the_tracker_exports_the_measured_market_and_records_the_definition(demo_project):
    cfg = json.loads((demo_project / "growth.json").read_text())
    cfg.update(target_markets=["usa"])
    (demo_project / "growth.json").write_text(json.dumps(cfg))
    script = textwrap.dedent("""
        import sys, datetime as dt
        sys.path.insert(0, %r)
        import config, tracker, export
        config.source_on = lambda n: True
        def fake(tool, **a):
            days = [dict(day=(dt.date.today() - dt.timedelta(days=i)).isoformat(), clicks=1, impressions=100, position=3.0, final=1) for i in range(1, 29)]
            return dict(structuredContent=dict(days=days, top_queries=[], countries=[dict(country="usa", clicks=2, impressions=40, position=5.0), dict(country="gbr", clicks=1, impressions=60, position=2.0)]))
        tracker.skald.call = fake
        c = tracker.db()
        c.execute("INSERT INTO pages VALUES('/lawn-mowing','','lawn-mowing','page','Lawn')")
        tracker.pull_search(c)
        m = export._market(c, '/lawn-mowing', export._top(c, 'search_countries', 'country', '/lawn-mowing')[1])
        assert m["measured"] == dict(clicks=2, impressions=40, position=5.0), m
        assert m["all"]["impressions"] == 2800 and m["definition_changed"] is False, m
        assert c.execute("SELECT definition FROM market_definition").fetchone()[0].startswith("target market usa")
        c.execute("INSERT INTO market_definition VALUES('2000-01-01', 'target market gbr')")
        assert export._market(c, '/lawn-mowing', export._top(c, 'search_countries', 'country', '/lawn-mowing')[1])["definition_changed"]
        print("ok")
    """) % str(ROOT / "kit" / "page-tracker")
    env = {**os.environ, "GROWTH_PROJECT": str(demo_project), "PYTHONDONTWRITEBYTECODE": "1"}
    cfg2 = json.loads((demo_project / "growth.json").read_text())
    cfg2["connectors"]["skald"]["on"] = True
    (demo_project / "growth.json").write_text(json.dumps(cfg2))
    r = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, env=env, cwd=demo_project, timeout=120)
    assert r.returncode == 0 and "ok" in r.stdout, r.stdout + r.stderr


NOISE = {"brand": ["acme boards"], "spam": ["free download"], "off_topic": ["jobs"]}
QUERIES = [("board tools", 5, 600), ("acme boards login", 9, 200), ("free download board", 0, 100), ("board jobs near me", 0, 50),
           ("https://spam.example.com", 0, 50), ("[us] board software", 1, 100)]


def test_queries_are_sorted_into_brand_spam_off_topic_and_buyer_searches():
    assert [market.classify(q, NOISE) for q, _c, _i in QUERIES] == ["buyer", "brand", "spam", "off_topic", "spam", "buyer"]
    assert market.classify("board tools", {"on_topic": ["software"]}) == "off_topic"        # nothing on topic in it
    assert market.classify("acme boards jobs", NOISE) == "brand"                            # first matching class wins
    assert market.classify("boards", {"brand": ["board"]}) == "buyer"                       # whole words only


def test_the_noise_share_is_measured_on_the_listed_searches_and_states_its_assumption():
    n = market.noise([(q, c, i) for q, c, i in QUERIES], NOISE)
    assert n["listed_impressions"] == 1100 and n["classes"]["brand"]["impressions"] == 200 and n["classes"]["spam"]["impressions"] == 150
    assert n["noise_share_impressions"] == round(400 / 1100, 4) and n["classes"]["brand"]["top"] == "acme boards login"
    assert "long tail" in n["assumption"]
    assert market.noise(QUERIES, {}) is None                                                # nothing configured, nothing claimed


def test_the_clean_figures_sit_next_to_the_measured_and_the_estimate_and_are_marked():
    rows = [("usa", 11, 27487, 5.2), ("gbr", 5, 20000, 2.0)]
    m = market.measure(rows, (88, 295810, 3.2), ["usa"], QUERIES, NOISE)
    keep = 1 - round(400 / 1100, 4)
    assert m["measured"]["impressions"] == 27487 and m["clean"]["measured_impressions"] == round(27487 * keep)
    assert m["clean"]["estimate_impressions"] == round(m["estimate"]["impressions"] * keep) and "assumed" in m["clean"]["assumption"] or "assumes" in m["clean"]["assumption"]
    assert "noise" in m["definition"] and market.definition(["usa"]) != market.definition(["usa"], NOISE)   # a new noise list is a new definition
    assert "clean" not in market.measure(rows, (88, 295810, 3.2), ["usa"])                  # no noise config: unchanged
