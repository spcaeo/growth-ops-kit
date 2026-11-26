#!/usr/bin/env python3
"""The project's brand kit: brand guidelines, colour guidelines and design tokens, made from the site, fine-tuned by the owner, reusable.

  growth brand-kit learn --base <preview address> [--page /about --page /pricing] [--max-pages 5]
  growth brand-kit set <path> <value>      e.g.  growth brand-kit set colors.primary "#0B6E4F"
  growth brand-kit unset <path>            go back to what the site says
  growth brand-kit show [path]             every value and where it came from (site, override, default)
  growth brand-kit build                   guidelines page, guidelines text, CSS / DTCG / Tailwind / SCSS tokens
  growth brand-kit check                   is brand.json valid, do the body and button colours pass WCAG AA, are the builds current
  growth brand-kit export <dir>            copy the built kit out, to use in another project
  growth brand-kit import <dir or brand.json> [--force]   start this project from another project's kit

Files, in <project>/brand/:
  brand.generated.json   what `learn` read from the site (colours by painted area and their roles, fonts, type scale, spacing, radius,
                         shadows, button and link states, logo and icons; the name, calls to action and contact facts from
                         docs/brand-scan.json; the voice and the words never to use from BRAND.md). Written by learn only.
  brand.overrides.json   the owner's changes, by hand or through set / unset / import. `learn` never touches it.
  brand.json             the merge: overrides win; every value says "source": site, override or default.
  brand-guidelines.html, BRAND-GUIDELINES.md, exports/tokens.css, tokens.json (W3C design tokens), tailwind.brand.cjs, tokens.scss

`learn` opens one headless browser on 3 to 6 pages of the PREVIEW (never the live host of a no-crawl project: it is refused, and the
browser is stopped from asking it). It hovers a few buttons, nothing else is clicked. Building twice gives the same bytes.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from brandkit import ops, store, tokens  # noqa: E402


def _project():
    import config
    return config.PROJECT, config.CFG, config.TZ


def cmd_learn(a):
    project, cfg, tz = _project()
    from brandkit import learn as L
    base = (a.base or cfg.get("preview_url") or "").rstrip("/")
    if not base:
        sys.exit("Give --base <preview address> (growth.json has no preview_url).")
    gen = L.learn(project, cfg, base, a.page, max(1, min(a.max_pages, 8)), datetime.now(tz).strftime("%Y-%m-%d"))
    tree = store.current_tree(project)
    meta = gen.get("meta") or {}
    print(f"Brand kit learned from {len(meta.get('pages', []))} page(s) of {base}.")
    for e in meta.get("errors", []):
        print(f"  could not read {e}")
    print("Colours:")
    for r in store.ROLES:
        n = (tree.get("colors") or {}).get(r)
        if store.is_leaf(n):
            print(f"  {r.ljust(10)} {n['value']}  {n['source']:8} {n.get('evidence', '')}")
    for role in ("heading", "body", "mono"):
        n = (tree.get("typography") or {}).get("families", {}).get(role)
        if store.is_leaf(n):
            print(f"Font {role}: {n['value']} (weights {', '.join(str(w) for w in n.get('weights') or [])}) [{n['source']}]")
    h1 = store.val(tree, "typography.scale.h1")
    print(f"Sizes: h1 {h1}, body {store.val(tree, 'typography.scale.body')}")
    if not (gen.get("colors") or {}).get("primary"):
        print("No button or brand colour was found: the primary colour is a default. Set it with: growth brand-kit set colors.primary \"#...\"")
    print("Written: brand/brand.generated.json and brand/brand.json (your overrides were not touched). Next: growth brand-kit build")
    return 0


def cmd_set(a):
    project, _cfg, _tz = _project()
    d = store.brand_dir(project)
    tree = store.current_tree(project)
    ovr = store.read_json(d / "brand.overrides.json", {}) or {}
    try:
        full = store.set_override(ovr, tree, a.path, store.coerce(a.value))
    except ValueError as e:
        sys.exit(f"Not changed: {e}")
    d.mkdir(parents=True, exist_ok=True)
    (d / "brand.overrides.json").write_text(store.dump(ovr))
    new = store.write_merged(project)
    node = store.get(new, full.rsplit(".", 1)[0]) if full.endswith(".value") else None
    was = node.get("was") if isinstance(node, dict) else None
    print(f"Set {full} = {store.get(new, full)!r}" + (f" (the site said {was!r})" if was is not None else "") + ". Next: growth brand-kit build")
    return 0


def cmd_unset(a):
    project, _cfg, _tz = _project()
    d = store.brand_dir(project)
    ovr = store.read_json(d / "brand.overrides.json", {}) or {}
    if not store.unset_override(ovr, a.path):
        sys.exit(f"No override at {a.path}. Overrides in brand/brand.overrides.json: {', '.join(p for p, _ in store._walk(ovr)) or 'none'}")
    (d / "brand.overrides.json").write_text(store.dump(ovr))
    store.write_merged(project)
    print(f"Removed the override at {a.path}; the value is back to what the site says (or the default). Next: growth brand-kit build")
    return 0


def cmd_show(a):
    project, _cfg, _tz = _project()
    tree = store.current_tree(project)
    node = store.get(tree, a.path) if a.path else tree
    if node is None:
        sys.exit(f"No value at {a.path}")
    for path, lf in store._walk(node, a.path or ""):
        v = lf["value"]
        v = v if not isinstance(v, (list, dict)) else str(v)[:60]
        print(f"{path.ljust(52)} {str(v)[:44].ljust(44)} {lf.get('source', ''):8} {lf.get('evidence', '')[:50]}")
    return 0


def cmd_build(a):
    project, _cfg, _tz = _project()
    files = ops.build(project)
    print("Built: " + ", ".join(files))
    bad = tokens.failures(store.current_tree(project))
    if bad:
        print(f"{len(bad)} body or button colour pair(s) are under WCAG AA (growth brand-kit check lists them).")
    return 0


def cmd_check(a):
    project, _cfg, _tz = _project()
    r = ops.check(project)
    for p in r["problems"]:
        print(f"PROBLEM  {p}")
    for row in r["contrast"]:
        print(f"CONTRAST {row['label']}: {row['fg']} on {row['bg']} is {row['ratio']}:1, AA needs {'4.5' if row['grade'] == 'fail' else '3'}:1 "
              f"(change {row['fg_name']} or {row['bg_name']} with growth brand-kit set)")
    for s in r["stale"]:
        print(f"STALE    {s}")
    n = len(r["problems"]) + len(r["contrast"]) + len(r["stale"])
    print("Brand kit OK: valid, body and button colours pass AA, builds current." if not n else f"{n} thing(s) to fix.")
    return 1 if n else 0


def cmd_export(a):
    project, _cfg, _tz = _project()
    files = ops.export_kit(project, a.dir)
    print(f"Exported {len(files)} files to {a.dir}. In the other project: growth brand-kit import {a.dir}")
    return 0


def cmd_import(a):
    project, _cfg, _tz = _project()
    try:
        print(ops.import_kit(project, a.src, a.force) + ". Next: growth brand-kit build (and learn, if you want this site's own values under yours)")
    except ValueError as e:
        sys.exit(str(e))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="growth brand-kit", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("learn", help="read the site's look into brand.generated.json")
    p.add_argument("--base", default="", help="the preview or local address to read (default: growth.json preview_url); the live host of a no-crawl project is refused")
    p.add_argument("--page", action="append", help="a page to read (path or address); repeat. Default: the home page and pages that differ, from the inventory or sitemap")
    p.add_argument("--max-pages", type=int, default=5, help="pages to read when none is named (default 5)")
    p.set_defaults(fn=cmd_learn)
    p = sub.add_parser("set", help="change one value")
    p.add_argument("path")
    p.add_argument("value")
    p.set_defaults(fn=cmd_set)
    p = sub.add_parser("unset", help="remove an override")
    p.add_argument("path")
    p.set_defaults(fn=cmd_unset)
    p = sub.add_parser("show", help="print values and where they came from")
    p.add_argument("path", nargs="?", default="")
    p.set_defaults(fn=cmd_show)
    sub.add_parser("build", help="write the guidelines and the token files").set_defaults(fn=cmd_build)
    sub.add_parser("check", help="validate and check contrast and freshness").set_defaults(fn=cmd_check)
    p = sub.add_parser("export", help="copy the built kit to a folder")
    p.add_argument("dir")
    p.set_defaults(fn=cmd_export)
    p = sub.add_parser("import", help="start from another project's kit")
    p.add_argument("src")
    p.add_argument("--force", action="store_true", help="replace overrides that already hold changes")
    p.set_defaults(fn=cmd_import)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
