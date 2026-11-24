"""The project's one local database (kit 3.0, micro kit "core").

Every project keeps its shared state in one SQLite file, `<project>/state/growth.db`: what every agent reads and writes
at the same time (tasks, the journal, verdicts, the work board, resources). Python's own sqlite3, WAL mode, so many
readers never wait and writers take short turns.

Three ideas:
  - **Each micro kit owns its tables.** It registers them once with `ensure(name, version, ddl)`; the DDL must be
    idempotent (CREATE ... IF NOT EXISTS). A higher version runs the micro kit's `migrate` callback.
  - **Every change is an event.** `event(kind, subject, data)` appends who did what and when (actor = $GROWTH_AGENT,
    else "lead"), so real timings can be read later (`growth board times`).
  - **Mirrors keep the plain files.** A micro kit may register a mirror: a readable file (for example docs/tasks.json)
    that the store rewrites after each change, so hooks, permissions, git diffs and older readers keep working and the
    project still moves between machines as plain files. When a mirror was changed outside the store (restored from
    git, copied from another machine) the next `sync()` imports it: the file wins, and the import is an event.

    with store.open().tx() as db:              # BEGIN IMMEDIATE ... COMMIT
        db.execute("INSERT INTO ...")
    store.open().event("task-added", "T12")

The database file is rebuildable from the mirrors; it is not meant for git (templates/project/.gitignore: state/).
"""
from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
import json
import os
import sqlite3
import sys
import threading
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))
import atomic  # noqa: E402

DB_NAME = "growth.db"
BUSY_MS = 10_000

CORE_DDL = """
CREATE TABLE IF NOT EXISTS meta    (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS schemas (name TEXT PRIMARY KEY, version INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS events  (id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, actor TEXT NOT NULL,
                                    kind TEXT NOT NULL, subject TEXT NOT NULL DEFAULT '', data TEXT);
CREATE INDEX IF NOT EXISTS events_kind ON events(kind, subject);
CREATE TABLE IF NOT EXISTS mirrors (name TEXT PRIMARY KEY, path TEXT NOT NULL, sha TEXT, at TEXT);
"""


def now() -> str:
    """UTC, ISO 8601 with the offset, to the second: sortable as text and never moved by a timezone change."""
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def actor() -> str:
    return (os.environ.get("GROWTH_AGENT") or "lead").strip() or "lead"


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Mirror:
    def __init__(self, name: str, rel: str, render: Callable[["Store"], str], load: Callable[["Store", str], None]):
        self.name, self.rel, self.render, self.load = name, rel, render, load


