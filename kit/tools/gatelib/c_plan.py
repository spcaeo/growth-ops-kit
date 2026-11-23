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


PLACEHOLDER = re.compile(r"(?i)^(tbd|todo|tba|\?+|-+|x|same|same as above|see above|later|wip|na|n/a|none|\.{2,})$")


def answered(v: str) -> bool:
    """A field is answered by a real answer, short or long ("plain", "sage tint"), or "n/a: <reason>". Placeholders
    (tbd, todo, ?, -, same, see above, bare n/a or none) are not answers (2.4.6: the old 12-character floor rejected
    true short answers)."""
    v = v.strip()
    if v.lower().startswith("n/a:"):
        return len(v) > 5
    return len(v) >= 4 and not PLACEHOLDER.match(v)


def problems(plan, page_folds):
    """List what is missing from a plan, against the folds actually on the page (their data-fold names)."""
    out = []
    if not isinstance(plan, dict):
        return ["no plan file (growth fold_plan init <path> --url <local URL>)"]
    folds = plan.get("folds") or []
    if not folds:
        out.append("the plan lists no folds (growth fold_plan init <path> --url <local URL>; a new page: --folds \"Hero;Proof;...\" and use those names as data-fold)")
    names = [f.get("fold", "") for f in folds]
    for want in page_folds:
        if want not in names:
            out.append(f"fold '{want}' is on the page but not in the plan")
    for f in folds:
        for k in FOLD_FIELDS:
            v = str(f.get(k, "")).strip()
            if not answered(v):
                out.append(f"fold '{f.get('fold', '?')}': '{k}' not answered")
    sh = plan.get("shared") or {}
    for s in SHARED:
        for k in SHARED_FIELDS:
            v = str((sh.get(s) or {}).get(k, "")).strip()
            if not answered(v):
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


# ---- 2.7.0: a plan is written for its page, and the page follows it ----------------------------------------------------
COPY_FREE = ("check", "icons")     # fields that may honestly read the same on every fold (the shared icon set, how it is checked)
COPIED_PAGES = 3                   # the same answer on this many different pages is a copied template, not a plan
NO = re.compile(r"(?i)^\s*(no|none|n/a|nothing)\b")


def norm(v):
    return re.sub(r"\s+", " ", str(v)).strip().lower()


def project_answers(project):
    """{field: {normalized answer: set of plan files}} over every plan of the project."""
    import glob
    out = {}
    for f in glob.glob(str(project / "research" / "plans" / "*.json")):
        for fd in (load(pathlib_path(f)) or {}).get("folds") or []:
            for k in FOLD_FIELDS:
                v = norm(fd.get(k, ""))
                if v:
                    out.setdefault(k, {}).setdefault(v, set()).add(f)
    return out


def pathlib_path(f):
    from pathlib import Path
    return Path(f)


def copied(plan, path, answers):
    """Fields of this plan whose exact answer also stands in the plans of COPIED_PAGES or more pages."""
    out = []
    for fd in plan.get("folds") or []:
        for k in FOLD_FIELDS:
            if k in COPY_FREE:
                continue
            v = norm(fd.get(k, ""))
            files = (answers.get(k) or {}).get(v, set())
            if v and len(files) >= COPIED_PAGES:
                out.append(f"fold '{fd.get('fold', '?')}': '{k}' is the same sentence as on {len(files) - 1} other page(s): '{v[:60]}'")
    return out


@check("ev.fold-plan-own", "36h", what="every fold plan is written for its own page: no field answer copied from three or more pages", needs="project")
def fold_plan_own(ctx):
    """From a real site (22 Nov 2026): 86% of 10,248 plan answers were one template sentence repeated across pages
    ("the fold heading, as a buyer would say it" 119 times), so ev.fold-plan passed while no fold had been designed."""
    key = ctx.need_key()
    path = ctx.project / "research" / "plans" / f"{key}.json"
    plan = load(path)
    if not isinstance(plan, dict):
        ctx.fail("no plan file", f"growth fold_plan init <path> --url <local URL> --key {key} (rule 36h)")
        return
    probs = copied(plan, str(path), project_answers(ctx.project))
    ctx.verdict(probs[:10] + ([f"+{len(probs) - 10} more"] if len(probs) > 10 else []),
                f"plan {path.name}: every answer is this page's own",
                "write each field for this fold: its real headline, what its picture shows, its links' exact words, its controls and states, what moves, its 390 order, its events (rule 36h)")


