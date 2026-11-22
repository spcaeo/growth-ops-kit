#!/usr/bin/env python3
"""The fingerprint of a page as served: evidence is fresh while the page's own built output is the same.

A fingerprint is the sha256 of the page's built HTML (build ids, build times, nonces and comments stripped) plus the sha256
of every CSS and JS file the page links. When evidence (a click-through, a share-preview look, screenshots) is recorded the
fingerprint is stored with it; the gate compares it with the page now. Same fingerprint = fresh, whatever commits happened
in between. Evidence with no fingerprint (older evidence) keeps the commit-based rule. Nothing is rebuilt: the page is read
from growth.json build_dir (relative to site_repo, else the project), or fetched from the preview URL.

  growth fingerprint show /page [--url URL]                  print the page's fingerprint now
  growth fingerprint record /page --key page-key [--url URL]  store it beside the page's screenshots (research/*<key>*-shots/)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402

SIDECAR = "fingerprint.json"
EVIDENCE_TAGS = ("click-test", "share-preview", "speed")

_STRIPS = (
    (re.compile(r"<!--.*?-->", re.S), ""),
    (re.compile(r"\s+nonce=(\"[^\"]*\"|'[^']*'|[^\s>]+)", re.I), ""),
    (re.compile(r"<meta\b[^>]*\bname=[\"'](?:generator|build[-_]?(?:id|time|date|number)|buildid)[\"'][^>]*>", re.I), ""),
    (re.compile(r"\sdata-(?:build|built|version|deploy)[\w-]*=(\"[^\"]*\"|'[^']*')", re.I), ""),
    (re.compile(r"(?i)\bbuild[-_ ]?(?:id|time|date|number)\b[\"':= ]+[^\"'<>,\s]+"), "build"),
    (re.compile(r"(?i)\bbuild \d+\b[^<\"]*?\b(?:EST|EDT|UTC)\b"), "build"),         # the footer release line
    (re.compile(r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b"), "TS"),
    (re.compile(r"\s+"), " "),
)


def normalize_html(html: str) -> str:
    """The page's HTML without what changes on every build: comments, nonces, build ids and times, timestamps."""
    for rx, rep in _STRIPS:
        html = rx.sub(rep, html)
    return html.strip()


def sha(b: bytes | str) -> str:
    return hashlib.sha256(b if isinstance(b, bytes) else b.encode("utf-8", "replace")).hexdigest()


def asset_refs(html: str) -> list[str]:
    """The CSS and JS files the page links (stylesheet links and script sources), in page order, without query strings."""
    out = []
    for m in re.finditer(r"<link\b[^>]*>", html, re.I):
        tag = m.group(0)
        if re.search(r"\brel=[\"']?(?:stylesheet|modulepreload)", tag, re.I):
            h = re.search(r"\bhref=[\"']([^\"']+)[\"']", tag, re.I)
            out.append(h.group(1) if h else "")
    for m in re.finditer(r"<script\b[^>]*\bsrc=[\"']([^\"']+)[\"']", html, re.I):
        out.append(m.group(1))
    seen = []
    for h in out:
        h = h.split("?")[0].split("#")[0]
        if h and h not in seen:
            seen.append(h)
    return seen


def make(html: str, read_asset, src: str) -> dict:
    """{"src", "html", "assets": {href: sha}}: read_asset(href) returns the file's bytes, or None when it cannot be read."""
    assets = {}
    for h in asset_refs(html):
        try:
            b = read_asset(h)
        except Exception:  # noqa: BLE001  (an unreadable file is part of the fingerprint, not a crash)
            b = None
        assets[h] = sha(b) if b is not None else "unreadable"
    return {"src": src, "html": sha(normalize_html(html)), "page": sha(page_only(html)), "assets": assets}


def page_only(html: str) -> str:
    """The page's own markup: normalize_html with every linked CSS/JS address replaced by one placeholder, so a shared
    bundle that was rebuilt (its hashed file name changed) does not change it (2.4.8)."""
    out = normalize_html(html)
    for h in asset_refs(html):
        out = out.replace(h, "ASSET")
    return re.sub(r"/_astro/[\w.-]+\.(?:css|js)", "ASSET", out)


