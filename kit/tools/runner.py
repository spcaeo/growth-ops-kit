#!/usr/bin/env python3
"""The machine runner (kit 3.0, micro kit "evidence"): takes the board's machine jobs and runs them side by side.

  growth run [--jobs N] [--once] [--kinds k1,k2] [--name runner] [--poll S] [--max-wait S]

It claims jobs whose runner is "machine" (board.claim as agent runner-1 ... runner-N), runs up to N side by side, and
for each job: holds the job's resource (a browser slot, say) while it runs, sends a heartbeat every 60 s, writes the whole
output to journal/runs/<kind>-<job id>.log, and ends the job: done (proof "exit 0, log journal/runs/...") on exit 0, else
failed with the last error line. A load guard comes first: when the 1-minute load average is above runner_max_load, or free
memory is under runner_min_free_pct, it prints why and waits instead of starting a job. Ctrl-C (or SIGTERM) stops every
running command and fails its job back to the queue. --once: stop when nothing is claimable and nothing is running.
Run two runners in one project only with different --name values (the name is the job holder).

The command for each job kind comes from growth.json "machine_jobs", a map kind -> command, for example
  {"shots": "{venv_python} tools/page_evidence.py {path} --key {key} --url {preview} --commit {commit} --journal"}
placeholders: {path} {key} {type} {cluster} {url} {preview} {repo} {commit} {growth} {venv_python} {project}
({url}: the page on the preview address, {preview}: the preview address itself). The command runs in the project folder.
The kit knows its own kinds (gate, ready, link-graph, inventory, fingerprint, tech-seo); a kind with no command fails with
a plain message.

growth.json keys read: machine_jobs, preview_url, preview_repo, site_repo, trailing_slash, runner_max_load (CPU count x 2),
runner_min_free_pct (20; 0 turns the memory test off), runner_beat_s (60), runner_job_timeout_s (1800).
"""
from __future__ import annotations

import argparse
import inspect
import os
import re
import shlex
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402

KIT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULTS = {
    "gate": "{growth} gate page {path} --url {url} --type {type} --key {key}",
    "ready": "{growth} ready {path} --type {type} --key {key}",
    "link-graph": "{growth} link_graph crawl --base {preview}",
    "inventory": "{growth} inventory --base {preview}",
    "fingerprint": "{growth} fingerprint record {path} --key {key} --url {url}",
    "tech-seo": "{growth} tech_seo_check {url}",
}
FIELDS = ("path", "key", "type", "cluster", "url", "preview", "repo", "commit", "growth", "venv_python", "project")
NEEDS_PREVIEW = ("url", "preview")


class JobError(Exception):
    """A job that cannot start; the message goes to the log and to the board as the reason."""


# -- the command of a job ------------------------------------------------------------------------------------------------
def venv_python() -> str:
    """The kit's own Python (as the `growth` dispatcher picks it): $GROWTH_VENV, else ~/.growth-ops-kit/venv, else this one."""
    venv = Path(os.environ.get("GROWTH_VENV") or Path.home() / ".growth-ops-kit" / "venv")
    for cand in (venv / "bin" / "python", venv / "Scripts" / "python.exe"):
        if cand.is_file():
            return str(cand)
    return sys.executable


def fetch_path(path: str, cfg: dict) -> str:
    """The address form the site wants (same rule as ready.fetch_path; copied so this module never loads a project)."""
    ts = cfg.get("trailing_slash")
    if ts in (True, "slash", "1", 1) and path != "/" and "." not in path.rsplit("/", 1)[-1]:
        return path + "/"
    return path


def command_for(kind: str, cfg: dict) -> str:
    jobs = cfg.get("machine_jobs") or {}
    for k in (kind, kind.replace("_", "-"), kind.replace("-", "_")):
        if jobs.get(k):
            return jobs[k]
        if k in DEFAULTS:
            return DEFAULTS[k]
    raise JobError(f"no command for job kind '{kind}': add it to growth.json machine_jobs "
                   f"(for example \"{kind}\": \"{{venv_python}} tools/{kind}.py {{path}}\"). The kit itself knows: {', '.join(sorted(DEFAULTS))}.")


