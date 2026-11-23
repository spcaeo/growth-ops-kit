"""2.6.0: the checks that once read only a Next.js repo (needs="repo") are correct on an Astro-like site: component discovery,
shared components, the copy component, the circled Tick, the logo accessible-name fix, the commit identity by sha256, the
commit style cut-off, the internal-link flags from a crawled link graph, and the type checker / dead-file checks."""
import datetime as dt
import hashlib
import json
import sqlite3
import stat
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixtures.astro_repo import commit, git, make_astro_repo  # noqa: E402

from gatelib import CHECKS  # noqa: E402
from gatelib.core import Ctx, run_check  # noqa: E402

HTML = '<html><body><main><h1>Lawn mowing</h1><p>text <a href="/contact-us/">Contact</a></p></main></body></html>'


def make_ctx(tmp_path, repo, path="/lawn-mowing", ptype="money", **cfg):
    project = tmp_path / "project"
    project.mkdir(exist_ok=True)
    c = Ctx(project=project, docs=project / "docs", path=path, repo=repo, ptype=ptype, key="lawn-mowing",
            cfg={"name": "Tiny", "site_url": "https://tiny.example", "stack": "static", **cfg})
    c.html = HTML
    return c


def line(c, cid):
    run_check(c, CHECKS[cid])
    return c.lines[-1]


@pytest.fixture
def repo(tmp_path):
    return make_astro_repo(tmp_path / "site")


# ---- 1. component discovery -----------------------------------------------------------------------------------
def test_components_are_found_by_name_on_any_stack(tmp_path, repo):
    c = make_ctx(tmp_path, repo)
    rel = lambda n: c.component(n).relative_to(repo).as_posix()          # noqa: E731
    assert rel("copy") == "src/components/frame/CopyOpen.astro"          # the markup file, not the copy-open.ts helper
    assert rel("link_cards") == "src/components/frame/LinkCard.astro"
    assert rel("sticky_cta") == "src/components/frame/StickyCta.astro"
    assert rel("tick") == "src/components/frame/Tick.astro"
    assert c.component("call_dialog") is None and c.component("exit_offer") is None


def test_growth_json_components_wins_and_nextjs_keeps_its_default(tmp_path, repo):
    (repo / "src/components/frame/Ticks.astro").write_text("x")
    c = make_ctx(tmp_path, repo, components={"tick": "src/components/frame/Ticks.astro", "link_cards_css_class": "card"})
    assert c.component("tick").name == "Ticks.astro"
    from gatelib import components
    assert components.css_prefix(c) == "card"
    assert components.css_prefix(make_ctx(tmp_path, repo)) == "lc"       # detected from the component's own markup
    nx = make_ctx(tmp_path, repo, stack="nextjs")
    assert nx.component("copy").as_posix().endswith("components/copy-button.tsx")
    assert components.css_prefix(nx) == "lcx"


def test_test_files_are_found_anywhere(tmp_path, repo):
    (repo / "src/lib/x.test.ts").write_text("")
    names = {p.name for p in make_ctx(tmp_path, repo).test_files()}
    assert {"copy-open.test.mjs", "x.test.ts"} <= names
    c = make_ctx(tmp_path, repo, components={"tests": ["tests/*.mjs"]})
    assert {p.name for p in c.test_files()} == {"copy-open.test.mjs"}


# ---- 2. shared components -------------------------------------------------------------------------------------
def test_shared_components_pass_when_the_tree_holds_the_file(tmp_path, repo):
    ln = line(make_ctx(tmp_path, repo), "repo.shared-components")
    assert ln.level == "OK", ln.text()


