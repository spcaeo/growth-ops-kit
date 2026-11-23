"""2.7.5: links.blue's '+' marker pattern skips BEM modifiers (.leadcard--plus) and CSS comments name no colour;
repo.guard-tests accepts one data-driven test named in growth.json guard_tests.all_pages."""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixtures.astro_repo import make_astro_repo  # noqa: E402

from gatelib import CHECKS  # noqa: E402
from gatelib.core import Ctx, run_check  # noqa: E402

PLUS = re.compile(r"\.[\w-]*[^-]-plus(?![\w-])")


def test_plus_marker_class_is_not_a_bem_modifier():
    assert PLUS.search(".link-plus") and PLUS.search(".lc-plus::after")
    assert not PLUS.search(".leadcard--plus") and not PLUS.search(".kbb__card--plus")


def test_css_comments_are_removed_before_reading_colours():
    css = ".kbb__card::after{content:'+'; /* brand colour var(--brand) was here */ color:currentColor}"
    assert "brand" not in re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def ctx(tmp_path, repo, **cfg):
    project = tmp_path / "project"
    project.mkdir(exist_ok=True)
    c = Ctx(project=project, docs=project / "docs", path="/lawn-mowing", repo=repo, ptype="money", key="lawn-mowing",
            cfg={"name": "Tiny", "site_url": "https://tiny.example", "stack": "static", **cfg})
    c.html = "<html><body><main><h1>x</h1></main></body></html>"
    return c


def line(c):
    run_check(c, CHECKS["repo.guard-tests"])
    return c.lines[-1]


def test_one_all_pages_test_covers_every_page(tmp_path):
    repo = make_astro_repo(tmp_path / "site")
    (repo / "tests").mkdir(exist_ok=True)
    (repo / "tests/house_features.test.mjs").write_text(
        "// house features (rule 156) for every built page\nfor (const p of pages) { assert(hasSticky(p)); assert(/FAQPage/.test(p.html)); }\n")
    assert line(ctx(tmp_path, repo, guard_tests={"all_pages": "tests/house_features.test.mjs"})).level == "OK"
    (repo / "tests/house_features.test.mjs").write_text("for (const p of pages) { assert(hasSticky(p)); }\n")
    ln = line(ctx(tmp_path, repo, guard_tests={"all_pages": "tests/house_features.test.mjs"}))
    assert ln.level == "FAIL" and "house features" in ln.what and "FAQPage" in ln.what, ln.text()
