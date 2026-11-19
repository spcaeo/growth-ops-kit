#!/usr/bin/env python3
"""Make a project folder from the kit's template (templates/project/): never by copying another project.

  growth new-project <folder> --site https://example.com [--name "Example"] [--stack static|nextjs] [--force]

Creates <folder> with growth.json (site URL and name filled in), BRAND.md, OWNER-RULES.md, SETUP.md, CLAUDE.md, docs/
(steps log, tasks.json), .claude/skills/onboard (the /onboard skill) and .claude/settings.json (the Stop hook that makes the
agent follow the rules), and the empty working folders (journal, research, inventory, archive, page-tracker) with a
.gitignore that keeps the tracker's data, keys and scratch files out of git. Then it prints what to do next.
It refuses to write into a folder that already holds files, unless --force (which never overwrites a file that exists).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import KIT_DIR, TEMPLATES  # noqa: E402

WORK_DIRS = ("journal", "research", "inventory", "archive", "page-tracker")
GITIGNORE = """# Growth project: data the tools write, keys and scratch files stay out of git.
.env
.env.*
!.env.example
*.db
*.sqlite
page-tracker/data.json
page-tracker/insights*.json
page-tracker/insights.md
page-tracker/cluster-*.json
page-tracker/diffs/
page-tracker/report.html
page-tracker/sitemap-cache.json
page-tracker/*.log
archive/
research/raw/
__pycache__/
.DS_Store
"""


def port_is_free(port: int) -> bool:
    import socket
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) != 0


def free_port(start: int, tries: int = 100) -> int:
    """`start` when nothing listens there, else the next free port above it."""
    return next((p for p in range(start, start + tries) if port_is_free(p)), start)


def name_from(site: str) -> str:
    host = urlsplit(site).netloc.lower().removeprefix("www.")
    return (host.split(".")[0] or "site").replace("-", " ").title()


def fill(text: str, values: dict) -> str:
    for k, v in values.items():
        text = text.replace("{{" + k + "}}", v)
    return text


def agent_files(folder: Path, name: str, site: str, kit_root: Path) -> list[Path]:
    """The agent's own files inside the project: the onboard skill (filled with what the kit already knows) and the Stop hook
    in .claude/settings.json. Never overwrites a skill that exists; adds the hook to an existing settings file without
    touching its other settings. Returns the files written."""
    made = []
    skill_src = KIT_DIR / "skills" / "onboard" / "SKILL.md"
    skill = folder / ".claude" / "skills" / "onboard" / "SKILL.md"
    if skill_src.is_file() and not skill.exists():
        skill.parent.mkdir(parents=True, exist_ok=True)
        text = skill_src.read_text().replace("](../../../book/", f"]({kit_root}/book/")
        text = text.replace("# Onboard (re-runnable)", f"# Onboard (re-runnable)\n\nThis project: **{name}** ({site}). The kit is at `{kit_root}`; "
                            "the book is in its `book/` folder.", 1)
        skill.write_text(text)
        made.append(skill)
    settings = folder / ".claude" / "settings.json"
    command = f'GROWTH_PROJECT="$CLAUDE_PROJECT_DIR" bash "${{GROWTH_KIT:-{kit_root}}}/kit/hooks/stop_hook.sh"'
    try:
        cfg = json.loads(settings.read_text()) if settings.exists() else {}
    except ValueError:
        raise SystemExit(f"{settings} is not valid JSON; fix it, then run this again")
    stop = cfg.setdefault("hooks", {}).setdefault("Stop", [])
    changed = False
    if "stop_hook.sh" not in json.dumps(stop):
        stop.append({"hooks": [{"type": "command", "command": command,
                                "statusMessage": "Checking every owner message is logged and every rule has its check"}]})
        changed = True
    if "statusLine" not in cfg:   # the owner watches the open task tick off at the bottom of the window (never replaced)
        cfg["statusLine"] = {"type": "command", "padding": 0,
                             "command": f'GROWTH_PROJECT="$CLAUDE_PROJECT_DIR" python3 "${{GROWTH_KIT:-{kit_root}}}/kit/tools/statusline.py"'}
        changed = True
    if changed:
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text(json.dumps(cfg, indent=2) + "\n")
        made.append(settings)
    return made


def make(folder: Path, site: str, name: str = "", stack: str = "static", force: bool = False, template: Path = TEMPLATES):
    site = site.rstrip("/")
    if not re.match(r"^https?://[^/\s]+\.[^/\s]+$", site) and not re.match(r"^https?://localhost(:\d+)?$", site):
        raise SystemExit(f"--site must look like https://example.com (got '{site}')")
    if not template.is_dir():
        raise SystemExit(f"template folder missing: {template}")
    folder = folder.expanduser().resolve()
    if folder.exists() and any(folder.iterdir()) and not force:
        raise SystemExit(f"{folder} is not empty; pick a new folder (or --force to add what is missing).")
    values = {"name": name or name_from(site), "site_url": site, "kit_root": str(KIT_DIR.parent)}
    made = []
    for src in sorted(template.rglob("*")):
        if not src.is_file():
            continue
        dest = folder / src.relative_to(template)
        if dest.exists():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            dest.write_text(fill(src.read_text(), values))
        except UnicodeDecodeError:
            dest.write_bytes(src.read_bytes())
        made.append(dest)
    cfg_file = folder / "growth.json"
    cfg = json.loads(cfg_file.read_text())
    cfg["stack"] = stack
    if cfg_file in made and isinstance(cfg.get("tracker_port"), int):     # a new file only: never move a port the owner chose
        cfg["tracker_port"] = free_port(cfg["tracker_port"])
    cfg_file.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")
    for d in WORK_DIRS:
        (folder / d).mkdir(parents=True, exist_ok=True)
        keep = folder / d / ".gitkeep"
        if not keep.exists():
            keep.write_text("")
    made += agent_files(folder, values["name"], site, KIT_DIR.parent)
    entries = folder / "journal" / "entries.jsonl"
    if not entries.exists():
        entries.write_text("")                       # the page journal starts empty
        made.append(entries)
    gi = folder / ".gitignore"
    if not gi.exists():
        gi.write_text(GITIGNORE)
    return folder, made


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder")
    ap.add_argument("--site", required=True, help="the site's address, e.g. https://example.com")
    ap.add_argument("--name", default="", help="the business's short name (default: from the address)")
    ap.add_argument("--stack", choices=["static", "nextjs"], default="static")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    folder, made = make(Path(a.folder), a.site, a.name, a.stack, a.force)
    import os
    import subprocess
    # the owner's journal page, built once so `growth doctor` step A9 starts green
    subprocess.run([sys.executable, str(KIT_DIR / "tools" / "owner_journal.py"), "--no-open"], cwd=folder, capture_output=True,
                   env={**os.environ, "GROWTH_PROJECT": str(folder), "PYTHONDONTWRITEBYTECODE": "1"})
    print(f"Project made: {folder} ({len(made)} files from templates/project)")
    print(f"Next: cd {folder} && growth doctor   (then fill in growth.json and BRAND.md; the onboard skill walks you through it)")
    print("Agent files: .claude/skills/onboard (type /onboard in Claude Code, started in this folder) and .claude/settings.json (the Stop hook, and the status bar that shows the open task's progress).")
    print(f"Put the kit's command on your PATH if `growth` is not found: export PATH=\"{KIT_DIR.parent}:$PATH\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