def test_shared_components_fail_without_the_sticky_bar_and_with_a_copy_of_it(tmp_path, repo):
    base = (repo / "src/layouts/Base.astro")
    base.write_text(base.read_text().replace("<StickyCta />", "").replace("import StickyCta from '../components/frame/StickyCta.astro';\n", ""))
    ln = line(make_ctx(tmp_path, repo), "repo.shared-components")
    assert ln.level == "FAIL" and "StickyCta" in ln.what, ln.text()
    base.write_text(base.read_text().replace("<slot />", '<slot /><div class="sticky-cta">own</div>'))
    ln = line(make_ctx(tmp_path, repo), "repo.shared-components")
    assert ln.level == "FAIL" and "builds its own sticky bar" in ln.what, ln.text()


# ---- copy.shared -----------------------------------------------------------------------------------------------
def test_copy_shared_allows_the_component_and_its_helper_only(tmp_path, repo):
    assert line(make_ctx(tmp_path, repo), "copy.shared").level == "OK"
    (repo / "src/components/blocks/Hero.astro").write_text("<script>navigator.clipboard.writeText('a')</script>")
    ln = line(make_ctx(tmp_path, repo), "copy.shared")
    assert ln.level == "FAIL" and "Hero.astro talks to the clipboard itself" in ln.what and "copy-open.ts" not in ln.what, ln.text()


def test_copy_shared_needs_a_guard_test_found_by_name(tmp_path, repo):
    (repo / "tests/copy-open.test.mjs").unlink()
    ln = line(make_ctx(tmp_path, repo), "copy.shared")
    assert ln.level == "FAIL" and "no guard test for CopyOpen" in ln.what, ln.text()
    (repo / "tests/anywhere").mkdir()
    (repo / "tests/anywhere/copy.test.mjs").write_text("")
    assert line(make_ctx(tmp_path, repo), "copy.shared").level == "OK"


# ---- icons.check-circle ----------------------------------------------------------------------------------------
def test_check_circle_accepts_a_tick_astro_with_a_circle(tmp_path, repo):
    ln = line(make_ctx(tmp_path, repo), "icons.check-circle")
    assert ln.level == "OK", ln.text()


def test_check_circle_fails_with_no_tick_no_circle_and_a_bare_tick(tmp_path, repo):
    tick = repo / "src/components/frame/Tick.astro"
    tick.write_text('<svg><path d="M4 8l3 3 5-6"/></svg>')
    ln = line(make_ctx(tmp_path, repo), "icons.check-circle")
    assert ln.level == "FAIL" and "Tick has no circle" in ln.what, ln.text()
    tick.unlink()
    (repo / "src/components/blocks/Hero.astro").write_text("<li>✓ done</li>")
    ln = line(make_ctx(tmp_path, repo), "icons.check-circle")
    assert ln.level == "FAIL" and "no shared Tick component" in ln.what and "bare tick" in ln.what, ln.text()


# ---- repo.logo-untouched ---------------------------------------------------------------------------------------
def test_logo_may_change_its_accessible_name_only(tmp_path, repo):
    logo = repo / "src/components/frame/Logo.astro"
    logo.write_text(logo.read_text().replace('aria-label="Old name"', 'aria-label="New name"'))
    commit(repo)
    ln = line(make_ctx(tmp_path, repo), "repo.logo-untouched")
    assert ln.level == "OK", ln.text()


def test_logo_change_of_a_shape_or_an_image_still_fails(tmp_path, repo):
    logo = repo / "src/components/frame/Logo.astro"
    logo.write_text(logo.read_text().replace('aria-label="Old name"', 'aria-label="New name"').replace("<svg", '<svg><path d="M0 0"/'))
    ln = line(make_ctx(tmp_path, repo), "repo.logo-untouched")
    assert ln.level == "FAIL" and "Logo.astro" in ln.what, ln.text()
    git(repo, "checkout", "--", ".")
    (repo / "public").mkdir()
    (repo / "public/logo.png").write_bytes(b"\x89PNG one")
    commit(repo, "Add the picture")
    ln = line(make_ctx(tmp_path, repo), "repo.logo-untouched")
    assert ln.level == "FAIL" and "public/logo.png" in ln.what
    (repo / "public/logo.png").write_bytes(b"\x89PNG two")
    ln = line(make_ctx(tmp_path, repo), "repo.logo-untouched")
    assert ln.level == "FAIL"


