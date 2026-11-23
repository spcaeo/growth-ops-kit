#!/usr/bin/env python3
"""The golden rule: never share a page URL with the owner before it is 100% approved and checked.

  growth ready <path> --type money|core|hub|post --key <key>    # check one page
  growth ready --list                                           # what is READY now
  growth ready --batch pages.txt [--jobs 3] [--stale-only]      # many pages side by side ("<path> <type> <key>" a line)
  growth ready --batch ledger --stale-only                      # re-check every page in the ledger that is not READY now

A page is READY only when the full gate, run on the one preview address (growth.json preview_url) against the
worktree that serves it (growth.json preview_repo), shows 0 FAIL. That includes the status of every internal link (growth.json link_check_cap, default 200), the independent review (rule 109),
fresh screenshots and click-test, the fact check, the AI baseline and the speed run: no exceptions, no "known" FAILs.
Manual checkpoints (research/<key>-checkpoints.md, see `growth checkpoints`) must each be ticked with a proof.
READY is recorded in journal/ready.json with the commit it was checked at and the page's fingerprint (its built HTML plus
every CSS and JS file it links, see fingerprint.py). It stays READY while either is unchanged: the same commit, or a
later commit whose fresh build leaves this page's output byte for byte the same (2.8.0; before, any commit anywhere on the
site made every page not READY, so one page's fix forced a re-check of all of them). A build older than the last commit
never vouches for a page: then only the commit counts.
growth url_guard (the Stop hook) blocks any reply that shows the owner a local page URL that is not READY.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import atomic  # noqa: E402
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


def _released(commit):
    """A page checked in a worktree that release then removed: READY still holds when the commit it was checked at is
    part of the site checkout's history (merged, so it is what went live). Kit friction 42."""
    site = CFG.get("site_repo")
    if not commit or not site:
        return False
    repo = (PROJECT / site).expanduser().resolve()
    if not (repo / ".git").exists():
        return False
    r = subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", commit, "HEAD"], capture_output=True)
    return r.returncode == 0


def page_fp(path):
    """The page's fingerprint from the built output (growth.json build_dir), or None when there is no build, the page is
    not in it, or the build is older than the preview repo's last commit (an old build cannot vouch for the code now)."""
    try:
        import fingerprint
        repo = preview_repo()
        root = fingerprint.build_root(CFG, PROJECT, repo)
        if not root or not root.is_dir():
            return None
        f = fingerprint._built_file(root, path)
        if not f:
            return None
        if repo is not None and (repo / ".git").exists():
            ct = subprocess.run(["git", "-C", str(repo), "log", "-1", "--format=%ct"], capture_output=True, text=True).stdout.strip()
            if ct.isdigit() and f.stat().st_mtime < int(ct):
                return None
        fp = fingerprint.current(CFG, PROJECT, repo, path)
        return fp if fp and fp.get("src") == "build" else None
    except Exception:  # noqa: BLE001  (no fingerprint: the commit rule decides)
        return None


def status(path, entry=None, now=None):
    """"same commit", "same output" or "" (not READY) for one ledger entry."""
    e = entry if entry is not None else ledger().get(path.rstrip("/") or "/")
    if not e:
        return ""
    now = now or head(preview_repo())
    if e.get("commit") == now:
        return "same commit"
    if now == "no-repo":
        return "released" if _released(e.get("commit")) else ""
    if e.get("fp"):
        import fingerprint
        cur = page_fp(path)
        if cur and fingerprint.same(e["fp"], cur, "built"):
            return "same output"
    return ""


def is_ready(path):
    return bool(status(path))


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
    text = plan.read_text()
    probs = checkpoints.manual_status(text, PROJECT, [r for r in [CFG.get("site_repo") and PROJECT / CFG["site_repo"], preview_repo()] if r])[2]
    extra_file = CFG.get("checkpoints_extra") or ""
    if extra_file and (PROJECT / extra_file).expanduser().is_file():
        probs += checkpoints.missing_extra(text, checkpoints.extra_items((PROJECT / extra_file).expanduser()))
    return probs


GATE_LINE = re.compile(r"^Gate: (\d+) FAIL, (\d+) WARN, (\d+) OK, (\d+) SKIP, (\d+) BLOCKED-SKIP", re.M)
RESULT_LINE = re.compile(r"^(?:(?:FAIL|WARN|OK)\s+\S+\s+\[([\w.-]+)\]|(?:BLOCKED-)?SKIP ([\w.-]+):)", re.M)


