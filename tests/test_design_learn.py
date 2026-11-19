"""`growth design learn` and `calibrate` (#58): the design map is proposed from a site's own pages, a meaning-first find
needs nothing, calibration lists detectors that FAIL on known-good pages as suspect, and read-next is found by meaning.
Example pages only; the local server binds 127.0.0.1 on a free port and is shut down."""
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from test_design import BASE, CLASSES, DESIGN, SEMANTIC, run

import site_design

TOOLS = Path(site_design.__file__).parent


def test_a_semantic_site_needs_no_map():
    res = site_design.learn({"/a/": SEMANTIC, "/b/": SEMANTIC}, BASE, Path("."))
    for c in ("site_header", "site_footer", "main", "cover_image", "byline", "updated_date", "faq_question"):
        assert res[c]["by"] == "meaning", c
    assert not [c for c, e in res.items() if e["by"] == "proposed"]


def test_a_class_built_site_gets_selectors_from_its_own_class_names():
    res = site_design.learn({"/a/": CLASSES, "/b/": CLASSES}, BASE, Path("."))
    assert res["cover_image"] == {**res["cover_image"], "by": "proposed", "selector": ".hero-pic img"}
    assert res["site_header"]["selector"] == ".top-bar" and res["site_footer"]["selector"] == ".bottom"
    assert res["main"]["selector"] in (".content", ".post")       # both hold the article; either finds it
    assert res["updated_date"]["selector"] in (".stamp", ".meta")


def test_proposals_that_match_in_the_design_map_make_the_detectors_pass():
    res = site_design.learn({"/a/": CLASSES}, BASE, Path("."))
    learned = {c: e["selector"] for c, e in res.items() if e["by"] == "proposed"}
    for cid in ("post.cover", "layout.shared-frame"):
        assert run(CLASSES, cid, {**BASE, "design": learned}).level == "OK", cid


def test_a_selector_is_not_proposed_when_it_matches_on_too_few_pages():
    only_one = {"/a/": CLASSES, "/b/": "<html><body><main><h1>x</h1></main></body></html>", "/c/": "<html><body><p>y</p></body></html>"}
    assert site_design.learn(only_one, BASE, Path("."))["cover_image"]["by"] == "missing"


def test_calibrate_lists_each_failing_detector_with_its_pages():
    got = site_design.calibrate_lines({"/a/": ["FAIL 61 [post.cover] no cover -> x", "FAIL 43 [layout.shared-frame] y -> z"],
                                       "/b/": ["FAIL 61 [post.cover] no cover -> x"]})
    assert got[0][0] == "post.cover" and got[0][1] == ["/a/", "/b/"] and got[1][0] == "layout.shared-frame"
    assert site_design.calibrate_lines({"/a/": []}) == []


def test_design_json_is_read_under_growth_json(tmp_path):
    (tmp_path / "design.json").write_text(json.dumps({"map": {**DESIGN, "cover_image": ".nope"}}))
    from gatelib.core import Ctx
    from gatelib import design
    ctx = Ctx(project=tmp_path, cfg={"design": {"cover_image": ".hero-pic img"}}, html=CLASSES, status=200)
    assert design.design_map(ctx)["cover_image"] == ".hero-pic img" and design.design_map(ctx)["byline"] == "a.who"


def test_read_next_is_found_by_its_label_and_counted_once():
    page = SEMANTIC.replace("<h2>Next</h2>", '<nav aria-label="Read next"><h2>More</h2><a href="/b/">B</a></nav><h2>Next</h2>')
    assert run(page, "post.read-next", BASE).level == "OK"
    assert run(page.replace("</article>", '<aside><h3>Read next</h3></aside></article>"'), "post.read-next", BASE).level == "FAIL"


@pytest.fixture
def served(tmp_path):
    from serve_build import make_server
    site = tmp_path / "site"
    (site / "post").mkdir(parents=True)
    (site / "index.html").write_text(CLASSES)
    (site / "post" / "index.html").write_text(CLASSES)
    srv = make_server(site, 0)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()
    t.join(5)


def cli(project, *args):
    env = {**os.environ, "GROWTH_PROJECT": str(project)}
    return subprocess.run([sys.executable, str(TOOLS / "site_design.py"), *args], capture_output=True, text=True, env=env, cwd=project)


def test_learn_writes_design_json_from_a_local_preview(demo_project, served):
    r = cli(demo_project, "learn", "--base", served, "--page", "/", "--page", "/post/", "--write")
    assert r.returncode == 0, r.stderr
    d = json.loads((demo_project / "design.json").read_text())
    assert d["map"]["cover_image"] == ".hero-pic img" and d["learned"]["pages"] == ["/", "/post/"]


def test_calibrate_reports_suspect_detectors_and_exits_1(demo_project, served):
    r = cli(demo_project, "calibrate", "--base", served, "--page", "/post/")
    assert r.returncode == 1 and "SUSPECT" in r.stdout


def test_learn_refuses_the_real_site(demo_project):
    cfg = json.loads((demo_project / "growth.json").read_text())
    cfg["site_url"] = "https://www.example.com"
    (demo_project / "growth.json").write_text(json.dumps(cfg))
    r = cli(demo_project, "learn", "--base", "https://www.example.com")
    assert r.returncode != 0 and "Refusing" in r.stderr