def test_a_file_changed_and_put_back_is_not_a_branch_file(tmp_path, repo):
    logo = repo / "src/components/frame/Logo.astro"
    original = logo.read_text()
    logo.write_text(original + "<!-- x -->\n")
    commit(repo, "Change it")
    logo.write_text(original)
    commit(repo, "Put it back")
    c = make_ctx(tmp_path, repo)
    assert "src/components/frame/Logo.astro" not in c.branch_files()
    assert line(c, "repo.logo-untouched").level == "OK"


# ---- identity and commit style ---------------------------------------------------------------------------------
def test_commit_identity_by_email_sha256(tmp_path, repo):
    digest = hashlib.sha256(b"owner@private.example").hexdigest()
    cfg = {"commit_identity": {"email_sha256": digest}}
    assert make_ctx(tmp_path, repo, **cfg).identity_ok("OWNER@private.example")
    assert not make_ctx(tmp_path, repo, **cfg).identity_ok("someone@else.example")
    (repo / "a.txt").write_text("a")
    commit(repo, "Add a", email="someone@else.example")
    ln = line(make_ctx(tmp_path, repo, **cfg), "repo.commit-identity")
    assert ln.level == "FAIL" and "commit_identity.email_sha256" in ln.fix, ln.text()
    git(repo, "reset", "-q", "--hard", "main")
    (repo / "a.txt").write_text("a")
    commit(repo, "Add a", email="owner@private.example")
    ln = line(make_ctx(tmp_path, repo, **cfg), "repo.commit-identity")
    assert ln.level == "OK" and "commit_identity.email_sha256" in ln.what, ln.text()
    assert "owner@private" not in ln.what + ln.fix                  # the address itself is never printed


def test_commit_style_since_exempts_history(tmp_path, repo):
    (repo / "a.txt").write_text("a")
    commit(repo, "x" * 120)                                  # a long subject and no co-author line
    assert line(make_ctx(tmp_path, repo), "repo.commit-style").level == "FAIL"
    future = (dt.date.today() + dt.timedelta(days=30)).isoformat()
    assert line(make_ctx(tmp_path, repo, commit_style={"since": future}), "repo.commit-style").level == "OK"


# ---- links from a crawled graph ---------------------------------------------------------------------------------
SCHEMA = """CREATE TABLE pages(url TEXT PRIMARY KEY, status INT, title TEXT, h1 TEXT, cluster TEXT, hub TEXT, type TEXT,
  noindex INT, canonical TEXT, in_sitemap INT, crawled_at TEXT);
CREATE TABLE links(src TEXT, dst TEXT, anchor TEXT, zone TEXT, rel TEXT, heading TEXT, crawled_at TEXT);
CREATE TABLE targets(path TEXT PRIMARY KEY, status INT, final TEXT, final_status INT, checked_at TEXT);
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);"""


def write_graph(project, links, targets=(), age_hours=0):
    (project / "inventory").mkdir(parents=True, exist_ok=True)
    db = project / "inventory" / "link-graph.db"
    db.unlink(missing_ok=True)
    c = sqlite3.connect(db)
    c.executescript(SCHEMA)
    for p in ("/", "/lawn-mowing", "/mulch", "/edging", "/old"):
        c.execute("INSERT INTO pages VALUES (?,?,?,?,?,?,?,?,?,?,?)", (p, 200, "", "", "lawn", "/lawn-mowing", "", 0, "", 1, ""))
    for s, d, a, z in links:
        c.execute("INSERT INTO links VALUES (?,?,?,?,?,?,?)", (s, d, a, z, "", "", ""))
    for t in targets:
        c.execute("INSERT INTO targets VALUES (?,?,?,?,?)", t + ("",))
    when = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=age_hours)
    c.execute("INSERT INTO meta VALUES ('last_crawl', ?)", (json.dumps({"at": when.strftime("%Y-%m-%d %H:%M:%S")}),))
    c.commit()
    c.close()


