#!/usr/bin/env python3
"""The independent review of a page (rule 109): start the review file from the kit's fixed checklist.

  growth review new <key> [--reviewer MODEL --builder MODEL]   # research/<key>-review-<date>.md from kit/checklists/review.md
  growth review items                                          # print the checklist ids and their text

The reviewer answers every item ("R1 pass: ...", "R1 fixed: ...", "R1 n/a: <reason>") and names a model that is not the
builder's. `growth ready` (check ev.review) needs all of it.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import KIT_DIR  # noqa: E402

CHECKLIST = KIT_DIR / "checklists" / "review.md"


def items():
    return re.findall(r"(?m)^- \*\*(R\d+) (.+?)\.\*\* (.+)$", CHECKLIST.read_text())


def template(key, reviewer="", builder="", day=""):
    out = [f"# Independent review: {key} ({day})", "", f"Reviewer: {reviewer}", f"Builder: {builder}", "",
           "Answer every item: `Rn pass: <what you saw>`, `Rn fixed: <what was wrong, what changed>` or `Rn n/a: <reason>`.", ""]
    for i, title, text in items():
        out += [f"{i} TODO ({title}): {text}", ""]
    out += ["## MUST-FIX", "", "## SHOULD-FIX", ""]
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["new", "items"])
    ap.add_argument("key", nargs="?")
    ap.add_argument("--reviewer", default="")
    ap.add_argument("--builder", default="")
    a = ap.parse_args(argv)
    if a.cmd == "items":
        for i, title, text in items():
            print(f"{i} {title}: {text}")
        return 0
    if not a.key:
        sys.exit("growth review new <key>")
    from config import PROJECT, TZ
    day = dt.datetime.now(TZ).strftime("%Y-%m-%d")
    f = PROJECT / "research" / f"{a.key}-review-{day}.md"
    if f.exists():
        sys.exit(f"{f} exists; edit it")
    f.parent.mkdir(exist_ok=True)
    f.write_text(template(a.key, a.reviewer, a.builder, day))
    print(f"wrote {f.relative_to(PROJECT)}: {len(items())} items to answer")
    return 0


if __name__ == "__main__":
    sys.exit(main())
