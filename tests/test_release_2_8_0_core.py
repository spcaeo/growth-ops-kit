"""2.8.0 (throughput): READY holds while the page's built output is unchanged; ready runs pages side by side; a proof
outside the project is refused; the golden-rule and check-in-2 steps may wait until READY."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent.parent / "kit" / "tools"
sys.path.insert(0, str(TOOLS))


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def site(tmp_path, demo_project, monkeypatch):
    """A git site with a built dist/ holding two pages that share one CSS file."""
    repo = tmp_path / "site"
    (repo / "dist" / "a").mkdir(parents=True)
    (repo / "dist" / "b").mkdir(parents=True)
    (repo / "dist" / "s.css").write_text("body{color:#111}")
    (repo / "dist" / "a" / "index.html").write_text('<link rel="stylesheet" href="/s.css"><h1>A</h1>')
    (repo / "dist" / "b" / "index.html").write_text('<link rel="stylesheet" href="/s.css"><h1>B</h1>')
    (repo / "src.txt").write_text("one")
    git(repo.parent, "init", "-q", str(repo))
    git(repo, "-c", "user.email=t@example.com", "-c", "user.name=t", "add", "src.txt")
    git(repo, "-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-qm", "one")
    monkeypatch.setenv("GROWTH_PROJECT", str(demo_project))
    import ready
    monkeypatch.setattr(ready, "PROJECT", demo_project)
    monkeypatch.setattr(ready, "LEDGER", demo_project / "journal" / "ready.json")
    monkeypatch.setattr(ready, "CFG", {"preview_url": "http://127.0.0.1:9", "build_dir": "dist", "site_repo": str(repo),
                                       "preview_repo": str(repo)})
    monkeypatch.setattr(ready, "preview_repo", lambda: repo)
    (demo_project / "journal").mkdir(exist_ok=True)
    return repo


def commit(repo, text):
    (repo / "src.txt").write_text(text)
    git(repo, "-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-qam", text)


def touch_build(repo):
    """A fresh build: every built file newer than the last commit (a build rewrites them all)."""
    later = time.time() + 5
    for f in (repo / "dist").rglob("*"):
        if f.is_file():
            os.utime(f, (later, later))


def record(ready, path):
    ready.atomic.update_json(ready.LEDGER, lambda x: x.update({path: {"commit": ready.head(ready.preview_repo()),
                                                                      "fp": ready.page_fp(path), "type": "post", "key": path.strip("/")}}),
                             default={}, indent=1)


def test_ready_holds_while_the_page_output_is_unchanged(site):
    import ready
    touch_build(site)
    record(ready, "/a")
    assert ready.status("/a") == "same commit"
    commit(site, "two")                       # another page's fix: this page's built output does not change
    touch_build(site)
    assert ready.status("/a") == "same output" and ready.is_ready("/a")


def test_a_changed_page_or_shared_css_is_not_ready(site):
    import ready
    touch_build(site)
    record(ready, "/a")
    record(ready, "/b")
    commit(site, "two")
    (site / "dist" / "a" / "index.html").write_text('<link rel="stylesheet" href="/s.css"><h1>A changed</h1>')
    touch_build(site)
    assert not ready.is_ready("/a") and ready.is_ready("/b")
    (site / "dist" / "s.css").write_text("body{color:#222}")   # a shared CSS change can change every page's look
    touch_build(site)
    assert not ready.is_ready("/b")


def test_a_build_older_than_the_last_commit_never_vouches(site):
    import ready
    touch_build(site)
    record(ready, "/a")
    old = time.time() - 3600
    for f in (site / "dist").rglob("*"):
        if f.is_file():
            os.utime(f, (old, old))
    commit(site, "two")
    assert ready.page_fp("/a") is None and not ready.is_ready("/a")


def test_list_says_why_a_page_is_ready(site, capsys, monkeypatch):
    import ready
    touch_build(site)
    record(ready, "/a")
    commit(site, "two")
    touch_build(site)
    monkeypatch.setattr(sys, "argv", ["ready", "--list"])
    ready.main()
    out = capsys.readouterr().out
    assert "READY  /a" in out and "same output" in out


def test_batch_lines_and_bad_lines(tmp_path, site):
    import ready
    f = tmp_path / "pages.txt"
    f.write_text("# hubs\n/a hub a-hub\n\n/b money b-key  # hire page\n")
    assert ready.batch_lines(str(f)) == [("/a", "hub", "a-hub"), ("/b", "money", "b-key")]
    f.write_text("/a hubb a\n")
    with pytest.raises(SystemExit):
        ready.batch_lines(str(f))


def test_batch_runs_side_by_side_and_keeps_ready_pages(tmp_path, site, monkeypatch, capsys):
    import ready
    touch_build(site)
    record(ready, "/a")
    calls = []

    def fake_run(cmd, capture_output, text, cwd):
        calls.append(cmd[2])
        time.sleep(0.3)
        out = f"READY {cmd[2]}: 0 FAIL" if cmd[2] == "/b" else f"NOT READY {cmd[2]}: 1 FAIL\n  FAIL 1 [x] broken"
        return subprocess.CompletedProcess(cmd, 0 if cmd[2] == "/b" else 1, out, "")
    real_run = subprocess.run
    monkeypatch.setattr(ready.subprocess, "run", lambda cmd, **k: fake_run(cmd, **k) if cmd[0] == sys.executable
                        else real_run(cmd, **k))
    f = tmp_path / "pages.txt"
    f.write_text("/a hub a\n/b hub b\n/c hub c\n/d hub d\n")
    t0 = time.time()
    code = ready.run_batch(str(f), jobs=3, stale_only=True)
    out = capsys.readouterr().out
    assert sorted(calls) == ["/b", "/c", "/d"]            # /a was READY and kept
    assert time.time() - t0 < 0.8                            # three pages side by side, not one after another
    assert "READY (kept, same commit)  /a" in out and "Batch: 2 of 4 READY" in out and code == 1
    assert list((ready.PROJECT / "journal" / "runs").glob("ready-batch-*.log"))


def test_a_proof_outside_the_project_is_refused(demo_project, tmp_path):
    import checkpoints
    scratch = tmp_path / "scratchpad" / "notes.md"
    scratch.parent.mkdir()
    scratch.write_text("layout looks fine")
    inside = demo_project / "research" / "notes.md"
    inside.parent.mkdir(exist_ok=True)
    inside.write_text("layout looks fine")
    why = checkpoints.proof_problem(f"file {scratch} shows the layout", demo_project, [])
    assert why and "outside the project" in why
    assert checkpoints.proof_problem("file research/notes.md shows the layout", demo_project, []) is None
    assert checkpoints.proof_problem(f"file {inside} shows the layout", demo_project, []) is None
    kit_file = Path(checkpoints.__file__).resolve()
    assert checkpoints.proof_problem(f"file {kit_file} read", demo_project, []) is None


def test_golden_rule_and_check_in_2_may_wait_until_ready():
    src = (TOOLS / "gatelib" / "c_evidence.py").read_text()
    import re
    m = re.search(r'after = re\.compile\(r"([^"]+)"\)', src)
    after = re.compile(m.group(1))
    for label in ("5. GOLDEN RULE before check-in 2", "5b. Owner check-in 2, the prototype", "7. Release alone",
                  "9. Measure (Part 3)"):
        assert after.search(label)
    for label in ("4a. Independent review, then fixes", "6. Finish (runs before 5", "3a. Fold plan before any build"):
        assert not after.search(label)


def test_a_process_rule_does_not_make_page_briefs_stale(tmp_path):
    from gatelib import CHECKS
    from gatelib.core import Ctx, run_check
    head = "| ID | Date | What the owner said | What was done | Where |\n"

    def line(rows):
        (tmp_path / "docs").mkdir(exist_ok=True)
        (tmp_path / "docs" / "steps-log.md").write_text(head + "".join(rows))
        (tmp_path / "research" / "briefs").mkdir(parents=True, exist_ok=True)
        (tmp_path / "research" / "briefs" / "pg.md").write_text("| I-1 | ... |\n")
        c = Ctx(project=tmp_path, path="/pg/", key="pg", ptype="core", cfg={}, html="", url="", status=200, docs=tmp_path / "docs")
        run_check(c, CHECKS["ev.brief"])
        return c.lines[-1]
    one = '| I-1 | 2026-11-22 | "use X" | Set rule X. | BRAND |\n'
    assert line([one, '| I-2 | 2026-11-23 | "fix the kit first" | Rule: page work pauses (no page rule). | lead |\n']).level == "OK"
    assert line([one, '| I-2 | 2026-11-23 | "use Y" | Set rule Y. | BRAND |\n']).level == "FAIL"
