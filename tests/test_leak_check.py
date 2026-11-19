"""The leak check: keys, tokens, private keys, .env files, personal emails, phone numbers and private words fail; the
safe lookalikes (example addresses, fictional phone numbers, placeholders) pass. Fake secrets are built at run time so no
secret-shaped string sits in this file."""
import subprocess
import sys
from pathlib import Path

import leak_check as lc

ROOT = Path(__file__).resolve().parent.parent


def kinds(text, words=()):
    return [k for _, k, _ in lc.scan_text(text, list(words))]


def test_key_shapes_fail():
    assert "AWS access key" in kinds("id = " + "AK" + "IA" + "ABCDEFGHIJKLMNOP")
    assert "API key (sk-)" in kinds("key: " + "sk" + "-" + "a1B2c3D4e5F6g7H8i9J0k1")
    assert "GitHub token" in kinds("t=" + "ghp" + "_" + "A" * 36)
    assert "private key block" in kinds("-----BEGIN " + "RSA " + "PRIVATE KEY-----")
    assert "bearer token" in kinds("Authorization: Bearer " + "a" * 12 + "." + "b" * 14)
    assert "JWT" in kinds("x " + "ey" + "J" + "a" * 12 + "." + "ey" + "J" + "b" * 12 + "." + "c" * 12)


def test_secret_assignments_fail_but_placeholders_pass():
    assert any(k.startswith("secret value") for k in kinds("API_TOKEN=" + "q1w2e3r4t5y6u7i8o9p0"))
    assert kinds("API_TOKEN=<your token>") == []
    assert kinds("export API_TOKEN=${TOKEN}") == []
    assert kinds("SECRET_KEY=changeme-please-1234") == []
    assert kinds("password = get_password()") == []


def test_emails():
    assert kinds("write to " + "jane" + "@" + "gmail.com") == ["email address"]
    for ok in ("hello@example.com", "a@mail.example.org", "me@brightline.example", "noreply@anthropic.com", "x@localhost.test"):
        assert kinds(ok) == [], ok


def test_phone_numbers():
    assert kinds("call " + "(415) " + "867-" + "5309") == ["phone number"]
    assert kinds("call " + "+44 " + "20 7946 " + "0958") == ["phone number"]
    assert kinds("call 555-0123 or (212) 555-0142") == []       # the reserved fictional range
    assert kinds("built 2026-11-18 on 127.0.0.1 port 3801, version 2.0.0") == []


def test_private_words_are_case_insensitive():
    assert kinds("Some ACMECORP text", ["acmecorp"]) == ["private word"]
    assert kinds("nothing here", ["acmecorp"]) == []


def test_private_words_match_across_spaces_hyphens_underscores_and_nothing():
    for text in ("the red fox hub", "the red-fox hub", "red_fox", "redfox", "Red.Fox", "RED   FOX", "path /red-fox-pages"):
        assert kinds(text, ["red fox"]) == ["private word"], text
    assert kinds("a red box", ["red fox"]) == []
    assert kinds("the hub", ["red-fox"]) == []
    assert lc.scan_name("pages/red-fox.md", ["red fox"])


def test_allow_marker_skips_a_line_only_under_tests_fixtures():
    line = "AKIA" + "ABCDEFGHIJKLMNOP  # leak-check: allow"
    assert kinds(line) != []                                                       # default: the marker is ignored
    assert [h for h in lc.scan_text(line, [], allow=lc.allow_marker_ok("tests/fixtures/a.txt"))] == []
    assert lc.scan_text(line, [], allow=lc.allow_marker_ok("src/app.py"))
    assert lc.scan_text(line, [], allow=lc.allow_marker_ok("docs/tests/fixtures-notes.md"))


