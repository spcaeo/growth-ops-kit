#!/usr/bin/env python3
"""Learn how a site is built, so the gate finds each part of a page by meaning on any design (#58).

  growth design learn --base <preview URL> [--page /] [--page /blog/a/] [--write]
        reads a few built pages of the local preview, finds each page concept (site header and footer, main, cover image,
        byline, updated date, reading aid, FAQ, read-next, calculator, ...) first by meaning (landmarks, schema.org, <time>),
        and for a concept the meaning misses proposes a selector from the page's own class names. Prints what each concept
        matched (the owner confirms or corrects it); --write saves the proposals to design.json in the project.
  growth design calibrate --base <preview URL> --page /blog/a/ [--page ...] [--type post]
        runs the gate on pages the owner marks as known-good. A detector that FAILs there missed the design, not the page:
        it is listed as SUSPECT with the pages it failed on (map the concept in design.json, or file a kit issue).

Local previews only: a host that is the site's real address (growth.json site_url) is refused.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# concept -> (class-name hint, selector suffix). A hint only ranks the page's own class names; the proposal must then match.
HINTS = {
    "site_header": (r"header|top-?bar|navbar|masthead|site-?nav", ""),
    "site_footer": (r"footer|bottom-?bar|colophon|^bottom$", ""),
    "main": (r"^(content|main|page|post|article|entry)$|main-?content|page-?content", ""),
    "cover_image": (r"hero|cover|featured|banner|lead-?image", " img"),
    "byline": (r"author|byline|written-?by|\bwho\b", ""),
    "updated_date": (r"updated|modified|stamp|date|meta", ""),
    "reading_aid": (r"toc|contents|progress|reading|min-?left", ""),
    "faq_question": (r"faq|\bqa\b|questions|accordion", " details"),
    "read_next": (r"read-?next|related|more-?posts|next-?up", ""),
    "calculator": (r"calc|calculator", ""),
}


def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "GrowthDesign/1.0 (read-only)"}), timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def refuse_live(base, cfg):
    host = urllib.parse.urlsplit(base).netloc.lower().removeprefix("www.")
    real = urllib.parse.urlsplit(cfg.get("site_url", "")).netloc.lower().removeprefix("www.")
    if real and host == real:
        sys.exit("Refusing to read the live site: pass the local preview address.")


def learn(pages, cfg, project):
    """pages: {path: html}. Returns {concept: {"by": "meaning"|"proposed"|"missing", "selector", "found": {path: n}, "sample": text}}."""
    from techseo.dom import parse
    from gatelib import design
    from gatelib.core import Ctx
    ctxs = {}
    for path, html in pages.items():
        ctxs[path] = Ctx(project=project, path=path, cfg={k: v for k, v in cfg.items() if k != "design"}, html=html, status=200)
    out = {}
    for concept in design.CONCEPTS:
        found = {p: len(design._semantic(c, c.root(), concept)) for p, c in ctxs.items()}
        entry = {"found": found, "by": "meaning", "selector": "", "sample": ""}
        if all(found.values()):
            first = next(iter(ctxs.values()))
            n = design._semantic(first, first.root(), concept)
            entry["sample"] = _sample(n[0])
            out[concept] = entry
            continue
        prop = propose(concept, ctxs)
        if prop:
            sel, counts, sample = prop
            entry.update(by="proposed", selector=sel, found=counts, sample=sample)
        else:
            entry["by"] = "missing"
        out[concept] = entry
    return out


def _sample(n):
    from gatelib import domx
    return re.sub(r"\s+", " ", domx.text(n) or n.get("alt") or n.get("src") or n.tag)[:70]


def propose(concept, ctxs):
    """The class-name selector that matches on most of the pages, or None. Needs a match on at least half of them."""
    from gatelib import design
    hint = HINTS.get(concept)
    if not hint:
        return None
    rx, suffix = re.compile(hint[0], re.I), hint[1]
    tokens = Counter()
    for c in ctxs.values():
        for n in c.root().iter():
            if n.tag:
                tokens.update({t for t in n.get("class").split() if rx.search(t)})
    best = None
    for tok in tokens:
        sel = f".{tok}{suffix}"
        counts = {p: len(design.select(c.root(), sel)) for p, c in ctxs.items()}
        hit = sum(1 for v in counts.values() if v)
        if hit * 2 >= len(ctxs) and (best is None or (hit, -len(tok)) > (best[0], -len(best[1]))):
            first = next(c for p, c in ctxs.items() if counts[p])
            best = (hit, tok, sel, counts, _sample(design.select(first.root(), sel)[0]))
    return best and (best[2], best[3], best[4])


def calibrate_lines(results):
    """results: {path: [FAIL lines of the gate]}. Returns [(check id, [paths], first line)] for every detector that FAILed."""
    by = {}
    for path, lines in results.items():
        for ln in lines:
            m = re.search(r"\[([\w.-]+)\]", ln)
            if m:
                by.setdefault(m.group(1), ([], ln))[0].append(path)
    return sorted(((cid, ps, ln) for cid, (ps, ln) in by.items()), key=lambda x: (-len(x[1]), x[0]))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["learn", "calibrate"])
    ap.add_argument("--base", required=True)
    ap.add_argument("--page", action="append", default=[])
    ap.add_argument("--type", default="post", choices=["money", "hub", "post", "core"])
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    from config import CFG, KIT_DIR, PROJECT
    refuse_live(a.base, CFG)
    base = a.base.rstrip("/")
    pages = a.page or ["/"]
    if a.cmd == "learn":
        got = {p: fetch(base + p) for p in pages}
        res = learn(got, CFG, PROJECT)
        for c, e in res.items():
            where = ", ".join(f"{p}:{n}" for p, n in e["found"].items())
            print(f"{c:<14} {e['by']:<9} {e['selector'] or '':<28} {where}  {e['sample']}")
        prop = {c: e["selector"] for c, e in res.items() if e["by"] == "proposed"}
        miss = [c for c, e in res.items() if e["by"] == "missing"]
        print(f"\n{sum(e['by'] == 'meaning' for e in res.values())} found by meaning, {len(prop)} proposed from class names, {len(miss)} not found"
              + (f" ({', '.join(miss)}: a site without that part needs nothing; otherwise map it by hand in design.json)" if miss else "") + ".")
        print("Confirm each proposal by looking at the page (the sample text above) before trusting it.")
        if a.write:
            f = PROJECT / "design.json"
            old = json.loads(f.read_text()) if f.exists() else {}
            old.setdefault("map", {}).update(prop)
            old["_about"] = "Concept -> CSS selector for parts the gate cannot find by meaning. Written by growth design learn; confirmed by the owner."
            old["learned"] = {"on": dt.date.today().isoformat(), "pages": pages}
            f.write_text(json.dumps(old, indent=1) + "\n")
            print(f"wrote {f.name}: {len(prop)} selectors")
        return 0
    results = {}
    for p in pages:
        r = subprocess.run([sys.executable, str(KIT_DIR / "tools" / "gate.py"), "page", p, "--url", base + p, "--type", a.type,
                            "--needs", "live", "--no-browser", "--no-link-status"], capture_output=True, text=True, cwd=PROJECT)
        results[p] = [l for l in r.stdout.splitlines() if l.startswith("FAIL")]
    bad = calibrate_lines(results)
    for cid, ps, ln in bad:
        print(f"SUSPECT {cid}: FAILs on known-good page(s) {', '.join(ps)}\n        {ln[:200]}")
    print(f"\n{len(pages)} known-good page(s): " + (f"{len(bad)} detector(s) SUSPECT. A FAIL here is a detector miss, not a page fault: "
          "map the concept (growth design learn --write, or design.json by hand), or file a kit issue." if bad else "every detector passes. Calibrated."))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
