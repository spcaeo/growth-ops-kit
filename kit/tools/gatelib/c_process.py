"""Process rules: setup, logs, tasks, commits, main untouched, the rulebook kept current
(rules 0, 105, 114, 118, 126, 128, 129, 161 and the checkable OWNER-RULES rows)."""
from __future__ import annotations

import json
import datetime as dt
import re
import sys

from .core import Missing, Skip, check, run
from config import BOOK, RULEBOOK

P = ("process",)


def site_repo(ctx):
    if not ctx.cfg.get("site_repo"):
        raise Missing("growth.json site_repo", "set site_repo in growth.json (book/01-flow.md A3)")
    r = (ctx.project / ctx.cfg["site_repo"]).resolve()
    if not (r / ".git").exists():
        raise Missing(f"site repo {r}", "git clone the site repo (book/01-flow.md A3)")
    return r


def worktrees(ctx):
    out = ctx.git("worktree", "list", "--porcelain", repo=site_repo(ctx))
    wts, cur = [], {}
    for line in out.splitlines() + [""]:
        if not line.strip():
            if cur:
                wts.append(cur)
            cur = {}
        elif " " in line:
            k, v = line.split(" ", 1)
            cur[k] = v
    return wts


@check("proc.doctor", "OR-setup", P, "growth doctor says every setup step is done", needs="project")
def doctor(ctx):
    code, out = run([sys.executable, str(ctx.kit_dir / "tools" / "doctor.py")], timeout=120)
    m = re.search(r"(\d+)/(\d+) setup steps done", out)
    if not m:
        raise Missing("doctor.py result", f"run growth doctor ({out.strip()[-120:]})")
    ctx.verdict([] if m.group(1) == m.group(2) else [f"{m.group(1)}/{m.group(2)} setup steps"], f"doctor {m.group(1)}/{m.group(2)}",
                "fix the TODO/FAIL lines of growth doctor (book/02-owner-rules.md 'Setup before page work')")


@check("proc.owner-messages", "OR-unlogged", P, "every owner message is in docs/steps-log.md (growth owner_messages check)", needs="project")
def owner_messages(ctx):
    tool = ctx.need_file(ctx.kit_dir / "tools" / "owner_messages.py", "restore growth owner_messages")
    code, out = run([sys.executable, str(tool), "check"], timeout=120)
    lines = [l for l in out.strip().splitlines() if l.strip()]
    summary = next((l for l in lines if re.search(r"\d+ owner messages;", l)), "")
    if code == 3 or any(l.startswith("NO TRANSCRIPTS") for l in lines):
        ctx.warn(next((l[len("NO TRANSCRIPTS "):] for l in lines if l.startswith("NO TRANSCRIPTS")), "no agent transcripts found, so no owner message was checked"),
                 "start the agent from the project folder so its transcripts are saved, or set growth.json transcripts_dir (book/02-owner-rules.md: log every owner message)")
    elif code == 0 and summary:
        ctx.ok(summary)
    elif code == 0:
        ctx.fail(f"owner_messages check printed no result: {(lines[-1] if lines else 'no output')[:120]}", "run growth owner_messages check and fix what it says")
    else:
        ctx.fail(summary or (lines[-1] if lines else "no output"), "log each missing owner message in docs/steps-log.md (book/01-flow.md stage F)")


def table_rows(text, header_start):
    i = text.find(header_start)
    if i < 0:
        return None
    rows = []
    for line in text[i:].splitlines()[2:]:
        if not line.startswith("|"):
            break
        rows.append([c.strip() for c in line.strip().strip("|").split("|")])
    return rows


@check("proc.steps-log", "OR-log", P, "the steps log keeps its format: numbered rows (I-1, I-2 ...), dates, every instruction says where it now lives", needs="project")
def steps_log(ctx):
    t = ctx.need_file(ctx.need_docs() / "steps-log.md", "create docs/steps-log.md").read_text()
    probs = []
    rows = []
    for line in t.splitlines():
        m = re.match(r"^\|\s*(I-(\d+))\s*\|", line)
        if m:
            rows.append((int(m.group(2)), [c.strip() for c in line.strip().strip("|").split("|")]))
    for n, r in rows:
        if len(r) != 5:
            probs.append(f"row {r[0]} has {len(r)} columns (5 needed: ID, date, what the owner said, what was done, where)")
        elif not re.fullmatch(r"\d{4}-\d\d-\d\d", r[1]) or not r[4]:
            probs.append(f"{r[0]} lacks a date (YYYY-MM-DD) or a 'Where'")
        # an instruction still "in progress" a day later was done and never closed, or forgotten
        elif re.search(r"(?i)in progress", r[3] + " " + r[4]) and r[1] < (dt.date.today() - dt.timedelta(days=1)).isoformat():
            probs.append(f"{r[0]} ({r[1]}) is still 'in progress': finish it or close it with its proof")
    nums = [n for n, _ in rows]
    gaps = sorted(set(range(1, max(nums) + 1)) - set(nums)) if nums else []
    if gaps:
        probs.append(f"instruction numbers missing: I-{gaps[0]}" + (f" and {len(gaps) - 1} more" if len(gaps) > 1 else ""))
    if len(nums) != len(set(nums)):
        probs.append("an instruction number is used twice")
    ctx.verdict(probs, f"{len(rows)} instructions, all well formed", "fix the rows as listed in docs/steps-log.md (flow stage F)")