def test_audit_h7_more_live_secret_shapes_fail():
    fake = "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"
    cases = {
        "Stripe-style key": "s" + "k_" + "live_" + fake[:24],
        "Slack webhook": "https://hooks." + "slack.com/services/T00/B00/" + fake[:12],
        "Discord webhook": "https://discord" + ".com/api/webhooks/123/" + fake[:12],
        "GitLab token": "gl" + "pat-" + fake[:20],
        "Hugging Face token": "h" + "f_" + fake[:34],
        "npm token": "n" + "pm_" + fake[:36],
        "Google OAuth secret": "GOC" + "SPX-" + fake[:24],
        "SendGrid key": "S" + "G." + fake[:20] + "." + fake[10:30],
        "password inside a web address": "postgres://app:" + "Zq8xPw27Lm" + "@db.internal.net/app",
        "email address (written out)": "mail jane " + "[at]" + " gmail.com",
    }
    for kind, text in cases.items():
        assert kind in kinds(text), (kind, text)
    assert "email address (written out)" in kinds("jane" + "%40" + "gmail.com")
    assert any(k.startswith("secret value") for k in kinds("api" + "-key: " + "q1w2e3r4t5y6u7i8o9p0"))
    assert kinds("postgres://user:pass@localhost/db") == []
    assert kinds("write [at] example.com") == []


def test_audit_h7_unspaced_and_international_phone_numbers():
    assert kinds("call " + "416" + "555" + "1234") == ["phone number"]
    assert kinds("mobile +91 " + "98765 " + "43210") == ["phone number"]
    assert kinds("order 4165551234 shipped") == []                                  # a bare number alone is not flagged


def test_audit_h7_big_files_are_scanned_in_chunks_not_skipped(tmp_path):
    filler = ("x" * 80 + "\n") * 40_000                                            # about 3.2 MB, over the old 2 MB limit
    (tmp_path / "big.txt").write_text(filler + "write to " + "jane" + "@" + "gmail.com\n" + filler)
    long_line = tmp_path / "oneline.json"
    long_line.write_text("a " * 700_000 + "AKIA" + "ABCDEFGHIJKLMNOP" + " b" * 10)       # one line longer than a chunk
    rep = lc.scan_files(tmp_path, ["big.txt", "oneline.json"], [])
    assert ("big.txt", 40_001, "email address", "jane…") in rep
    assert any(f == "oneline.json" and k == "AWS access key" for f, _n, k, _s in rep)


def test_audit_h7_binary_files_are_listed_and_database_files_fail(tmp_path):
    (tmp_path / "shot.png").write_bytes(b"\x89PNG\0\0\0data")
    (tmp_path / "app.sqlite").write_bytes(b"SQLite\0")
    warns = []
    rep = lc.scan_files(tmp_path, ["shot.png", "app.sqlite"], [], warns=warns)
    assert [w[0] for w in warns] == ["shot.png", "app.sqlite"]
    assert any(f == "app.sqlite" and "by name" in k for f, _n, k, _s in rep)
    assert not any(f == "shot.png" for f, *_ in rep)


def test_file_names():
    assert lc.scan_name(".env", [])
    assert lc.scan_name("sub/.env.production", [])
    assert lc.scan_name("keys/id_rsa", [])
    assert lc.scan_name("deploy.pem", [])
    assert not lc.scan_name(".env.example", [])
    assert lc.scan_name("docs/acmecorp-notes.md", ["acmecorp"])


def run(*args, cwd):
    return subprocess.run([sys.executable, str(ROOT / "kit" / "tools" / "leak_check.py"), *args], cwd=cwd, capture_output=True, text=True)


def test_cli_on_a_clean_and_a_dirty_folder(tmp_path):
    (tmp_path / "a.md").write_text("Hello from the Brightline example. Mail: team@example.com\n")
    ok = run(cwd=tmp_path)
    assert ok.returncode == 0 and "0 hit(s)" in ok.stdout
    (tmp_path / "b.txt").write_text("token " + "sk" + "-" + "Zz9" * 8 + "\n")
    (tmp_path / ".env").write_text("A=1\n")
    bad = run(cwd=tmp_path)
    assert bad.returncode == 1
    assert "API key (sk-)" in bad.stdout and "secret or environment file by name" in bad.stdout
    assert "Zz9Zz9" not in bad.stdout                 # a hit never prints the secret itself


