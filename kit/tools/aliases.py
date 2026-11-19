"""Old addresses of a page, so Search Console numbers for every address a page has had are added together.

Google keeps showing a page's OLD address for months after a move, so counting only the current address undercounts the
page (one real page: 13,860 impressions on the new address, 280,563 on the old one). Two sources, both optional, in
growth.json:

  "page_aliases":  {"/topic/some-post": ["/blog/some-post/", "/es/blog/some-post/"]}   # current address -> old ones
  "redirects_file": "../site/_redirects"   # a redirect list, one "old new [301]" per line (Netlify / Cloudflare style)

From the redirect list only plain 301/302/307/308 lines count (no wildcards, no :placeholders, no other hosts) and
chains are followed (a -> b -> c gives c both a and b). Addresses are used exactly as written, so a trailing slash stays.

  aliases.build(page_aliases, redirects_text)  -> {current key: [old address, ...]}
  growth aliases                               # (python3 aliases.py) print the map this project resolves to
"""
from __future__ import annotations

import re
from pathlib import Path

import paths

OK_CODES = {"", "301", "302", "307", "308"}


def parse_redirects(text: str) -> dict[str, str]:
    """{old address: new address} from a redirect list."""
    out = {}
    for line in (text or "").splitlines():
        line = line.split("#", 1)[0].strip()
        parts = re.split(r"\s+", line)
        if len(parts) < 2 or not parts[0].startswith("/") or not parts[1].startswith("/"):
            continue
        code = (parts[2] if len(parts) > 2 else "").rstrip("!")
        if code not in OK_CODES or any(ch in x for x in parts[:2] for ch in "*:"):
            continue
        out[parts[0]] = parts[1].split("#", 1)[0].split("?", 1)[0]
    return out


def build(page_aliases: dict | None = None, redirects_text: str = "") -> dict[str, list[str]]:
    """{current page key (no trailing slash): old addresses}, from the growth.json map and the redirect list."""
    out: dict[str, list[str]] = {}

    def add(current, old):
        k = paths.key(current)
        if paths.key(old) != k and old not in out.setdefault(k, []):
            out[k].append(old)
    for cur, olds in (page_aliases or {}).items():
        for old in ([olds] if isinstance(olds, str) else olds or []):
            add(cur, old)
    red = parse_redirects(redirects_text)
    by_key = {paths.key(o): n for o, n in red.items()}
    for old, new in red.items():
        seen = {paths.key(old)}
        while paths.key(new) in by_key and paths.key(new) not in seen:    # follow a chain to the last address
            seen.add(paths.key(new))
            new = by_key[paths.key(new)]
        add(new, old)
    return out


def load(growth: dict, project: str | Path) -> dict[str, list[str]]:
    text = ""
    f = growth.get("redirects_file")
    if f:
        p = Path(f).expanduser()
        p = p if p.is_absolute() else Path(project) / p
        text = p.read_text(errors="replace") if p.is_file() else ""
    return build(growth.get("page_aliases"), text)


if __name__ == "__main__":
    from config import CFG, PROJECT
    for cur, olds in sorted(load(CFG, PROJECT).items()):
        print(f"{cur}\t" + "  ".join(olds))
