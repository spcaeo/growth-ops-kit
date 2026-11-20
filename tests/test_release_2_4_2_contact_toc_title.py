"""2.4.2: the conversion page skips hero-height and label-same (its form is the first fold, rule 38); dialog.call matches
the contact path with or without the slash; a plan's use_target_searches overrides Search Console for seo.title-query."""
import json
from pathlib import Path

from gatelib import CHECKS
from gatelib.core import Ctx, run_check

CFG = {"stack": "static", "conversion_path": "/contact-us/", "cta": {"contact_path": "/contact-us/"},
       "features": {"call_dialog": True}}


def last(cid, path, html="<html><body><main><form><input name=e><button>Send</button></form></main></body></html>",
         cfg=CFG, ptype="core", project=Path("/nonexistent"), key="x"):
    c = Ctx(project=project, path=path, key=key, ptype=ptype, cfg=cfg, html=html, url="http://127.0.0.1:9" + path, status=200)
    run_check(c, CHECKS[cid])
    return c.lines[-1]


def test_contact_page_skips_hero_and_label_and_dialog():
    assert last("layout.hero-height", "/contact-us/").level == "SKIP"
    assert last("cta.label-same", "/contact-us/").level == "SKIP"
    for p in ("/contact-us/", "/contact-us"):
        assert last("dialog.call", p).level == "OK"


def test_title_query_uses_plan_targets_with_reason(tmp_path):
    (tmp_path / "research" / "plans").mkdir(parents=True)
    plan = {"target_searches": ["hire patient portal developers"],
            "use_target_searches": {"why": "the register gives this page's GSC searches to the hub"}}
    (tmp_path / "research" / "plans" / "exp.json").write_text(json.dumps(plan))
    html = "<html><head><title>Hire Patient Portal Developers | Space-O</title></head><body><main></main></body></html>"
    ln = last("seo.title-query", "/x/experts/", html=html, ptype="money", project=tmp_path, key="exp", cfg={"stack": "static"})
    assert ln.level == "OK", ln.what
