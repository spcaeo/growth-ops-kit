"""growth index: the indexing step after a page is live. A fake MCP server on 127.0.0.1 stands in for the provider; the tests never
call a real indexing service and never see a real key."""
import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "kit" / "tools"))
import index_pages  # noqa: E402

KEY = "test-key-not-real-0123"
SITE = "https://example.com"


class Fake(BaseHTTPRequestHandler):
    calls = []           # (method, tool, arguments, auth, session)
    sse = False
    credits = 10
    indexed = set()

    def log_message(self, *a):
        pass

    def _send(self, obj, status=200, extra=None):
        body = json.dumps(obj)
        if Fake.sse and obj is not None:
            body, ctype = f"event: message\ndata: {body}\n\n", "text/event-stream"
        else:
            ctype = "application/json"
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body.encode())

    def do_POST(self):
        msg = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        auth, sess = self.headers.get("Authorization"), self.headers.get("Mcp-Session-Id")
        if auth != f"Bearer {KEY}":
            return self._send({"error": "no"}, 401)
        m = msg.get("method")
        if m == "initialize":
            Fake.calls.append((m, None, None, auth, sess))
            return self._send({"jsonrpc": "2.0", "id": msg["id"], "result": {"protocolVersion": "2025-03-26", "capabilities": {}}}, 200, {"Mcp-Session-Id": "sess-1"})
        if m == "notifications/initialized":
            Fake.calls.append((m, None, None, auth, sess))
            self.send_response(202)
            self.end_headers()
            return
        name, args = msg["params"]["name"], msg["params"]["arguments"]
        Fake.calls.append((m, name, args, auth, sess))
        out = {"get_credits": lambda: {"credits": Fake.credits},
               "submit_index_job": lambda: {"job": {"id": "job-7"}, "queued": len(args["urls"])},
               "get_job_status": lambda: {"status": "completed"},
               "list_job_urls": lambda: {"urls": [{"url": u, "status": "indexed" if u in Fake.indexed else "submitted"} for u in sorted(set(Fake.indexed) | {c[2]["urls"][0] for c in Fake.calls if c[1] == "submit_index_job"})]},
               "add_sitemap": lambda: {"text": "sitemap added"}, "add_indexnow_site": lambda: {"text": "site added"},
               "verify_indexnow_site": lambda: {"text": "verified"}}[name]()
        self._send({"jsonrpc": "2.0", "id": msg["id"], "result": {"content": [{"type": "text", "text": json.dumps(out)}]}})


@pytest.fixture
def server():
    Fake.calls, Fake.sse, Fake.credits, Fake.indexed = [], False, 10, set()
    srv = HTTPServer(("127.0.0.1", 0), Fake)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_port}/mcp"
    srv.shutdown()
    srv.server_close()


@pytest.fixture
def proj(tmp_path, server):
    (tmp_path / "keys.env").write_text(f"FRESHLYCITED_API_KEY={KEY}\n")
    cfg = {"name": "Demo", "site_url": SITE, "timezone": "UTC",
           "indexing": {"provider": "freshlycited", "keys_file": "keys.env", "endpoint": server}}
    (tmp_path / "growth.json").write_text(json.dumps(cfg))
    os.environ["GROWTH_PROJECT"] = str(tmp_path)
    yield tmp_path, cfg
    os.environ.pop("GROWTH_PROJECT", None)


def tool_calls(name):
    return [c for c in Fake.calls if c[1] == name]


def test_submit_smart_keeps_session_and_never_prints_key(proj, capsys):
    p, cfg = proj
    assert index_pages.cmd_index(p, cfg, [f"{SITE}/a", f"{SITE}/b#x"]) == 0
    out = capsys.readouterr().out
    assert KEY not in out and "at most 2 credit" in out
    sub = tool_calls("submit_index_job")[0]
    assert sub[2]["urls"] == [f"{SITE}/a", f"{SITE}/b"] and sub[2]["smart"] is True and "force_refresh" not in sub[2]
    assert sub[4] == "sess-1" and sub[3] == f"Bearer {KEY}"
    st = json.loads((p / "indexing" / "state.json").read_text())
    assert st["days"] and st["pages"]["/a"]["submissions"][0]["job_id"] == "job-7"
    assert KEY not in (p / "indexing" / "state.json").read_text()
    assert any("indexing" in f.read_text() for f in (p / "journal").rglob("*") if f.is_file())


