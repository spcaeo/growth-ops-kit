"""Kit friction 43 and 44, with fixture pages in a real headless browser (file:// pages, no network).
43: a focus ring is judged against the colour OUTSIDE the element, not the button's own fill; the text colour of a link comes from
    the link's own words, not from a child span inside it.
44: a link inline in a sentence is not a too-small tap target (WCAG 2.5.8); a footer list of links still is."""
import json
import os
import re
import subprocess
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "kit" / "tools"))
pytest.importorskip("playwright")
import contrast_check  # noqa: E402
import phone_check  # noqa: E402


def page(tmp_path, body, css="", name="p.html"):
    f = tmp_path / name
    f.write_text(f"<!doctype html><meta name=viewport content='width=device-width'><style>body{{margin:0;font:16px sans-serif;background:#fff}}{css}</style>{body}")
    return f.as_uri()


def browser_ok():
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            p.chromium.launch(headless=True).close()
        return True
    except Exception:  # noqa: BLE001
        return False


pytestmark = pytest.mark.skipif(not browser_ok(), reason="no headless Chromium here")

RING = "a.b{display:inline-block;padding:10px 16px;background:#1a1a8c;color:#fff;text-decoration:none}a.b:focus{outline:3px solid %s;outline-offset:%s}"


def test_ring_judged_against_outside_not_the_buttons_fill(tmp_path):
    # ring dark blue on a white page: 3:1 against white is fine even though it nearly matches the button's own dark fill
    probs, _ = contrast_check.check(page(tmp_path, "<a class=b href='#x'>Book now</a>", RING % ("#1a1a8c", "2px")))
    assert not [p for p in probs if "focus ring" in p], probs


def test_ring_that_vanishes_on_the_page_is_still_caught(tmp_path):
    # light ring on a white page passes against a dark fill but cannot be seen outside the button
    probs, _ = contrast_check.check(page(tmp_path, "<a class=b href='#x'>Book now</a>", RING % ("#e8e8f5", "2px")))
    assert any("focus ring" in p and "#ffffff" in p for p in probs), probs


def test_ring_inside_the_button_uses_the_fill(tmp_path):
    ok, _ = contrast_check.check(page(tmp_path, "<a class=b href='#x'>Book now</a>", RING % ("#ffffff", "-4px")))
    assert not [p for p in ok if "focus ring" in p], ok


def test_ring_over_a_dark_section_uses_that_section(tmp_path):
    body = "<div style='background:#111;padding:20px'><a class=b href='#x'>Book now</a></div>"
    probs, _ = contrast_check.check(page(tmp_path, body, RING % ("#1a1a8c", "2px")))
    assert any("focus ring" in p and "#111111" in p for p in probs), probs


def test_link_text_colour_is_the_links_own_not_a_child(tmp_path):
    # "Move <b>offer</b>": the link's own words are dark on white; the child is white (a badge on its own dark chip). Judged by the link.
    body = "<a href='#x' style='color:#222'>Move <span style='color:#fff;background:#000'>offer</span></a>"
    probs, rows = contrast_check.check(page(tmp_path, body))
    assert not probs, probs
    assert {r["fg"] for r in rows if r["text"].startswith("Move")} == {"#222222"}


def test_label_inside_an_icon_button_is_still_read(tmp_path):
    body = "<a href='#x' style='background:#fff'><svg width=10 height=10></svg><span style='color:#ddd'>Pay</span></a>"
    probs, _ = contrast_check.check(page(tmp_path, body))
    assert any("Pay" in p for p in probs), probs


def taps(tmp_path, body, css=""):
    return [p for p in phone_check.check(page(tmp_path, body, css), 390) if p.startswith("taps")]


def test_inline_link_in_a_sentence_is_not_a_small_target(tmp_path):
    body = "<footer><p>Read our <a href='/privacy'>privacy policy</a> and the <a href='/terms'>terms</a> before you book.</p></footer>"
    assert taps(tmp_path, body) == []


def test_footer_list_of_links_with_separators_is_still_small(tmp_path):
    body = "<footer><a href='/a'>Privacy</a> | <a href='/b'>Terms</a> &middot; <a href='/c'>Help</a></footer>"
    assert len(taps(tmp_path, body)) == 3


def test_a_link_alone_in_a_list_item_is_still_small(tmp_path):
    assert taps(tmp_path, "<footer><ul><li><a href='/a'>Pricing</a></li></ul></footer>")


def test_a_big_enough_link_in_a_sentence_and_a_button_are_unchanged(tmp_path):
    body = "<footer><button style='width:10px;height:10px'>x</button></footer>"
    assert taps(tmp_path, body)


