#!/usr/bin/env python3
"""Held-field proposals: a field the site holds on purpose (titles, descriptions, H1s during a freeze) is left unchanged,
and what the page would say instead is stored, structured, in the page plan (research/plans/<key>.json, key "held"):
the field, its current value, the proposed value, the facts and numbers the proposal quotes, and the date.

  growth held add <key> --field description --current "..." --proposed "..." --fact "$159.90" [--fact ...]
  growth held list <key>                          # every proposal with its status
  growth held changed <key> --old "$19.90" [--new "$159.90"] [--why "review fix"]
                                                  # a review or fact check changed a fact: every open proposal quoting it is stale
  growth held rewrite <key> <id> --proposed "..." [--fact ...]   # a stale proposal rewritten: open again
  growth held apply <key> <id>                    # the freeze is over and the proposal went live
  growth held drop <key> <id> [--why "..."]

Status: open (current), stale (quotes a fact that changed or is no longer on the page: rewrite it before the freeze ends),
applied, dropped. `growth ready` prints the list; the gate check ev.held-proposals FAILs while one is stale.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def plan_path(project, key):
    return Path(project) / "research" / "plans" / f"{key}.json"


def load(path):
    try:
        d = json.loads(Path(path).read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def save(path, plan):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan, indent=1, ensure_ascii=False) + "\n")


def entries(plan):
    return [e for e in (plan.get("held") or []) if isinstance(e, dict)]


def norm(s):
    """A fact compared loosely: case, spaces and thousands commas do not matter."""
    return re.sub(r"[\s,]+", "", str(s)).lower()


def quotes(entry, text):
    """True when the proposal quotes this text, as one of its facts or inside its proposed value."""
    n = norm(text)
    return bool(n) and (any(n in norm(f) or norm(f) in n for f in entry.get("facts", []) if norm(f)) or n in norm(entry.get("proposed", "")))


def add(plan, field, current, proposed, facts, day=None):
    ids = [int(re.sub(r"\D", "", e.get("id", "")) or 0) for e in entries(plan)]
    e = {"id": f"H{max(ids, default=0) + 1}", "field": field, "current": current, "proposed": proposed, "facts": list(facts),
         "date": day or dt.date.today().isoformat(), "status": "open"}
    plan.setdefault("held", []).append(e)
    return e


def find(plan, hid):
    for e in entries(plan):
        if e.get("id") == hid:
            return e
    raise KeyError(hid)


def fact_changed(plan, old, why="a fact it quotes changed", day=None):
    """Mark every open proposal that quotes `old` stale; returns their ids."""
    hit = []
    for e in entries(plan):
        if e.get("status", "open") == "open" and quotes(e, old):
            e["status"], e["stale_reason"], e["stale_on"] = "stale", f"{why}: {old}", day or dt.date.today().isoformat()
            hit.append(e["id"])
    return hit


def rewrite(plan, hid, proposed, facts=None, day=None):
    e = find(plan, hid)
    e["proposed"] = proposed
    if facts:
        e["facts"] = list(facts)
    e["status"], e["date"] = "open", day or dt.date.today().isoformat()
    e.pop("stale_reason", None)
    e.pop("stale_on", None)
    return e


def missing_facts(entry, page_text):
    """The facts a proposal quotes that the page no longer states (the page text, compared loosely)."""
    page = norm(page_text)
    return [f for f in entry.get("facts", []) if norm(f) and norm(f) not in page]


def status_of(entry, page_text=None):
    """(status, why): the stored status, and 'stale' too when a quoted fact is no longer on the page."""
    st = entry.get("status", "open")
    if st == "open" and page_text is not None:
        gone = missing_facts(entry, page_text)
        if gone:
            return "stale", "the page no longer states: " + ", ".join(gone)
    return st, entry.get("stale_reason", "")


def lines(plan, page_text=None):
    out = []
    for e in entries(plan):
        st, why = status_of(e, page_text)
        if st in ("applied", "dropped"):
            continue
        out.append(f"{e.get('id')} {st.upper():<5} {e.get('field')}: \"{str(e.get('proposed'))[:70]}\" quotes {', '.join(e.get('facts', [])) or 'no fact'}"
                   + (f" ({why})" if why else ""))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["add", "list", "changed", "rewrite", "apply", "drop"])
    ap.add_argument("key")
    ap.add_argument("id", nargs="?")
    ap.add_argument("--field")
    ap.add_argument("--current", default="")
    ap.add_argument("--proposed")
    ap.add_argument("--fact", action="append", default=[])
    ap.add_argument("--old")
    ap.add_argument("--new")
    ap.add_argument("--why", default="")
    a = ap.parse_args(argv)
    from config import PROJECT
    f = plan_path(PROJECT, a.key)
    plan = load(f)
    if a.cmd == "list":
        ls = lines(plan)
        print("\n".join(ls) if ls else "no open held-field proposals")
        return 0
    if a.cmd == "add":
        if not (a.field and a.proposed):
            sys.exit("--field and --proposed are required")
        e = add(plan, a.field, a.current, a.proposed, a.fact)
        print(f"{e['id']} added: {a.field} ({len(a.fact)} facts quoted)")
    elif a.cmd == "changed":
        if not a.old:
            sys.exit("--old <the fact that changed> is required")
        hit = fact_changed(plan, a.old, a.why or "a fact it quotes changed")
        print(f"marked stale: {', '.join(hit) if hit else 'none quote it'}" + (f"  (new value: {a.new})" if a.new else ""))
    else:
        if not a.id:
            sys.exit(f"growth held {a.cmd} <key> <id>")
        try:
            if a.cmd == "rewrite":
                if not a.proposed:
                    sys.exit("--proposed is required")
                rewrite(plan, a.id, a.proposed, a.fact)
            else:
                e = find(plan, a.id)
                e["status"] = "applied" if a.cmd == "apply" else "dropped"
                if a.why:
                    e["note"] = a.why
        except KeyError:
            sys.exit(f"no proposal {a.id} in {f}")
        print(f"{a.id}: {a.cmd} done")
    save(f, plan)
    return 0


if __name__ == "__main__":
    sys.exit(main())