@check("proc.tasks", "0", P, "tasks.json: steps numbered 1..n with a status and time; nothing skipped; at least one task", needs="project")
def tasks(ctx):
    t = ctx.need_tasks("growth tasks")
    probs = []
    ids = [x["id"] for x in t["tasks"]]
    if len(ids) != len(set(ids)):
        probs.append("duplicate task ids")
    if not ids:
        probs.append("no task yet (growth tasks add ...)")
    for x in t["tasks"]:
        ns = [s.get("n") for s in x.get("steps", [])]
        if ns != list(range(1, len(ns) + 1)):
            probs.append(f"{x['id']} steps not numbered 1..{len(ns)}")
        for s in x.get("steps", []):
            if s.get("status") not in ("done", "doing", "todo", "waiting-owner", "blocked"):
                probs.append(f"{x['id']} step {s.get('n')} status '{s.get('status')}'")
            if not s.get("at"):
                probs.append(f"{x['id']} step {s.get('n')} has no time")
        if x.get("status") == "done" and not x.get("finished"):
            probs.append(f"{x['id']} done but no finished time")
    ctx.verdict(probs, f"{len(ids)} tasks, steps in order", "growth tasks step ... keeps the format (rule 0)")


@check("proc.rulebook-current", "128", P, "the rulebook's version, header line and newest change-log row agree; every rule is in the registry", needs="project")
def rulebook(ctx):
    t = ctx.need_file(RULEBOOK, "restore PAGE-RULEBOOK.md").read_text()
    v = re.search(r"(?m)^version: (\S+)", t)
    head = re.search(r"\*\*Version (\S+)", t)
    rows = re.findall(r"(?m)^\| \d{4}-\d\d-\d\d \| (\d+\.\d+\.\d+) \|", t)
    probs = []
    if not v or not head or v.group(1) != head.group(1):
        probs.append("frontmatter and header versions differ")
    if v and (not rows or max(rows, key=lambda s: tuple(map(int, s.split(".")))) != v.group(1)):
        probs.append(f"no change-log row for {v.group(1)}")
    from . import registry
    missing = registry.unregistered()
    if missing:
        probs.append(f"rules without a registry entry: {missing[:8]}")
    ctx.verdict(probs, f"rulebook {v.group(1) if v else '?'}: versions agree, every rule registered", "bump the version, add the change-log row, add the rule to rules/registry.json (rule 128)")


@check("proc.dropped-reasons", "161", P, "every dropped-rules row of a project's own rulebook or owner rules gives a reason (skipped when the project keeps no such table)", needs="project")
def dropped(ctx):
    t, where = "", ""
    for name in ("PAGE-RULEBOOK.md", "OWNER-RULES.md"):   # a project may keep its own adapted rulebook or list the rules it drops in its owner rules
        f = ctx.project / name
        if f.exists() and re.search(r"(?m)^## Dropped rules", f.read_text()):
            t, where = f.read_text(), name
            break
    sec = re.split(r"(?m)^## Dropped rules[^\n]*\n", t, maxsplit=1)
    if len(sec) < 2:
        raise Skip("this project drops no rules (no '## Dropped rules' section in PAGE-RULEBOOK.md or OWNER-RULES.md)")
    body = re.split(r"(?m)^## ", sec[1], maxsplit=1)[0]
    rows = [l for l in body.splitlines() if l.startswith("| ") and not l.startswith("| Rule") and not l.startswith("| ---")]
    bad = [r[:40] for r in rows if re.search(r"(?i)not in (our|the) notes", r) or len(r.split("|")) < 4 or not r.split("|")[2].strip()]
    ctx.verdict(bad, f"{len(rows)} dropped rows in {where}, each with a fit reason", "give each dropped row a fit reason (rule 161)")


@check("proc.owner-actions", "OR-actions", P, "every owner-action journal entry is listed in journal/OWNER-ACTIONS.md", needs="project")
def owner_actions(ctx):
    acts = [e for e in ctx.journal() if e.get("kind") == "owner-action"]
    if not acts:
        ctx.ok("the journal holds no owner action yet, so nothing needs listing")
        return
    f = ctx.need_file(ctx.project / "journal" / "OWNER-ACTIONS.md", "growth journal render").read_text()
    miss = [e["id"] for e in acts if e["id"] not in f]
    ctx.verdict(miss, f"{len(acts)} owner actions, all listed", "growth journal render (book/02-owner-rules.md 'Owner action items')")


