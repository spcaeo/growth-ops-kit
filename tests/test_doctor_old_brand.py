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


def setup(project, site=None):
    cfg = json.loads((project / "growth.json").read_text())
    cfg["old_brand_words"] = WORDS
    if site:
        cfg["build_dir"] = str(site)
    (project / "growth.json").write_text(json.dumps(cfg))
    (project / "BRAND.md").write_text("# Brand\n\n## 7. What we never claim\n\n- Never say \"Old Brand Co\" or oldbrand (a previous name).\n")
    (project / "docs").mkdir(exist_ok=True)
    (project / "docs" / "steps-log.md").write_text('| I-1 | 2026-11-18 | "remove Old Brand Co everywhere" | done | BRAND.md |\n')


def test_the_defining_and_banning_files_do_not_count(demo_project):
    setup(demo_project)
    line = a2(demo_project)
    assert line.startswith("OK") and "built site not searched (set growth.json build_dir)" in line


def test_a_real_mention_in_a_project_doc_fails(demo_project):
    setup(demo_project)
    (demo_project / "docs" / "02-site.md").write_text("The site was built by Old Brand Co in 2024.\n")
    line = a2(demo_project)
    assert line.startswith("FAIL") and "docs/02-site.md" in line


def test_the_built_site_is_searched(demo_project, tmp_path):
    site = tmp_path / "dist"
    (site / "about").mkdir(parents=True)
    (site / "index.html").write_text("<h1>Bright lawns</h1>")
    (site / "logo-oldbrand.webp").write_bytes(b"\x00binary")   # a file NAME is not page text
    setup(demo_project, site)
    assert a2(demo_project).startswith("OK") and "dist/ searched: 0 file(s)" in a2(demo_project)
    (site / "about" / "index.html").write_text("<p>Formerly oldbrand.</p>")
    line = a2(demo_project)
    assert line.startswith("FAIL") and "site: about/index.html" in line
