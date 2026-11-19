#!/usr/bin/env python3
"""Detect, never ask, what a site's files and sitemap already say (library; `growth wizard` shows the result to confirm).

  growth detect --repo <site repo> [--sitemap <url-or-file>]     # print what was found, as JSON

  stack            from the repo: astro.config.*, next.config.*, hugo.toml, _config.yml, ... (and the growth.json stack it means)
  commands         the local build and preview commands (package.json scripts, or the generator's own)
  sitemap          index or urlset, how many child sitemaps, how many pages
  trailing_slash   "slash" (/about/), "no-slash" (/about) or "mixed", from the sitemap's own addresses
  languages        language copies (/en-us/...) and whether the sitemap carries hreflang alternates
  redirects        the files that hold redirects; content_dirs: the folders content lives in

Only the sitemap files are read, never a page of the live site.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sitemaps  # noqa: E402

# (marker file glob in the repo root, framework, growth.json stack, build dir, build command, preview command)
GENERATORS = [
    ("astro.config.*", "astro", "static", "dist", "npm run build", "npm run preview"),
    ("next.config.*", "nextjs", "nextjs", ".next", "npm run build", "npm run start"),
    ("nuxt.config.*", "nuxt", "static", ".output/public", "npm run build", "npm run preview"),
    ("svelte.config.*", "sveltekit", "static", "build", "npm run build", "npm run preview"),
    ("gatsby-config.*", "gatsby", "static", "public", "npm run build", "npm run serve"),
    ("eleventy.config.*", "eleventy", "static", "_site", "npx @11ty/eleventy", "npx @11ty/eleventy --serve"),
    (".eleventy.js", "eleventy", "static", "_site", "npx @11ty/eleventy", "npx @11ty/eleventy --serve"),
    ("hugo.toml", "hugo", "static", "public", "hugo", "hugo server"),
    ("hugo.yaml", "hugo", "static", "public", "hugo", "hugo server"),
    ("_config.yml", "jekyll", "static", "_site", "bundle exec jekyll build", "bundle exec jekyll serve"),
    ("mkdocs.yml", "mkdocs", "static", "site", "mkdocs build", "mkdocs serve"),
]
REDIRECT_FILES = ["_redirects", "public/_redirects", "static/_redirects", "vercel.json", "netlify.toml", "redirects.json",
                  "src/redirects.json", ".htaccess", "public/.htaccess"]
CONTENT_DIRS = ["src/content", "content", "src/pages", "pages", "app", "src/posts", "posts", "_posts", "blog", "docs"]
LANG_SEGMENT = re.compile(r"^[a-z]{2}(?:-[a-z]{2})?$")
LANG_CODES = {"en", "fr", "de", "es", "it", "pt", "nl", "sv", "ja", "ko", "zh", "ar", "hi", "pl", "ru", "tr"}


def detect_stack(repo: Path) -> dict:
    repo = Path(repo)
    for pattern, framework, stack, build_dir, build, preview in GENERATORS:
        hit = next(iter(sorted(repo.glob(pattern))), None)
        if hit:
            pkg = _package_scripts(repo)
            return {"framework": framework, "stack": stack, "evidence": hit.name, "build_dir": build_dir,
                    "build_cmd": "npm run build" if "build" in pkg and build.startswith("npm") else build,
                    "preview_cmd": next((f"npm run {s}" for s in ("preview", "start", "serve", "dev") if s in pkg and preview.startswith("npm")), preview)}
    pkg = _package_scripts(repo)
    if pkg:
        return {"framework": "node", "stack": "static", "evidence": "package.json", "build_dir": "",
                "build_cmd": "npm run build" if "build" in pkg else "", "preview_cmd": next((f"npm run {s}" for s in ("preview", "start", "dev") if s in pkg), "")}
    if (repo / "index.html").is_file():
        return {"framework": "plain html", "stack": "static", "evidence": "index.html", "build_dir": "", "build_cmd": "", "preview_cmd": "python3 -m http.server"}
    return {}


def _package_scripts(repo: Path) -> dict:
    try:
        return json.loads((Path(repo) / "package.json").read_text()).get("scripts") or {}
    except (OSError, ValueError):
        return {}


def detect_layout(repo: Path) -> dict:
    repo = Path(repo)
    redirects = []
    for f in REDIRECT_FILES:
        p = repo / f
        if not p.is_file():
            continue
        if f in ("vercel.json", "netlify.toml") and "redirect" not in p.read_text(errors="replace").lower():
            continue
        redirects.append(f)
    for cfg in sorted(repo.glob("next.config.*")):
        if "redirects" in cfg.read_text(errors="replace"):
            redirects.append(cfg.name)
    return {"redirects": redirects, "content_dirs": [d for d in CONTENT_DIRS if (repo / d).is_dir()]}


def _documents(source: str, get, depth: int = 0, folder=None):
    """Every sitemap document under `source` as (source, body): the index first, then its children (two levels)."""
    body, folder = sitemaps._load(str(source), get, folder)
    yield source, body
    is_index, entries = sitemaps.parse(body)
    if is_index and depth < sitemaps.MAX_DEPTH:
        for child, _ in entries:
            yield from _documents(child, get, depth + 1, folder)


def detect_sitemap(source: str, get=None) -> dict:
    """The sitemap's shape. Raises sitemaps.SitemapError when it cannot be read."""
    get = get or sitemaps.default_get
    docs = list(_documents(source, get))
    is_index = sitemaps.parse(docs[0][1])[0]
    pages = sitemaps.read(source, get)
    locs = [loc for loc, _ in pages]
    paths = [re.sub(r"^[a-z]+://[^/]+", "", loc).split("?")[0] or "/" for loc in locs]
    inner = [p for p in paths if p != "/"]
    slashed = sum(1 for p in inner if p.endswith("/"))
    form = "mixed" if 0 < slashed < len(inner) else ("slash" if inner and slashed == len(inner) else "no-slash")
    segs: dict[str, int] = {}
    for p in inner:
        first = p.strip("/").split("/", 1)[0].lower()
        if "-" in first and LANG_SEGMENT.match(first) or first in LANG_CODES:
            segs[first] = segs.get(first, 0) + 1
    langs = sorted(segs)
    hreflang = any("hreflang" in body for _, body in docs)
    return {"shape": "index" if is_index else "urlset", "children": len(docs) - 1 if is_index else 0, "pages": len(locs),
            "trailing_slash": form, "languages": langs, "hreflang": hreflang}


def detect_all(repo: Path | None, sitemap: str = "", get=None) -> dict:
    out: dict = {}
    if repo and Path(repo).is_dir():
        out["stack"] = detect_stack(repo)
        out.update(detect_layout(repo))
    if sitemap:
        try:
            out["sitemap"] = detect_sitemap(sitemap, get)
        except sitemaps.SitemapError as e:
            out["sitemap_error"] = str(e)
    return out


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default="")
    ap.add_argument("--sitemap", default="")
    a = ap.parse_args(argv)
    print(json.dumps(detect_all(Path(a.repo) if a.repo else None, a.sitemap), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
