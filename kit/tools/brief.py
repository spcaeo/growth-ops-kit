#!/usr/bin/env python3
"""Build a helper's brief from the project's own files, so no rule, step or owner instruction is left out
(from a real project: "are your agents following the guide, SOP, background data, all of it 100%, not a single item
missed?"). A hand-written brief forgets things; this one is generated.

  growth brief <path> --type money|core|hub|post --task T14 [--playbook money-page] [--since I-75]
         [--job "what this helper does"] [--out research/briefs/<key>.md]

The brief holds, in order:
  1. The job, the page, the task id, the one preview address, the agent rules (cap, browsers, cleanup, commits).
  2. Files to read in full before any work (FLOW, OWNER-RULES, BRAND, PAGE-RULEBOOK at its version, the playbook,
     the page's research files).
  3. Every playbook step, copied, with its status in the task (so nothing is skipped silently).
  4. Every rule in scope for the page type, with its code checks (the gate decides them).
  5. Every owner instruction since --since (default: the task's start), word for word.
  6. The finish list: what the report must contain, and that the lead re-runs the gate before trusting it.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import BOOK, CFG, DOCS, PROJECT, REGISTRY  # noqa: E402

def agent_rules():
    ci = CFG.get("commit_identity") or {}
    name, email = ci.get("name") or CFG.get("committer_name"), ci.get("email") or CFG.get("committer_email")
    ident = (f'site commits as {name} <{email}>' if name and email else
             "commit with the repo's own identity (growth.json commit_identity: name and email)")
    return f"""- At most {CFG.get("agent_cap", 4)} agents in the project, lead included; you never start sub-agents.
- One headless browser at a time; close every browser and server you start; never browse the real site
  ({CFG.get("site_url", "growth.json site_url")}) with a browser (a visit counts in analytics; plain curl is fine).
- Never push or merge. Commit by path (`git commit -- <paths>`), never `git add -A`; {ident}; subject under
  120 characters; end with the attribution line your setup requires.
- Touch only the files your brief gives you; if another file must change, tell the lead the exact change.
- Use what is shared (byline, call dialog, schema graph, link cards); never build a second copy.
- Never invent a fact about a person, customer, price or result. Only what BRAND.md allows or the owner confirmed.
- A rework deletes what it replaced in the same commit (rule 124a). Clean up and end with a "Cleaned: ..." line.
- Scratch files live only in your own folder, <scratchpad>/<your agent name>/. Delete that folder and nothing else,
  never by wildcard in a shared folder (a reviewer's *.py delete once removed another helper's scripts).
- Pre-flight came first (rule 0a): work from research/<key>-checkpoints.md, tick each box with its evidence, and run
  the gate after EVERY commit; fix its FAILs before the next one, never at the end.
- Write reports in simple English: what happened and what it means first."""


FINISH = """Your report is not done until it has:
- the page link on the one preview address and the commits;
- the site's own checks (type check, unit tests), contrast_check at 1366 and 390, and the full gate run AFTER your last commit, with every FAIL either
  fixed or named as one of the known site-wide items with its reason;
