"""A page's folds are its own words: no fold copies another page of the same site (2.8.2; rule 157a).

words.own-copy: from a real site (23 Nov 2026) an independent reviewer found a "hire experts" page whose 3 folds copied a
sibling hire page: 68 to 88% of their 7-word runs (shingles) were the same. The gate had no cross-page wording check.
The page's folds are read the way words.fact-repeats reads them, and each fold's shingles are compared with every fold of
every other page in the built output (growth.json build_dir). No server is needed; no build means SKIP, never OK.
Limits come from growth.json "words": own_copy {fail, warn, min_words, shared_pages, shared_max_words, shingle} and
own_copy_ok [{path, fold, reason}]."""
from __future__ import annotations

import re
from pathlib import Path

import fingerprint
import paths
from techseo.dom import parse

from . import domx, mainwalk
from .c_repeats import _drop_for_facts
from .c_words import wcfg
from .core import Skip, check, short

DEFAULTS = {"fail": 0.5, "warn": 0.3, "min_words": 40, "shared_pages": 3, "shared_max_words": 40, "shingle": 7}
QUOTE = 12


def settings(ctx):
    cfg = dict(DEFAULTS)
    cfg.update({k: v for k, v in (wcfg(ctx, "own_copy", {}) or {}).items() if k in DEFAULTS and not str(k).startswith("_")})
    return cfg


def _quoted(n):
    """A client's own review or quote is their words, shown on purpose wherever it helps (a Clutch wall, a testimonials page):
    never counted as this page's wording. Only a blockquote, a q or a small element (never a section) with such a class."""
    if n.tag in ("li", "article", "figure") and any(c.tag in ("blockquote", "q") for c in n.iter() if c is not n and c.tag):
        return True                      # a review card: the quote and the name and role under it
    return n.tag in ("blockquote", "q") or (n.tag != "section" and any(
        re.fullmatch(r"(?:\w+[-_]{1,2})?(?:rcard|testimonials?|reviews?|quotes?)(?:[-_]{1,2}\w+)?", c, re.I) for c in n.get("class").split()))


def _drop(n):
    return _drop_for_facts(n) or n.tag in ("fieldset", "label", "legend") or _quoted(n)   # filter labels are controls, not wording


def _words(s):
    return re.findall(r"[a-z0-9]+", s.lower())


def folds_of(root):
    """{fold: [runs]} for the folds of <main> of a parsed page, each run a list of normalized words. The shared chrome (header,
    nav, footer, anything outside <main>) is never read; neither are forms, buttons, dialogs, reason lines and drawn examples."""
    if domx.find(root, "main") is None:
        return {}
    out = {}
    for fold, text in mainwalk.units_of(root, _drop):
        if fold == mainwalk.OUTSIDE and not text.strip():
            continue
        w = _words(text)
        if w:
            out.setdefault(fold, []).append(w)
    return out


def _grams(words, k):
    return [" ".join(words[i:i + k]) for i in range(len(words) - k + 1)]


def other_pages(ctx, root):
    """{site path: {fold: [runs]}} for every other built page; cached for the run. None when there is no build."""
    key = "own-copy-pages"
    if key not in ctx.cache:
        base = fingerprint.build_root(ctx.cfg, ctx.project, ctx.repo)
        ctx.cache[key] = None
        if base and base.is_dir():
            files = sorted(f for f in base.rglob("*.html") if "_astro" not in f.parts and "node_modules" not in f.parts)
            ctx.cache[key] = (base, files)
    got = ctx.cache[key]
    if got is None:
        return None
    base, files = got
    mine = fingerprint._built_file(base, ctx.path) if ctx.path else None
    pages = ctx.cache.setdefault("own-copy-parsed", {})
    out = {}
    for f in files:
        if mine and f.resolve() == mine.resolve():
            continue
        rel = f.relative_to(base).as_posix()
        pth = paths.normalize("/" + re.sub(r"(?:^|/)index\.html$|\.html$", "", rel))
        if pth == paths.normalize(ctx.path or "/") or pth.lower() in ("/404", "/500"):
            continue
        if f not in pages:
            try:
                pages[f] = folds_of(parse(f.read_text(errors="replace")))
            except OSError:
                pages[f] = {}
        if pages[f]:
            out[pth] = pages[f]
    return out


def _longest_run(mine, theirs, k):
    """The longest stretch of consecutive 7-word runs of `mine` that `theirs` also has, as words (at most QUOTE of them)."""
    best, cur = (0, 0), 0
    for i, g in enumerate(_grams(mine, k)):
        if g in theirs:
            cur += 1
            if cur > best[0]:
                best = (cur, i)
        else:
            cur = 0
    n, end = best
    if not n:
        return ""
    start = end - n + 1
    return " ".join(mine[start:start + min(QUOTE, n + k - 1)])


