"""Gate and evidence fixes: findings stay open until closed (#48), the review check cannot pass on the checkpoints file
(#49), preview_repo is required when the site has a checkout (#51), small crashes (#52), manual checkpoints (#62)."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "kit" / "tools"


def tool(project, script, *args):
    env = {**os.environ, "GROWTH_PROJECT": str(project), "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run([sys.executable, str(TOOLS / script), *args], capture_output=True, text=True, env=env, cwd=project)


def entries(project):
    return [json.loads(l) for l in (project / "journal" / "entries.jsonl").read_text().splitlines() if l.strip()]


# ---- #48

def test_a_new_finding_starts_open_and_close_needs_output(demo_project):
    r = tool(demo_project, "journal.py", "add", "--page", "/x", "--kind", "finding", "--title", "t")
    assert r.returncode == 0, r.stderr
    fid = r.stdout.split()[0]
    assert [e for e in entries(demo_project) if e["id"] == fid][0]["status"] == "open"
    assert tool(demo_project, "journal.py", "close", fid).returncode != 0            # --output is required
    assert tool(demo_project, "journal.py", "close", fid, "--output", "  ").returncode != 0
    assert "No open" not in tool(demo_project, "journal.py", "open").stdout
    assert tool(demo_project, "journal.py", "close", fid, "--output", "commit abc1234").returncode == 0
    assert entries(demo_project)[-1]["status"] == "done"
    assert "No open" in tool(demo_project, "journal.py", "open").stdout


def test_decisions_and_notes_are_still_filed_done(demo_project):
    r = tool(demo_project, "journal.py", "add", "--page", "/x", "--kind", "decision", "--title", "t")
    assert [e for e in entries(demo_project) if e["id"] == r.stdout.split()[0]][0]["status"] == "done"


def test_stale_open_finding_fails_ev_open_findings():
    import datetime as dt
    from gatelib import CHECKS
    from gatelib.core import Ctx, run_check
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp)
        (p / "journal").mkdir()
        old = (dt.datetime.now() - dt.timedelta(days=10)).strftime("%Y-%m-%d %H:%M UTC")
        (p / "journal/entries.jsonl").write_text(json.dumps({"id": "J0001", "at": old, "pages": ["/x"], "kind": "finding", "status": "open", "tags": []}) + "\n")
        c = Ctx(project=p, path="/x", cfg={})
        run_check(c, CHECKS["ev.open-findings"])
        assert c.lines[0].level == "FAIL"


# ---- #49

def review_ctx(tmp, key, names):
    from gatelib.core import Ctx
    (tmp / "research").mkdir(exist_ok=True)
    for n in names:
        (tmp / "research" / n).write_text("x\n")
    return Ctx(project=tmp, path="/" + key, key=key, cfg={})


def run_review(ctx):
    from gatelib import CHECKS
    from gatelib.core import run_check
    run_check(ctx, CHECKS["ev.review"])
    return ctx.lines[0].level


def test_a_key_containing_review_does_not_pass_on_the_checkpoints_file(tmp_path):
    ctx = review_ctx(tmp_path, "asana-review", ["asana-review-checkpoints.md"])
    assert run_review(ctx) == "FAIL"


def test_a_key_containing_review_does_not_pass_on_another_research_file(tmp_path):
    ctx = review_ctx(tmp_path, "asana-review", ["asana-review-research-check-2026-11-18.md", "asana-review-dossier.md"])
    assert run_review(ctx) == "FAIL"


def test_a_dated_audit_or_review_file_passes(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    assert run_review(review_ctx(tmp_path / "a", "asana-review", ["asana-review-audit-2026-11-18.md"])) == "OK"
    assert run_review(review_ctx(tmp_path / "b", "lawn", ["lawn-opus-review-2026-11-18.md"])) == "OK"


def test_an_undated_review_name_fails(tmp_path):
    assert run_review(review_ctx(tmp_path, "lawn", ["lawn-review.md"])) == "FAIL"


# ---- #51

def set_cfg(project, **kw):
    f = project / "growth.json"
    d = json.loads(f.read_text())
    d.update(kw)
    f.write_text(json.dumps(d))


def test_ready_and_preflight_refuse_a_site_checkout_without_preview_repo(demo_project):
    set_cfg(demo_project, site_repo="../site-main", preview_repo="", preview_url="http://127.0.0.1:9")
    for script, args in (("ready.py", ["/x", "--type", "post", "--key", "x"]), ("preflight.py", ["/x", "--type", "post", "--key", "x"])):
        r = tool(demo_project, script, *args)
        assert r.returncode != 0 and "preview_repo" in r.stderr, (script, r.stderr)


def test_the_preview_repo_problem_clears_when_it_is_set_or_there_is_no_checkout(demo_project, monkeypatch):
    monkeypatch.setenv("GROWTH_PROJECT", str(demo_project))
    sys.path.insert(0, str(TOOLS))
    import ready
    for cfg, bad in (({"site_repo": "../s", "preview_repo": ""}, True), ({"site_repo": "../s", "preview_repo": "../wt"}, False),
                     ({"site_repo": "", "preview_repo": ""}, False)):
        monkeypatch.setattr(ready, "CFG", cfg, raising=False)
        assert bool(ready.preview_repo_problem()) is bad, cfg
