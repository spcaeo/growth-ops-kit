#!/usr/bin/env python3
"""The agent harness of a project, installed and checked as one set (library; `growth wizard --repair` installs what is missing,
doctor A13 lists each piece).

Pieces: the Stop hook (with a status message), the workflow guard (when this kit has one), the status line (bars), the
permissions block (allow the kit's own commands, deny pushes, deploys and a live crawl), the skills, the project CLAUDE.md
"before you act" lines, and the git hooks. Installing never overwrites what the owner set: a missing entry is added, an
existing one is left alone, a setting of the owner's own is never touched. Nothing here changes a global setting.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wizard_state  # noqa: E402

KIT_DIR = Path(__file__).resolve().parent.parent
KIT_ROOT = KIT_DIR.parent
CLAUDE_START, CLAUDE_END = "<!-- growth-harness:start -->", "<!-- growth-harness:end -->"
CLAUDE_BLOCK = f"""{CLAUDE_START}
Before you act (written by `growth wizard`; edit outside these markers):
- The workflow is the rule: every job is a task. Open it with `growth tasks add`, copy the playbook's steps into it, tick each
  step with its proof. Setup itself is task "Project setup".
- Re-read the job's checkpoints at the start of each stage, not only at the start of the job.
- Show progress: the status bar at the bottom of the window follows the open task; say which step you are on, and never go
  silent for long.
