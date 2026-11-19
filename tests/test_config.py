"""Project discovery: $GROWTH_PROJECT, else the nearest folder at or above the current one holding growth.json."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

import config


def make(tmp, name="p", **extra):
    p = Path(tmp) / name
    p.mkdir(parents=True)
    (p / "growth.json").write_text(json.dumps({"name": "T", "site_url": "https://t.example", **extra}))
    return p


def test_env_wins(tmp_path):
    a, b = make(tmp_path, "a"), make(tmp_path, "b")
    assert config.find_project(start=a, env={"GROWTH_PROJECT": str(b)}) == b.resolve()


def test_walks_up_to_the_nearest_growth_json(tmp_path):
    p = make(tmp_path)
    deep = p / "journal" / "pages"
    deep.mkdir(parents=True)
    assert config.find_project(start=deep, env={}) == p.resolve()


def test_nearest_wins_over_a_farther_one(tmp_path):
    outer = make(tmp_path, "outer")
    inner = make(outer, "inner")
    assert config.find_project(start=inner / "docs" if (inner / "docs").exists() else inner, env={}) == inner.resolve()


def test_none_when_there_is_no_project(tmp_path):
    (tmp_path / "x").mkdir()
    assert config.find_project(start=tmp_path / "x", env={}) is None


def test_env_pointing_at_a_folder_without_growth_json_is_none(tmp_path):
    (tmp_path / "x").mkdir()
    assert config.find_project(start=tmp_path, env={"GROWTH_PROJECT": str(tmp_path / "x")}) is None


def test_paths_resolve_from_the_project_root(tmp_path):
    p = make(tmp_path)
    assert config.resolve_in(p, "../site") == (tmp_path / "site").resolve()
    assert config.resolve_in(p, "~/k.env") == Path("~/k.env").expanduser()
    assert config.project_dirs(p)["journal"] == p / "journal"


def test_kit_files_are_not_in_the_project():
    assert config.REGISTRY.is_file() and config.KIT_DIR in config.REGISTRY.parents
    assert config.RULEBOOK.parent == config.BOOK


def test_importing_without_a_project_is_safe_and_reading_a_fact_says_why(tmp_path):
    """`import config` never fails; the first read of a project fact stops with one clear line."""
    code = "import config\nprint(config.KIT_DIR.name)\ntry:\n    config.CFG\nexcept SystemExit as e:\n    print('EXIT', e)\n"
    out = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, capture_output=True, text=True,
                         env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(Path(config.__file__).parent), "HOME": str(tmp_path)})
    assert "kit" in out.stdout and "EXIT No project found" in out.stdout, out.stdout + out.stderr


def test_loading_sets_env_for_child_tools(tmp_path):
    p = make(tmp_path, stack="nextjs")
    code = "import config, os\nprint(config.CFG['stack'], config.PROJECT.name, os.environ['GROWTH_PROJECT'])"
    out = subprocess.run([sys.executable, "-c", code], cwd=p, capture_output=True, text=True,
                         env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(Path(config.__file__).parent), "HOME": str(tmp_path)})
    assert out.stdout.split()[:2] == ["nextjs", "p"], out.stderr


def test_missing_key_gives_a_note_not_a_crash(tmp_path, monkeypatch, capsys):
    p = make(tmp_path, keys_file=str(tmp_path / "none.env"), connectors={"skald": {"on": True}})
    monkeypatch.setenv("GROWTH_PROJECT", str(p))
    for k in ("PROJECT", "CFG", "DOCS", "SITE_URL", "HOST", "TZ", "SITE_REPO", "KEYS", "UA"):
        config.__dict__.pop(k, None)
    assert config.connector_on("skald")
    assert config.keys() == {}
    assert config.note_missing_key("skald", "SKALD_MCP_URL", "SKALD_MCP_TOKEN") is True
    assert "keys file" in capsys.readouterr().err
    for k in ("PROJECT", "CFG", "DOCS", "SITE_URL", "HOST", "TZ", "SITE_REPO", "KEYS", "UA"):
        config.__dict__.pop(k, None)


def test_owner_messages_find_the_transcripts_of_the_projects_own_path(tmp_path, demo_project, monkeypatch):
    monkeypatch.setenv("GROWTH_PROJECT", str(demo_project))
    for k in ("PROJECT", "CFG", "DOCS", "SITE_URL", "HOST", "TZ", "SITE_REPO", "KEYS", "UA"):
        config.__dict__.pop(k, None)
    import owner_messages as om
    proj = tmp_path / "work" / "my_site"
    proj.mkdir(parents=True)
    home = tmp_path / "home"
    want = home / ".claude" / "projects" / om.slug(proj)
    want.mkdir(parents=True)
    assert om.slug(proj) == "-" + str(proj).strip("/").replace("/", "-").replace("_", "-")
    assert om.transcript_dirs(proj, home=home) == [want]
    parent = home / ".claude" / "projects" / om.slug(proj.parent)
    parent.mkdir(parents=True)
    assert om.transcript_dirs(proj, home=home) == [want]      # the folder above is never read by default (#21)
    assert om.transcript_dirs(proj, home=home, cfg={"transcripts_dir": str(parent)}) == [parent]       # only when growth.json says so
    assert om.transcript_dirs(proj, home=home, cfg={"transcripts_dir": [str(want), str(parent)]}) == [want, parent]
    assert om.transcript_dirs(proj, home=tmp_path / "empty") == []
