"""2.4.9: seo.title-query warns (rule 74) when the page keeps its live title; words.question-title skips the byline."""
import json
from pathlib import Path

from gatelib import CHECKS
from gatelib.core import Ctx, run_check


def last(cid, html, project=Path("/nonexistent"), key="g", path="/g/", ptype="post"):
    c = Ctx(project=project, path=path, key=key, ptype=ptype, cfg={"stack": "static"}, html=html, url="http://127.0.0.1:9" + path, status=200)
    run_check(c, CHECKS[cid])
    return c.lines[-1]


def test_kept_live_title_is_a_warning(tmp_path):
    (tmp_path / "inventory").mkdir()
    (tmp_path / "inventory" / "inventory.json").write_text(json.dumps({"pages": [{"path": "/g/", "title": "AI in Healthcare: A Guide"}]}))
    (tmp_path / "research" / "plans").mkdir(parents=True)
    (tmp_path / "research" / "plans" / "g.json").write_text(json.dumps({
        "target_searches": ["ai diagnostics software"], "use_target_searches": {"why": "test: plan targets stand in for GSC here"}}))
    html = "<html><head><title>AI in Healthcare: A Guide</title></head><body><main></main></body></html>"
    assert last("seo.title-query", html, project=tmp_path).level == "WARN"
    html2 = html.replace("AI in Healthcare: A Guide", "A New Title We Made")
    assert last("seo.title-query", html2, project=tmp_path).level == "FAIL"


def test_question_title_skips_the_byline():
    html = ("<html><body><main><section><h1>Is AI safe in hospitals?</h1>"
            "<p class='byline'>By Rakesh Patel, updated 20 Nov 2026, eleven minute read</p>"
            "<p>Yes, when it is validated on local data and a clinician stays in the loop.</p></section></main></body></html>")
    assert last("words.question-title", html).level == "OK"


def test_what_question_needs_a_direct_answer_not_yes_no():
    """2.4.10: 'What is FHIR?' is answered by a direct line, not yes/no; a preamble still fails."""
    ok = ("<html><body><main><section><h1>What Is FHIR?</h1>"
          "<p>FHIR is the HL7 standard for exchanging health records through web APIs.</p></section></main></body></html>")
    assert last("words.question-title", ok).level == "OK"
    bad = ok.replace("FHIR is the HL7 standard", "In this guide we explain the HL7 standard")
    assert last("words.question-title", bad).level == "FAIL"
