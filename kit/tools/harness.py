#!/usr/bin/env python3
"""The agent harness of a project, installed and checked as one set (library; `growth wizard --repair` installs what is missing,
doctor A13 lists each piece).

Pieces: the Stop hook (with a status message), the workflow guard (when this kit has one), the status line (bars), the
permissions block (allow the kit's own commands and read-only git; deny pushes, deploys, a live crawl, ref and hook changes,
owner-only commands and editing the protected files), the skills, the project CLAUDE.md
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
import atomic  # noqa: E402
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
STAGE_MESSAGE = "Re-reading the page checkpoints"
STOP_MESSAGE = "Checking every owner message is logged and every rule has its check"
# Read-only git only. `git branch*` was here once and allowed `git branch -f main <sha>` / `git branch -D main` (audit C4).
READ_ONLY_GIT = ["status", "log", "diff", "show", "branch --list", "branch --show-current", "worktree list", "rev-parse", "remote -v"]
# Owner-only acts: the agent may not run them (growth approve needs the owner's own terminal anyway).
OWNER_ONLY = ["approve", "approvals", "wizard confirm", "tasks answer", "journal answer", "install_hooks remove", "install-hooks remove"]
# Prefix rules are a speed bump, not a wall: they stop the plain forms an agent types; a determined agent with a shell can
# find others. The `*` forms cover `git -C . push`, `env git push`, a kit path in front of growth, and flags anywhere.
DENY_ALWAYS = ["Bash(git push*)", "Bash(git * push*)", "Bash(env git*)", "Bash(command git*)",
               "Bash(git merge* main*)", "Bash(git merge main*)",
               "Bash(git branch -f*)", "Bash(git branch -D*)", "Bash(git branch -d*)", "Bash(git branch -m*)", "Bash(git branch -M*)",
               "Bash(git branch -c*)", "Bash(git branch -C*)", "Bash(git branch --force*)", "Bash(git branch --delete*)",
               "Bash(git branch --move*)", "Bash(git update-ref*)", "Bash(git * update-ref*)", "Bash(git symbolic-ref*)",
               "Bash(*core.hooksPath*)", "Bash(*core.hookspath*)", "Bash(*--no-verify*)", "Bash(git commit -n*)",
               "Bash(git * --output*)", "Bash(git *--ext-diff*)",
               "Bash(rm -rf /*)", "Bash(rm -rf ~*)", "Bash(rm -rf ..*)", "Bash(rm -rf $HOME*)", "Bash(rm -fr *)",
               "Bash(rm *.git/hooks*)", "Bash(rm *.claude*)"]
# Files only the owner (or the kit's own commands) change: the agent's settings, the project's settings and setup memory,
# the approvals log, the task list and journal (written through growth tasks / growth journal) and the database they live in
# (state/growth.db: never edited by hand), git hooks, the signing key.
PROTECTED_FILES = [".claude/settings.json", ".claude/settings.local.json", "growth.json", "setup-state.json", "setup-answers.json",
                   "approvals.jsonl", "docs/tasks.json", "journal/**", "state/**", "research/*-record.json", ".git/hooks/**", ".githooks/**"]
# Allow-list entries older kits wrote that hand the agent arbitrary code (any Python, any test file) or ref changes;
# install() removes exactly these strings and check() reports them.
OLD_UNSAFE_ALLOW = ["Bash(git branch*)", "Bash(python3 -m pytest*)", "Bash(pytest*)"]


OURS = 'GROWTH_PROJECT="$CLAUDE_PROJECT_DIR" '


def run_growth() -> str:
    """The kit's own growth by its absolute path (audit L5: `command -v growth` ran whatever `growth` came first on the
    PATH as the Stop hook). GROWTH_KIT in your own environment may point it elsewhere; --repair refreshes the path and doctor
    A12 reports a kit folder that moved."""
    return OURS + '"${GROWTH_KIT:-%s}/growth"' % KIT_ROOT


def _refresh(c: str, wanted: str) -> str:
    """Our own hook command (any older form, or a kit path that moved) -> the current one; anything else unchanged."""
    if c.startswith(OURS) and ("command -v growth" in c or "${GROWTH_KIT:-" in c) and c != wanted:
        return wanted
    return c


def venv_python() -> str:
    return str(Path(os.environ.get("GROWTH_VENV") or Path.home() / ".growth-ops-kit" / "venv") / "bin" / "python")


def unsafe_allow(entry: str) -> bool:
    """An allow entry this kit once wrote that lets the agent run any code or move a branch."""
    return entry in OLD_UNSAFE_ALLOW or (entry.startswith("Bash(") and "/.growth-ops-kit/venv/bin/python" in entry) \
        or entry == f"Bash({venv_python()} *)"


def permissions_wanted(cfg: dict, kit_root: Path = KIT_ROOT) -> tuple[list[str], list[str]]:
    """(allow, deny) for .claude/settings.json. Allowed: the growth command and read-only git, nothing that runs arbitrary
    code (no bare Python or pytest: a test file the agent writes is code). Denied: pushes, merges to main, ref and hook
    changes, owner-only commands, and editing the protected files or the kit itself."""
    allow = ["Bash(growth *)", "Bash(growth)"]
    allow += [f"Bash(git {g}*)" for g in READ_ONLY_GIT]
    deny = list(DENY_ALWAYS)
    delegate = (cfg.get("approvals") or {}).get("delegate_local") is True if isinstance(cfg.get("approvals"), dict) else False
    for cmd in OWNER_ONLY:
        if delegate and cmd == "approve":      # delegated local approvals: allow only the --delegated form; the rest stays denied
            for never in ("browser", "region", "pending", "key"):
                deny += [f"Bash(growth approve {never}*)", f"Bash(*/growth approve {never}*)"]
            allow += ["Bash(growth approve * --delegated)", "Bash(growth approve * --delegated *)"]
            continue
        deny += [f"Bash(growth {cmd}*)", f"Bash(*/growth {cmd}*)"]
    # Edit(path) rules cover every file-writing tool in Claude Code; a Write(path) rule is not matched and only prints a
    # warning on every start (a real scheduled run logged 17 such lines), so the kit writes Edit rules only.
    for f in PROTECTED_FILES:
        deny += [f"Edit(**/{f})"]
    deny += [f"Edit(/{kit_root}/**)", "Read(~/.config/growth-ops-kit/**)", "Edit(~/.config/growth-ops-kit/**)"]
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
    with atomic.locked(settings):          # read, merge and write under one lock: two installs never lose each other's entries
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
                elif "hook stop" in c:
                    h["command"] = _refresh(c, command)
                if ("hook stop" in h.get("command", "") or "stop_hook.sh" in h.get("command", "")) and not h.get("statusMessage"):
                    h["statusMessage"] = STOP_MESSAGE
        post = cfg_s["hooks"].setdefault("PostToolUse", [])       # the workflow guard: re-read the checkpoints at each stage (once)
        if "hook stage" not in json.dumps(post):
            post.append({"matcher": "Bash", "hooks": [{"type": "command", "command": f"{run_growth()} hook stage".replace(str(KIT_ROOT), str(kit_root)),
                                                        "statusMessage": STAGE_MESSAGE}]})
        stage_command = f"{run_growth()} hook stage".replace(str(KIT_ROOT), str(kit_root))
        for entry in post:
            for h in entry.get("hooks", []):
                if "hook stage" in h.get("command", ""):
                    h["command"] = _refresh(h["command"], stage_command)
        if not post:
            del cfg_s["hooks"]["PostToolUse"]
        if "statusLine" not in cfg_s:       # the owner watches the open task tick off at the bottom of the window (never replaced)
            cfg_s["statusLine"] = {"type": "command", "padding": 0, "command": status_command}
        elif "${GROWTH_KIT:-" in str(cfg_s["statusLine"].get("command", "")) and "statusline.py" in cfg_s["statusLine"]["command"]:
            cfg_s["statusLine"]["command"] = status_command
        elif str(cfg_s["statusLine"].get("command", "")).endswith(" statusline"):
            cfg_s["statusLine"]["command"] = _refresh(cfg_s["statusLine"]["command"], status_command)
        if permissions:
            allow, deny = permissions_wanted(cfg or _project_cfg(folder), kit_root)
            perm = cfg_s.setdefault("permissions", {})
            if perm.get("allow"):
                perm["allow"] = [a for a in perm["allow"] if not unsafe_allow(a)]     # our own older, unsafe entries only
            for key, wanted in (("allow", allow), ("deny", deny)):
                have = perm.setdefault(key, [])
                have.extend(w for w in wanted if w not in have)
        if json.dumps(cfg_s, sort_keys=True) != before:
            atomic.write_json(settings, cfg_s, indent=2)
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
    jobs = [["project"]]
    if cfg.get("site_repo") and (cfg.get("stack") or "") == "nextjs":
        jobs.append(["site", str(Path(project, cfg["site_repo"]).expanduser())])
    for args in jobs:
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
    stage = [h for e in settings.get("hooks", {}).get("PostToolUse", []) for h in e.get("hooks", []) if "hook stage" in h.get("command", "")]
    out.append(("Workflow guard (hook stage)", "ok" if stage and all(h.get("statusMessage") for h in stage) else "todo",
                "the stage hook re-reads the page checkpoints after each task step" if stage and all(h.get("statusMessage") for h in stage)
                else "no `hook stage` PostToolUse hook (or no statusMessage), so checkpoints are not re-read at each stage", fix))
    sl = settings.get("statusLine") or {}
    out.append(("Status line", "ok" if "statusline" in str(sl.get("command", "")) else "todo",
                "status line shows the open task as a bar" if "statusline" in str(sl.get("command", "")) else "no growth status line in .claude/settings.json", fix))
    asked = wizard_state.get(project, "harness").get("answer") or {}
    perm = settings.get("permissions") or {}
    if isinstance(asked, dict) and asked.get("permissions") is False:
        out.append(("Permissions block", "na", "the owner declined it (setup-state.json)", ""))
    else:
        allow, deny = permissions_wanted(cfg)
        have_deny = perm.get("deny") or []
        # the kit-folder entries name the kit's path at install time; any such entry counts
        missing = [x for x in allow + deny if x not in (perm.get("allow") or []) + have_deny and not x.startswith(("Edit(//", "Write(//"))]
        if not any(h.startswith("Edit(//") for h in have_deny):
            missing.append("Edit(//<kit folder>/**)")
        unsafe = [a for a in perm.get("allow") or [] if unsafe_allow(a)]
        what = ("allow and deny lists are in .claude/settings.json (see /permissions)" if not missing and not unsafe
                else (f"allow list has an entry that runs any code or moves a branch: {unsafe[0]}" if unsafe
                      else f"{len(missing)} allow/deny entries missing (removed?), for example {missing[0]}"))
        out.append(("Permissions block", "ok" if not missing and not unsafe else "todo", what, fix))
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
        hp = subprocess.run(["git", "-C", str(project), "config", "--get", "core.hooksPath"], capture_output=True, text=True).stdout.strip()
        if hp:
            bad.append(f"core.hooksPath is set to {hp}, so git skips the installed hooks (git config --unset core.hooksPath)")
        out.append(("Git hooks", "ok" if not bad else "todo", "git pre-commit hooks installed" if not bad else f"not installed or bypassed: {', '.join(bad)}", fix))
    return out
