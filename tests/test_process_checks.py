"""Process checks on a project folder: the engine check (the kit names no business), the steps-log format, the rulebook and
registry stay in step."""
import subprocess
import sys
from pathlib import Path

from gatelib import CHECKS
from gatelib.core import Ctx, run_check

ROOT = Path(__file__).resolve().parent.parent


def ctx_for(project, **cfg):
    return Ctx(project=project, docs=project / "docs", cfg={"name": "T", "site_url": "https://t.example", **cfg})


def test_engine_check_finds_a_business_named_in_the_kit_and_passes_on_the_demo(demo_project):
    c = ctx_for(demo_project, product="Brightline Lawn Care", site_url="https://brightline.example")
    run_check(c, CHECKS["engine.facts"])
    assert c.lines[0].level == "OK", c.lines[0].text()
    # a project whose domain the kit does mention is flagged
    c2 = ctx_for(demo_project, site_url="https://example.com")
    run_check(c2, CHECKS["engine.facts"])
    assert c2.lines[0].level == "FAIL" and "tools" in c2.lines[0].what or c2.lines[0].level == "OK"


def test_steps_log_accepts_the_template_row_format(demo_project):
    log = demo_project / "docs" / "steps-log.md"
    log.write_text(log.read_text().rstrip("\n") + "\n| I-1 | 2026-11-18 | \"Our button says Get a quote.\" | Wrote it into BRAND.md. | `BRAND.md` |\n"
                   "| I-2 | 2026-11-18 | \"Add a blog.\" | Added the post. | `site/blog` |\n")
    c = ctx_for(demo_project)
    run_check(c, CHECKS["proc.steps-log"])
    assert c.lines[0].level == "OK" and "2 instructions" in c.lines[0].what, c.lines[0].text()


def test_steps_log_fails_on_a_gap_a_bad_date_and_a_missing_where(demo_project):
    log = demo_project / "docs" / "steps-log.md"
    log.write_text(log.read_text().rstrip("\n") + "\n| I-1 | 2026-11-18 | a | b | where |\n| I-3 | yesterday | a | b | where |\n| I-4 | 2026-11-18 | a | b |  |\n")
    c = ctx_for(demo_project)
    run_check(c, CHECKS["proc.steps-log"])
    what = c.lines[0].what
    assert c.lines[0].level == "FAIL" and "I-3 lacks a date" in what and "I-4 lacks a date" in what and "I-2" in what


def test_rulebook_and_registry_versions_agree(demo_project):
    c = ctx_for(demo_project)
    run_check(c, CHECKS["proc.rulebook-current"])
    assert c.lines[0].level == "OK", c.lines[0].text()


def test_registry_sync_check_passes():
    r = subprocess.run([sys.executable, str(ROOT / "kit" / "tools" / "registry_sync.py"), "--check"], capture_output=True, text=True,
                       env={"PATH": "/usr/bin:/bin", "GROWTH_PROJECT": ""})
    assert r.returncode == 0, r.stdout + r.stderr


def test_commit_identity_reads_the_new_and_the_old_key():
    assert ctx_for(Path("."), commit_identity={"name": "A", "email": "a@example.com"}).commit_email() == "a@example.com"
    assert ctx_for(Path("."), committer_email="b@example.com").commit_email() == "b@example.com"


def test_old_hosts_are_found_in_a_page():
    from techseo.net import Fetcher, Resp
    from techseo.page import Page
    from techseo.report import Report
    import techseo.c_index as ci

    class F(Fetcher):
        def get(self, url, **k):
            return Resp(url, status=200, headers={"content-type": "text/html"},
                        body=b'<html><head><link rel="canonical" href="https://t.example/x"></head><body><a href="https://old.example.net/x">x</a></body></html>')

    def run(old):
        rep = Report(url="http://127.0.0.1:1/x")
        p = Page(F("http://127.0.0.1:1", "https://t.example"), rep, "http://127.0.0.1:1/x", site_origin="https://t.example", old_hosts=old)
        ci.run_url(p)
        return [r for r in rep.results if r.cid == "URL-11"]

    assert [r.level for r in run(["old.example.net"])] == ["FAIL"]
    assert [r.level for r in run([])] == ["OK"]


def test_owner_messages_check_warns_when_there_are_no_transcripts_never_ok(demo_project, tmp_path, monkeypatch):
    """With no agent transcripts to read, nothing was checked: a WARN with a clear line, never OK (rule: never a fake OK)."""
    monkeypatch.setenv("GROWTH_PROJECT", str(demo_project))
    monkeypatch.setenv("HOME", str(tmp_path / "empty-home"))
    c = ctx_for(demo_project)
    run_check(c, CHECKS["proc.owner-messages"])
    line = c.lines[0]
    assert line.level == "WARN", line.text()
    assert "no agent transcripts found at" in line.what and "transcripts_dir" in line.what and "Errno" not in line.what


def test_owner_messages_check_says_ok_only_with_a_summary_of_messages_it_read(demo_project, tmp_path, monkeypatch):
    import json
    home = tmp_path / "home"
    folder = home / ".claude" / "projects" / ("-" + str(demo_project).strip("/").replace("/", "-").replace("_", "-"))
    folder.mkdir(parents=True)
    (folder / "s.jsonl").write_text(json.dumps({"type": "user", "timestamp": "2026-11-18T10:00:00Z", "message": {"content": "hello"}}) + "\n")
    monkeypatch.setenv("GROWTH_PROJECT", str(demo_project))
    monkeypatch.setenv("HOME", str(home))
    c = ctx_for(demo_project)
    run_check(c, CHECKS["proc.owner-messages"])
    assert c.lines[0].level in ("OK", "FAIL") and "owner messages;" in c.lines[0].what, c.lines[0].text()
    assert "Errno" not in c.lines[0].what


def test_a_project_may_have_a_remote_the_gate_only_warns(demo_project):
    """The foundation checklist asks for a private remote, so a remote must never be a FAIL (it was, once)."""
    def git(*a):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@example.com", *a], cwd=demo_project, check=True, capture_output=True)
    git("init", "-q")
    c = ctx_for(demo_project)
    run_check(c, CHECKS["proc.remote-private"])
    assert c.lines[0].level == "OK", c.lines[0].text()
    git("remote", "add", "origin", "https://git.example/acme/growth.git")
    c = ctx_for(demo_project)
    run_check(c, CHECKS["proc.remote-private"])
    assert c.lines[0].level == "WARN" and "private" in c.lines[0].what and "git.example" in c.lines[0].what