def test_inline_flex_link_with_an_icon_in_a_sentence_is_not_a_small_target(tmp_path):
    # friction 44: the footer's "A <a style=inline-flex>Space-O Technologies <svg/></a> company" was counted on every page
    css = "footer p a{display:inline-flex;align-items:center;gap:3px}"
    body = ("<footer><p>A <a href='https://example.com'>Parent Co<svg width='12' height='12'></svg></a> company, "
            "since 2010.</p></footer>")
    assert taps(tmp_path, body, css) == []


def test_inline_block_links_with_only_separators_are_still_small(tmp_path):
    css = "footer a{display:inline-block}"
    body = "<footer><a href='/a'>Privacy</a> | <a href='/b'>Terms</a></footer>"
    assert len(taps(tmp_path, body, css)) == 2


# ---- 2.8.0: the same checks, faster: one browser, look-alike controls measured once, measurements kept between runs ----
LIST = ("<header><nav><a href='/a'>Alpha</a><a href='/b'>Beta</a><a href='/c'>Gamma</a></nav></header><main><p>Hello</p></main>"
        "<footer><ul><li><a href='/p'>Privacy</a></li><li><a href='/t'>Terms</a></li><li><a href='/h'>Help</a></li><li><a href='/x'>Extra</a></li></ul>"
        "<ul class=second><li><a href='/s1'>One</a></li><li><a href='/s2'>Two</a></li></ul></footer>")
FINE = "nav a{color:#111} footer a{color:#222}"


def names(problems):
    return sorted({p.split('"')[1] for p in problems})


def test_look_alike_controls_are_measured_once_and_every_one_is_still_named(tmp_path):
    # six footer links share one failing style at rest and on hover: the problem list must name all six
    css = FINE + " footer a{color:#bbb} footer a:hover{color:#ccc}"
    url = page(tmp_path, LIST, css)
    st = {}
    fast, rows = contrast_check.check(url, stats=st)
    slow, slow_rows = contrast_check.check(url, dedupe=False)
    assert fast == slow and rows == slow_rows
    assert names(fast) == ["Extra", "Help", "One", "Privacy", "Terms", "Two"]
    assert sum(" rest: " in p for p in fast) == 6
    assert st["groups"] < st["controls"], st          # it really measured fewer than there are controls


@pytest.mark.parametrize("css, failing", [
    # a position among siblings: only the second item of each list (at rest, and on hover only: the look at rest is then the same)
    ("footer li:nth-child(2) a{color:#ccc}", ["Terms", "Two"]),
    ("footer li:nth-child(2) a:hover{color:#ccc}", ["Terms", "Two"]),
    # a sibling combinator on hover: every item that follows another
    ("footer li+li a:hover{color:#eee}", ["Extra", "Help", "Terms", "Two"]),
    # an attribute selector (at rest, and on hover only)
    ("a[href^='/h']{color:#ddd}", ["Help"]),
    ("a[href^='/h']:hover{color:#ddd}", ["Help"]),
    # the last child
    ("footer ul li:last-child a{color:#ddd}", ["Extra", "Two"]),
    ("footer ul li:last-child a:hover{color:#ddd}", ["Extra", "Two"]),
    # :has on an ancestor, hover only
    ("footer ul:has(li:nth-child(4)) a:hover{color:#ddd}", ["Extra", "Help", "Privacy", "Terms"]),
    # a rule on an ancestor's class
    ("ul.second a{color:#ddd}", ["One", "Two"]),
    # an inline style attribute on one link
    ("", ["Gamma"]),
])
def test_dedupe_never_hides_a_problem_the_slow_way_finds(tmp_path, css, failing):
    body = LIST.replace("<a href='/c'>Gamma</a>", "<a href='/c' style='color:#ddd'>Gamma</a>") if failing == ["Gamma"] else LIST
    url = page(tmp_path, body, FINE + " " + css)
    fast, _ = contrast_check.check(url)
    slow, _ = contrast_check.check(url, dedupe=False)
    assert fast == slow, (fast, slow)
    assert names(fast) == failing


def test_a_hover_that_misses_the_first_look_alike_is_read_from_the_next(tmp_path):
    # something sits over "Terms": the mouse cannot reach it. "Help" looks the same, so the hover is read from it, and BOTH are named
    cover = ("<script>addEventListener('load',()=>{const r=document.querySelectorAll('footer li a')[1].getBoundingClientRect();"
             "const d=document.createElement('div');d.style.cssText=`position:absolute;left:${r.left}px;top:${r.top+scrollY}px;"
             "width:${r.width}px;height:${r.height}px`;document.body.appendChild(d)})</script>")
    url = page(tmp_path, LIST + cover, FINE + " footer a:hover{color:#ccc}")
    fast, _ = contrast_check.check(url)
    assert any(p.startswith('"Terms" hover') for p in fast) and any(p.startswith('"Help" hover') for p in fast), fast


