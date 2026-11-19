"""No test module defines a function named setup or teardown at module level: pytest 7 (the kit's venv) calls those
as nose-style module hooks with the module as the argument, so a helper with that name breaks every test in the file,
while pytest 8+ ignores it. Found the hard way on 2026-11-18."""
import re
from pathlib import Path

HOOK = re.compile(r"^def (setup|teardown)\(", re.M)


def test_no_module_level_setup_or_teardown_helpers():
    bad = [p.name for p in Path(__file__).parent.glob("test_*.py") if HOOK.search(p.read_text())]
    assert bad == [], f"rename these helpers (pytest 7 runs them as module hooks): {bad}"
