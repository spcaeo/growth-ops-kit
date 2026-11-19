"""Rule 36h: a fold-by-fold detail plan exists before a page is optimized (from a real project: "the AI needs to pay
attention to the smallest details for each page element and each fold ... and it needs a proper plan when it starts to
optimize any page"). The plan is research/plans/<key>.json, written with growth fold_plan; every fold on the page and
every shared element has every detail field answered (or "n/a: <reason>")."""
from __future__ import annotations

import json
import re

from .core import check

import paths  # noqa: E402  kit/tools/paths.py: one form of a site path

# Every fold answers these. Each one is a lesson learned on a first money page.
FOLD_FIELDS = {
    "job": "the fold's job in the reader's mind (hook, show, compare, reassure, prove, relief, act, read, answer) and the one thing they should think after it",
    "surface": "its background (plain, tint, warm, geo-grid, geo-lines, geo-contour, geo-hatch, dark), different from its neighbours (36f)",
    "headline": "the headline as a buyer would say it, and the search or question it answers",
    "copy": "answer first, plain words, sentence lengths; every claim with its source on the site or the owner's yes",
    "visual": "the picture or chart: one idea, readable in 3 seconds, in the project's style, true to the real thing (e.g. the right product shown) (36g)",
    "edge_cases": "what the visual and numbers do with extreme inputs (tiny, huge, zero) and long text",
    "links": "in-text links: target pages and their exact words, blue with '+', a space before and after, punctuation after the '+' (36c, 88b)",
    "cta": "the call to action here (or none and why): label with a reason, glow only on the primary (32a, 32c)",
    "controls": "every interactive control: its hint, its states (empty, working, result), keyboard and touch (36a)",
    "icons": "ticks, icons and markers from the shared components (circled Tick, 36e)",
    "motion": "what moves and when, and the reduced-motion version",
    "mobile": "the 390 px layout: order, wrapping, nothing hidden, no sideways scroll",
    "analytics": "the events this fold sends",
    "check": "how the result will be checked: screenshots at 1366 and 390, the 3-second test, the gate",
}
SHARED = ["header", "sticky_bar", "exit_offer", "link_previews", "footer", "schema", "speed"]
SHARED_FIELDS = {"plan": "what it does on this page", "detail": "the small details to get right", "check": "how it is checked"}


def load(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def problems(plan, page_folds):
    """List what is missing from a plan, against the folds actually on the page (their data-fold names)."""
    out = []
    if not isinstance(plan, dict):
        return ["no plan file (growth fold_plan init <path> --url <local URL>)"]
    folds = plan.get("folds") or []
    if not folds:
        out.append("the plan lists no folds (growth fold_plan init <path> --url <local URL>, or list the planned folds by hand)")
    names = [f.get("fold", "") for f in folds]
    for want in page_folds:
        if want not in names:
            out.append(f"fold '{want}' is on the page but not in the plan")
    for f in folds:
        for k in FOLD_FIELDS:
            v = str(f.get(k, "")).strip()
            if len(v) < 12 and not v.lower().startswith("n/a:"):
                out.append(f"fold '{f.get('fold', '?')}': '{k}' not answered")
    sh = plan.get("shared") or {}
    for s in SHARED:
        for k in SHARED_FIELDS:
            v = str((sh.get(s) or {}).get(k, "")).strip()
            if len(v) < 12 and not v.lower().startswith("n/a:"):
                out.append(f"shared '{s}': '{k}' not answered")
    if not str(plan.get("goal", "")).strip():
        out.append("no page goal")
    return out


def page_folds(html):
    m = re.search(r"<main\b.*?</main>", html, re.S)
    return re.findall(r'<section\b[^>]*\bdata-fold="([^"]+)"', m.group(0) if m else html)


@check("ev.fold-plan", "36h", what="a fold-by-fold detail plan exists for the page and answers every field for every fold and shared element", needs="project")
def fold_plan(ctx):
    key = ctx.need_key()
    path = ctx.project / "research" / "plans" / f"{key}.json"
    folds = page_folds(ctx.html) if ctx.html else []
    probs = problems(load(path), folds)
    ctx.verdict(probs, f"plan {path.name}: {len(folds)} folds and {len(SHARED)} shared elements answered",
                f"growth fold_plan init <path> --url <local URL> --key {key}, then answer every field (rule 36h)")


def _archive(ctx, stage):
    path = ctx.need_path()
    import paths
    slug = paths.snapshot_slug(path)
    d = ctx.project / "archive" / "pages" / slug
    runs = sorted(x for x in d.glob(f"*-{stage}") if x.is_dir()) if d.exists() else []
    need = ("desktop-1366.png", "mobile-390.png", "page.html", "meta.json")
    good = [r for r in runs if all((r / n).exists() for n in need)]
    return d, runs, good


@check("ev.archive-before", "36i", what="the live page was archived before any change ships: full-page images at 1366 and 390 plus its HTML", needs="project")
def archive_before(ctx):
    if paths.key(ctx.need_path()) in {paths.key(p) for p in ctx.cfg.get("new_pages", [])}:
        ctx.ok("new page: nothing live to archive before (growth.json new_pages)")
        return
    d, runs, good = _archive(ctx, "before")
    probs = [] if good else [f"no complete 'before' capture in {d.relative_to(ctx.project)}" + (f" ({runs[-1].name} is incomplete)" if runs else "")]
    ctx.verdict(probs, f"before: {good[-1].name if good else ''}",
                f"growth page_archive capture {ctx.path} --stage before (rule 36i)")


@check("ev.archive-after", "36i", what="the live page was archived after release, next to its 'before' capture", stage="release", needs="project")
def archive_after(ctx):
    d, _, before = _archive(ctx, "before")
    _, runs, good = _archive(ctx, "after")
    probs = []
    if not good:
        probs.append(f"no complete 'after' capture in {d.relative_to(ctx.project)}")
    elif before and good[-1].name < before[-1].name:
        probs.append("the newest 'after' capture is older than the newest 'before'")
    ctx.verdict(probs, f"after: {good[-1].name if good else ''}",
                f"growth page_archive capture {ctx.path} --stage after, once the release is live (rule 36i)")
