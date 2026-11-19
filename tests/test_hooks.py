"""The git pre-commit hooks: the project hook blocks a commit that holds a key or a private word and lets a clean one through;
the kit hook runs the leak check and the tests; installing twice changes nothing; an earlier hook is kept and still runs."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTALL = ROOT / "kit" / "hooks" / "install_hooks.py"


def sh(cwd, *cmd, env=None):
    e = {**os.environ, "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "T",
         "GIT_COMMITTER_EMAIL": "t@example.com", **(env or {})}
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=e)


def project(tmp_path):
    p = tmp_path / "proj"
    (p / "docs").mkdir(parents=True)
    (p / "growth.json").write_text(json.dumps({"name": "T", "site_url": "https://t.example"}))
    sh(p, "git", "init", "-q")
    return p


def install(p, *args):
    return sh(p, sys.executable, str(INSTALL), *args, env={"GROWTH_PROJECT": str(p)})


def test_project_hook_blocks_a_key_and_passes_clean_files(tmp_path):
    p = project(tmp_path)
    r = install(p, "project")
    assert r.returncode == 0 and "installed" in r.stdout, r.stderr
    hook = p / ".git" / "hooks" / "pre-commit"
    assert hook.is_file() and "growth-gate-hook" in hook.read_text() and os.access(hook, os.X_OK)
    (p / "ok.md").write_text("plain text\n")
    sh(p, "git", "add", "ok.md")
    assert sh(p, "git", "commit", "-qm", "clean").returncode == 0
    (p / "bad.txt").write_text("API_TOKEN=" + "q1w2e3r4t5y6u7i8o9p0" + "\n")
    sh(p, "git", "add", "bad.txt")
    c = sh(p, "git", "commit", "-qm", "dirty")
    assert c.returncode != 0 and "leak check" in (c.stdout + c.stderr)


def test_installing_twice_changes_nothing_and_remove_restores(tmp_path):
    p = project(tmp_path)
    install(p, "project")
    again = install(p, "project")
    assert "unchanged" in again.stdout
    st = install(p, "status")
    assert "project: installed" in st.stdout
    rm = install(p, "remove", "project")
    assert "removed" in rm.stdout and not (p / ".git" / "hooks" / "pre-commit").exists()


def test_an_earlier_hook_is_kept_and_runs_first(tmp_path):
    p = project(tmp_path)
    hook = p / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\necho earlier hook ran >&2\nexit 1\n")
    hook.chmod(0o755)
    r = install(p, "project")
    assert "kept the earlier hook" in r.stdout and (p / ".git" / "hooks" / "pre-commit.local").is_file()
    (p / "a.md").write_text("x\n")
    sh(p, "git", "add", "a.md")
    c = sh(p, "git", "commit", "-qm", "x")
    assert c.returncode != 0 and "earlier hook ran" in c.stderr


def test_the_kit_hook_text_runs_the_leak_check_and_the_tests():
    import hooks_text
    assert "leak_check.py" in hooks_text.KIT_HOOK and "pytest" in hooks_text.KIT_HOOK


def test_the_kit_hook_clears_the_commits_git_variables_before_running_the_tests():
    """Found when the hook first ran: the tests inherited GIT_INDEX_FILE from the commit and their own git repos broke."""
    import hooks_text
    assert "unset GIT_INDEX_FILE" in hooks_text.KIT_HOOK and "unset \"$v\"" in hooks_text.KIT_HOOK
    assert hooks_text.KIT_HOOK.index("checkout-index") < hooks_text.KIT_HOOK.index("unset GIT_INDEX_FILE") < hooks_text.KIT_HOOK.index("pytest")


def test_commit_msg_hook_blocks_a_private_word_in_the_message(tmp_path):
    p = project(tmp_path)
    (p / ".private-words").write_text("initech\n")
    r = install(p, "project")
    assert r.returncode == 0, r.stderr
    hook = p / ".git" / "hooks" / "commit-msg"
    assert hook.is_file() and "growth-gate-hook" in hook.read_text() and os.access(hook, os.X_OK)
    (p / "ok.md").write_text("plain text\n")
    sh(p, "git", "add", "ok.md")
    c = sh(p, "git", "commit", "-qm", "work for the Initech run")
    assert c.returncode != 0 and "commit-msg BLOCKED" in (c.stdout + c.stderr)
    assert sh(p, "git", "commit", "-qm", "plain message").returncode == 0
    assert "removed" in install(p, "remove", "project").stdout and not hook.exists()


def test_leak_check_message_mode_reads_a_file_and_ignores_comment_lines(tmp_path):
    (tmp_path / "words").write_text("initech\n")
    msg = tmp_path / "MSG"
    leak = ROOT / "kit" / "tools" / "leak_check.py"
    msg.write_text("fine subject\n# initech in a git comment line\n")
    ok = sh(tmp_path, sys.executable, str(leak), "--message", str(msg), "--private-words", str(tmp_path / "words"))
    assert ok.returncode == 0, ok.stdout
    msg.write_text("fine subject\n\nbody names Initech\n")
    bad = sh(tmp_path, sys.executable, str(leak), "--message", str(msg), "--private-words", str(tmp_path / "words"))
    assert bad.returncode == 1 and "FAIL commit message:3 private word" in bad.stdout


def test_kit_hook_scripts_find_the_word_list_of_the_main_checkout():
    sys.path.insert(0, str(ROOT / "kit" / "hooks"))
    import install_hooks
    for body in (install_hooks.KIT_HOOK, install_hooks.KIT_MSG_HOOK, install_hooks.KIT_PUSH_HOOK):
        assert "git-common-dir" in body and "--private-words" in body
    assert "--history" in install_hooks.KIT_PUSH_HOOK


def test_kit_commit_msg_hook_blocks_in_the_main_checkout_and_in_a_linked_worktree(tmp_path):
    sys.path.insert(0, str(ROOT / "kit" / "hooks"))
    import install_hooks
    main = tmp_path / "main"
    main.mkdir()
    sh(main, "git", "init", "-q")
    (main / ".private-words").write_text("initech\n")
    (main / "a.txt").write_text("a\n")
    sh(main, "git", "add", "a.txt")
    assert sh(main, "git", "commit", "-qm", "first").returncode == 0
    install_hooks.write_hook(main / ".git" / "hooks" / "commit-msg", install_hooks.KIT_MSG_HOOK)
    wt = tmp_path / "wt"
    sh(main, "git", "worktree", "add", "-q", str(wt), "-b", "side")
    for where in (main, wt):
        (where / f"{where.name}.txt").write_text("x\n")
        sh(where, "git", "add", f"{where.name}.txt")
        bad = sh(where, "git", "commit", "-qm", "the Initech run")
        assert bad.returncode != 0 and "commit-msg BLOCKED" in (bad.stdout + bad.stderr), where
        assert sh(where, "git", "commit", "-qm", "neutral words").returncode == 0, where
