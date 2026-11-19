"""Doctor shows BUSY, not TODO/FAIL, for the normal moments of work: a log line just written (the owner journal page
is rebuilt when the agent stops) and a tracker sync writing (the database is locked). BUSY counts as done."""
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCTOR = ROOT / "kit" / "tools" / "doctor.py"


def doctor(project):
    env = {**os.environ, "GROWTH_PROJECT": str(project), "GROWTH_CRONTAB": "", "GROWTH_LAUNCHD_DIRS": str(project / "none")}
    r = subprocess.run([sys.executable, str(DOCTOR)], capture_output=True, text=True, cwd=project, env=env)
    return r


def line(r, step):
    return next(l for l in r.stdout.splitlines() if step in l)


def journal(project, journal_age, log_age):
    now = time.time()
    (project / "journal").mkdir(exist_ok=True)
    page, log = project / "journal" / "owner-journal.html", project / "docs" / "steps-log.md"
    page.write_text("<html></html>")
    log.parent.mkdir(exist_ok=True)
    log.write_text("I-1 x\n")
    os.utime(page, (now - journal_age, now - journal_age))
    os.utime(log, (now - log_age, now - log_age))
    entries = project / "journal" / "entries.jsonl"
    entries.write_text("")
    os.utime(entries, (now - log_age - 5, now - log_age - 5))


def test_a9_is_busy_right_after_a_log_line_and_todo_when_long_stale(demo_project):
    journal(demo_project, journal_age=120, log_age=10)
    r = doctor(demo_project)
    assert line(r, "A9").startswith("BUSY") and "FAIL" not in line(r, "A9")
    assert "BUSY" in r.stdout.splitlines()[-1] or "BUSY" in r.stdout
    journal(demo_project, journal_age=7200, log_age=3600)
    assert line(doctor(demo_project), "A9").startswith("FAIL")
    journal(demo_project, journal_age=10, log_age=120)
    assert line(doctor(demo_project), "A9").startswith("OK")


def test_busy_counts_as_done_in_the_total(demo_project):
    journal(demo_project, journal_age=120, log_age=10)
    r = doctor(demo_project)
    n_ok = sum(1 for l in r.stdout.splitlines() if l.startswith(("OK ", "BUSY")))
    assert f"{n_ok}/" in r.stdout and "1 BUSY" in r.stdout


def test_a8_is_busy_while_the_database_is_locked(demo_project):
    db = demo_project / "page-tracker" / "tracker.db"
    db.parent.mkdir(exist_ok=True)
    c = sqlite3.connect(db, isolation_level=None)
    c.execute("create table search (day text, path text)")
    c.execute("create table pages (file text)")
    c.execute("create table changes (x)")
    c.execute("begin exclusive")           # a sync writing right now
    try:
        a8 = line(doctor(demo_project), "A8")
    finally:
        c.execute("rollback")
        c.close()
    assert a8.startswith("BUSY") and "database is busy" in a8
