"""Builder lanes (kit 3.0, micro kit "build"): two lanes at once on their own ports and worktrees, the cap, the lanes
folder rule, and a close that stops only its own server, keeps the branch and frees the port. Real git repos and real
servers, all under pytest's tmp_path; every server is stopped by the fixture, pass or fail."""
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _board_stub  # noqa: E402
import lane  # noqa: E402  (kit/tools is on sys.path from conftest)

BUILD = "rm -rf dist && mkdir dist && cp -R src/. dist/"


def sh(*cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def commit(repo, msg):
    sh("git", "add", "-A", cwd=repo)
    sh("git", "-c", "core.hooksPath=/dev/null", "commit", "-q", "-m", msg, cwd=repo)   # a scratch repo, not the kit's own


@pytest.fixture
def env(tmp_path, monkeypatch):
    work, lanes = tmp_path / "work", tmp_path / "lanes"
    project, site = work / "project", work / "site"
    project.mkdir(parents=True)
    (site / "src").mkdir(parents=True)
    (site / "src" / "index.html").write_text("<h1>hello lane</h1>")
    (site / "src" / "about.html").write_text("<h1>about</h1>")
    (site / ".gitignore").write_text("dist/\nnode_modules/\n")
    (site / "node_modules").mkdir()
    sh("git", "init", "-q", "-b", "main", cwd=site)
    sh("git", "config", "user.email", "builder@example.test", cwd=site)
    sh("git", "config", "user.name", "Builder", cwd=site)
    commit(site, "first")
    cfg = {"name": "T", "site_url": "https://t.example", "site_repo": str(site), "build_cmd": BUILD, "build_dir": "dist",
           "lanes_dir": str(lanes)}
    (project / "growth.json").write_text(json.dumps(cfg))
    monkeypatch.setenv("GROWTH_PROJECT", str(project))
    board = _board_stub.use_board(monkeypatch)
    e = type("Env", (), {})()
    e.project, e.site, e.lanes, e.board, e.cfg = project.resolve(), site.resolve(), lanes, board, cfg
    e.set_cfg = lambda **kw: (project / "growth.json").write_text(json.dumps({**cfg, **kw}))
    yield e
    for r in lane._open_rows(lane._db(e.project)):             # teardown: no server survives a test
        try:
            lane.close_lane(r["agent"], force=True, project=e.project)
        except Exception:  # noqa: BLE001
            lane.stop_server(r["pid"], r["port"])
    for pid, proc in list(lane._CHILDREN.items()):
        if proc.poll() is None:
            proc.kill()
        proc.wait()


def get(port, path="/"):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as r:
        return r.status, r.read().decode()


def test_two_lanes_at_once_on_their_own_ports_and_worktrees(env):
    a = lane.open_lane("/", "builder-1", project=env.project)
    b = lane.open_lane("/about", "builder-2", project=env.project)
    assert a["port"] != b["port"]
    assert a["dir"] != b["dir"] and Path(a["dir"]).is_dir() and Path(b["dir"]).is_dir()
    assert a["branch"] == "page/home" and b["branch"] == "page/about"
    for r in (a, b):
        assert get(r["port"])[0] == 200
        d = Path(r["dir"]).resolve()
        assert env.project not in d.parents and env.site.parent not in d.parents      # outside the project and the site's folder
        assert env.lanes.resolve() in d.parents
    assert "hello lane" in get(a["port"])[1]
    rows = lane.list_lanes(env.project)
    assert [r["status"] for r in rows] == ["open", "open"]
    assert {r["agent"] for r in rows} == {"builder-1", "builder-2"}


def test_node_modules_linked_identity_kept_and_events_recorded(env):
    a = lane.open_lane("/", "builder-1", project=env.project)
    wt = Path(a["dir"])
    assert (wt / "node_modules").is_symlink() and (wt / "node_modules").resolve() == (env.site / "node_modules").resolve()
    assert sh("git", "config", "user.email", cwd=wt) == "builder@example.test"
    kinds = [e["kind"] for e in lane.store.open(env.project).events(subject="builder-1")]
    for k in ("lane-port", "lane-worktree", "lane-built", "lane-server"):
        assert k in kinds
    assert get(a["port"], "/about")[0] == 200            # /about answers about.html (serve_build)


def test_the_cap_refuses_a_fourth_lane_in_plain_words(env):
    for i, p in enumerate(["/", "/about", "/c"], 1):
        lane.open_lane(p, f"b{i}", project=env.project)
    with pytest.raises(lane.LaneError) as e:
        lane.open_lane("/d", "b4", project=env.project)
    assert "3 lanes are open and the limit is 3" in str(e.value)
    assert len(lane.list_lanes(env.project)) == 3
    assert not (env.lanes / "b4-d").exists()


def test_lane_cap_comes_from_growth_json(env):
    env.set_cfg(lane_cap=1)
    lane.open_lane("/", "b1", project=env.project)
    with pytest.raises(lane.LaneError, match="limit is 1"):
        lane.open_lane("/about", "b2", project=env.project)


def test_one_lane_per_agent_and_per_page(env):
    lane.open_lane("/", "b1", project=env.project)
    with pytest.raises(lane.LaneError, match="already has a lane"):
        lane.open_lane("/about", "b1", project=env.project)
    with pytest.raises(lane.LaneError, match="already in lane b1"):
        lane.open_lane("/", "b2", project=env.project)


@pytest.mark.parametrize("where", ["inside_project", "inside_site_parent"])
def test_a_lanes_dir_inside_the_project_or_the_sites_folder_is_refused(env, where):
    bad = env.project / "lanes" if where == "inside_project" else env.site.parent / "lanes"
    env.set_cfg(lanes_dir=str(bad))
    with pytest.raises(lane.LaneError, match="outside"):
        lane.open_lane("/", "b1", project=env.project)
    assert not bad.exists()                                # nothing was made
    assert env.board.held("port", project=env.project) == []


def test_close_stops_only_its_own_server_keeps_the_branch_and_frees_the_port(env):
    a = lane.open_lane("/", "builder-1", project=env.project)
    b = lane.open_lane("/about", "builder-2", project=env.project)
    assert {h["slot"] for h in env.board.held("port", project=env.project)} == {str(a["port"]), str(b["port"])}
    r = lane.close_lane("builder-1", project=env.project)
    assert r["state"] == "closed"
    assert not lane.server_alive(a["pid"], a["port"])
    with pytest.raises(OSError):
        get(a["port"])
    assert get(b["port"])[0] == 200                         # the other lane never noticed
    assert lane.server_alive(b["pid"], b["port"])
    assert not Path(a["dir"]).exists() and Path(b["dir"]).is_dir()
    assert "page/home" in sh("git", "branch", "--list", "page/home", cwd=env.site)        # the branch is kept
    assert str(a["dir"]) not in sh("git", "worktree", "list", cwd=env.site)
    assert (env.site / "node_modules").is_dir()             # the clone's own node_modules is untouched
    assert {h["slot"] for h in env.board.held("port", project=env.project)} == {str(b["port"])}
    assert [x["agent"] for x in lane.list_lanes(env.project)] == ["builder-2"]
    assert "lane-closed" in [e["kind"] for e in lane.store.open(env.project).events(subject="builder-1")]
    with pytest.raises(lane.LaneError, match="no open lane"):
        lane.close_lane("builder-1", project=env.project)


def test_close_refuses_uncommitted_work_unless_forced(env):
    a = lane.open_lane("/", "b1", project=env.project)
    (Path(a["dir"]) / "src" / "new.html").write_text("work in progress")
    with pytest.raises(lane.LaneError, match="not committed"):
        lane.close_lane("b1", project=env.project)
    assert lane.server_alive(a["pid"], a["port"]) and Path(a["dir"]).is_dir()     # nothing was touched
    lane.close_lane("b1", force=True, project=env.project)
    assert not Path(a["dir"]).exists()


def test_a_lane_whose_server_died_shows_server_stopped_and_rebuild_restarts_it(env):
    a = lane.open_lane("/", "b1", project=env.project)
    assert lane.stop_server(a["pid"], a["port"])
    assert lane.list_lanes(env.project)[0]["status"] == "server stopped"
    (Path(a["dir"]) / "src" / "index.html").write_text("<h1>second build</h1>")
    r = lane.rebuild_lane("b1", project=env.project)
    assert r["port"] == a["port"] and lane.server_alive(r["pid"], r["port"])
    assert "second build" in get(r["port"])[1]
    assert lane.list_lanes(env.project)[0]["status"] == "open"


def test_a_failed_build_keeps_the_lane_so_the_builder_can_fix_it(env):
    env.set_cfg(build_cmd="echo 'error: nope' >&2; exit 3")
    with pytest.raises(lane.LaneError, match="build of lane b1 failed.*nope"):
        lane.open_lane("/", "b1", project=env.project)
    r = lane.list_lanes(env.project)[0]
    assert r["status"] == "build failed" and Path(r["dir"]).is_dir()
    env.set_cfg()                                             # fixed: the normal build
    r2 = lane.rebuild_lane("b1", project=env.project)
    assert get(r2["port"])[0] == 200


def test_url_and_check_use_the_lanes_own_address_never_the_preview(env):
    env.set_cfg(preview_url="http://127.0.0.1:18432", trailing_slash=True)
    a = lane.open_lane("/about", "b1", project=env.project)
    cmd, row, _ = lane.check_cmd("/about", "post", "about", project=env.project)
    assert cmd[cmd.index("--url") + 1] == f"http://127.0.0.1:{a['port']}/about/"
    assert cmd[cmd.index("--repo") + 1] == a["dir"] and "18432" not in " ".join(cmd)
    assert cmd[cmd.index("--type") + 1] == "post" and cmd[cmd.index("--key") + 1] == "about"


def test_command_line_open_list_url_close(env, capsys):
    assert lane.main(["open", "/", "--agent", "b1"]) == 0
    assert lane.main(["list"]) == 0
    assert lane.main(["url", "b1"]) == 0
    out = capsys.readouterr().out
    assert "Lane open: b1" in out and "page/home" in out and "http://127.0.0.1:" in out
    assert lane.main(["close", "b1"]) == 0
    assert lane.main(["close", "b1"]) == 1
    assert "no open lane" in capsys.readouterr().err
