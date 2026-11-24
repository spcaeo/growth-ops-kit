#!/usr/bin/env python3
"""The pacer (kit 3.0, micro kit core): a shared timer for a door that must not be hit too often, today Google.

  growth pace google                  block until it is this agent's turn, record the turn, then return (exit 0)
  growth pace google --max-wait 30    give up (exit 3) when the turn is more than 30 s away; 0 = ask once, never wait
  growth pace google --robot          Google showed its robot check: no agent gets a turn for 10 minutes
  growth pace google --status         when the next turn may be taken

Rule (OWNER-RULES "Slow Google searches"): at most one Google search every 20 to 30 seconds, for ALL agents together;
when Google's robot check appears, pause 10 minutes. After each turn the next one is set a random 20 to 30 s later, and a
turn is given inside one write transaction, so two agents never get turns closer than the minimum. Run `growth pace
google` before EVERY Google search, in the agent's own browser.

Settings (growth.json): {"pacers": {"google": {"min_s": 20, "max_s": 30, "robot_pause_s": 600}}} (tests use small numbers).
"""
from __future__ import annotations

import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from boardlib import resources, schema as board_schema  # noqa: E402
import store  # noqa: E402

DEFAULTS = {"google": {"min_s": 20, "max_s": 30, "robot_pause_s": 600}}


def settings(st, name: str) -> dict:
    base = DEFAULTS.get(name)
    over = (resources.project_cfg(st).get("pacers") or {}).get(name)
    if base is None and over is None:
        raise KeyError(f"no pacer '{name}' (known: {', '.join(sorted(set(DEFAULTS) | set((resources.project_cfg(st).get('pacers') or {}))))})")
    cfg = {**(base or {"min_s": 20, "max_s": 30, "robot_pause_s": 600}), **(over or {})}
    cfg["max_s"] = max(cfg["max_s"], cfg["min_s"])
    return cfg


def turn(name: str = "google", agent: str | None = None, max_wait: float | None = None, st=None,
         sleep=time.sleep, clock=time.time):
    """Wait for the turn and take it. Returns {"at", "waited_s", "next_at"} or None when the turn is farther away than max_wait."""
    st = st or store.open()
    board_schema.ready(st)
    cfg = settings(st, name)
    started = clock()
    while True:
        with st.tx() as db:                                   # the write lock is ours: the decision below cannot race
            now = clock()
            row = db.execute("SELECT * FROM pacers WHERE name=?", (name,)).fetchone()
            ready_at = max((row["next_at"] or 0) if row else 0, (row["paused_until"] or 0) if row else 0)
            if now >= ready_at:
                nxt = now + random.uniform(cfg["min_s"], cfg["max_s"])
                db.execute("INSERT INTO pacers(name, last_turn, next_at, paused_until) VALUES(?, ?, ?, ?) ON CONFLICT(name) DO UPDATE "
                           "SET last_turn=excluded.last_turn, next_at=excluded.next_at", (name, now, nxt, row["paused_until"] if row else None))
                st.event("pace-turn", name, {"t": now, "next_at": nxt, "waited_s": round(now - started, 3)}, who=agent)
                return {"at": now, "waited_s": now - started, "next_at": nxt}
        wait = ready_at - now
        if max_wait is not None and (now - started) + wait > max_wait:
            return None
        sleep(min(wait, 5.0) + random.uniform(0.0, 0.05))


def robot(name: str = "google", agent: str | None = None, st=None, clock=time.time) -> float:
    """Pause every turn of `name` for its robot pause (default 10 minutes). Returns the time the pause ends."""
    st = st or store.open()
    board_schema.ready(st)
    cfg = settings(st, name)
    with st.tx() as db:
        until = clock() + cfg["robot_pause_s"]
        db.execute("INSERT INTO pacers(name, last_turn, next_at, paused_until) VALUES(?, NULL, NULL, ?) ON CONFLICT(name) DO UPDATE "
                   "SET paused_until=MAX(COALESCE(pacers.paused_until, 0), excluded.paused_until)", (name, until))
        st.event("pace-robot", name, {"until": until, "pause_s": cfg["robot_pause_s"]}, who=agent)
        return until


def status(name: str = "google", st=None, clock=time.time) -> dict:
    st = st or store.open()
    board_schema.ready(st)
    row = st.q1("SELECT * FROM pacers WHERE name=?", (name,))
    now = clock()
    nxt = max((row["next_at"] or 0) if row else 0, (row["paused_until"] or 0) if row else 0)
    return {"in_s": max(0.0, nxt - now), "paused": bool(row and (row["paused_until"] or 0) > now),
            "last_turn": row["last_turn"] if row else None}


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="growth pace", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("name", nargs="?", default="google")
    ap.add_argument("--robot", action="store_true", help="Google's robot check appeared: pause every turn for the robot pause")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--max-wait", type=float, default=None, help="seconds; give up (exit 3) when the turn is farther away")
    ap.add_argument("--agent", default=None)
    a = ap.parse_args(argv)
    agent = a.agent or store.actor()
    try:
        if a.robot:
            until = robot(a.name, agent)
            print(f"{a.name} paused for {settings(store.open(), a.name)['robot_pause_s'] // 60} minutes (until {time.strftime('%H:%M:%S', time.localtime(until))}). "
                  f"Do not search until growth pace {a.name} returns.")
        elif a.status:
            s = status(a.name)
            print(f"{a.name}: next turn in {s['in_s']:.0f} s" + (" (paused: robot check)" if s["paused"] else ""))
        else:
            r = turn(a.name, agent, a.max_wait)
            if r is None:
                s = status(a.name)
                print(f"{a.name}: the next turn is {s['in_s']:.0f} s away (more than --max-wait)")
                return 3
            print(f"{a.name}: your turn (waited {r['waited_s']:.0f} s)")
    except KeyError as e:
        print(f"growth pace: {e.args[0]}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
