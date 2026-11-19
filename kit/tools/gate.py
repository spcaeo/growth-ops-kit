#!/usr/bin/env python3
"""The rule gate: a page cannot ship while any check fails (".py runs become rules").

Every numbered rule of book/03-page-rulebook.md (and every checkable owner-rules row) has an entry in
kit/rules/registry.json: "code" (a check here decides it) or "judgment" (a person decides; a code proxy checks the
evidence exists). Each check says what it reads (registry "needs"): live (the served page, any stack), project (the
project folder: journal, research, tasks), nextjs (the site's code: kit/adapters/nextjs, only when growth.json "stack"
is "nextjs"; on any other stack the gate prints "SKIP <id>: no adapter for <stack>" and counts those apart).

  growth gate page /pricing --url http://127.0.0.1:3801/pricing --type money [--key pricing] [--stage release] [--md out.md]
  growth gate page /pricing --url ... --needs live         # only the checks that read the served page
  growth gate page /pricing --repo ../site --type money    # no --url = static mode: only the checks that read the source
  growth gate process        # setup, logs, tasks, commits, main untouched, rulebook current
  growth gate engine         # kit files hold no project facts (file:line, count by file)
  growth gate coverage       # per rule: code or judgment + proxy, and the % enforced by code

Each line: FAIL|WARN|OK <rule> [check id] <what> -> <exact fix>, or SKIP <id>: <why> (does not apply here) or BLOCKED-SKIP <id>: <why> (applies but could not run: no browser, no way to date the page; READY refuses it). Exit 1 when any line is FAIL.
Read-only: GETs the one local page (and the links the technical SEO check follows); never fetches the live site.
"""
import argparse
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import CFG, DOCS, PROJECT  # noqa: E402
from gatelib import CHECKS, registry  # noqa: E402
from gatelib.core import Ctx, run_check  # noqa: E402

_HOST = urllib.parse.urlsplit(CFG.get("site_url", "")).netloc.lower().removeprefix("www.")
LIVE = (_HOST, "www." + _HOST) if _HOST else ()
STATIC_SKIP = ("c_evidence.py", "c_seo.py")   # evidence is proved at build/release time; technical SEO reads the page


def rule_key(r):
    m = re.match(r"(\d+)([a-z]?)", r)
    return (0, int(m.group(1)), m.group(2)) if m else (1, 0, r)


def severities():
    try:
        return {e["id"]: e.get("severity", "FAIL") for e in registry.load()["rules"]}
    except (OSError, ValueError):
        return {}


def fetch(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "GrowthGate/1.0 (read-only)"}), timeout=60) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:  # noqa: BLE001
        return 0, ""


def site_repo_default():
    """growth.json site_repo as a folder, or None when the project keeps no site checkout."""
    from config import SITE_REPO
    return SITE_REPO if CFG.get("site_repo") else None


def print_lines(ctx, title, md=None):
    sev = severities()
    for ln in ctx.lines:
        if ln.level == "FAIL" and sev.get(ln.rule) == "WARN":
            ln.level = "WARN"
    order = {"FAIL": 0, "WARN": 1, "OK": 2, "SKIP": 3}
    ctx.lines.sort(key=lambda l: (order[l.level], rule_key(l.rule), l.cid))
    n = {k: sum(1 for l in ctx.lines if l.level == k) for k in order}
    n["BLOCKED"] = sum(1 for l in ctx.lines if l.level == "SKIP" and l.blocked)
    n["SKIP"] -= n["BLOCKED"]
    out = [title, ""] + [l.text() for l in ctx.lines] + ["", f"Gate: {n['FAIL']} FAIL, {n['WARN']} WARN, {n['OK']} OK, {n['SKIP']} SKIP, {n['BLOCKED']} BLOCKED-SKIP "
                                                           f"({len(ctx.lines)} checks; SKIP = does not apply to this site, BLOCKED-SKIP = applies but could not run, "
                                                           f"never counted as OK). "
                                                           f"{'BLOCKED: fix every FAIL before release.' if n['FAIL'] else 'PASS.'}"
                                                           + (f" {n['BLOCKED']} check(s) could not run: READY needs them." if n["BLOCKED"] and not n["FAIL"] else "")]
    print("\n".join(out))
    if md:
        Path(md).write_text("\n".join(["```", *out, "```", ""]))
    return 1 if n["FAIL"] else 0


def default_key(path):
    """The page key when --key is not given: the path's snapshot slug (paths.default_key), never containing a slash."""
    import paths
    return paths.default_key(path)


def cmd_page(a):
    u = urllib.parse.urlsplit(a.url or "")
    if u.netloc.lower() in LIVE:
        print("Refusing to run the gate against the live site: pass a local URL.", file=sys.stderr)
        return 2
    repo = Path(a.repo).resolve() if a.repo else site_repo_default()
    key = a.key or default_key(a.path)
    static = not a.url
    ctx = Ctx(project=PROJECT, path=a.path, url=a.url or "", repo=repo, ptype=a.type, docs=DOCS, cfg=CFG, key=key, static=static)
    if not static:
        ctx.status, ctx.html = fetch(a.url)
    ctx.cache["no_link_status"] = a.no_link_status
    ctx.cache["no_browser"] = a.no_browser
    ctx.cache["needs_filter"] = set(filter(None, (a.needs or "").split(",")))
    only = set(filter(None, (getattr(a, "only", "") or "").split(",")))
    needs = set(filter(None, (a.needs or "").split(",")))
    todo = [c for c in CHECKS.values() if a.type in c.types and c.stage == a.stage and c.cid != "house.features"
            and not (static and c.file in STATIC_SKIP) and (not only or c.cid in only) and (not needs or c.needs in needs)]
    for c in todo:
        run_check(ctx, c)
    if not static and not only and (not needs or "live" in needs):
        run_check(ctx, CHECKS["house.features"])
    later = [c.cid for c in CHECKS.values() if a.type in c.types and c.stage != a.stage]
    title = (f"Rule gate: {a.path} ({a.type} page, stage {a.stage}, stack {ctx.stack()})  url {a.url or 'none: STATIC mode'}  repo {repo}"
             + (f"  only checks that read: {', '.join(sorted(needs))}" if needs else "") + "\n"
             f"Checks run: {len(todo) + (0 if static else 1) - len(ctx.skipped)}. Not run at this stage: {', '.join(later) or 'none'}.")
    if static:
        title += (f"\nStatic mode (source only, for the pre-commit hook): {len(ctx.skipped)} checks that read the page and "
                  f"the evidence checks did not run. Release still needs the full gate with --url.")
    return print_lines(ctx, title, a.md)


