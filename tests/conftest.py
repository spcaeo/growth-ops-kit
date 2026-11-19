"""Shared test setup: the kit's tools on sys.path, and no test ever sees a real project or real keys."""
import os
import sys
from pathlib import Path

import pytest

sys.dont_write_bytecode = True                    # nothing is written inside the kit while the tests run
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"       # ... and neither do the tools the tests start

ROOT = Path(__file__).resolve().parent.parent
KIT = ROOT / "kit"
sys.path.insert(0, str(KIT / "tools"))
sys.path.insert(0, str(KIT))
import importlib.util
_spec = importlib.util.spec_from_file_location("hooks_text", KIT / "hooks" / "install_hooks.py")
sys.modules["hooks_text"] = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sys.modules["hooks_text"])
DEMO = ROOT / "examples" / "demo-site"
os.environ.pop("GROWTH_PROJECT", None)
for _v in [k for k in os.environ if k.startswith("GIT_")]:    # a test run from a git hook must not touch the hook's repository or author
    os.environ.pop(_v, None)


@pytest.fixture
def root():
    return ROOT


@pytest.fixture
def demo_project(tmp_path):
    """A scratch copy of the demo project folder (so a test can never write into the repo)."""
    import shutil
    dest = tmp_path / "project"
    shutil.copytree(DEMO / "project", dest)
    return dest


@pytest.fixture
def clean_env(monkeypatch):
    monkeypatch.delenv("GROWTH_PROJECT", raising=False)
    return monkeypatch
