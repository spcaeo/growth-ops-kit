"""kit 3.0 core: the one access layer for the task list, the page journal and the verdicts.

These three records live in the project's database (`<project>/state/growth.db`, see store.py). The plain files stay as
byte-compatible mirrors (docs/tasks.json, journal/entries.jsonl, journal/ready.json, journal/ready-failed.json,
journal/preflight.json): the store rewrites them after every change, so hooks, permissions, git diffs and older readers
keep working. Every kit module reads and writes these records ONLY through the functions below; a test fails when a
module opens one of the mirrored files itself (tests/test_records_guard.py).

    tasks_doc(project)                     the task list as a dict (FileNotFoundError / ValueError like reading the file)
    tasks_update(project, change, default) load + change(doc) + save in ONE transaction (nothing is ever lost)
    tasks_save(project, doc)               replace the whole list
    journal_lines(project)                 every line of the journal, in order (FileNotFoundError when there is none)
    journal_entries(project)               the readable entries (blank and broken lines left out)
    journal_add(project, make)             next id + line, decided inside the write transaction: make(jid) -> entry
    journal_append(project, entry)         one more line (an entry that already has its id, or an update line)
    verdicts(project, kind)                {page: verdict} of "ready", "ready-failed" or "preflight" ({} when none)
    verdicts_update(project, kind, change) load + change(dict) + save in ONE transaction

`project` is a folder, or None for the current project. A mirror edited outside the store (restored from git, copied
from another machine, written by a test) is imported at the next read or write; a mirror that was deleted empties its
records, exactly as deleting the file did before. Reads never create a database when there is nothing to read.

Lock order: the mirror file's lock first, then the database's write lock (store.sync and store.write do the same), so two
processes never wait for each other.
"""
from __future__ import annotations

import copy
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import atomic  # noqa: E402
import store  # noqa: E402

VERDICT_FILES = {"ready": "ready.json", "ready-failed": "ready-failed.json", "preflight": "preflight.json"}
_SETTLE = 2.0          # a file changed less than this many seconds ago is always compared by content, never by its stamp

TASKS_DDL = """
CREATE TABLE IF NOT EXISTS task_doc (pos INTEGER PRIMARY KEY, key TEXT NOT NULL UNIQUE, body TEXT);
CREATE TABLE IF NOT EXISTS tasks (pos INTEGER PRIMARY KEY, id TEXT, status TEXT, body TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS tasks_id ON tasks(id)
"""
JOURNAL_DDL = """
CREATE TABLE IF NOT EXISTS journal (seq INTEGER PRIMARY KEY, jid INTEGER, line TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS journal_jid ON journal(jid)
"""
VERDICTS_DDL = """
CREATE TABLE IF NOT EXISTS verdicts (seq INTEGER PRIMARY KEY, kind TEXT NOT NULL, path TEXT NOT NULL, body TEXT NOT NULL,
                                     UNIQUE(kind, path))
"""


# ---- where things are -------------------------------------------------------------------------------------------------
def project_of(project=None) -> Path:
    if project is None:
        import config
        return config.require_project()
    return Path(project)


def docs_dir(project=None) -> Path:
    """The project's docs folder: growth.json "project_docs", else docs/."""
    p = project_of(project)
    try:
        cfg = json.loads((p / "growth.json").read_text())
    except (OSError, ValueError):
        cfg = {}
    return p / ((cfg.get("project_docs") if isinstance(cfg, dict) else None) or "docs")


def tasks_path(project=None, docs=None) -> Path:
    """The task list's mirror file (for existence and message checks; read it with tasks_doc)."""
    return (Path(docs) if docs else docs_dir(project)) / "tasks.json"


def tasks_rel(project=None) -> str:
    """The task list's mirror, as a path relative to the project (for `git log -- <path>`)."""
    p = project_of(project)
    f = tasks_path(p)
    try:
        return f.resolve().relative_to(p.resolve()).as_posix()
    except ValueError:
        return str(f)


