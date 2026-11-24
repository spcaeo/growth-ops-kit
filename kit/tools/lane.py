#!/usr/bin/env python3
"""Builder lanes (kit 3.0, micro kit "build"): one private copy of the site, one port, one preview server per builder.

  growth lane open <path> --agent NAME [--from REF] [--branch NAME]   make the lane: worktree, port, build, own server
  growth lane list                                                    every open lane, its port and whether its server runs
  growth lane url <path|agent>                                        the lane's own preview address (never the owner's)
  growth lane rebuild <agent|path>                                    build again and restart that lane's server
  growth lane check <path|agent> [--type T --key K]                   the page gate on the lane's own build
  growth lane close <agent|path> [--force]                            stop its server, remove the worktree (the branch stays)

A lane is a git worktree of the site repo (growth.json "site_repo") kept in growth.json "lanes_dir" (default
~/lanes/<project folder name>). The lanes folder may sit next to the site repo (one folder for the whole project), but
never inside the project folder or inside the site repo itself. At most growth.json "lane_cap" lanes (default 3)
are open at once. The builder checks on its own port; READY stays on the owner's one preview address.

growth.json keys read: site_repo, lanes_dir, lane_cap (3), build_cmd, build_dir (dist, or "." with no build_cmd),
lane_build_timeout_s (900), lane_start_timeout_s (20), trailing_slash.
Lanes are the table `lanes`, owned by "build.lanes" in the project's store; every step is a store event.
Ports come from the board (`board.acquire("port", agent)`), so two lanes never share one.
"""
from __future__ import annotations

import argparse
import os
import re
import shlex
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402
import store  # noqa: E402

KIT_DIR = Path(__file__).resolve().parent.parent
SERVE = KIT_DIR / "tools" / "serve_build.py"
DDL = """
CREATE TABLE IF NOT EXISTS lanes (id INTEGER PRIMARY KEY AUTOINCREMENT, agent TEXT NOT NULL, page TEXT NOT NULL,
    dir TEXT NOT NULL, branch TEXT NOT NULL, port INTEGER, pid INTEGER, opened TEXT NOT NULL, state TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS lanes_state ON lanes(state)
"""
DIRTY_OK = ("next-env.d.ts", "*.tsbuildinfo")      # files a build rewrites by itself (like ready.py DIRTY_OK)
_CHILDREN: dict[int, subprocess.Popen] = {}         # servers this process started, so a stopped one is reaped, not a zombie


class LaneError(Exception):
    """A plain-words refusal; the command line prints it and exits 1."""


# -- small helpers -------------------------------------------------------------------------------------------------------
def _board():
    import board            # lazily: the real board.py arrives with its own branch
    return board


def _ctx(project):
    project = Path(project).resolve() if project else config.require_project()
    return project, config.load_cfg(project), store.open(project)


def _db(project):
    s = store.open(project)
    s.ensure("build.lanes", 1, DDL)
    return s


def norm_path(path: str) -> str:
    p = "/" + (path or "").strip().strip("/")
    return p if p != "/" else "/"


def slug(path: str) -> str:
    p = norm_path(path).strip("/")
    return re.sub(r"[^A-Za-z0-9._-]+", "-", p.replace("/", "__")) or "home"


def fetch_path(path: str, cfg: dict) -> str:
    """The address form the site wants (same rule as ready.fetch_path; copied so this module never loads a project)."""
    ts = cfg.get("trailing_slash")
    if ts in (True, "slash", "1", 1) and path != "/" and "." not in path.rsplit("/", 1)[-1]:
        return path + "/"
    return path


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def site_repo(project, cfg) -> Path:
    if not cfg.get("site_repo"):
        raise LaneError("growth.json has no site_repo: a lane is a copy of the site's code, so name its folder first.")
    repo = config.resolve_in(project, cfg["site_repo"])
    if git(repo, "rev-parse", "--git-dir").returncode != 0:
        raise LaneError(f"{repo} is not a git checkout, so no lane can be made from it.")
    return repo


