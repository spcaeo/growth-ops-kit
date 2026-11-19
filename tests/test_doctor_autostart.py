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


def test_a8_before_go_live_needs_mapped_pages_not_changes(demo_project, tmp_path):
    """A site rebuilt locally sets page_tracker.changes_since to a future day so local commits are not read as live
    changes. A8 then passes with 0 changes as long as pages are mapped to files, and says it is waiting for go-live."""
    import json
    import sqlite3
    from datetime import date
    agents = tmp_path / "LaunchAgents"
    agents.mkdir()
    (demo_project / "page-tracker").mkdir(exist_ok=True)
    db = sqlite3.connect(demo_project / "page-tracker" / "tracker.db")
    db.executescript("create table search(path, day); create table pages(path, file); create table changes(id);")
    db.execute("insert into search values ('*', '2025-07-27'), ('*', ?)", (date.today().isoformat(),))
    db.execute("insert into pages values ('/x', 'src/content/x.mdx'), ('/y', null)")
    db.commit()
    db.close()
    site = tmp_path / "site"
    site.mkdir()
    cfg = json.loads((demo_project / "growth.json").read_text())
    cfg.update(site_repo=str(site), search_console_history_start="2025-07-27", tracker_port=1)
    (demo_project / "growth.json").write_text(json.dumps(cfg))
    line = doctor(demo_project, agents)
    assert line.startswith("FAIL") and "changes tracked: 0" in line and "waiting for go-live" not in line
    cfg["page_tracker"] = {"changes_since": "9999-12-31"}
    (demo_project / "growth.json").write_text(json.dumps(cfg))
    line = doctor(demo_project, agents)
    assert line.startswith("OK") and "waiting for go-live: changes count from 9999-12-31" in line and "changes tracked: 0" in line
    cfg["page_tracker"] = {"changes_since": "2000-01-01"}                       # a past day: changes are expected again
    (demo_project / "growth.json").write_text(json.dumps(cfg))
    line = doctor(demo_project, agents)
    assert line.startswith("FAIL") and "waiting for go-live" not in line
