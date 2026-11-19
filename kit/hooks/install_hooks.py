#!/usr/bin/env python3
"""Install the git pre-commit hooks that run the rules, so they run at every commit instead of being read and forgotten.
Run by hand; safe to run again (idempotent); prints what it did. Local .git hooks only: nothing is pushed, nothing
starts with the computer.

  growth install_hooks kit                 # the kit's own repo: tests + leak check (for kit contributors)
  growth install_hooks project             # the project's repo: every owner message logged + leak check of staged files
  growth install_hooks site <worktree>     # a Next.js site worktree: the static gate for every page whose files changed
  growth install_hooks remove [kit|project|site <worktree>]
  growth install_hooks status

A hook that was already there is kept as pre-commit.local and runs first. Site worktrees share one hooks folder, so the
site hook is installed once and runs only in the worktrees listed in <git common dir>/growth-gate-worktrees.
The site hook itself calls: growth install_hooks run-site <worktree> (see run_site below).
"""
from __future__ import annotations

import os
import re
import stat
import subprocess
import sys
from pathlib import Path

KIT_DIR = Path(__file__).resolve().parent.parent          # growth-ops-kit/kit
KIT_ROOT = KIT_DIR.parent                                 # growth-ops-kit
GROWTH = KIT_ROOT / "growth"
sys.path.insert(0, str(KIT_DIR / "tools"))
MARK = "growth-gate-hook"
LIST = "growth-gate-worktrees"

KIT_HOOK = f"""#!/bin/sh
# {MARK} kit: written by kit/hooks/install_hooks.py (edit that file, then run it again; not this one).
# Blocks the commit when the tests fail or the leak check finds a key, a private word or a personal address.
if [ -x "$0.local" ]; then "$0.local" "$@" || exit 1; fi
cd "$(git rev-parse --show-toplevel)" || exit 1
# The git-ignored word list lives in the main checkout; a linked worktree has no copy of its own.
WORDS="$PWD/.private-words"
[ -f "$WORDS" ] || WORDS="$(cd "$(git rev-parse --git-common-dir)/.." && pwd)/.private-words"
# Test what is being committed (the staged files), not the shared working tree other people are editing.
SNAP=$(mktemp -d "${{TMPDIR:-/tmp}}/growth-hook.XXXXXX") || exit 1
trap 'rm -rf "$SNAP"' EXIT
git checkout-index -a --prefix="$SNAP/" || exit 1
# The tests make their own git repositories: they must not inherit this commit's index, repository or author.
for v in $(env | grep '^GIT_' | cut -d= -f1); do unset "$v"; done
unset GIT_INDEX_FILE
if ! out=$(cd "$SNAP" && PYTHONDONTWRITEBYTECODE=1 python3 kit/tools/leak_check.py --root "$SNAP" --private-words "$WORDS" 2>&1); then
  printf '%s\n' "$out" | tail -15
  echo "pre-commit BLOCKED: the leak check found something that must not be committed (growth leak_check)."
  exit 1
fi
if ! out=$(cd "$SNAP" && PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -x tests 2>&1); then
  printf '%s\n' "$out" | tail -15
  echo "pre-commit BLOCKED: tests fail (python3 -m pytest tests). Fix them, then commit."
  exit 1
fi
exit 0
"""


KIT_MSG_HOOK = f"""#!/bin/sh
# {MARK} kit-msg: written by kit/hooks/install_hooks.py (edit that file, then run it again; not this one).
# Blocks the commit when its message holds a key or a private word (the pre-commit hook only reads files).
if [ -x "$0.local" ]; then "$0.local" "$@" || exit 1; fi
cd "$(git rev-parse --show-toplevel)" || exit 1
WORDS="$PWD/.private-words"
[ -f "$WORDS" ] || WORDS="$(cd "$(git rev-parse --git-common-dir)/.." && pwd)/.private-words"
MSG="$1"; case "$MSG" in /*) ;; *) MSG="$PWD/$MSG" ;; esac
[ -f "$MSG" ] || MSG="$(git rev-parse --git-dir)/COMMIT_EDITMSG"
if ! out=$(PYTHONDONTWRITEBYTECODE=1 python3 "{KIT_DIR}/tools/leak_check.py" --message "$MSG" --private-words "$WORDS" 2>&1); then
  printf '%s\\n' "$out" | tail -10
  echo "commit-msg BLOCKED: the commit message holds a key or a private word. Reword it, then commit."
  exit 1
fi
exit 0
"""

