"""Kit friction 43 and 44, with fixture pages in a real headless browser (file:// pages, no network).
43: a focus ring is judged against the colour OUTSIDE the element, not the button's own fill; the text colour of a link comes from
    the link's own words, not from a child span inside it.
44: a link inline in a sentence is not a too-small tap target (WCAG 2.5.8); a footer list of links still is."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "kit" / "tools"))
pytest.importorskip("playwright")
import contrast_check  # noqa: E402
import phone_check  # noqa: E402


def page(tmp_path, body, css=""):
    f = tmp_path / "p.html"
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