- every playbook step above marked done in the task (`docs/tasks.json`), or named as waiting on the owner or the lead;
- each owner instruction above that touches your page, and where the page follows it;
- the owner questions, each with its safe default;
- a "Cleaned: ..." line.
The lead re-runs the gate and reads the task steps before telling the owner anything you report."""


def steps_log_rows(since):
    rows = []
    for line in (DOCS / "steps-log.md").read_text().splitlines():
        m = re.match(r"\| (I-(\d+)) \| ([^|]+) \| (.+?) \| (.+?) \|", line)
        if m and int(m.group(2)) >= since:
            rows.append(f"- {m.group(1)} ({m.group(3).strip()}): {m.group(4).strip()}  -> {m.group(5).strip()}")
    return rows


def playbook_steps(name):
    pb = BOOK / "playbooks" / f"{name}.md"
    if not pb.exists():
        return [f"(no playbook {pb.name})"], pb
    text = pb.read_text()
    m = re.search(r"(?ms)^## Part 2\..*?(?=^---|\Z)", text) or re.search(r"(?ms)^## .*?(?=^---|\Z)", text)
    return [l for l in (m.group(0) if m else text).splitlines() if re.match(r"^\s*(\d+[a-z]?\.|-) ", l)], pb


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path")
    ap.add_argument("--type", required=True, choices=["money", "core", "hub", "post"])
    ap.add_argument("--task", required=True)
    ap.add_argument("--playbook", default="money-page")
    ap.add_argument("--since", default="", help="first steps-log row to include, e.g. I-75 (default: all of today)")
    ap.add_argument("--job", default="")
    ap.add_argument("--key", default="")
    ap.add_argument("--out")
    a = ap.parse_args()

    tasks = json.loads((DOCS / "tasks.json").read_text())
    task = next((t for t in tasks["tasks"] if t["id"] == a.task), None)
    if not task:
        sys.exit(f"no task {a.task} in docs/tasks.json")
    reg = json.loads(REGISTRY.read_text())
    since = int(a.since.split("-")[1]) if a.since else 1
    key = a.key or a.path.strip("/").split("/")[-1].replace("-software", "")

    out = [f"# Brief: {a.path} ({a.type} page), task {a.task}", ""]
    out += ["## 1. The job", "", a.job or task["title"], "",
            f"Owner's words: {task.get('owner_words', '')}", "",
            f"Preview address the owner sees: {CFG.get('preview_url', '(growth.json preview_url)')}{a.path}. Your own "
            "working port is never sent to the owner.", "", agent_rules(), ""]
    research = sorted(p.relative_to(PROJECT).as_posix() for p in (PROJECT / "research").rglob(f"*{key}*") if p.is_file() and not p.name.endswith("-checkpoints.md")
                      and p.suffix in (".md", ".json"))
    pb_steps, pb = playbook_steps(a.playbook)
    out += ["## 2. Read in full before any work", "",
            f"- the book: {BOOK / '01-flow.md'}, {BOOK / '02-owner-rules.md'}; the project's own BRAND.md and OWNER-RULES.md",
            f"- the book: {BOOK / '03-page-rulebook.md'} (rule set version {reg.get('rulebook_version')})",
            f"- the book: {pb}"]
    out += [f"- project: {r}" for r in research]
    cp = PROJECT / "research" / f"{key}-checkpoints.md"
    out += [f"- project: research/{cp.name} (the checkpoint list from growth preflight; "
            + ("tick every box)" if cp.exists() else "MISSING: the lead runs growth preflight first)")] + [""]
    out += ["## 3. Every playbook step (none skipped; raise a step with the lead before skipping it)", ""] + pb_steps + [""]
    out += ["Task steps so far:"] + [f"- {s['n']}. [{s['status']}] {s.get('what', '')[:150]}" for s in task.get("steps", [])] + [""]
    scoped = [r for r in reg["rules"] if a.type in r.get("scope", [])]
    out += [f"## 4. The {len(scoped)} rules for a {a.type} page (the gate checks the coded ones)", ""]
    out += [f"- {r['id']}: {r['rule']}" + (f"  [{', '.join(r.get('checks', []))}]" if r.get("checks") else "  [judgment]")
            for r in scoped] + [""]
    rows = steps_log_rows(since)
    out += [f"## 5. The owner's instructions (docs/steps-log.md, {len(rows)} rows, newest last)", ""] + rows + [""]
    out += ["## 6. Finish", "", FINISH, "",
            f"Gate: `growth gate page {a.path} --url <local URL> --repo <worktree> --type {a.type} --key {key} --no-link-status`"]
    text = "\n".join(out) + "\n"
    if a.out:
        p = PROJECT / a.out
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        shown = p.relative_to(PROJECT) if p.resolve().is_relative_to(PROJECT.resolve()) else p
        print(f"wrote {shown}: {len(scoped)} rules, {len(pb_steps)} playbook lines, {len(rows)} owner instructions")
    else:
        print(text)


if __name__ == "__main__":
    main()
