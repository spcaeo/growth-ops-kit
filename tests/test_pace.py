"""kit 3.0 pacer (kit/tools/pace.py): at most one Google turn every 20 to 30 s for all agents; a robot check pauses everyone."""
import json
import subprocess
import sys
import time

import pace
import store
from board_helpers import TOOLS, growth, make_project

CALLER = r"""
import json, sys
sys.path.insert(0, %r)
import pace, store
st = store.open(sys.argv[1])
print(json.dumps([pace.turn("google", sys.argv[2], st=st)["at"] for _ in range(int(sys.argv[3]))]))
""" % str(TOOLS)


def test_settings_default_to_the_owner_rule_and_growth_json_changes_them(tmp_path):
    project = make_project(tmp_path)
    assert pace.settings(store.Store(project), "google") == {"min_s": 20, "max_s": 30, "robot_pause_s": 600}
    project2 = make_project(tmp_path / "two", pacers={"google": {"min_s": 1, "max_s": 2, "robot_pause_s": 5}})
    assert pace.settings(store.Store(project2), "google") == {"min_s": 1, "max_s": 2, "robot_pause_s": 5}


def test_four_parallel_callers_never_get_turns_closer_than_the_minimum(tmp_path):
    project = make_project(tmp_path, pacers={"google": {"min_s": 1, "max_s": 2, "robot_pause_s": 600}})
    store.Store(project)
    procs = [subprocess.Popen([sys.executable, "-c", CALLER, str(project), f"r{n}", "2"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
             for n in range(4)]
    outs = [p.communicate(timeout=120) for p in procs]
    assert all(p.returncode == 0 for p in procs), outs
    turns = sorted(t for o, _ in outs for t in json.loads(o))
    assert len(turns) == 8
    gaps = [b - a for a, b in zip(turns, turns[1:])]
    assert min(gaps) >= 1.0, gaps                                         # never closer than min_s
    assert max(gaps) <= 2.0 + 1.0, gaps                                   # and nobody waits for nothing (max_s plus a poll)
    ev = [e["data"]["t"] for e in store.Store(project).events("pace-turn", limit=50)]
    assert sorted(ev) == turns                                            # every turn is an event with its time


def test_robot_pauses_every_turn(tmp_path):
    project = make_project(tmp_path, pacers={"google": {"min_s": 0.1, "max_s": 0.2, "robot_pause_s": 2}})
    st = store.Store(project)
    assert pace.turn("google", "a", st=st)["waited_s"] < 0.5
    until = pace.robot("google", "a", st=st)
    assert 1.5 < until - time.time() <= 2.1 and pace.status("google", st=st)["paused"]
    assert pace.turn("google", "b", max_wait=0.5, st=st) is None          # a turn more than max_wait away is not taken
    got = pace.turn("google", "b", st=st)
    assert got["waited_s"] >= 1.4 and got["at"] >= until - 0.01
    assert not pace.status("google", st=st)["paused"]
    assert st.events("pace-robot", "google")


def test_the_pace_command(tmp_path):
    project = make_project(tmp_path, pacers={"google": {"min_s": 0.2, "max_s": 0.3, "robot_pause_s": 600}})
    r = growth(project, "pace", "google", agent="r1")
    assert r.returncode == 0 and "your turn" in r.stdout
    r = growth(project, "pace", "google", "--max-wait", "0")
    assert r.returncode == 3 and "away" in r.stdout
    assert "next turn in" in growth(project, "pace", "google", "--status").stdout
    r = growth(project, "pace", "google", "--robot")
    assert r.returncode == 0 and "paused for 10 minutes" in r.stdout
    assert growth(project, "pace", "google", "--max-wait", "1").returncode == 3
    assert "paused" in growth(project, "pace", "google", "--status").stdout
    assert growth(project, "pace", "bing").returncode == 2