def lanes_dir(project, cfg, repo) -> Path:
    """Where lanes live. Refused: inside the project folder (the growth notes stay free of code copies) and inside the
    site repo itself (a worktree nested in its own repo confuses git and the build). Next to the site repo is fine, so a
    whole project can live in one folder (owner, 24 Nov 2026: "keep all things releated to this project in this folder")."""
    given = cfg.get("lanes_dir")
    d = config.resolve_in(project, given) if given else Path.home() / "lanes" / project.name
    d = d.resolve()
    if d == project or project in d.parents:
        raise LaneError(f"lanes_dir {d} is inside the project folder {project}. Builder copies must live outside it: set "
                        f"growth.json lanes_dir to another folder, for example one beside the site repo.")
    site = repo.resolve()
    if d == site or site in d.parents:
        raise LaneError(f"lanes_dir {d} is inside the site repo {site}. Keep builder copies next to it, not in it: set "
                        f"growth.json lanes_dir to a folder beside the site, for example {site.parent / 'lanes'}.")
    return d


def port_free(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) != 0


def wait_port_free(port: int, seconds: float = 5.0) -> bool:
    """Wait (polling) until nothing listens on the port, up to `seconds`. A server that was just stopped may still be closing."""
    end = time.time() + seconds
    while True:
        if port_free(port):
            return True
        if time.time() >= end:
            return False
        time.sleep(0.1)


def take_port(agent: str, project, tries: int = 40) -> int:
    """A port from the board's pool that nothing is listening on. A port bound by something else is parked under a helper
    holder name (so the board hands out the next one), and every parked slot is given back at the end. Fails in plain words
    only when no port of the pool is usable."""
    board, parked = _board(), []
    try:
        for i in range(tries):
            lease = board.acquire("port", agent, project=project)
            if not lease:
                raise LaneError("no preview port is free right now (the board's port pool is used up or every free port is "
                                "in use by something else). Close a lane, or free a port, and try again.")
            port = int(lease["slot"])
            if wait_port_free(port, 0.5 if i == 0 else 0.0):
                return port
            board.release("port", agent, project=project)               # busy: park it under another name, ask for the next
            helper = f"{agent}~busy{i}"
            if board.acquire("port", helper, project=project):
                parked.append(helper)
        raise LaneError("every preview port of the pool is in use by something else. Free one, then try again.")
    finally:
        for h in parked:
            board.release("port", h, project=project)


def run_log(project: Path, name: str) -> Path:
    p = project / "journal" / "runs"
    p.mkdir(parents=True, exist_ok=True)
    return p / name


def _tail(path: Path, n=3) -> str:
    try:
        lines = [l for l in path.read_text(errors="replace").splitlines() if l.strip()]
    except OSError:
        return ""
    return " | ".join(l.strip()[:160] for l in lines[-n:])


# -- the server of a lane ------------------------------------------------------------------------------------------------
def _ps(pid: int) -> tuple[str, str]:
    r = subprocess.run(["ps", "-p", str(pid), "-o", "stat=,command="], capture_output=True, text=True)
    out = r.stdout.strip()
    if r.returncode != 0 or not out:
        return "", ""
    stat, _, cmd = out.partition(" ")
    return stat, cmd.strip()


def server_alive(pid, port) -> bool:
    """True only for OUR serve_build process on this port: a recycled pid of something else counts as stopped."""
    if not pid:
        return False
    child = _CHILDREN.get(int(pid))
    if child is not None and child.poll() is not None:
        return False
    stat, cmd = _ps(int(pid))
    if not stat or stat.startswith("Z"):
        return False
    return "serve_build" in cmd and f"--port {port}" in cmd


def stop_server(pid, port, wait_s=6.0) -> bool:
    """Stop the lane's server by its recorded pid (never by name or pattern). True when it was running and is now stopped."""
    if not server_alive(pid, port):
        return False
    pid = int(pid)
    for sig, grace in ((signal.SIGTERM, wait_s), (signal.SIGKILL, 3.0)):
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            break
        end = time.time() + grace
        while time.time() < end and server_alive(pid, port):
            time.sleep(0.1)
        if not server_alive(pid, port):
            break
    child = _CHILDREN.pop(pid, None)
    if child is not None:
        try:
            child.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass
    return not server_alive(pid, port)