def served(tmp_path):
    """The folder over http on 127.0.0.1 (the command line refuses file: pages), and a stop function."""
    class Quiet(SimpleHTTPRequestHandler):
        def log_message(self, *a, **k):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), partial(Quiet, directory=str(tmp_path)))
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return f"http://127.0.0.1:{srv.server_port}", srv


def test_kept_measurements_are_reused_and_a_css_change_misses(tmp_path):
    cache = tmp_path / "cache"
    url = page(tmp_path, LIST, FINE)
    first, second, third = {}, {}, {}
    p1, _ = contrast_check.check(url, cache_dir=cache, stats=first)
    assert first["measured"] == first["groups"] and first["cached"] == 0
    p2, _ = contrast_check.check(url, cache_dir=cache, stats=second)
    assert second["measured"] == 0 and second["cached"] == first["groups"] and p2 == p1 == []
    assert (cache / ".gitignore").read_text().strip() == "*"                  # kept out of git
    # one CSS rule changes: every key changes, nothing is reused, and the new failure is found
    url = page(tmp_path, LIST, FINE + " footer a{color:#bbb}")
    p3, _ = contrast_check.check(url, cache_dir=cache, stats=third)
    assert third["cached"] == 0 and third["measured"] == third["groups"], third
    assert names(p3) == ["Extra", "Help", "One", "Privacy", "Terms", "Two"]
    # an inline <style> or a linked sheet are both part of the CSS that is hashed: edit a linked sheet and it misses too
    (tmp_path / "s.css").write_text(FINE)
    linked = tmp_path / "l.html"
    linked.write_text(f"<!doctype html><meta name=viewport content='width=device-width'><link rel=stylesheet href='s.css'>{LIST}")
    base, srv = served(tmp_path)
    try:
        a, b = {}, {}
        contrast_check.check(base + "/l.html", cache_dir=cache, stats=a)
        contrast_check.check(base + "/l.html", cache_dir=cache, stats=b)
        assert a["measured"] > 0 and b["measured"] == 0
        (tmp_path / "s.css").write_text(FINE + " footer a:hover{color:#ccc}")
        c = {}
        pc, _ = contrast_check.check(base + "/l.html", cache_dir=cache, stats=c)
        assert c["cached"] == 0 and any("hover" in x for x in pc)
    finally:
        srv.shutdown()


def test_controls_shared_by_two_pages_with_the_same_css_are_measured_once(tmp_path):
    cache = tmp_path / "cache"
    a, b = {}, {}
    contrast_check.check(page(tmp_path, LIST, FINE, "a.html"), cache_dir=cache, stats=a)
    contrast_check.check(page(tmp_path, LIST + "<main><a href='/more'>More</a></main>", FINE, "b.html"), cache_dir=cache, stats=b)
    assert b["cached"] > 0 and b["measured"] < b["groups"], b


def run_cli(tmp_path, url, *flags, cfg=None):
    proj = tmp_path / "proj"
    proj.mkdir(exist_ok=True)
    (proj / "growth.json").write_text(json.dumps({"name": "t", "site_url": "https://example.com", **(cfg or {})}))
    env = {**os.environ, "GROWTH_PROJECT": str(proj)}
    r = subprocess.run([sys.executable, str(ROOT / "kit" / "tools" / "contrast_check.py"), url, *flags], capture_output=True, text=True,
                       env=env, cwd=proj, timeout=300)
    return r, proj / ".cache" / "contrast"


def test_command_line_keeps_measurements_unless_told_not_to(tmp_path):
    (tmp_path / "web").mkdir()
    page(tmp_path / "web", LIST, FINE)
    base, srv = served(tmp_path / "web")
    try:
        r, cache = run_cli(tmp_path, base + "/p.html", "--no-cache")
        assert r.returncode == 0 and not cache.parent.exists(), r.stdout + r.stderr          # --no-cache: nothing read, nothing written
        r, cache = run_cli(tmp_path, base + "/p.html", cfg={"contrast_cache": False})
        assert r.returncode == 0 and not cache.parent.exists(), r.stdout + r.stderr          # growth.json switch
        r, cache = run_cli(tmp_path, base + "/p.html")
        assert r.returncode == 0 and any(cache.rglob("*.json")), r.stdout + r.stderr          # default: kept under <project>/.cache/contrast
        assert not re.search(r"\b0 measured now", r.stdout), r.stdout
        r, cache = run_cli(tmp_path, base + "/p.html")
        assert re.search(r"\b0 measured now", r.stdout) and "kept from before" in r.stdout, r.stdout      # the second run reads them back
        r, _ = run_cli(tmp_path, base + "/p.html", "--width", "1366", "--width", "390", "--no-dedupe")
        assert r.stdout.count("states measured") == 2 and "at 1366px" in r.stdout and "at 390px" in r.stdout
    finally:
        srv.shutdown()


