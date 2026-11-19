"""Owner-only approvals (audit V1): `growth approve` runs only in a real terminal with a typed code, and its log
(docs/approvals.jsonl) is tamper-evident: a hand-written or edited line breaks the chain or the signature, and content
changed after approval no longer matches its hash. Temp HOME only; no network."""
import json
import os
import stat
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import approvals  # noqa: E402
from wizard_helpers import growth, owner_approve  # noqa: E402


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    h.mkdir(exist_ok=True)
    monkeypatch.setenv("HOME", str(h))
    return h


def project(tmp_path):
    p = tmp_path / "proj"
    (p / "docs").mkdir(parents=True)
    (p / "growth.json").write_text(json.dumps({"name": "T", "site_url": "https://t.example"}))
    (p / "docs" / "tasks.json").write_text(json.dumps({"tasks": [], "questions": [
        {"id": "Q1", "question": "May the page name the partner?", "task": None, "asked": "2026-11-18", "answer": None}]}))
    return p


def test_a_recorded_approval_matches_only_its_own_content(tmp_path, home):
    docs = project(tmp_path) / "docs"
    approvals.record(docs, "exception", "post.cover", {"check": "post.cover", "why": "decorative covers here"})
    assert approvals.status(docs, "exception", "post.cover", {"check": "post.cover", "why": "decorative covers here"})[0] == "ok"
    assert approvals.status(docs, "exception", "post.cover", {"check": "post.cover", "why": "anything at all now"})[0] == "changed"
    assert approvals.status(docs, "exception", "post.toc", {})[0] == "missing"


def test_a_hand_written_or_edited_line_is_seen(tmp_path, home):
    docs = project(tmp_path) / "docs"
    approvals.record(docs, "decision", "J0001", {"id": "J0001"})
    log = docs / "approvals.jsonl"
    forged = {"id": "A0002", "kind": "decision", "ref": "J0002", "sha256": approvals.digest({"id": "J0002"}), "prev": "x"}
    log.write_text(log.read_text() + json.dumps(forged) + "\n")
    state, why = approvals.status(docs, "decision", "J0002", {"id": "J0002"})
    assert state == "tampered" and "edited" in why
    # an edited hash on the one real line breaks nothing in the chain, so only a signature catches it: with the key it does
    log.unlink()
    approvals.ensure_key()
    approvals.record(docs, "decision", "J0001", {"id": "J0001"})
    e = json.loads(log.read_text())
    e["sha256"] = approvals.digest({"id": "J0001", "title": "changed"})
    log.write_text(json.dumps(e) + "\n")
    state, why = approvals.status(docs, "decision", "J0001", {"id": "J0001", "title": "changed"})
    assert state == "tampered" and "signature" in why


def test_an_unsigned_line_fails_once_a_key_exists_and_a_lost_key_is_seen(tmp_path, home):
    docs = project(tmp_path) / "docs"
    approvals.record(docs, "review", "x-review-2026-11-18.md", b"text")      # no key yet: unsigned
    approvals.ensure_key()
    assert approvals.verify(docs)[1] and "not signed" in approvals.verify(docs)[1][0]
    (docs / "approvals.jsonl").unlink()
    approvals.record(docs, "review", "x-review-2026-11-18.md", b"text")
    assert approvals.verify(docs)[1] == []
    approvals.key_path().unlink()
    assert "key is gone" in approvals.verify(docs)[1][0]


def test_approve_refuses_without_a_terminal(tmp_path):
    p = project(tmp_path)
    r = growth(tmp_path, "approve", "answer", "Q1", "yes, name them", cwd=p)
    assert r.returncode != 0 and "own terminal" in (r.stdout + r.stderr)
    assert json.loads((p / "docs" / "tasks.json").read_text())["questions"][0]["answer"] is None
    assert not (p / "docs" / "approvals.jsonl").exists()


def test_the_owner_approves_in_a_terminal_by_typing_the_code(tmp_path):
    p = project(tmp_path)
    rc, out = owner_approve(tmp_path, "answer", "Q1", "yes, name them", cwd=p, typed="approve 0000x")
    assert rc != 0 and "did not match" in out
    assert json.loads((p / "docs" / "tasks.json").read_text())["questions"][0]["answer"] is None
    rc, out = owner_approve(tmp_path, "answer", "Q1", "yes, name them", cwd=p)
    assert rc == 0, out
    q = json.loads((p / "docs" / "tasks.json").read_text())["questions"][0]
    assert q["answer"] == "yes, name them" and q["approval"] == "A0001"
    key = tmp_path / "home" / ".config" / "growth-ops-kit" / "approvals.key"
    assert key.is_file() and stat.S_IMODE(os.stat(key).st_mode) == 0o600          # made on the first approval, owner-only
    e = json.loads((p / "docs" / "approvals.jsonl").read_text())
    assert e["kind"] == "answer" and e["sig"] and e["via"].startswith("terminal")
    assert growth(tmp_path, "approve", "verify", cwd=p).returncode == 0


def test_tasks_answer_goes_through_the_same_owner_door(tmp_path):
    p = project(tmp_path)
    r = growth(tmp_path, "tasks", "answer", "Q1", "yes", cwd=p)
    assert r.returncode != 0 and "own terminal" in (r.stdout + r.stderr)
    assert json.loads((p / "docs" / "tasks.json").read_text())["questions"][0]["answer"] is None


def test_pending_approves_everything_waiting_with_one_code(tmp_path):
    """growth approve pending: every unapproved exception on one screen, one typed code, one log line each."""
    p = project(tmp_path)
    cfg = json.loads((p / "growth.json").read_text())
    import datetime as _dt
    until = (_dt.date.today() + _dt.timedelta(days=20)).isoformat()
    cfg["design_exceptions"] = [{"check": "faq.box", "why": "built in the browser by the site's script", "until": until},
                                {"check": "ui.phone", "why": "inline links in a sentence are exempt", "until": until},
                                {"check": "ev.review", "why": "this can never be excused at all", "until": until}]
    (p / "growth.json").write_text(json.dumps(cfg))
    rc, out = owner_approve(tmp_path, "pending", cwd=p, typed="approve 0000x")
    assert rc != 0 and "did not match" in out and not (p / "docs" / "approvals.jsonl").exists()
    rc, out = owner_approve(tmp_path, "pending", cwd=p)
    assert "2 item(s)" in out and "cannot approve: exception ev.review" in out
    lines = [json.loads(l) for l in (p / "docs" / "approvals.jsonl").read_text().splitlines()]
    assert [(e["kind"], e["ref"]) for e in lines] == [("exception", "faq.box"), ("exception", "ui.phone")]
    assert all("batch" in e["via"] for e in lines)
    rc, out = owner_approve(tmp_path, "pending", cwd=p)
    assert "nothing waits for your approval" in out                       # already approved: nothing left
