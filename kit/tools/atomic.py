"""Safe writes for files that several agents change at the same time (journal, tasks, checkpoints, state files).

Two parts, use both:
  - a lock: `with locked(path):` lets one process at a time through for that file (fcntl.flock on `<file>.lock`;
    it waits up to `timeout` seconds, then stops with a plain message instead of hanging for ever);
  - an atomic write: the new content goes to a temp file with its own unique name next to the target and then
    replaces it in one step (os.replace), so a reader never sees half a file and two writers never share a temp name.

Load, change and save belong inside ONE lock, or a second writer saves over the first one's change:

    from atomic import update_json
    update_json(DATA, lambda db: db["tasks"].append(task), default={"tasks": []})   # load + change + save under the lock

Helpers: locked(path), write_text(path, text), write_json(path, obj), update_json(path, change, default),
append_line(path, line), read_json(path, default).
"""
from __future__ import annotations

import contextlib
import fcntl
import json
import os
import tempfile
import time
from pathlib import Path


class LockTimeout(RuntimeError):
    pass


@contextlib.contextmanager
def locked(path, timeout: float = 30.0):
    """Hold the lock for `path` (one lock file per target: `<name>.lock` beside it). Not reentrant: take it once."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(path.name + ".lock")
    fd = os.open(lock, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() > deadline:
                    raise LockTimeout(f"{path.name} is being written by another process (waited {timeout:.0f} s); try again")
                time.sleep(0.02)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def write_text(path, text: str) -> None:
    """Replace the file with `text` in one step. The temp file name is unique, so parallel writers never collide."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def read_json(path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, obj, indent: int | None = 2) -> None:
    write_text(path, json.dumps(obj, indent=indent, ensure_ascii=False) + "\n")


def update_json(path, change, default=None, indent: int | None = 2):
    """Under the lock: read the file (or `default`), call change(data) (it may change in place or return a new value),
    write the result atomically, return it."""
    with locked(path):
        data = read_json(path, default)
        if data is None and default is None:
            raise FileNotFoundError(str(path))
        new = change(data)
        if new is None:
            new = data
        write_json(path, new, indent)
        return new


def append_line(path, line: str) -> None:
    """Append one line under the lock (one write call, so lines never interleave)."""
    path = Path(path)
    with locked(path):
        with path.open("a", encoding="utf-8") as f:
            f.write(line.rstrip("\n") + "\n")
            f.flush()
            os.fsync(f.fileno())
