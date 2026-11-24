"""Helpers for the work-board tests: a scratch project with its own growth.json settings, and the kit's tools run as a person would."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "kit" / "tools"
DEMO = ROOT / "examples" / "demo-site" / "project"
# ports and the like far from anything a real lane uses on this machine
SAFE_PORTS = [28440, 28459]


def make_project(tmp_path, **cfg):
    """A copy of the demo project folder whose growth.json carries the extra settings (resources, pacers)."""
    dest = tmp_path / "project"
    shutil.copytree(DEMO, dest)
    f = dest / "growth.json"
    data = json.loads(f.read_text())
    data.setdefault("resources", {})["port_range"] = SAFE_PORTS
    for k, v in cfg.items():
        data[k] = {**data.get(k, {}), **v} if isinstance(v, dict) and isinstance(data.get(k), dict) else v
    f.write_text(json.dumps(data, indent=2))
    return dest


def growth(project, *args, agent=None, check=False, timeout=120):
    """`growth <args>` as a person types it (through the dispatcher), in the project folder."""
    env = {k: v for k, v in os.environ.items() if k not in ("GROWTH_KIT", "GROWTH_VENV", "GROWTH_AGENT")}
    env.update(GROWTH_PROJECT=str(project), PYTHONDONTWRITEBYTECODE="1")
    if agent:
        env["GROWTH_AGENT"] = agent
    r = subprocess.run([sys.executable, str(ROOT / "growth"), *args], capture_output=True, text=True, cwd=str(project), env=env, timeout=timeout)
    if check:
        assert r.returncode == 0, (args, r.stdout, r.stderr)
    return r


def proof_file(project, name="proof.md"):
    """A file inside the project that counts as proof (the name of it is the proof text)."""
    f = Path(project) / "research" / name
    f.parent.mkdir(exist_ok=True)
    f.write_text("checked\n")
    return f"research/{name}"
