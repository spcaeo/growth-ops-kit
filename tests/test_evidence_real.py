"""Evidence checks read proof, not names (audit H2): screenshots must be real images of the named width, a decision and an
answer count only with the owner's approval, AI runs need distinct questions with a saved answer, a dossier question needs
an answer under it. Temp HOME, no network."""
import datetime as dt
import json
import os
import time
from pathlib import Path

import pytest

import approvals
from gatelib import CHECKS
from gatelib.core import Ctx, run_check
from test_demo import png


@pytest.fixture(autouse=True)
def _home(tmp_path, monkeypatch):
    (tmp_path / "home").mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))


def line(ctx, cid):
    run_check(ctx, CHECKS[cid])
    return ctx.lines[-1]


def project(tmp_path, entries=()):
    p = tmp_path / "p"
    for d in ("docs", "journal", "research"):
        (p / d).mkdir(parents=True)
    (p / "journal" / "entries.jsonl").write_text("".join(json.dumps(e) + "\n" for e in entries))
    return p


def test_zero_byte_or_wrong_size_shots_do_not_count(tmp_path):
    p = project(tmp_path)
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text("x")
    old = time.time() - 3600
    os.utime(site / "index.html", (old, old))
    shots = p / "research" / "x-shots"
    shots.mkdir()
    (shots / "a-1366.png").write_bytes(b"")                       # touch-made
    (shots / "a-390.png").write_bytes(png(1366, 800))             # a 1366 image named 390
    cfg = {"site_dir": str(site)}
    ln = line(Ctx(project=p, path="/x", key="x", cfg=cfg), "ev.shots-1366-390")
    assert ln.level == "FAIL" and "1366px" in ln.what and "390px" in ln.what
    (shots / "a-1366.png").write_bytes(png(1366, 800))
    (shots / "a-390.png").write_bytes(png(780, 1600))             # 390 px at 2x
    assert line(Ctx(project=p, path="/x", key="x", cfg=cfg), "ev.shots-1366-390").level == "OK"


def test_a_decision_counts_only_with_the_owners_approval(tmp_path):
    e = {"id": "J0001", "at": "2026-11-19 09:00", "kind": "decision", "pages": ["/x"], "tags": [], "title": "owner said yes", "text": "yes"}
    p = project(tmp_path, [e])
    ln = line(Ctx(project=p, path="/x", key="x", cfg={}, docs=p / "docs"), "ev.decision")
    assert ln.level == "FAIL" and "growth approve decision J0001" in ln.what
    approvals.record(p / "docs", "decision", "J0001", approvals.decision_content(e), by="owner")
    assert line(Ctx(project=p, path="/x", key="x", cfg={}, docs=p / "docs"), "ev.decision").level == "OK"
    e2 = {**e, "title": "owner said yes to everything"}             # the entry edited after approval
    (p / "journal" / "entries.jsonl").write_text(json.dumps(e2) + "\n")
    assert line(Ctx(project=p, path="/x", key="x", cfg={}, docs=p / "docs"), "ev.decision").level == "FAIL"


def test_ai_runs_need_distinct_questions_and_a_saved_answer(tmp_path):
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    p = project(tmp_path)
    runs = p / "journal" / "runs"
    runs.mkdir()
    def entry(i, q, resp):
        f = runs / f"J{i}.json"
        f.write_text(json.dumps({"query": q, "response": resp}))
        return {"id": f"J{i}", "at": now, "kind": "run", "pages": ["/x"], "market": "US", "title": f"chatgpt (US): {q}", "source": str(f.relative_to(p))}
    fake = [entry(i, "q1", "made up") for i in range(10)]           # one question, a 7-character answer, ten times
    (p / "journal" / "entries.jsonl").write_text("".join(json.dumps(e) + "\n" for e in fake))
    ln = line(Ctx(project=p, path="/x", key="x", ptype="money", cfg={}), "ev.ai-baseline")
    assert ln.level == "FAIL" and "0 US runs" in ln.what
    real = [entry(i, f"best board tool question {i}", f"Answer {i}: Acme and Beta are named; Acme is first for small teams.") for i in range(10)]
    (p / "journal" / "entries.jsonl").write_text("".join(json.dumps(e) + "\n" for e in real))
    assert line(Ctx(project=p, path="/x", key="x", ptype="money", cfg={}), "ev.ai-baseline").level == "OK"
    (runs / "J3.json").unlink()                                       # a run whose saved answer is gone
    assert line(Ctx(project=p, path="/x", key="x", ptype="money", cfg={}), "ev.ai-baseline").level == "FAIL"


def test_a_dossier_of_bare_headings_fails(tmp_path):
    p = project(tmp_path)
    (p / "research" / "x-dossier.md").write_text("".join(f"## Q{i}\n\n" for i in range(1, 33)))
    assert line(Ctx(project=p, path="/x", key="x", ptype="money", cfg={}), "ev.dossier").level == "FAIL"
    (p / "research" / "x-dossier.md").write_text("".join(f"## Q{i}\n\n" + "word " * 25 + "\n\n" for i in range(1, 33)))
    assert line(Ctx(project=p, path="/x", key="x", ptype="money", cfg={}), "ev.dossier").level == "OK"