def run_gate(cmd):
    """Run the gate; a gate that cannot even start is a result too (code 99), never an exception that skips the verdict."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT)
    except OSError as e:
        return subprocess.CompletedProcess(cmd, 99, "", f"{type(e).__name__}: {e}")


def expected_checks(ptype):
    """The check ids the gate must report for a page of this type at READY: the build stage, plus house.features."""
    from gatelib import CHECKS
    ids = {c.cid for c in CHECKS.values() if ptype in c.types and c.stage == "build"}
    return ids | {"house.features"}


def gate_problem(r, ptype):
    """"" when the gate ran to the end and reported every check; else the plain reason it did not.
    Fail closed: a non-zero exit, no summary line, no checks run or a check that did not report is never READY."""
    out = r.stdout or ""
    if r.returncode != 0 and not any(l.startswith("FAIL") for l in out.splitlines()):
        why = ((r.stderr or "").strip().splitlines() or ["no message"])[-1][:160]
        return f"gate did not complete (exit code {r.returncode}): {why}"
    summ = GATE_LINE.findall(out)
    if len(summ) != 1:
        return f"gate did not complete: expected one 'Gate:' summary line, found {len(summ)}"
    if not any(int(x) for x in summ[0]):
        return "gate ran 0 checks"
    try:
        want = expected_checks(ptype)
    except Exception as e:  # noqa: BLE001
        return f"gate checks could not be loaded: {type(e).__name__}: {str(e)[:120]}"
    if int(summ[0][4]) or re.search(r"^BLOCKED-SKIP ", out, re.M):
        names = sorted({m for m in re.findall(r"^BLOCKED-SKIP ([\w.-]+):", out, re.M)})
        import approvals
        open_ = [n for n in names if not approvals.excuses_blocked_skip(PROJECT, CFG, n)[0]]
        if open_ or len(names) != int(summ[0][4]):
            return (f"{int(summ[0][4])} required check(s) could not run ({', '.join((open_ or names)[:6])}); install what they need "
                    "or fix the setup, or have the owner approve a design exception (growth approve exception), then run ready again")
    got = {a or b for a, b in RESULT_LINE.findall(out)}
    if want - got:
        return f"gate did not report {len(want - got)} expected check(s): {', '.join(sorted(want - got)[:6])}"
    return ""


def key_problem(path, key):
    """The key a page was pre-flighted with is its key for good: READY refuses another one (a page cannot borrow the
    review, dossier and fact check of a different page by naming its key). "" when it matches."""
    try:
        e = json.loads((PROJECT / "journal" / "preflight.json").read_text()).get(path, {})
    except (OSError, ValueError):
        return ""                        # no pre-flight record: ev.preflight is the check that wants one
    if not e:
        return ""
    if not e.get("key"):
        return f"the pre-flight of {path} did not record a page key: run growth preflight {path} again with --key {key}"
    if e["key"] != key:
        return f"{path} was pre-flighted with key '{e['key']}', not '{key}': use --key {e['key']}"
    return ""


def held_proposals(key):
    """The page's held-field proposals with their status (growth held): listed so the owner sees them before a freeze lifts."""
    import held
    return held.lines(held.load(held.plan_path(PROJECT, key)))


def print_held(lines):
    if lines:
        print(f"Held-field proposals ({len(lines)}; growth held list <key>):")
        for l in lines:
            print(" ", l[:200])


def fetch_path(path: str, typed: str, cfg: dict) -> str:
    """The address the preview is asked for. `path` is the page key (no trailing slash). A trailing-slash site answers 301 to
    /x/, and a 301 makes the technical SEO checks report "input missing", so ask for the site's own form: growth.json
    trailing_slash (true, or "slash"), else the slash the caller typed. Never a slash on a file ("/feed.xml")."""
    ts = cfg.get("trailing_slash")
    slash = ts in (True, "slash", "1", 1) if ts is not None else typed.endswith("/")
    if slash and path != "/" and "." not in path.rsplit("/", 1)[-1]:
        return path + "/"
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", nargs="?")
    ap.add_argument("--type", choices=["money", "core", "hub", "post"])
    ap.add_argument("--key")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--batch", help='file with "<path> <type> <key>" a line, or "ledger" for every page in journal/ready.json')
    ap.add_argument("--jobs", type=int, default=0, help="pages checked side by side (default growth.json ready_jobs, else 3)")
    ap.add_argument("--stale-only", action="store_true", help="skip pages that are READY now (same commit or same output)")
    a = ap.parse_args()
    repo = preview_repo()
    if not a.list and a.path and preview_repo_problem():
        sys.exit(preview_repo_problem())
    if a.batch:
        sys.exit(run_batch(a.batch, a.jobs, a.stale_only))
    if a.list or not a.path:
        cur = head(repo)
        for p, e in sorted(ledger().items()):
            why = status(p, e, cur)
            print(f"{'READY' if why else 'STALE'}  {p}  (checked {e.get('at')} at {e.get('commit', '')[:7]}"
                  f"{'; ' + why if why else ''})")
        return
    if not (a.type and a.key):
        sys.exit("--type and --key are required")
    path = a.path.rstrip("/") or "/"
    if not CFG.get("preview_url"):
        sys.exit("growth.json has no preview_url: set the one address the owner sees previews on")
    url = CFG["preview_url"].rstrip("/") + fetch_path(path, a.path, CFG)
    cmd = [sys.executable, str(KIT_DIR / "tools" / "gate.py"), "page", path, "--url", url,
           "--type", a.type, "--key", a.key] + (["--repo", str(repo)] if repo else [])
    t0 = time.time()
    r = run_gate(cmd)
    fails = [l for l in (r.stdout + r.stderr).splitlines() if l.startswith("FAIL")]
    broken = key_problem(path, a.key) or gate_problem(r, a.type)
    if broken:
        fails.insert(0, f"FAIL {broken}")
    fails += [f"FAIL manual checkpoint {m}" for m in manual_problems(path, a.key)]
    oks = sum(1 for l in r.stdout.splitlines() if l.startswith("OK"))
    held_lines = held_proposals(a.key)
    if fails:
        atomic.update_json(LEDGER, lambda x: x.pop(path, None) and None, default={}, indent=1)
        print(f"NOT READY {path}: {len(fails)} FAIL, {oks} OK. The URL may not be shared with the owner.")
        for l in fails:
            print(" ", l[:200])
        print_held(held_lines)
        sys.exit(1)
    entry = {"commit": head(repo), "at": dt.datetime.now(TZ).strftime("%Y-%m-%d %H:%M %Z"), "ok": oks, "url": url,
             "type": a.type, "key": a.key, "secs": round(time.time() - t0)}
    fp = page_fp(path)
    if fp:
        entry["fp"] = fp
    atomic.update_json(LEDGER, lambda x: x.update({path: entry}), default={}, indent=1)
    d = {path: entry}
    print(f"READY {path}: 0 FAIL, {oks} OK at {d[path]['commit'][:7]}. It may be shared: {url}")
    print_held(held_lines)


