"""Design-agnostic gate (gatelib/design.py): the same page concepts found on two very different designs.

SEMANTIC is a page built with landmarks, schema.org and microdata; CLASSES is a page built from class names only, read
through a growth.json "design" map. Both pass the rewritten detectors; seeded faults (a cover with no alt, a missing
date, a drifted FAQ, a table with no source, a number only in a box, a bare booking label) fail on both. Also:
design_exceptions print a WARN with the reason and FAIL again when their task is done or their date has passed.
Example markup only (example.com). No network."""
import copy
import datetime as dt
import json
import tempfile
from pathlib import Path

import pytest

from gatelib import CHECKS
from gatelib.core import Ctx, run_check
from gatelib.design import select

LD = json.dumps([
    {"@context": "https://schema.org", "@type": "BlogPosting", "headline": "Best mowing height", "dateModified": "2026-11-18",
     "image": {"@type": "ImageObject", "url": "https://www.example.com/img/mowing-cover-abc123.jpg"},
     "author": {"@type": "Person", "name": "Pat Doe", "url": "https://www.example.com/author/pat/"}},
    {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": "How high should I mow?", "acceptedAnswer": {"@type": "Answer", "text": "Three inches suits most lawns. Cut a third at most."}},
        {"@type": "Question", "name": "When is the best time to mow?", "acceptedAnswer": {"@type": "Answer", "text": "Weekly in spring is right for most lawns. Less in summer."}},
        {"@type": "Question", "name": "Should I bag clippings?", "acceptedAnswer": {"@type": "Answer", "text": "No, leave them on the lawn. They feed it."}}]}])

FAQ = ("<details><summary><h3>How high should I mow?</h3></summary><p>Three inches suits most lawns. Cut a third at most.</p></details>"
       "<details><summary><h3>When is the best time to mow?</h3></summary><p>Weekly in spring is right for most lawns. Less in summer.</p></details>"
       "<details><summary><h3>Should I bag clippings?</h3></summary><p>No, leave them on the lawn. They feed it.</p></details>")
TABLE = "<table><caption>Mower prices</caption><tr><th>Mower</th><th>Price</th></tr><tr><td>A</td><td>$300</td></tr></table>"

SEMANTIC = f"""<html><head><title>Best mowing height</title><script type="application/ld+json">{LD}</script></head><body>
<header><a href="/">Example</a><a class="btn" href="/contact/">Get a quote</a></header>
<main><article>
<details><summary>On this page</summary><a href="#a">A</a></details>
<h1>Best mowing height</h1>
<p>By <a rel="author" href="/author/pat/">Pat Doe</a> · Updated <time itemprop="dateModified" datetime="2026-11-18">Nov 18, 2026</time></p>
<p>We are a lawn-care partner of the mower brands below.</p>
<figure><img itemprop="image" src="/img/mowing-cover-abc123.jpg" alt="A lawn being mowed"></figure>
<p>4 min left</p>
<h2>Prices</h2><div data-checked="2026-11-18" data-source="https://www.example.com/mowers"><div class="t">{TABLE}</div></div>
<div data-calculator><aside><p>$1,234 a year</p></aside></div>
<h2>Frequently asked questions</h2>{FAQ}
<h2>Next</h2><p>Quote in a day.</p><p><a href="/contact/">Get a quote</a> for a lawn quote in a day.</p>
</article></main>
<footer><a href="/about/">About</a></footer></body></html>"""

CLASSES = f"""<html><head><title>Best mowing height</title><script type="application/ld+json">{LD}</script></head><body>
<div class="top-bar"><a href="/">Example</a></div>
<div class="content"><div class="post">
<div class="toc-box"><details><summary>Contents</summary><a href="#a">A</a></details></div>
<h1>Best mowing height</h1>
<div class="meta"><a class="who" href="/author/pat/">Pat Doe</a> · Updated <span class="stamp">Nov 18, 2026</span></div>
<p>We are a lawn-care partner of the mower brands below.</p>
<div class="hero-pic"><img src="/static/hero.jpg" alt="A lawn being mowed"></div>
<span class="left">4 min left</span>
<h2>Prices</h2><div class="t">{TABLE}</div><p>Sources: each maker's price page, checked Nov 18, 2026.</p>
<div class="calc"><div class="callout"><p>$1,234 a year</p></div></div>
<h2>Questions people ask</h2><div class="qa">{FAQ}</div>
</div></div>
<div class="bottom"><a href="/about/">About</a></div></body></html>"""

