#!/usr/bin/env python3
"""The golden rule: never share a page URL with the owner before it is 100% approved and checked.

  growth ready <path> --type money|core|hub|post --key <key>    # check one page
  growth ready --list                                           # what is READY now

A page is READY only when the full gate, run on the one preview address (growth.json preview_url) against the
worktree that serves it (growth.json preview_repo), shows 0 FAIL. That includes the independent review (rule 109),
fresh screenshots and click-test, the fact check, the AI baseline and the speed run: no exceptions, no "known" FAILs.
Manual checkpoints (research/<key>-checkpoints.md, see `growth checkpoints`) must each be ticked with a proof.
READY is recorded in journal/ready.json with the commit it was checked at; any later commit makes it not READY again.
growth url_guard (the Stop hook) blocks any reply that shows the owner a local page URL that is not READY.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import CFG, KIT_DIR, PROJECT, TZ  # noqa: E402

LEDGER = PROJECT / "journal" / "ready.json"


def preview_repo():
    given = CFG.get("preview_repo") or CFG.get("site_repo")
    return (PROJECT / given).expanduser().resolve() if given else None


def preview_repo_problem():
    """A site with a checkout must name the worktree the page is built in: with preview_repo empty, READY and the evidence
    dates would read the main site folder, so commits in the worktree would never make READY stale (#51)."""
    if CFG.get("site_repo") and not CFG.get("preview_repo"):
        return ("growth.json has site_repo but no preview_repo: READY and the screenshot dates would read the main site "
                "folder, not the worktree the page is built in. Set preview_repo to that worktree "
                "(to the site_repo folder itself only if you build there).")
    return ""


def head(repo):
    """The commit a page was checked at. A site with no git checkout has none: READY then cannot go stale by itself."""
    if repo is None or not (repo / ".git").exists():
        return "no-repo"
    return subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()


def ledger():
    try:
        return json.loads(LEDGER.read_text())
    except (OSError, ValueError):
        return {}


def is_ready(path):
    e = ledger().get(path.rstrip("/") or "/")
    return bool(e) and e.get("commit") == head(preview_repo())


def manual_problems(path, key):
    """Manual checkpoints of the page still open (unticked, or ticked with no proof), read from the file preflight writes."""
    import checkpoints
    plan = None
    try:
        rel = json.loads((PROJECT / "journal" / "preflight.json").read_text()).get(path, {}).get("plan")
        plan = PROJECT / rel if rel else None
    except (OSError, ValueError):
        pass
    plan = plan if plan and plan.is_file() else PROJECT / "research" / f"{key}-checkpoints.md"
    if not plan.is_file():
        return []                        # no file: ev.preflight (rule 0a) is the check that wants one
    return checkpoints.manual_status(plan.read_text())[2]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", nargs="?")
    ap.add_argument("--type", choices=["money", "core", "hub", "post"])
    ap.add_argument("--key")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    repo = preview_repo()
    if not a.list and a.path and preview_repo_problem():
        sys.exit(preview_repo_problem())
    if a.list or not a.path:
        cur = head(repo)
        for p, e in sorted(ledger().items()):
            print(f"{'READY' if e.get('commit') == cur else 'STALE'}  {p}  (checked {e.get('at')} at {e.get('commit', '')[:7]})")
        return
    if not (a.type and a.key):
        sys.exit("--type and --key are required")
    path = a.path.rstrip("/") or "/"
    if not CFG.get("preview_url"):
        sys.exit("growth.json has no preview_url: set the one address the owner sees previews on")
    url = CFG["preview_url"].rstrip("/") + path
    cmd = [sys.executable, str(KIT_DIR / "tools" / "gate.py"), "page", path, "--url", url,
           "--type", a.type, "--key", a.key, "--no-link-status"] + (["--repo", str(repo)] if repo else [])
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT)
    fails = [l for l in (r.stdout + r.stderr).splitlines() if l.startswith("FAIL")]
    fails += [f"FAIL manual checkpoint {m}" for m in manual_problems(path, a.key)]
    oks = sum(1 for l in r.stdout.splitlines() if l.startswith("OK"))
    d = ledger()
    if fails:
        d.pop(path, None)
        LEDGER.write_text(json.dumps(d, indent=1) + "\n")
        print(f"NOT READY {path}: {len(fails)} FAIL, {oks} OK. The URL may not be shared with the owner.")
        for l in fails:
            print(" ", l[:200])
        sys.exit(1)
    d[path] = {"commit": head(repo), "at": dt.datetime.now(TZ).strftime("%Y-%m-%d %H:%M %Z"), "ok": oks, "url": url}
    LEDGER.write_text(json.dumps(d, indent=1) + "\n")
    print(f"READY {path}: 0 FAIL, {oks} OK at {d[path]['commit'][:7]}. It may be shared: {url}")


if __name__ == "__main__":
    main()
