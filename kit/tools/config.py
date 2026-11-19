"""Project discovery and growth.json: the one place every tool finds its project.

The kit is a library; a project is a folder of data. The project root is `$GROWTH_PROJECT`, else the nearest folder at
or above the current directory that holds `growth.json`. Every path to project data (growth.json, BRAND.md,
OWNER-RULES.md, SETUP.md, docs/, journal/, research/, inventory/, archive/, page-tracker/) resolves from the project
root. Kit files (rules/registry.json, hooks, templates, the book) resolve from the kit. A project run never writes
inside the kit.

Importing this module never fails. The project facts (PROJECT, CFG, SITE_URL, ...) are loaded the first time a tool
reads one of them; if there is no project, that read stops with one clear line.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

KIT_DIR = Path(__file__).resolve().parent.parent          # growth-ops-kit/kit
KIT_ROOT = KIT_DIR.parent                                 # growth-ops-kit
BOOK = KIT_ROOT / "book"
TEMPLATES = KIT_ROOT / "templates" / "project"
REGISTRY = KIT_DIR / "rules" / "registry.json"
RULEBOOK = BOOK / "03-page-rulebook.md"


class NoProject(SystemExit):
    """Raised (as a clean exit with a message) when no project folder can be found."""


def find_project(start: Path | None = None, env: dict | None = None) -> Path | None:
    """$GROWTH_PROJECT, else the nearest folder at or above `start` (default: cwd) holding growth.json. None if neither."""
    env = os.environ if env is None else env
    given = env.get("GROWTH_PROJECT", "").strip()
    if given:
        p = Path(given).expanduser().resolve()
        return p if (p / "growth.json").is_file() else None
    here = Path(start or Path.cwd()).resolve()
    for d in (here, *here.parents):
        if (d / "growth.json").is_file():
            return d
    return None


def require_project() -> Path:
    p = find_project()
    if p is None:
        raise NoProject("No project found: run from a folder that holds growth.json (or inside one), or set "
                        "GROWTH_PROJECT=<project folder>. New project: growth new-project <folder> --site <url>")
    return p


def load_cfg(project: Path) -> dict:
    try:
        return json.loads((project / "growth.json").read_text())
    except ValueError as e:
        raise SystemExit(f"{project / 'growth.json'} is not valid JSON: {e}")


def resolve_in(project: Path, value: str) -> Path:
    """A path from growth.json: ~ expands to the home folder; a relative path is relative to the project root."""
    p = Path(value).expanduser()
    return p.resolve() if p.is_absolute() else (project / p).resolve()


def parse_keys(text: str) -> dict:
    return dict(l.split("=", 1) for l in text.splitlines() if "=" in l and not l.lstrip().startswith("#"))


def project_dirs(project: Path) -> dict:
    """The named places inside a project folder."""
    return {name: project / name for name in ("docs", "journal", "research", "inventory", "archive", "page-tracker")}


_LAZY = ("PROJECT", "CFG", "DOCS", "SITE_URL", "HOST", "TZ", "SITE_REPO", "KEYS", "UA")


def __getattr__(name):  # PEP 562: loaded on first read, so `import config` is always safe
    if name not in _LAZY:
        raise AttributeError(name)
    from zoneinfo import ZoneInfo
    project = require_project()
    os.environ["GROWTH_PROJECT"] = str(project)         # tools this one starts (the gate runs several) find the same project
    cfg = load_cfg(project)
    g = globals()
    g["PROJECT"] = project
    g["CFG"] = cfg
    g["DOCS"] = project / "docs"
    g["SITE_URL"] = cfg.get("site_url", "").rstrip("/")
    g["HOST"] = g["SITE_URL"].split("://", 1)[-1]
    g["TZ"] = ZoneInfo(cfg.get("timezone", "UTC"))
    g["SITE_REPO"] = resolve_in(project, cfg["site_repo"]) if cfg.get("site_repo") else project / "site"
    g["KEYS"] = resolve_in(project, cfg["keys_file"]) if cfg.get("keys_file") else None
    g["UA"] = {"User-Agent": f"Mozilla/5.0 ({(cfg.get('name') or 'growth').lower().replace(' ', '-')}-growth-ops)"}
    return g[name]


def keys():
    """The connector keys, read from the keys file named in growth.json (outside git). {} when there is none.
    Never print the result."""
    k = globals().get("KEYS") if "KEYS" in globals() else __getattr__("KEYS")
    if not k or not Path(k).is_file():
        return {}
    return parse_keys(Path(k).read_text())


skald_env = keys  # the older name


def connector_on(name: str) -> bool:
    """True when growth.json switches a connector on (connectors.<name>.on)."""
    c = (__getattr__("CFG").get("connectors") or {}).get(name)
    return isinstance(c, dict) and bool(c.get("on"))


def note_missing_key(name: str, *needed: str) -> bool:
    """Print one clear line and return True when a connector is on but its keys are absent. Never raises."""
    have = keys()
    miss = [n for n in needed if not have.get(n)]
    if miss:
        print(f"note: connector '{name}' is on but the keys file has no {', '.join(miss)} "
              f"(growth.json keys_file); skipping it.", file=sys.stderr)
    return bool(miss)


def sibling_tools_path():
    """Put kit/tools on sys.path so `import config` and `from gatelib import ...` work from any tool."""
    t = str(Path(__file__).resolve().parent)
    if t not in sys.path:
        sys.path.insert(0, t)