@check("proc.remote-private", "OR-sharing", P, "the project folder's remote, if it has one, stays private until the owner says public", needs="project")
def remote_private(ctx):
    code, out = run(["git", "-C", str(ctx.project), "remote", "-v"])
    if code != 0:
        raise Skip("the project folder is not a git repository (growth.json is read from it; `git init` it and add a private remote, book/foundation.md)")
    remotes = sorted({" ".join(l.split()[:2]) for l in out.splitlines() if l.strip()})
    if remotes:
        ctx.warn(f"the project folder has a remote ({'; '.join(remotes)}): it must stay private until the owner says public",
                 "check the remote's visibility on the host; make it public only on the owner's yes (book/02-owner-rules.md 'Keep the remote private')")
    else:
        ctx.ok("no remote yet: the work lives on this machine only (the foundation checklist asks for a private remote and backups)")


@check("proc.plain-report", "129", P, "the steps log is written in short sentences (average 25 words or fewer)", needs="project")
def plain(ctx):
    t = ctx.need_file(ctx.need_docs() / "steps-log.md", "create docs/steps-log.md").read_text()
    rows = (table_rows(t, "| # | Date | Instruction") or []) + (table_rows(t, "| # | Date | Step") or [])
    text = " ".join(r[3] for r in rows if len(r) >= 4)
    sents = [s for s in re.split(r"(?<=[.!?;:])\s+", text) if s.strip()]
    avg = sum(len(s.split()) for s in sents) / max(len(sents), 1)
    long_ = [s[:50] for s in sents if len(s.split()) > 45]
    probs = ([f"average sentence {avg:.0f} words"] if avg > 25 else []) + [f"{len(long_)} sentence(s) over 45 words"] * bool(long_)
    ctx.verdict(probs, f"average sentence {avg:.0f} words", "write short sentences, answer first (rule 129)")


@check("proc.workflows", "OR-workflows", P, "multi-step jobs exist as watchable workflow scripts", needs="project")
def workflows(ctx):
    if not (ctx.project / "prompts" / "workflows").is_dir():
        raise Skip("this project keeps no workflow scripts (prompts/workflows/): only needed when the agent tool runs workflows")
    w = sorted((ctx.project / "prompts" / "workflows").glob("*.js"))
    ctx.verdict([] if w else ["no prompts/workflows/*.js"], f"{len(w)} workflow scripts", "write the job as a workflow script (book/02-owner-rules.md 'Workflows you can watch')")


LOOSE = r"\b(should|shouldn't|try to|ideally|where possible|if possible|as needed|when possible|preferably)\b"


@check("proc.rules-code", "OR-rules-code", P, "every rule has a registry entry, every named check exists, no loose words, hooks installed", needs="project")
def rules_code(ctx):
    from . import registry
    from .core import CHECKS
    book = ctx.need_file(RULEBOOK, "restore PAGE-RULEBOOK.md")
    if not (ctx.kit_dir / "rules" / "registry.json").exists():
        raise Missing("rules/registry.json", "restore rules/registry.json")
    reg = registry.load()
    probs = [f"rule {i} has no registry entry" for i in registry.unregistered()]
    probs += [f"{e['id']} names unknown check {c}" for e in reg["rules"] for c in registry.checks_of(e) if c not in CHECKS]
    probs += [f"owner-rules row '{t}' has no registry entry" for t in registry.unregistered_rows(BOOK / "02-owner-rules.md")]
    text = book.read_text()
    ver = re.search(r"(?m)^version:\s*(\S+)", text)
    if not ver or ver.group(1) != reg.get("rulebook_version"):
        probs.append(f"registry rulebook_version {reg.get('rulebook_version')} != PAGE-RULEBOOK {ver and ver.group(1)}")
    rules = text.split("\n## Rules", 1)[-1].split("\n## Mistakes already caught", 1)[0]
    for n, line in enumerate(rules.splitlines(), 1):
        # the owner's own words are quoted as they were said; only the rule's wording must be strict
        m = re.search(LOOSE, re.sub(r'"[^"]*"|“[^”]*”', " ", line), re.I)
        if m:
            probs.append(f"loose word '{m.group(0)}' in the rules: {line.strip()[:60]}")
    hook = ctx.project / ".git" / "hooks" / "pre-commit"
    if not hook.exists() or "growth-gate-hook" not in hook.read_text(errors="replace"):
        probs.append("no rule pre-commit hook in this repo")
    ctx.verdict(probs, f"{len(reg['rules'])} entries; every rule and OWNER-RULES row registered; no loose words; pre-commit hook in place",
                "add the entry to rules/registry.json, write must/never or a number, or run growth install_hooks")