KIT_PUSH_HOOK = f"""#!/bin/sh
# {MARK} kit-push: written by kit/hooks/install_hooks.py (edit that file, then run it again; not this one).
# Blocks a push while the whole history (every commit, message and identity) is not clean.
if [ -x "$0.local" ]; then "$0.local" "$@" || exit 1; fi
cd "$(git rev-parse --show-toplevel)" || exit 1
WORDS="$PWD/.private-words"
[ -f "$WORDS" ] || WORDS="$(cd "$(git rev-parse --git-common-dir)/.." && pwd)/.private-words"
if ! out=$(PYTHONDONTWRITEBYTECODE=1 python3 "{KIT_DIR}/tools/leak_check.py" --history --private-words "$WORDS" 2>&1); then
  printf '%s\\n' "$out" | tail -15
  echo "pre-push BLOCKED: growth leak_check --history found something that must not be published."
  exit 1
fi
exit 0
"""


def project_hook(project: Path) -> str:
    return f"""#!/bin/sh
# {MARK} project: written by kit/hooks/install_hooks.py (edit that file, then run it again; not this one).
# Blocks the commit when an owner message is not in the steps log or a staged file holds a key or private word.
if [ -x "$0.local" ]; then "$0.local" "$@" || exit 1; fi
export GROWTH_PROJECT="{project}"
G="{GROWTH}"
[ -x "$G" ] || {{ echo "pre-commit: growth kit not found at $G; project hooks skipped"; exit 0; }}
if [ -f "$GROWTH_PROJECT/docs/steps-log.md" ] && ! out=$("$G" owner_messages check 2>&1); then
  printf '%s\n' "$out" | grep -E '^(MISSING|ANSWER)' | head -10
  echo "pre-commit BLOCKED: owner messages not in docs/steps-log.md (book/01-flow.md stage F). Log them, then commit."
  exit 1
fi
if ! out=$("$G" leak_check --staged 2>&1); then
  printf '%s\n' "$out" | tail -15
  echo "pre-commit BLOCKED: the leak check found something that must not be committed."
  exit 1
fi
exit 0
"""


def project_msg_hook(project: Path) -> str:
    return f"""#!/bin/sh
# {MARK} project-msg: written by kit/hooks/install_hooks.py (edit that file, then run it again; not this one).
# Blocks the commit when its message holds a key or a private word.
if [ -x "$0.local" ]; then "$0.local" "$@" || exit 1; fi
export GROWTH_PROJECT="{project}"
G="{GROWTH}"
[ -x "$G" ] || exit 0
MSG="$1"; case "$MSG" in /*) ;; *) MSG="$PWD/$MSG" ;; esac
if ! out=$(cd "{project}" && "$G" leak_check --message "$MSG" 2>&1); then
  printf '%s\\n' "$out" | tail -10
  echo "commit-msg BLOCKED: the commit message holds a key or a private word. Reword it, then commit."
  exit 1
fi
exit 0
"""


def site_hook(project: Path) -> str:
    return f"""#!/bin/sh
# {MARK} site: written by the growth kit's kit/hooks/install_hooks.py (edit that file, then run it again; not this one).
# Runs the static rule gate for every page whose files are in this commit; blocks on any FAIL.
if [ -x "$0.local" ]; then "$0.local" "$@" || exit 1; fi
export GROWTH_PROJECT="{project}"
H="{KIT_DIR / 'hooks' / 'install_hooks.py'}"
[ -f "$H" ] || {{ echo "pre-commit: growth kit not found at $H; rule gate skipped"; exit 0; }}
exec python3 "$H" run-site "$(git rev-parse --show-toplevel)"
"""


def git(repo: Path, *args) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()


def hooks_dir(repo: Path) -> Path:
    custom = subprocess.run(["git", "-C", str(repo), "config", "core.hooksPath"], capture_output=True, text=True).stdout.strip()
    if custom:
        sys.exit(f"{repo} uses core.hooksPath={custom}; install the hook there by hand or unset it first.")
    common = Path(git(repo, "rev-parse", "--git-common-dir"))
    return (common if common.is_absolute() else (repo / common)).resolve() / "hooks"


