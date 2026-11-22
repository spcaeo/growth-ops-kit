"""2.5.0: hero.unique (157) reads the served page and its siblings on any stack: a shared hero design, picture or
animation among siblings fails."""
import functools
import http.server
import json
import socket
import tempfile
import threading
from pathlib import Path
from urllib.request import urlopen

import pytest

from gatelib import CHECKS
from gatelib.core import Ctx, run_check

FRAME = ('<section class="hero"><div class="hero__text"><h1>{t}</h1><p>{t} lead line.</p></div>'
         '<figure class="draw"><svg><path d="{d}"/><rect width="9" height="9"/></svg></figure></section>')
OTHER = ('<section class="intro"><h1>{t}</h1><div class="tool"><input type="range"><output>4</output></div>'
         '<ol class="steps"><li>a</li><li>b</li></ol></section>')
D1 = "M0 0 L10 10 L20 0 L30 10 L40 0 L50 10 L60 0 L70 10"
D2 = "M5 5 C10 40 30 40 60 5 S90 40 120 5 L130 30"


def page(sec):
    return f"<html><body><main>{sec}<section><h2>More</h2></section></main></body></html>"


PAGES = {"c/a": page(FRAME.format(t="A", d=D1)), "c/b": page(FRAME.format(t="B", d=D2)), "c/x": page(OTHER.format(t="X"))}


@pytest.fixture(scope="module")
def site():
    with tempfile.TemporaryDirectory() as d:
        for k, v in PAGES.items():
            (Path(d) / k).mkdir(parents=True)
            (Path(d) / k / "index.html").write_text(v)
        proj = Path(d) / "proj"
        (proj / "inventory").mkdir(parents=True)
        (proj / "inventory" / "inventory.json").write_text(json.dumps({"pages": [{"path": "/" + k + "/"} for k in PAGES]}))
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        quiet = type("H", (http.server.SimpleHTTPRequestHandler,), {"log_message": lambda *a: None})
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), functools.partial(quiet, directory=d))
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        try:
            yield f"http://127.0.0.1:{port}", proj
        finally:
            srv.shutdown()
            srv.server_close()
            t.join(5)


def line(site, name):
    base, proj = site
    url = f"{base}/{name}/"
    c = Ctx(project=proj, path=f"/{name}/", key="x", ptype="post", cfg={"trailing_slash": True}, html=urlopen(url).read().decode(),
            url=url, status=200)
    run_check(c, CHECKS["hero.unique"])
    return c.lines[-1]


def test_two_siblings_with_one_hero_design_fail(site):
    ln = line(site, "c/a")
    assert ln.level == "FAIL" and "same hero design as /c/b" in ln.what


def test_a_hero_of_its_own_passes(site):
    assert line(site, "c/x").level == "OK"
