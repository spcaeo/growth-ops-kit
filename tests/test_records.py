"""kit 3.0 core: the task list, the page journal and the verdicts live in the project's database (kit/tools/records.py),
and the plain files stay as byte-compatible mirrors."""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

import records
import store

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "kit" / "tools"

SAMPLE_TASKS = {
    "project": "Brightline Lawn Care",
    "site": "https://brightline.example",
    "about": "Tasks and steps: café, —, 日本",
    "updated": "2026-11-24 10:00 EST",
    "tasks": [
        {"id": "T1", "title": "Project setup", "owner_words": "Set up.", "status": "doing", "started": "2026-11-24 09:00 EST",
         "finished": None, "steps": [{"n": 1, "what": "A1 Understand", "status": "done", "at": "2026-11-24 09:05 EST",
                                      "output": "doctor OK: fine", "proof_refs": {"files": [], "commits": ["abc1234"], "journal": []}},
                                     {"n": 2, "what": "A2 “quoted”", "status": "todo", "at": "2026-11-24 09:06 EST", "output": None}]},
        {"id": "T2", "title": "Page: /x", "owner_words": "", "status": "done", "started": "2026-11-24 09:30 EST",
         "finished": "2026-11-24 09:59 EST", "steps": [], "forced": [{"at": "x", "reason": "because", "open_steps": [1, 2]}]},
    ],
    "questions": [{"id": "Q1", "question": "Which?", "task": "T1", "asked": "2026-11-24 09:10 EST", "answer": None}],
}
SAMPLE_JOURNAL = [
    {"id": "J0001", "at": "2026-11-24 06:48-05:00", "kind": "finding", "pages": ["/pricing"], "tags": ["pricing"],
     "title": "Café price", "text": "line one\nline two", "source": "", "status": "open", "recheck_on": "", "by": "lead"},
    {"of": "J0001", "at": "2026-11-24 07:00-05:00", "status": "done", "done_note": "fixed", "done_at": "2026-11-24 07:00-05:00"},
]


def project(tmp_path):
    p = tmp_path / "proj"
    shutil.copytree(ROOT / "examples" / "demo-site" / "project", p)
    return p


def entry(jid, title="t"):
    return {"id": jid, "at": "2026-11-24 06:48-05:00", "kind": "finding", "pages": ["/x"], "tags": [], "title": title, "text": "",
            "source": "", "status": "open", "recheck_on": "", "by": "lead"}


def tasks_text(doc):
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"       # what atomic.write_json wrote in 2.8.5


def journal_text(rows):
    return "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)


def roundtrip(p, name):
    """Import the mirror, then have the store write it again from the database: the bytes must not change."""
    s = records._kit(p)
    s.sync(name, force=True)
    f = s.write(name)
    return f.read_bytes()


def run_tool(p, tool, *args, stdin=None):
    env = {**os.environ, "GROWTH_PROJECT": str(p), "PYTHONDONTWRITEBYTECODE": "1"}
    env.pop("GROWTH_AGENT", None)
    return subprocess.run([sys.executable, str(TOOLS / tool), *args], capture_output=True, text=True, env=env, cwd=p,
                          input=stdin, timeout=120)


# ---- byte-identical mirrors -----------------------------------------------------------------------------------------------
def test_a_task_list_round_trips_byte_for_byte(tmp_path):
    p = project(tmp_path)
    text = tasks_text(SAMPLE_TASKS)
    (p / "docs" / "tasks.json").write_text(text, encoding="utf-8")
    assert roundtrip(p, "tasks") == text.encode("utf-8")
    assert records.tasks_doc(p) == SAMPLE_TASKS


def test_the_demo_projects_own_files_round_trip(tmp_path):
    p = project(tmp_path)
    before = (p / "docs" / "tasks.json").read_bytes()
    assert roundtrip(p, "tasks") == before
    assert roundtrip(p, "journal") == (p / "journal" / "entries.jsonl").read_bytes()


def test_a_journal_round_trips_byte_for_byte_blank_and_broken_lines_included(tmp_path):
    p = project(tmp_path)
    text = journal_text(SAMPLE_JOURNAL) + "\n" + "{not json\n" + json.dumps({"id": "J0007", "at": "x"}) + "\n"
    (p / "journal" / "entries.jsonl").write_text(text, encoding="utf-8")
    assert roundtrip(p, "journal") == text.encode("utf-8")
    assert records.journal_next_id(p) == "J0008"