def start_server(project, cfg, agent, root: Path, port: int) -> int:
    """Start `growth serve <root> --port <port>` in the background (its own session, output in journal/runs) and wait until it
    answers. Returns its pid. serve_build.py is started directly, so the recorded pid is the server itself."""
    if not root.is_dir():
        raise LaneError(f"there is no folder {root} to serve: the build made no {root.name}/ (growth.json build_dir).")
    if not wait_port_free(port, 3.0):
        raise LaneError(f"port {port} is already in use by something else; close what uses it or free the port, then rebuild.")
    log = open(run_log(project, f"lane-{agent}-server.log"), "ab")
    proc = subprocess.Popen([sys.executable, str(SERVE), str(root), "--port", str(port)], stdout=log, stderr=log,
                            stdin=subprocess.DEVNULL, start_new_session=True, close_fds=True)
    log.close()
    _CHILDREN[proc.pid] = proc
    end = time.time() + float(cfg.get("lane_start_timeout_s") or 20)
    while time.time() < end:
        if proc.poll() is not None:
            _CHILDREN.pop(proc.pid, None)
            raise LaneError(f"the server for lane {agent} stopped at once: {_tail(run_log(project, f'lane-{agent}-server.log'))}")
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=1) as r:
                r.read(1)
            return proc.pid
        except OSError:
            pass
        except Exception:  # noqa: BLE001  an HTTP error status still means the server is up (a site may have no /)
            return proc.pid
        time.sleep(0.15)
    stop_server(proc.pid, port)
    raise LaneError(f"the server for lane {agent} did not answer on port {port} within {cfg.get('lane_start_timeout_s') or 20} s.")


def build(project, cfg, agent, wt: Path) -> None:
    cmd = (cfg.get("build_cmd") or "").strip()
    if not cmd:
        return
    log = run_log(project, f"lane-{agent}-build.log")
    try:
        with open(log, "wb") as fh:
            r = subprocess.run(cmd, shell=True, cwd=wt, stdout=fh, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                               env={**os.environ, "GROWTH_AGENT": agent}, timeout=float(cfg.get("lane_build_timeout_s") or 900))
    except subprocess.TimeoutExpired:
        raise LaneError(f"the build of lane {agent} ran too long and was stopped (growth.json lane_build_timeout_s). Log: {log}")
    if r.returncode != 0:
        raise LaneError(f"the build of lane {agent} failed (exit {r.returncode}): {_tail(log)}. Full log: {log}. "
                        f"Fix it in {wt}, then: growth lane rebuild {agent}")


def build_root(cfg, wt: Path) -> Path:
    bd = cfg.get("build_dir") or ("dist" if (cfg.get("build_cmd") or "").strip() else ".")
    return (wt / bd).resolve()


# -- lanes (the table) ---------------------------------------------------------------------------------------------------
def _open_rows(s):
    return s.q("SELECT * FROM lanes WHERE state != 'closed' ORDER BY id")


def find(s, who: str):
    """The open lane named by its agent or by its page path."""
    for r in _open_rows(s):
        if r["agent"] == who or r["page"] == norm_path(who):
            return r
    raise LaneError(f"no open lane for '{who}'. See: growth lane list")


def status_word(r) -> str:
    if r["state"] == "build-failed":
        return "build failed"
    return "open" if server_alive(r["pid"], r["port"]) else "server stopped"


def lane_url(r, cfg) -> str:
    return f"http://127.0.0.1:{r['port']}{fetch_path(r['page'], cfg)}"


