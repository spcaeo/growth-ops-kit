"""rules/registry.json: one entry per numbered rule of the page rulebook (book/03-page-rulebook.md) and per
OWNER-RULES.md row. The registry lives in the kit; the owner-rules file is the project's."""
from __future__ import annotations

import json
import re
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import REGISTRY, RULEBOOK  # noqa: E402

ENFORCEMENT = ("code", "judgment")
SCOPES = ("money", "hub", "post", "core", "site", "process")
NEEDS = ("live", "project", "nextjs", "repo")      # what a check reads: the live page, the project folder, the site's code (repo: any stack, nextjs: Next.js only)


def rulebook_ids(book: Path = RULEBOOK):
    """Every numbered rule in the rulebook: rules 0 and 0a plus the numbered items of its 'Rules' section."""
    t = book.read_text()
    body = t.split("\n## Rules", 1)[1] if "\n## Rules" in t else t
    body = re.split(r"\n## (?:Mistakes already caught|Dropped rules|Change log)", body, 1)[0]
    ids = re.findall(r"(?m)^(\d+[a-z]?)\. \*\*", body)
    zero = re.findall(r"\*\*Rule (0[a-z]?)\.", t)          # "Rule 0" and "Rule 0a" sit in the how-to-use section
    return list(dict.fromkeys(zero)) + ids


def rule_headings(book: Path = RULEBOOK):
    """{rule number: the bold heading of the rule in the book, without its closing full stop or colon}."""
    t = book.read_text()
    body = t.split("\n## Rules", 1)[1] if "\n## Rules" in t else t
    body = re.split(r"\n## (?:Mistakes already caught|Dropped rules|Change log)", body, 1)[0]
    return {m.group(1): re.sub(r"\s+", " ", m.group(2)).strip().rstrip(".:,;") for m in re.finditer(r"(?ms)^(\d+[a-z]?)\. \*\*(.+?)\*\*", body)}


def code_tags(book: Path = RULEBOOK):
    """Every check id named by a [code: id, id] or [judgment: proxy id] tag in the rulebook."""
    out = set()
    for m in re.finditer(r"\[(?:code|judgment: proxy)[: ]\s*([^\]]+)\]", book.read_text()):
        out |= {x.strip() for x in re.split(r"[,\s]+", m.group(1)) if re.match(r"^[a-z][\w.-]*$", x.strip())}
    return out


def load(path: Path = REGISTRY):
    return json.loads(Path(path).read_text())


def unregistered(book: Path = RULEBOOK, path: Path = REGISTRY):
    have = {e["id"] for e in load(path)["rules"]}
    return [i for i in rulebook_ids(book) if i not in have]


def checks_of(entry):
    return list(entry.get("checks", [])) + list(entry.get("proxy", []))


def owner_rows(owner_rules: Path):
    """The bold title of every row in OWNER-RULES.md's numbered sections (not the 'Not adopted' table)."""
    t = Path(owner_rules).read_text()
    t = t.split("\n## Not adopted", 1)[0]
    return re.findall(r"(?m)^\| \*\*([^*]+)\*\*", t)


def unregistered_rows(owner_rules: Path, path: Path = REGISTRY):
    have = {e.get("row") for e in load(path)["rules"]}
    return [r for r in owner_rows(owner_rules) if r not in have]
