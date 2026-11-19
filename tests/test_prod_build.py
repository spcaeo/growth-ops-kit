"""READY runs on a production build served locally (#57): the gate refuses a page a dev server answered, and
`growth serve <dist>` serves a built folder. Example markup only; the server binds 127.0.0.1 on a free port and is shut down."""
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from gatelib import CHECKS
from gatelib.core import Ctx, run_check

PROD = "<html><head><title>T</title><script type='module' src='/_astro/page.Ab12.js'></script></head><body><main><h1>T</h1></main></body></html>"
DEV = {
    "vite": "<script type='module' src='/@vite/client'></script>",
    "astro toolbar": "<astro-dev-toolbar></astro-dev-toolbar>",
    "astro source": "<div data-astro-source-file='/src/x.astro'>x</div>",
    "next hmr": "<script src='/_next/webpack-hmr'></script>",
    "webpack dev": "<script src='/main.abc.hot-update.js'></script>",
    "live reload": "<script src='/livereload.js?port=1313'></script>",
}


def line(html, cfg=None):
    with tempfile.TemporaryDirectory() as tmp:
        ctx = Ctx(project=Path(tmp), path="/x/", url="http://127.0.0.1:9/x/", ptype="post", cfg=cfg or {}, html=html, status=200)
        run_check(ctx, CHECKS["ev.prod-build"])
        return ctx.lines[0]


def test_a_production_page_passes():
    assert line(PROD).level == "OK"


@pytest.mark.parametrize("name", DEV)
def test_a_dev_server_page_fails_and_says_what_to_run(name):
    ln = line(PROD.replace("</body>", DEV[name] + "</body>"))
    assert ln.level == "FAIL" and "dev server" in ln.what and "growth serve" in ln.fix


def test_the_fix_names_the_sites_own_preview_command_when_recorded():
    ln = line(PROD.replace("</body>", DEV["vite"] + "</body>"), {"preview_cmd": "npm run preview"})
    assert "npm run preview" in ln.fix


def test_growth_serve_serves_a_built_folder(tmp_path):
    from serve import make_server
    (tmp_path / "about").mkdir()
    (tmp_path / "about" / "index.html").write_text("<h1>About</h1>")
    (tmp_path / "pricing.html").write_text("<h1>Pricing</h1>")
    (tmp_path / "404.html").write_text("<h1>Gone</h1>")
    srv = make_server(tmp_path, 0)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        for path, want in (("/about/", "About"), ("/pricing", "Pricing")):
            with urllib.request.urlopen(base + path) as r:
                assert want in r.read().decode()
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(base + "/nope/")
        assert e.value.code == 404 and "Gone" in e.value.read().decode()
    finally:
        srv.shutdown()
        srv.server_close()
        t.join(5)