def test_an_owner_question_answered_by_hand_is_seen(tmp_path):
    p = project(tmp_path)
    (p / "research" / "a.md").write_text("x\n")
    st = [{"n": i, "what": f"Step {i}.", "status": "done", "at": "2026-11-19 10:00", "output": "see research/a.md"} for i in range(1, 7)]
    q = {"id": "Q1", "question": "Name the partner?", "task": "T1", "answer": "yes"}
    (p / "docs" / "tasks.json").write_text(json.dumps({"tasks": [{"id": "T1", "title": "Job: /x", "status": "doing", "steps": st}], "questions": [q]}))
    ln = line(Ctx(project=p, path="/x", key="x", cfg={}, docs=p / "docs"), "ev.task-steps")
    assert ln.level == "FAIL" and "Q1" in ln.what and "growth approve answer Q1" in ln.what
    approvals.record(p / "docs", "answer", "Q1", approvals.answer_content(q), by="owner")
    assert line(Ctx(project=p, path="/x", key="x", cfg={}, docs=p / "docs"), "ev.task-steps").level == "OK"


def test_runs_from_an_excluded_engine_do_not_count(tmp_path):
    # owner rule (a real project, 19 Nov 2026): ChatGPT is not a research source; Google AI Overview / AI Mode are
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    p = project(tmp_path)
    runs = p / "journal" / "runs"
    runs.mkdir()
    def entry(i, engine):
        f = runs / f"J{engine}{i}.json"
        f.write_text(json.dumps({"query": f"{engine} question {i}", "response": f"Answer {i} from {engine}: Acme first, Beta second."}))
        return {"id": f"J{engine}{i}", "at": now, "kind": "run", "pages": ["/x"], "market": "US", "tags": ["ai-answer", engine],
                "title": f"{engine} (US): q{i}", "source": str(f.relative_to(p))}
    gpt = [entry(i, "chatgpt") for i in range(10)]
    (p / "journal" / "entries.jsonl").write_text("".join(json.dumps(e) + "\n" for e in gpt))
    cfg = {"research": {"excluded_engines": ["ChatGPT"]}}
    assert line(Ctx(project=p, path="/x", key="x", ptype="money", cfg={}), "ev.ai-baseline").level == "OK"   # no rule: counted
    assert line(Ctx(project=p, path="/x", key="x", ptype="money", cfg=cfg), "ev.ai-baseline").level == "FAIL"
    google = [entry(i, "google-ai-mode") for i in range(10)]
    (p / "journal" / "entries.jsonl").write_text("".join(json.dumps(e) + "\n" for e in gpt + google))
    assert line(Ctx(project=p, path="/x", key="x", ptype="money", cfg=cfg), "ev.ai-baseline").level == "OK"


def test_an_owner_delegation_lets_the_leads_verdict_stand_in(tmp_path):
    d = {"id": "J0001", "at": "2026-11-19 15:00", "kind": "decision", "pages": ["/x", "/y"], "tags": [],
         "title": "Delegation: lead's VERDICT stands in for my look", "text": "RhinoMove plan pages until 2099-12-31"}
    v = {"id": "J0002", "at": "2026-11-19 16:00", "kind": "decision", "pages": ["/x"], "tags": [],
         "title": "Lead VERDICT: OK", "text": "reviewed screens 1366/390, gate 0 FAIL"}
    p = project(tmp_path, [d, v])
    c = lambda path="/x": Ctx(project=p, path=path, key="x", cfg={}, docs=p / "docs")   # noqa: E731
    assert line(c(), "ev.decision").level == "FAIL"                       # the delegation is not approved yet
    approvals.record(p / "docs", "decision", "J0001", approvals.decision_content(d), by="owner")
    assert line(c(), "ev.decision").level == "OK"                         # approved delegation + the lead's verdict
    assert line(c("/y"), "ev.decision").level == "FAIL"                   # listed page, but no lead verdict yet
    assert line(c("/z"), "ev.decision").level == "FAIL"                   # not in the delegation's pages
    old = {**d, "id": "J0003", "text": "until 2020-01-01"}
    q = project(tmp_path / "q", [old, {**v, "id": "J0004"}])
    approvals.record(q / "docs", "decision", "J0003", approvals.decision_content(old), by="owner")
    ln = line(Ctx(project=q, path="/x", key="x", cfg={}, docs=q / "docs"), "ev.decision")
    assert ln.level == "FAIL" and "ended" in ln.what


def test_a_delegation_in_growth_json_lets_the_leads_verdict_stand_in(tmp_path):
    v = {"id": "J0002", "at": "2026-11-19 16:00", "kind": "decision", "pages": ["/x"], "tags": [],
         "title": "Lead VERDICT: OK", "text": "reviewed"}
    p = project(tmp_path, [v])
    good = {"decision_delegation": {"to": "lead", "pages": ["/x/"], "until": "2099-12-31",
                                    "why": "owner in chat: publish without waiting for me"}}
    c = lambda cfg, path="/x": Ctx(project=p, path=path, key="x", cfg=cfg, docs=p / "docs")   # noqa: E731
    assert line(c({}), "ev.decision").level == "FAIL"
    assert line(c(good), "ev.decision").level == "OK"
    assert line(c(good, "/other"), "ev.decision").level == "FAIL"                       # page not listed
    old = {"decision_delegation": {**good["decision_delegation"], "until": "2020-01-01"}}
    assert line(c(old), "ev.decision").level == "FAIL"                                   # expired
    bare = {"decision_delegation": {**good["decision_delegation"], "why": ""}}
    assert line(c(bare), "ev.decision").level == "FAIL"                                  # no owner words