class Store:
    def __init__(self, project: Path):
        self.project = Path(project).resolve()
        self.path = self.project / "state" / DB_NAME
        self._local = threading.local()
        self._mirrors: dict[str, Mirror] = {}
        self._synced: set[str] = set()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._core()

    # -- connection -------------------------------------------------------------------------------------------------
    @property
    def conn(self) -> sqlite3.Connection:
        """One connection per thread and per process (a forked child never reuses its parent's)."""
        c = getattr(self._local, "conn", None)
        if c is None or getattr(self._local, "pid", None) != os.getpid():
            c = sqlite3.connect(self.path, timeout=BUSY_MS / 1000, isolation_level=None, check_same_thread=True)
            c.row_factory = sqlite3.Row
            c.execute(f"PRAGMA busy_timeout={BUSY_MS}")
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA synchronous=NORMAL")
            c.execute("PRAGMA foreign_keys=ON")
            self._local.conn, self._local.pid, self._local.depth = c, os.getpid(), 0
        return c

    @contextlib.contextmanager
    def tx(self):
        """A write transaction (BEGIN IMMEDIATE: the write lock is taken at the start, so two writers never both read
        old data and then both write). Nested use joins the outer transaction."""
        c = self.conn
        if self._local.depth:
            self._local.depth += 1
            try:
                yield c
            finally:
                self._local.depth -= 1
            return
        c.execute("BEGIN IMMEDIATE")
        self._local.depth = 1
        try:
            yield c
            c.execute("COMMIT")
        except BaseException:
            c.execute("ROLLBACK")
            raise
        finally:
            self._local.depth = 0

    def q(self, sql: str, args=()) -> list[sqlite3.Row]:
        return self.conn.execute(sql, args).fetchall()

    def q1(self, sql: str, args=()):
        return self.conn.execute(sql, args).fetchone()

    # -- schemas ----------------------------------------------------------------------------------------------------
    def _core(self):
        c = self.conn
        c.executescript(CORE_DDL)

    def ensure(self, name: str, version: int, ddl: str, migrate: Callable[[sqlite3.Connection, int], None] | None = None):
        """Create a micro kit's tables (idempotent DDL) and run its migration when the stored version is lower."""
        row = self.q1("SELECT version FROM schemas WHERE name=?", (name,))
        if row and row["version"] >= version:
            return
        with self.tx() as db:
            row = db.execute("SELECT version FROM schemas WHERE name=?", (name,)).fetchone()
            old = row["version"] if row else 0
            if old >= version:
                return
            for stmt in [s for s in ddl.split(";") if s.strip()]:
                db.execute(stmt)
            if migrate and old:
                migrate(db, old)
            db.execute("INSERT INTO schemas(name, version) VALUES(?, ?) ON CONFLICT(name) DO UPDATE SET version=excluded.version",
                       (name, version))

    # -- meta and events --------------------------------------------------------------------------------------------
    def get(self, key: str, default=None):
        row = self.q1("SELECT value FROM meta WHERE key=?", (key,))
        return json.loads(row["value"]) if row else default

    def set(self, key: str, value) -> None:
        with self.tx() as db:
            db.execute("INSERT INTO meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                       (key, json.dumps(value)))

    def event(self, kind: str, subject: str = "", data=None, who: str | None = None) -> int:
        with self.tx() as db:
            cur = db.execute("INSERT INTO events(at, actor, kind, subject, data) VALUES(?, ?, ?, ?, ?)",
                             (now(), who or actor(), kind, subject, json.dumps(data) if data is not None else None))
            return cur.lastrowid

    def events(self, kind: str | None = None, subject: str | None = None, limit: int = 1000) -> list[dict]:
        sql, args = "SELECT * FROM events", []
        conds = []
        if kind:
            conds.append("kind=?"); args.append(kind)
        if subject is not None:
            conds.append("subject=?"); args.append(subject)
        if conds:
            sql += " WHERE " + " AND ".join(conds)
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        return [{**dict(r), "data": json.loads(r["data"]) if r["data"] else None} for r in self.q(sql, args)]

    # -- mirrors ----------------------------------------------------------------------------------------------------
    def mirror(self, name: str, rel: str, render: Callable[["Store"], str], load: Callable[["Store", str], None]) -> None:
        """Register a mirror: `rel` is the file's path inside the project; render(store) gives its text from the
        database; load(store, text) replaces the micro kit's rows from the file's text."""
        self._mirrors[name] = Mirror(name, rel, render, load)

    def _file(self, m: Mirror) -> Path:
        return self.project / m.rel

    def sync(self, name: str, force: bool = False) -> bool:
        """Import the mirror when the file differs from what the store last wrote (or the database has never seen it).
        Returns True when it imported. Runs once per process per mirror unless forced."""
        if name in self._synced and not force:
            return False
        m = self._mirrors[name]
        f = self._file(m)
        imported = False
        with atomic.locked(f):
            if f.exists():
                text = f.read_text(encoding="utf-8")
                h = sha(text)
                row = self.q1("SELECT sha FROM mirrors WHERE name=?", (name,))
                if not row or row["sha"] != h:
                    with self.tx() as db:
                        m.load(self, text)
                        db.execute("INSERT INTO mirrors(name, path, sha, at) VALUES(?, ?, ?, ?) ON CONFLICT(name) DO UPDATE "
                                   "SET path=excluded.path, sha=excluded.sha, at=excluded.at", (name, m.rel, h, now()))
                        self.event("mirror-import", name, {"path": m.rel, "sha": h[:12], "was": (row["sha"][:12] if row and row["sha"] else None)})
                    imported = True
        self._synced.add(name)
        return imported

    def write(self, name: str) -> Path:
        """Rewrite the mirror from the database (under the file's lock, so the last writer always writes the newest
        state) and remember its hash."""
        m = self._mirrors[name]
        f = self._file(m)
        with atomic.locked(f):
            text = m.render(self)
            atomic.write_text(f, text)
            with self.tx() as db:
                db.execute("INSERT INTO mirrors(name, path, sha, at) VALUES(?, ?, ?, ?) ON CONFLICT(name) DO UPDATE "
                           "SET path=excluded.path, sha=excluded.sha, at=excluded.at", (name, m.rel, sha(text), now()))
        return f


_OPEN: dict[tuple[str, int], Store] = {}
_LOCK = threading.Lock()


def open(project: Path | str | None = None) -> Store:  # noqa: A001  (store.open reads well at the call site)
    """The store of `project` (default: config.find_project()), one per process."""
    if project is None:
        import config
        project = config.require_project()
    key = (str(Path(project).resolve()), os.getpid())
    with _LOCK:
        s = _OPEN.get(key)
        if s is None:
            s = _OPEN[key] = Store(Path(project))
        return s


def main(argv=None) -> int:
    """growth store info | events [--kind K] [--subject S] [--limit N] | sync"""
    import argparse
    ap = argparse.ArgumentParser(prog="growth store", description=main.__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("info", help="where the database is, its size, its micro kits' tables and versions, its mirrors")
    e = sub.add_parser("events", help="the newest events (who did what, when)")
    e.add_argument("--kind"); e.add_argument("--subject"); e.add_argument("--limit", type=int, default=30)
    a = ap.parse_args(argv)
    s = open()
    if a.cmd == "info":
        size = s.path.stat().st_size if s.path.exists() else 0
        print(f"database {s.path} ({size / 1024:.0f} KB)")
        for r in s.q("SELECT name, version FROM schemas ORDER BY name"):
            print(f"  micro kit {r['name']}: schema v{r['version']}")
        for r in s.q("SELECT name, path, at FROM mirrors ORDER BY name"):
            print(f"  mirror {r['name']}: {r['path']} (written {r['at']})")
        print(f"  events: {s.q1('SELECT COUNT(*) n FROM events')['n']}")
    elif a.cmd == "events":
        for ev in reversed(s.events(a.kind, a.subject, a.limit)):
            print(f"{ev['at']}  {ev['actor']:12} {ev['kind']:18} {ev['subject']}  {json.dumps(ev['data']) if ev['data'] else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