def compare(page_folds, pages, cfg, ok_folds=()):
    """[(fraction, fold, other path, other fold, quote)] for every fold of 40+ words, worst first."""
    k, shared_n, shared_max = int(cfg["shingle"]), int(cfg["shared_pages"]), int(cfg["shared_max_words"])
    where = {}                                   # shingle -> set of pages that have it, in a run short enough to be shared on purpose
    for pth, folds in list(pages.items()) + [("", page_folds)]:
        for runs in folds.values():
            for r in runs:
                if not shared_max or len(r) <= shared_max:
                    for g in set(_grams(r, k)):
                        where.setdefault(g, set()).add(pth)
    index = {}                                   # shingle -> [(page, fold)]
    for pth, folds in pages.items():
        for fold, runs in folds.items():
            for r in runs:
                for g in set(_grams(r, k)):
                    index.setdefault(g, set()).add((pth, fold))
    out = []
    for fold, runs in page_folds.items():
        if fold in ok_folds:
            continue
        words = [w for r in runs for w in r]
        if len(words) < int(cfg["min_words"]):
            continue
        own = {g for r in runs for g in _grams(r, k)
               if not (len(where.get(g, ())) >= shared_n and (not shared_max or len(r) <= shared_max))}
        if not own:
            continue
        hits = {}
        for g in own:
            for key in index.get(g, ()):
                hits[key] = hits.get(key, 0) + 1
        if not hits:
            continue
        (opth, ofold), n = max(hits.items(), key=lambda kv: (kv[1], kv[0]))
        theirs = {g for r in pages[opth][ofold] for g in _grams(r, k)} & own
        quote = max((_longest_run(r, theirs, k) for r in runs), key=lambda q: len(q.split()))
        out.append((n / len(own), fold, opth, ofold, quote))
    return sorted(out, key=lambda t: -t[0])


@check("words.own-copy", "157a", what="a page's folds are its own words: no fold copies a fold of another page of the site", needs="live")
def own_copy(ctx):
    """FAIL when a fold of 40+ words shares 50% or more of its 7-word runs with one fold of another page of the site; WARN from
    30%. The other pages are read from the built output (growth.json build_dir); no build is a SKIP. A run that sits in a short
    block (40 words or fewer) on 3 or more pages is shared on purpose (a call to action's reason line, a trust line) and is not
    counted. growth.json words.own_copy sets the numbers; words.own_copy_ok lists [{path, fold, reason}] that may stay."""
    cfg = settings(ctx)
    root = ctx.root()
    if domx.find(root, "main") is None:
        raise Skip("the page has no <main>, so there are no folds to read")
    pages = other_pages(ctx, root)
    if pages is None:
        raise Skip("no built output to compare with (set build_dir in growth.json and build the site)")
    me = paths.normalize(ctx.path or "/")
    ok_folds, bad = set(), []
    for e in wcfg(ctx, "own_copy_ok", []) or []:
        if isinstance(e, dict) and paths.normalize(str(e.get("path") or "/")) == me:
            if not str(e.get("reason") or "").strip():
                bad.append(f"own_copy_ok entry for {me} fold '{e.get('fold', '*')}' has no reason")
            elif e.get("fold") in (None, "", "*"):
                ok_folds.add("*")
            else:
                ok_folds.add(str(e["fold"]))
    if bad:
        ctx.fail("; ".join(bad), "give each own_copy_ok entry a reason (growth.json words.own_copy_ok)")
        return
    folds = folds_of(root)
    if "*" in ok_folds:
        ctx.ok("every fold is excused by words.own_copy_ok")
        return
    rows = compare(folds, pages, cfg, ok_folds)

    def say(r):
        return (f"fold '{r[1]}' shares {round(r[0] * 100)}% of its {cfg['shingle']}-word runs with fold '{r[3]}' of {r[2]}: "
                f"\"{short(r[4], 120)}\"")
    fails = [r for r in rows if r[0] >= float(cfg["fail"])]
    warns = [r for r in rows if float(cfg["warn"]) <= r[0] < float(cfg["fail"])]
    fix = ("write this fold for this page: its own examples, numbers and wording, not the sibling's with the names swapped "
           "(rule 157a; growth.json words.own_copy_ok lists a fold that may stay, with a reason)")
    if fails:
        ctx.verdict([say(r) for r in fails + warns], "", fix)
    elif warns:
        ctx.warn(f"{len(warns)} fold(s) lean on another page: " + "; ".join(say(r) for r in warns[:4]), fix)
    else:
        worst = f", most alike {round(rows[0][0] * 100)}% ({rows[0][2]})" if rows else ""
        ctx.ok(f"{len(folds)} folds read against {len(pages)} other pages: none copies another page{worst}")
