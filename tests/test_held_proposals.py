"""Held-field proposals are stored structured in the page plan and go stale when a fact they quote changes (#61)."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from gatelib import CHECKS
from gatelib.core import Ctx, run_check

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "kit" / "tools"
PAGE = "<html><body><main><h1>A vs B</h1><h2>Sums</h2><p>For 10 people B saves $159.90 a month; A's plan starts at $259.90.</p></main></body></html>"


def held(project, *args):
    env = {**os.environ, "GROWTH_PROJECT": str(project)}
    return subprocess.run([sys.executable, str(TOOLS / "held.py"), *args], capture_output=True, text=True, env=env, cwd=project)


def plan(project, key="ab"):
    return json.loads((project / "research" / "plans" / f"{key}.json").read_text())


def gate(project, html=None, key="ab"):
    ctx = Ctx(project=project, path="/ab/", key=key, cfg={}, html=html, status=200 if html else 0)
    run_check(ctx, CHECKS["ev.held-proposals"])
    return ctx.lines[0]


def add(project):
    r = held(project, "add", "ab", "--field", "description", "--current", "old text", "--proposed", "B saves $19.90 a month for 10 people",
             "--fact", "$19.90")
    assert r.returncode == 0, r.stderr
    return r


def test_a_proposal_is_stored_structured_in_the_page_plan(demo_project):
    add(demo_project)
    e = plan(demo_project)["held"][0]
    assert {"id", "field", "current", "proposed", "facts", "date", "status"} <= set(e)
    assert e["status"] == "open" and e["facts"] == ["$19.90"] and e["field"] == "description"


def test_a_changed_fact_marks_quoting_proposals_stale_and_only_those(demo_project):
    add(demo_project)
    held(demo_project, "add", "ab", "--field", "title", "--proposed", "A vs B compared", "--fact", "2026 prices")
    r = held(demo_project, "changed", "ab", "--old", "$19.90", "--new", "$159.90", "--why", "review fix")
    assert "H1" in r.stdout and "H2" not in r.stdout
    h = {e["id"]: e for e in plan(demo_project)["held"]}
    assert h["H1"]["status"] == "stale" and "review fix" in h["H1"]["stale_reason"] and h["H2"]["status"] == "open"
    assert "STALE" in held(demo_project, "list", "ab").stdout


def test_a_figure_written_another_way_still_counts_as_the_same_fact(demo_project):
    held(demo_project, "add", "ab", "--field", "description", "--proposed", "Save $1,918.80 a year", "--fact", "$1,918.80")
    assert "H1" in held(demo_project, "changed", "ab", "--old", "$1918.80").stdout


def test_rewrite_makes_it_open_again_and_apply_or_drop_remove_it_from_the_list(demo_project):
    add(demo_project)
    held(demo_project, "changed", "ab", "--old", "$19.90")
    held(demo_project, "rewrite", "ab", "H1", "--proposed", "B saves $159.90 a month for 10 people", "--fact", "$159.90")
    e = plan(demo_project)["held"][0]
    assert e["status"] == "open" and e["facts"] == ["$159.90"] and "stale_reason" not in e
    held(demo_project, "apply", "ab", "H1")
    assert "no open" in held(demo_project, "list", "ab").stdout


def test_the_gate_fails_on_a_stale_proposal_and_passes_once_rewritten(demo_project):
    assert gate(demo_project).level == "OK"                                   # none held
    add(demo_project)
    held(demo_project, "changed", "ab", "--old", "$19.90")
    ln = gate(demo_project)                                                   # static: the stored status alone
    assert ln.level == "FAIL" and "H1" in ln.what
    held(demo_project, "rewrite", "ab", "H1", "--proposed", "B saves $159.90 a month", "--fact", "$159.90")
    assert gate(demo_project, PAGE).level == "OK"


def test_the_gate_finds_a_proposal_whose_fact_left_the_page_without_anyone_marking_it(demo_project):
    add(demo_project)                                                         # quotes $19.90; the page says $159.90
    ln = gate(demo_project, PAGE)
    assert ln.level == "FAIL" and "no longer states" in ln.what and "$19.90" in ln.what


def test_ready_lists_the_held_proposals_with_their_status(demo_project, monkeypatch):
    add(demo_project)
    monkeypatch.setenv("GROWTH_PROJECT", str(demo_project))
    sys.path.insert(0, str(TOOLS))
    import ready
    monkeypatch.setattr(ready, "PROJECT", demo_project)
    ls = ready.held_proposals("ab")
    assert len(ls) == 1 and "OPEN" in ls[0] and "$19.90" in ls[0]
