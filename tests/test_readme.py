"""README promises that first-time users need (#11, #14)."""
from pathlib import Path

README = (Path(__file__).resolve().parent.parent / "README.md").read_text()


def test_readme_says_any_folder_works_and_three_folders():
    assert "Any folder works" in README and "three separate folders" in README
    assert "inside the site" in README

