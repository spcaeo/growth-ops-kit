"""The page tracker on a project folder: it reads the demo site's sitemap, groups the pages, writes its data into the project's
page-tracker/ folder (never into the kit), runs with every connector off and says so, and serves the dashboard from the kit and
the data from the project. No network beyond 127.0.0.1; Google's status feed is switched off."""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parent.parent
TRACKER = ROOT / "kit" / "page-tracker"
DEMO = ROOT / "examples" / "demo-site"


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def served(demo_project):
    port = free_port()
    srv = subprocess.Popen([sys.executable, str(DEMO / "serve.py"), str(port)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/robots.txt", timeout=1).read()
                break
            except OSError:
                time.sleep(0.1)
        cfg = json.loads((demo_project / "growth.json").read_text())
        cfg["connectors"]["google_updates"]["on"] = False
        cfg["sitemap_url"] = f"http://127.0.0.1:{port}/sitemap.xml"
        cfg["tracker_port"] = free_port()
        (demo_project / "growth.json").write_text(json.dumps(cfg))
        yield demo_project, cfg
    finally:
        srv.terminate()
        srv.wait(timeout=10)


def run(project, script, *args):
    env = {**os.environ, "GROWTH_PROJECT": str(project), "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run([sys.executable, str(TRACKER / script), *args], capture_output=True, text=True, env=env, cwd=project, timeout=120)


def test_sync_and_report_write_into_the_project_only(served):
    project, cfg = served
    before = {p.relative_to(ROOT) for p in TRACKER.rglob("*") if p.is_file()}
    s = run(project, "tracker.py", "sync")
    assert s.returncode == 0, s.stderr
    assert "6 pages from the sitemap" in s.stdout and "skald: off" in s.stdout and "search console: off" in s.stdout
    r = run(project, "tracker.py", "report")
    assert r.returncode == 0, r.stderr
    data = json.loads((project / "page-tracker" / "data.json").read_text())
    assert {p["path"] for p in data["pages"]} == {"/", "/lawn-mowing", "/blog", "/blog/best-mowing-height", "/about", "/contact"}
    assert data["config"]["site_url"] == "https://brightline.example"
    assert data["config"]["sources"]["skald"] is False and data["config"]["sources"]["search_console"] is False
    assert data["release"]["version"] == (ROOT / "kit" / "VERSION").read_text().strip() and data["release"]["build"] == 1
    assert (project / "page-tracker" / "tracker.db").is_file()
    after = {p.relative_to(ROOT) for p in TRACKER.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
    assert after - {p for p in before} == set(), "the tracker wrote a file inside the kit"


def test_a_missing_key_is_a_note_not_a_crash(served, tmp_path):
    project, cfg = served
    cfg["connectors"]["skald"] = {"on": True}
    cfg["connectors"]["search_console"] = {"on": True, "via": "skald"}
    cfg["keys_file"] = str(tmp_path / "no-such.env")
    (project / "growth.json").write_text(json.dumps(cfg))
    s = run(project, "tracker.py", "sync")
    assert s.returncode == 0, s.stderr
    assert "connector 'skald' is on in growth.json but the keys file was not found: " in s.stderr
    assert "no-such.env" in s.stderr
    assert "Traceback" not in s.stderr


def test_clusters_come_from_the_silos_and_core_pages(served):
    project, cfg = served
    cfg["silos"] = {"lawn-mowing": "Lawn mowing"}
    (project / "growth.json").write_text(json.dumps(cfg))
    code = "import config; print(config.cluster_of('/'), config.cluster_of('/lawn-mowing/x'), config.cluster_of('/zzz'), config.cluster_order())"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=TRACKER,
                         env={**os.environ, "GROWTH_PROJECT": str(project)})
    assert out.stdout.split()[:3] == ["core", "lawn-mowing", "other"], out.stderr


def test_the_dashboard_serves_kit_files_and_project_data_and_hides_secrets(served):
    project, cfg = served
    assert run(project, "tracker.py", "sync").returncode == 0 and run(project, "tracker.py", "report").returncode == 0
    port = cfg["tracker_port"]
    srv = subprocess.Popen([sys.executable, str(TRACKER / "serve.py")], env={**os.environ, "GROWTH_PROJECT": str(project)},
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=project)
    try:
        for _ in range(50):
            try:
                html = urllib.request.urlopen(f"http://127.0.0.1:{port}/dashboard.html", timeout=1).read().decode()
                break
            except OSError:
                time.sleep(0.1)
        assert "<title>Page tracker</title>" in html
        data = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/data.json", timeout=2).read())
        assert len(data["pages"]) == 6
        for hidden in ("/tracker.db", "/tracker.py", "/config.py"):
            with pytest.raises(urllib.error.HTTPError) as e:
                urllib.request.urlopen(f"http://127.0.0.1:{port}{hidden}", timeout=2)
            assert e.value.code == 404, hidden
    finally:
        srv.terminate()
        srv.wait(timeout=10)
