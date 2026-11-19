"""The audit fixes joined up (each fixer batch left changes for other files): READY reads the approvals and the proofs, the
research gate reads the project's files, the workflow cuts at the proof's commit, the journal answers go through the owner,
JSON files are written under the lock, the live-site rule reaches every fetcher, one transcript reader, setup files, model
roles. Temp folders only; no network."""
import json
import os
import re
import subprocess
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "kit" / "tools"
sys.path.insert(0, str(Path(__file__).parent))
from wizard_helpers import growth, owner_approve  # noqa: E402
from test_ready_fail_closed import gate_out, rdy  # noqa: E402,F401  (the ready fixture)


# ---- 1. ready.py -------------------------------------------------------------------------------------------------------

def blocked_out(cid):
    return gate_out(drop=[cid], blocked=1, extra=[f"BLOCKED-SKIP {cid}: no headless browser installed"])


def test_a_blocked_skip_is_accepted_only_when_the_owner_approved_an_exception(rdy, monkeypatch, capsys):
    import approvals
    seen = []
    monkeypatch.setattr(approvals, "excuses_blocked_skip", lambda project, cfg, cid, today=None: seen.append(cid) or (True, "excused"))
    assert rdy(0, blocked_out("ui.phone")) == 0 and seen == ["ui.phone"]
    monkeypatch.setattr(approvals, "excuses_blocked_skip", lambda project, cfg, cid, today=None: (False, "no approval"))
    assert rdy(0, blocked_out("ui.phone")) == 1
    assert "could not run (ui.phone)" in capsys.readouterr().out


def test_a_blocked_evidence_or_process_check_is_never_excused(demo_project):
    import approvals
    cfg = {"design_exceptions": [{"check": c, "why": "the owner said so, many words here", "until": "2099-01-01"}
                                 for c in ("ev.review", "proc.no-push-main")]}
    for cid in ("ev.review", "proc.no-push-main"):
        ok, line = approvals.excuses_blocked_skip(demo_project, cfg, cid)
        assert ok is False and line


def test_ready_checks_that_a_proof_exists_and_that_extra_rules_are_still_in_the_file(rdy, demo_project, monkeypatch):
    import ready
    (demo_project / "research").mkdir(exist_ok=True)
    (demo_project / "rules-extra.md").write_text("- house rule: no stock photos\n")
    monkeypatch.setattr(ready, "CFG", {"preview_url": "http://127.0.0.1:9", "checkpoints_extra": "rules-extra.md"})
    plan = demo_project / "research" / "x-checkpoints.md"
    plan.write_text("# Checkpoints\n\n## Manual checks (1)\n\n- [x] rule 530: click test -- research/nothing-here.md\n")
    probs = ready.manual_problems("/x", "x")
    assert any("nothing checkable" in p for p in probs)                          # the named file does not exist
    assert any("missing from the checkpoints file: house rule: no stock photos" in p for p in probs)   # the rule was deleted
    (demo_project / "research" / "nothing-here.md").write_text("seen\n")
    plan.write_text(plan.read_text() + "- [x] house rule: no stock photos -- research/nothing-here.md\n")
    assert ready.manual_problems("/x", "x") == []


def test_the_ready_ledger_is_written_under_the_lock(rdy, demo_project):
    import ready
    for i in range(3):
        assert rdy(0, gate_out()) == 0
    assert (ready.LEDGER.with_name("ready.json.lock")).exists()


# ---- 2. c_research passes the project ----------------------------------------------------------------------------------

def test_the_research_gate_reads_sources_from_the_gate_projects_folder(tmp_path, monkeypatch):
    import research
    from test_research_record import ctx_for, rec, run
    seen = {}
    real = research.problems
    monkeypatch.setattr(research, "problems", lambda *a, **k: seen.update(k) or real(*a, **k))
    r = rec()
    r["ai_answers"][0]["source"] = "research/raw/chat.html"
    (tmp_path / "research" / "raw").mkdir(parents=True)
    (tmp_path / "research" / "raw" / "chat.html").write_text("<p>answer</p>")
    c = ctx_for(tmp_path, r)
    assert run("ev.research-record", c).level == "OK"
    assert seen.get("project") == tmp_path


# ---- 3. workflow cuts at the proof's commit ----------------------------------------------------------------------------

def git(p, *a):
    return subprocess.run(["git", "-c", "user.email=t@example.com", "-c", "user.name=T", *a], cwd=p, capture_output=True, text=True)


def wf_project(tmp_path):
    p = tmp_path / "wf"
    (p / "docs").mkdir(parents=True)
    (p / "growth.json").write_text(json.dumps({"name": "T", "site_url": "https://t.example", "timezone": "UTC"}))
    (p / "docs" / "tasks.json").write_text(json.dumps({"tasks": [], "questions": []}))
    git(p, "init", "-q")
    git(p, "add", "-A")
    git(p, "commit", "-qm", "init")
    return p


