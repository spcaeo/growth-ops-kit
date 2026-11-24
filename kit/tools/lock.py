#!/usr/bin/env python3
"""Locks of the work board (kit 3.0, micro kit core): a door that only one holder may use at a time.

  growth lock shared-code --agent builder-1 [--lease 1800] [--wait 60]    take it (exit 3 when someone else holds it)
  growth unlock shared-code --agent builder-1 [--force]                   give it back
  growth lock status                                                      who holds what (also: growth lock --list)

Locks: owner-preview (the one preview address the owner sees; the READY job holds it) and shared-code (one writer of the
shared site code: nothing else enforces it on a site whose own checks read no code). A lock is held for a lease (30 minutes by default; take it again to renew it); a holder that stopped
loses it when the lease runs out, so a stopped agent never keeps a door shut. A READY job or a shared-code job holds
its lock for as long as the job's own lease runs.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from boardlib import resources  # noqa: E402
import store  # noqa: E402


def main(argv=None, mode: str = "lock") -> int:
    import argparse
    ap = argparse.ArgumentParser(prog=f"growth {mode}", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("name", nargs="?")
    ap.add_argument("--agent", default=None, help="who takes the lock (default: $GROWTH_AGENT, else lead)")
    ap.add_argument("--lease", type=int, default=resources.DEFAULT_LEASE_S, help="seconds the lock is held before it frees itself")
    ap.add_argument("--wait", type=float, default=0, help="seconds to keep trying when someone else holds it")
    ap.add_argument("--force", action="store_true", help="unlock: free a lock another holder had (only when that holder is gone)")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args(argv)
    st = store.open()
    agent = a.agent or store.actor()
    if a.list or not a.name or a.name == "status":
        from boardlib import schema as board_schema
        board_schema.ready(st)
        rows = [r for r in resources.lease_rows(st) if resources.defs(st).get(r["resource"], {}).get("kind") == "lock"]
        locks = [n for n, d in resources.defs(st).items() if d["kind"] == "lock"]
        for n in locks:
            held = [r for r in rows if r["resource"] == n]
            print(f"{n}: " + (f"held by {held[0]['holder']}{' (job ' + str(held[0]['job']) + ')' if held[0]['job'] else ''} until {held[0]['until']}" if held else "free"))
        return 0
    try:
        if mode == "unlock":
            r = resources.lock_free(st, a.name, agent, a.force)
            if r in ("freed", "free"):
                print(f"{a.name}: {'freed' if r == 'freed' else 'was not held'}")
                return 0
            print(f"growth unlock: {r}", file=sys.stderr)
            return 1
        deadline = time.monotonic() + a.wait
        while True:
            ok, who = resources.lock_take(st, a.name, agent, a.lease)
            if ok:
                print(f"{a.name}: held by {agent} for {a.lease // 60} minutes (growth unlock {a.name} --agent {agent} when done)")
                return 0
            if time.monotonic() >= deadline:
                print(f"{a.name} is held by {who['holder']} until {who['until']}", file=sys.stderr)
                return 3
            time.sleep(min(1.0, max(0.05, deadline - time.monotonic())))
    except KeyError as e:
        print(f"growth {mode}: {e.args[0]}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