DESIGN = {"site_header": ".top-bar", "site_footer": ".bottom", "main": ".content", "cover_image": ".hero-pic img",
          "byline": "a.who", "updated_date": ".meta .stamp", "faq_question": ".qa details"}
BASE = {"site_url": "https://www.example.com", "name": "Example", "product": "Example",
        "default_author": {"name": "Pat Doe", "path": "/author/pat/", "slug": "pat"},
        "disclosure_pattern": r"\bwe are a [\w-]+ partner\b", "conversion_path": "/contact/",
        "cta": {"label": "Get a quote", "contact_path": "/contact/", "reason_words": "quote|day"},
        "box_ignore": [{"selector": ".calc", "why": "the calculator's computed sums"}]}


def run(html, cid, cfg, ptype="post", docs=None):
    with tempfile.TemporaryDirectory() as tmp:
        ctx = Ctx(project=Path(tmp), path="/blog/best-mowing-height/", url="http://127.0.0.1:9/blog/best-mowing-height/",
                  ptype=ptype, cfg=cfg, html=html, status=200, docs=docs, today=dt.date(2026, 11, 19))
        run_check(ctx, CHECKS[cid])
        return ctx.lines[0]


PAGES = [("semantic", SEMANTIC, BASE), ("classes", CLASSES, {**BASE, "design": DESIGN})]
CHECKS_OK = ["faq.schema-equal", "post.cover", "words.disclosure", "words.named-author", "geo.table-sources",
             "claims.box-numbers", "layout.shared-frame"]


@pytest.mark.parametrize("name,html,cfg", PAGES, ids=[p[0] for p in PAGES])
@pytest.mark.parametrize("cid", CHECKS_OK)
def test_both_designs_pass(name, html, cfg, cid):
    line = run(html, cid, cfg)
    assert line.level == "OK", (name, cid, line.what)


@pytest.mark.parametrize("name,html,cfg", PAGES, ids=[p[0] for p in PAGES])
def test_the_updated_date_and_reading_aid_are_found(name, html, cfg):
    from gatelib import design
    with tempfile.TemporaryDirectory() as tmp:
        ctx = Ctx(project=Path(tmp), path="/x", cfg=cfg, html=html, status=200)
        assert design.find(ctx, "reading_aid"), name
        assert design.find(ctx, "updated_date"), name
        assert [q for q, _ in design.faq_items(ctx)] == ["How high should I mow?", "When is the best time to mow?", "Should I bag clippings?"]


FAULTS = [
    ("post.cover", ('alt="A lawn being mowed"', 'alt=""')),
    ("faq.schema-equal", ("Less in summer.</p>", "Less in late summer, and never in a drought.</p>")),   # the visible answer only
    ("geo.table-sources", ('data-checked="2026-11-18" ', ""), ("Sources: each maker's price page, checked Nov 18, 2026.", "")),
    ("words.disclosure", ("We are a lawn-care partner of the mower brands below.", "Here are the mowers.")),
]


@pytest.mark.parametrize("name,html,cfg", PAGES, ids=[p[0] for p in PAGES])
@pytest.mark.parametrize("fault", FAULTS, ids=[f[0] for f in FAULTS])
def test_seeded_faults_fail_on_both_designs(name, html, cfg, fault):
    cid, *swaps = fault
    for old, new in swaps:
        html = html.replace(old, new)
    assert run(html, cid, cfg).level == "FAIL", (name, cid)


def test_a_number_only_in_a_real_box_still_fails():
    html = SEMANTIC.replace("<h2>Next</h2>", '<aside class="takeaway"><p>Saves 37% a year</p></aside><h2>Next</h2>')
    assert run(html, "claims.box-numbers", BASE).level == "FAIL"


def test_the_sites_own_label_with_a_reason_line_is_not_bare_but_a_bare_one_is():
    assert run(SEMANTIC, "cta.no-bare-book", {**BASE, "cta": {**BASE["cta"], "label": "Get a quote"}}).level == "OK"
    bare = SEMANTIC.replace("<p><a href=\"/contact/\">Get a quote</a> for a lawn quote in a day.</p>", "<p><a href=\"/contact/\">Book a call</a></p>")
    assert run(bare, "cta.no-bare-book", BASE).level == "FAIL"


def _approve(docs, exc):
    import approvals
    approvals.record(docs, "exception", exc["check"], exc, "test approval", by="owner")


@pytest.fixture
def owner_home(tmp_path, monkeypatch):
    (tmp_path / "home").mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))       # never the real signing key


