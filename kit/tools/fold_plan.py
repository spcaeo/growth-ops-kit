#!/usr/bin/env python3
"""Fold-by-fold detail plan for a page (rule 36h). From a real project: "pay attention to the smallest details for each
page element and each fold ... a proper plan when it starts to optimize any page".

  growth fold_plan init  <path> --url <local URL> --key <key>   # skeleton from the page's folds
  growth fold_plan check <path> --key <key> [--url <local URL>] # exit 1 on any unanswered field
  growth fold_plan show  <path> --key <key>                     # the plan as a Markdown table

For a page being rebuilt, list the planned folds by hand (same names as each section's data-fold).
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gatelib.c_plan import FOLD_FIELDS, SHARED, SHARED_FIELDS, load, page_folds, problems  # noqa: E402

from config import PROJECT  # noqa: E402


def fetch(url):
    with urllib.request.urlopen(url, timeout=20) as r:  # local dev server only
        return r.read().decode("utf-8", "replace")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["init", "check", "show"])
    ap.add_argument("path")
    ap.add_argument("--key", required=True)
    ap.add_argument("--url")
    # accepted like every page command, so one --repo flag works across a lane; the plan lives in the project, not the site
    ap.add_argument("--repo", default="", help="the site checkout (accepted for a uniform command line; not needed here)")
    a = ap.parse_args()
    f = PROJECT / "research" / "plans" / f"{a.key}.json"
    folds = page_folds(fetch(a.url)) if a.url else []
    if a.cmd == "init":
        old = load(f) if f.exists() else None
        if f.exists() and (old or {}).get("folds"):
            sys.exit(f"{f} exists; edit it instead")
        plan = {"page": a.path, "goal": "", "folds": [dict(fold=n, **{k: "" for k in FOLD_FIELDS}) for n in folds],
                "shared": {s: {k: "" for k in SHARED_FIELDS} for s in SHARED},
                "_fields": FOLD_FIELDS, "_shared_fields": SHARED_FIELDS}
        for k in ("goal", "target_searches", "research_paa"):   # what `growth research plan` wrote from the research record stays
            if (old or {}).get(k):
                plan[k] = old[k]
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(plan, indent=1, ensure_ascii=False) + "\n")
        print(f"wrote {f.relative_to(PROJECT)}: {len(folds)} folds x {len(FOLD_FIELDS)} fields, {len(SHARED)} shared elements")
        return
    plan = load(f)
    if a.cmd == "show":
        if not plan:
            sys.exit(f"no plan at {f}")
        print(f"# Fold plan: {plan.get('page')}\n\nGoal: {plan.get('goal')}\n")
        for fd in plan.get("folds", []):
            print(f"## {fd.get('fold')}\n")
            for k in FOLD_FIELDS:
                print(f"- **{k}:** {fd.get(k, '')}")
            print()
        return
    probs = problems(plan, folds)
    for p in probs:
        print("MISSING ", p)
    print(f"{len(probs)} unanswered" if probs else "plan complete")
    sys.exit(1 if probs else 0)


if __name__ == "__main__":
    main()