def test_sse_replies_are_read(proj):
    p, cfg = proj
    Fake.sse = True
    index_pages.cmd_index(p, cfg, [f"{SITE}/a"])
    assert tool_calls("submit_index_job")


def test_refresh_prints_cost_first_and_forces(proj, capsys):
    p, cfg = proj
    index_pages.cmd_index(p, cfg, [f"{SITE}/a", f"{SITE}/b"], refresh=True)
    out = capsys.readouterr().out
    assert out.index("COST: --refresh") < out.index("sent 2")
    assert "2 credit(s)" in out and "no credit back" in out
    assert tool_calls("submit_index_job")[0][2]["force_refresh"] is True


def test_refresh_refused_when_credits_short(proj):
    p, cfg = proj
    Fake.credits = 1
    with pytest.raises(SystemExit) as e:
        index_pages.cmd_index(p, cfg, [f"{SITE}/a", f"{SITE}/b"], refresh=True)
    assert "only 1" in str(e.value) and not tool_calls("submit_index_job")


def test_dry_run_sends_nothing(proj, capsys):
    p, cfg = proj
    index_pages.cmd_index(p, cfg, [f"{SITE}/a"], dry=True)
    assert "COST" in capsys.readouterr().out and not Fake.calls


def test_daily_cap(proj):
    p, cfg = proj
    cfg["indexing"]["max_pages_per_day"] = 2
    index_pages.cmd_index(p, cfg, [f"{SITE}/a", f"{SITE}/b"])
    with pytest.raises(SystemExit) as e:
        index_pages.cmd_index(p, cfg, [f"{SITE}/c"])
    assert "daily cap" in str(e.value) and len(tool_calls("submit_index_job")) == 1


def test_other_host_and_bad_address_refused(proj):
    p, cfg = proj
    for bad in ("https://other.example/a", "/a", "ftp://example.com/a"):
        with pytest.raises(SystemExit):
            index_pages.cmd_index(p, cfg, [bad])
    assert not Fake.calls


def test_off_until_configured(tmp_path, capsys):
    cfg = {"site_url": SITE}
    assert index_pages.cmd_index(tmp_path, cfg, [f"{SITE}/a"]) == 0
    assert "indexing is off" in capsys.readouterr().out and not (tmp_path / "indexing").exists()


def test_missing_or_wrong_key_stops_without_printing_it(proj):
    p, cfg = proj
    (p / "keys.env").write_text("FRESHLYCITED_API_KEY=wrong-key\n")
    with pytest.raises(SystemExit) as e:
        index_pages.cmd_index(p, cfg, [f"{SITE}/a"])
    assert "wrong-key" not in str(e.value) and "401" in str(e.value)
    (p / "keys.env").write_text("")
    with pytest.raises(SystemExit) as e:
        index_pages.cmd_index(p, cfg, [f"{SITE}/a"])
    assert "no key" in str(e.value)


def test_status_marks_google_sees_and_measure_line(proj, capsys):
    p, cfg = proj
    assert "unknown" in index_pages.google_sees(p, "/a")["text"]
    index_pages.cmd_index(p, cfg, [f"{SITE}/a"])
    assert index_pages.google_sees(p, "/a")["sees"] is False
    index_pages.cmd_status(p, cfg)
    g = index_pages.google_sees(p, "/a")
    assert g["sees"] is False and "Google sees the page: no" in g["text"]
    Fake.indexed = {f"{SITE}/a"}
    index_pages.cmd_status(p, cfg)
    g = index_pages.google_sees(p, "/a/")
    assert g["sees"] is True and g["text"].startswith("Google sees the page: yes since 20")
    capsys.readouterr()
    index_pages.cmd_report(p, cfg)
    out = capsys.readouterr().out
    assert "yes since" in out and "credits: 10" in out and KEY not in out


def test_measure_shows_the_line_first(proj, capsys):
    import measure
    p, cfg = proj
    index_pages.cmd_index(p, cfg, [f"{SITE}/a"])
    capsys.readouterr()
    measure.show({"indexing": index_pages.google_sees(p, "/a"), "page_numbers": [], "site_numbers": [], "queries": None})
    assert capsys.readouterr().out.startswith("== Google sees the page: no")


