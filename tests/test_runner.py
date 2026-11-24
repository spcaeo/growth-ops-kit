"""The machine runner (kit 3.0, micro kit "evidence") on the real board: jobs side by side but never more than --jobs, a
failing command fails its job with the last error line, a browser pool of 1 runs browser jobs one at a time, the load
guard waits, and an interrupt ends every command and fails its jobs back. The jobs are a tiny script that records its start
and end times; job kinds are the manifest's (inventory and link-graph need no page, shots needs the browser)."""
import json
import shlex
import sys
import threading
import time
from pathlib import Path

import pytest

import board  # noqa: E402  (the real board; kit/tools is on sys.path from conftest)
import runner  # noqa: E402

FAKE = '''
import sys, time, os
key, secs, code = sys.argv[1], float(sys.argv[2]), int(sys.argv[3])
log = os.environ["FAKE_LOG"]
with open(log, "a") as f: f.write(f"start {key} {time.time()}\\n")
time.sleep(secs)
if code:
    print("starting the thing"); print(f"error: {key} blew up", file=sys.stderr); print("cleaning up")
with open(log, "a") as f: f.write(f"end {key} {time.time()}\\n")
sys.exit(code)
'''
PY = shlex.quote(sys.executable)


def job_cmd(secs, code=0):
    return f"{PY} tools/fake_job.py $$ {secs} {code}"          # $$ = the shell's own number: a distinct key for every run


@pytest.fixture
def env(tmp_path, monkeypatch):
    project = tmp_path / "project"
    (project / "tools").mkdir(parents=True)
    (project / "tools" / "fake_job.py").write_text(FAKE)
    cfg = {"name": "T", "site_url": "https://t.example", "runner_max_load": 1000, "runner_min_free_pct": 0, "runner_beat_s": 0.2,
           "machine_jobs": {"inventory": job_cmd(0.6), "link-graph": job_cmd(0.1, 3), "shots": job_cmd(0.6)}}
    (project / "growth.json").write_text(json.dumps(cfg))
    monkeypatch.setenv("GROWTH_PROJECT", str(project))
    monkeypatch.setenv("FAKE_LOG", str(tmp_path / "times.log"))
    e = type("Env", (), {})()
    e.project, e.board, e.log, e.cfg = project.resolve(), board, tmp_path / "times.log", cfg
    e.set_cfg = lambda **kw: (project / "growth.json").write_text(json.dumps({**cfg, **kw}))
    e.run = lambda **kw: runner.Runner(e.project, once=True, poll=0.2, out=lambda t: None, **kw).run()
    e.job = lambda i: next(j for j in board.jobs_view(project=e.project) if j["id"] == i)
    e.add = lambda kind, n=1: [board.add_job(kind, project=e.project) for _ in range(n)]

    def shots(n):                                              # n browser jobs on pages of the board
        ids = []
        for i in range(n):
            board.add_page(f"/b{i}", "post", f"b{i}", project=e.project)
            ids.append(board.add_job("shots", f"/b{i}", project=e.project))
        return ids
    e.shots = shots
    return e


def spans(log: Path):
    start, out = {}, []
    for ln in log.read_text().splitlines():
        what, key, t = ln.split()
        if what == "start":
            start[key] = float(t)
        else:
            out.append((start[key], float(t)))
    return out


def max_overlap(spans_):
    events = sorted([(s, 1) for s, _ in spans_] + [(e, -1) for _, e in spans_], key=lambda x: (x[0], x[1]))
    cur = best = 0
    for _, d in events:
        cur += d
        best = max(best, cur)
    return best


def test_six_jobs_with_three_side_by_side_all_done(env, monkeypatch):
    beats = []
    real_beat = board.beat
    monkeypatch.setattr(board, "beat", lambda *a, **k: beats.append(a) or real_beat(*a, **k))
    ids = env.add("inventory", 6)
    t0 = time.time()
    assert env.run(jobs=3) == 0
    wall = time.time() - t0
    assert [env.job(i)["status"] for i in ids] == ["done"] * 6
    sp = spans(env.log)
    assert len(sp) == 6 and max_overlap(sp) == 3          # three ran at the same time, never four
    assert wall < 6 * 0.6                                  # and so it was faster than one at a time
    j = env.job(ids[0])
    log = j["proof"].split("log ")[1]
    assert j["proof"].startswith("exit 0, log journal/runs/inventory-") and (env.project / log).is_file()
    assert j["holder"].startswith("runner-")
    assert (env.project / log).read_text().startswith("$ ")
    assert beats                                           # a heartbeat went out while they ran (runner_beat_s 0.2)


def test_jobs_one_runs_them_in_a_row(env):
    env.add("inventory", 3)
    assert env.run(jobs=1) == 0
    assert max_overlap(spans(env.log)) == 1


def test_a_failing_command_fails_the_job_with_its_last_error_line(env):
    bad, ok = env.add("link-graph")[0], env.add("inventory")[0]
    assert env.run(jobs=2) == 1                            # the run says something failed
    j = env.job(bad)
    # the board puts a failed job back for a second and third try, then keeps it failed with the reason
    assert j["status"] == "failed" and j["attempts"] == board.MAX_ATTEMPTS
    assert j["why"].startswith("exit 3: error:") and "blew up" in j["why"]       # the last error line, not "cleaning up"
    assert "blew up" in (env.project / "journal" / "runs" / f"link-graph-{bad}.log").read_text()
    assert env.job(ok)["status"] == "done"                 # one failure does not stop the others


