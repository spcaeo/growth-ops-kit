"""Checks that READ the page's research record (research/<key>-record.json), not only its file name (#53, #43, #50).

The older ev.research-check still asks for a dated fact-check file; these checks open the structured record and hold the
page to it: every number about another product has a row read within N days by raw text or a real browser (never a
summary), every chosen People-also-ask question is answered, and the re-checks sit on the release date plus 7/14/28/56."""
from __future__ import annotations

import datetime as dt

import research  # noqa: E402  kit/tools/research.py

from . import domx
from .core import Skip, check
from .c_evidence import at, tz

WINDOWS = (7, 14, 28, 56)


def record(ctx):
    return research.load(ctx.project, ctx.need_key())


def need_record(ctx):
    rec = record(ctx)
    if rec is None:
        raise Skip(f"no research record yet (growth research init {ctx.path} --key {ctx.key}); ev.research-record fails until there is one", blocked=True)
    return rec


def page_words(ctx):
    return domx.text(domx.body(ctx.root()))


@check("ev.research-record", "5", what="the page's research record exists and is complete: search window, AI answers, PAA, vendor facts read by raw text or browser, all dated", needs="project")
def research_record(ctx):
    rec = record(ctx)
    if rec is None:
        ctx.fail("no research record", f"growth research init {ctx.need_path()} --key {ctx.key}, then fill it (growth research search/paa/ai/fact; book/playbooks/update-post.md)")
        return
    ctx.verdict(research.problems(rec, ctx.today, ctx.cfg),
                f"record {ctx.key}-record.json: {len(rec.get('vendor_facts') or [])} vendor facts, {len(rec.get('paa') or [])} PAA questions, search to {(rec.get('search') or {}).get('window', {}).get('to')}",
                "fix the record (growth research check <path> --key K lists each gap); a number read only from a summary tool does not count (rule 5)")


@check("ev.vendor-numbers", "7", what="every amount of money on the page is a vendor fact row in the research record, read within the window", needs="live")
def vendor_numbers(ctx):
    rec = need_record(ctx)
    ctx.verdict(research.vendor_number_problems(rec, page_words(ctx), ctx.today, ctx.cfg),
                "every amount on the page has a fresh vendor fact row",
                "add the row with growth research fact (the vendor's own words, the view it was read in), re-read it if it is old, or list the number in other_numbers with a why (rules 5, 7)")


@check("ev.paa-answered", "5", what="every chosen People-also-ask question is answered on the page", needs="live")
def paa_answered(ctx):
    rec = need_record(ctx)
    ctx.verdict(research.paa_problems(rec, page_words(ctx)), f"{sum(1 for q in rec.get('paa') or [] if q.get('status') == 'chosen')} chosen PAA questions are answered",
                "answer the question on the page (its words or an answered_in line from the page), or decline it with a reason: growth research paa (rule 5)")


def release_date(ctx):
    rel = [e for e in ctx.page_entries() if "release" in (e.get("tags") or [])]
    d = research.day(rel[-1].get("at", "")) if rel else None
    return d, rel[-1] if rel else None


@check("ev.rechecks-release", "OR-measure", what="re-checks sit on this release's date plus 7, 14, 28 and 56 days", stage="release", needs="project")
def rechecks_release(ctx):
    d, rel = release_date(ctx)
    if d is None:
        ctx.fail("no release filed for this page (journal tag release), so the re-checks have no date to hang on",
                 "file the release first (growth journal add --page <path> --tag release), then growth measure schedule <path> --release <date>")
        return
    t = tz(ctx)
    mine = [e for e in ctx.page_entries() if e.get("recheck_on") and (at(e, t) or dt.datetime.min.replace(tzinfo=t)) >= (at(rel, t) or dt.datetime.min.replace(tzinfo=t))]
    have = {x for e in mine if (x := research.day(e["recheck_on"]))}
    miss = [f"day {n} ({(d + dt.timedelta(days=n)).isoformat()})" for n in WINDOWS if (d + dt.timedelta(days=n)) not in have]
    ctx.verdict(miss, f"re-checks on release {d.isoformat()} + 7/14/28/56",
                f"growth measure schedule {ctx.path} --release {d.isoformat()} files the four re-checks on their dates")
