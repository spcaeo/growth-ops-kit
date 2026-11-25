"""A gate run on the project's preview address reads the worktree that serves it (growth.json preview_repo), not the
main checkout (24 Nov 2026: the gate said "branch main" and found no shared components while the page came from the
worktree)."""
import json
import os
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "kit" / "tools"


def ask(project, url):
    code = f"import gate; r = gate.preview_repo_for({url!r}); print(r or '')"
    env = {**os.environ, "GROWTH_PROJECT": str(project), "PYTHONPATH": str(TOOLS)}
    return subprocess.run([sys.executable, "-c", code], cwd=project, env=env, capture_output=True, text=True).stdout.strip()


def test_preview_url_uses_preview_repo(tmp_path):
    p = tmp_path / "proj"
    p.mkdir()
    (p / "growth.json").write_text(json.dumps({"name": "T", "site_url": "https://t.example", "site_repo": str(tmp_path / "main"),
                                               "preview_repo": str(tmp_path / "wt"), "preview_url": "http://localhost:4321"}))
    wt = str((tmp_path / "wt").resolve())
    assert ask(p, "http://127.0.0.1:4321/") == wt
    assert ask(p, "http://localhost:4321/pricing/") == wt
    assert ask(p, "http://localhost:3801/") == ""          # another server: the main default stays
