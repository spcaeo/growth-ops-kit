"""The work board's tables (kit 3.0, micro kit core), registered once with store.ensure("core.board", ...).

  pages   one row per page on the board: path, key, type, cluster, stage, holder, updated
  jobs    one row per job (see board.py for the life of a job)
  resources, leases   what the resources are and who holds which slot (resources.py)
  pacers  the next time a paced door (google) may take a turn (pace.py)

The DDL holds no semicolon inside a statement: store.ensure splits on them.
"""
from __future__ import annotations

NAME = "core.board"
VERSION = 1

DDL = """
CREATE TABLE IF NOT EXISTS pages (
    path TEXT PRIMARY KEY, key TEXT NOT NULL, type TEXT NOT NULL, cluster TEXT,
    stage TEXT NOT NULL DEFAULT 'research', holder TEXT, created TEXT NOT NULL, updated TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, kit TEXT NOT NULL, page TEXT,
    way TEXT NOT NULL, runner TEXT NOT NULL, resource TEXT NOT NULL DEFAULT 'none',
    needs TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','claimed','done','failed','blocked','cancelled')),
    holder TEXT, lease_until TEXT, lease_s INTEGER, attempts INTEGER NOT NULL DEFAULT 0, slot INTEGER,
    priority INTEGER NOT NULL DEFAULT 0, refresh INTEGER NOT NULL DEFAULT 0, proof TEXT, why TEXT, task TEXT, step INTEGER,
    created TEXT NOT NULL, started TEXT, finished TEXT);
CREATE INDEX IF NOT EXISTS jobs_queue ON jobs(status, kit);
CREATE INDEX IF NOT EXISTS jobs_page ON jobs(page);
CREATE TABLE IF NOT EXISTS resources (name TEXT PRIMARY KEY, kind TEXT NOT NULL, capacity INTEGER, info TEXT);
CREATE TABLE IF NOT EXISTS leases (
    id INTEGER PRIMARY KEY AUTOINCREMENT, resource TEXT NOT NULL, slot INTEGER NOT NULL, holder TEXT NOT NULL,
    job INTEGER, taken TEXT NOT NULL, until TEXT NOT NULL, UNIQUE(resource, slot));
CREATE TABLE IF NOT EXISTS pacers (name TEXT PRIMARY KEY, last_turn REAL, next_at REAL, paused_until REAL)
"""


def ready(st) -> None:
    """Make sure the board's tables exist in this store (once per store object)."""
    if getattr(st, "_board_ready", False):
        return
    st.ensure(NAME, VERSION, DDL)
    st._board_ready = True
