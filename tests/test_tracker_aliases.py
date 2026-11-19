"""Old addresses of a moved page are added together (page_aliases, redirects_file) and the split per address is kept for
the page view. No network: the search tool is replaced by a fake inside the run."""
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "kit" / "tools"))
import aliases  # noqa: E402

REDIRECTS = """
# old blog addresses
/blog/some-post/  /topic/some-post/  301
/old/a            /old/b             301
/old/b            /topic/b           308
/blog/*           /topic/:splat      301
/docs             https://other.example/docs  301
/gone             /new              410
"""


def test_aliases_come_from_the_map_and_the_redirect_list_and_follow_chains():
    got = aliases.build({"/topic/some-post/": ["/es/blog/some-post/"]}, REDIRECTS)
    assert got["/topic/some-post"] == ["/es/blog/some-post/", "/blog/some-post/"]
    assert sorted(got["/topic/b"]) == ["/old/a", "/old/b"]
    assert "/new" not in got and "/topic/:splat" not in got and len(got) == 2   # wildcards, other hosts, 410 are not aliases


def test_the_tracker_adds_old_addresses_keeps_the_split_and_records_the_definition(demo_project):
    cfg = json.loads((demo_project / "growth.json").read_text())
    cfg.update(page_aliases={"/lawn-mowing": ["/services/lawn-mowing/"]})
    cfg["connectors"]["skald"]["on"] = True
    (demo_project / "growth.json").write_text(json.dumps(cfg))
    script = textwrap.dedent("""
        import sys, datetime as dt
        sys.path.insert(0, %r)
        import config, tracker, export
        config.source_on = lambda n: True
        asked = []
        def fake(tool, **a):
            asked.append(a.get("path"))
            imp = 100 if a.get("path") == "/lawn-mowing" else 900
            days = [dict(day=(dt.date.today() - dt.timedelta(days=i)).isoformat(), clicks=1, impressions=imp, position=3.0, final=1) for i in range(1, 29)]
            return dict(structuredContent=dict(days=days, top_queries=[], countries=[dict(country="usa", clicks=2, impressions=40, position=5.0), dict(country="gbr", clicks=1, impressions=60, position=2.0)]))
        tracker.skald.call = fake
        c = tracker.db()
        c.execute("INSERT INTO pages VALUES('/lawn-mowing','','lawn-mowing','page','Lawn')")
        tracker.pull_search(c)
        assert "/services/lawn-mowing/" in asked, asked
        day = c.execute("SELECT impressions FROM search WHERE path='/lawn-mowing' ORDER BY day DESC").fetchone()[0]
        assert day == 1000, day                                    # the page and its old address, added together
        sp = export._split(c, '/lawn-mowing')
        assert sorted(r[2] for r in sp) == [2800, 25200], sp        # 28 days of 100 and of 900
        print("ok")
    """) % str(ROOT / "kit" / "page-tracker")
    env = {**os.environ, "GROWTH_PROJECT": str(demo_project), "PYTHONDONTWRITEBYTECODE": "1"}
    r = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, env=env, cwd=demo_project, timeout=120)
    assert r.returncode == 0 and "ok" in r.stdout, r.stdout + r.stderr
