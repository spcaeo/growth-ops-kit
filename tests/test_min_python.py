"""The kit promises Python 3.10 or newer (setup.sh, README). Every file must compile on the oldest Python found on the
machine, because the hooks run through `python3` on the PATH, not the kit's own environment. On 24 Nov 2026 two files
used a 3.12-only f-string (a backslash inside the braces) and the Stop hook crashed on a Mac whose python3 was 3.11."""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
OLD = [p for p in (shutil.which(n) for n in ("python3.10", "python3.11")) if p]
SCRIPT = """
import pathlib, sys
bad = []
for f in sys.argv[1:]:
    try:
        compile(pathlib.Path(f).read_text(encoding="utf-8"), f, "exec")
    except SyntaxError as e:
        bad.append(f"{f}:{e.lineno}: {e.msg}")
print("\\n".join(bad))
sys.exit(1 if bad else 0)
"""


@pytest.mark.skipif(not OLD, reason="no python3.10 or python3.11 on this machine")
@pytest.mark.parametrize("py", OLD)
def test_every_kit_file_compiles_on_older_python(py):
    files = [str(p) for p in sorted((ROOT / "kit").rglob("*.py"))] + [str(ROOT / "growth")]
    r = subprocess.run([py, "-c", SCRIPT, *files], capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, f"these files do not compile on {py}:\n{r.stdout}{r.stderr}"