def batch_lines(src):
    """[(path, type, key)] from a file ("<path> <type> <key>" a line, # comments) or "ledger" (pages checked since 2.8.0)."""
    if src == "ledger":
        return [(p, e["type"], e["key"]) for p, e in sorted(ledger().items()) if e.get("type") and e.get("key")]
    out = []
    for ln in Path(src).expanduser().read_text().splitlines():
        ln = ln.split("#", 1)[0].strip()
        if not ln:
            continue
        parts = ln.split()
        if len(parts) != 3 or parts[1] not in ("money", "core", "hub", "post"):
            sys.exit(f"bad batch line (want '<path> <type> <key>'): {ln}")
        out.append(tuple(parts))
    return out


def run_batch(src, jobs=0, stale_only=False):
    """Check many pages side by side: each page is its own `growth ready` run (its own gate and browser), so a page's verdict
    is exactly what a single run gives. Prints each verdict as it lands, then the totals and the full log's location."""
    import concurrent.futures as cf
    rows = batch_lines(src)
    jobs = jobs or int(CFG.get("ready_jobs") or 3)
    kept, todo = [], []
    for p, t, k in rows:
        (kept if stale_only and is_ready(p) else todo).append((p, t, k))
    for p, *_ in kept:
        print(f"READY (kept, {status(p)})  {p}", flush=True)
    t0 = time.time()
    logs, verdicts = {}, {}

    def one(row):
        p, t, k = row
        s0 = time.time()
        r = subprocess.run([sys.executable, str(Path(__file__).resolve()), p, "--type", t, "--key", k],
                           capture_output=True, text=True, cwd=PROJECT)
        return row, r, time.time() - s0

    with cf.ThreadPoolExecutor(max_workers=max(1, jobs)) as ex:
        for fut in cf.as_completed([ex.submit(one, row) for row in todo]):
            (p, t, k), r, secs = fut.result()
            out = (r.stdout or "") + (r.stderr or "")
            logs[p] = out
            ok = r.returncode == 0 and out.lstrip().startswith("READY")
            verdicts[p] = ok
            first = next((l.strip() for l in out.splitlines() if l.strip().startswith("FAIL")), "")
            print(f"{'READY' if ok else 'NOT READY'}  {p}  {secs:.0f}s" + ("" if ok else f"  {first[:150]}"), flush=True)
    wall = time.time() - t0
    n_ok = sum(verdicts.values()) + len(kept)
    stamp = dt.datetime.now(TZ).strftime("%Y-%m-%d-%H%M%S")
    log = PROJECT / "journal" / "runs" / f"ready-batch-{stamp}.log"
    try:
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text("".join(f"===== {p}\n{logs[p]}\n" for p in sorted(logs)))
    except OSError:
        log = None
    print(f"\nBatch: {n_ok} of {len(rows)} READY ({len(kept)} kept unchanged, {len(todo)} checked with {jobs} side by side in "
          f"{wall / 60:.1f} min){'; full log ' + str(log.relative_to(PROJECT)) if log else ''}")
    return 0 if n_ok == len(rows) else 1


if __name__ == "__main__":
    main()
