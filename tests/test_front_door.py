"""The front door: `growth setup`, `page`, `check`, `ready`, `status` for a person who is not an engineer. A stranger test drives
`growth setup` on a fixture site and counts the questions; every prompt must be plain words, never a command or JSON."""
import http.server
import json
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_wizard import answers  # noqa: E402
from wizard_helpers import ROOT, growth, make_site  # noqa: E402

MAX_QUESTIONS = 8          # website, country, approver, live-site rule, safety helpers, browser done, region read, region right


def run_setup(tmp, port=18999, repo_answers=True):
    repo, index = make_site(tmp)
    f = answers(tmp, repo, live_rule={"rule": "no-crawl", "preview_url": f"http://127.0.0.1:{port}"},
                browser={"name": "Browser 1"}, region={"seen": "United States", "owner_confirmed": True})
    r = growth(tmp, "setup", str(tmp / "proj"), "--site", "https://shop.example", "--answers", str(f), "--sitemap", str(index))
    return tmp / "proj", r, repo


def test_setup_without_a_terminal_keeps_the_question_protocol(tmp_path):
    repo, index = make_site(tmp_path)
    r = growth(tmp_path, "setup", str(tmp_path / "proj"), "--site", "https://shop.example", "--sitemap", str(index))
    assert r.returncode == 3 and "QUESTION market" in r.stdout          # an agent still gets QUESTION <step> and exit 3
    assert "Setup is not finished" in r.stdout.splitlines()[-1]


def test_setup_ends_with_one_line_saying_done_and_the_next_command(tmp_path):
    proj, r, _ = run_setup(tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.splitlines()[-1] == "Setup done. Next: growth page /your-page"
    assert "Google region:** United States" in (proj / "SETUP.md").read_text()


def test_the_wizard_says_the_problem_in_plain_words_before_the_command(tmp_path):
    repo, index = make_site(tmp_path)
    f = answers(tmp_path, repo)
    r = growth(tmp_path, "setup", str(tmp_path / "proj"), "--site", "https://shop.example", "--answers", str(f), "--sitemap", str(index))
    out = r.stdout
    assert r.returncode == 3
    assert out.index("The research browser is not connected yet.") < out.index("WAITING browser")
    assert "growth wizard confirm browser" in out                       # the exact command is still there, second


def test_a_stranger_answers_a_handful_of_plain_questions(tmp_path, monkeypatch):
    """Drive the interactive setup in-process, answering like a marketing person, and count what is asked."""
    import front_door
    repo, index = make_site(tmp_path)
    (tmp_path / "home").mkdir(exist_ok=True)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GROWTH_CRONTAB", "")
    monkeypatch.setenv("GROWTH_LAUNCHD_DIRS", str(tmp_path / "none"))
    monkeypatch.delenv("GROWTH_PROJECT", raising=False)
    monkeypatch.chdir(repo)                                              # run from the site's own code folder: it is found, not asked
    asked = []

    def person(prompt):
        asked.append(prompt)
        p = prompt.lower()
        for key, reply in (("address", "https://shop.example"), ("country", ""), ("approves", "Pat"), ("live website", ""),
                           ("safety helpers", ""), ("done?", "y"), ("what does it say", "United States"), ("right for", "y")):
            if key in p:
                return reply
        raise AssertionError(f"an unexpected question: {prompt!r}")

    rc = front_door.cmd_setup([str(tmp_path / "proj"), "--sitemap", str(index)], ask=person)
    assert rc == 0
    proj = tmp_path / "proj"
    import wizard_state as ws
    steps = ws.load(proj)["steps"]
    assert all(steps[s]["status"] in ("done", "declined") for s in steps), {s: steps[s]["status"] for s in steps}
    cfg = json.loads((proj / "growth.json").read_text())
    assert cfg["market"]["primary_country"] == "US" and cfg["live_site_rule"] == "no-crawl" and cfg["preview_url"] == "http://localhost:4321"
    print(f"\nSTRANGER TEST: {len(asked)} questions asked")
    assert len(asked) <= MAX_QUESTIONS, asked
    for q in asked:                                                      # plain words: no command, no JSON, no flag
        assert "growth " not in q and "--" not in q and "{" not in q and "answer:" not in q, q


def test_a_job_from_start_to_check_and_status(tmp_path):
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
        def translate_path(self, path):
            return str(tmp_path / "www" / path.lstrip("/").rstrip("/") / "index.html") if path != "/" else str(tmp_path / "www" / "index.html")
    (tmp_path / "www" / "blog" / "post-a").mkdir(parents=True)
    (tmp_path / "www" / "blog" / "post-a" / "index.html").write_text("<html><head><title>x</title></head><body><h1>Hi</h1></body></html>")
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Quiet)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        proj, r, _ = run_setup(tmp_path, port=srv.server_address[1])
        assert r.returncode == 0, r.stdout
        job = growth(tmp_path, "page", "/blog/post-a", cwd=proj)
        assert job.returncode == 0, job.stdout + job.stderr
        assert "Opened T2" in job.stdout and "Brief for your agent: research/briefs/blog-post.md" in job.stdout
        assert job.stdout.rstrip().splitlines()[-1].startswith("Next:") and (proj / "research" / "briefs" / "blog-post.md").is_file()
        task = json.loads((proj / "docs" / "tasks.json").read_text())["tasks"][-1]
        assert task["page"] == {"path": "/blog/post-a", "type": "post", "key": "blog-post", "playbook": "update-post"} and task["steps"]
        again = growth(tmp_path, "page", "/blog/post-a", cwd=proj)
        assert "already open: T2" in again.stdout
        status = growth(tmp_path, "status", cwd=proj).stdout
        assert "Page: /blog/post-a" in status and "Setup" in status and status.rstrip().splitlines()[-1].startswith("Next:")
        chk = growth(tmp_path, "check", "--no-browser", cwd=proj)
        first = chk.stdout.splitlines()[0]
        assert chk.returncode == 1 and "problems on /blog/post-a" in first and chk.stdout.count("\n  - ") == 3
        assert "Rule gate: /blog/post-a" in chk.stdout and "Gate:" in chk.stdout        # the exact lines follow the summary
        rdy = growth(tmp_path, "ready", cwd=proj)
        assert rdy.returncode != 0 and "ready" in rdy.stdout.lower()
    finally:
        srv.shutdown()
        srv.server_close()


def test_page_says_what_to_do_outside_a_project(tmp_path):
    r = growth(tmp_path, "page", "/x", cwd=tmp_path)
    assert r.returncode == 2 and "growth setup" in r.stdout


def test_doctor_shows_four_stages_to_a_person_and_every_step_with_verbose(tmp_path):
    proj, _, _ = run_setup(tmp_path)
    short = growth(tmp_path, "doctor", "--summary", cwd=proj).stdout
    for stage in ("Your site", "Access", "Agent setup", "Research browser"):
        assert stage in short
    assert "A13 " not in short and "▰" in short
    full = growth(tmp_path, "doctor", "--verbose", cwd=proj).stdout
    assert "A13 Agent harness complete" in full
    assert growth(tmp_path, "doctor", cwd=proj).stdout == full                      # no terminal (a pipe, an agent): every step, as before
