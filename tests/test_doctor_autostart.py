"""Doctor A8 counts only the auto-start jobs of THIS project: a launchd plist or crontab line that runs something inside
the project folder (or names it). Another tool for the same business, in its own folder, is not counted, even when its
label carries the business name, and a sibling folder whose name starts the same is not mistaken for ours."""
import os
import plistlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCTOR = ROOT / "kit" / "tools" / "doctor.py"


def plist(folder, label, args, **extra):
    (folder / f"{label}.plist").write_bytes(plistlib.dumps({"Label": label, "ProgramArguments": args, **extra}))


def doctor(project, agents, cron=""):
    env = {**os.environ, "GROWTH_PROJECT": str(project), "GROWTH_LAUNCHD_DIRS": str(agents), "GROWTH_CRONTAB": cron}
    r = subprocess.run([sys.executable, str(DOCTOR)], capture_output=True, text=True, cwd=project, env=env)
    return next(l for l in r.stdout.splitlines() if "A8 Page tracker" in l)


def test_only_jobs_inside_this_project_folder_count(demo_project, tmp_path):
    agents = tmp_path / "LaunchAgents"
    agents.mkdir()
    name = "brightline"  # the demo business: the old check matched any job with this word in it
    other = tmp_path / f"{name}-tools" / "tracker"
    plist(agents, f"com.{name}.page-tracker", ["/bin/zsh", "-l", str(other / "daily.sh")])
    plist(agents, f"com.{name}.page-tracker-web", ["python3", str(other / "serve.py")])
    plist(agents, "com.example.sibling", ["python3", str(demo_project) + "-copy/run.py"])
    assert "auto-start jobs: 0" in doctor(demo_project, agents)

    plist(agents, "com.example.ours", ["python3", str(demo_project / "page-tracker" / "start.py")])
    line = doctor(demo_project, agents, cron=f"# {demo_project}\n15 9 * * * GROWTH_PROJECT={demo_project} growth page-tracker sync\n")
    assert "auto-start jobs: 2" in line and "launchd com.example.ours" in line and "cron: 15 9" in line


def test_a_job_that_names_the_folder_in_its_environment_counts(demo_project, tmp_path):
    agents = tmp_path / "LaunchAgents"
    agents.mkdir()
    plist(agents, "com.example.env", ["growth", "page-tracker", "sync"], EnvironmentVariables={"GROWTH_PROJECT": str(demo_project)})
    assert "auto-start jobs: 1" in doctor(demo_project, agents)


def test_jobs_the_owner_scheduled_are_allowed(demo_project, tmp_path):
    """growth.json automation.jobs (label + why) lists jobs the owner chose to run by themselves: shown, not blocking."""
    import json
    agents = tmp_path / "LaunchAgents"
    agents.mkdir()
    plist(agents, "com.example.operator", ["/bin/zsh", "run.sh", str(demo_project)], WorkingDirectory=str(demo_project))
    assert "auto-start jobs: 1" in doctor(demo_project, agents)
    cfg = json.loads((demo_project / "growth.json").read_text())
    cfg["automation"] = {"jobs": [{"label": "com.example.operator", "why": "the owner wants a daily operator run"}]}
    (demo_project / "growth.json").write_text(json.dumps(cfg))
    line = doctor(demo_project, agents)
    assert "auto-start jobs: 0" in line and "scheduled by the owner (growth.json automation.jobs): launchd com.example.operator" in line
    cfg["automation"] = {"jobs": [{"label": "com.example.operator"}]}            # no why: not allowed
    (demo_project / "growth.json").write_text(json.dumps(cfg))
    assert "auto-start jobs: 1" in doctor(demo_project, agents)
