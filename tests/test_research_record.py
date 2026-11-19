"""The research record is READ by the gate (#53): vendor numbers need a fresh row read by raw text or a browser (#43), chosen
People-also-ask questions are answered, the brief and plan come from the record, and the tracker fills the search section.
Invented vendors and example.com only; no network."""
import datetime as dt
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "kit" / "tools"
TODAY = dt.date.today()


def d(n):
    return (TODAY - dt.timedelta(days=n)).isoformat()


def fact(**kw):
    row = dict(vendor="Acme Boards", fact="Basic plan per user a month", value="$12", shown_as="$12", view="Monthly", how_read="browser",
               source_url="https://acme.example.com/pricing", quote="$12 user / mo, billed monthly", read_on=d(2))
    row.update(kw)
    return row


def rec(**kw):
    r = dict(schema=1, page="/pm", key="pm",
             search=dict(scope="page", window={"from": d(30), "to": d(3)}, definition="page rows", totals=dict(clicks=5, impressions=900, position=6.1),
                         queries=[dict(query="board tools", clicks=3, impressions=500, position=5.0)]),
             site_search={}, ai_answers=[dict(engine="chatbot", market="US", query="best board tools", summary="Acme named", seen_on=d(2),
                                              source="https://chat.example.com/share/abc")],     # audit H9: every row cites its source
             paa=[dict(question="Is Acme free?", status="chosen", reason="", answered_in="", source="https://search.example.com/?q=acme"),
                  dict(question="Who invented boards?", status="declined", reason="off topic for buyers", answered_in="",
                       source="https://search.example.com/?q=acme")],
             vendor_facts=[fact()], other_numbers=[], baseline={})
    r.update(kw)
    return r


def ctx_for(tmp_path, record, html="<html><body><main><h2>Is Acme free?</h2><p>Basic is $12 per user.</p></main></body></html>", cfg=None):
    sys.path.insert(0, str(TOOLS))
    from gatelib.core import Ctx
    (tmp_path / "research").mkdir(exist_ok=True)
    if record is not None:
        (tmp_path / "research" / "pm-record.json").write_text(json.dumps(record))
    return Ctx(project=tmp_path, path="/pm", key="pm", html=html, cfg=cfg or {}, today=TODAY)


def run(cid, ctx):
    from gatelib import CHECKS
    from gatelib.core import run_check
    run_check(ctx, CHECKS[cid])
    return ctx.lines[-1]


def test_a_complete_record_passes_and_a_page_matching_it_passes(tmp_path):
    c = ctx_for(tmp_path, rec())
    assert run("ev.research-record", c).level == "OK"
    assert run("ev.vendor-numbers", c).level == "OK"
    assert run("ev.paa-answered", c).level == "OK"


def test_no_record_fails_the_record_check_and_skips_the_page_checks(tmp_path):
    c = ctx_for(tmp_path, None)
    assert run("ev.research-record", c).level == "FAIL"
    assert run("ev.vendor-numbers", c).level == "SKIP"


def test_a_number_read_only_from_a_summary_fails_the_record(tmp_path):
    c = ctx_for(tmp_path, rec(vendor_facts=[fact(how_read="summary")]))
    ln = run("ev.research-record", c)
    assert ln.level == "FAIL" and "summary is not the source" in ln.what


def test_a_fact_without_its_view_quote_or_date_fails(tmp_path):
    c = ctx_for(tmp_path, rec(vendor_facts=[fact(view="", quote="")]))
    assert "missing view, quote" in run("ev.research-record", c).what


def test_an_amount_on_the_page_with_no_row_fails_and_other_numbers_allows_it(tmp_path):
    html = "<html><body><p>Basic is $12 and Pro is $30 per user. Is Acme free?</p></body></html>"
    ln = run("ev.vendor-numbers", ctx_for(tmp_path, rec(), html))
    assert ln.level == "FAIL" and "'$30'" in ln.what and "'$12'" not in ln.what
    ok = ctx_for(tmp_path, rec(other_numbers=[dict(value="$30", why="our own example sum")]), html)
    assert run("ev.vendor-numbers", ok).level == "OK"


def test_a_stale_fact_row_fails_the_page_number_check(tmp_path):
    ln = run("ev.vendor-numbers", ctx_for(tmp_path, rec(vendor_facts=[fact(read_on=d(60))])))
    assert ln.level == "FAIL" and "older than 30 days" in ln.what
    cfg = {"research": {"fact_days": 90}}
    assert run("ev.vendor-numbers", ctx_for(tmp_path, rec(vendor_facts=[fact(read_on=d(60))]), cfg=cfg)).level == "OK"


def test_a_chosen_paa_question_must_be_answered_and_a_declined_one_needs_a_reason(tmp_path):
    html = "<html><body><p>Nothing about it.</p></body></html>"
    assert run("ev.paa-answered", ctx_for(tmp_path, rec(), html)).level == "FAIL"
    ok = rec(paa=[dict(question="Is Acme free?", status="chosen", answered_in="Acme has no free plan")])
    assert run("ev.paa-answered", ctx_for(tmp_path, ok, "<p>Acme has no free plan; Basic is $12.</p>")).level == "OK"
    bad = rec(paa=[dict(question="Why?", status="declined", reason="")])
    assert "declined with no reason" in run("ev.research-record", ctx_for(tmp_path, bad)).what


