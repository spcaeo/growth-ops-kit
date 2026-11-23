"""2.6.1: links.blue skips a site's own menu/contents classes (links.not_text), hover colours, and the dark colour on a
site with no dark theme; repo.logo-untouched judges logo-named files only."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "kit" / "tools"))

from gatelib.c_links import prose_link_rules  # noqa: E402

CSS = ".body p a{color:var(--link);text-decoration:underline}.mn__p a{color:var(--ink)}.ratings a{color:var(--text)}"


def test_not_text_classes_are_left_out():
    sels = [s for s, _ in prose_link_rules(CSS, r"\.mn__|\.ratings")]
    assert sels == [".body p a"]
    assert len(prose_link_rules(CSS)) == 3


def test_logo_pattern_is_logo_named_files_only():
    pat = re.compile(r"(?i)(logo|lockup|wordmark|brand-mark)[^/]*$")
    assert pat.search("src/components/frame/Logo.astro") and pat.search("public/brand/logo-word.svg")
    assert not pat.search("public/brand/tick.svg")


def test_dark_surface_link_token_pattern():
    """2.6.2: a link rule scoped to a dark surface may use a light --*link* token."""
    on_dark = re.compile(r"(?i)dark|ink|night|\[data-theme=[\"']?dark")
    assert on_dark.search('[data-surface="dark"] a:not(.btn)') and re.search(r"var\(--[\w-]*link[\w-]*\)", "var(--link-on-ink)")