def journal_path(project=None) -> Path:
    return project_of(project) / "journal" / "entries.jsonl"


def verdict_path(project, kind: str) -> Path:
    return project_of(project) / "journal" / VERDICT_FILES[kind]


def _db_path(p: Path) -> Path:
    return p / "state" / store.DB_NAME


def _rel(p: Path, f: Path) -> str:
    try:
        return f.resolve().relative_to(p.resolve()).as_posix()
    except ValueError:
        return str(f)


# ---- the mirrors: how each record becomes its file, and the file becomes the record ------------------------------------
def _tasks_rows(conn):
    return conn.execute("SELECT 0 AS k, pos, key AS name, body FROM task_doc UNION ALL "
                        "SELECT 1, pos, '', body FROM tasks ORDER BY k, pos").fetchall()


def _read_tasks(conn) -> dict | None:
    """The task list from its rows (one statement: always one consistent snapshot), None when there is none."""
    rows = _tasks_rows(conn)
    if not any(r["k"] == 0 for r in rows):
        return None
    tasks = [json.loads(r["body"]) for r in rows if r["k"] == 1]
    doc = {}
    for r in rows:
        if r["k"] == 0:
            doc[r["name"]] = tasks if (r["name"] == "tasks" and r["body"] is None) else json.loads(r["body"])
    return doc


def _write_tasks(conn, doc: dict) -> None:
    """Replace the task list's rows. Only the tasks that changed are written, the rest stay as they are."""
    conn.execute("DELETE FROM task_doc")
    items = doc.get("tasks") if isinstance(doc.get("tasks"), list) else []
    conn.executemany("INSERT INTO task_doc(pos, key, body) VALUES (?, ?, ?)",
                     [(i, k, None if (k == "tasks" and isinstance(v, list)) else json.dumps(v, ensure_ascii=False))
                      for i, (k, v) in enumerate(doc.items())])
    old = {r["pos"]: r["body"] for r in conn.execute("SELECT pos, body FROM tasks")}
    for i, t in enumerate(items):
        body = json.dumps(t, ensure_ascii=False)
        tid = str(t["id"]) if isinstance(t, dict) and "id" in t else None
        status = t.get("status") if isinstance(t, dict) and isinstance(t.get("status"), str) else None
        if i not in old:
            conn.execute("INSERT INTO tasks(pos, id, status, body) VALUES (?, ?, ?, ?)", (i, tid, status, body))
        elif old[i] != body:
            conn.execute("UPDATE tasks SET id=?, status=?, body=? WHERE pos=?", (tid, status, body, i))
    if len(old) > len(items):
        conn.execute("DELETE FROM tasks WHERE pos >= ?", (len(items),))


def _render_tasks(s) -> str:
    """Exactly what `atomic.write_json(tasks.json, doc)` wrote in 2.8.5: indent 2, no ASCII escapes, a final newline."""
    doc = _read_tasks(s.conn)
    return json.dumps(doc if doc is not None else {}, indent=2, ensure_ascii=False) + "\n"


def _load_tasks(s, text: str) -> None:
    doc = json.loads(text)
    if not isinstance(doc, dict):
        raise ValueError("the task list must be a JSON object")
    _write_tasks(s.conn, doc)


def _jid_of(obj) -> int | None:
    m = re.fullmatch(r"J(\d+)", str(obj.get("id", ""))) if isinstance(obj, dict) else None
    return int(m.group(1)) if m else None


def _jid_of_line(line: str) -> int | None:
    try:
        return _jid_of(json.loads(line))
    except ValueError:
        return None


def _render_journal(s) -> str:
    return "".join(r["line"] + "\n" for r in s.conn.execute("SELECT line FROM journal ORDER BY seq"))


def _load_journal(s, text: str) -> None:
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()                      # the last newline ends the last line; a blank line in the middle stays a line
    s.conn.execute("DELETE FROM journal")
    s.conn.executemany("INSERT INTO journal(jid, line) VALUES (?, ?)", [(_jid_of_line(ln), ln) for ln in lines])


