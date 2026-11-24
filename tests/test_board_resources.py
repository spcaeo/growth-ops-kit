"""kit 3.0 work board: the port pool, the browser pool and the locks (kit/tools/boardlib/resources.py, lock.py)."""
import json
import socket
import subprocess
import sys

import board
import store
from boardlib import resources
from board_helpers import TOOLS, growth, make_project


def fresh(tmp_path, **cfg):
    project = make_project(tmp_path, **cfg)
    return project, store.Store(project)


def proof(j):
    return "https://example.com/p/%d" % j["id"]


def test_the_port_pool_hands_out_distinct_ports_and_frees_them(tmp_path):
    _, st = fresh(tmp_path)                                               # the safe test range: 28440 to 28459, 20 ports
    for _ in range(21):
        board.add_job("build", st=st)
    held = [board.claim(f"lane-{n}", st=st) for n in range(20)]
    ports = [j["port"] for j in held]
    assert sorted(ports) == list(range(28440, 28460)) and len(set(ports)) == 20
    assert board.claim("lane-x", st=st) is None                           # the pool is empty: the 21st build waits
    board.add_job("cleanup", st=st)
    assert board.claim("lane-x", st=st)["kind"] == "cleanup"              # a job with no port still goes
    board.done(held[3]["id"], "lane-3", proof(held[3]), st=st)
    again = board.claim("lane-y", st=st)
    assert again["kind"] == "build" and again["port"] == ports[3]         # the freed port comes back
    board.fail(held[5]["id"], "lane-5", "broke", st=st)
    assert board.claim("lane-z", st=st)["port"] == ports[5]


def test_a_port_another_program_listens_on_is_skipped(tmp_path):
    _, st = fresh(tmp_path, resources={"port_range": [28440, 28442]})
    s = socket.socket()
    s.bind(("127.0.0.1", 28440))
    s.listen(1)
    try:
        for _ in range(3):
            board.add_job("build", st=st)
        ports = sorted(j["port"] for j in (board.claim(f"l{n}", st=st) for n in range(3)) if j)
        assert ports == [28441, 28442]                                     # 28440 is taken by someone else
    finally:
        s.close()


def test_the_browser_pool_has_three_places_by_default_and_follows_growth_json(tmp_path):
    _, st = fresh(tmp_path)
    for _ in range(4):
        board.add_job("shots", st=st)
    got = [board.claim(f"m{n}", st=st) for n in range(4)]
    assert [j is not None for j in got] == [True, True, True, False]
    board.done(got[0]["id"], "m0", proof(got[0]), st=st)
    assert board.claim("m9", st=st) is not None
    _, st2 = fresh(tmp_path / "two", resources={"browser": 1})
    board.add_job("shots", st=st2), board.add_job("click-test", st=st2)
    assert board.claim("a", st=st2) and board.claim("b", st=st2) is None


def test_the_shared_code_lock_has_one_holder(tmp_path):
    project, st = fresh(tmp_path)
    script = ("import sys; sys.path.insert(0, %r); import store; from boardlib import resources; st = store.open(sys.argv[1]); "
              "ok, who = resources.lock_take(st, 'shared-code', sys.argv[2]); print('TAKEN' if ok else 'HELD')") % str(TOOLS)
    procs = [subprocess.Popen([sys.executable, "-c", script, str(project), f"agent-{n}"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
             for n in range(6)]
    outs = [p.communicate(timeout=60)[0].strip() for p in procs]
    assert sorted(outs) == ["HELD"] * 5 + ["TAKEN"]
    row = st.q1("SELECT holder FROM leases WHERE resource='shared-code'")
    ok, who = resources.lock_take(st, "shared-code", "late")
    assert not ok and who["holder"] == row["holder"]
    assert resources.lock_take(st, "shared-code", row["holder"])[0]       # the holder takes it again: its lease is renewed
    assert "held by" in resources.lock_free(st, "shared-code", "late")    # nobody else may give it back
    assert resources.lock_free(st, "shared-code", row["holder"]) == "freed"
    assert resources.lock_take(st, "shared-code", "late")[0]
    assert resources.lock_free(st, "shared-code", "late") == "freed" and resources.lock_free(st, "shared-code", "late") == "free"


def test_a_lock_held_by_an_expired_lease_is_freed(tmp_path):
    _, st = fresh(tmp_path)
    assert resources.lock_take(st, "shared-code", "gone", lease_s=1)[0]
    st.conn.execute("UPDATE leases SET until='2000-01-01T00:00:00+00:00'")
    ok, _ = resources.lock_take(st, "shared-code", "next")
    assert ok and st.events("lock-expired", "shared-code")


def test_lock_and_unlock_commands(tmp_path):
    project, _ = fresh(tmp_path)
    assert growth(project, "lock", "shared-code", "--agent", "X").returncode == 0
    r = growth(project, "lock", "shared-code", "--agent", "Y")
    assert r.returncode == 3 and "held by X" in r.stderr
    assert growth(project, "lock", "shared-code", "--agent", "Y", "--wait", "1").returncode == 3
    assert growth(project, "lock", "--list").stdout.count("held by X") == 1
    assert growth(project, "unlock", "shared-code", "--agent", "Y").returncode == 1
    assert growth(project, "unlock", "shared-code", "--agent", "X").returncode == 0
    assert growth(project, "lock", "shared-code", "--agent", "Y").returncode == 0
    assert growth(project, "unlock", "shared-code", "--agent", "Z", "--force").returncode == 0
    assert growth(project, "lock", "browser", "--agent", "Y").returncode == 2        # a pool, not a lock


def test_a_ready_job_holds_the_owner_preview_lock_for_its_lease(tmp_path):
    _, st = fresh(tmp_path)
    j1, j2 = board.add_job("ready", st=st), board.add_job("ready", st=st)
    first = board.claim("m1", st=st)
    assert first["id"] == j1 and board.claim("m2", st=st) is None          # one holder at a time
    ok, who = resources.lock_take(st, "owner-preview", "lead")
    assert not ok and who["job"] == j1
    assert "held by job" in resources.lock_free(st, "owner-preview", "lead")
    board.done(j1, "m1", proof(first), st=st)
    assert board.claim("m2", st=st)["id"] == j2


def test_a_shared_code_job_waits_while_the_lock_is_taken_by_hand(tmp_path):
    _, st = fresh(tmp_path)
    board.add_job("shared-change", st=st)
    assert resources.lock_take(st, "shared-code", "lead")[0]
    assert board.claim("b1", st=st) is None
    resources.lock_free(st, "shared-code", "lead")
    assert board.claim("b1", st=st)["kind"] == "shared-change"


def test_board_resources_lists_who_holds_what(tmp_path):
    project, st = fresh(tmp_path)
    board.add_job("build", st=st)
    board.claim("lane-1", st=st)
    out = growth(project, "board", "resources", check=True).stdout
    assert "port" in out and "lane-1" in out and "google" in out and "slot 28440" in out
