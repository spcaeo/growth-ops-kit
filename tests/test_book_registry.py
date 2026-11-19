"""The book and the registry agree: every [code: <id>] tag of the page rulebook names a check that exists in the registry,
and every registry check points at a rule number present in the book. Skipped while the rulebook is not there."""
import re

import pytest

from config import RULEBOOK
from gatelib import CHECKS, registry

pytestmark = pytest.mark.skipif(not RULEBOOK.exists(), reason="book/03-page-rulebook.md does not exist yet (the book is written in parallel)")


def test_every_code_tag_is_a_registered_check():
    reg_checks = {c for e in registry.load()["rules"] for c in registry.checks_of(e)}
    tags = registry.code_tags()
    assert tags, "the rulebook has no [code: ...] tags"
    unknown = sorted(t for t in tags if t not in CHECKS)
    unregistered = sorted(t for t in tags if t not in reg_checks)
    assert unknown == [] and unregistered == [], f"tags with no check: {unknown}; tags with no registry entry: {unregistered}"


def test_every_registry_check_points_at_a_rule_in_the_book():
    book_ids = set(registry.rulebook_ids())
    owner_rows = {e["id"] for e in registry.load()["rules"] if e["id"].startswith("OR-")}
    orphans = sorted(e["id"] for e in registry.load()["rules"] if registry.checks_of(e) and e["id"] not in book_ids and e["id"] not in owner_rows)
    assert orphans == [], f"registry rules that the book does not have: {orphans}"
    for c in CHECKS.values():
        assert c.rule in book_ids or c.rule in owner_rows or c.rule == "OR-engine" or c.rule.startswith("OR-"), \
            f"check {c.cid} prints under rule {c.rule}, which is not in the book"


def test_every_numbered_rule_of_the_book_has_an_entry_and_the_same_kind():
    assert registry.unregistered() == []
    text = RULEBOOK.read_text()
    body = text.split("\n## Rules", 1)[1].split("\n## Mistakes already caught", 1)[0]
    blocks = {}
    for it in re.split(r"(?m)^(?=\d+[a-z]?\. \*\*)", body):
        m = re.match(r"(\d+[a-z]?)\. \*\*", it)
        if m:
            blocks[m.group(1)] = it.strip().split("\n\n")[0]
    for m in re.finditer(r"\*\*Rule (0[a-z]?)\..*", text):
        blocks[m.group(1)] = m.group(0)
    by_id = {e["id"]: e for e in registry.load()["rules"]}
    for rid, block in blocks.items():
        tag = re.findall(r"\[(code|judgment): ([^\]]+)\]", block)
        assert tag, f"rule {rid} has no [code: ...] or [judgment: proxy ...] tag"
        kind, ids = tag[-1]
        e = by_id[rid]
        assert kind == e["enforcement"], f"rule {rid}: the book says {kind}, the registry says {e['enforcement']}"
        named = re.findall(r"[a-z0-9]+\.[a-z0-9.-]+[a-z0-9]", ids)
        assert sorted(named) == sorted(registry.checks_of(e)), f"rule {rid}: tag and registry name different checks"


def test_the_registry_version_is_the_books():
    m = re.search(r"(?m)^version:\s*(\S+)", RULEBOOK.read_text())
    assert m and registry.load()["rulebook_version"] == m.group(1)


def test_every_registry_rule_text_is_the_books_heading():
    """The registry's text for a rule (which the gate prints) is copied from the book's bold heading by `growth registry_sync`."""
    heads = registry.rule_headings()
    assert len(heads) > 100
    wrong = sorted(e["id"] for e in registry.load()["rules"] if e["id"] in heads and e["rule"].rstrip(".:,;") != heads[e["id"]])
    assert wrong == [], f"registry text differs from the book's heading for rules {wrong}; run: growth registry_sync"


def test_the_attributes_and_names_the_book_tells_builders_to_use_are_the_ones_the_gate_reads():
    """A builder who follows the rulebook must not meet a FAIL for using the book's own words (fold attribute, surfaces, jobs)."""
    from config import KIT_DIR
    from gatelib.c_links import JOBS, SURFACES
    text = RULEBOOK.read_text()
    code = "\n".join(p.read_text(errors="replace") for p in KIT_DIR.rglob("*.py"))
    attrs = set(re.findall(r"\bdata-[a-z][a-z-]+", text))
    assert attrs, "the rulebook names no data- attribute"
    unread = sorted(a for a in attrs if a not in code)
    assert unread == [], f"the book names attributes no kit code reads: {unread}"
    rule = next(l for l in text.splitlines() if l.startswith("36f."))
    named = set(re.findall(r"`((?:plain|tint|warm|dark|geo-[a-z]+))`", rule))
    assert named == SURFACES, f"36f lists surfaces {sorted(named)}; the gate accepts {sorted(SURFACES)}"
    jobs = set(re.findall(r"`(hook|show|compare|reassure|prove|relief|act|read|answer)`", rule))
    assert jobs == JOBS
