"""SETUP.md and BRAND.md templates: short cells, hints in a comment (#23)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_setup_and_brand_templates_have_short_cells_and_the_hints_in_comments():
    import re
    for f in ("SETUP.md", "BRAND.md"):
        text = (ROOT / "templates" / "project" / f).read_text()
        cells = [l for l in text.splitlines() if l.startswith("|") and "<fill in" in l and not l.startswith("| Control check")]
        assert cells and all("<fill in:" not in l for l in cells), f      # a cell is filled by replacing a short <fill in>
        assert re.search(r"<!-- What goes in each <fill in> cell", text), f