def open_lane(path, agent, ref=None, branch=None, project=None) -> dict:
    project, cfg, _ = _ctx(project)
    s = _db(project)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", agent or ""):
        raise LaneError("--agent must be a simple name (letters, digits, dot, dash), for example builder-1.")
    page = norm_path(path)
    repo = site_repo(project, cfg)
    base = lanes_dir(project, cfg, repo)
    cap = int(cfg.get("lane_cap") or 3)
    rows = _open_rows(s)
    for r in rows:
        if r["agent"] == agent:
            raise LaneError(f"{agent} already has a lane ({r['page']}). Close it first: growth lane close {agent}")
        if r["page"] == page:
            raise LaneError(f"{page} is already in lane {r['agent']}. One lane per page.")
    if len(rows) >= cap:
        raise LaneError(f"{len(rows)} lanes are open and the limit is {cap} (growth.json lane_cap). Close one first: "
                        f"{', '.join(r['agent'] for r in rows)}. A lane runs a build and a server, so the machine is the limit.")
    ref = ref or git(repo, "branch", "--show-current").stdout.strip() or "HEAD"
    if git(repo, "rev-parse", "--verify", "--quiet", ref + "^{commit}").returncode != 0:
        raise LaneError(f"{ref} is not a branch or commit of {repo}.")
    branch = branch or f"page/{slug(page)}"
    wt = base / f"{agent}-{slug(page)}"
    if wt.exists():
        raise LaneError(f"{wt} already exists. Remove it, or pick another agent name.")
    port = take_port(agent, project)
    s.event("lane-port", agent, {"port": port, "page": page})
    try:
        base.mkdir(parents=True, exist_ok=True)
        exists = git(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}").returncode == 0
        add = ["worktree", "add", str(wt), branch] if exists else ["worktree", "add", "-b", branch, str(wt), ref]
        r = git(repo, *add)
        if r.returncode != 0:
            raise LaneError(f"git could not make the worktree: {(r.stderr or r.stdout).strip().splitlines()[-1:]}")
    except BaseException:
        _board().release("port", agent, project=project)
        raise
    s.event("lane-worktree", agent, {"dir": str(wt), "branch": branch, "from": ref, "branch_existed": exists})
    nm = repo / "node_modules"
    if nm.is_dir() and not (wt / "node_modules").exists():
        os.symlink(nm, wt / "node_modules")
        s.event("lane-node-modules", agent, {"linked": str(nm)})
    email = git(repo, "config", "user.email").stdout.strip()
    if email and git(wt, "config", "user.email").stdout.strip() != email:     # rule 118: the commit identity
        git(wt, "config", "user.email", email)
    with s.tx() as db:
        cur = db.execute("INSERT INTO lanes(agent, page, dir, branch, port, pid, opened, state) VALUES(?,?,?,?,?,NULL,?,'open')",
                         (agent, page, str(wt), branch, port, store.now()))
        lane_id = cur.lastrowid
    return _build_and_serve(project, cfg, s, lane_id, wt)


def _build_and_serve(project, cfg, s, lane_id, wt) -> dict:
    r = s.q1("SELECT * FROM lanes WHERE id=?", (lane_id,))
    agent, port = r["agent"], r["port"]
    try:
        build(project, cfg, agent, wt)
    except LaneError as e:
        with s.tx() as db:
            db.execute("UPDATE lanes SET state='build-failed', pid=NULL WHERE id=?", (lane_id,))
        s.event("lane-build-failed", agent, {"why": str(e)[:300]})
        raise
    s.event("lane-built", agent, {"cmd": cfg.get("build_cmd") or ""})
    try:
        pid = start_server(project, cfg, agent, build_root(cfg, wt), port)
    except LaneError as e:
        with s.tx() as db:
            db.execute("UPDATE lanes SET state='open', pid=NULL WHERE id=?", (lane_id,))
        s.event("lane-server-failed", agent, {"why": str(e)[:300]})
        raise
    with s.tx() as db:
        db.execute("UPDATE lanes SET state='open', pid=? WHERE id=?", (pid, lane_id))
    s.event("lane-server", agent, {"pid": pid, "port": port})
    return dict(s.q1("SELECT * FROM lanes WHERE id=?", (lane_id,)))


def rebuild_lane(who, project=None) -> dict:
    project, cfg, _ = _ctx(project)
    s = _db(project)
    r = find(s, who)
    stop_server(r["pid"], r["port"])
    wt = Path(r["dir"])
    if not wt.is_dir():
        raise LaneError(f"the lane's folder {wt} is gone. Close it (growth lane close {r['agent']}) and open it again.")
    return _build_and_serve(project, cfg, s, r["id"], wt)


def dirty(wt: Path, cfg) -> list[str]:
    import fnmatch
    out = git(wt, "status", "--porcelain", "--untracked-files=all").stdout
    bd = (cfg.get("build_dir") or "dist").strip("/")
    files = []
    for ln in out.splitlines():
        f = ln[3:].split(" -> ")[-1].strip().strip('"')
        if not f or f == "node_modules" or f.startswith("node_modules/") or (bd != "." and f.startswith(bd + "/")):
            continue
        if any(fnmatch.fnmatch(f, p) or fnmatch.fnmatch(Path(f).name, p) for p in DIRTY_OK):
            continue
        files.append(f)
    return files