@check("ev.fold-plan-match", "36h", what="the built page follows its fold plan: surface, job, headline, call to action, controls and picture fold by fold", needs="live")
def fold_plan_match(ctx):
    from . import domx
    from .c_links import JOBS, SURFACES
    key = ctx.need_key()
    plan = load(ctx.project / "research" / "plans" / f"{key}.json")
    if not isinstance(plan, dict):
        from .core import Skip
        raise Skip("no plan file to compare with (ev.fold-plan reports the missing plan)")
    secs = {s.get("data-fold"): s for s in ctx.root().iter() if s.tag == "section" and s.get("data-fold")}
    probs = []
    for fd in plan.get("folds") or []:
        name, s = fd.get("fold", ""), secs.get(fd.get("fold", ""))
        if s is None:
            probs.append(f"fold '{name}' is planned but not on the page")
            continue
        sf = next((w for w in re.findall(r"[a-z-]+", norm(fd.get("surface", ""))) if w in SURFACES), None)
        if sf and s.get("data-surface") and sf != s.get("data-surface"):
            probs.append(f"fold '{name}': planned surface {sf}, built {s.get('data-surface')}")
        jb = next((w for w in re.findall(r"[a-z]+", norm(fd.get("job", ""))[:40]) if w in JOBS), None)
        if jb and s.get("data-job") and jb != s.get("data-job"):
            probs.append(f"fold '{name}': planned job {jb}, built {s.get('data-job')}")
        heads = [domx.text(h) for h in s.iter() if h.tag in ("h1", "h2", "h3")][:2]
        want = set(re.findall(r"[a-z0-9]{4,}", norm(fd.get("headline", ""))))
        got = set(re.findall(r"[a-z0-9]{4,}", " ".join(heads).lower()))
        if heads and want and len(want & got) < max(1, min(3, len(got)) // 2):
            probs.append(f"fold '{name}': the planned headline does not match the built heading '{heads[0][:50]}'")
        asks = domx.booking_links(ctx, s)
        cta = str(fd.get("cta", ""))
        if NO.match(cta) and asks:
            probs.append(f"fold '{name}': the plan says no call to action, the page has {len(asks)}")
        elif cta and not NO.match(cta) and re.search(r"(?i)book|call|button|ask|form", cta) and not asks and not any(n.tag == "form" for n in s.iter()):
            probs.append(f"fold '{name}': the plan has a call to action, the page has none")
        ctl = str(fd.get("controls", ""))
        has_ctl = any(n.tag in ("input", "select", "textarea", "details") or (n.tag == "button" and not n.get("aria-label", "").lower().startswith("copy"))
                      or "data-tool" in n.attrs for n in s.iter() if n.tag)
        if ctl and not NO.match(ctl) and not has_ctl:
            probs.append(f"fold '{name}': the plan describes controls, the page has none")
        vis = str(fd.get("visual", ""))
        has_pic = any(n.tag in ("svg", "img", "picture", "canvas", "figure", "table") for n in s.iter() if n.tag)
        if vis and not NO.match(vis) and not has_pic:
            probs.append(f"fold '{name}': the plan describes a picture, the page has none")
    ctx.verdict(probs[:10] + ([f"+{len(probs) - 10} more"] if len(probs) > 10 else []),
                f"{len(plan.get('folds') or [])} folds built as planned",
                "build each fold as its plan says, or change the plan with the reason when the build is better (rule 36h)")