def write_hook(hook: Path, body: str) -> str:
    hook.parent.mkdir(parents=True, exist_ok=True)
    if hook.exists():
        old = hook.read_text(errors="replace")
        if old == body:
            return f"unchanged: {hook}"
        if MARK not in old:
            keep = hook.with_name(hook.name + ".local")
            if keep.exists():
                sys.exit(f"{hook} and {keep} both exist and neither is ours; merge them by hand first.")
            hook.rename(keep)
            print(f"kept the earlier hook as {keep} (it runs first)")
    hook.write_text(body)
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return f"installed: {hook}"


def remove_hook(hook: Path) -> str:
    if not hook.exists() or MARK not in hook.read_text(errors="replace"):
        return f"nothing to remove: {hook}"
    hook.unlink()
    keep = hook.with_name(hook.name + ".local")
    if keep.exists():
        keep.rename(hook)
        return f"removed: {hook} (the earlier hook is back)"
    return f"removed: {hook}"


def site_list(repo: Path) -> Path:
    return hooks_dir(repo).parent / LIST


def listed(repo: Path) -> list[str]:
    f = site_list(repo)
    return [l for l in f.read_text().splitlines() if l.strip()] if f.exists() else []


def cmd_kit(remove=False):
    for name, body in (("pre-commit", KIT_HOOK), ("commit-msg", KIT_MSG_HOOK), ("pre-push", KIT_PUSH_HOOK)):
        hook = hooks_dir(KIT_ROOT) / name
        print(remove_hook(hook) if remove else write_hook(hook, body))


def cmd_project(remove=False):
    from config import require_project
    project = require_project()
    if not (project / ".git").exists() and subprocess.run(["git", "-C", str(project), "rev-parse"], capture_output=True).returncode:
        sys.exit(f"{project} is not inside a git repository; run git init there first.")
    for name, body in (("pre-commit", project_hook(project)), ("commit-msg", project_msg_hook(project))):
        hook = hooks_dir(project) / name
        print(remove_hook(hook) if remove else write_hook(hook, body))


def cmd_site(wt: str, remove=False):
    repo = Path(wt).resolve()
    if not (repo / ".git").exists():
        sys.exit(f"{repo} is not a git checkout or worktree")
    top = git(repo, "rev-parse", "--show-toplevel")
    hook = hooks_dir(repo) / "pre-commit"
    have = listed(repo)
    if remove:
        rest = [w for w in have if w != top]
        site_list(repo).write_text("".join(w + "\n" for w in rest))
        print(f"removed from {site_list(repo)}: {top}" if top in have else f"not listed: {top}")
        if not rest:
            print(remove_hook(hook))
        return
    from config import require_project
    print(write_hook(hook, site_hook(require_project())))
    if top in have:
        print(f"unchanged: {top} already in {site_list(repo)}")
    else:
        site_list(repo).write_text("".join(w + "\n" for w in have + [top]))
        print(f"added: {top} to {site_list(repo)} (the hook runs only in listed worktrees)")


def cmd_status():
    def line(name, repo):
        h = hooks_dir(repo) / "pre-commit"
        print(f"{name}: {'installed' if h.exists() and MARK in h.read_text(errors='replace') else 'NOT installed'} ({h})")
    if (KIT_ROOT / ".git").exists():
        line("kit", KIT_ROOT)
    from config import find_project, load_cfg, resolve_in
    project = find_project()
    if project:
        try:
            line("project", project)
        except subprocess.CalledProcessError:
            print(f"project: {project} is not in a git repository")
        cfg = load_cfg(project)
        site = resolve_in(project, cfg["site_repo"]) if cfg.get("site_repo") else None
        if site and (site / ".git").exists():
            h = hooks_dir(site) / "pre-commit"
            ok = h.exists() and MARK in h.read_text(errors="replace")
            print(f"site: {'installed' if ok else 'NOT installed'} ({h}); worktrees: {', '.join(listed(site)) or 'none'}")