def test_verdicts_are_written_in_the_format_ready_py_always_used(tmp_path):
    p = project(tmp_path)
    ledger = {"/b": {"commit": "c1", "ok": 3}, "/a": {"commit": "c2", "type": "post", "key": "a"}}
    text = json.dumps(ledger, indent=1, ensure_ascii=False) + "\n"
    (p / "journal" / "ready.json").write_text(text)
    assert roundtrip(p, "verdicts.ready") == text.encode()
    assert list(records.verdicts(p, "ready")) == ["/b", "/a"]                # the order of the file is kept
    records.verdicts_update(p, "ready", lambda d: d.update({"/c": {"commit": "c3"}}))
    records.verdicts_update(p, "ready", lambda d: d.update({"/b": {"commit": "c9"}}))
    expected = {"/b": {"commit": "c9"}, "/a": {"commit": "c2", "type": "post", "key": "a"}, "/c": {"commit": "c3"}}
    assert (p / "journal" / "ready.json").read_text() == json.dumps(expected, indent=1, ensure_ascii=False) + "\n"
    records.verdicts_update(p, "ready", lambda d: (d.pop("/a"), d.pop("/b"), d.pop("/c")) and None)
    assert (p / "journal" / "ready.json").read_text() == "{}\n"


def test_a_tasks_change_writes_exactly_what_2_8_5_wrote(tmp_path):
    p = project(tmp_path)
    (p / "docs" / "tasks.json").write_text(tasks_text(SAMPLE_TASKS), encoding="utf-8")
    records.tasks_update(p, lambda db: db["tasks"][0]["steps"].append({"n": 3, "what": "new", "status": "todo", "at": "t", "output": None}))
    expected = json.loads(tasks_text(SAMPLE_TASKS))
    expected["tasks"][0]["steps"].append({"n": 3, "what": "new", "status": "todo", "at": "t", "output": None})
    assert (p / "docs" / "tasks.json").read_text(encoding="utf-8") == tasks_text(expected)


def test_a_change_that_exits_saves_nothing(tmp_path):
    p = project(tmp_path)
    (p / "docs" / "tasks.json").write_text(tasks_text(SAMPLE_TASKS), encoding="utf-8")

    def bad(db):
        db["tasks"].clear()
        sys.exit("refused")
    with pytest.raises(SystemExit):
        records.tasks_update(p, bad)
    assert records.tasks_doc(p) == SAMPLE_TASKS
    assert (p / "docs" / "tasks.json").read_text(encoding="utf-8") == tasks_text(SAMPLE_TASKS)


# ---- the file can win ------------------------------------------------------------------------------------------------------
def test_a_task_list_edited_outside_the_store_is_imported(tmp_path):
    p = project(tmp_path)
    records.tasks_update(p, lambda db: db["tasks"].append({"id": "T1", "title": "one", "status": "doing", "steps": []}))
    assert [t["id"] for t in records.tasks_doc(p)["tasks"]] == ["T1"]
    outside = {**SAMPLE_TASKS, "updated": "restored from git"}
    (p / "docs" / "tasks.json").write_text(tasks_text(outside), encoding="utf-8")        # a git checkout, a copy from another machine
    assert records.tasks_doc(p) == outside                                              # same process, no restart needed
    records.tasks_update(p, lambda db: db["tasks"].append({"id": "T3", "title": "three", "status": "todo", "steps": []}))
    assert [t["id"] for t in json.loads((p / "docs" / "tasks.json").read_text())["tasks"]] == ["T1", "T2", "T3"]
    assert store.open(p).events("mirror-import", "tasks")


def test_journal_lines_added_outside_the_store_are_imported_and_the_next_id_follows_them(tmp_path):
    p = project(tmp_path)
    records.journal_add(p, lambda jid: {"id": jid, "at": "2026-11-24 06:48-05:00", "title": "inside"})
    with (p / "journal" / "entries.jsonl").open("a") as f:
        f.write(json.dumps({"id": "J0040", "at": "2026-11-24 06:50-05:00", "title": "outside"}) + "\n")
    assert [e["title"] for e in records.journal_entries(p)] == ["inside", "outside"]
    e = records.journal_add(p, lambda jid: {"id": jid, "at": "2026-11-24 06:51-05:00", "title": "after"})
    assert e["id"] == "J0041"
    assert [json.loads(l)["id"] for l in (p / "journal" / "entries.jsonl").read_text().splitlines()] == ["J0001", "J0040", "J0041"]


