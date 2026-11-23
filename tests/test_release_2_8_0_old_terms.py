"""2.8.0: migrate.old-terms (rule 36): every item of a short list on a rebuilt page is on an archived old page of the site or in BRAND.md."""
from pathlib import Path

import pytest

from gatelib import CHECKS
from gatelib.core import Ctx, run_check

TAGS = ["React", "Vue.js", "Node.js", "Hugging Face Transformers", "scikit-learn"]


def ul(items, attrs=""):
    return f"<ul {attrs}>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"


def old(project, slug, words, stage="2026-11-22-before"):
    d = project / "archive" / "pages" / slug / stage
    d.mkdir(parents=True)
    (d / "page.html").write_text("<html><body><nav>Menu</nav><main><p>" + " ".join(words) + "</p></main></body></html>")


@pytest.fixture
def project(tmp_path):
    return tmp_path


def line(project, body, cfg=None, path="/hire/experts/"):
    html = f"<html><body><main><section data-fold='a'>{body}</section></main></body></html>"
    c = Ctx(project=project, path=path, key="p", ptype="money", cfg=cfg or {}, html=html, url="http://127.0.0.1:9/p/", status=200)
    run_check(c, CHECKS["migrate.old-terms"])
    return c.lines


def test_no_archived_old_version_is_a_skip_not_blocked(project):
    ln = line(project, ul(TAGS))[0]
    assert ln.level == "SKIP" and not ln.blocked and "archived old version" in ln.what, ln.text()


def test_items_on_the_pages_own_old_version_pass(project):
    old(project, "hire__experts", ["React", "Vue.js", "Node.js", "Hugging Face", "Transformers", "scikit", "learn"])
    ln = line(project, ul(TAGS))
    assert [x.level for x in ln] == ["OK"], [x.text() for x in ln]


def test_an_item_no_old_page_has_fails_and_is_named(project):
    old(project, "hire__experts", ["React", "Vue.js", "Node.js", "Hugging Face Transformers", "scikit-learn"])
    ln = line(project, ul(TAGS[:4] + ["LangChain"]))
    assert ln[0].level == "FAIL" and "'LangChain'" in ln[0].what and "React" not in ln[0].what, ln[0].text()


def test_any_old_page_of_the_site_approves_an_item_but_warns_that_this_page_did_not_have_it(project):
    old(project, "hire__experts", ["React", "Vue.js", "Node.js"])
    old(project, "other__page", ["Hugging Face Transformers", "scikit-learn", "Angular"], "2026-11-19-before")
    ln = line(project, ul(TAGS))
    assert [x.level for x in ln] == ["WARN", "OK"] or [x.level for x in ln] == ["OK", "WARN"], [x.text() for x in ln]
    warn = next(x for x in ln if x.level == "WARN")
    assert "2 short-list item(s)" in warn.what and "Hugging Face Transformers" in warn.what


def test_scope_page_makes_the_other_page_items_a_fail(project):
    old(project, "hire__experts", ["React", "Vue.js", "Node.js"])
    old(project, "other__page", ["Hugging Face Transformers", "scikit-learn"], "2026-11-19-before")
    ln = line(project, ul(TAGS), {"words": {"old_terms_scope": "page"}})
    assert [x.level for x in ln] == ["FAIL"] and "Hugging Face Transformers" in ln[0].what and "React" not in ln[0].what


def test_brand_md_counts_as_a_source(project):
    old(project, "hire__experts", ["React", "Vue.js", "Node.js", "scikit-learn"])
    assert line(project, ul(TAGS))[0].level == "FAIL"
    (project / "BRAND.md").write_text("We work with Hugging Face Transformers and more.")
    assert [x.level for x in line(project, ul(TAGS))] == ["OK"]


def test_matching_ignores_case_marks_and_picture_descriptions(project):
    d = project / "archive" / "pages" / "hire__experts" / "2026-11-22-before"
    d.mkdir(parents=True)
    (d / "page.html").write_text('<main><img alt="NODE.JS"><span title="Hugging-Face Transformers">x</span>React &amp; Vue.js, scikit learn</main>')
    assert [x.level for x in line(project, ul(TAGS))] == ["OK"]


def test_only_short_lists_are_compared(project):
    old(project, "hire__experts", ["nothing relevant"])
    assert line(project, ul(["Alpha", "Beta", "Gamma", "Delta"]))[0].level == "OK"                       # 4 items: not a list of tags
    longer = ul(["Alpha one", "Beta two", "Gamma three", "Delta four", "We build this in six words total."])
    assert line(project, longer)[0].level == "OK"                                                   # one item is a sentence
    assert line(project, ul(["Alpha", "Beta", "Gamma", "Delta", "Epsilon"]))[0].level == "FAIL"
    assert line(project, ul(["Alpha", "Beta", "Gamma", "Delta", "Epsilon"], 'class="toc"'))[0].level == "OK"      # a contents list is exempt


def test_data_tags_marks_a_list_of_any_size(project):
    old(project, "hire__experts", ["nothing relevant"])
    assert line(project, '<div data-tags="stack"><span>Alpha</span><span>Beta</span></div>')[0].level == "FAIL"
    assert line(project, ul(["Alpha", "Beta"], "data-tags"))[0].level == "FAIL"


def test_step_numbers_and_the_projects_ok_list(project):
    old(project, "hire__experts", ["Discovery", "Design", "Build", "Test", "Launch"])
    assert [x.level for x in line(project, ul(["1Discovery", "2Design", "3Build", "4Test", "5Launch"]))] == ["OK"]
    old(project, "x__y", ["nothing"], "2026-11-19-before")
    assert line(project, ul(["Alpha", "Beta", "Gamma", "Delta", "Epsilon"]), {"words": {"old_terms_ok": ["alpha", "Beta", "Gamma", "Delta", "Epsilon"]}})[0].level == "OK"