# ---- the site hook's work ----------------------------------------------------------------------------------------------
def route_of(f: str, repo: Path, cfg: dict | None = None) -> str | None:
    """The page a changed file belongs to, or None when it is shared (components/, lib/, app/*.css, layout).
    Next.js layout: posts in growth.json posts_dir (default content/posts, served under blog_path, default /blog),
    pages in pages_dir (default content/pages), routes in app/**/page.tsx."""
    from config import site_setting
    blog = (cfg or {}).get("blog_path", "/blog").rstrip("/")
    posts, pages = site_setting(cfg or {}, "posts_dir", "content/posts").strip("/"), site_setting(cfg or {}, "pages_dir", "content/pages").strip("/")
    m = re.match(re.escape(posts) + r"/(.+)\.mdx?$", f)
    if m:
        return blog + "/" + m.group(1)
    m = re.match(re.escape(pages) + r"/(.+)\.mdx?$", f)
    if m:
        return "/" + m.group(1)
    if not f.startswith("app/"):
        return None
    d = (repo / f).parent
    app = repo / "app"
    while d != app and app in d.parents:
        if (d / "page.tsx").exists() and "[" not in d.name:
            segs = [s for s in d.relative_to(app).parts if not (s.startswith("(") and s.endswith(")"))]
            return "/" + "/".join(segs)
        d = d.parent
    return None


def page_type(route: str, cfg: dict) -> str:
    slug = route.strip("/")
    if slug in cfg.get("silos", {}):
        return "money"
    if route in cfg.get("core_pages", {}) or route in cfg.get("money_core", []):
        return "core"
    blog = cfg.get("blog_path", "/blog").rstrip("/")
    if route.startswith(blog + "/"):
        return "post"
    return "hub" if route == blog else "core"


def run_site(wt: str) -> int:
    repo = Path(wt).resolve()
    top = git(repo, "rev-parse", "--show-toplevel")
    if top not in listed(repo):
        return 0
    from config import CFG
    staged = [f for f in git(repo, "diff", "--cached", "--name-only", "--diff-filter=ACMR").splitlines() if f]
    routes = {r for r in (route_of(f, repo, CFG) for f in staged) if r}
    if any(route_of(f, repo, CFG) is None for f in staged):
        # a shared file changed: check the pages this branch is building (one page per branch, OWNER-RULES)
        from gatelib.core import base_ref_of
        base = base_ref_of(repo, CFG)
        try:
            branch = git(repo, "diff", "--name-only", base + "...HEAD").splitlines() if base else []
        except subprocess.CalledProcessError:
            branch = []
        routes |= {r for r in (route_of(f, repo, CFG) for f in branch) if r}
    if not routes:
        print("pre-commit rule gate: no page in this commit (shared files only, no page on this branch); nothing to check.")
        return 0
    worst = 0
    for r in sorted(routes):
        t = page_type(r, CFG)
        print(f"pre-commit rule gate (static): {r} as a {t} page")
        p = subprocess.run([sys.executable, str(KIT_DIR / "tools" / "gate.py"), "page", r, "--repo", top, "--type", t],
                           capture_output=True, text=True)
        lines = (p.stdout + p.stderr).splitlines()
        print("\n".join(l for l in lines if l.startswith(("FAIL", "Gate:", "Static mode"))))
        worst = max(worst, p.returncode)
    if worst:
        print("pre-commit BLOCKED: fix every FAIL above, then commit. Full gate before release: "
              "growth gate page <path> --url <local url> --repo <worktree> --type <type>")
    return 1 if worst else 0


def main(argv: list[str]) -> int:
    if argv == ["kit"]:
        cmd_kit()
    elif argv == ["project"]:
        cmd_project()
    elif argv[:1] == ["site"] and len(argv) == 2:
        cmd_site(argv[1])
    elif argv[:1] == ["remove"]:
        if argv[1:2] == ["site"] and len(argv) == 3:
            cmd_site(argv[2], remove=True)
        elif argv[1:2] == ["project"]:
            cmd_project(remove=True)
        else:
            cmd_kit(remove=True)
    elif argv[0] == "status":
        cmd_status()
    elif argv[0] == "run-site" and len(argv) == 2:
        return run_site(argv[1])
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    sys.exit(main(sys.argv[1:]))