def graph_ctx(tmp_path, repo, **kw):
    c = make_ctx(tmp_path, repo, timezone="UTC", **kw)
    c.url = "http://127.0.0.1:18432/lawn-mowing/"
    return c


def test_link_checks_read_the_crawled_graph(tmp_path, repo):
    c = graph_ctx(tmp_path, repo)
    write_graph(c.project, [("/mulch", "/lawn-mowing", "lawn mowing prices", "body"), ("/edging", "/lawn-mowing", "mowing plans", "body"),
                            ("/lawn-mowing", "/mulch", "mulch", "body"), ("/lawn-mowing", "/edging", "edging", "body")])
    assert line(c, "links.inbound").level == "OK"
    c2 = graph_ctx(tmp_path, repo)
    assert line(c2, "links.no-redirect").level == "OK"
    assert line(graph_ctx(tmp_path, repo), "links.anchor-unique").level == "OK"


def test_link_checks_flag_a_thin_page_a_redirect_and_a_repeated_anchor(tmp_path, repo):
    c = graph_ctx(tmp_path, repo)
    write_graph(c.project, [("/mulch", "/lawn-mowing", "mowing", "body"), ("/lawn-mowing", "/old", "old page", "body"),
                            ("/lawn-mowing", "/edging", "shared words", "body"), ("/mulch", "/mulch", "x", "body"),
                            ("/edging", "/mulch", "shared words", "body")],
                [("/old", 301, "/mulch", 200)])
    assert line(c, "links.inbound").level == "FAIL"                        # one page links here: weak
    assert "redirects" in line(graph_ctx(tmp_path, repo), "links.no-redirect").what
    ln = line(graph_ctx(tmp_path, repo), "links.anchor-unique")
    assert ln.level == "FAIL" and "shared words" in ln.what, ln.text()


def test_a_missing_or_stale_graph_is_a_blocked_skip_naming_the_command(tmp_path, repo):
    c = graph_ctx(tmp_path, repo)
    ln = line(c, "links.inbound")
    assert ln.level == "SKIP" and ln.blocked
    assert "growth link_graph crawl --base http://127.0.0.1:18432" in ln.what
    write_graph(c.project, [], age_hours=200)
    c2 = graph_ctx(tmp_path, repo)
    ln = line(c2, "links.no-redirect")
    assert ln.level == "SKIP" and ln.blocked and "stale" in ln.what and "link_graph crawl --base" in ln.what
    # the page itself is missing from the graph
    write_graph(c.project, [])
    c3 = graph_ctx(tmp_path, repo, path="/new-page")
    ln = line(c3, "links.inbound")
    assert ln.level == "SKIP" and ln.blocked and "/new-page" in ln.what
    assert not (c.project / "inventory" / "link-graph.db-journal").exists()        # only read, never written


# ---- type checker and dead files ----------------------------------------------------------------------------------
def test_no_unused_code_is_a_blocked_skip_when_the_stack_has_no_checker(tmp_path, repo):
    (repo / "src/lib/new.ts").write_text("const a = 1;\n")
    commit(repo)
    ln = line(make_ctx(tmp_path, repo), "repo.no-unused-code")
    assert ln.level == "SKIP" and ln.blocked and "tsc" in ln.what and "install node_modules" not in ln.what, ln.text()


def test_no_unused_code_runs_the_sites_tsc(tmp_path, repo):
    bin_dir = repo / "node_modules" / ".bin"
    bin_dir.mkdir(parents=True)
    tsc = bin_dir / "tsc"
    tsc.write_text("#!/bin/sh\necho \"src/lib/new.ts(1,7): error TS6133: 'a' is declared but its value is never read.\"\nexit 2\n")
    tsc.chmod(tsc.stat().st_mode | stat.S_IXUSR)
    (repo / "tsconfig.json").write_text("{}")
    (repo / "src/lib/new.ts").write_text("const a = 1;\n")
    commit(repo)
    ln = line(make_ctx(tmp_path, repo), "repo.no-unused-code")
    assert ln.level == "FAIL" and "src/lib/new.ts:1" in ln.what, ln.text()