def test_a_kind_with_no_command_fails_with_a_plain_message(env):
    board.add_page("/x", "post", "x", project=env.project)
    jid = board.add_job("brief", "/x", project=env.project)           # a manifest kind the kit has no default command for
    env.run(jobs=1, kinds=["brief"])
    j = env.job(jid)
    assert j["status"] == "failed" and "no command for job kind 'brief'" in j["why"] and "machine_jobs" in j["why"]


def test_a_command_needing_the_preview_without_one_fails_plainly(env):
    env.set_cfg(machine_jobs={"shots": "echo {url}"})
    jid = env.shots(1)[0]
    env.run(jobs=1, kinds=["shots"])
    assert env.job(jid)["status"] == "failed" and "preview_url" in env.job(jid)["why"]


def test_placeholders_are_filled_and_quoted(env):
    job = {"kind": "shots", "page": "/a b", "key": "a-b", "type": "post", "cluster": None}
    cfg = {"preview_url": "http://127.0.0.1:18432/", "trailing_slash": True}
    assert runner.render("echo {path} {key} {url} {cluster}", job, env.project, cfg) == "echo '/a b' a-b 'http://127.0.0.1:18432/a b/' ''"
    assert "ready" in runner.render(runner.DEFAULTS["ready"], {**job, "kind": "ready"}, env.project, {}).split("growth")[-1]
    with pytest.raises(runner.JobError, match="not a placeholder"):
        runner.render("echo {nope}", job, env.project, {})


def test_every_default_kind_is_a_manifest_kind():
    import kits
    assert set(runner.DEFAULTS) <= set(kits.jobs())


def test_a_job_page_is_read_in_the_boards_shape_and_in_the_older_dict_shape():
    assert runner.page_of({"page": "/a", "key": "k", "type": "post"}) == {"path": "/a", "key": "k", "type": "post", "cluster": ""}
    assert runner.page_of({"page": {"path": "/b", "key": "k", "type": "hub", "cluster": "c"}})["cluster"] == "c"
    assert runner.page_of({"page": None}) == {} and runner.page_of({}) == {}


def test_a_browser_pool_of_one_runs_browser_jobs_one_at_a_time(env):
    env.set_cfg(resources={"browser": 1})
    ids = env.shots(4)
    assert env.run(jobs=3, kinds=["shots"]) == 0
    assert [env.job(i)["status"] for i in ids] == ["done"] * 4
    assert max_overlap(spans(env.log)) == 1                # three workers, one browser: one at a time
    assert board.held("browser", project=env.project) == []      # every slot given back


def test_a_pool_of_two_lets_two_browser_jobs_overlap(env):
    env.set_cfg(resources={"browser": 2})
    env.shots(4)
    assert env.run(jobs=4, kinds=["shots"]) == 0
    assert max_overlap(spans(env.log)) == 2


def test_the_load_guard_waits_and_starts_nothing(env):
    env.set_cfg(runner_max_load=0.0)
    jid = env.add("inventory")[0]
    lines = []
    r = runner.Runner(env.project, jobs=2, once=True, poll=0.2, max_wait=1.0, out=lines.append)
    t0 = time.time()
    assert r.run() == 3
    assert 0.9 < time.time() - t0 < 10
    assert env.job(jid)["status"] == "queued" and not env.log.exists()
    assert any("busy" in l and "load" in l and "runner_max_load" in l for l in lines)
    assert sum("waiting:" in l for l in lines) == 1        # the reason is said once, not on every look


def test_the_memory_guard_waits_when_free_memory_is_low(env, monkeypatch):
    env.set_cfg(runner_min_free_pct=20)
    monkeypatch.setattr(runner, "free_memory_pct", lambda: 5)
    jid = env.add("inventory")[0]
    lines = []
    assert runner.Runner(env.project, once=True, poll=0.2, max_wait=0.6, out=lines.append).run() == 3
    assert env.job(jid)["status"] == "queued" and any("memory is low: 5% free" in l for l in lines)
    monkeypatch.setattr(runner, "free_memory_pct", lambda: None)       # cannot be read: the test is skipped, jobs run
    assert env.run(jobs=1) == 0 and env.job(jid)["status"] == "done"


def test_an_interrupt_ends_every_command_and_fails_the_jobs_back(env):
    env.set_cfg(machine_jobs={"inventory": job_cmd(60)})
    ids = env.add("inventory", 2)
    r = runner.Runner(env.project, jobs=2, once=True, poll=0.2, out=lambda t: None)
    result = []
    t = threading.Thread(target=lambda: result.append(r.run()))
    t.start()
    end = time.time() + 15
    while time.time() < end and len(r.procs) < 2:
        time.sleep(0.05)
    procs = list(r.procs.values())
    assert len(procs) == 2
    r.interrupt()
    t.join(30)
    assert not t.is_alive() and result == [130]
    assert all(p.poll() is not None for p in procs)        # both commands are gone
    for i in ids:
        j = env.job(i)
        assert j["status"] == "queued" and "interrupted" in j["why"] and j["holder"] is None     # back in the queue, free to claim


def test_kinds_filter_only_takes_those_kinds(env):
    a = env.add("inventory")[0]
    b = env.add("link-graph")[0]
    env.set_cfg(machine_jobs={"inventory": job_cmd(0.1), "link-graph": job_cmd(0.1)})
    assert env.run(jobs=1, kinds=["link-graph"]) == 0
    assert env.job(a)["status"] == "queued" and env.job(b)["status"] == "done"


def test_command_line_runs_once(env, capsys):
    env.add("inventory")
    assert runner.main(["--once", "--jobs", "1", "--poll", "0.2"]) == 0
    out = capsys.readouterr().out
    assert "DONE   inventory" in out and "Runner finished: 1 done, 0 failed." in out
