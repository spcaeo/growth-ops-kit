"""2.2.6: numbers inside a drawn example (svg, aria-hidden, data-example) are not claims."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "kit" / "tools"))
sys.path.insert(0, str(ROOT / "kit" / "tools" / "gatelib"))

import fact_sources  # noqa: E402
import domx  # noqa: E402
from techseo.dom import parse  # noqa: E402


def stats(html):
    return " | ".join(x["sentence"] for x in fact_sources.page_stats(parse(html), domx))


PAGE = """<html><body><main>
<p>Portals cut no-shows by 30% in one study.</p>
<figure aria-label="An example app, drawn"><div data-example><p>Visit summary, 12 Nov</p><p>You owe $42.10</p></div></figure>
<div aria-hidden="true"><p>Balance $99.00</p></div>
<svg><text>Due 3 Dec</text></svg>
<p>Real claim: 64% of patients use portals. <span aria-hidden="true">$15.00</span></p>
</main></body></html>"""


def test_examples_skipped():
    s = stats(PAGE)
    assert "42.10" not in s and "12 Nov" not in s and "99.00" not in s and "3 Dec" not in s and "15.00" not in s


def test_real_claims_kept():
    s = stats(PAGE)
    assert "30%" in s and "64%" in s
