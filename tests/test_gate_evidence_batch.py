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
