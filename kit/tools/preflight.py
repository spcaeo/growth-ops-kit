#!/usr/bin/env python3
"""Pre-flight: a page is ready to BUILD only when its planning is complete and every checkpoint is set (from a real project:
"when you start a new page the planning and preparation should be done in depth and all checkpoints clear set
as part of the playbook and workflow", after four pages spent hours being fixed at the end).

  growth preflight <path> --type money|core|hub|post --key <key> [--repo <worktree>]

It does three things, before the first line of page code:
  1. Site health: the shared problems that would otherwise fail every page at the end are found now, across the whole
     site repo (files over 1,000 lines, raw colour codes in CSS, animation libraries). Fix them first, on their own.
  2. Planning evidence: runs the gate's planning checks (inventory, snapshot, dossier, brief, task steps, fold plan,
     link plan, AI baseline, archive) and needs every one to pass. A baseline is taken BEFORE the build, not after.
  3. The checkpoint plan: writes research/<key>-checkpoints.md, every check in scope sorted by WHEN it is checked:
     before the build, after every fold commit, before READY, after publishing. The builder gets it with the brief.
PASS is recorded in journal/preflight.json; the gate check ev.preflight (rule 0a) fails a page without it.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import CFG, KIT_DIR, PROJECT, TZ  # noqa: E402
from ready import preview_repo_problem  # noqa: E402
import checkpoints  # noqa: E402  (merge the checkpoints file, never overwrite it)

LEDGER = PROJECT / "journal" / "preflight.json"
PLAN = ["proc.doctor", "proc.owner-messages", "proc.rulebook-current", "ev.inventory", "ev.snapshot", "ev.dossier",
        "ev.brief", "ev.task-steps", "ev.fold-plan", "links.plan", "ev.ai-baseline", "ev.archive-before"]
# A rebuilt page is still the OLD page at pre-flight, so these two are judged on the plan itself here; the gate judges
# the built page against them after every fold.
PLAN_ONLY = {"ev.fold-plan", "links.plan"}


def plan_files(path, key, ptype):
    """The fold plan is complete and the link plan is filed (the page-side half waits for the build). Each only when
    the gate scopes that check to this page type."""
    probs = []
    scope = {c.cid for c in checks_in_scope(ptype)}
    if "ev.fold-plan" not in scope:
        return probs
    r = subprocess.run([sys.executable, str(KIT_DIR / "tools" / "fold_plan.py"), "check", path, "--key", key],
                       capture_output=True, text=True, cwd=PROJECT)
    if r.returncode:
        probs.append("FAIL 36h   [ev.fold-plan] fold plan not complete: " + (r.stdout + r.stderr).strip().splitlines()[-1][:160])
    jf = PROJECT / "journal" / "entries.jsonl"       # no journal yet is a finding to report, not a crash
    ents = [json.loads(l) for l in jf.read_text().splitlines() if l.strip()] if jf.exists() else []
    planned = [e for e in ents if "internal-link" in (e.get("tags") or []) and path in (e.get("title", "") + " " + e.get("text", ""))
               and (e.get("pages") or []) != [path]]
    if "links.plan" not in scope or (CFG.get("stack") or "static").lower() != "nextjs":
        return probs                       # the link plan is checked by the Next.js adapter only
    if len(planned) < 3:
        probs.append(f"FAIL 88a   [links.plan] {len(planned)} planned links filed (3 or more needed)")
    if not list((PROJECT / "research").glob(f"*{key}*internal-link*")):
        probs.append(f"FAIL 88a   [links.plan] no research/*{key}*internal-link* plan file")
    return probs
FINISH = ["ev.research-check", "ev.review", "ev.open-findings", "ev.shots-widths", "ev.shots-1366-390", "ev.click-test",
          "ev.share-preview", "ev.archive-after", "repo.commit-style", "ev.preflight"]
MOTION = ("framer-motion", "motion", "gsap", "animejs", "lottie-web", "lottie-react", "react-spring", "aos")


def site_health(repo):
    probs = []
    for f in sorted(p for d in ("app", "components", "lib") for p in (repo / d).rglob("*")
                    if p.suffix in (".ts", ".tsx", ".css", ".mjs") and p.is_file() and "node_modules" not in p.parts):
        lines = f.read_text(errors="replace").splitlines()
        if len(lines) > 1000:
            probs.append(f"{f.relative_to(repo)}: {len(lines)} lines (rule 124: split it first)")
        if f.suffix == ".css":
            n = sum(len(re.findall(r"(?<![\w-])#[0-9a-fA-F]{3,8}\b", ln)) for ln in lines
                    if not re.search(r"^\s*--[\w-]+\s*:", ln) and not ln.strip().startswith(("/*", "*")))
            if n:
                probs.append(f"{f.relative_to(repo)}: {n} raw colour codes (rule 41: use tokens)")
    pkg = json.loads((repo / "package.json").read_text())
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    probs += [f"package.json: animation library {d} (rule 58)" for d in MOTION if d in deps]
    return probs


def checks_in_scope(ptype):
    from gatelib import CHECKS  # noqa: E402
    return [c for c in CHECKS.values() if ptype in c.types]


def write_plan(path, ptype, key, checks):
    when = {"before": [], "fold": [], "finish": [], "release": []}
    for c in sorted(checks, key=lambda c: (c.rule, c.cid)):
        phase = ("release" if c.stage == "release" else "before" if c.cid in PLAN else
                 "finish" if c.cid in FINISH else "fold")
        when[phase].append((c.cid, f"`{c.cid}` (rule {c.rule}): {c.what}"))
    head = {"before": "1. Before the build (growth preflight must PASS)",
            "fold": "2. After EVERY fold commit (gate on the preview; fix before the next fold, never at the end)",
            "finish": "3. Before READY (growth ready), after the last commit",
            "release": "4. After publishing, on the production site"}
    header = (f"# Checkpoints: {path} ({ptype} page)\n\n"
              f"Updated {dt.datetime.now(TZ):%Y-%m-%d %H:%M %Z} by growth preflight (it merges: ticks, proofs and your own items stay). "
              "Generated items are proven by the gate run. Manual items (section 5) have no gate check: the builder ticks each "
              "with one line of proof after ' -- ', and `growth ready` fails while one is open.")
    extra_file = CFG.get("checkpoints_extra") or ""
    extra = []
    if extra_file:
        ef = (PROJECT / extra_file).expanduser()
        if not ef.is_file():
            sys.exit(f"growth.json checkpoints_extra points at {extra_file}, which does not exist")
        extra = checkpoints.extra_items(ef)
    p = PROJECT / "research" / f"{key}-checkpoints.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    old = p.read_text() if p.exists() else ""
    p.write_text(checkpoints.merge(old, [(head[k], when[k]) for k in head], extra, header, dt.datetime.now(TZ).strftime("%Y-%m-%d")))
    total, done, _ = checkpoints.manual_status(p.read_text())
    return p, {**{k: len(v) for k, v in when.items()}, "manual": total, "manual_done": done}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path")
    ap.add_argument("--type", required=True, choices=["money", "core", "hub", "post"])
    ap.add_argument("--key", required=True)
    given = CFG.get("preview_repo") or CFG.get("site_repo") or ""
    ap.add_argument("--repo", default=str((PROJECT / given).expanduser().resolve()) if given else "",
                    help="the site checkout (default: growth.json preview_repo; site_repo only when no preview_repo is needed)")
    a = ap.parse_args()
    if preview_repo_problem() and not any(x.startswith("--repo") for x in sys.argv[1:]):
        sys.exit(preview_repo_problem())     # an explicit --repo is the worktree; otherwise it must be in growth.json
    repo, path = (Path(a.repo).resolve() if a.repo else None), a.path.rstrip("/") or "/"
    if not CFG.get("preview_url"):
        sys.exit("growth.json has no preview_url: set the address pages are previewed on")

    nextjs = (CFG.get("stack") or "static").lower() == "nextjs" and repo is not None and (repo / "package.json").exists()
    health = site_health(repo) if nextjs else []        # the site-code health check is the Next.js adapter's
    url = CFG["preview_url"].rstrip("/") + path
    r = subprocess.run([sys.executable, str(KIT_DIR / "tools" / "gate.py"), "page", path, "--url", url,
                        *(["--repo", str(repo)] if repo else []),
                        "--type", a.type, "--key", a.key, "--no-link-status", "--only", ",".join(c for c in PLAN if c not in PLAN_ONLY)],
                       capture_output=True, text=True, cwd=PROJECT)
    plan_fails = [l for l in (r.stdout + r.stderr).splitlines() if l.startswith("FAIL")] + plan_files(path, a.key, a.type)
    plan_file, counts = write_plan(path, a.type, a.key, checks_in_scope(a.type))

    print(f"Checkpoint plan: {plan_file.relative_to(PROJECT)} ({counts['before']} before the build, {counts['fold']} after "
          f"every fold, {counts['finish']} before READY, {counts['release']} after publishing; "
          f"manual checks {counts['manual_done']}/{counts['manual']})")
    print(f"Site health ({repo.name if repo else 'no site checkout'}): "
          + ("OK" if not health else f"{len(health)} problems, fix them before the page:") + ("" if nextjs else " (not checked: Next.js adapter only)"))
    for h in health:
        print("  " + h)
    print("Planning evidence: " + ("OK" if not plan_fails else f"{len(plan_fails)} missing:"))
    for l in plan_fails:
        print("  " + l[:220])
    d = json.loads(LEDGER.read_text()) if LEDGER.exists() else {}
    ok = not health and not plan_fails
    d[path] = {"ok": ok, "at": dt.datetime.now(TZ).strftime("%Y-%m-%d %H:%M %Z"), "site_problems": len(health),
               "plan_missing": len(plan_fails), "plan": plan_file.relative_to(PROJECT).as_posix()}
    LEDGER.write_text(json.dumps(d, indent=1) + "\n")
    print(f"PRE-FLIGHT {'PASS' if ok else 'FAIL'} {path}: " + ("build may start." if ok else "do not start the build."))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
