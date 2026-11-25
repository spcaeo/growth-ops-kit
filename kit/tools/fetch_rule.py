"""One check every fetcher runs before it asks a web address: is the live site off limits?

growth.json `live_site_rule: no-crawl` means no tool of the kit may request pages from the live host. Local addresses
and the project's `preview_url` are always fine. Use `assert_may_fetch(url)` in front of every network read.
"""
from __future__ import annotations

from urllib.parse import urlsplit


def _host(url: str) -> str:
    return (urlsplit(url or "").hostname or "").lower().removeprefix("www.")


def no_crawl(cfg: dict) -> bool:
    return str(cfg.get("live_site_rule") or "").startswith("no-crawl")


def is_live(url: str, cfg: dict) -> bool:
    """True when the address is on the project's live host (www or not)."""
    live = _host(cfg.get("site_url") or "")
    return bool(live) and _host(url) == live


def blocked(url: str, cfg: dict | None = None) -> bool:
    if cfg is None:
        import config
        cfg = config.CFG
    return no_crawl(cfg) and is_live(url, cfg)


def assert_may_fetch(url: str, cfg: dict | None = None, sitemap_only: bool = False) -> None:
    """Exit with a plain refusal when the live-site rule is no-crawl and the address is on the live host.
    sitemap_only=True: the sitemap files alone (`growth inventory --no-pages`), no page is visited; the page tracker reads
    them the same way."""
    if sitemap_only:
        return
    if blocked(url, cfg):
        if cfg is None:
            import config
            cfg = config.CFG
        preview = cfg.get("preview_url") or "a local preview address"
        raise SystemExit(
            f"REFUSED: growth.json says live_site_rule is no-crawl, and {url} is on the live site. "
            f"Run this against the preview instead (--base {preview}), or ask the owner to change the rule.")