def close_lane(who, force=False, project=None) -> dict:
    project, cfg, _ = _ctx(project)
    s = _db(project)
    r = find(s, who)
    wt = Path(r["dir"])
    repo = site_repo(project, cfg)
    if wt.is_dir() and not force:
        d = dirty(wt, cfg)
        if d:
            raise LaneError(f"lane {r['agent']} has changes that are not committed ({', '.join(d[:5])}"
                            f"{'...' if len(d) > 5 else ''}). Commit them, or close with --force to throw them away.")
    stopped = stop_server(r["pid"], r["port"])
    if r["port"]:
        wait_port_free(int(r["port"]))                   # the next lane may get this port at once: it must really be free
    s.event("lane-server-stopped", r["agent"], {"pid": r["pid"], "was_running": stopped})
    if wt.is_dir():
        link = wt / "node_modules"
        if link.is_symlink():
            link.unlink()                    # the link only: never the clone's own node_modules
        g = git(repo, "worktree", "remove", "--force", str(wt))
        if g.returncode != 0:
            raise LaneError(f"git could not remove {wt}: {(g.stderr or g.stdout).strip().splitlines()[-1:]}")
    git(repo, "worktree", "prune")
    _board().release("port", r["agent"], project=project)
    with s.tx() as db:
        db.execute("UPDATE lanes SET state='closed', pid=NULL WHERE id=?", (r["id"],))
    s.event("lane-closed", r["agent"], {"dir": str(wt), "branch": r["branch"], "branch_kept": True})
    return dict(s.q1("SELECT * FROM lanes WHERE id=?", (r["id"],)))


def list_lanes(project=None) -> list[dict]:
    project, cfg, _ = _ctx(project)
    s = _db(project)
    return [{**dict(r), "status": status_word(r), "url": lane_url(r, cfg)} for r in _open_rows(s)]


def check_cmd(who, ptype=None, key=None, project=None):
    project, cfg, _ = _ctx(project)
    s = _db(project)
    r = find(s, who)
    cmd = [sys.executable, str(KIT_DIR / "tools" / "gate.py"), "page", r["page"], "--url", lane_url(r, cfg), "--repo", r["dir"]]
    if ptype:
        cmd += ["--type", ptype]
    if key:
        cmd += ["--key", key]
    return cmd, r, project


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="growth lane", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("open", help="make a lane for a page")
    o.add_argument("path"); o.add_argument("--agent", required=True)
    o.add_argument("--from", dest="ref", help="branch or commit to start from (default: the site repo's current branch)")
    o.add_argument("--branch", help="branch name (default page/<slug>)")
    sub.add_parser("list", help="open lanes")
    for name, h in (("url", "the lane's own preview address"), ("rebuild", "build again and restart the server"),
                    ("close", "stop the server, remove the worktree (branch kept)"), ("check", "run the page gate on the lane")):
        p = sub.add_parser(name, help=h)
        p.add_argument("who", metavar="agent-or-path")
        if name == "close":
            p.add_argument("--force", action="store_true", help="throw away uncommitted changes")
        if name == "check":
            p.add_argument("--type", choices=["money", "hub", "post", "core"]); p.add_argument("--key")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "open":
            r = open_lane(a.path, a.agent, a.ref, a.branch)
            cfg = config.load_cfg(config.require_project())
            print(f"Lane open: {r['agent']} on {r['page']}\n  worktree {r['dir']}\n  branch   {r['branch']}\n  preview  {lane_url(r, cfg)}")
        elif a.cmd == "list":
            rows = list_lanes()
            if not rows:
                print("No lanes are open.")
            for r in rows:
                print(f"{r['agent']:14} {r['page']:28} port {r['port']}  {r['status']:15} {r['branch']}  {r['dir']}")
        elif a.cmd == "url":
            project, cfg, s = _ctx(None)
            r = find(_db(project), a.who)
            if not server_alive(r["pid"], r["port"]):
                print(f"note: the server of lane {r['agent']} is stopped (growth lane rebuild {r['agent']} starts it).", file=sys.stderr)
            print(lane_url(r, cfg))
        elif a.cmd == "rebuild":
            r = rebuild_lane(a.who)
            print(f"Lane {r['agent']} rebuilt and serving on port {r['port']}.")
        elif a.cmd == "close":
            r = close_lane(a.who, a.force)
            print(f"Lane {r['agent']} closed: server stopped, worktree removed, port {r['port']} freed. Branch {r['branch']} is kept.")
        elif a.cmd == "check":
            cmd, r, project = check_cmd(a.who, a.type, a.key)
            return subprocess.call(cmd, cwd=project)
    except LaneError as e:
        print(f"growth lane: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