def wf_check(p):
    from test_workflow import run
    return run(p, "workflow", "check")


def test_work_committed_after_the_proofs_commit_is_not_covered_even_in_the_same_minute(tmp_path):
    from test_workflow import run
    p = wf_project(tmp_path)
    (p / "page.md").write_text("page\n")
    git(p, "add", "page.md")
    git(p, "commit", "-qm", "page work")
    head = git(p, "rev-parse", "--short", "HEAD").stdout.strip()
    run(p, "tasks", "add", "Page job", "words")
    run(p, "tasks", "step", "T1", "Edit the page", "--status", "done", "--output", f"commit {head}")
    run(p, "tasks", "status", "T1", "done")
    step = json.loads((p / "docs" / "tasks.json").read_text())["tasks"][0]["steps"][0]
    assert step["last_checked_commit"] == git(p, "rev-parse", "HEAD").stdout.strip()
    assert wf_check(p).returncode == 0                       # everything up to the proof's commit is covered
    (p / "more.md").write_text("more\n")
    git(p, "add", "more.md")
    git(p, "commit", "-qm", "more work, same minute")
    r = wf_check(p)
    assert r.returncode == 2 and "committed since the last page task" in r.stderr and "more.md" in r.stderr


def test_the_cover_commit_is_the_one_stored_with_the_latest_proof():
    import workflow
    tasks = [{"id": "T1", "steps": [{"status": "done", "output": "x", "at": "2026-11-19 10:00 UTC", "last_checked_commit": "aaa"},
                                    {"status": "done", "output": "x", "at": "2026-11-19 11:00 UTC", "last_checked_commit": "bbb"}]}]
    assert workflow.cover_commit(tasks) == "bbb"
    assert workflow.cover_commit([{"id": "T2", "type": "chat", "steps": tasks[0]["steps"]}]) is None


# ---- 4. journal answers, runs, decisions -------------------------------------------------------------------------------

def jr(proj, *args):
    env = {**os.environ, "GROWTH_PROJECT": str(proj), "PYTHONDONTWRITEBYTECODE": "1", "HOME": str(proj.parent / "home")}
    return subprocess.run([sys.executable, str(TOOLS / "journal.py"), *args], capture_output=True, text=True, env=env, cwd=proj, timeout=120)


def test_journal_answer_needs_the_owner_in_their_own_terminal(demo_project, tmp_path):
    assert jr(demo_project, "ask", "--page", "/x", "May we name the partner?").stdout.strip() == "J0001"
    r = jr(demo_project, "answer", "J0001", "yes, name them")                    # an agent's shell: no terminal
    assert r.returncode != 0 and "terminal" in (r.stderr + r.stdout)
    assert "answer" not in (demo_project / "journal" / "entries.jsonl").read_text()
    code, shown = owner_approve(tmp_path, "answer", "J0001", "yes, name them", cwd=demo_project)
    assert code == 0, shown
    lines = [json.loads(l) for l in (demo_project / "journal" / "entries.jsonl").read_text().splitlines()]
    done = [l for l in lines if l.get("of") == "J0001"]
    assert done and done[0]["answer"] == "yes, name them" and done[0]["answered_by"] == "owner" and done[0]["approval"].startswith("A")
    log = [json.loads(l) for l in (demo_project / "docs" / "approvals.jsonl").read_text().splitlines()]
    assert log[-1]["kind"] == "answer" and log[-1]["ref"] == "J0001"


def test_journal_run_records_the_hash_of_its_raw_answer_and_how_it_was_captured(demo_project, tmp_path):
    import hashlib
    f = tmp_path / "answer.txt"
    f.write_bytes("The answer, with café\n".encode())
    r = jr(demo_project, "run", "--page", "/x", "--engine", "chatbot", "--query", "best tools", "--response-file", str(f),
           "--capture-method", "browser")
    assert r.returncode == 0, r.stderr
    run_file = next((demo_project / "journal" / "runs").rglob("J0001-*.json"))
    run = json.loads(run_file.read_text())
    sha = hashlib.sha256(f.read_bytes()).hexdigest()
    assert run["response_sha256"] == sha and run["capture_method"] == "browser"
    entry = json.loads((demo_project / "journal" / "entries.jsonl").read_text().splitlines()[0])
    assert entry["response_sha256"] == sha and entry["capture_method"] == "browser"
    r2 = jr(demo_project, "run", "--page", "/x", "--engine", "chatbot", "--query", "q2", "--response", "typed")
    assert json.loads(next((demo_project / "journal" / "runs").rglob("J0002-*.json")).read_text())["capture_method"] == "typed-inline"


