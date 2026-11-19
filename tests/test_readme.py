"""README promises that first-time users need (#11, #14)."""
from pathlib import Path

README = (Path(__file__).resolve().parent.parent / "README.md").read_text()


def test_readme_says_any_folder_works_and_three_folders():
    assert "Any folder works" in README and "three separate folders" in README
    assert "inside the site" in README



def test_readme_has_the_what_you_get_per_stack_table():
    assert "## What you get per stack" in README
    table = README.split("## What you get per stack", 1)[1].split("\n## ", 1)[0]
    for stack in ("Next.js", "Astro", "Hugo", "static"):
        assert stack in table
    assert "Roadmap" in table and "content collections" in table
