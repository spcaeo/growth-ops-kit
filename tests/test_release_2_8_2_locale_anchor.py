"""2.8.2: the same link words to a page and its language copy (/x/ and /en-us/x/) are one page, not a duplicate anchor."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "kit" / "tools"))
from gatelib.graph_links import same_page  # noqa: E402


def test_language_copy_is_the_same_page():
    assert same_page("/en-us/data-migration/") == "/data-migration/"
    assert same_page("/en-us/") == "/" and same_page("/en-us") == "/"
    assert same_page("/data-migration/") == "/data-migration/"


def test_other_paths_are_untouched():
    assert same_page("/blog/en-us-tips/") == "/blog/en-us-tips/"
    assert same_page("/use/x/") == "/use/x/"
    assert same_page("/de/x/") == "/de/x/"          # a two-letter folder is not taken as a locale without a region
