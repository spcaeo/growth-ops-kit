"""page_snapshot --base reads the page from a preview or local build, never the live site (the demo's real host does not
resolve, so a live request fails the run), records the base it read, and finds a page whose inventory row keeps the
site's trailing slash. Skald is off: no network beyond 127.0.0.1."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "examples" / "demo-site"


@pytest.fixture
def served():
    sys.path.insert(0, str(DEMO))
    import threading
    import serve
    srv = serve.make_server(0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{srv.server_address[1]}"
    finally:
        srv.shutdown()
        srv.server_close()


def run(project, *args):
    env = {**os.environ, "GROWTH_PROJECT": str(project)}
    return subprocess.run([sys.executable, str(ROOT / "kit" / "tools" / "page_snapshot.py"), *args],
                          capture_output=True, text=True, env=env, cwd=project, timeout=60)


def inventory(project, path):
    (project / "inventory").mkdir(exist_ok=True)
    row = {"path": path, "status": "live", "silo": "Lawn mowing", "type": "pillar", "pillar": path, "stage": "BOFU"}
    (project / "inventory" / "inventory.json").write_text(json.dumps({"meta": {}, "pages": [row]}))


def test_the_snapshot_reads_the_base_and_records_it(demo_project, served):
    inventory(demo_project, "/lawn-mowing")
    r = run(demo_project, "/lawn-mowing", "--base", served, "--task", "T1", "--action", "update start")
    assert r.returncode == 0, r.stderr
    snap = json.loads(next((demo_project / "inventory" / "pages" / "lawn-mowing").glob("*.json")).read_text())
    assert snap["base"] == served and snap["elements"]["h1"] == ["Lawn mowing with a fixed quote"]
    md = next((demo_project / "inventory" / "pages" / "lawn-mowing").glob("*.md")).read_text()
    assert f"## Page elements (read from {served})" in md


def test_a_trailing_slash_inventory_row_is_found_and_used_as_is(demo_project, served):
    inventory(demo_project, "/lawn-mowing/")          # the sitemap's form; the demo serves only /lawn-mowing
    r = run(demo_project, "/lawn-mowing", "--base", served)
    out = r.stdout + r.stderr
    assert "is not a live page" not in out            # the row was matched despite the slash
    assert r.returncode != 0 and "404" in out         # and the page was requested as the row says: /lawn-mowing/
