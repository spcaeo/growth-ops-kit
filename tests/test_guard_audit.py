"""Audit 19 Nov (C2, H5, H6, M3, M7, M8): the workflow guard really holds."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
GROWTH = str(ROOT / "growth")


def run(project, *args, stdin="", cwd=None, env=None):
    e = {**os.environ, "GROWTH_PROJECT": str(project), "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.com",
         "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@example.com", **(env or {})}
    if project is None:
        e.pop("GROWTH_PROJECT")
    return subprocess.run([sys.executable, GROWTH, *args], capture_output=True, text=True, env=e, input=stdin, cwd=cwd)


def git(p, *a, date=None):
    env = {**os.environ, "GIT_COMMITTER_DATE": date, "GIT_AUTHOR_DATE": date} if date else None
    subprocess.run(["git", "-c", "user.email=t@example.com", "-c", "user.name=T", *a], cwd=p, check=True, capture_output=True, env=env)


def proj(tmp_path, name="proj", tasks=None, cfg=None):
    p = tmp_path / name
    (p / "docs").mkdir(parents=True)
    (p / "growth.json").write_text(json.dumps({"name": "T", "site_url": "https://t.example", **(cfg or {})}))
    (p / "docs" / "tasks.json").write_text(json.dumps({"tasks": tasks or [], "questions": []}))
    subprocess.run(["git", "init", "-q"], cwd=p)
    git(p, "add", "-A")
    git(p, "commit", "-qm", "init", date="2026-01-01T00:00:00")
    return p


# C2: the setup task does not cover page work; a chat task covers no file changes; commits count
def test_setup_task_open_does_not_cover_page_files(tmp_path):
    p = proj(tmp_path)
    run(p, "tasks", "add", "Project setup", "set up")
    run(p, "tasks", "step", "T1", "Doctor step")
    (p / "page.html").write_text("x\n")
    r = run(p, "workflow", "check")
    assert r.returncode == 2 and "page task" in r.stderr
    (p / "page.html").unlink()
    (p / "SETUP.md").write_text("setup\n")              # a setup file is covered by the setup task
    assert run(p, "workflow", "check").returncode == 0


def test_chat_task_covers_no_file_changes(tmp_path):
    p = proj(tmp_path)
    run(p, "tasks", "add", "Chat: hi", "", "--type", "chat")
    assert run(p, "workflow", "check").returncode == 0
    (p / "page.html").write_text("x\n")
    r = run(p, "workflow", "check")
    assert r.returncode == 2 and "chat task covers no file changes" in r.stderr


def test_committed_work_counts(tmp_path):
    p = proj(tmp_path)
    (p / "page.html").write_text("x\n")
    git(p, "add", "page.html")
    git(p, "commit", "-qm", "work", date="2030-06-01T00:00:00")
    r = run(p, "workflow", "check")                      # clean tree, no task, work already committed
    assert r.returncode == 2 and "committed" in r.stderr
    run(p, "tasks", "add", "Chat: hi", "", "--type", "chat")
    assert run(p, "workflow", "check").returncode == 2    # a chat task does not hide it
    run(p, "tasks", "add", "Page job", "words")
    run(p, "tasks", "step", "T2", "Edit")
    assert run(p, "workflow", "check").returncode == 0    # a page task covers it


def test_commit_before_the_last_proof_is_covered(tmp_path):
    p = proj(tmp_path)
    run(p, "tasks", "add", "Page job", "words")
    run(p, "tasks", "step", "T1", "Edit", "--status", "done", "--output", "commit abc")
    (p / "page.html").write_text("x\n")
    git(p, "add", "page.html")
    git(p, "commit", "-qm", "work", date="2026-01-02T00:00:00")   # older than the proof: covered by that task
    run(p, "tasks", "status", "T1", "done")
    assert run(p, "workflow", "check").returncode == 0


# H6: Claude started above the project
def test_hook_finds_the_project_below_the_start_folder(tmp_path):
    p = proj(tmp_path, "ws/site-project")
    (p / "page.md").write_text("work\n")
    for active in (False, True):
        r = run(None, "hook", "stop", stdin=json.dumps({"stop_hook_active": active, "cwd": str(tmp_path / "ws")}))
        assert r.returncode == 2 and "no task is open" in r.stderr


def test_no_project_refuses_loudly(tmp_path):
    (tmp_path / "empty").mkdir()
    r = run(tmp_path / "empty", "workflow", "check", cwd=tmp_path / "empty")
    assert r.returncode == 2 and "not inside a growth project" in r.stderr
    r = run(None, "hook", "stop", stdin=json.dumps({"cwd": str(tmp_path / "empty")}))
    assert r.returncode == 2 and "Rule guards are not running" in r.stderr
    gone = run(tmp_path / "missing", "workflow", "check")
    assert gone.returncode == 2 and "is not a folder" in gone.stderr


def test_two_projects_below_use_the_one_with_changes(tmp_path):
    a, b = proj(tmp_path, "ws/a"), proj(tmp_path, "ws/b")
    (b / "page.md").write_text("w\n")
    r = run(None, "workflow", "resolve", str(tmp_path / "ws"))
    assert r.returncode == 0 and r.stdout.strip() == str(b.resolve())
    (a / "page.md").write_text("w\n")
    assert run(None, "workflow", "resolve", str(tmp_path / "ws")).returncode == 2


# H5 / M8: the url guard
def guard(tmp_path, monkeypatch, cfg=None):
    p = proj(tmp_path, cfg={"preview_url": "http://127.0.0.1:3801", **(cfg or {})})
    monkeypatch.setenv("GROWTH_PROJECT", str(p))
    sys.modules.pop("url_guard", None)
    sys.modules.pop("config", None)
    import url_guard
    monkeypatch.setattr(url_guard, "is_ready", lambda path: False)
    return url_guard


@pytest.mark.parametrize("url", ["http://127.0.0.1:3801/pricing", "http://0.0.0.0:3801/pricing", "127.0.0.1:3801/pricing",
                                 "http://192.168.1.5:3801/pricing", "http://LOCALHOST:3801/pricing", "http://10.1.2.3:3750/x",
                                 "http://[::1]:3801/p", "http://mybox.local:3801/p"])
def test_url_guard_catches_local_forms(tmp_path, monkeypatch, url):
    assert guard(tmp_path, monkeypatch).offenders(f"See {url} for the page.")


def test_url_guard_leaves_other_things_alone(tmp_path, monkeypatch):
    g = guard(tmp_path, monkeypatch)
    assert not g.offenders("Docs at https://example.com/a and http://127.0.0.1:9999/x and version 1.2.3")


def test_url_guard_ports_list_range_and_dict(tmp_path, monkeypatch):
    g = guard(tmp_path, monkeypatch)
    assert g.port_ok(3300, [3100, 3200, 3300]) and not g.port_ok(3400, [3100, 3200, 3300])
    assert g.port_ok(3750, {"from": 3700, "to": 3799}) and g.port_ok(3750, "3700-3799") and g.port_ok(3750, [3700, 3799])


def test_url_guard_host_of_preview_url_any_port(tmp_path, monkeypatch):
    g = guard(tmp_path, monkeypatch, {"preview_url": "https://prev.example.test"})
    assert g.offenders("https://prev.example.test/pricing") and g.offenders("prev.example.test/pricing")


def transcript(tmp_path, entries):
    t = tmp_path / "t.jsonl"
    t.write_text("\n".join(json.dumps(e) for e in entries))
    return str(t)


def asst(text, model="claude-sonnet-5-5"):
    return {"type": "assistant", "message": {"model": model, "content": [{"type": "text", "text": text}]}}


def test_owner_message_with_blocks_resets_the_window(tmp_path, monkeypatch):
    g = guard(tmp_path, monkeypatch)
    t = transcript(tmp_path, [
        {"type": "user", "message": {"content": "send me the unapproved link"}}, asst("http://127.0.0.1:3801/a"),
        {"type": "user", "message": {"content": [{"type": "text", "text": "thanks"}, {"type": "image", "source": {}}]}},
        asst("nothing here")])
    text, asked, _ = g.last_exchange(t)
    assert "127.0.0.1" not in text and asked.startswith("thanks")


def test_owner_asked_escape_is_narrow(tmp_path, monkeypatch):
    g = guard(tmp_path, monkeypatch)
    assert not g.OWNER_ASKED.search("how are my backlinks and links doing?")
    assert g.OWNER_ASKED.search("send me the unapproved link")


def test_stop_hook_url_guard_never_softens(tmp_path):
    p = proj(tmp_path, cfg={"preview_url": "http://127.0.0.1:3801"})
    t = transcript(tmp_path, [{"type": "user", "message": {"content": "show me"}}, asst("Try http://0.0.0.0:3801/pricing")])
    for active in (False, True):
        r = run(p, "hook", "stop", stdin=json.dumps({"stop_hook_active": active, "transcript_path": t}))
        assert r.returncode == 2 and "GOLDEN RULE" in r.stderr


# M3: agent_models
def call(name, desc, model=None, sub=None):
    inp = {"name": name, "description": desc, **({"model": model} if model else {}), **({"subagent_type": sub} if sub else {})}
    return {"type": "assistant", "message": {"model": "claude-sonnet-5-5", "content": [{"type": "tool_use", "name": "Agent", "input": inp}]}}


def test_unmatched_role_fails_and_lead_comes_from_the_transcript(tmp_path):
    import agent_models as am
    assert am.problems([{"name": "page helper", "description": "does stuff", "model": "sonnet"}])      # no role: name it
    t = transcript(tmp_path, [{"type": "user", "message": {"content": "go"}}, asst("ok", "claude-sonnet-5-5"),
                              call("pp-builder", "Pricing page builder")])
    tp = str(t)
    calls = am.agent_calls(tp)
    assert am.problems(calls) == []                      # inherits the lead's real model: sonnet, a builder's model
    t2 = transcript(tmp_path, [{"type": "user", "message": {"content": "go"}}, asst("ok", "claude-opus-5-5"),
                               {"type": "assistant", "message": {"model": "claude-opus-5-5", "content": [
                                   {"type": "tool_use", "name": "Agent", "input": {"name": "b", "description": "builder"}}]}}])
    assert am.problems(am.agent_calls(t2))


def test_reviewer_exception_needs_a_real_opus_builder(tmp_path, capsys, monkeypatch):
    import agent_models as am
    rv = call("r", "Review of Opus-built pricing folds", "sonnet")
    bld = call("b", "Pricing builder", "sonnet")
    t = transcript(tmp_path, [{"type": "user", "message": {"content": "go"}}, bld, rv])
    monkeypatch.setattr(sys, "argv", ["agent_models", "--transcript", t])
    assert am.main() == 1                                # the builder really ran on sonnet: a sonnet reviewer is wrong
    bld2 = call("b", "Pricing builder", "opus")
    t = transcript(tmp_path, [{"type": "user", "message": {"content": "go"}}, bld2, rv])
    monkeypatch.setattr(sys, "argv", ["agent_models", "--transcript", t])
    assert am.main() == 1 and "builder" in capsys.readouterr().out   # the opus builder itself is wrong, the reviewer is fine


def test_agent_models_reads_block_owner_messages(tmp_path):
    import agent_models as am
    t = transcript(tmp_path, [
        {"type": "user", "message": {"content": "go"}}, call("x", "Count log lines", "opus"),
        {"type": "user", "message": {"content": [{"type": "text", "text": "ok"}, {"type": "image", "source": {}}]}}])
    assert am.agent_calls(t) == []                       # the list-form owner message started a new window


# M7: the Stop hook never shows an empty block
def test_stop_hook_no_transcripts_has_its_own_message(tmp_path):
    p = proj(tmp_path)
    r = run(p, "hook", "stop", stdin=json.dumps({"cwd": str(p)}), env={"HOME": str(tmp_path / "nohome")})
    assert r.returncode == 2 and r.stderr.strip() and "Owner messages" in r.stderr
    assert r.stderr.split("Owner messages")[1].strip(": \n") != ""


# L2 / L3 / L4: install_hooks
def test_install_hooks_strict_arguments_and_quoting(tmp_path):
    hook = ROOT / "kit" / "hooks" / "install_hooks.py"
    run_h = lambda *a: subprocess.run([sys.executable, str(hook), *a], capture_output=True, text=True)
    assert run_h().returncode == 2                           # no arguments: help, not a crash
    r = run_h("remove", "foo")
    assert r.returncode == 2 and "unknown target" in r.stderr
    import hooks_text
    body = hooks_text.project_hook(Path('/tmp/we"ird $(x) `y`'))
    assert "'/tmp/we\"ird $(x) `y`'" in body and 'GROWTH_PROJECT="/tmp' not in body
    assert '"$PY" -m pytest' in hooks_text.KIT_HOOK


# Kit friction 42: a withdrawn link stops blocking; a new mention still blocks; a stop with no correction still blocks
def test_withdrawn_link_stops_blocking_but_new_mentions_block(tmp_path):
    p = proj(tmp_path, cfg={"preview_url": "http://127.0.0.1:3801"})
    rows = [{"type": "user", "message": {"content": "show me"}}, asst("Try http://127.0.0.1:3801/pricing")]
    t = transcript(tmp_path, rows)
    stop = lambda: run(p, "hook", "stop", stdin=json.dumps({"stop_hook_active": True, "transcript_path": t}))
    assert stop().returncode == 2                                          # blocked
    assert stop().returncode == 2                                          # no correction yet: still blocked
    rows.append(asst("Correction: http://127.0.0.1:3801/pricing is withdrawn, it is not ready."))
    t = transcript(tmp_path, rows)
    assert stop().returncode == 0                                          # the correction names the link: passes
    rows.append(asst("Here it is again: http://127.0.0.1:3801/pricing"))
    t = transcript(tmp_path, rows)
    assert stop().returncode == 2                                          # a new mention blocks again


def test_released_page_stays_ready_after_its_worktree_is_removed(tmp_path, monkeypatch):
    site = tmp_path / "site"
    site.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=site)
    (site / "a.md").write_text("a\n")
    git(site, "add", "-A")
    git(site, "commit", "-qm", "page")
    commit = subprocess.run(["git", "-C", str(site), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    p = proj(tmp_path, cfg={"site_repo": str(site), "preview_repo": str(tmp_path / "gone-worktree")})
    (p / "journal").mkdir()
    (p / "journal" / "ready.json").write_text(json.dumps({"/pricing": {"commit": commit}}))
    monkeypatch.setenv("GROWTH_PROJECT", str(p))
    for m in ("ready", "config"):
        sys.modules.pop(m, None)
    import ready
    assert ready.is_ready("/pricing")                                      # merged into the site: what went live
    (p / "journal" / "ready.json").write_text(json.dumps({"/pricing": {"commit": "0" * 40}}))
    assert not ready.is_ready("/pricing")                                  # a commit the site never got: not ready


def test_withdrawal_accepts_contractions():
    # 24 Nov 2026: "the localhost address isn't ready to open yet" did not count as a withdrawal
    from url_guard import WITHDRAW
    for line in ["That address isn't ready yet.", "These links aren't ready.", "It is not ready.", "Withdrawn."]:
        assert WITHDRAW.search(line), line
    assert not WITHDRAW.search("The page is ready.")
