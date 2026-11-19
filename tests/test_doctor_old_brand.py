"""Doctor A2: old-brand words left in the project folder or the built site fail; the files that DEFINE the words
(growth.json), the lines that BAN them (a brand sheet's "never say" line) and the steps log, which quotes the owner,
do not count. No network."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCTOR = ROOT / "kit" / "tools" / "doctor.py"
WORDS = "oldbrand|Old Brand Co"


def a2(project):
    r = subprocess.run([sys.executable, str(DOCTOR)], capture_output=True, text=True, cwd=project,
                       env={**os.environ, "GROWTH_PROJECT": str(project)})
    return next(l for l in r.stdout.splitlines() if "A2 Project adapted" in l)


def prepare(project, site=None):
    cfg = json.loads((project / "growth.json").read_text())
    cfg["old_brand_words"] = WORDS
    if site:
        cfg["build_dir"] = str(site)
    (project / "growth.json").write_text(json.dumps(cfg))
    (project / "BRAND.md").write_text("# Brand\n\n## 7. What we never claim\n\n- Never say \"Old Brand Co\" or oldbrand (a previous name).\n")
    (project / "docs").mkdir(exist_ok=True)
    (project / "docs" / "steps-log.md").write_text('| I-1 | 2026-11-18 | "remove Old Brand Co everywhere" | done | BRAND.md |\n')


def test_the_defining_and_banning_files_do_not_count(demo_project, tmp_path):
    site = tmp_path / "dist"
    site.mkdir()
    (site / "index.html").write_text("<h1>Bright lawns</h1>")
    prepare(demo_project, site)
    line = a2(demo_project)
    assert line.startswith("OK") and "0 mention the old brand" in line


def test_no_build_dir_is_never_ok(demo_project):
    prepare(demo_project)
    cfg = json.loads((demo_project / "growth.json").read_text())
    cfg["site_dir"] = ""   # no build_dir and no site_dir: nothing to search
    (demo_project / "growth.json").write_text(json.dumps(cfg))
    line = a2(demo_project)
    assert line.startswith("TODO") and "set growth.json build_dir" in line


def test_a_missing_or_empty_build_dir_is_never_ok(demo_project, tmp_path):
    prepare(demo_project, tmp_path / "not-built")
    line = a2(demo_project)
    assert line.startswith("TODO") and f"{(tmp_path / 'not-built').resolve()} does not exist" in line
    (tmp_path / "not-built").mkdir()
    (tmp_path / "not-built" / "app.js").write_text("console.log(1)")   # no page files
    line = a2(demo_project)
    assert line.startswith("TODO") and "no page files" in line


def test_a_real_mention_in_a_project_doc_fails(demo_project):
    prepare(demo_project)
    (demo_project / "docs" / "02-site.md").write_text("The site was built by Old Brand Co in 2024.\n")
    line = a2(demo_project)
    assert line.startswith("FAIL") and "docs/02-site.md" in line and "1 mention the old brand" in line


def test_the_built_site_is_searched(demo_project, tmp_path):
    site = tmp_path / "dist"
    (site / "about").mkdir(parents=True)
    (site / "index.html").write_text("<h1>Bright lawns</h1>")
    (site / "logo-oldbrand.webp").write_bytes(b"\x00binary")   # a file NAME is not page text
    prepare(demo_project, site)
    line = a2(demo_project)
    assert line.startswith("OK") and f"built site {site.resolve()}: 1 files searched, 0 mention the old brand" in line
    (site / "about" / "index.html").write_text("<p>Formerly oldbrand.</p>")
    line = a2(demo_project)
    assert line.startswith("FAIL") and "site: about/index.html" in line
