"""2.2.3: evidence is fresh while the page's own built output (its fingerprint) is unchanged, whatever commits came since.
Evidence with no fingerprint keeps the commit-based rule. Nothing is rebuilt; no network."""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import fingerprint  # noqa: E402
from test_demo import png  # noqa: E402
from test_release_2_2_fixes import git_repo  # noqa: E402

from gatelib import CHECKS  # noqa: E402
from gatelib.core import Ctx, run_check  # noqa: E402

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _project(demo_project, monkeypatch):
    monkeypatch.setenv("GROWTH_PROJECT", str(demo_project))        # journal.parse_at reads the project's time zone


PAGE = ('<html><head><meta name="build-id" content="{b}"><link rel="stylesheet" href="/_a/s.css"><script nonce="{b}" src="/_a/m.js"></script></head>'
        '<body><main><h1>A</h1><p>Hello {t}</p></main><!-- built {b} --></body></html>')
CFG = {"build_dir": "dist", "timezone": "UTC",
       "page_tracker": {"content_globs": [{"glob": "src/content/blog/*.md", "address": "/blog/{slug}/"}]}}


def build(r, css="a{}", js="1", b="b1", t="x"):
    d = r / "dist" / "blog" / "a"
    d.mkdir(parents=True, exist_ok=True)
    (d / "index.html").write_text(PAGE.format(b=b, t=t))
    (r / "dist" / "_a").mkdir(exist_ok=True)
    (r / "dist" / "_a" / "s.css").write_text(css)
    (r / "dist" / "_a" / "m.js").write_text(js)


def mk(tmp_path, fp=True):
    r, commit = git_repo(tmp_path)
    commit("src/content/blog/a.md", "---\ntitle: A\nslug: a\n---\nA", "2026-11-01T10:00:00+00:00")
    build(r)
    p = tmp_path / "p"
    for d in ("docs", "journal", "research"):
        (p / d).mkdir(parents=True)
    now = fingerprint.current(CFG, p, r, "/blog/a/")
    e = {"id": "J0001", "at": "2026-11-02 10:00+00:00", "kind": "note", "pages": ["/blog/a"], "tags": ["click-test"], "title": "t", "text": "t"}
    if fp:
        e["fp"] = {"/blog/a": now}
    (p / "journal" / "entries.jsonl").write_text(json.dumps(e) + "\n")
    return r, p, commit


def gate(r, p, cid="ev.click-test"):
    c = Ctx(project=p, repo=r, path="/blog/a/", key="a", cfg=CFG)
    run_check(c, CHECKS[cid])
    return c.lines[-1]


def test_fingerprint_ignores_build_ids_nonces_comments_and_times():
    a = fingerprint.make(PAGE.format(b="b1", t="x") + "<p>2026-11-02T10:00:00Z</p>", lambda h: b"x", "build")
    b = fingerprint.make(PAGE.format(b="b2", t="x") + "<p>2026-11-09T11:30:00Z</p>", lambda h: b"x", "build")
    c = fingerprint.make(PAGE.format(b="b1", t="y"), lambda h: b"x", "build")
    assert fingerprint.same(a, b) and not fingerprint.same(a, c)
    assert not fingerprint.same(a, fingerprint.make(PAGE.format(b="b1", t="x"), lambda h: b"changed", "build"))   # a linked file changed


def test_shared_code_commits_do_not_stale_evidence_with_the_same_fingerprint(tmp_path):
    r, p, commit = mk(tmp_path)
    commit("src/components/Hero.astro", "<h1/>", "2026-11-05T10:00:00+00:00")      # shared code, after the evidence
    commit("src/components/Footer.astro", "<f/>", "2026-11-06T10:00:00+00:00")
    build(r, b="b2")                                                                  # a new build id only
    assert gate(r, p).level == "OK"


def test_the_same_commits_stale_evidence_that_has_no_fingerprint(tmp_path):
    r, p, commit = mk(tmp_path, fp=False)
    assert gate(r, p).level == "OK"                                                   # filed after the last change
    commit("src/components/Hero.astro", "<h1/>", "2026-11-05T10:00:00+00:00")
    assert gate(r, p).level == "FAIL"                                                 # the commit-based fallback, as before


def test_a_changed_page_stales_evidence_filed_before_its_last_change(tmp_path):
    r, p, commit = mk(tmp_path)
    commit("src/components/Hero.astro", "<h1/>", "2026-11-05T10:00:00+00:00")
    build(r, t="changed text")
    assert gate(r, p).level == "FAIL"
    build(r, css="a{color:red}")                                                      # or a linked file
    assert gate(r, p).level == "FAIL"


def test_journal_entries_with_an_evidence_tag_get_the_fingerprint(tmp_path):
    r, commit = git_repo(tmp_path)
    build(r)
    e = {"pages": ["/blog/a"], "tags": ["click-test"]}
    fingerprint.attach(e, CFG, tmp_path / "p", r)
    assert e["fp"]["/blog/a"]["src"] == "build" and len(e["fp"]["/blog/a"]["assets"]) == 2
    other = {"pages": ["/blog/a"], "tags": ["finding"]}
    fingerprint.attach(other, CFG, tmp_path / "p", r)
    assert "fp" not in other


def test_shots_with_a_stored_fingerprint_stay_fresh(tmp_path):
    r, p, commit = mk(tmp_path, fp=False)
    shots = p / "research" / "a-shots"
    shots.mkdir()
    (shots / "s-1366.png").write_bytes(png(1366, 800))
    (shots / "s-390.png").write_bytes(png(780, 1600))
    old = time.time() - 86400 * 30
    for f in shots.iterdir():
        os.utime(f, (old, old))                                                       # older than every commit
    assert gate(r, p, "ev.shots-1366-390").level == "FAIL"                           # no fingerprint: the commit rule
    assert fingerprint.record_shots(p, "a", "/blog/a/", fingerprint.current(CFG, p, r, "/blog/a/")) == ["a-shots"]
    assert gate(r, p, "ev.shots-1366-390").level == "OK"
    build(r, t="changed text")
    assert gate(r, p, "ev.shots-1366-390").level == "FAIL"
