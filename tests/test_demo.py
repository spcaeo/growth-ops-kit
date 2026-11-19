"""The demo site end to end: serve examples/demo-site/site on a free 127.0.0.1 port (Python's http.server, our own pid,
stopped at the end) and run the gate on two pages. The strong page (/lawn-mowing) has 0 FAIL among the checks that read the
live page; the deliberately weak page (/lawn-offers) FAILs the specific checks that should catch it. No network beyond
127.0.0.1, no keys, no money."""
import os
import re
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "examples" / "demo-site"
GATE = ROOT / "kit" / "tools" / "gate.py"


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def base():
    port = free_port()
    proc = subprocess.Popen([sys.executable, str(DEMO / "serve.py"), str(port)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/robots.txt", timeout=1).read()
                break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError("the demo server did not start")
        yield f"http://127.0.0.1:{port}"
    finally:
        proc.terminate()                    # only our own pid
        proc.wait(timeout=10)


def gate(base, path, *extra):
    env = {k: v for k, v in os.environ.items() if k != "GROWTH_PROJECT"}
    env["GROWTH_PROJECT"] = str(DEMO / "project")
    r = subprocess.run([sys.executable, str(GATE), "page", path, "--url", base + path, "--type", "money", "--no-browser", *extra],
                       capture_output=True, text=True, env=env, cwd=DEMO / "project", timeout=300)
    lines = r.stdout.splitlines()
    fails = {m.group(1) for l in lines if l.startswith("FAIL") for m in [re.search(r"\[([\w.-]+)\]", l)] if m}
    return r, lines, fails


@pytest.fixture(scope="module")
def strong(base):
    return gate(base, "/lawn-mowing", "--needs", "live")


@pytest.fixture(scope="module")
def weak(base):
    return gate(base, "/lawn-offers", "--needs", "live")


def test_the_demo_site_serves_its_pages(base):
    for p in ("/", "/lawn-mowing", "/blog", "/blog/best-mowing-height", "/about", "/contact", "/sitemap.xml", "/robots.txt"):
        assert urllib.request.urlopen(base + p, timeout=5).status == 200, p


def test_strong_page_has_no_fail_in_the_live_checks(strong):
    r, lines, fails = strong
    assert fails == set(), "\n".join(l for l in lines if l.startswith("FAIL"))
    assert r.returncode == 0
    summary = next(l for l in lines if l.startswith("Gate:"))
    assert "0 FAIL" in summary and "PASS" in summary
    ok = sum(1 for l in lines if l.startswith("OK"))
    assert ok >= 50, f"only {ok} live checks said OK"


def test_strong_page_skips_what_does_not_apply_never_fakes_ok(strong):
    _, lines, _ = strong
    skips = [l for l in lines if l.startswith("SKIP")]
    assert any(l.startswith("SKIP dialog.call:") and "feature" in l for l in skips)         # a feature this site does not have
    assert any(l.startswith("SKIP words.named-author:") for l in skips)                      # no author set in growth.json
    assert not any(l.startswith("OK") and "[dialog.call]" in l for l in lines)


def test_weak_page_fails_the_checks_that_should_catch_it(weak):
    r, lines, fails = weak
    assert r.returncode == 1
    must = {"words.hype", "words.placeholders", "words.no-customers", "cta.one-path", "cta.label-same", "cta.no-bare-book",
            "seo.canonical", "seo.basics", "crumbs.visible", "faq.box", "geo.answer-passage", "geo.updated", "seo.alt",
            "schema.org-id", "seo.headings", "motion.reveal", "layout.folds-distinct"}
    assert must <= fails, f"these checks did not fire: {sorted(must - fails)}"
    assert "BLOCKED" in next(l for l in lines if l.startswith("Gate:"))


def test_weak_page_fix_lines_say_what_to_do(weak):
    _, lines, _ = weak
    hype = next(l for l in lines if "[words.hype]" in l)
    assert "->" in hype and "'" in hype                       # it names the word and gives the fix


def test_whole_gate_skips_the_nextjs_adapter_on_a_static_site(base):
    r, lines, _ = gate(base, "/lawn-mowing")
    nx = [l for l in lines if l.startswith("SKIP") and "no adapter for static" in l]
    assert len(nx) >= 40, f"{len(nx)} adapter checks skipped"
    assert any(l.startswith("SKIP repo.no-secrets: no adapter for static") for l in lines)
    assert not any(l.startswith("OK") and "[repo." in l for l in lines)
    summary = next(l for l in lines if l.startswith("Gate:"))
    assert re.search(r"\d+ SKIP", summary)


def test_the_gate_refuses_the_real_site(base):
    env = {**os.environ, "GROWTH_PROJECT": str(DEMO / "project")}
    r = subprocess.run([sys.executable, str(GATE), "page", "/", "--url", "https://brightline.example/", "--type", "core"],
                       capture_output=True, text=True, env=env, cwd=DEMO / "project")
    assert r.returncode == 2 and "Refusing to run the gate against the live site" in r.stderr


def test_inventory_reads_the_demo_sitemap_offline(demo_project, base):
    env = {**os.environ, "GROWTH_PROJECT": str(demo_project)}
    r = subprocess.run([sys.executable, str(ROOT / "kit" / "tools" / "inventory.py"), "--base", base,
                        "--offline", str(DEMO / "site" / "sitemap.xml")], capture_output=True, text=True, env=env, cwd=demo_project)
    assert r.returncode == 0, r.stderr
    import json
    inv = json.loads((demo_project / "inventory" / "inventory.json").read_text())
    rows = {p["path"]: p for p in inv["pages"]}
    assert set(rows) == {"/", "/lawn-mowing", "/blog", "/blog/best-mowing-height", "/about", "/contact"}
    assert rows["/lawn-mowing"]["money_page"] and rows["/lawn-mowing"]["status"] == "live"
    assert rows["/lawn-mowing"]["h1"] == "Lawn mowing with a fixed quote" and rows["/lawn-mowing"]["words"] > 400
    assert (demo_project / "inventory" / "INVENTORY.md").read_text().startswith("# brightline.example page inventory")


def _chromium_ready():
    if os.environ.get("GROWTH_SKIP_BROWSER") == "1":
        return False
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            b.close()
        return True
    except Exception:  # noqa: BLE001
        return False


def test_browser_checks_pass_on_the_strong_page_when_a_browser_is_installed(base):
    """Contrast at rest, hover and focus, and phone readability, measured in a real headless browser (closed at the end).
    Skipped, never faked, when no browser is installed: setup.sh --browsers installs one."""
    if not _chromium_ready():
        pytest.skip("no headless chromium (python3 -m playwright install chromium)")
    env = {**os.environ, "GROWTH_PROJECT": str(DEMO / "project")}
    r = subprocess.run([sys.executable, str(GATE), "page", "/lawn-mowing", "--url", base + "/lawn-mowing", "--type", "money",
                        "--only", "ui.contrast-states,ui.phone", "--no-link-status"], capture_output=True, text=True, env=env,
                       cwd=DEMO / "project", timeout=300)
    assert "FAIL" not in r.stdout.split("Gate:")[0], r.stdout
    assert sum(1 for l in r.stdout.splitlines() if l.startswith("OK")) == 2, r.stdout


def test_a_static_site_with_no_checkout_can_pass_the_evidence_checks(base, tmp_path):
    """No site_repo: the evidence checks date the page's last change from the site folder (growth.json site_dir), so they can
    pass; they used to FAIL with 'input missing: site checkout' and no static site could ever be READY."""
    import json
    import shutil
    proj = tmp_path / "project"
    shutil.copytree(DEMO / "project", proj)
    cfg = json.loads((proj / "growth.json").read_text())
    cfg["site_dir"] = str(DEMO / "site")
    (proj / "growth.json").write_text(json.dumps(cfg))
    shots = proj / "research" / "lawn-mowing-shots"
    shots.mkdir(parents=True)
    for w in (360, 390, 820, 1280, 1366, 1920):
        (shots / f"hero-{w}.png").write_bytes(b"\x89PNG")
    now = time.strftime("%Y-%m-%d %H:%M")
    with open(proj / "journal" / "entries.jsonl", "a") as f:
        for i, tag in enumerate(("click-test", "share-preview")):
            f.write(json.dumps({"id": f"J-{i}", "at": now, "kind": "note", "pages": ["/lawn-mowing"], "tags": [tag], "title": tag, "text": tag, "status": "done"}) + "\n")
    env = {k: v for k, v in os.environ.items() if k != "GROWTH_PROJECT"}
    env["GROWTH_PROJECT"] = str(proj)
    r = subprocess.run([sys.executable, str(GATE), "page", "/lawn-mowing", "--url", base + "/lawn-mowing", "--type", "money", "--no-browser",
                        "--only", "ev.shots-widths,ev.shots-1366-390,ev.share-preview,ev.click-test"],
                       capture_output=True, text=True, env=env, cwd=proj, timeout=300)
    assert "site checkout" not in r.stdout, r.stdout
    oks = [l for l in r.stdout.splitlines() if l.startswith("OK")]
    assert len(oks) == 4, r.stdout
    # and with nothing to date the change by, it says so plainly instead of failing on a missing checkout
    cfg["site_dir"] = ""
    (proj / "growth.json").write_text(json.dumps(cfg))
    r = subprocess.run([sys.executable, str(GATE), "page", "/lawn-mowing", "--url", base + "/lawn-mowing", "--type", "money", "--no-browser",
                        "--only", "ev.click-test"], capture_output=True, text=True, env=env, cwd=proj, timeout=300)
    assert "SKIP ev.click-test: no way to date this page's last change" in r.stdout, r.stdout
