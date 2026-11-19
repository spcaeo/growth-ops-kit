#!/usr/bin/env python3
"""Keep rules/registry.json in step with the code: each entry's "files" (where its checks live, relative to the kit) and
"needs" (what they read: live = the served page, project = the project folder, nextjs = the site's code; a list when an
entry's checks differ). The check's own @check(..., needs=...) is the source of truth.

  growth registry_sync          # rewrite the registry
  growth registry_sync --check  # exit 1 when the registry is out of step (the tests run this)

Each numbered rule's "rule" text is copied from the bold heading of the rule in book/03-page-rulebook.md, so the registry
(and the gate's messages) can never disagree with the book.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import REGISTRY, RULEBOOK  # noqa: E402
from gatelib import CHECKS, registry  # noqa: E402


def expected(entry):
    ids = registry.checks_of(entry)
    files, needs = [], []
    for c in ids:
        ch = CHECKS.get(c)
        if not ch:
            continue
        files.append(ch.where)
        needs.append(ch.needs)
    for extra in entry.get("files", []):
        if extra.startswith("tools/") and not extra.startswith("tools/gatelib/") and extra not in files:
            files.append(extra)                      # a helper tool named by hand (preflight.py, link_map.py ...)
    n = sorted(set(needs))
    return sorted(dict.fromkeys(files)), (n[0] if len(n) == 1 else n) if n else None


def rulebook_version():
    """The version in the book's frontmatter (book/03-page-rulebook.md), when the book is there."""
    import re
    m = re.search(r"(?m)^version:\s*(\S+)", RULEBOOK.read_text()) if RULEBOOK.exists() else None
    return m.group(1) if m else None


def write(reg):
    """One entry per line, as the file has always been laid out (readable diffs)."""
    head = {k: v for k, v in reg.items() if k != "rules"}
    out = ["{"] + [f" {json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}," for k, v in head.items()]
    out.append(' "rules": [')
    out.append(",\n".join("  " + json.dumps(e, ensure_ascii=False) for e in reg["rules"]))
    out.append(" ]\n}")
    REGISTRY.write_text("\n".join(out) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    reg = registry.load()
    bad = []
    ver = rulebook_version()
    if ver and reg.get("rulebook_version") != ver:
        bad.append("rulebook_version")
        reg["rulebook_version"] = ver
    heads = registry.rule_headings() if RULEBOOK.exists() else {}
    for e in reg["rules"]:
        h = heads.get(e["id"])                      # the registry's rule text is the book's heading, never a second copy
        if h and e.get("rule", "").rstrip(".:,;") != h:
            bad.append(e["id"])
            e["rule"] = h
        files, needs = expected(e)
        if needs is None:
            continue
        if e.get("files") != files or e.get("needs") != needs:
            bad.append(e["id"])
            e["files"], e["needs"] = files, needs
    if a.check:
        if bad:
            print(f"registry out of step for: {', '.join(bad)}; run growth registry_sync")
            return 1
        print(f"registry in step ({len(reg['rules'])} entries)")
        return 0
    write(reg)
    print(f"registry rewritten: {len(bad)} entries changed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