def render(template: str, job: dict, project: Path, cfg: dict) -> str:
    """The shell command for a job: every placeholder filled with a shell-quoted value."""
    import string
    used = {f for _, f, _, _ in string.Formatter().parse(template) if f}
    unknown = sorted(used - set(FIELDS))
    if unknown:
        raise JobError(f"the command for '{job['kind']}' uses {{{unknown[0]}}}, which is not a placeholder. Known: "
                       + " ".join("{" + f + "}" for f in FIELDS))
    page = job.get("page") or {}
    preview = (cfg.get("preview_url") or "").rstrip("/")
    if used & set(NEEDS_PREVIEW) and not preview:
        raise JobError(f"the command for '{job['kind']}' needs the preview address but growth.json has no preview_url.")
    given = cfg.get("preview_repo") or cfg.get("site_repo")
    repo = config.resolve_in(project, given) if given else None
    commit = ""
    if "commit" in used:
        r = subprocess.run(["git", "-C", str(repo), "rev-parse", "--short", "HEAD"], capture_output=True, text=True) if repo else None
        commit = r.stdout.strip() if r is not None and r.returncode == 0 else "no-repo"
    path = page.get("path") or ""
    q = shlex.quote
    py = q(venv_python())
    vals = {"path": q(path), "key": q(page.get("key") or ""), "type": q(page.get("type") or ""), "cluster": q(page.get("cluster") or ""),
            "url": q(preview + fetch_path(path, cfg)) if preview else "", "preview": q(preview), "repo": q(str(repo or "")),
            "commit": q(commit), "growth": f"{py} {q(str(KIT_ROOT / 'growth'))}", "venv_python": py, "project": q(str(project))}
    if (used & {"path", "key", "type"}) and not page:
        raise JobError(f"the command for '{job['kind']}' needs a page (path, key, type) but the job has none.")
    return template.format(**vals)


def last_error(text: str, code: int) -> str:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    pat = re.compile(r"error|fail|fatal|exception|traceback|cannot|refus|not ready|no such", re.I)
    pick = next((l for l in reversed(lines) if pat.search(l)), lines[-1] if lines else "")
    return f"exit {code}: {pick[:200]}" if pick else f"exit {code}, no output"


# -- the load guard ------------------------------------------------------------------------------------------------------
def free_memory_pct():
    """Free memory in percent: macOS memory_pressure, Linux /proc/meminfo; None when neither can be read."""
    try:
        out = subprocess.run(["memory_pressure"], capture_output=True, text=True, timeout=10).stdout
        m = re.search(r"free percentage:\s*(\d+)%", out)
        if m:
            return int(m.group(1))
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        info = {l.split(":")[0]: int(l.split()[1]) for l in Path("/proc/meminfo").read_text().splitlines() if ":" in l}
        return round(100 * info["MemAvailable"] / info["MemTotal"])
    except (OSError, KeyError, ValueError, IndexError):
        return None


def load_problem(cfg: dict) -> str:
    """Why no new job should start now, or "" when the machine has room."""
    limit = cfg.get("runner_max_load")
    limit = float(limit) if limit is not None else float((os.cpu_count() or 4) * 2)
    try:
        load = os.getloadavg()[0]
    except (OSError, AttributeError):
        load = None
    if load is not None and load > limit:
        return f"the machine is busy: load {load:.1f} is above the limit {limit:g} (growth.json runner_max_load)"
    need = cfg.get("runner_min_free_pct")
    need = 20 if need is None else float(need)
    if need > 0:
        free = free_memory_pct()
        if free is not None and free < need:
            return f"memory is low: {free}% free, the limit is {need:g}% (growth.json runner_min_free_pct)"
    return ""


def _on_term(*_):
    raise KeyboardInterrupt()


