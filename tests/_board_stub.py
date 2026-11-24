"""A small stand-in for kit/tools/board.py (the real one is built on another branch), with the same functions the lane and
runner modules call, over two SQLite tables in the project's store. Tests put it in sys.modules["board"]; after the merge
the real board replaces it (set LANES_TEST_REAL_BOARD=1 to run the same tests against the real one).

Extra helpers only the stub has: enqueue(), jobs(), set_pool().
"""
from __future__ import annotations

import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "kit" / "tools"))
import store  # noqa: E402

DDL = """
CREATE TABLE IF NOT EXISTS stub_jobs (id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, kit TEXT, runner TEXT, path TEXT,
    key TEXT, type TEXT, cluster TEXT, resource TEXT, status TEXT NOT NULL DEFAULT 'queued', holder TEXT, attempts INTEGER NOT NULL DEFAULT 0,
    proof TEXT, why TEXT, beats INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS stub_res (resource TEXT NOT NULL, slot TEXT NOT NULL, holder TEXT NOT NULL, PRIMARY KEY(resource, slot))
"""
POOLS = {"browser": 3}


def _s(project):
    s = store.open(project)
    s.ensure("stub.board", 1, DDL)
    return s


def set_pool(resource: str, size: int) -> None:
    POOLS[resource] = size


def _take(db, resource, holder):
    mine = db.execute("SELECT slot FROM stub_res WHERE resource=? AND holder=?", (resource, holder)).fetchone()
    if mine:
        return mine["slot"]
    taken = {r["slot"] for r in db.execute("SELECT slot FROM stub_res WHERE resource=?", (resource,))}
    if resource == "port":
        slot = None
        for _ in range(50):
            with socket.socket() as k:
                k.bind(("127.0.0.1", 0))
                cand = str(k.getsockname()[1])
            if cand not in taken:
                slot = cand
                break
    elif resource in POOLS:
        slot = next((str(i) for i in range(1, POOLS[resource] + 1) if str(i) not in taken), None)
    else:
        slot = None if "lock" in taken else "lock"
    if slot is not None:
        db.execute("INSERT INTO stub_res(resource, slot, holder) VALUES(?,?,?)", (resource, slot, holder))
    return slot


def acquire(resource, holder, lease_s=1800, project=None):
    s = _s(project)
    with s.tx() as db:
        slot = _take(db, resource, holder)
        return None if slot is None else {"resource": resource, "slot": slot, "holder": holder, "until": "later"}


def release(resource, holder, project=None):
    s = _s(project)
    with s.tx() as db:
        return db.execute("DELETE FROM stub_res WHERE resource=? AND holder=?", (resource, holder)).rowcount > 0


def held(resource=None, project=None):
    s = _s(project)
    q, a = "SELECT resource, slot, holder FROM stub_res", ()
    if resource:
        q, a = q + " WHERE resource=?", (resource,)
    return [dict(r) for r in s.q(q, a)]


def enqueue(kind, path="/x", key="x", type="post", cluster="", resource=None, runner="machine", kit="evidence", project=None):
    s = _s(project)
    with s.tx() as db:
        return db.execute("INSERT INTO stub_jobs(kind, kit, runner, path, key, type, cluster, resource) VALUES(?,?,?,?,?,?,?,?)",
                          (kind, kit, runner, path, key, type, cluster, resource)).lastrowid


def jobs(project=None):
    return [dict(r) for r in _s(project).q("SELECT * FROM stub_jobs ORDER BY id")]


def claim(agent, kit=None, runner=None, lease_s=None, project=None, kinds=None, st=None):
    """Like the real board: the claim takes the job's resource itself (resource_slot), and a job whose resource is full is skipped."""
    s = _s(project)
    with s.tx() as db:
        sql, args = "SELECT * FROM stub_jobs WHERE status='queued'", []
        if kit:
            sql += " AND kit=?"; args.append(kit)
        if runner:
            sql += " AND runner=?"; args.append(runner)
        if kinds:
            sql += f" AND kind IN ({','.join('?' * len(kinds))})"; args += list(kinds)
        for row in db.execute(sql + " ORDER BY id", args).fetchall():
            slot = _take(db, row["resource"], agent) if row["resource"] else None
            if row["resource"] and slot is None:
                continue
            db.execute("UPDATE stub_jobs SET status='claimed', holder=?, attempts=attempts+1 WHERE id=?", (agent, row["id"]))
            return {"id": row["id"], "kind": row["kind"], "kit": row["kit"], "resource": row["resource"], "resource_slot": slot,
                    "port": int(slot) if row["resource"] == "port" else None,
                    "page": row["path"] or None, "path": row["path"] or None, "key": row["key"], "type": row["type"], "cluster": row["cluster"]}
    return None


def beat(job_id, agent, project=None):
    s = _s(project)
    with s.tx() as db:
        return db.execute("UPDATE stub_jobs SET beats=beats+1 WHERE id=? AND holder=? AND status='claimed'", (job_id, agent)).rowcount > 0


def done(job_id, agent, proof, project=None):
    s = _s(project)
    with s.tx() as db:
        db.execute("UPDATE stub_jobs SET status='done', proof=? WHERE id=? AND holder=?", (proof, job_id, agent))
        db.execute("DELETE FROM stub_res WHERE holder=?", (agent,))
    return {"id": job_id, "status": "done"}


def fail(job_id, agent, why, project=None):
    s = _s(project)
    with s.tx() as db:
        db.execute("UPDATE stub_jobs SET status='failed', why=? WHERE id=? AND holder=?", (why, job_id, agent))
        db.execute("DELETE FROM stub_res WHERE holder=?", (agent,))
    return {"id": job_id, "status": "failed"}


def use_board(monkeypatch):
    """Make `import board` give this stub (or the real board.py when LANES_TEST_REAL_BOARD=1). Returns that module."""
    import os
    if os.environ.get("LANES_TEST_REAL_BOARD") == "1":
        import board
        return board
    monkeypatch.setitem(sys.modules, "board", sys.modules[__name__])
    POOLS.clear()
    POOLS["browser"] = 3
    return sys.modules[__name__]