def test_a_deleted_mirror_empties_its_records_as_deleting_the_file_always_did(tmp_path):
    p = project(tmp_path)
    (p / "journal" / "entries.jsonl").write_text(journal_text(SAMPLE_JOURNAL))
    assert len(records.journal_lines(p)) == 2
    (p / "journal" / "entries.jsonl").unlink()
    with pytest.raises(FileNotFoundError):
        records.journal_lines(p)
    assert records.journal_entries(p) == []
    e = records.journal_add(p, lambda jid: {"id": jid, "at": "2026-11-24 06:48-05:00"})
    assert e["id"] == "J0001"                                     # nothing of the deleted journal comes back


def test_a_mirror_that_is_not_valid_json_raises_like_reading_the_file(tmp_path):
    p = project(tmp_path)
    (p / "docs" / "tasks.json").write_text("{not json")
    with pytest.raises(ValueError):
        records.tasks_doc(p)
    (p / "journal" / "ready.json").write_text("[1, 2]")
    with pytest.raises(ValueError):
        records.verdicts(p, "ready")


def test_reading_where_nothing_exists_makes_no_database(tmp_path):
    p = tmp_path / "bare"
    p.mkdir()
    with pytest.raises(FileNotFoundError):
        records.tasks_doc(p)
    assert records.verdicts(p, "ready") == {} and records.journal_entries(p) == []
    assert not (p / "state").exists()


DIGEST = """
import json, sys
sys.path.insert(0, %r)
import records
p = sys.argv[1]
print(json.dumps({"tasks": records.tasks_doc(p), "journal": records.journal_lines(p),
                  "ready": records.verdicts(p, "ready"), "failed": records.verdicts(p, "ready-failed"),
                  "pre": records.verdicts(p, "preflight")}, sort_keys=True))
"""


def test_a_deleted_database_is_rebuilt_from_the_mirrors_with_the_same_content(tmp_path):
    p = project(tmp_path)
    records.tasks_update(p, lambda db: db["tasks"].append({"id": "T1", "title": "one", "status": "doing", "steps": []}))
    records.tasks_update(p, lambda db: db["questions"].append({"id": "Q1", "question": "?", "answer": None}))
    for i in range(3):
        records.journal_add(p, lambda jid, i=i: {"id": jid, "at": "2026-11-24 06:48-05:00", "title": f"t{i}"})
    records.verdicts_update(p, "ready", lambda d: d.update({"/a": {"commit": "c"}}))
    records.verdicts_update(p, "ready-failed", lambda d: d.update({"/b": {"first": "FAIL"}}))
    records.verdicts_update(p, "preflight", lambda d: d.update({"/a": {"ok": True, "key": "a"}}))
    files = {f: (p / f).read_bytes() for f in ("docs/tasks.json", "journal/entries.jsonl", "journal/ready.json",
                                               "journal/ready-failed.json", "journal/preflight.json")}
    script = DIGEST % str(TOOLS)
    before = subprocess.run([sys.executable, "-c", script, str(p)], capture_output=True, text=True, timeout=60)
    assert before.returncode == 0, before.stderr
    for f in (p / "state").iterdir():
        f.unlink()
    after = subprocess.run([sys.executable, "-c", script, str(p)], capture_output=True, text=True, timeout=60)
    assert after.returncode == 0, after.stderr
    assert after.stdout == before.stdout
    assert (p / "state" / "growth.db").exists()
    assert {f: (p / f).read_bytes() for f in files} == files                 # the files themselves were not touched