def test_cli_reads_private_words_from_the_root(tmp_path):
    (tmp_path / "a.md").write_text("we work for Initech this year\n")
    (tmp_path / ".private-words").write_text("# comment\ninitech\n")
    r = run(cwd=tmp_path)
    assert r.returncode == 1 and "private word: initech" in r.stdout
    assert ".private-words" not in "\n".join(l for l in r.stdout.splitlines() if l.startswith("FAIL"))   # the list itself is not scanned


def git(cwd, *a):
    subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@example.com", *a], cwd=cwd, check=True, capture_output=True)


def test_history_scan_finds_a_secret_that_was_deleted_later(tmp_path):
    git(tmp_path, "init", "-q")
    (tmp_path / "f.txt").write_text("API_TOKEN=" + "q1w2e3r4t5y6u7i8o9p0" + "\n")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "first")
    (tmp_path / "f.txt").write_text("clean now\n")
    git(tmp_path, "commit", "-qam", "second")
    assert run(cwd=tmp_path).returncode == 0          # the files are clean today
    h = run("--history", cwd=tmp_path)
    assert h.returncode == 1 and "secret value for API_TOKEN" in h.stdout and "commit " in h.stdout


def test_staged_scan_only_looks_at_staged_files(tmp_path):
    git(tmp_path, "init", "-q")
    (tmp_path / "ok.md").write_text("fine\n")
    (tmp_path / "bad.md").write_text("mail " + "jane" + "@" + "gmail.com" + "\n")
    git(tmp_path, "add", "ok.md")
    assert run("--staged", cwd=tmp_path).returncode == 0
    git(tmp_path, "add", "bad.md")
    assert run("--staged", cwd=tmp_path).returncode == 1


def test_the_repo_itself_is_clean():
    r = run("--root", str(ROOT), cwd=ROOT)
    assert r.returncode == 0, r.stdout


def git_id(cwd, name, email, *a):
    subprocess.run(["git", "-c", f"user.name={name}", "-c", f"user.email={email}", *a], cwd=cwd, check=True, capture_output=True)


def test_history_scan_identity_is_a_warning_once_pushed_and_a_fail_before(tmp_path):
    git_id(tmp_path, "Jane Initech", "jane@users.noreply.example", "init", "-q")
    (tmp_path / "f.txt").write_text("clean\n")
    git_id(tmp_path, "Jane Initech", "jane@users.noreply.example", "add", "-A")
    git_id(tmp_path, "Jane Initech", "jane@users.noreply.example", "commit", "-qm", "clean message")
    (tmp_path / ".private-words").write_text("initech\n")
    h = run("--history", cwd=tmp_path)
    assert h.returncode == 1, h.stdout                # not on any remote yet: one push would publish it
    assert "FAIL commit" in h.stdout and "private word in the author name (not pushed yet): initech" in h.stdout
    # a remote that has the commit makes it history already published: only a warning
    remote = tmp_path.parent / (tmp_path.name + "-remote.git")
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True, capture_output=True)
    subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "push", "-q", "origin", "HEAD:refs/heads/main"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "fetch", "-q", "origin"], cwd=tmp_path, check=True, capture_output=True)
    h = run("--history", cwd=tmp_path)
    assert h.returncode == 0, h.stdout
    assert "WARN private word in the author name: initech" in h.stdout
    assert "WARN private word in the committer name" in h.stdout
    assert "0 hit(s)" in h.stdout and "warning(s)" in h.stdout


def test_history_scan_fails_on_a_spaced_word_in_a_message_and_a_file(tmp_path):
    git_id(tmp_path, "T", "t@example.com", "init", "-q")
    (tmp_path / "f.txt").write_text("the red-fox page\n")
    (tmp_path / ".private-words").write_text("red fox\n")
    git_id(tmp_path, "T", "t@example.com", "add", "f.txt")
    git_id(tmp_path, "T", "t@example.com", "commit", "-qm", "add red_fox notes")
    h = run("--history", cwd=tmp_path)
    assert h.returncode == 1
    assert "private word in the commit message" in h.stdout and "f.txt:1 private word: red fox" in h.stdout
