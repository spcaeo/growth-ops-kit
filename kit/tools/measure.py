#!/usr/bin/env python3
"""Measure a released page against the SAME baseline numbers it started from (#53, #50).

  growth measure schedule <path> --release 2026-12-01        file the day 7/14/28/56 re-checks, each on release + N days
  growth measure run <path> --key K --release 2026-12-01 [--windows 7,14,28,56] [--task T3]
                                                            clicks, impressions, position per day, before vs after, for each
                                                            window that is over; searches won and lost; the site beside it

Rules this tool keeps:
- The after window is the N days after the release day (the release day itself is left out); a window that is not over yet
  prints "not yet", never a guess. Days Google has not settled count as provisional and the verdict says "too early".
- "Before" is the frozen baseline in the page's research record (growth research baseline), the same numbers at every window,
  with its definition; without one it is the N days before the release from the tracker. Counts are compared per day, so
  windows of different length compare like with like.
- The page's own rows and the whole site's rows are separate tables. A site-wide number is never shown as the page's.
- The result is written to research/<key>-measure.json and, with --task, as a step of the task.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "page-tracker"))   # the tracker's verdict rules (insights.verdict): one set of rules
import research  # noqa: E402

WINDOWS = (7, 14, 28, 56)
RULE_NOTE = "per-day counts; a move under 20% (or under 1 click or 10 impressions a day) and a position move under 1.0 are 'no clear change'; fewer than 7 whole days, or unsettled Google days, are 'too early'"


def verdict(metric, b, a, n, prov):
    import insights
    return insights.verdict(metric, b, a, n, prov)


def per_day(tot, days):
    return {"clicks": round(tot["clicks"] / days, 2), "impressions": round(tot["impressions"] / days, 1), "position": tot["position"]}


def rows(before, after, n_before, n_after, prov):
    """The three metrics, before and after as per-day figures, with the change and the verdict."""
    b, a = per_day(before, n_before), per_day(after, n_after)
    out = []
    for m in ("clicks", "impressions", "position"):
        bv, av = b[m], a[m]
        out.append({"metric": m, "before": bv, "after": av, "change_pct": round(100 * (av - bv) / bv, 1) if bv and av is not None else None,
                    "verdict": verdict(m, bv, av, n_after, prov)})
    return out


def baseline_for(rec, rel: dt.date, which: str):
    """(totals, days, source) of the frozen baseline for the page ('totals') or the site ('site_totals'), or None."""
    b = (rec or {}).get("baseline") or {}
    w = b.get("window") or {}
    f, t = research.day(w.get("from")), research.day(w.get("to"))
    tot = b.get("totals") if which == "page" else b.get("site_totals")
    if not (f and t and tot and tot.get("impressions") is not None):
        return None
    return tot, (t - f).days + 1, f"frozen baseline {b.get('frozen_on', '')} ({f} to {t}; {b.get('definition', 'definition not recorded')})", t >= rel


def window_result(db, pk, rec, rel: dt.date, n: int, today: dt.date, which="page"):
    a_from, a_to = rel + dt.timedelta(days=1), rel + dt.timedelta(days=n)
    if today <= a_to:
        return {"n": n, "status": "not yet", "ready_on": (a_to + dt.timedelta(days=1)).isoformat()}
    path = pk if which == "page" else "*"
    after = research.tracker_window(db, path, a_from.isoformat(), a_to.isoformat())
    if not after:
        return {"n": n, "status": "no data", "note": f"the tracker has no Search Console rows for {a_from} to {a_to}"}
    prov = n - after["final_days"]
    base = baseline_for(rec, rel, which)
    note = ""
    if base and not base[3]:
        before, nb, src = base[0], base[1], base[2]
    else:
        b_from, b_to = rel - dt.timedelta(days=n), rel - dt.timedelta(days=1)
        before = research.tracker_window(db, path, b_from.isoformat(), b_to.isoformat())
        if not before:
            return {"n": n, "status": "no baseline", "note": "no frozen baseline in the research record and no tracker rows before the release"}
        nb, src = n, f"tracker rows {b_from} to {b_to}"
        if base and base[3]:
            note = "the frozen baseline ends on or after the release, so it is not a 'before'; tracker rows were used"
    return {"n": n, "status": "measured", "after_window": [a_from.isoformat(), a_to.isoformat()], "provisional_days": prov, "before_source": src,
            "note": note, "rows": rows(before, after, nb, n, prov)}


def query_moves(db, pk, rec):
    """Searches won and lost against the baseline's list (both are Google's top lists for the page, so a search can enter or
    leave the list without moving)."""
    base = {q["query"]: q for q in ((rec or {}).get("baseline") or {}).get("queries") or []}
    if not base or not Path(db).exists():
        return None
    now = {q["query"]: q for q in research.tracker_queries(db, pk)}
    return {"won": [q for k, q in now.items() if k not in base][:10], "lost": [q for k, q in base.items() if k not in now][:10],
            "moved": [{"query": k, "before": base[k]["position"], "after": q["position"]} for k, q in now.items()
                      if k in base and base[k]["position"] and q["position"] and abs(q["position"] - base[k]["position"]) >= 1.0][:10],
            "note": "top lists only: a search 'won' or 'lost' may only have entered or left the list"}


def run_all(db, pk, rec, rel, windows, today):
    out = {"page": pk, "release": rel.isoformat(), "measured_on": today.isoformat(), "rule": RULE_NOTE,
           "page_numbers": [window_result(db, pk, rec, rel, n, today, "page") for n in windows],
           "site_numbers": [window_result(db, pk, rec, rel, n, today, "site") for n in windows],
           "site_note": "the whole site's numbers beside the page's: they show a site-wide move, they are never the page's own",
           "queries": query_moves(db, pk, rec)}
    return out


def show(res):
    for title, key in (("THE PAGE'S OWN NUMBERS", "page_numbers"), ("THE WHOLE SITE (not the page)", "site_numbers")):
        print(f"== {title}")
        for w in res[key]:
            if w["status"] != "measured":
                print(f"  day {w['n']}: {w['status']} {w.get('ready_on') or w.get('note', '')}")
                continue
            print(f"  day {w['n']} ({w['after_window'][0]} to {w['after_window'][1]}, before: {w['before_source']})" + (f" [{w['provisional_days']} unsettled days]" if w["provisional_days"] else ""))
            for r in w["rows"]:
                ch = f"{r['change_pct']:+}%" if r["change_pct"] is not None else "n/a"
                print(f"    {r['metric']:<12} {r['before']} -> {r['after']} ({ch}) {r['verdict']}")
    q = res.get("queries")
    if q:
        print(f"== searches won {[x['query'] for x in q['won']]}, lost {[x['query'] for x in q['lost']]}, moved {[x['query'] for x in q['moved']]}  ({q['note']})")


def schedule(page, rel: dt.date, windows):
    out = []
    for n in windows:
        due = (rel + dt.timedelta(days=n)).isoformat()
        r = subprocess.run([sys.executable, str(HERE / "journal.py"), "add", "--page", page, "--kind", "note", "--tag", "measure", "--tag", f"day-{n}",
                            "--title", f"Measure day {n} after the {rel} release: growth measure run {page} --release {rel}", "--recheck", due],
                           capture_output=True, text=True)
        if r.returncode:
            sys.exit(r.stderr or r.stdout)
        out.append(f"{r.stdout.strip()} day {n} on {due}")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["run", "schedule"])
    ap.add_argument("path")
    ap.add_argument("--release", required=True, help="the release day, YYYY-MM-DD")
    ap.add_argument("--key", default="")
    ap.add_argument("--windows", default=",".join(map(str, WINDOWS)))
    ap.add_argument("--today", default="", help="measure as of this day (default today)")
    ap.add_argument("--task", default="")
    a = ap.parse_args(argv)
    rel = research.day(a.release)
    if not rel or a.release != rel.isoformat():
        sys.exit("--release must be a real date as YYYY-MM-DD")
    try:
        windows = tuple(sorted({int(x) for x in a.windows.split(",") if x.strip()}))
    except ValueError:
        sys.exit("--windows is a list of day counts, e.g. 7,14,28,56")
    from config import PROJECT
    import paths
    pk = paths.key(a.path)
    if a.cmd == "schedule":
        print("\n".join(schedule(pk, rel, windows)))
        return 0
    if not a.key:
        sys.exit("--key is needed (the page's research record)")
    rec = research.load(PROJECT, a.key)
    if rec is None:
        print(f"note: no research record for {a.key}; 'before' comes from the tracker's rows before the release", file=sys.stderr)
    today = research.day(a.today) or dt.date.today()
    res = run_all(PROJECT / "page-tracker" / "tracker.db", pk, rec, rel, windows, today)
    show(res)
    out = PROJECT / "research" / f"{a.key}-measure.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {out.relative_to(PROJECT)}")
    if a.task:
        done = [w for w in res["page_numbers"] if w["status"] == "measured"]
        if done:
            last = done[-1]
            line = f"day {last['n']}: " + "; ".join(f"{r['metric']} {r['before']}->{r['after']} {r['verdict']}" for r in last["rows"]) + f" (research/{a.key}-measure.json)"
            r = subprocess.run([sys.executable, str(HERE / "tasks.py"), "step", a.task, f"Measure day {last['n']} of {pk} (release {rel})", "--output", line],
                               capture_output=True, text=True)
            print(r.stderr.strip() or f"task {a.task}: step added")
    return 0


if __name__ == "__main__":
    sys.exit(main())