def test_an_empty_section_needs_a_reason(tmp_path):
    ln = run("ev.research-record", ctx_for(tmp_path, rec(paa=[])))
    assert ln.level == "FAIL" and "paa_none" in ln.what
    assert run("ev.research-record", ctx_for(tmp_path, rec(paa=[], paa_none="the search shows no People also ask box"))).level == "OK"


def test_the_search_window_must_be_the_pages_own_and_recent(tmp_path):
    r = rec()
    r["search"]["scope"] = "site"
    assert "scope must be 'page'" in run("ev.research-record", ctx_for(tmp_path, r)).what
    r = rec()
    r["search"]["window"] = {"from": d(200), "to": d(180)}
    assert "older than 45 days" in run("ev.research-record", ctx_for(tmp_path, r)).what


def test_the_plan_text_and_target_searches_come_from_the_record():
    sys.path.insert(0, str(TOOLS))
    import research
    t = research.plan_markdown(rec())
    assert "board tools" in t and "Is Acme free?" in t and "view Monthly" in t and "same numbers" in t
    assert research.target_searches(rec()) == ["board tools"]


def tool(project, script, *args):
    env = {**os.environ, "GROWTH_PROJECT": str(project), "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run([sys.executable, str(TOOLS / script), *args], capture_output=True, text=True, env=env, cwd=project)


def test_the_command_line_builds_a_record_that_passes_check(demo_project):
    p = demo_project
    assert tool(p, "research.py", "init", "/pm", "--key", "pm").returncode == 0
    assert tool(p, "research.py", "check", "/pm", "--key", "pm").returncode == 1            # empty: reasons missing
    db = p / "page-tracker" / "tracker.db"
    c = sqlite3.connect(db)
    c.executescript("CREATE TABLE search(path TEXT, day TEXT, clicks INTEGER, impressions INTEGER, ctr REAL, position REAL, final INTEGER, PRIMARY KEY(path, day));"
                    "CREATE TABLE search_queries(path TEXT, snapshot TEXT, query TEXT, clicks INTEGER, impressions INTEGER, position REAL);")
    for i in range(1, 29):
        c.execute("INSERT INTO search VALUES('/pm',?,1,100,0.01,4.0,1)", (d(i),))
        c.execute("INSERT INTO search VALUES('*',?,10,1000,0.01,8.0,1)", (d(i),))
    c.execute("INSERT INTO search_queries VALUES('/pm',?,'board tools',3,500,5.0)", (d(1),))
    c.commit(); c.close()
    assert tool(p, "research.py", "search", "/pm", "--key", "pm").returncode == 0
    r = json.loads((p / "research" / "pm-record.json").read_text())
    assert r["search"]["totals"] == dict(clicks=28, impressions=2800, position=4.0) and r["site_search"]["scope"] == "site"
    assert r["site_search"]["totals"]["impressions"] == 28000                                # kept apart from the page's
    assert tool(p, "research.py", "fact", "/pm", "--key", "pm", "--vendor", "Acme", "--fact", "Basic", "--value", "$12", "--view", "Monthly",
                "--how", "summary", "--source-url", "https://acme.example.com/p", "--quote", "$12").returncode == 0
    assert tool(p, "research.py", "check", "/pm", "--key", "pm").returncode == 1            # a summary is refused by check
    assert tool(p, "research.py", "fact", "/pm", "--key", "pm", "--vendor", "Acme", "--fact", "Basic").returncode != 0   # no proof, refused
    assert tool(p, "research.py", "plan", "/pm", "--key", "pm").returncode == 0
    plan = json.loads((p / "research" / "plans" / "pm.json").read_text())
    assert plan["target_searches"] == ["board tools"]
    assert tool(p, "research.py", "baseline", "/pm", "--key", "pm").returncode == 0
    assert json.loads((p / "research" / "pm-record.json").read_text())["baseline"]["totals"]["impressions"] == 2800


def test_the_brief_carries_the_record_and_fold_plan_init_keeps_its_target_searches(demo_project):
    p = demo_project
    db = p / "docs" / "tasks.json"
    db.write_text(json.dumps({"tasks": [{"id": "T1", "title": "post: /pm", "steps": [], "owner_words": ""}]}))
    task = "T1"
    (p / "research" / "pm-record.json").write_text(json.dumps(rec()))
    r = tool(p, "brief.py", "/pm", "--type", "post", "--task", task, "--key", "pm")
    assert r.returncode == 0, r.stderr
    assert "Research record for /pm" in r.stdout and "board tools" in r.stdout and "Is Acme free?" in r.stdout
    missing = tool(p, "brief.py", "/other", "--type", "post", "--task", task, "--key", "other")
    assert "Research record: MISSING" in missing.stdout
    assert tool(p, "research.py", "plan", "/pm", "--key", "pm").returncode == 0           # a plan with no folds yet
    assert tool(p, "fold_plan.py", "init", "/pm", "--key", "pm").returncode == 0           # init may fill it in, keeping what the record wrote
    assert json.loads((p / "research" / "plans" / "pm.json").read_text())["target_searches"] == ["board tools"]
