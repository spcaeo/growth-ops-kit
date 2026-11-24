"""2.8.2: words.own-copy (rule 157a): a page's folds are its own words; no fold copies another page of the site."""
from pathlib import Path

from gatelib import CHECKS
from gatelib.core import Ctx, run_check

HIRE = ("Our healthcare developers join your team within days and work inside your sprint rhythm, your tickets and your review rules, "
        "so the first merged change lands in the first week and the handover notes stay current for every release that follows after it.")
OTHER = ("A different story altogether: we start by mapping the clinic's own booking gaps with the front desk, then we prototype the "
         "smallest fix, test it with real nurses on a quiet ward and only then widen the pilot to the next department in the building.")
CTA = "Book a free thirty minute call with an engineer who has shipped a product like yours before and reply arrives within one working day."


def fold(name, inner):
    return f'<section data-fold="{name}"><div><h2>{name}</h2>{inner}</div></section>'


def page(*folds):
    return ("<html><body><header>Menu Home About</header><main>" + "".join(folds) +
            "</main><footer>Footer words appear everywhere on the site, every single page, always.</footer></body></html>")


def site(tmp_path, pages):
    for rel, html in pages.items():
        f = tmp_path / rel / "index.html"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(html)
    return tmp_path


def run(tmp_path, path, html, cfg=None):
    cfg = {"build_dir": str(tmp_path), **(cfg or {})}
    c = Ctx(project=Path("/nonexistent"), path=path, key="p", ptype="money", cfg=cfg, html=html, url="http://127.0.0.1:9/p/", status=200)
    run_check(c, CHECKS["words.own-copy"])
    return c.lines[-1]


def test_a_copied_fold_fails_and_names_the_other_page_and_a_run(tmp_path):
    mine = page(fold("why", f"<p>{HIRE}</p>"))
    site(tmp_path, {"a": mine, "b": page(fold("why-b", f"<p>{HIRE}</p>"))})
    ln = run(tmp_path, "/a/", mine)
    assert ln.level == "FAIL" and "fold 'why'" in ln.what and "fold 'why-b' of /b" in ln.what and "100%" in ln.what, ln.text()
    assert "join your team within days and work inside" in ln.what, ln.text()


def test_a_reworded_fold_passes(tmp_path):
    mine = page(fold("why", f"<p>{OTHER}</p>"))
    site(tmp_path, {"a": mine, "b": page(fold("why", f"<p>{HIRE}</p>"))})
    assert run(tmp_path, "/a/", mine).level == "OK"


def test_a_partly_copied_fold_warns(tmp_path):
    words = HIRE.split()
    mixed = " ".join(words[:22]) + " " + OTHER + " " + OTHER.replace("clinic", "hospital")
    mine = page(fold("why", f"<p>{mixed}</p>"))
    site(tmp_path, {"a": mine, "b": page(fold("why", f"<p>{HIRE}</p>"))})
    ln = run(tmp_path, "/a/", mine, {"words": {"own_copy": {"warn": 0.1, "fail": 0.9}}})
    assert ln.level == "WARN", ln.text()


def test_a_line_shared_on_three_pages_is_ignored(tmp_path):
    """a call to action's reason or trust line on 3+ pages is shared on purpose."""
    mine = page(fold("ask", f"<p>{CTA}</p>"))
    site(tmp_path, {"a": mine, "b": page(fold("ask", f"<p>{CTA}</p>")), "c": page(fold("x", f"<p>{CTA}</p>"))})
    small = {"words": {"own_copy": {"min_words": 10}}}
    assert run(tmp_path, "/a/", mine, small).level == "OK"
    # the same line on only two pages is a copy
    site(tmp_path, {"c": page(fold("x", f"<p>{OTHER}</p>"))})
    assert run(tmp_path, "/a/", mine, small).level == "FAIL"


def test_chrome_outside_main_and_quoted_reviews_are_not_read(tmp_path):
    quote = f"<ul><li><blockquote>{HIRE}</blockquote><p>Jane Doe, CEO</p></li></ul>"
    mine = page(fold("why", quote)).replace("<header>Menu Home About</header>", f"<header>{HIRE}</header>")
    site(tmp_path, {"a": mine, "b": page(fold("w", quote)).replace("<header>Menu Home About</header>", f"<header>{HIRE}</header>")})
    assert run(tmp_path, "/a/", mine).level == "OK"


def test_no_build_is_a_skip_never_ok(tmp_path):
    mine = page(fold("why", f"<p>{HIRE}</p>"))
    ln = run(tmp_path / "missing", "/a/", mine)
    assert ln.level == "SKIP" and "no built output" in ln.what, ln.text()
    c = Ctx(project=Path("/nonexistent"), path="/a/", key="p", ptype="money", cfg={}, html=mine, url="http://127.0.0.1:9/a/", status=200)
    run_check(c, CHECKS["words.own-copy"])
    assert c.lines[-1].level == "SKIP"


def test_an_exception_with_a_reason_works_and_one_without_fails(tmp_path):
    mine = page(fold("why", f"<p>{HIRE}</p>"))
    site(tmp_path, {"a": mine, "b": page(fold("why", f"<p>{HIRE}</p>"))})
    ok = {"words": {"own_copy_ok": [{"path": "/a", "fold": "why", "reason": "the same legal wording on purpose"}]}}
    assert run(tmp_path, "/a/", mine, ok).level == "OK"
    no = {"words": {"own_copy_ok": [{"path": "/a", "fold": "why"}]}}
    ln = run(tmp_path, "/a/", mine, no)
    assert ln.level == "FAIL" and "no reason" in ln.what, ln.text()
    other = {"words": {"own_copy_ok": [{"path": "/zzz", "fold": "why", "reason": "x"}]}}
    assert run(tmp_path, "/a/", mine, other).level == "FAIL"


def test_a_short_fold_is_not_judged(tmp_path):
    mine = page(fold("why", "<p>Short fold of only a few words here.</p>"))
    site(tmp_path, {"a": mine, "b": page(fold("why", "<p>Short fold of only a few words here.</p>"))})
    assert run(tmp_path, "/a/", mine).level == "OK"
