"""The research record cannot be typed in (audit H9): no date after today, every row cites a source, a raw vendor fact
carries its saved page with the quote in it, a frozen baseline is re-frozen only after the owner approves it once, and a
task that names research meets the research-browser gate without --playbook."""
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import research  # noqa: E402
from test_research_record import ctx_for, fact, rec, run  # noqa: E402
from test_research_gate import project as gated_project  # noqa: E402
from wizard_helpers import growth, owner_approve  # noqa: E402

TODAY = dt.date.today()
FUTURE = (TODAY + dt.timedelta(days=400)).isoformat()


def test_dates_after_today_are_never_fresh(tmp_path):
    r = rec(search={**rec()["search"], "window": {"from": FUTURE, "to": FUTURE}},
            ai_answers=[{**rec()["ai_answers"][0], "seen_on": FUTURE}], vendor_facts=[fact(read_on=FUTURE)])
    probs = "; ".join(research.problems(r, TODAY, {}, tmp_path))
    assert "search window to" in probs and "ai_answers[0]: seen_on" in probs and "vendor_facts[0]: read_on" in probs and "after today" in probs


def test_rows_without_a_source_fail(tmp_path):
    r = rec(ai_answers=[{k: v for k, v in rec()["ai_answers"][0].items() if k != "source"}],
            paa=[{**rec()["paa"][0], "source": "research/raw/none.html"}])
    probs = "; ".join(research.problems(r, TODAY, {}, tmp_path))
    assert "ai_answers[0]: no source" in probs and "paa[0]: source file research/raw/none.html does not exist" in probs
    assert run("ev.research-record", ctx_for(tmp_path, r)).level == "FAIL"


def test_a_raw_fact_needs_its_saved_page_with_the_quote_in_it(tmp_path):
    raw = tmp_path / "research" / "raw"
    raw.mkdir(parents=True)
    (raw / "acme.html").write_text("<p>Basic <b>$12 user / mo</b>, billed monthly</p>")
    assert "no raw_file" in research.raw_problem(fact(how_read="raw"), tmp_path)
    assert research.raw_problem(fact(how_read="raw", raw_file="research/raw/acme.html"), tmp_path) is None
    assert "not in" in research.raw_problem(fact(how_read="raw", raw_file="research/raw/acme.html", quote="$9 user / mo"), tmp_path)


def cli(p, *args):
    return subprocess.run([sys.executable, str(Path(research.__file__)), *args], capture_output=True, text=True,
                          env={**os.environ, "GROWTH_PROJECT": str(p), "HOME": str(p.parent / "home")}, cwd=p)


def test_the_cli_refuses_future_dates_and_sourceless_rows(tmp_path):
    p = tmp_path / "p"
    (p / "docs").mkdir(parents=True)
    (p / "growth.json").write_text(json.dumps({"name": "T", "site_url": "https://t.example"}))
    assert cli(p, "init", "/pm", "--key", "pm").returncode == 0
    r = cli(p, "ai", "/pm", "--key", "pm", "--engine", "chatbot", "--market", "US", "--query", "q", "--summary", "made up")
    assert r.returncode != 0 and "source" in r.stderr
    r = cli(p, "ai", "/pm", "--key", "pm", "--engine", "chatbot", "--market", "US", "--query", "q", "--summary", "s",
            "--source", "https://chat.example.com/share/1", "--seen-on", FUTURE)
    assert r.returncode != 0 and "after today" in r.stderr
    r = cli(p, "fact", "/pm", "--key", "pm", "--vendor", "Acme", "--fact", "f", "--value", "$12", "--view", "Monthly", "--how", "raw",
            "--source-url", "https://acme.example.com/p", "--quote", "$12 user / mo")
    assert r.returncode != 0 and "raw_file" in r.stderr
    assert json.loads((p / "research" / "pm-record.json").read_text())["ai_answers"] == []


def test_a_frozen_baseline_is_refrozen_only_after_the_owner_approves_it_once(tmp_path):
    p = tmp_path / "p"
    (p / "docs").mkdir(parents=True)
    (p / "growth.json").write_text(json.dumps({"name": "T", "site_url": "https://t.example"}))
    (tmp_path / "home").mkdir()
    (p / "research").mkdir()
    (p / "research" / "pm-record.json").write_text(json.dumps(rec()))
    assert cli(p, "baseline", "/pm", "--key", "pm").returncode == 0
    r = cli(p, "baseline", "/pm", "--key", "pm")
    assert r.returncode != 0 and "--refreeze" in r.stderr
    why = "the old window held a site outage week"
    r = cli(p, "baseline", "/pm", "--key", "pm", "--refreeze", "--reason", why)
    assert r.returncode != 0 and "growth approve baseline pm" in r.stderr
    rc, out = owner_approve(tmp_path, "baseline", "pm", "--reason", why, cwd=p)
    assert rc == 0, out
    assert cli(p, "baseline", "/pm", "--key", "pm", "--refreeze", "--reason", why).returncode == 0
    b = json.loads((p / "research" / "pm-record.json").read_text())["baseline"]
    assert b["approval"] == "A0001" and b["reason"] == why and len(b["history"]) == 1
    r = cli(p, "baseline", "/pm", "--key", "pm", "--refreeze", "--reason", why)         # one approval, one re-freeze
    assert r.returncode != 0 and "already used" in r.stderr


def test_a_task_that_names_research_meets_the_gate_without_a_playbook(tmp_path):
    folder, _ = gated_project(tmp_path)
    r = growth(tmp_path, "tasks", "add", "Page: /x", "do the research for it", cwd=folder)
    assert r.returncode != 0 and "research step" in (r.stdout + r.stderr)
    r = growth(tmp_path, "tasks", "add", "ChatGPT answers for /x", "", cwd=folder)
    assert r.returncode != 0
    assert growth(tmp_path, "tasks", "add", "Fix the footer: /x", "the link is broken", cwd=folder).returncode == 0
