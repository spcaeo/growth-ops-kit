"""2.2.5: a page's own computed reading time ("11 min read", "N min left") and its table of contents are no stats."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "kit" / "tools"))
sys.path.insert(0, str(ROOT / "kit" / "tools" / "gatelib"))

import fact_sources  # noqa: E402


def test_reading_time_is_no_stat():
    s = fact_sources.without_contact("By Rakesh Patel Published August 14, 2026 \u00b7 Updated October 20, 2026 \u00b7 11 min read")
    assert "11" not in s
    assert "4" not in fact_sources.without_contact("Contents 4 min left")
    assert "6" not in fact_sources.without_contact("Reading time: 6 minutes")


def test_real_minutes_stay_a_stat():
    assert "15" in fact_sources.without_contact("Patients wait 15 minutes on average for a reply.")


def test_toc_class_is_skipped():
    assert fact_sources.BYLINE_CLS.search("toc") and fact_sources.BYLINE_CLS.search("desk-toc toc")
    assert not fact_sources.BYLINE_CLS.search("stock-chart")
