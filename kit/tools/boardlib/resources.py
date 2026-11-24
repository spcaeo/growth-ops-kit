"""Resources of the work board (kit 3.0, micro kit core): pools and locks handed out one turn at a time.

  pool   browser (capacity 3), port (18440 to 18459): each holder gets a distinct slot; a port is a preview port.
  lock   owner-preview, shared-code: one holder.
  pacer  google: not held; every turn goes through pace.py.

A hold is a row in `leases` (resource, slot, holder, job, until). UNIQUE(resource, slot) means two holders can never
share a slot, whatever the code does. A job's lease is its resource lease: it lives and dies with the job's own lease
(board.claim, beat, done, fail, expire). A lock taken by hand (`growth lock shared-code --agent X`) has no job and its
own expiry; a lease whose time ran out is freed by the next claim or lock call, so a stopped agent never holds a door shut.

Settings (growth.json): {"resources": {"browser": 3, "port_range": [18440, 18459]}}.
"""
from __future__ import annotations

import datetime as dt
import errno
import socket
from pathlib import Path

import kits
import store

from . import schema as board_schema

DEFAULT_LEASE_S = 1800


def ts(offset_s: float = 0) -> str:
    """UTC ISO time in store.now()'s own form (sortable as text), `offset_s` seconds from now."""
    return (dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=offset_s)).replace(microsecond=0).isoformat()


def project_cfg(st) -> dict:
    f = Path(st.project) / "growth.json"
    if not f.is_file():
        return {}
    import config
    return config.load_cfg(Path(st.project))


def defs(st) -> dict:
    """Every resource: the manifest's definition with growth.json's numbers laid over it. Pools: {"resources": {"browser": 3,
    "port": [18440, 18459]}} (port_range is the same list under its older name). Every pacer named in growth.json "pacers"
    is a resource too (an engine other than google comes only from the project's own config)."""
    out = {name: dict(d) for name, d in kits.resources().items()}
    cfg = project_cfg(st)
    over = cfg.get("resources") or {}
    if isinstance(over.get("browser"), int) and over["browser"] > 0 and "browser" in out:
        out["browser"]["capacity"] = over["browser"]
    rng = over.get("port") if isinstance(over.get("port"), (list, tuple)) else over.get("port_range")
    if isinstance(rng, (list, tuple)) and len(rng) == 2 and "port" in out:
        out["port"]["first"], out["port"]["last"] = int(rng[0]), int(rng[1])
    for name in (cfg.get("pacers") or {}):
        out.setdefault(name, {"kind": "pacer", "what": "a pacer named in growth.json"})
    return out


def _slots(d: dict) -> list:
    if d["kind"] == "lock":
        return [0]
    if d.get("first") is not None:
        return list(range(int(d["first"]), int(d["last"]) + 1))
    return list(range(1, int(d.get("capacity", 1)) + 1))


