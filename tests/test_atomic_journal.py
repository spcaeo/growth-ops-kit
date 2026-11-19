"""Audit M1 and M5: parallel writers never lose or repeat a line (atomic.py + the journal lock), and a journal time must be
a real time with a zone: a bad or zone-less one is ignored and reported, never counted as fresh."""
import datetime as dt
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

import atomic

ROOT = Path(__file__).resolve().parent.parent


def jrun(proj, *args, tz=None):
    if tz:
        cfg = json.loads((proj / "growth.json").read_text())
        cfg["timezone"] = tz
        (proj / "growth.json").write_text(json.dumps(cfg))
    env = {**os.environ, "GROWTH_PROJECT": str(proj), "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run([sys.executable, str(ROOT / "kit" / "tools" / "journal.py"), *args], capture_output=True, text=True,
                          env=env, cwd=proj, timeout=120)


def test_twenty_parallel_journal_adds_keep_every_line_with_unique_ids(demo_project):
    procs = [subprocess.Popen([sys.executable, str(ROOT / "kit" / "tools" / "journal.py"), "add", "--page", f"/p{i}", "--title", f"t{i}"],
                              env={**os.environ, "GROWTH_PROJECT": str(demo_project), "PYTHONDONTWRITEBYTECODE": "1"},
                              cwd=demo_project, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for i in range(40)]
    outs = [p.communicate(timeout=120) for p in procs]
    assert all(p.returncode == 0 for p in procs), outs
    ids = [json.loads(l)["id"] for l in (demo_project / "journal" / "entries.jsonl").read_text().splitlines() if l.strip()]
    assert len(ids) == len(set(ids)) and len(ids) >= 40, ids


def test_update_json_keeps_every_parallel_change(tmp_path):
    f = tmp_path / "db.json"
    atomic.write_json(f, {"steps": []})

    def add(i):
        atomic.update_json(f, lambda d: d["steps"].append(i))
    ts = [threading.Thread(target=add, args=(i,)) for i in range(40)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert sorted(json.loads(f.read_text())["steps"]) == list(range(40))
    assert not [p for p in tmp_path.iterdir() if p.suffix == ".tmp"]


def test_write_text_leaves_no_temp_file_and_survives_a_failed_write(tmp_path):
    f = tmp_path / "a.txt"
    atomic.write_text(f, "one")
    with pytest.raises(TypeError):
        atomic.write_text(f, None)
    assert f.read_text() == "one" and [p.name for p in tmp_path.iterdir() if p.name.startswith("a.txt.")] == []


def test_lock_times_out_with_a_plain_message(tmp_path):
    f = tmp_path / "x.json"
    with atomic.locked(f):
        # a second holder (another file descriptor) cannot get in
        with pytest.raises(atomic.LockTimeout):
            with atomic.locked(f, timeout=0.2):
                pass


def test_journal_times_carry_their_zone_and_keep_their_meaning_when_the_timezone_changes(demo_project, monkeypatch):
    monkeypatch.setenv("GROWTH_PROJECT", str(demo_project))
    jrun(demo_project, "add", "--page", "/x", "--title", "a", tz="UTC")
    jrun(demo_project, "add", "--page", "/x", "--title", "b", tz="America/Toronto")
    rows = [json.loads(l) for l in (demo_project / "journal" / "entries.jsonl").read_text().splitlines() if l.strip()]
    ats = [r["at"] for r in rows if r["title"] in ("a", "b")]
    assert ats[0].endswith("+00:00") and ats[1][-6:] in ("-05:00", "-04:00")
    import journal
    assert all(journal.parse_at(a) is not None for a in ats)
    first = journal.parse_at(ats[0])
    assert first.utcoffset() == dt.timedelta(0)           # still UTC after the project moved to Toronto time


@pytest.mark.parametrize("bad", ["x", "", "2026-11-19 06:48", "2026-11-19T06:48", "2026-13-45 06:48-05:00", "2026-11-19 06:48 XYZ", None, 5])
def test_unreadable_or_zone_less_times_are_rejected(demo_project, monkeypatch, bad):
    monkeypatch.setenv("GROWTH_PROJECT", str(demo_project))
    import journal
    assert journal.parse_at(bad) is None


def test_a_bad_time_entry_is_ignored_and_reported(demo_project):
    jrun(demo_project, "add", "--page", "/x", "--title", "good")
    with (demo_project / "journal" / "entries.jsonl").open("a") as f:
        f.write(json.dumps({"id": "J0500", "at": "not a time", "pages": ["/x"], "kind": "finding", "status": "open", "title": "edited"}) + "\n")
    r = jrun(demo_project, "open")
    assert "good" in r.stdout and "edited" not in r.stdout
    assert "J0500" in r.stderr and "unreadable time" in r.stderr


def test_parse_at_accepts_iso_with_offset_and_the_older_form_in_the_project_zone(demo_project, monkeypatch):
    monkeypatch.setenv("GROWTH_PROJECT", str(demo_project))
    import journal
    assert journal.parse_at("2026-11-19 06:48-05:00").utcoffset() == dt.timedelta(hours=-5)
    assert journal.parse_at("2026-11-19T11:48:00Z").utcoffset() == dt.timedelta(0)
    assert journal.parse_at("2026-11-19 06:48 UTC").utcoffset() == dt.timedelta(0)
