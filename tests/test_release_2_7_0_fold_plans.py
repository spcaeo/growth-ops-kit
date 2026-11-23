"""2.7.0: a fold plan is written for its own page (ev.fold-plan-own) and the page follows it (ev.fold-plan-match)."""
import json
from pathlib import Path

from gatelib import CHECKS
from gatelib.c_plan import FOLD_FIELDS
from gatelib.core import Ctx, run_check


def plan(fold, **over):
    f = {k: f"{fold} {k} written for this page only" for k in FOLD_FIELDS}
    f.update(fold=fold, **over)
    return {"page": "/x/", "goal": "g", "folds": [f], "shared": {}}


def ctx(tmp_path, key, html="", cid="ev.fold-plan-own"):
    c = Ctx(project=tmp_path, path="/x/", key=key, ptype="money", cfg={}, html=html, url="http://127.0.0.1:9/x/", status=200)
    run_check(c, CHECKS[cid])
    return c.lines[-1]


def test_copied_answers_fail(tmp_path):
    d = tmp_path / "research" / "plans"
    d.mkdir(parents=True)
    for k in ("a", "b", "c"):
        (d / f"{k}.json").write_text(json.dumps(plan(k, headline="the fold heading, as a buyer would say it")))
    ln = ctx(tmp_path, "a")
    assert ln.level == "FAIL" and "headline" in ln.what
    (d / "d.json").write_text(json.dumps(plan("d")))
    assert ctx(tmp_path, "d").level == "OK"


def test_built_page_must_follow_the_plan(tmp_path):
    d = tmp_path / "research" / "plans"
    d.mkdir(parents=True)
    p = plan("proof", surface="warm", job="prove: the buyer sees named results", headline="Results from named hospital projects",
             cta="none: the ask is in the next fold", controls="none: a still list", visual="a drawn chart of three results")
    (d / "pg.json").write_text(json.dumps(p))
    good = ('<html><body><main><section data-fold="proof" data-surface="warm" data-job="prove"><h2>Results from named hospital projects</h2>'
            '<svg></svg></section></main></body></html>')
    assert ctx(tmp_path, "pg", good, "ev.fold-plan-match").level == "OK"
    bad = good.replace('data-surface="warm"', 'data-surface="dark"').replace("<svg></svg>", "")
    ln = ctx(tmp_path, "pg", bad, "ev.fold-plan-match")
    assert ln.level == "FAIL" and "planned surface warm" in ln.what and "picture" in ln.what
