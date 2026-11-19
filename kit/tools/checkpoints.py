#!/usr/bin/env python3
"""The page's checkpoints file (research/<key>-checkpoints.md): write it without losing what the builder ticked, and read
the manual half back.

  growth checkpoints <path-to-checkpoints-file>     # print the manual checks still open (exit 1 while any is)

Two kinds of item:
  generated   - [ ] `ev.review` (rule 109): ...      one gate check; its proof is the gate run, so a tick is optional
  manual      anything else that is a checkbox: the project's own rules (growth.json "checkpoints_extra" names a file
              with one rule per bullet) and any line the builder adds. No gate check runs them, so each one must be
              ticked with its proof after " -- ":   - [x] rule 530: click test -- J0028, 53/53 clicked
`growth ready` fails while a manual item is unticked or ticked with no proof. `growth preflight` merges into the file
instead of rewriting it: ticks, proofs, hand-added items and project sections stay, new generated items are added and a
generated item that left the scope moves to "Removed from scope" (kept for the record, never counted).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

GEN_HEADS = ("1. Before the build", "2. After EVERY fold", "3. Before READY", "4. After publishing")
MANUAL_HEAD = "5. Manual checks"
REMOVED_HEAD = "Removed from scope"
ITEM = re.compile(r"^- \[([ xX])\] (.*)$")
GEN_ITEM = re.compile(r"^`([\w.\-]+)`")
SEP = re.compile(r"\s(?:--|—)\s")
WEAK = {"", "proof", "todo", "tbd", "done", "ok", "..."}


def split_proof(text):
    """(rule text, proof) of an item: the proof follows the first ' -- '."""
    m = SEP.search(text)
    return (text[:m.start()].strip(), text[m.end():].strip()) if m else (text.strip(), "")


def sections(text):
    """[(heading or None, [lines])]: the lines before the first '## ' have heading None."""
    out = [(None, [])]
    for ln in text.splitlines():
        if ln.startswith("## "):
            out.append((ln[3:].strip(), []))
        else:
            out[-1][1].append(ln)
    return out


def kind_of(heading):
    h = re.sub(r"\s*\(\d+\)\s*$", "", heading or "")
    if h.startswith(GEN_HEADS):
        return "generated"
    if h.startswith(MANUAL_HEAD):
        return "manual"
    if h.startswith(REMOVED_HEAD):
        return "removed"
    return "other"


def extra_items(path):
    """The project's own rules: one per bullet of the checkpoints_extra file (a checkbox or its proof is ignored)."""
    out = []
    for ln in Path(path).read_text().splitlines():
        m = re.match(r"^\s*[-*]\s+(?:\[[ xX]\]\s+)?(.+)$", ln)
        if m and split_proof(m.group(1))[0]:
            out.append(split_proof(m.group(1))[0])
    return out


def merge(old, gen, extra, header, today):
    """The new file text. gen: [(heading, [(cid, line_without_tick)])]; extra: rule texts; old: the previous file text."""
    secs = sections(old) if old else [(None, [])]
    old_gen, old_manual, removed, keep_other, added = {}, {}, [], [], {}
    for head, lines in secs[1:]:
        k = kind_of(head)
        for ln in lines:
            m = ITEM.match(ln)
            if k in ("generated", "manual") and m:
                g = GEN_ITEM.match(m.group(2))
                if g and k == "generated":
                    old_gen[g.group(1)] = (m.group(1), split_proof(m.group(2))[1])
                else:
                    (old_manual if k == "manual" else added.setdefault(head, {}))[split_proof(m.group(2))[0]] = ln
            elif k == "removed" and ln.startswith("- "):
                removed.append(ln)
        if k == "other":
            keep_other.append((head, lines))
    out = [header, ""]
    live = set()
    for head, items in gen:
        out += [f"## {head} ({len(items)})", ""]
        for cid, line in items:
            live.add(cid)
            tick, proof = old_gen.get(cid, (" ", ""))
            out.append(f"- [{tick}] {line}" + (f" -- {proof}" if proof else ""))
        base = re.sub(r"\s*\(\d+\)\s*$", "", head)
        for text, ln in next((v for k, v in added.items() if re.sub(r"\s*\(\d+\)\s*$", "", k) == base), {}).items():
            out.append(ln)                       # a manual line the builder added inside a generated section
        out.append("")
    for cid, (tick, proof) in sorted(old_gen.items()):
        if cid not in live:
            removed.append(f"- `{cid}` left the scope on {today}" + (f" (it was ticked: {proof})" if tick != " " and proof else ""))
    manual = dict(old_manual)
    for t in extra:
        manual.setdefault(t, f"- [ ] {t}")
    if manual:
        out += [f"## {MANUAL_HEAD} ({len(manual)}): tick each with its proof after ' -- ', e.g. '- [x] rule 530: click test -- J0028, 53/53'", ""]
        out += list(manual.values()) + [""]
    for head, lines in keep_other:
        out += [f"## {head}"] + lines
        if lines and lines[-1].strip():
            out.append("")
    if removed:
        out += [f"## {REMOVED_HEAD}", ""] + list(dict.fromkeys(removed)) + [""]
    return "\n".join(out).rstrip("\n") + "\n"


def manual_status(text):
    """(total, done, problems): every manual checkbox item must be ticked with a proof."""
    total = done = 0
    probs = []
    for head, lines in sections(text)[1:]:
        k = kind_of(head)
        if k == "removed":
            continue
        for ln in lines:
            m = ITEM.match(ln)
            if not m or (k == "generated" and GEN_ITEM.match(m.group(2))):
                continue
            total += 1
            rule, proof = split_proof(m.group(2))
            if m.group(1) == " ":
                probs.append(f"unticked: {rule[:140]}")
            elif proof.lower() in WEAK or len(proof) < 3:
                probs.append(f"ticked with no proof (add ' -- <what you saw>'): {rule[:120]}")
            else:
                done += 1
    return total, done, probs


def main():
    if len(sys.argv) != 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    total, done, probs = manual_status(Path(sys.argv[1]).read_text())
    print(f"manual checks {done}/{total}")
    for p in probs:
        print("  " + p)
    return 1 if probs else 0


if __name__ == "__main__":
    sys.exit(main())
