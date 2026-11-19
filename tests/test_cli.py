"""The `growth` command: help lists every tool with one line, a tool runs by name (hyphens or underscores), a missing
tool and a missing project say so plainly."""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GROWTH = ROOT / "growth"


def growth(*args, cwd=None, env=None):
    import os
    e = {**os.environ, "GROWTH_PROJECT": ""}
    e.pop("GROWTH_PROJECT")
    e.update(env or {})
    return subprocess.run([sys.executable, str(GROWTH), *args], capture_output=True, text=True, cwd=cwd or ROOT, env=e)


def test_help_lists_every_tool_with_one_line():
    r = growth("help")
    assert r.returncode == 0
    for line in r.stdout.splitlines():
        pass
    listed = {l.split()[0] for l in r.stdout.split("Tools:")[1].splitlines() if l.startswith("  ")}
    tools = {p.stem.replace("_", "-") for p in (ROOT / "kit" / "tools").glob("*.py") if p.stem not in ("config",)}
    quiet = {"owner-messages"}  # listed below as owner-messages
    missing = {t for t in tools if t.replace("-", "_") not in {x.replace("-", "_") for x in listed}}
    assert missing == set(), f"tools with no line in growth help: {sorted(missing)}"
    assert all(re.search(r"\S+\s{2,}\S", l) for l in r.stdout.split("Tools:")[1].splitlines() if l.startswith("  "))


def test_no_args_is_help():
    assert growth().stdout == growth("help").stdout


def test_every_listed_tool_file_exists():
    ns = {}
    exec(compile(GROWTH.read_text(), "growth", "exec"), {"__name__": "x", "__file__": str(GROWTH)}, ns)
    for name, (rel, _line) in ns["TOOLS"].items():
        assert (ROOT / "kit" / rel).is_file(), f"growth help lists {name} but kit/{rel} is missing"


def test_unknown_tool():
    r = growth("nope")
    assert r.returncode == 2 and "no tool 'nope'" in r.stderr


def test_a_tool_runs_by_name_with_hyphen_or_underscore(demo_project):
    a = growth("tech-seo-check", "--help", cwd=demo_project)
    b = growth("tech_seo_check", "--help", cwd=demo_project)
    assert a.returncode == 0 and a.stdout == b.stdout and "Technical SEO checker" in a.stdout


def test_a_project_tool_outside_a_project_says_what_to_do(tmp_path):
    r = growth("doctor", cwd=tmp_path)
    assert r.returncode != 0 and "No project found" in (r.stderr + r.stdout) and "GROWTH_PROJECT" in (r.stderr + r.stdout)


def test_doctor_runs_inside_the_demo_project(demo_project):
    r = growth("doctor", cwd=demo_project)
    assert "Brightline Lawn Care growth setup" in r.stdout and "A6 Task tracker" in r.stdout


def test_project_found_from_the_env(demo_project, tmp_path):
    r = growth("tasks", "list", cwd=tmp_path, env={"GROWTH_PROJECT": str(demo_project)})
    assert r.returncode == 0, r.stderr


def test_tasks_round_trip_in_a_scratch_project(demo_project):
    t = growth("tasks", "add", "Check the pricing page", "owner words", cwd=demo_project)
    assert t.stdout.strip() == "T1"
    growth("tasks", "step", "T1", "Read the page", cwd=demo_project)
    data = json.loads((demo_project / "docs" / "tasks.json").read_text())
    assert data["tasks"][0]["steps"][0]["what"] == "Read the page"
    assert "T1" in growth("tasks", "list", cwd=demo_project).stdout


def test_gate_coverage_runs_without_a_page(demo_project):
    r = growth("gate", "coverage", cwd=demo_project)
    assert r.returncode == 0, r.stdout[-400:]
    assert "read the live page" in r.stdout and "Next.js site code via the adapter" in r.stdout


def test_techseo_selftest_runs():
    r = growth("techseo", "selftest")
    assert r.returncode == 0 and "selftest: PASS" in r.stdout, r.stdout + r.stderr


def test_checks_command_exists_and_prints_its_plan(tmp_path):
    import shutil
    if not shutil.which("git"):
        return
    subprocess.run(["git", "init", "-q"], cwd=tmp_path)
    r = growth("checks", "--dry-run", cwd=tmp_path)
    assert r.returncode == 0 and "nothing to check" in r.stdout.lower() or "Changed:" in r.stdout


def test_the_book_names_only_real_growth_json_keys(root):
    """Every growth.json key the book mentions is a field of the template."""
    import re
    keys = set(json.loads((root / "templates" / "project" / "growth.json").read_text()))
    cfg = json.loads((root / "templates" / "project" / "growth.json").read_text())
    for v in cfg.values():
        if isinstance(v, dict):
            keys |= set(v)
    text = "\n".join(p.read_text() for p in (root / "book").rglob("*.md"))
    named = set(re.findall(r"`growth\.json`\s+`([a-z_]+)`", text)) | set(re.findall(r"growth\.json`?\s+`([a-z_]+)`", text))
    missing = sorted(k for k in named if k not in keys)
    assert missing == [], f"the book names growth.json keys the template lacks: {missing}"


def test_adapter_tools_on_a_static_project_say_skip(demo_project):
    for tool in ("link_map", "checks"):
        r = growth(tool, "orphans" if tool == "link_map" else "--dry-run", cwd=demo_project, env={"GROWTH_PROJECT": str(demo_project)})
        assert r.returncode == 0 and r.stdout.startswith("SKIP: no adapter for static"), (tool, r.stdout, r.stderr)


def test_brief_with_an_output_outside_the_project_has_no_traceback(demo_project, tmp_path):
    out = tmp_path / "elsewhere" / "brief.md"
    env = {"GROWTH_PROJECT": str(demo_project)}
    growth("tasks", "add", "Money page: lawn mowing", "Make it better", cwd=demo_project, env=env)
    r = growth("brief", "/lawn-mowing", "--type", "money", "--task", "T1", "--out", str(out), cwd=demo_project, env=env)
    assert "Traceback" not in r.stderr and r.returncode == 0, r.stderr
    assert out.exists()
    assert str(ROOT / "book" / "01-flow.md") in out.read_text()    # absolute kit paths: they resolve from the project folder