# Updated for audit C3: an exception now needs an 'until' within 30 days and the owner's approval (growth approve), so the
# old test's exceptions without either no longer excuse anything; the expiry and task rules are kept.
def test_design_exceptions_warn_with_their_reason_and_expire(tmp_path, owner_home):
    html = SEMANTIC.replace('alt="A lawn being mowed"', 'alt=""')
    until = (dt.date.today() + dt.timedelta(days=20)).isoformat()
    exc = {"check": "post.cover", "why": "covers are decorative on this site", "task": "T9", "until": until}
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "tasks.json").write_text(json.dumps({"tasks": [{"id": "T9", "status": "doing", "steps": []}]}))
    _approve(docs, exc)
    line = run(html, "post.cover", {**BASE, "design_exceptions": [exc]}, docs=docs)
    assert line.level == "WARN" and "covers are decorative on this site" in line.what and "task T9" in line.what
    assert "owner approval A0001" in line.what
    (docs / "tasks.json").write_text(json.dumps({"tasks": [{"id": "T9", "status": "done", "steps": []}]}))
    assert run(html, "post.cover", {**BASE, "design_exceptions": [exc]}, docs=docs).level == "FAIL"       # task done
    old = {"check": "post.cover", "why": "covers are decorative on this site", "until": "2026-11-01"}
    _approve(docs, old)
    assert run(html, "post.cover", {**BASE, "design_exceptions": [old]}, docs=docs).level == "FAIL"       # date passed
    assert run(html, "post.cover", {**BASE, "design_exceptions": [{"check": "post.cover"}]}, docs=docs).level == "FAIL"  # no reason


def test_an_exception_the_owner_did_not_approve_excuses_nothing(tmp_path, owner_home):
    """audit C3: before, any entry the agent typed into growth.json turned a FAIL into a WARN."""
    html = SEMANTIC.replace('alt="A lawn being mowed"', 'alt=""')
    exc = {"check": "post.cover", "why": "covers are decorative on this site", "until": (dt.date.today() + dt.timedelta(days=5)).isoformat()}
    docs = tmp_path / "docs"
    docs.mkdir()
    line = run(html, "post.cover", {**BASE, "design_exceptions": [exc]}, docs=docs)
    assert line.level == "FAIL" and "no owner approval" in line.what and "growth approve exception post.cover" in line.what
    _approve(docs, exc)
    changed = {**exc, "why": "covers are decorative on this site, and more"}
    line = run(html, "post.cover", {**BASE, "design_exceptions": [changed]}, docs=docs)
    assert line.level == "FAIL" and "changed after the owner approved it" in line.what
    far = {**exc, "until": (dt.date.today() + dt.timedelta(days=90)).isoformat()}
    _approve(docs, far)
    assert run(html, "post.cover", {**BASE, "design_exceptions": [far]}, docs=docs).level == "FAIL"        # more than 30 days
    log = docs / "approvals.jsonl"
    log.write_text(log.read_text().replace('"by": "owner"', '"by": "someone"', 1))                       # edited by hand
    line = run(html, "post.cover", {**BASE, "design_exceptions": [exc]}, docs=docs)
    assert line.level == "FAIL" and "cannot be trusted" in line.what


def test_no_exception_excuses_evidence_or_a_page_that_did_not_load(tmp_path, owner_home):
    """audit C3: ev.* / proc.* checks and 'input missing' lines are never excused, even when approved."""
    import approvals
    from gatelib.core import Ctx
    docs = tmp_path / "docs"
    docs.mkdir()
    until = (dt.date.today() + dt.timedelta(days=5)).isoformat()
    excs = [{"check": c, "why": "does not fit this site's design", "until": until} for c in ("ev.decision", "seo.basics")]
    for e in excs:
        _approve(docs, e)
    cfg = {**BASE, "design_exceptions": excs}
    (tmp_path / "journal").mkdir()
    (tmp_path / "journal" / "entries.jsonl").write_text("")
    ctx = Ctx(project=tmp_path, path="/x", key="x", cfg=cfg, docs=docs, today=dt.date(2026, 11, 19))
    run_check(ctx, CHECKS["ev.decision"])
    assert ctx.lines[-1].level == "FAIL" and "evidence or process check" in ctx.lines[-1].what
    ctx = Ctx(project=tmp_path, path="/x", url="http://127.0.0.1:9/x", ptype="post", cfg=cfg, docs=docs, today=dt.date(2026, 11, 19))
    run_check(ctx, CHECKS["seo.basics"])                    # no page HTML: input missing
    assert [ln.level for ln in ctx.lines] == ["FAIL"] and "input missing" in ctx.lines[0].what
    assert approvals.exception_problem(excs[0], dt.date.today())
    assert approvals.excuses_blocked_skip(tmp_path, {"design_exceptions": [excs[0]]}, "ev.decision")[0] is False


