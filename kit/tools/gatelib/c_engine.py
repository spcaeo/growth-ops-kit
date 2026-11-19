"""Kit vs project data: the kit's files hold no project facts. The facts to look for are read from
growth.json (domain, product name, old brand words), so this file names none of them."""
from __future__ import annotations

import re
import urllib.parse
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import KIT_DIR  # noqa: E402

from .core import Missing, check

# The kit's own files, which must hold no fact about any one business (checked against the facts of the current project).
ENGINE = ["tools", "adapters", "rules", "hooks", "skills", "page-tracker"]
EXT = {".py", ".sh", ".js", ".mjs", ".ts", ".json", ".md", ".txt", ".yml", ".yaml"}
KEYLIKE = r"(AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{30,}|xox[bp]-[A-Za-z0-9-]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY)"
EMAIL = r"[A-Za-z0-9._%+-]+@(?!example\b|anthropic\.com)[A-Za-z0-9-]+\.[A-Za-z]{2,}"
GSC = r"/[a-z0-9][a-z0-9/-]+\b.{0,80}?\b\d[\d,]*\s*(impressions|impr\.?|clicks)\b"


def patterns(cfg):
    host = urllib.parse.urlsplit(cfg.get("site_url", "")).netloc.replace("www.", "")
    pats = []
    if host:
        pats.append(("domain", re.escape(host)))
    if cfg.get("product"):
        pats.append(("product name", r"\b" + re.escape(cfg["product"]) + r"\b"))
    if cfg.get("old_brand_words"):
        pats.append(("old brand word", r"\b(" + cfg["old_brand_words"] + r")\b"))
    pats += [("email", EMAIL), ("absolute /Users/ path", r"/Users/[A-Za-z0-9._-]+"), ("key-like string", KEYLIKE),
             ("GSC number tied to a page", GSC)]
    return [(k, re.compile(p, re.I)) for k, p in pats]


def engine_files(kit: Path = KIT_DIR):
    out = []
    for e in ENGINE:
        p = kit / e
        if p.is_file():
            out.append(p)
        elif p.is_dir():
            out += [f for f in sorted(p.rglob("*")) if f.is_file() and f.suffix in EXT and "__pycache__" not in f.parts]
    return out


def scan(cfg: dict, kit: Path = KIT_DIR):
    """[(relative file, line number, kind, snippet)] for every project fact in a kit file."""
    files = engine_files(kit)
    if not files:
        raise Missing("kit files (tools/, adapters/, rules/, ...)", "the kit folder is incomplete")
    if not cfg:
        raise Missing("growth.json", "the project facts to look for come from growth.json")
    pats = patterns(cfg)
    hits = []
    for f in files:
        for n, line in enumerate(f.read_text(errors="replace").splitlines(), 1):
            for kind, rx in pats:
                m = rx.search(line)
                if m:
                    hits.append((str(f.relative_to(kit)), n, kind, line[max(0, m.start() - 30):m.end() + 30].strip()))
    return hits


@check("engine.facts", "OR-engine", ("engine",), "the kit's files hold no project facts (domain, product, emails, /Users/ paths, keys, GSC numbers)", needs="project")
def facts(ctx):
    hits = scan(ctx.cfg)
    by = {}
    for f, *_ in hits:
        by[f] = by.get(f, 0) + 1
    top = sorted(by.items(), key=lambda x: -x[1])
    ctx.verdict([f"{f}: {n}" for f, n in top], "no project facts in the kit files",
                "move the fact into the project's growth.json or BRAND.md and read it from there (growth gate engine lists file:line)")
