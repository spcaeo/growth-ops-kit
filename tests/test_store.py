"""kit 3.0 core: the project's one local database (kit/tools/store.py)."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

import store

ROOT = Path(__file__).resolve().parent.parent

WRITER = """
import sys
sys.path.insert(0, %r)
import store
s = store.open(sys.argv[1])
for i in range(int(sys.argv[3])):
    s.event("w", sys.argv[2], {"i": i})
"""


def fresh(tmp_path):
    p = tmp_path / "proj"
    p.mkdir()
    return store.Store(p)


def test_database_lives_in_the_project_state_folder(tmp_path):
    s = fresh(tmp_path)
    assert s.path == (tmp_path / "proj" / "state" / "growth.db").resolve()
    assert s.q1("PRAGMA journal_mode")[0] == "wal"


def test_eight_parallel_writers_lose_and_repeat_nothing(tmp_path):
    p = tmp_path / "proj"
    p.mkdir()
    store.Store(p)
    script = WRITER % str(ROOT / "kit" / "tools")
    procs = [subprocess.Popen([sys.executable, "-c", script, str(p), f"w{n}", "200"], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True) for n in range(8)]
    outs = [pr.communicate(timeout=180) for pr in procs]
    assert all(pr.returncode == 0 for pr in procs), outs
    s = store.Store(p)
    rows = s.q("SELECT subject, data FROM events WHERE kind='w'")
    assert len(rows) == 1600
    seen = {(r["subject"], json.loads(r["data"])["i"]) for r in rows}
    assert len(seen) == 1600


def test_transaction_rolls_back_on_error_and_nests(tmp_path):
    s = fresh(tmp_path)
    s.ensure("t", 1, "CREATE TABLE IF NOT EXISTS t (x INTEGER)")
    with pytest.raises(RuntimeError):
        with s.tx() as db:
            db.execute("INSERT INTO t VALUES (1)")
            with s.tx() as inner:
                inner.execute("INSERT INTO t VALUES (2)")
            raise RuntimeError("stop")
    assert s.q1("SELECT COUNT(*) n FROM t")["n"] == 0
    with s.tx() as db:
        db.execute("INSERT INTO t VALUES (3)")
        with s.tx() as inner:
            inner.execute("INSERT INTO t VALUES (4)")
    assert s.q1("SELECT COUNT(*) n FROM t")["n"] == 2


def test_ensure_creates_once_and_migrates_on_a_higher_version(tmp_path):
    s = fresh(tmp_path)
    calls = []
    s.ensure("kit-a", 1, "CREATE TABLE IF NOT EXISTS a (x)")
    s.ensure("kit-a", 1, "CREATE TABLE IF NOT EXISTS a (x)", lambda db, old: calls.append(old))
    assert calls == []
    s.ensure("kit-a", 2, "CREATE TABLE IF NOT EXISTS a2 (y)", lambda db, old: calls.append(old))
    assert calls == [1]
    assert s.q1("SELECT version FROM schemas WHERE name='kit-a'")["version"] == 2


def test_events_record_who_and_when(tmp_path, monkeypatch):
    s = fresh(tmp_path)
    monkeypatch.setenv("GROWTH_AGENT", "builder-1")
    s.event("job-done", "J7", {"secs": 4})
    ev = s.events("job-done")[0]
    assert ev["actor"] == "builder-1" and ev["subject"] == "J7" and ev["data"] == {"secs": 4}
    assert ev["at"].endswith("+00:00")


def _list_mirror(s, rel="docs/list.json"):
    s.ensure("demo", 1, "CREATE TABLE IF NOT EXISTS items (v TEXT)")

    def render(st):
        return json.dumps([r["v"] for r in st.q("SELECT v FROM items ORDER BY rowid")]) + "\n"

    def load(st, text):
        st.conn.execute("DELETE FROM items")
        for v in json.loads(text):
            st.conn.execute("INSERT INTO items VALUES (?)", (v,))

    s.mirror("demo", rel, render, load)


def test_mirror_is_written_after_a_change_and_read_back_on_a_new_database(tmp_path):
    s = fresh(tmp_path)
    _list_mirror(s)
    with s.tx() as db:
        db.execute("INSERT INTO items VALUES ('a')")
        db.execute("INSERT INTO items VALUES ('b')")
    f = s.write("demo")
    assert json.loads(f.read_text()) == ["a", "b"]
    s.path.unlink()
    for extra in ("-wal", "-shm"):
        Path(str(s.path) + extra).unlink(missing_ok=True)
    s2 = store.Store(tmp_path / "proj")
    _list_mirror(s2)
    assert s2.sync("demo") is True
    assert [r["v"] for r in s2.q("SELECT v FROM items")] == ["a", "b"]


def test_an_outside_edit_of_the_mirror_wins_and_is_an_event(tmp_path):
    s = fresh(tmp_path)
    _list_mirror(s)
    with s.tx() as db:
        db.execute("INSERT INTO items VALUES ('a')")
    f = s.write("demo")
    assert s.sync("demo") is False                      # the file is what the store wrote: nothing to import
    f.write_text(json.dumps(["restored"]) + "\n")       # for example a git checkout or a copy from another machine
    assert s.sync("demo", force=True) is True
    assert [r["v"] for r in s.q("SELECT v FROM items")] == ["restored"]
    assert s.events("mirror-import", "demo")
