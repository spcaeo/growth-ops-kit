"""Doctor A5: the 'Control check' row counts only when its status cell says done AND it names a commit id; with a site
repo the ids must exist there."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCTOR = ROOT / "kit" / "tools" / "doctor.py"
ROW = "| Control check: edit the live site and roll back | {mid} | {status} |\n"


def a5_line(project, row):
    f = project / "SETUP.md"
    keep = [l for l in f.read_text().splitlines(True) if "Control check" not in l] if f.exists() else []
    f.write_text("".join(keep) + row)
    env = {**os.environ, "GROWTH_PROJECT": str(project), "GROWTH_CRONTAB": "", "GROWTH_LAUNCHD_DIRS": str(project / "none")}
    r = subprocess.run([sys.executable, str(DOCTOR)], capture_output=True, text=True, cwd=project, env=env)
    return next(l for l in r.stdout.splitlines() if "A5 Control" in l)


def test_done_with_proof_after_the_word_passes(demo_project):
    mid = "release a1b2c3d (one visible character), rollback to 9f8e7d6, revert 1234abc, tag live-2026-01-02-0304"
    assert a5_line(demo_project, ROW.format(mid=mid, status="proof above; done")).startswith("OK")
    assert a5_line(demo_project, ROW.format(mid=mid, status="done, proof: the owner saw it")).startswith("OK")


def test_done_without_a_commit_id_or_not_done_is_todo(demo_project):
    assert a5_line(demo_project, ROW.format(mid="the two commits", status="done")).startswith("TODO")
    assert a5_line(demo_project, ROW.format(mid="release a1b2c3d", status="not yet")).startswith("TODO")
    assert a5_line(demo_project, ROW.format(mid="<fill in: the two commits>", status="<fill in: done or not>")).startswith("TODO")


def test_ids_must_exist_in_the_site_repo(demo_project, tmp_path):
    repo = tmp_path / "site"
    repo.mkdir()
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-C", str(repo)]
    subprocess.run(git + ["init", "-q"], check=True)
    subprocess.run(git + ["commit", "-q", "--allow-empty", "-m", "x"], check=True)
    sha = subprocess.run(git + ["rev-parse", "--short=7", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    cfg = demo_project / "growth.json"
    c = json.loads(cfg.read_text())
    c["site_repo"] = str(repo)
    cfg.write_text(json.dumps(c))
    good = a5_line(demo_project, ROW.format(mid=f"release {sha}", status="done"))
    assert good.startswith("OK") and "found in the site repo" in good
    bad = a5_line(demo_project, ROW.format(mid="release 0badc0d", status="done"))
    assert bad.startswith("TODO") and "0badc0d" in bad