def _port_free(port: int) -> bool:
    """True when nothing on this machine listens on the port (an old server of a closed lane would clash). Only a refused
    connection counts as free: a busy or slow answer means someone is there."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.2)
    try:
        if s.connect_ex(("127.0.0.1", port)) != errno.ECONNREFUSED:
            return False
    except OSError:
        return True
    finally:
        s.close()
    b = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        b.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        b.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        b.close()


def holds(d: dict) -> bool:
    return d["kind"] in ("pool", "lock")


def acquire(db, st, name: str, holder: str, job_id, until: str):
    """Take a slot of `name` (inside the caller's write transaction). Returns (True, slot) or (False, None) when none is
    free. A resource that is not held (none, pacer) always gives (True, None)."""
    d = defs(st).get(name)
    if d is None:
        raise KeyError(f"unknown resource '{name}' (known: {', '.join(defs(st))})")
    if not holds(d):
        return True, None
    taken = {r["slot"] for r in db.execute("SELECT slot FROM leases WHERE resource=?", (name,))}
    for slot in _slots(d):
        if slot in taken or (name == "port" and not _port_free(slot)):
            continue
        db.execute("INSERT INTO leases(resource, slot, holder, job, taken, until) VALUES(?, ?, ?, ?, ?, ?)",
                   (name, slot, holder, job_id, store.now(), until))
        return True, slot
    return False, None


def has_room(db, st, name: str) -> bool:
    """Is a slot free (checked without taking it)?"""
    d = defs(st).get(name)
    if d is None or not holds(d):
        return True
    n = db.execute("SELECT COUNT(*) n FROM leases WHERE resource=?", (name,)).fetchone()["n"]
    return n < len(_slots(d))


def release_job(db, job_id) -> None:
    db.execute("DELETE FROM leases WHERE job=?", (job_id,))


def renew_job(db, job_id, until: str) -> None:
    db.execute("UPDATE leases SET until=? WHERE job=?", (until, job_id))


def expire_manual(db, st) -> list:
    """Free every hand-taken lock (no job) whose time ran out; returns the freed rows as events were written."""
    rows = db.execute("SELECT * FROM leases WHERE job IS NULL AND until < ?", (store.now(),)).fetchall()
    for r in rows:
        db.execute("DELETE FROM leases WHERE id=?", (r["id"],))
        st.event("lock-expired", r["resource"], {"holder": r["holder"], "slot": r["slot"]}, who=r["holder"])
    return rows


# -- locks taken by hand ----------------------------------------------------------------------------------------------
def lock_take(st, name: str, agent: str, lease_s: int = DEFAULT_LEASE_S):
    """Try to take lock `name`. Returns (True, None) when taken or already yours (the lease is renewed), else
    (False, {"holder", "until", "job"}) of the one who holds it."""
    d = defs(st).get(name)
    if d is None or d["kind"] != "lock":
        raise KeyError(f"'{name}' is not a lock (locks: {', '.join(n for n, v in defs(st).items() if v['kind'] == 'lock')})")
    board_schema.ready(st)
    with st.tx() as db:
        expire_manual(db, st)
        row = db.execute("SELECT * FROM leases WHERE resource=? AND slot=0", (name,)).fetchone()
        if row:
            if row["holder"] == agent and row["job"] is None:
                db.execute("UPDATE leases SET until=? WHERE id=?", (ts(lease_s), row["id"]))
                return True, None
            return False, {"holder": row["holder"], "until": row["until"], "job": row["job"]}
        db.execute("INSERT INTO leases(resource, slot, holder, job, taken, until) VALUES(?, 0, ?, NULL, ?, ?)",
                   (name, agent, store.now(), ts(lease_s)))
        st.event("lock-taken", name, {"lease_s": lease_s}, who=agent)
        return True, None


def lock_free(st, name: str, agent: str, force: bool = False):
    """Free lock `name`. Returns "freed", "free" (nobody held it), or an error text when someone else holds it."""
    board_schema.ready(st)
    with st.tx() as db:
        row = db.execute("SELECT * FROM leases WHERE resource=? AND slot=0", (name,)).fetchone()
        if not row:
            return "free"
        if row["job"] is not None and not force:
            return f"{name} is held by job {row['job']} of {row['holder']}; it frees itself when the job is done, failed or expires"
        if row["holder"] != agent and not force:
            return f"{name} is held by {row['holder']} (until {row['until']}), not by {agent}; use --force only when that holder is gone"
        db.execute("DELETE FROM leases WHERE id=?", (row["id"],))
        st.event("lock-freed", name, {"holder": row["holder"], "forced": bool(force and row["holder"] != agent)}, who=agent)
        return "freed"


def lease_rows(st) -> list:
    return [dict(r) for r in st.q("SELECT * FROM leases ORDER BY resource, slot")]


# -- slots taken by hand (no job): acquire / release / held of the board's public interface -----------------------------
def _row(r, kinds: dict) -> dict:
    """A lease row as a plain dict; the slot is text: the port number for "port", "lock" for a lock, "1".."N" for another pool."""
    slot = "lock" if kinds.get(r["resource"]) == "lock" else str(r["slot"])
    return {"resource": r["resource"], "slot": slot, "holder": r["holder"], "until": r["until"], "job": r["job"]}


def take(st, name: str, holder: str, lease_s: int = DEFAULT_LEASE_S):
    """A slot of pool or lock `name` for `holder`, outside any job. The same holder asking again gets its own slot back with a
    renewed lease. Returns {"resource", "slot", "holder", "until", "job"} or None when no slot is free."""
    board_schema.ready(st)
    d = defs(st).get(name)
    if d is None:
        raise KeyError(f"unknown resource '{name}' (known: {', '.join(defs(st))})")
    if not holds(d):
        raise KeyError(f"'{name}' is not a pool or a lock (a pacer is used through growth pace)")
    until = ts(lease_s)
    with st.tx() as db:
        expire_manual(db, st)
        mine = db.execute("SELECT * FROM leases WHERE resource=? AND holder=? AND job IS NULL", (name, holder)).fetchone()
        if mine:
            db.execute("UPDATE leases SET until=? WHERE id=?", (until, mine["id"]))
        else:
            ok, _ = acquire(db, st, name, holder, None, until)
            if not ok:
                return None
            st.event("lock-taken" if d["kind"] == "lock" else "slot-taken", name, {"lease_s": lease_s}, who=holder)
        return _row(db.execute("SELECT * FROM leases WHERE resource=? AND holder=? AND job IS NULL", (name, holder)).fetchone(),
                    {name: d["kind"]})


def give(st, name: str, holder: str) -> bool:
    """Give back the slot `holder` took by hand. False when it held none."""
    board_schema.ready(st)
    with st.tx() as db:
        cur = db.execute("DELETE FROM leases WHERE resource=? AND holder=? AND job IS NULL", (name, holder))
        if cur.rowcount:
            st.event("lock-freed", name, {"holder": holder}, who=holder)
        return bool(cur.rowcount)


def held(st, name: str | None = None) -> list:
    """Who holds which slot now (job holds included), expired hand-taken leases freed first."""
    board_schema.ready(st)
    kinds = {n: v["kind"] for n, v in defs(st).items()}
    with st.tx() as db:
        expire_manual(db, st)
        rows = db.execute("SELECT * FROM leases" + (" WHERE resource=?" if name else "") + " ORDER BY resource, slot", (name,) if name else ()).fetchall()
        return [_row(r, kinds) for r in rows]