def test_setup_calls_sitemap_and_indexnow(proj, capsys):
    p, cfg = proj
    cfg["indexing"]["indexnow_key"] = "abc123"
    index_pages.cmd_setup(p, cfg)
    assert [c[1] for c in Fake.calls if c[1]] == ["add_sitemap", "add_indexnow_site", "verify_indexnow_site"]
    assert tool_calls("add_sitemap")[0][2]["url"] == f"{SITE}/sitemap.xml"


def test_manual_prints_steps(tmp_path, capsys):
    cfg = {"site_url": SITE, "timezone": "UTC", "indexing": {"provider": "manual"}}
    (tmp_path / "growth.json").write_text(json.dumps(cfg))
    os.environ["GROWTH_PROJECT"] = str(tmp_path)
    try:
        index_pages.cmd_index(tmp_path, cfg, [f"{SITE}/a"])
    finally:
        os.environ.pop("GROWTH_PROJECT")
    out = capsys.readouterr().out
    assert "Request indexing" in out and "Inspect any URL" in out
    assert index_pages.load_state(tmp_path)["days"] == {}      # manual steps are not pages sent to a service


def test_indexnow_posts_key_file_and_urls(tmp_path, server, capsys):
    got = []

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            got.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            self.send_response(200)
            self.end_headers()
    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    cfg = {"site_url": SITE, "timezone": "UTC", "indexing": {"provider": "indexnow", "indexnow_key": "k123",
           "indexnow_endpoint": f"http://127.0.0.1:{srv.server_port}/indexnow"}}
    (tmp_path / "growth.json").write_text(json.dumps(cfg))
    os.environ["GROWTH_PROJECT"] = str(tmp_path)
    try:
        index_pages.cmd_index(tmp_path, cfg, [f"{SITE}/a"])
    finally:
        os.environ.pop("GROWTH_PROJECT")
        srv.shutdown()
        srv.server_close()
    assert got[0]["urlList"] == [f"{SITE}/a"] and got[0]["keyLocation"] == f"{SITE}/k123.txt" and got[0]["host"] == "example.com"
    assert "Google does not use IndexNow" in capsys.readouterr().out


def test_key_is_never_sent_over_plain_http_to_another_host():
    with pytest.raises(SystemExit):
        index_pages.Mcp("http://freshlycited.example/mcp", KEY)


def test_default_endpoint_is_the_providers_https_address_and_tests_never_use_it():
    assert index_pages.DEFAULT_ENDPOINT == "https://freshlycited.com/mcp"


def test_growth_command_exists():
    r = subprocess.run([sys.executable, str(ROOT / "growth"), "index", "--help"], capture_output=True, text=True)
    assert r.returncode == 0 and "growth index" in r.stdout


def test_wizard_indexing_step_is_skippable_and_sets_config(tmp_path):
    import wizard
    (tmp_path / "growth.json").write_text(json.dumps({"site_url": SITE}))
    assert "skipped" in wizard.step_indexing(wizard.Session(tmp_path, {"indexing": "later"}))
    r = wizard.step_indexing(wizard.Session(tmp_path, {"indexing": {"provider": "indexnow", "indexnow_key": "k"}}))
    cfg = json.loads((tmp_path / "growth.json").read_text())
    assert cfg["indexing"]["provider"] == "indexnow" and "indexnow" in r


def test_job_urls_reads_the_providers_real_shape():
    """The provider's list_job_urls replies {items: [...]} with indexed as 1/0/None (shape from a real reply, 19 Nov 2026)."""
    import importlib, sys as _s
    from pathlib import Path as _P
    _s.path.insert(0, str(_P(__file__).resolve().parent.parent / "kit" / "tools"))
    ip = importlib.import_module("index_pages")
    out = {"items": [{"url": "https://example.com/a/", "indexed": 1, "state": "completed"},
                     {"url": "https://example.com/b/", "indexed": 0, "state": "completed"},
                     {"url": "https://example.com/c/", "indexed": None, "state": "pending"}], "total": 3, "page": 1, "page_size": 200}
    rows = {u: seen for u, seen, _ in ip.job_urls(out)}
    assert rows == {"https://example.com/a/": True, "https://example.com/b/": False, "https://example.com/c/": False}
