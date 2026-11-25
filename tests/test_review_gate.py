"""The gate checks the argument, not only the structure (#60): the independent review must answer the kit's fixed
checklist and name a reviewer who is not the builder; a money figure in the first screen or verdict must be stated in the
body. Example markup only (example.com)."""
import tempfile
from pathlib import Path

import pytest

from gatelib import CHECKS
from gatelib.core import Ctx, run_check
import review

PAGE = """<html><head><title>T</title></head><body><header><a href="/">Example</a></header><main><article>
<h1>Tool A vs tool B</h1>
<p>Tool B costs $159.90 a month less than tool A for 10 people.</p>
<div class="verdict"><p>Pick tool B and save $1,918.80 a year.</p></div>
<h2>The sums</h2>
<p>For 10 people tool A's time-tracking plan costs $259.90 a month and tool B's costs $100.00 a month: a gap of 159.90.
Over a year that is $1,918.80 (source: each vendor's price page, checked Nov 18, 2026).</p>
<h2>Questions</h2><p>One person pays $0 on the personal plan.</p>
</article></main><footer>F</footer></body></html>"""


def run(html, cid="claims.head-figures", cfg=None):
    with tempfile.TemporaryDirectory() as tmp:
        ctx = Ctx(project=Path(tmp), path="/x/", url="http://127.0.0.1:9/x/", ptype="post", cfg=cfg or {}, html=html, status=200)
        run_check(ctx, CHECKS[cid])
        return ctx.lines[0]


def test_a_page_whose_head_figures_are_in_the_body_passes():
    assert run(PAGE).level == "OK"


def test_a_head_figure_the_body_never_states_fails_and_names_it():
    ln = run(PAGE.replace("a gap of 159.90", "a gap of 19.90"))
    assert ln.level == "FAIL" and "$159.90" in ln.what


def test_a_figure_only_in_the_verdict_block_fails():
    ln = run(PAGE.replace("save $1,918.80 a year", "save $2,400 a year"))
    assert ln.level == "FAIL" and "$2,400" in ln.what


def test_formats_of_one_figure_count_as_one():
    html = PAGE.replace("$159.90 a month less", "$159.9 a month less").replace("$100.00", "$100")
    assert run(html).level == "OK"


def test_a_verdict_placed_after_the_first_heading_is_still_head():
    html = PAGE.replace('<div class="verdict"><p>Pick tool B and save $1,918.80 a year.</p></div>', "").replace(
        "<h2>Questions</h2>", '<h2>Questions</h2><div data-verdict><p>Save $9,999 a year.</p></div>')
    assert run(html).level == "FAIL"


def test_a_page_with_no_money_in_the_head_or_no_body_passes():
    assert run(PAGE.replace("$159.90", "much").replace("$1,918.80 a year", "a lot")).level == "OK"
    assert run("<main><h1>T</h1><p>From $5 a month.</p></main>").level == "OK"


# ---- the review file ----------------------------------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _temp_home(tmp_path, monkeypatch):
    (tmp_path / "home").mkdir(exist_ok=True)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))         # approvals never read the real signing key


def review_line(tmp, text, key="lawn", signed=True):
    """audit H2: a review counts only once the owner signed it off (growth approve review); signed=True records that."""
    import approvals
    (tmp / "research").mkdir(exist_ok=True)
    f = tmp / "research" / f"{key}-review-2026-11-18.md"
    f.write_text(text)
    if signed:
        approvals.record(tmp / "docs", "review", f.name, f.read_bytes(), by="owner")
    ctx = Ctx(project=tmp, path="/" + key, key=key, cfg={})
    run_check(ctx, CHECKS["ev.review"])
    return ctx.lines[0]


def answered(**kw):
    ids = review_ids()
    return "Reviewer: model-b\nBuilder: model-a\n" + "".join(f"{i} pass: seen\n" for i in ids)


def review_ids():
    return [i for i, _, _ in review.items()]


def test_the_checklist_has_the_three_fixed_items_the_issue_names():
    text = Path(review.CHECKLIST).read_text().lower()
    assert "same feature" in text and "appears in the body" in text and "contradict" in text


def test_a_review_that_answers_every_item_passes(tmp_path):
    assert review_line(tmp_path, answered()).level == "OK"


def test_the_generated_template_fails_until_answered(tmp_path):
    t = review.template("lawn", "model-b", "model-a", "2026-11-18")
    ln = review_line(tmp_path, t)
    assert ln.level == "FAIL" and "R1 has no verdict" in ln.what
    filled = t
    for i in review_ids():
        filled = filled.replace(f"{i} TODO", f"{i} pass:")
    assert review_line(tmp_path, filled).level == "OK"


@pytest.mark.parametrize("drop", ["R1", "R2", "R3"])
def test_a_review_that_skips_an_item_fails(tmp_path, drop):
    text = "".join(l + "\n" for l in answered().splitlines() if not l.startswith(drop + " "))
    ln = review_line(tmp_path, text)
    assert ln.level == "FAIL" and f"{drop} has no verdict" in ln.what


def test_na_needs_to_be_stated_and_counts(tmp_path):
    text = answered().replace("R4 pass: seen", "R4 n/a: no prices on this page")
    assert review_line(tmp_path, text).level == "OK"


def test_the_reviewer_must_be_named_and_not_the_builder(tmp_path):
    assert "Reviewer" in review_line(tmp_path, answered().replace("Reviewer: model-b\n", "")).what
    same = answered().replace("Reviewer: model-b", "Reviewer: model-a")
    assert "is the builder" in review_line(tmp_path, same).what


def test_growth_review_new_writes_the_file_from_the_checklist(demo_project):
    import subprocess
    import sys
    env = {"GROWTH_PROJECT": str(demo_project), "PATH": "/usr/bin:/bin"}
    r = subprocess.run([sys.executable, str(Path(review.__file__)), "new", "lawn", "--reviewer", "model-b", "--builder", "model-a"],
                       capture_output=True, text=True, env=env, cwd=demo_project)
    assert r.returncode == 0, r.stderr
    f = next((demo_project / "research").glob("lawn-review-*.md"))
    assert "Reviewer: model-b" in f.read_text() and "R1 TODO" in f.read_text()


def test_a_review_the_owner_did_not_sign_off_or_that_changed_after_fails(tmp_path):
    """audit H2: a hand-typed review file with all verdicts passed on its own."""
    ln = review_line(tmp_path, answered(), signed=False)
    assert ln.level == "FAIL" and "growth approve review research/lawn-review-2026-11-18.md" in ln.what
    review_line(tmp_path, answered())
    f = tmp_path / "research" / "lawn-review-2026-11-18.md"
    f.write_text(f.read_text() + "R1 pass: edited after sign-off\n")
    ctx = Ctx(project=tmp_path, path="/lawn", key="lawn", cfg={})
    run_check(ctx, CHECKS["ev.review"])
    assert ctx.lines[0].level == "FAIL" and "changed after the owner approved it" in ctx.lines[0].what


def test_a_review_needs_a_builder_line(tmp_path):
    ln = review_line(tmp_path, answered().replace("Builder: model-a\n", ""))
    assert ln.level == "FAIL" and "Builder" in ln.what


def test_the_review_fixes_file_is_not_the_review():
    # 24 Nov 2026: home-review-fixes-<date>.md was read as the review and failed for its missing R verdicts
    import re
    from gatelib.c_evidence import REVIEW_NAME
    assert re.search(REVIEW_NAME, "-review-2026-11-24.md")
    assert not re.search(REVIEW_NAME, "-review-fixes-2026-11-24.md")
