"""Cases for the Stop-hook model guard (kit/tools/agent_models.py). 1 = the call must be flagged, 0 = it must pass."""
import pytest

from agent_models import problems

CASES = [
    ("pp-fixer", "Pricing page review fixes builder", "sonnet", 0),  # a fixer named after a review is a builder
    ("pp-builder", "Pricing page builder", "opus", 1),  # builders run on Sonnet
    ("pp-builder", "Pricing page builder", None, 1),  # no model inherits the lead's (Opus)
    ("pp-review-a", "Pricing page independent review, part 1", "opus", 0),
    ("pp-review-b", "Review of Opus-built pricing folds (part 2)", "sonnet", 0),
    ("pp-review-b", "Review of Opus-built pricing folds (part 2)", "opus", 1),
    ("r", "Independent review", "sonnet", 1),
    ("x", "Count log lines", None, 1),
    ("e", "Final evidence shots", "sonnet", 0),
    ("rs", "Researcher: AU region vendor pages, verify facts", "sonnet", 0),  # a researcher is known (friction 45)
    ("rs", "Researcher: AU region vendor pages", "opus", 1),
]


@pytest.mark.parametrize("name,desc,model,flagged", CASES)
def test_cases(name, desc, model, flagged):
    assert len(problems([{"name": name, "description": desc, "model": model}])) == flagged