def count_launches(monkeypatch):
    from playwright import async_api, sync_api
    n = {"n": 0}
    for mod in (sync_api, async_api):
        def counting(self, *a, _real=mod.BrowserType.launch, **k):
            n["n"] += 1
            return _real(self, *a, **k)
        monkeypatch.setattr(mod.BrowserType, "launch", counting)
    return n


def test_every_width_is_measured_in_one_browser(tmp_path, monkeypatch):
    url = page(tmp_path, LIST, FINE)
    n = count_launches(monkeypatch)
    res = contrast_check.check_widths(url, (1366, 390))
    assert n["n"] == 1 and sorted(res) == [390, 1366]
    n["n"] = 0
    res = phone_check.check_widths(url, (360, 390, 820, 1024))
    assert n["n"] == 1 and sorted(res) == [360, 390, 820, 1024]
    assert res[360] == phone_check.check(url, 360)                       # one width on its own reads the same


def test_widths_side_by_side_read_the_same_as_one_after_the_other(tmp_path):
    # a page with something to find at the phone widths and at the wide ones: small text, small footer targets, a sideways scroll
    css = "footer a{display:block;width:10px;height:10px;overflow:hidden} main{width:1200px} p{font-size:9px}"
    url = page(tmp_path, LIST.replace("<p>Hello</p>", "<p>Hello</p>" * 3), css)
    side = phone_check.check_widths(url, phone_check.WIDTHS)
    after = phone_check.check_widths(url, phone_check.WIDTHS, parallel=False)
    assert side == after and any(side[w] for w in side), side
    assert any(x.startswith("taps") for x in side[360]) and any(x.startswith("text") for x in side[360])
    assert any(x.startswith("overflow") for x in side[820])


def test_a_width_that_fails_to_load_raises_and_the_browser_closes(tmp_path):
    with pytest.raises(Exception):
        phone_check.check_widths("http://127.0.0.1:9/nothing", (360, 820))


def test_profile_prints_each_checks_seconds_slowest_first_on_stderr(tmp_path):
    proj = tmp_path / "proj"
    import shutil
    shutil.copytree(ROOT / "examples" / "demo-site" / "project", proj)
    code = ("import sys; sys.path.insert(0, %r); import gate; gate.print_profile({'c.%%02d' %% i: i / 10 for i in range(30)} | {'slow.one': 9.0})"
            % str(ROOT / "kit" / "tools"))
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env={**os.environ, "GROWTH_PROJECT": str(proj)}, cwd=proj)
    assert r.stdout == "", r.stdout
    lines = [l for l in r.stderr.splitlines() if l.startswith("  ")]
    assert len(lines) == 25 and lines[0].split()[-1] == "slow.one" and "slowest 25 of 31" in r.stderr
    assert "Total: " in r.stderr and "over 31 checks" in r.stderr
    secs = [float(l.split()[0]) for l in lines]
    assert secs == sorted(secs, reverse=True)


def test_gate_page_profile_flag_leaves_the_normal_output_alone(tmp_path):
    proj = tmp_path / "proj"
    import shutil
    shutil.copytree(ROOT / "examples" / "demo-site" / "project", proj)
    (tmp_path / "web").mkdir()
    page(tmp_path / "web", LIST, FINE)
    base, srv = served(tmp_path / "web")
    try:
        env = {**os.environ, "GROWTH_PROJECT": str(proj)}
        args = [sys.executable, str(ROOT / "kit" / "tools" / "gate.py"), "page", "/p.html", "--url", base + "/p.html", "--type", "core",
                "--only", "icons.no-emoji,embeds.lazy"]
        plain = subprocess.run(args, capture_output=True, text=True, env=env, cwd=proj, timeout=120)
        prof = subprocess.run([*args, "--profile"], capture_output=True, text=True, env=env, cwd=proj, timeout=120)
        assert "Profile" not in plain.stderr and plain.stdout == prof.stdout
        assert "Profile: seconds per check" in prof.stderr and "icons.no-emoji" in prof.stderr and "Total:" in prof.stderr
    finally:
        srv.shutdown()