# -- the runner ----------------------------------------------------------------------------------------------------------
class Runner:
    def __init__(self, project=None, jobs=3, once=False, kinds=None, name="runner", poll=10.0, max_wait=None, out=print):
        self.project = Path(project).resolve() if project else config.require_project()
        self.cfg = config.load_cfg(self.project)
        self.jobs, self.once, self.kinds, self.name = max(1, jobs), once, kinds or None, name
        self.poll, self.max_wait, self.out = poll, max_wait, out
        self.cv = threading.Condition()
        self.stopping = threading.Event()
        self.running: dict[int, threading.Thread] = {}      # worker number -> thread
        self.procs: dict[int, subprocess.Popen] = {}        # job id -> its command
        self.done_n = self.failed_n = 0
        self.board = None
        self.beat_s = float(self.cfg.get("runner_beat_s") or 60)
        self.timeout_s = float(self.cfg.get("runner_job_timeout_s") or 1800)

    def say(self, text):
        self.out(text)
        sys.stdout.flush()

    # -- control
    def interrupt(self):
        """Stop everything: every running command is terminated and its job fails back (the worker threads do that)."""
        self.stopping.set()
        for p in list(self.procs.values()):
            self._kill(p)
        with self.cv:
            self.cv.notify_all()

    @staticmethod
    def _kill(proc, grace=5.0):
        if proc.poll() is not None:
            return
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            return
        try:
            proc.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass

    # -- the main loop
    def run(self) -> int:
        import board
        self.board = board
        self.claim_kinds = bool(self.kinds) and "kinds" in inspect.signature(board.claim).parameters
        if self.kinds and not self.claim_kinds:
            self.say("growth run: --kinds needs a board that can pick jobs by kind; this board cannot yet. Run without --kinds.")
            return 2
        (self.project / "journal" / "runs").mkdir(parents=True, exist_ok=True)
        if threading.current_thread() is threading.main_thread():
            signal.signal(signal.SIGTERM, _on_term)
        guard_since, last_why, said_at = None, "", 0.0
        try:
            while not self.stopping.is_set():
                with self.cv:
                    for n in [n for n, t in self.running.items() if not t.is_alive()]:
                        del self.running[n]
                job, why = None, ""
                if len(self.running) < self.jobs:
                    why = load_problem(self.cfg)
                    if why:
                        guard_since = guard_since or time.time()
                        if why.split(":")[0] != last_why or time.time() - said_at > 60:      # the numbers move; say it once a minute
                            self.say(f"waiting: {why}")
                            last_why, said_at = why.split(":")[0], time.time()
                    else:
                        guard_since, last_why = None, ""
                        n = next(i for i in range(1, self.jobs + 1) if i not in self.running)
                        job = self._claim(f"{self.name}-{n}")
                        if job:
                            t = threading.Thread(target=self._work, args=(n, job), daemon=True)
                            with self.cv:
                                self.running[n] = t
                            t.start()
                            continue
                if not self.running:
                    if not why and self.once:
                        break
                    if why and self.max_wait is not None and time.time() - guard_since > self.max_wait:
                        self.say(f"growth run: stopping, waited {self.max_wait:g} s and the machine was still busy. Nothing was started.")
                        return 3
                with self.cv:
                    self.cv.wait(timeout=(self.poll if not self.running else min(self.poll, 0.5)))
        except KeyboardInterrupt:
            self.say("stopping: Ctrl-C. Running commands are being ended and their jobs go back to the queue.")
            self.interrupt()
        finally:
            for t in list(self.running.values()):
                t.join(timeout=30)
        if self.stopping.is_set():
            return 130
        self.say(f"Runner finished: {self.done_n} done, {self.failed_n} failed.")
        return 1 if self.failed_n else 0

    def _claim(self, agent):
        kw = {"kit": None, "runner": "machine", "project": self.project}
        if self.claim_kinds:
            kw["kinds"] = list(self.kinds)
        return self.board.claim(agent, **kw)

    # -- one job
    def _work(self, n, job):
        agent, jid, kind = f"{self.name}-{n}", job["id"], job["kind"]
        stop_beat = threading.Event()
        lost = threading.Event()
        label = f"{kind} {((job.get('page') or {}).get('path') or '')}".strip()
        log = self.project / "journal" / "runs" / f"{re.sub(r'[^A-Za-z0-9._-]+', '-', kind)}-{jid}.log"
        rel = log.relative_to(self.project)
        res = job.get("resource")
        t0 = time.time()

        def beater():
            while not stop_beat.wait(self.beat_s):
                try:
                    if not self.board.beat(jid, agent, project=self.project):
                        lost.set()
                        proc = self.procs.get(jid)
                        if proc is not None:
                            self._kill(proc)
                        return
                except Exception:  # noqa: BLE001  a missed heartbeat must not kill the job; the lease has room for a few
                    pass

        threading.Thread(target=beater, daemon=True).start()
        try:
            try:
                cmd = render(command_for(kind, self.cfg), job, self.project, self.cfg)
                if res and res != "google":
                    self._take(res, agent, jid, t0)
                self.say(f"START  {label}  (job {jid}, {agent})")
                code, text = self._exec(cmd, jid, log)
            except JobError as e:
                log.write_text(f"{e}\n")
                code, text = None, str(e)
            if lost.is_set():
                self.say(f"LOST   {label}: the lease ran out, so another runner may have it; this run was stopped")
                return
            if self.stopping.is_set():
                self.board.fail(jid, agent, "stopped: the runner was interrupted", project=self.project)
                self.say(f"BACK   {label}: stopped, back in the queue")
            elif code == 0:
                self.board.done(jid, agent, f"exit 0, log {rel}", project=self.project)
                with self.cv:
                    self.done_n += 1
                self.say(f"DONE   {label}  {time.time() - t0:.0f}s")
            else:
                why = text if code is None else last_error(text, code)
                self.board.fail(jid, agent, why, project=self.project)
                with self.cv:
                    self.failed_n += 1
                self.say(f"FAILED {label}: {why}")
        except Exception as e:  # noqa: BLE001  the board or the disk failed: say so and fail the job
            self.failed_n += 1
            self.say(f"FAILED {label}: {type(e).__name__}: {e}")
            try:
                self.board.fail(jid, agent, f"runner error: {type(e).__name__}: {e}"[:200], project=self.project)
            except Exception:  # noqa: BLE001
                pass
        finally:
            stop_beat.set()
            if res and res != "google":
                try:
                    self.board.release(res, agent, project=self.project)
                except Exception:  # noqa: BLE001
                    pass
            with self.cv:
                self.cv.notify_all()

    def _take(self, res, agent, jid, t0) -> bool:
        """Hold the job's resource (a browser slot) while it runs; wait for a free slot, the heartbeat keeps the lease."""
        if res == "google":
            return False
        while not self.stopping.is_set():
            if self.board.acquire(res, agent, project=self.project):
                return True
            if time.time() - t0 > self.timeout_s:
                raise JobError(f"waited {self.timeout_s:g} s for a free '{res}' and none came (growth.json runner_job_timeout_s)")
            time.sleep(min(self.poll, 0.5))
        return False

    def _exec(self, cmd, jid, log):
        with open(log, "wb") as fh:
            fh.write(f"$ {cmd}\n".encode())
            fh.flush()
            proc = subprocess.Popen(cmd, shell=True, cwd=self.project, stdout=fh, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                    start_new_session=True, env={**os.environ, "GROWTH_PROJECT": str(self.project)})
            self.procs[jid] = proc
            try:
                if self.stopping.is_set():
                    self._kill(proc)
                try:
                    code = proc.wait(timeout=self.timeout_s)
                except subprocess.TimeoutExpired:
                    self._kill(proc)
                    fh.write(f"\nerror: timed out after {self.timeout_s:g} s and was stopped\n".encode())
                    code = 124
            finally:
                self.procs.pop(jid, None)
        return code, log.read_text(errors="replace")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="growth run", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--jobs", type=int, default=3, help="jobs side by side (default 3)")
    ap.add_argument("--once", action="store_true", help="stop when nothing is claimable and nothing is running")
    ap.add_argument("--kinds", help="only these job kinds (comma list)")
    ap.add_argument("--name", default="runner", help="holder name prefix (default runner; jobs are runner-1, runner-2 ...)")
    ap.add_argument("--poll", type=float, default=10.0, help="seconds between looks at the board when idle or waiting (default 10)")
    ap.add_argument("--max-wait", type=float, help="give up after this many seconds of waiting for the machine to have room")
    a = ap.parse_args(argv)
    kinds = [k.strip() for k in a.kinds.split(",") if k.strip()] if a.kinds else None
    return Runner(None, a.jobs, a.once, kinds, a.name, a.poll, a.max_wait).run()


if __name__ == "__main__":
    sys.exit(main())
