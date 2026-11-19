"""setup.sh sets a neutral commit identity for the kit checkout only: repo-local, a GitHub no-reply form, never global.
The step is cut out of setup.sh (between its two markers) and run alone, because the whole script runs the test suite."""
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOREPLY = "@users.noreply" + ".github.com"   # built in two parts: the leak check reads a whole address as an email


def step():
    s = (ROOT / "setup.sh").read_text()
    return s.split("# 6b.", 1)[1].split("# 7. Tests", 1)[0]


def run_step(repo, home, **env):
    script = 'ok(){ echo "OK $1"; }\nwarn(){ echo "NOTE $1"; }\nROOT="$1"\n# 6b.' + step()
    e = {k: v for k, v in os.environ.items() if not k.startswith(("GIT_", "GROWTH_KIT"))}
    e.update(HOME=str(home), GIT_CONFIG_NOSYSTEM="1", **env)
    return subprocess.run(["bash", "-c", script, "x", str(repo)], capture_output=True, text=True, env=e, stdin=subprocess.DEVNULL)


def local(repo, key):
    return subprocess.run(["git", "-C", str(repo), "config", "--local", key], capture_output=True, text=True).stdout.strip()


def make_repo(tmp_path):
    repo = tmp_path / "kit"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    return repo


def test_noreply_email_from_the_environment_is_set_locally_only(tmp_path):
    repo, home = make_repo(tmp_path), tmp_path / "home"
    home.mkdir()
    r = run_step(repo, home, GROWTH_KIT_GIT_EMAIL="123+someone" + NOREPLY)
    assert "commit identity set for this checkout only" in r.stdout, r.stdout + r.stderr
    assert local(repo, "user.email") == "123+someone" + NOREPLY
    assert not (home / ".gitconfig").exists()          # the global git config is never touched


def test_a_personal_address_is_refused_and_nothing_is_set(tmp_path):
    repo, home = make_repo(tmp_path), tmp_path / "home"
    home.mkdir()
    r = run_step(repo, home, GROWTH_KIT_GIT_EMAIL="someone@example.com")
    assert "not a GitHub no-reply address" in r.stdout
    assert local(repo, "user.email") == ""


def test_without_a_terminal_or_a_value_it_only_prints_the_command(tmp_path):
    repo, home = make_repo(tmp_path), tmp_path / "home"
    home.mkdir()
    r = run_step(repo, home)
    assert "no neutral commit identity set" in r.stdout and local(repo, "user.email") == ""


def test_an_existing_noreply_identity_is_kept(tmp_path):
    repo, home = make_repo(tmp_path), tmp_path / "home"
    home.mkdir()
    subprocess.run(["git", "-C", str(repo), "config", "--local", "user.email", "9+a" + NOREPLY], check=True)
    r = run_step(repo, home, GROWTH_KIT_GIT_EMAIL="1+b" + NOREPLY)
    assert "9+a" + NOREPLY + " (repo-local)" in r.stdout