def test_a_decision_tells_the_owner_to_approve_it(demo_project):
    r = jr(demo_project, "add", "--page", "/x", "--kind", "decision", "--title", "Use the short title")
    assert r.returncode == 0 and "growth approve decision J0001" in r.stdout
    assert "approve" not in jr(demo_project, "add", "--page", "/x", "--kind", "finding", "--title", "f").stdout


# ---- 5. c_evidence reads times with journal.parse_at -------------------------------------------------------------------

def test_an_entry_with_no_real_zone_is_not_counted(monkeypatch):
    sys.path.insert(0, str(TOOLS))
    from gatelib import c_evidence
    assert c_evidence.at({"at": "2026-11-19 06:48-05:00"}, None).utcoffset() is not None
    assert c_evidence.at({"at": "2026-11-19 06:48"}, None) is None             # the old reader assumed a zone
    assert c_evidence.at({"at": "2026-11-19 06:48 ZZZ"}, None) is None
    assert c_evidence.at({}, None) is None


# ---- 6. JSON read-modify-write goes through atomic ---------------------------------------------------------------------

def test_twenty_parallel_task_steps_all_survive(demo_project, tmp_path):
    env = {**os.environ, "GROWTH_PROJECT": str(demo_project), "PYTHONDONTWRITEBYTECODE": "1"}
    tid = subprocess.run([sys.executable, str(ROOT / "growth"), "tasks", "add", "Page job", "words"], env=env, cwd=demo_project, check=True,
                         capture_output=True, text=True).stdout.strip()
    procs = [subprocess.Popen([sys.executable, str(ROOT / "growth"), "tasks", "step", tid, f"step number {i}"], env=env, cwd=demo_project,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for i in range(20)]
    outs = [p.communicate(timeout=120) for p in procs]
    assert all(p.returncode == 0 for p in procs), outs
    db = json.loads((demo_project / "docs" / "tasks.json").read_text())
    task = next(t for t in db["tasks"] if t["id"] == tid)
    assert len(task["steps"]) == 20 and len({s["n"] for s in task["steps"]}) == 20


def test_wizard_steps_recorded_in_parallel_all_survive(tmp_path):
    sys.path.insert(0, str(TOOLS))
    import wizard_state as ws
    (tmp_path / "p").mkdir()
    ts = [threading.Thread(target=ws.record, args=(tmp_path / "p", f"step{i}", "done")) for i in range(20)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(ws.load(tmp_path / "p")["steps"]) == 20


STATE_FILES = ["tasks.py", "checkpoints.py", "research.py", "harness.py", "wizard_state.py", "preflight.py", "ready.py", "measure.py",
               "registry_sync.py", "setup_task.py"]


@pytest.mark.parametrize("name", STATE_FILES)
def test_state_files_are_never_written_by_a_plain_write_text_of_json(name):
    text = (TOOLS / name).read_text()
    assert not re.search(r"write_text\(\s*json\.dumps|json\.dump\(", text), f"{name} writes JSON without kit/tools/atomic.py"


def test_the_page_tracker_state_files_are_written_atomically():
    for f in ("ai_summary.py", "diffs.py", "sitepaths.py", "export.py"):
        text = (ROOT / "kit" / "page-tracker" / f).read_text()
        assert "json.dump(" not in text and not re.search(r'open\([^)]*"w"[^)]*\)\.write\(json\.dumps', text), f
        assert "save_json(" in text


# ---- 7. the live-site rule reaches every fetcher -----------------------------------------------------------------------

@pytest.fixture
def no_crawl(monkeypatch, demo_project):
    monkeypatch.setenv("GROWTH_PROJECT", str(demo_project))
    sys.path.insert(0, str(TOOLS))
    import config
    monkeypatch.setattr(config, "CFG", {"site_url": "https://shop.example", "live_site_rule": "no-crawl"}, raising=False)


def test_page_snapshot_and_page_archive_refuse_the_live_host(no_crawl):
    import page_archive
    import page_snapshot
    with pytest.raises(SystemExit, match="REFUSED"):
        page_snapshot.elements("/pricing/", base="https://www.shop.example")
    with pytest.raises(SystemExit, match="REFUSED"):
        page_archive.capture("/pricing/", "before", "https://shop.example")


def test_vendor_pages_are_other_hosts_so_only_the_sites_own_host_is_refused(no_crawl, monkeypatch):
    import vendor_page
    seen = []

    class Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b"<p>ok</p>"
    monkeypatch.setattr(vendor_page.urllib.request, "urlopen", lambda req, timeout=30: seen.append(req.full_url) or Resp())
    assert vendor_page.fetch("https://vendor.example/pricing") == "<p>ok</p>" and seen
    with pytest.raises(SystemExit, match="REFUSED"):
        vendor_page.fetch("https://shop.example/pricing")


# ---- 8. owner_messages: one reader, and a scheduled prompt is not an owner message ------------------------------------------

def transcript_project(tmp_path, monkeypatch, texts):
    sys.path.insert(0, str(TOOLS))
    import owner_messages
    d = tmp_path / "transcripts"
    d.mkdir()
    lines = [json.dumps({"type": "user", "timestamp": f"2026-11-19T10:0{i}:00Z", "message": {"role": "user", "content": t}})
             for i, t in enumerate(texts)]
    lines.append(json.dumps({"type": "user", "timestamp": "2026-11-19T11:00:00Z", "message": {"role": "user", "content": [
        {"type": "tool_result", "content": "a tool answered with plenty of words in it"}]}}))
    (d / "s1.jsonl").write_text("\n".join(lines) + "\n")
    monkeypatch.setattr(owner_messages, "transcript_dirs", lambda *a, **k: [d])
    monkeypatch.setattr(owner_messages, "DOCS", tmp_path / "docs")
    return owner_messages


def test_owner_messages_reads_through_the_one_transcript_reader(tmp_path, monkeypatch):
    om = transcript_project(tmp_path, monkeypatch, ["Please add the pricing table to the page today", "<task-notification>x</task-notification>"])
    assert [m["text"] for m in om.owner_messages()] == ["Please add the pricing table to the page today"]
    import transcript
    assert not hasattr(om, "SKIP") and transcript.owner_text({"type": "user", "message": {"content": "hello there friend"}})


def test_a_scheduled_runs_prompt_is_not_an_owner_message(tmp_path, monkeypatch):
    prompt = "Run the nightly page tracker sync, then write the daily report for every tracked page."
    om = transcript_project(tmp_path, monkeypatch, [prompt, "Please change the pricing page headline to the short one"])
    (tmp_path / "docs").mkdir()
    pf = tmp_path / "nightly.txt"
    pf.write_text(prompt + "\n")
    assert len(om.owner_messages()) == 2                                          # nothing recorded: both look typed
    (tmp_path / "docs" / "scheduled-prompts.txt").write_text(f"{pf}\n")
    assert [m["text"] for m in om.owner_messages()] == ["Please change the pricing page headline to the short one"]
    (tmp_path / "docs" / "scheduled-prompts.txt").unlink()
    monkeypatch.setenv("GROWTH_SCHEDULED_PROMPT_FILE", str(pf))
    assert len(om.owner_messages()) == 1
    monkeypatch.delenv("GROWTH_SCHEDULED_PROMPT_FILE")
    monkeypatch.setenv("GROWTH_SCHEDULED", "1")                                    # an unattended run: its first turn is its prompt
    assert [m["text"] for m in om.owner_messages()] == ["Please change the pricing page headline to the short one"]


# ---- 9. new-project writes a commented .private-words ------------------------------------------------------------------

def test_new_project_writes_a_commented_git_ignored_private_words_file(tmp_path):
    r = growth(tmp_path, "new-project", str(tmp_path / "p"), "--site", "https://shop.example")
    assert r.returncode == 0, r.stderr
    words = (tmp_path / "p" / ".private-words").read_text()
    assert words.startswith("#") and all(l.startswith("#") or not l.strip() for l in words.splitlines())
    assert ".private-words" in (tmp_path / "p" / ".gitignore").read_text().splitlines()
    sys.path.insert(0, str(TOOLS))
    import leak_check
    assert leak_check.private_words(tmp_path / "p" / ".private-words") == []      # only comments: no word to match
    again = growth(tmp_path, "new-project", str(tmp_path / "p"), "--site", "https://shop.example", "--force")
    assert again.returncode == 0 and (tmp_path / "p" / ".private-words").read_text() == words


def test_the_setup_task_covers_only_the_setup_files(tmp_path):
    from test_workflow import run
    p = tmp_path / "np"
    assert growth(tmp_path, "new-project", str(p), "--site", "https://shop.example").returncode == 0
    subprocess.run(["git", "init", "-q"], cwd=p)
    (p / "page.md").write_text("page work\n")
    r = run(p, "workflow", "check")
    assert r.returncode == 2 and "page.md" in r.stderr and "setup task covers only the setup files" in r.stderr


# ---- 10. model roles ---------------------------------------------------------------------------------------------------

def test_default_roles_builders_sonnet_reviewer_opus_log_work_haiku():
    from agent_models import problems
    ok = lambda name, model, **k: problems([{"name": name, "description": name, "model": model}], **k) == []
    assert ok("page builder", "sonnet") and not ok("page builder", "opus")
    assert ok("independent review", "opus") and not ok("independent review", "sonnet")
    assert ok("count log lines", "haiku") and not ok("count log lines", "opus")
    assert not ok("independent review", "opus", builders={"opus"})                # the reviewer must differ from the builders
    assert ok("independent review", "opus", builders={"sonnet"})