- No research step starts until the research browser is connected and Google is set to the target country (`growth doctor` A14).
{CLAUDE_END}
"""
STOP_MESSAGE = "Checking every owner message is logged and every rule has its check"
READ_ONLY_GIT = ["status", "log", "diff", "show", "branch", "worktree list", "rev-parse", "remote -v"]
DENY_ALWAYS = ["Bash(git push*)", "Bash(git merge* main*)", "Bash(git merge main*)", "Bash(rm -rf /*)", "Bash(rm -rf ~*)",
               "Bash(rm -rf ..*)", "Bash(rm -rf $HOME*)"]


def run_growth() -> str:
    return 'GROWTH_PROJECT="$CLAUDE_PROJECT_DIR" "$(command -v growth || echo "${GROWTH_KIT:-%s}/growth")"' % KIT_ROOT


def venv_python() -> str:
    return str(Path(os.environ.get("GROWTH_VENV") or Path.home() / ".growth-ops-kit" / "venv") / "bin" / "python")


def permissions_wanted(cfg: dict) -> tuple[list[str], list[str]]:
    allow = ["Bash(growth *)", "Bash(growth)", f"Bash({venv_python()} *)", "Bash(python3 -m pytest*)", "Bash(pytest*)"]
    allow += [f"Bash(git {g}*)" for g in READ_ONLY_GIT]
    deny = list(DENY_ALWAYS)
    for cmd in cfg.get("deploy_commands") or []:
        deny.append(f"Bash({cmd}*)")
    host = urlsplit(cfg.get("site_url") or "").netloc
    if host and (cfg.get("live_site_rule") or "").startswith("no-crawl"):
        deny += [f"WebFetch(domain:{host})", f"Bash(curl*{host}*)", f"Bash(wget*{host}*)"]
    return allow, deny


def _load(settings: Path) -> dict:
    try:
        return json.loads(settings.read_text()) if settings.exists() else {}
    except ValueError:
        raise SystemExit(f"{settings} is not valid JSON; fix it, then run this again")


def install(folder: Path, name: str, site: str, kit_root: Path = KIT_ROOT, permissions: bool = True,
            claude_md: bool = True, cfg: dict | None = None) -> list[Path]:
    """Write the missing pieces into <folder>; returns the files written or changed."""
    folder, made = Path(folder), []
    skills_src = KIT_DIR / "skills"
    for src in sorted(skills_src.glob("*/SKILL.md")):
        skill = folder / ".claude" / "skills" / src.parent.name / "SKILL.md"
        if skill.exists():
            continue
        skill.parent.mkdir(parents=True, exist_ok=True)
        text = src.read_text().replace("](../../../book/", f"]({kit_root}/book/")
        if src.parent.name == "onboard":
            text = text.replace("# Onboard (re-runnable)", f"# Onboard (re-runnable)\n\nThis project: **{name}** ({site}). The kit is at "
                                f"`{kit_root}`; the book is in its `book/` folder.", 1)
        skill.write_text(text)
        made.append(skill)
    settings = folder / ".claude" / "settings.json"
    command, status_command = f"{run_growth()} hook stop".replace(str(KIT_ROOT), str(kit_root)), \
        f"{run_growth()} statusline".replace(str(KIT_ROOT), str(kit_root))
    cfg_s = _load(settings)
    before = json.dumps(cfg_s, sort_keys=True)
    stop = cfg_s.setdefault("hooks", {}).setdefault("Stop", [])
    if "stop_hook.sh" not in json.dumps(stop) and "hook stop" not in json.dumps(stop):
        stop.append({"hooks": [{"type": "command", "command": command, "statusMessage": STOP_MESSAGE}]})
    for entry in stop:
        for h in entry.get("hooks", []):
            c = h.get("command", "")
            if "${GROWTH_KIT:-" in c and "stop_hook.sh" in c:           # our own older form (absolute kit path)
                h["command"] = command
            if ("hook stop" in h.get("command", "") or "stop_hook.sh" in h.get("command", "")) and not h.get("statusMessage"):
                h["statusMessage"] = STOP_MESSAGE
    if "statusLine" not in cfg_s:       # the owner watches the open task tick off at the bottom of the window (never replaced)
        cfg_s["statusLine"] = {"type": "command", "padding": 0, "command": status_command}
    elif "${GROWTH_KIT:-" in str(cfg_s["statusLine"].get("command", "")) and "statusline.py" in cfg_s["statusLine"]["command"]:
        cfg_s["statusLine"]["command"] = status_command
    if permissions:
        allow, deny = permissions_wanted(cfg or _project_cfg(folder))
        perm = cfg_s.setdefault("permissions", {})
        for key, wanted in (("allow", allow), ("deny", deny)):
            have = perm.setdefault(key, [])
            have.extend(w for w in wanted if w not in have)
    if json.dumps(cfg_s, sort_keys=True) != before:
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text(json.dumps(cfg_s, indent=2) + "\n")
        made.append(settings)
    if claude_md:
        md = folder / "CLAUDE.md"
        text = md.read_text() if md.exists() else ""
        if CLAUDE_START not in text:
            md.write_text(text.rstrip("\n") + ("\n\n" if text.strip() else "") + CLAUDE_BLOCK)
            made.append(md)
    return made


def _project_cfg(folder: Path) -> dict:
    try:
        return json.loads((Path(folder) / "growth.json").read_text())
    except (OSError, ValueError):
        return {}


def git_repo_of(path: Path) -> bool:
    return subprocess.run(["git", "-C", str(path), "rev-parse", "--git-dir"], capture_output=True).returncode == 0


def hook_installed(repo: Path, name: str = "pre-commit") -> bool:
    r = subprocess.run(["git", "-C", str(repo), "rev-parse", "--git-common-dir"], capture_output=True, text=True)
    if r.returncode:
        return False
    d = Path(r.stdout.strip())
    f = (d if d.is_absolute() else Path(repo) / d) / "hooks" / name
    return f.is_file() and "growth-gate-hook" in f.read_text(errors="replace")


def install_git_hooks(project: Path, cfg: dict) -> list[str]:
    """Run the kit's installer for the project's own repo (git init first), and the site hook for a Next.js site repo."""
    out = []
    if not git_repo_of(project):
        subprocess.run(["git", "init", "-q", str(project)], check=False)
    inst = KIT_DIR / "hooks" / "install_hooks.py"
    env = {**os.environ, "GROWTH_PROJECT": str(project)}
    for args in (["project"],) + ([["site", str(Path(project, cfg["site_repo"]).expanduser())]]
                                  if cfg.get("site_repo") and (cfg.get("stack") or "") == "nextjs" else []):
        r = subprocess.run([sys.executable, str(inst), *args], capture_output=True, text=True, env=env, cwd=project)
        out.append((r.stdout + r.stderr).strip().splitlines()[-1] if (r.stdout + r.stderr).strip() else f"hooks {args[0]}: no output")
    return out


def check(project: Path, cfg: dict) -> list[tuple[str, str, str, str]]:
    """[(piece, "ok" | "todo" | "na", what, fix)] for every piece of the harness."""
    project = Path(project)
    fix = "growth wizard --repair   (installs what is missing; never overwrites your own settings)"
    out = []
    settings = {}
    try:
        settings = json.loads((project / ".claude" / "settings.json").read_text())
    except (OSError, ValueError):
        pass
    stops = [h for e in settings.get("hooks", {}).get("Stop", []) for h in e.get("hooks", [])]
    ours = [h for h in stops if "hook stop" in h.get("command", "") or "stop_hook.sh" in h.get("command", "")]
    out.append(("Stop hook with status message", "ok" if ours and all(h.get("statusMessage") for h in ours) else "todo",
                "Stop hook runs and says what it is doing" if ours and all(h.get("statusMessage") for h in ours)
                else "no Stop hook, or it has no statusMessage (a silent hook looks like a stall)", fix))
    out.append(("Workflow guard", "na", "this kit version has no workflow guard yet (issue #24); nothing to install", ""))
    sl = settings.get("statusLine") or {}
    out.append(("Status line", "ok" if "statusline" in str(sl.get("command", "")) else "todo",
                "status line shows the open task as a bar" if "statusline" in str(sl.get("command", "")) else "no growth status line in .claude/settings.json", fix))
    asked = wizard_state.get(project, "harness").get("answer") or {}
    perm = settings.get("permissions") or {}
    if isinstance(asked, dict) and asked.get("permissions") is False:
        out.append(("Permissions block", "na", "the owner declined it (setup-state.json)", ""))
    else:
        allow, deny = permissions_wanted(cfg)
        missing = [x for x in allow + deny if x not in (perm.get("allow") or []) + (perm.get("deny") or [])]
        out.append(("Permissions block", "ok" if not missing else "todo",
                    "allow and deny lists are in .claude/settings.json (see /permissions)" if not missing
                    else f"{len(missing)} allow/deny entries missing, for example {missing[0]}", fix))
    skills = [p.parent.name for p in (KIT_DIR / "skills").glob("*/SKILL.md")]
    lost = [s for s in skills if not (project / ".claude" / "skills" / s / "SKILL.md").is_file()]
    out.append(("Skills", "ok" if not lost else "todo", f"skills present: {', '.join(skills)}" if not lost else f"missing skill: {', '.join(lost)}", fix))
    md = project / "CLAUDE.md"
    has = md.is_file() and CLAUDE_START in md.read_text(errors="replace")
    out.append(("CLAUDE.md before-you-act lines", "ok" if has else "todo",
                "CLAUDE.md has the workflow, checkpoints and progress lines" if has else "CLAUDE.md lacks the growth-harness block", fix))
    if not (isinstance(asked, dict) and asked.get("git_hooks")):
        out.append(("Git hooks", "na", "not asked, or the owner said no (setup-state.json); `growth install_hooks project` adds them later", ""))
    else:
        bad = []
        if not hook_installed(project):
            bad.append("project pre-commit")
        if cfg.get("site_repo") and (cfg.get("stack") or "") == "nextjs":
            site = Path(project, cfg["site_repo"]).expanduser()
            if site.is_dir() and not hook_installed(site):
                bad.append("site pre-commit")
        out.append(("Git hooks", "ok" if not bad else "todo", "git pre-commit hooks installed" if not bad else f"not installed: {', '.join(bad)}", fix))
    return out