# ---- parallel writers --------------------------------------------------------------------------------------------------
def test_eight_parallel_growth_tasks_commands_keep_every_change(tmp_path):
    p = project(tmp_path)
    env = {**os.environ, "GROWTH_PROJECT": str(p), "PYTHONDONTWRITEBYTECODE": "1"}
    procs = [subprocess.Popen([sys.executable, str(TOOLS / "tasks.py"), "add", f"Parallel job {i}", f"words {i}"], env=env, cwd=p,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for i in range(8)]
    outs = [pr.communicate(timeout=120) for pr in procs]
    assert all(pr.returncode == 0 for pr in procs), outs
    ids = sorted(o[0].strip() for o in outs)
    assert len(set(ids)) == 8, ids                                        # no two jobs got the same id
    db = json.loads((p / "docs" / "tasks.json").read_text())
    assert sorted(t["title"] for t in db["tasks"]) == sorted(f"Parallel job {i}" for i in range(8))
    first = db["tasks"][0]["id"]
    procs = [subprocess.Popen([sys.executable, str(TOOLS / "tasks.py"), "step", first, f"Extra step {i}"], env=env, cwd=p,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for i in range(8)]
    outs = [pr.communicate(timeout=120) for pr in procs]
    assert all(pr.returncode == 0 for pr in procs), outs
    steps = json.loads((p / "docs" / "tasks.json").read_text())["tasks"][0]["steps"]
    assert sorted(s["what"] for s in steps) == sorted(f"Extra step {i}" for i in range(8))
    assert [s["n"] for s in steps] == list(range(1, 9))                   # numbered one by one, never twice


def test_parallel_journal_adds_append_to_the_file_and_never_rewrite_it(tmp_path):
    p = project(tmp_path)
    for i in range(5):
        records.journal_add(p, lambda jid, i=i: entry(jid, f"old{i}"))
    f = p / "journal" / "entries.jsonl"
    inode, head = f.stat().st_ino, f.read_text()
    env = {**os.environ, "GROWTH_PROJECT": str(p), "PYTHONDONTWRITEBYTECODE": "1"}
    procs = [subprocess.Popen([sys.executable, str(TOOLS / "journal.py"), "add", "--page", f"/p{i}", "--title", f"new{i}"], env=env,
                              cwd=p, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for i in range(8)]
    outs = [pr.communicate(timeout=120) for pr in procs]
    assert all(pr.returncode == 0 for pr in procs), outs
    assert f.stat().st_ino == inode and f.read_text().startswith(head)       # appended in place, not replaced
    ids = [json.loads(l)["id"] for l in f.read_text().splitlines()]
    assert ids == [f"J{n:04d}" for n in range(1, 14)]                       # unique, in order, no gaps
    s = store.Store(p)
    assert records._render_journal(s) == f.read_text()                       # the database and the file agree line by line
    assert s.q1("SELECT sha FROM mirrors WHERE name='journal'")["sha"] == store.sha(f.read_text())


# ---- speed ------------------------------------------------------------------------------------------------------------------
def test_the_status_line_and_the_stage_hook_stay_fast(tmp_path):
    p = project(tmp_path)
    run_tool(p, "tasks.py", "add", "Page job: /pricing", "words")
    run_tool(p, "tasks.py", "step", "T1", "Step 1. Research")
    run_tool(p, "statusline.py")                                            # the first run opens the database and imports the files
    hook = json.dumps({"tool_input": {"command": "growth tasks tick T1 1 --output x   # build stage"}})
    run_tool(p, "workflow.py", "stage", stdin=hook)
    t0 = time.time()
    r = run_tool(p, "statusline.py")
    t_status = time.time() - t0
    assert r.returncode == 0 and "T1" in r.stdout, r.stdout + r.stderr
    t0 = time.time()
    r = run_tool(p, "workflow.py", "stage", stdin=hook)
    t_hook = time.time() - t0
    assert r.returncode == 0, r.stderr
    assert t_status < 0.5, f"the status line took {t_status:.2f} s"
    assert t_hook < 0.5, f"the stage hook took {t_hook:.2f} s"


def test_no_lock_file_is_left_by_reads(tmp_path):
    p = project(tmp_path)
    records.tasks_doc(p)                                  # the first read imports the files (and takes their locks)
    records.journal_lines(p)
    for lock in list((p / "docs").glob("*.lock")) + list((p / "journal").glob("*.lock")):
        lock.unlink()
    before = {x.name for x in (p / "docs").iterdir()} | {x.name for x in (p / "journal").iterdir()}
    records.tasks_doc(p)
    records.journal_lines(p)
    records.verdicts(p, "ready")
    after = {x.name for x in (p / "docs").iterdir()} | {x.name for x in (p / "journal").iterdir()}
    assert not [n for n in after - before if n.endswith(".lock")]