def same(a, b, mode: str = "built") -> bool:
    """True only when both fingerprints exist, come from the same kind of source, and every part is equal.
    mode "page_html" (growth.json evidence.fresh_on): the page's own markup must be equal; the shared CSS/JS bundles may
    differ, because every new page merged into a site rebuilds them. Old fingerprints without "page" use "html"."""
    if not (a and b and a.get("src") == b.get("src")):
        return False
    if mode == "page_html":
        if a.get("page") and b.get("page"):
            return a["page"] == b["page"]
        return a.get("html") == b.get("html")
    return a.get("html") == b.get("html") and a.get("assets") == b.get("assets")


def build_root(cfg: dict, project: Path, repo: Path | None) -> Path | None:
    b = cfg.get("build_dir") or cfg.get("site_dir")
    if not b:
        return None
    q = Path(b).expanduser()
    if q.is_absolute():
        return q
    base = repo if (repo and cfg.get("build_dir")) else project
    return base / q


def _built_file(root: Path, path: str) -> Path | None:
    p = paths.normalize(path or "/").strip("/")
    for c in ([root / "index.html"] if not p else [root / p / "index.html", root / f"{p}.html", root / p]):
        if c.is_file():
            return c
    return None


def fetch(url: str, timeout=30) -> bytes | None:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "GrowthGate/1.0 (read-only)"}), timeout=timeout) as r:
            return r.read()
    except Exception:  # noqa: BLE001
        return None


def current(cfg: dict, project: Path, repo: Path | None, path: str, url: str = "") -> dict | None:
    """The fingerprint of the page now, from the built output (build_dir) or else the preview URL; None when neither can be read."""
    root = build_root(cfg, project, repo)
    if root and root.is_dir():
        f = _built_file(root, path)
        if f:
            html = f.read_text(errors="replace")

            def read(h, root=root):
                if re.match(r"^(https?:)?//", h):
                    return None
                x = root / h.lstrip("/") if h.startswith("/") else f.parent / h
                return x.read_bytes() if x.is_file() else None
            return make(html, read, "build")
    if url:
        raw = fetch(url)
        if raw is not None:
            html = raw.decode("utf-8", "replace")
            return make(html, lambda h: fetch(urllib.parse.urljoin(url, h)), "url")
    return None


def attach(e: dict, cfg: dict, project: Path, repo: Path | None, url: str = "") -> None:
    """Put e["fp"] = {page: fingerprint} on a journal entry tagged as evidence, for each of its pages that can be read now."""
    if not set(e.get("tags") or []) & set(EVIDENCE_TAGS):
        return
    fps = {}
    for p in e.get("pages") or []:
        if p.startswith("/"):
            try:
                fp = current(cfg, project, repo, p, url)
            except Exception:  # noqa: BLE001
                fp = None
            if fp:
                fps[p] = fp
    if fps:
        e["fp"] = fps


# ---- stored with the evidence ------------------------------------------------------------------------------------------
def shots_sidecar(d: Path) -> dict:
    try:
        return json.loads((d / SIDECAR).read_text()) or {}
    except (OSError, ValueError):
        return {}


def record_shots(project: Path, key: str, page: str, fp: dict) -> list[str]:
    """Store the fingerprint in every research/*<key>*-shots/ folder; returns the folders written."""
    out = []
    rdir = project / "research"
    for d in sorted(rdir.iterdir()) if rdir.is_dir() else []:
        if d.is_dir() and key in d.name and d.name.endswith("-shots"):
            data = shots_sidecar(d)
            data[paths.key(page)] = fp
            (d / SIDECAR).write_text(json.dumps(data, indent=1) + "\n")
            out.append(d.name)
    return out


def main():
    from config import CFG, PROJECT, SITE_REPO
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for n in ("show", "record"):
        s = sub.add_parser(n)
        s.add_argument("page")
        s.add_argument("--url", default="")
        if n == "record":
            s.add_argument("--key", required=True)
    a = ap.parse_args()
    fp = current(CFG, PROJECT, SITE_REPO if CFG.get("site_repo") else None, a.page, a.url)
    if not fp:
        sys.exit("cannot read the page: set growth.json build_dir (the built site) or pass --url <the preview address>")
    if a.cmd == "show":
        print(json.dumps(fp, indent=1))
    else:
        done = record_shots(PROJECT, a.key, a.page, fp)
        print("fingerprint stored in: " + (", ".join(done) or "no research/*-shots/ folder for that key"))


if __name__ == "__main__":
    main()
