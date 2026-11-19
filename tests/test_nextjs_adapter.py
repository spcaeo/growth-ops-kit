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
    assert any(l.startswith("SKIP repo.content-reader:") and "growth.json content_reader" in l for l in skips)
    assert any(l.startswith("SKIP repo.retired-410:") and "growth.json retired_paths" in l for l in skips)


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


def test_stack_neutral_settings_at_the_top_level_switch_the_checks_on(nx_project, base):
    project, repo = nx_project
    cfg = json.loads((project / "growth.json").read_text())
    cfg["content_reader"] = "lib/posts.ts"                 # top level, nothing under "nextjs"
    (project / "growth.json").write_text(json.dumps(cfg))
    _, lines = run_gate(project, base, "--only", "repo.content-reader")
    assert any("[repo.content-reader]" in l and l.startswith("OK") for l in lines), "\n".join(lines)
    assert not any(l.startswith("SKIP repo.content-reader") for l in lines)


def test_site_setting_reads_the_top_level_first_then_the_older_nextjs_block():
    import config
    old = {"nextjs": {"posts_dir": "old/posts", "retired_paths": ["/tag"]}}
    assert config.site_setting(old, "posts_dir", "content/posts") == "old/posts"      # the one-release fallback
    assert config.site_setting(old, "pages_dir", "content/pages") == "content/pages"  # default when neither has it
    both = {"posts_dir": "new/posts", "nextjs": {"posts_dir": "old/posts"}}
    assert config.site_setting(both, "posts_dir") == "new/posts"                      # the top level wins
    assert config.site_setting({"posts_dir": ""}, "posts_dir", "d") == "d"            # empty counts as not set
    assert set(config.SITE_KEYS) == {"retired_paths", "redirect_files", "posts_dir", "pages_dir", "content_reader"}


def test_the_project_template_keeps_the_neutral_keys_at_the_top_level():
    tpl = json.loads((ROOT / "templates" / "project" / "growth.json").read_text())
    import config
    for k in config.SITE_KEYS:
        assert k in tpl and k not in tpl["nextjs"], k


def test_the_site_hook_reads_posts_dir_from_either_place():
    sys.path.insert(0, str(ROOT / "kit" / "hooks"))
    import install_hooks
    for cfg in ({"posts_dir": "writing"}, {"nextjs": {"posts_dir": "writing"}}):
        assert install_hooks.route_of("writing/hello.md", Path("."), cfg) == "/blog/hello"