def test_no_dead_files_reads_src_on_astro(tmp_path, repo):
    (repo / "src/components/blocks/Unused.astro").write_text("<p>x</p>")
    (repo / "src/components/blocks/Used.astro").write_text("<p>y</p>")
    hero = repo / "src/components/blocks/Hero.astro"
    hero.write_text("---\nimport Used from './Used.astro';\n---\n<Used />")
    commit(repo)
    ln = line(make_ctx(tmp_path, repo), "repo.no-dead-files")
    assert ln.level == "FAIL" and "Unused.astro" in ln.what and "Used.astro is not" not in ln.what, ln.text()


# ---- 2.7.3: three misreads on a real Astro site ----------------------------------------------------------------
def test_reading_utm_tags_for_attribution_is_not_a_utm_link(tmp_path, repo):
    hero = repo / "src/components/blocks/Hero.astro"            # imported by the lawn-mowing page, so in its source tree
    hero.write_text("<script>const p = new URLSearchParams(location.search); const s = p.get('utm_source');</script>")
    assert line(make_ctx(tmp_path, repo), "links.no-utm").level == "OK"
    hero.write_text("<script>a.href = '/contact-us/?utm_source=footer';</script>")
    ln = line(make_ctx(tmp_path, repo), "links.no-utm")
    assert ln.level == "FAIL" and "Hero.astro" in ln.what, ln.text()


def test_mailto_with_no_address_needs_no_copy_button(tmp_path, repo):
    c = make_ctx(tmp_path, repo)
    c.html = '<html><body><main><h1>x</h1><p><a href="mailto:?subject=Read%20this">Email it</a></p></main></body></html>'
    assert line(c, "copy.shared").level == "OK"
    c = make_ctx(tmp_path, repo)
    c.html = '<html><body><main><h1>x</h1><p><a href="mailto:hi@tiny.example">hi@tiny.example</a></p></main></body></html>'
    ln = line(c, "copy.shared")
    assert ln.level == "FAIL" and "has no copy button" in ln.what, ln.text()


def test_a_tick_inside_a_regex_is_not_a_bare_tick(tmp_path, repo):
    (repo / "src/components/article").mkdir(parents=True, exist_ok=True)
    (repo / "src/components/article/emoji.ts").write_text("const TICK = /[\\u2713✓✔]/g;\nexport const has = (s) => TICK.test(s);\n")
    assert line(make_ctx(tmp_path, repo), "icons.check-circle").level == "OK"
    (repo / "src/components/article/emoji.ts").write_text("el.textContent = '✓ done';\n")
    ln = line(make_ctx(tmp_path, repo), "icons.check-circle")
    assert ln.level == "FAIL" and "bare tick" in ln.what, ln.text()


def test_retired_groups_found_in_an_nginx_style_rule(tmp_path, repo):
    (repo / "src/lib").mkdir(parents=True, exist_ok=True)
    (repo / "src/lib/redirects.mjs").write_text(
        "export const conf = `\n  location ~ ^/(wp-admin|wp-json|graphql)(/|$) { return 410; }\n`;\n")
    ok = make_ctx(tmp_path, repo, nextjs={"retired_paths": ["/wp-admin", "/wp-json", "/graphql"], "redirect_files": ["src/lib/redirects.mjs"]})
    assert line(ok, "repo.retired-410").level == "OK"
    bad = make_ctx(tmp_path, repo, nextjs={"retired_paths": ["/wp-admin", "/tag"], "redirect_files": ["src/lib/redirects.mjs"]})
    ln = line(bad, "repo.retired-410")
    assert ln.level == "FAIL" and "/tag" in ln.what and "/wp-admin" not in ln.what, ln.text()
