#!/usr/bin/env python3
"""Pull work from the board (kit 3.0, micro kit core): an agent or the machine runner takes the next job it can do.

  growth work next --kit K --agent NAME [--runner R] [--lease 1800] [--wait SECONDS] [--json]
        claim one job (a lease; exit 0 and the job printed, exit 3 when there is nothing to claim now). --wait keeps
        asking for up to that many seconds. --runner narrows who the job is for: machine, owner, agent:<role> (research,
        plan, build, review, lead) or agent (any worker role); with none, the jobs of the owner and of the lead (agent:lead) are
        never given out: ask for them by name.
  growth work beat <job> [--agent NAME] [--lease S]        renew the lease (a job whose lease runs out goes back to the queue)
  growth work done <job> --proof "..." [--agent NAME]      finish it; the proof must name something checkable (a file, a commit,
        a journal id, a command with its output line, an address); a job linked to a task step ticks that step
  growth work fail <job> --why "..." [--agent NAME]        give it back (tried 3 times: failed for good)
  growth work list [--kit K] [--status S] [--page P]       the jobs

The board itself (pages, stages, times): growth board. Pools and locks: growth board resources, growth lock.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import board  # noqa: E402
import kits  # noqa: E402
import store  # noqa: E402


def describe(j: dict) -> str:
    lines = [f"job {j['id']}: {j['kind']}" + (f" for {j['page']} ({j['page_type']}, key {j['page_key']})" if j["page"] else " (no page)"),
             f"  kit {j['kit']}, runs {j['way']}, for {j['runner']}",
             f"  what: {kits.jobs().get(j['kind'], {}).get('what', '')}"]
    if j["needs_info"]:
        lines.append("  needs (all done): " + ", ".join(f"{n['id']} {n['kind']}" for n in j["needs_info"]))
    res = j["resource"]
    if res == "port":
        lines.append(f"  resource: port {j['port']} (serve your build on it; it is yours until the job ends)")
    elif res == "google":
        lines.append("  resource: google (run `growth pace google` before EVERY Google search; on a robot check: `growth pace google --robot`)")
    elif res != "none":
        lines.append(f"  resource: {res}" + (f" (slot {j['slot']})" if j["slot"] else " (held for you until the job ends)"))
    lines.append(f"  lease until {j['lease_until']} (renew: growth work beat {j['id']}; finish: growth work done {j['id']} --proof \"...\")")
    if j["task"]:
        lines.append(f"  linked to task {j['task']} step {j['step']}: ticked with your proof when you finish")
    if j["why"]:
        lines.append(f"  last note: {j['why']}")
    return "\n".join(lines)


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="growth work", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    n_ = sub.add_parser("next")
    n_.add_argument("--kit"); n_.add_argument("--runner"); n_.add_argument("--agent")
    n_.add_argument("--lease", type=int, default=board.DEFAULT_LEASE_S)
    n_.add_argument("--wait", type=float, default=0); n_.add_argument("--json", action="store_true")
    b_ = sub.add_parser("beat"); b_.add_argument("job"); b_.add_argument("--agent"); b_.add_argument("--lease", type=int)
    d_ = sub.add_parser("done"); d_.add_argument("job"); d_.add_argument("--proof", required=True); d_.add_argument("--agent")
    f_ = sub.add_parser("fail"); f_.add_argument("job"); f_.add_argument("--why", required=True); f_.add_argument("--agent")
    l_ = sub.add_parser("list"); l_.add_argument("--kit"); l_.add_argument("--status"); l_.add_argument("--page")
    a = ap.parse_args(argv)
    try:
        return _run(a)
    except (board.BoardError, KeyError) as e:
        print(f"growth work: {e.args[0] if e.args else e}", file=sys.stderr)
        return 1


def _run(a) -> int:
    st = store.open()
    agent = getattr(a, "agent", None) or store.actor()
    if a.cmd == "next":
        deadline = time.monotonic() + a.wait
        while True:
            j = board.claim(agent, a.kit, a.runner, a.lease, st=st)
            if j:
                print(json.dumps(j, default=str) if a.json else describe(j))
                return 0
            if time.monotonic() >= deadline:
                print("nothing to claim now" + (f" for kit {a.kit}" if a.kit else ""), file=sys.stderr)
                return 3
            time.sleep(min(2.0, max(0.05, deadline - time.monotonic())))
    if a.cmd == "beat":
        j = board.renew(a.job, a.agent, a.lease, st=st)
        print(f"job {j['id']}: lease renewed until {j['lease_until']}")
    elif a.cmd == "done":
        j = board.done(a.job, a.agent, a.proof, st=st)
        print(f"job {j['id']} ({j['kind']}) done" + (f"; page {j['page']} is now at {st.q1('SELECT stage FROM pages WHERE path=?', (j['page'],))['stage']}" if j["page"] else ""))
        if j["ready"]:
            print("now ready: " + ", ".join(str(i) for i in j["ready"]))
    elif a.cmd == "fail":
        j = board.fail(a.job, a.agent, a.why, st=st)
        print(f"job {j['id']} ({j['kind']}): {j['status']} (attempt {j['attempts']} of {board.MAX_ATTEMPTS})")
    elif a.cmd == "list":
        board._table([(j["id"], j["kind"], j["status"], j["page"] or "-", j["runner"], j["holder"] or "-") for j in board.jobs_view(a.kit, a.status, a.page, st=st)],
                     ["job", "kind", "status", "page", "runner", "holder"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
