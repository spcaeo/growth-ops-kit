"""The rule gate: every page rule a program can decide is a check here (see rules/registry.json).

Importing the package registers every check in core.CHECKS: the stack-free checks of this package (they read the
served page or the project folder), then the adapters' checks (adapters/nextjs reads a Next.js site's code).
c_house runs last: it reads the other results.
"""
import sys
from pathlib import Path

_TOOLS = str(Path(__file__).resolve().parent.parent)           # kit/tools: holds config.py and techseo/
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)
from . import c_cta, c_engine, c_evidence, c_links, c_plan, c_layout, c_page, c_process, c_release, c_research, c_seo, c_types, c_words  # noqa: F401
from . import c_house  # noqa: F401  (last: reads the feature checks' results)

_KIT = str(Path(__file__).resolve().parent.parent.parent)      # the kit/ folder: holds adapters/
if _KIT not in sys.path:
    sys.path.insert(0, _KIT)
import adapters.nextjs  # noqa: E402,F401
from .core import CHECKS  # noqa: E402,F401