def test_ready_may_accept_a_blocked_skip_only_with_an_owner_approved_exception(tmp_path, owner_home):
    import approvals
    (tmp_path / "docs").mkdir()
    exc = {"check": "phone.readable", "why": "no headless browser on this machine yet", "until": (dt.date.today() + dt.timedelta(days=7)).isoformat()}
    ok, why = approvals.excuses_blocked_skip(tmp_path, {"design_exceptions": [exc]}, "phone.readable")
    assert not ok and "no owner approval" in why
    _approve(tmp_path / "docs", exc)
    ok, why = approvals.excuses_blocked_skip(tmp_path, {"design_exceptions": [exc]}, "phone.readable")
    assert ok and "excused by the owner" in why


def test_the_selector_subset():
    from techseo.dom import parse
    root = parse('<div class="a b" id="x"><p data-k="v1"><span class="c">t</span></p></div><span class="c">u</span>')
    assert len(select(root, ".a .c")) == 1 and len(select(root, "span.c")) == 2
    assert len(select(root, "#x p[data-k^=v] span, div.b")) == 2


BUILT = (SEMANTIC
         .replace('"image": {"@type": "ImageObject", "url": "https://www.example.com/img/mowing-cover-abc123.jpg"},',
                  '"image": {"@id": "https://www.example.com/_assets/mowing-cover-abc123.Xy12_Ab9.jpg"},')
         .replace('{"@type": "Person", "name": "Pat Doe", "url": "https://www.example.com/author/pat/"}',
                  '{"@type": "Person", "name": "Pat Doe", "image": {"url": "https://www.example.com/_assets/pat-doe.Qw3.webp"}}')
         .replace('<figure><img itemprop="image" src="/img/mowing-cover-abc123.jpg" alt="A lawn being mowed"></figure>',
                  '<img src="/_assets/pat-doe.Qw3.webp" alt=""><figure><picture><source srcset="/_assets/mowing-cover-abc123.Xy12_Zz.avif 960w">'
                  '<img src="/_assets/mowing-cover-abc123.Xy12_Zz.jpg" alt="A lawn being mowed"></picture></figure>')
         .replace('<p>By <a rel="author" href="/author/pat/">Pat Doe</a> · Updated <time itemprop="dateModified" datetime="2026-11-18">Nov 18, 2026</time></p>',
                  '<p><a href="/author/pat/">Pat Doe</a><time datetime="2024-01-02T10:00:00.000Z">Jan 2, 2024</time>'
                  '<span>Updated <time datetime="2026-11-19T01:42:00.000Z">Nov 18, 2026</time></span></p>')
         .replace('"dateModified": "2026-11-18"', '"dateModified": "2026-11-19T01:42:00Z"'))


def test_a_built_page_with_hashed_names_and_utc_times():
    cfg = {**BASE, "timezone": "America/Toronto"}
    assert run(BUILT, "post.cover", cfg).level == "OK"                       # the article's image, not the Person's
    line = run(BUILT, "geo.updated", cfg)                                     # 01:42 UTC on the 19th is the 18th in Toronto
    assert line.level == "OK", line.what                                      # and the byline sits one level up
    assert run(BUILT.replace('alt="A lawn being mowed"', 'alt=""'), "post.cover", cfg).level == "FAIL"


def test_the_title_check_counts_a_search_once_across_page_copies(tmp_path):
    import sqlite3
    from gatelib.c_page import gsc_top
    (tmp_path / "page-tracker").mkdir()
    c = sqlite3.connect(tmp_path / "page-tracker/tracker.db")
    c.executescript("create table search_queries(path, snapshot, query, clicks, impressions, position);"
                    "insert into search_queries values('/blog/x', '2026-11-18', '[us] mowing height', 1, 900, 4);"
                    "insert into search_queries values('/blog/x', '2026-11-18', 'mowing height', 1, 100, 4);"
                    "insert into search_queries values('/blog/x', '2026-11-18', 'lawn care', 1, 300, 4);")
    c.commit(); c.close()
    assert gsc_top(Ctx(project=tmp_path, path="/blog/x/"), 2) == [("mowing height", 1000), ("lawn care", 300)]