def _verdicts_in(conn, kind: str) -> dict:
    return {r["path"]: json.loads(r["body"])
            for r in conn.execute("SELECT path, body FROM verdicts WHERE kind=? ORDER BY seq", (kind,))}


def _write_verdicts(conn, kind: str, d: dict) -> None:
    """Make the rows equal `d`: a page that stays keeps its place, a new page goes to the end (dict order)."""
    old = {r["path"]: r["body"] for r in conn.execute("SELECT path, body FROM verdicts WHERE kind=?", (kind,))}
    for path in [x for x in old if x not in d]:
        conn.execute("DELETE FROM verdicts WHERE kind=? AND path=?", (kind, path))
    for path, v in d.items():
        body = json.dumps(v, ensure_ascii=False)
        if path not in old:
            conn.execute("INSERT INTO verdicts(kind, path, body) VALUES (?, ?, ?)", (kind, path, body))
        elif old[path] != body:
            conn.execute("UPDATE verdicts SET body=? WHERE kind=? AND path=?", (body, kind, path))


def _verdict_mirror(kind: str):
    def render(s) -> str:
        return json.dumps(_verdicts_in(s.conn, kind), indent=1, ensure_ascii=False) + "\n"      # as ready.py wrote it

    def load(s, text: str) -> None:
        d = json.loads(text)
        if not isinstance(d, dict):
            raise ValueError(f"{VERDICT_FILES[kind]} must be a JSON object")
        _write_verdicts(s.conn, kind, d)
    return render, load


def _clear(s, name: str) -> None:
    c = s.conn
    if name == "tasks":
        c.execute("DELETE FROM task_doc")
        c.execute("DELETE FROM tasks")
    elif name == "journal":
        c.execute("DELETE FROM journal")
    else:
        c.execute("DELETE FROM verdicts WHERE kind=?", (name.split(".", 1)[1],))


# ---- opening the store with the three micro kits registered -----------------------------------------------------------
def _kit(p: Path) -> store.Store:
    s = store.open(p)
    if not getattr(s, "_records_ready", False):
        keep_out_of_git(s)
        s.ensure("core.tasks", 1, TASKS_DDL)
        s.ensure("core.journal", 1, JOURNAL_DDL)
        s.ensure("core.verdicts", 1, VERDICTS_DDL)
        s.mirror("tasks", _rel(p, tasks_path(p)), _render_tasks, _load_tasks)
        s.mirror("journal", _rel(p, journal_path(p)), _render_journal, _load_journal)
        for kind in VERDICT_FILES:
            render, load = _verdict_mirror(kind)
            s.mirror(f"verdicts.{kind}", _rel(p, verdict_path(p, kind)), render, load)
        s._records_ready = True
    return s


def keep_out_of_git(s: store.Store) -> None:
    """The database and its side files never belong in git (they are rebuilt from the mirrors), whatever the project's own
    .gitignore says: a `*` inside state/ ignores the whole folder, this file included."""
    gi = s.path.parent / ".gitignore"
    if not gi.exists():
        try:
            gi.write_text("*\n")
        except OSError:
            pass


_SIGS: dict = {}     # (database, mirror) -> the file's stamp when this process last saw it equal to the database


def _sig(f: Path):
    try:
        st = f.stat()
    except OSError:
        return None
    return (st.st_mtime_ns, st.st_size, st.st_ino)


def _forget(s: store.Store, name: str) -> None:
    """The mirror file is gone: its records are empty again (what deleting the file always meant)."""
    row = s.q1("SELECT sha FROM mirrors WHERE name=?", (name,))
    if row and row["sha"]:
        with s.tx() as db:
            _clear(s, name)
            db.execute("UPDATE mirrors SET sha=NULL, at=? WHERE name=?", (store.now(), name))
            s.event("mirror-gone", name)


