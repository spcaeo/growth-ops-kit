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
