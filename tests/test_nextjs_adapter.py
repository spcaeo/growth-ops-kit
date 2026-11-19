"""The Next.js adapter on a plain Next.js repo (tests/fixtures/nextjs_repo.py): no check crashes, and no check FAILs only
because this site is laid out differently from the site the checks were first written for (a production branch called
trunk and no remote, no content folder, no content-reader module, no retired page groups, no redirect file)."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixtures.nextjs_repo import make_repo  # noqa: E402
from test_demo import base, free_port  # noqa: E402,F401  (the demo server fixture: the page the adapter's checks read)

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "examples" / "demo-site"
GATE = ROOT / "kit" / "tools" / "gate.py"


def run_gate(project, base_url, *extra):
    env = {k: v for k, v in os.environ.items() if k != "GROWTH_PROJECT"}
    env["GROWTH_PROJECT"] = str(project)
    r = subprocess.run([sys.executable, str(GATE), "page", "/lawn-mowing", "--url", base_url + "/lawn-mowing", "--type", "money",
                        "--no-browser", "--no-link-status", "--needs", "nextjs", *extra],
                       capture_output=True, text=True, env=env, cwd=project, timeout=600)
    return r, r.stdout.splitlines()


@pytest.fixture
def nx_project(tmp_path, demo_project):
    repo = make_repo(tmp_path / "site")
    cfg = json.loads((demo_project / "growth.json").read_text())
    cfg.update({"stack": "nextjs", "site_repo": str(repo), "nextjs": {"production_branch": "trunk"}})
    (demo_project / "growth.json").write_text(json.dumps(cfg, indent=2))
    return demo_project, repo


def test_no_adapter_check_crashes_on_a_plain_nextjs_repo(nx_project, base):
    project, _ = nx_project
    r, lines = run_gate(project, base)
    crashed = [l for l in lines if "check crashed" in l]
    assert crashed == [], "\n".join(crashed)
    assert any(l.startswith("OK") for l in lines), "no adapter check ran at all"


def test_no_false_fail_from_layout_assumptions(nx_project, base):
    project, _ = nx_project
    _, lines = run_gate(project, base)
    fails = "\n".join(l for l in lines if l.startswith("FAIL"))
    for assumption in ("lib/content.ts", "/tag/", "origin/main", "unknown revision", "lib/hubs", "content/posts"):
        assert assumption not in fails, f"a FAIL still assumes {assumption!r}:\n{fails}"
    skips = [l for l in lines if l.startswith("SKIP")]
    assert any(l.startswith("SKIP repo.content-reader:") and "nextjs.content_reader" in l for l in skips)
    assert any(l.startswith("SKIP repo.retired-410:") and "nextjs.retired_paths" in l for l in skips)


def test_the_branch_checks_use_the_configured_production_branch(nx_project, base):
    project, repo = nx_project
    _, lines = run_gate(project, base, "--only", "repo.branch,repo.commit-identity,repo.url-frozen,repo.bulk-backup")
    assert not [l for l in lines if l.startswith("FAIL") and "revision" in l], "\n".join(lines)
    assert any("[repo.url-frozen]" in l and l.startswith("OK") for l in lines), "\n".join(lines)


def test_with_no_production_branch_the_error_names_the_setting(nx_project, base):
    project, repo = nx_project
    cfg = json.loads((project / "growth.json").read_text())
    cfg["nextjs"] = {}                                  # default main (or master): the fixture has only trunk
    (project / "growth.json").write_text(json.dumps(cfg))
    _, lines = run_gate(project, base, "--only", "repo.url-frozen")
    assert any("nextjs.production_branch" in l for l in lines), "\n".join(lines)


def test_a_configured_content_reader_is_checked(nx_project, base):
    project, repo = nx_project
    cfg = json.loads((project / "growth.json").read_text())
    cfg["nextjs"]["content_reader"] = "lib/posts.ts"
    (project / "growth.json").write_text(json.dumps(cfg))
    _, lines = run_gate(project, base, "--only", "repo.content-reader")
    assert any("[repo.content-reader]" in l and l.startswith("OK") for l in lines), "\n".join(lines)