def _fresh(s: store.Store, name: str, f: Path) -> None:
    """Bring the records up to date with their mirror file before a read or write. A file this process has already seen
    unchanged (same stamp, settled) costs one stat call; otherwise its hash is compared with what the store last wrote
    and only a difference is imported (the file wins)."""
    key = (str(s.path), name)
    sig = _sig(f)
    if sig is not None and _SIGS.get(key) == sig and time.time() - sig[0] / 1e9 > _SETTLE:
        return
    if sig is None:
        _forget(s, name)
    else:
        row = s.q1("SELECT sha FROM mirrors WHERE name=?", (name,))
        if not (row and row["sha"] == store.sha(f.read_text(encoding="utf-8"))):
            s.sync(name, force=True)
    _SIGS[key] = sig


def _publish(s: store.Store, name: str, f: Path) -> None:
    s.write(name)
    _SIGS[(str(s.path), name)] = _sig(f)


def _reader(p: Path, name: str, f: Path):
    """The store, up to date, for a read; None when there is nothing at all (no file, no database): no database is
    created just to find that out."""
    if not f.exists() and not _db_path(p).exists():
        return None
    s = _kit(p)
    _fresh(s, name, f)
    return s if f.exists() else None


# ---- tasks ------------------------------------------------------------------------------------------------------------
def tasks_exists(project=None) -> bool:
    return tasks_path(project).is_file()


def tasks_doc(project=None) -> dict:
    """The task list. Raises FileNotFoundError when there is none and ValueError when the file is not valid JSON, the
    same as reading the file did."""
    p = project_of(project)
    f = tasks_path(p)
    s = _reader(p, "tasks", f)
    if s is None:
        raise FileNotFoundError(2, "No such file or directory", str(f))
    doc = _read_tasks(s.conn)
    return {} if doc is None else doc


def tasks_text(project=None) -> str:
    """The mirror's text (what git and the owner see), after bringing it up to date."""
    p = project_of(project)
    f = tasks_path(p)
    if _reader(p, "tasks", f) is None:
        raise FileNotFoundError(2, "No such file or directory", str(f))
    return f.read_text(encoding="utf-8")


def tasks_update(project, change, default=None) -> dict:
    """Load the task list (or a copy of `default` when there is none), call change(doc) (it may change the dict in place or
    return a new one), save. All in ONE write transaction, so two agents changing it at once never lose a change; if
    change() raises or exits, nothing is saved. Nothing is written when change() left the list as it was. With a default,
    a task list that is not valid JSON is replaced by it (what the setup task always did). Returns the saved list."""
    p = project_of(project)
    f = tasks_path(p)
    s = _kit(p)
    corrupt = False
    try:
        _fresh(s, "tasks", f)
    except ValueError:
        if default is None:
            raise
        corrupt = True
    with s.tx() as db:
        doc = None if corrupt else _read_tasks(db)
        if doc is None:
            if default is None and not f.exists():
                raise FileNotFoundError(2, "No such file or directory", str(f))
            doc, before = copy.deepcopy(default) if default is not None else {}, None
        else:
            before = json.dumps(doc, sort_keys=False)
        new = change(doc)
        new = doc if new is None else new
        if before is not None and json.dumps(new, sort_keys=False) == before:
            return new
        _write_tasks(db, new)
    _publish(s, "tasks", f)
    return new


def tasks_save(project, doc: dict) -> None:
    tasks_update(project, lambda _old: doc, default={})


# ---- journal ----------------------------------------------------------------------------------------------------------
def journal_present(project=None) -> bool:
    return journal_path(project).is_file()


def journal_lines(project=None) -> list[str]:
    """Every line of the journal, in order, blank ones included (a line's number is its position). FileNotFoundError when
    there is no journal."""
    p = project_of(project)
    f = journal_path(p)
    s = _reader(p, "journal", f)
    if s is None:
        raise FileNotFoundError(2, "No such file or directory", str(f))
    return [r["line"] for r in s.conn.execute("SELECT line FROM journal ORDER BY seq")]