def cmd_process(a):
    ctx = Ctx(project=PROJECT, docs=DOCS, cfg=CFG, repo=site_repo_default())
    for c in CHECKS.values():
        if "process" in c.types:
            run_check(ctx, c)
    return print_lines(ctx, "Rule gate: process rules", a.md)


def cmd_engine(a):
    from gatelib.c_engine import scan
    ctx = Ctx(project=PROJECT, docs=DOCS, cfg=CFG)
    run_check(ctx, CHECKS["engine.facts"])
    if ctx.lines and ctx.lines[0].level == "FAIL" and not ctx.lines[0].what.startswith(("input missing", "check crashed")):
        hits = scan(CFG)
        by = {}
        for f, n, kind, snip in hits:
            by[f] = by.get(f, 0) + 1
            print(f"FAIL OR-engine [engine.facts] {f}:{n} {kind}: {snip[:90]} -> move it to the project's growth.json or BRAND.md")
        print(f"\nBy file ({len(hits)} hits in {len(by)} files):")
        for f, c in sorted(by.items(), key=lambda x: (-x[1], x[0])):
            print(f"  {c:>4}  {f}")
        print(f"\nGate: {len(hits)} FAIL. BLOCKED: kit files hold project facts.")
        return 1
    return print_lines(ctx, "Rule gate: engine files", a.md)


def cmd_coverage(a):
    reg = registry.load()["rules"]
    code = [e for e in reg if e["enforcement"] == "code"]
    judg = [e for e in reg if e["enforcement"] == "judgment"]
    book = [e for e in reg if not e["id"].startswith("OR-")]
    book_code = [e for e in book if e["enforcement"] == "code"]
    print(f"{'rule':<14} {'enforced by':<9} {'sev':<4} checks / proxies")
    for e in sorted(reg, key=lambda e: rule_key(e["id"])):
        ch = ", ".join(e.get("checks", [])) if e["enforcement"] == "code" else "proxy " + ", ".join(e.get("proxy", []))
        print(f"{e['id']:<14} {e['enforcement']:<9} {e.get('severity', 'FAIL'):<4} {ch}")
    missing = registry.unregistered() if RULEBOOK_EXISTS else []
    unknown = sorted({c for e in reg for c in registry.checks_of(e)} - set(CHECKS))
    print(f"\nRulebook rules: {len(book)}; enforced by code: {len(book_code)} ({100 * len(book_code) / max(len(book), 1):.0f}%); "
          f"judgment with a code proxy: {len(book) - len(book_code)}.")
    print(f"All entries (rulebook + OWNER-RULES rows): {len(reg)}; code {len(code)} ({100 * len(code) / len(reg):.0f}%), judgment {len(judg)}.")
    by = {n: sum(1 for c in CHECKS.values() if c.needs == n) for n in ("live", "project", "nextjs")}
    print(f"Checks: {len(CHECKS)} ({by['live']} read the live page, {by['project']} the project folder, {by['nextjs']} the Next.js site code via the adapter).")
    print(f"Registry: Rules without an entry: {missing or 'none'}. Unknown check ids: {unknown or 'none'}.")
    return 1 if missing or unknown else 0


from config import RULEBOOK  # noqa: E402

RULEBOOK_EXISTS = RULEBOOK.exists()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("page", help="run every check that applies to one page")
    p.add_argument("path")
    p.add_argument("--url", help="local URL of the page (dev or preview server); leave out for static mode (source checks only)")
    p.add_argument("--repo", default="", help="the site's checkout (default: growth.json site_repo)")
    p.add_argument("--no-browser", action="store_true", help="skip the two checks that measure the page in a headless browser (contrast, phone)")
    p.add_argument("--needs", default="", help="only checks that read: live, project, nextjs (comma list)")
    p.add_argument("--type", choices=["money", "hub", "post", "core"], default="money")
    p.add_argument("--key", default="", help="research file key (default: the path as a slug, e.g. blog__my-post)")
    p.add_argument("--stage", choices=["build", "release"], default="build", help="release = after the merge")
    p.add_argument("--no-link-status", action="store_true", help="skip the status check of every internal link (faster)")
    p.add_argument("--only", default="", help="comma list of check ids to run (growth preflight uses it)")
    p.add_argument("--md", help="also write the output to this file")
    q = sub.add_parser("process", help="process rules")
    q.add_argument("--md")
    e = sub.add_parser("engine", help="engine files hold no project facts")
    e.add_argument("--md")
    sub.add_parser("coverage", help="code vs judgment per rule")
    a = ap.parse_args(argv)
    return {"page": cmd_page, "process": cmd_process, "engine": cmd_engine, "coverage": cmd_coverage}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