def journal_entries(project=None) -> list[dict]:
    """The journal's entries (dicts), in file order; blank and unreadable lines are left out; [] when there is no journal."""
    try:
        lines = journal_lines(project)
    except FileNotFoundError:
        return []
    out = []
    for ln in lines:
        if ln.strip():
            try:
                e = json.loads(ln)
            except ValueError:
                continue
            if isinstance(e, dict):
                out.append(e)
    return out


def journal_next_id(project=None) -> str:
    """The id the next entry would get (a peek: journal_add decides the real one inside its transaction)."""
    p = project_of(project)
    s = _reader(p, "journal", journal_path(p))
    if s is None:
        return "J0001"
    return f"J{(s.q1('SELECT MAX(jid) m FROM journal')['m'] or 0) + 1:04d}"


def journal_ensure(project) -> bool:
    """Make sure the journal exists (empty when new). True when this call made it."""
    p = project_of(project)
    f = journal_path(p)
    if f.exists():
        return False
    s = _kit(p)
    _fresh(s, "journal", f)
    _publish(s, "journal", f)
    return True


def journal_add(project, make) -> dict:
    """File one new entry: under the journal's lock and inside one write transaction the next free id is taken,
    make(jid) builds the entry (a dict that carries that id), and its line is saved and appended to the mirror. Two
    parallel adds never get the same id. The mirror is appended to, never rewritten."""
    p = project_of(project)
    f = journal_path(p)
    s = _kit(p)
    for _ in range(5):
        _fresh(s, "journal", f)
        with atomic.locked(f):
            cur = f.read_text(encoding="utf-8") if f.exists() else None
            row = s.q1("SELECT sha FROM mirrors WHERE name='journal'")
            known = row["sha"] if row else None
            if (cur is None and known) or (cur is not None and store.sha(cur) != known):
                continue                 # the file changed outside the store since the last look: import it, then retry
            with s.tx() as db:
                n = (db.execute("SELECT MAX(jid) m FROM journal").fetchone()["m"] or 0) + 1
                entry = make(f"J{n:04d}")
                line = json.dumps(entry, ensure_ascii=False)
                db.execute("INSERT INTO journal(jid, line) VALUES (?, ?)", (_jid_of(entry), line))
                add = ("\n" if cur and not cur.endswith("\n") else "") + line + "\n"
                with f.open("a", encoding="utf-8") as fh:
                    fh.write(add)
                    fh.flush()
                    os.fsync(fh.fileno())
                db.execute("INSERT INTO mirrors(name, path, sha, at) VALUES ('journal', ?, ?, ?) ON CONFLICT(name) DO UPDATE "
                           "SET path=excluded.path, sha=excluded.sha, at=excluded.at",
                           (_rel(p, f), store.sha((cur or "") + add), store.now()))
            _SIGS[(str(s.path), "journal")] = _sig(f)
            return entry
    raise RuntimeError("the journal is being changed by something outside the kit; try again")


def journal_append(project, entry: dict) -> dict:
    """File an entry that is complete (it carries its own id, or it is an update line with `of`)."""
    return journal_add(project, lambda _jid: entry)


# ---- verdicts (READY, failed READY, pre-flight) -----------------------------------------------------------------------
def verdicts(project, kind: str) -> dict:
    """{page: verdict} of the kind; {} when none was ever recorded; ValueError when the file is not valid JSON."""
    p = project_of(project)
    f = verdict_path(p, kind)
    s = _reader(p, f"verdicts.{kind}", f)
    return {} if s is None else _verdicts_in(s.conn, kind)


def verdicts_update(project, kind: str, change) -> dict:
    """Load the verdicts, change(dict) (in place, or return a new one), save, all in ONE write transaction."""
    p = project_of(project)
    f = verdict_path(p, kind)
    name = f"verdicts.{kind}"
    s = _kit(p)
    _fresh(s, name, f)
    with s.tx() as db:
        d = _verdicts_in(db, kind)
        new = change(d)
        new = d if new is None else new
        _write_verdicts(db, kind, new)
    _publish(s, name, f)
    return new
