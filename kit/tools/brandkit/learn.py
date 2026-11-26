"""`growth brand-kit learn`: choose the pages, read them in one headless browser, build brand.generated.json."""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import fetch_rule  # noqa: E402
import sitemaps  # noqa: E402

from . import extract, snapshot, store  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (compatible; growth-ops-kit brand-kit)"}
MAX_ASSET = 300_000


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower().removeprefix("www.")


def on_base(url: str, base: str, cfg: dict) -> str:
    """A link to this site as an address on `base` ("" for another site)."""
    own = {_host(base)} | ({_host(cfg["site_url"])} if cfg.get("site_url") else set())
    u = urlsplit(url)
    return base.rstrip("/") + (u.path or "/") if _host(url) in own else ""


def choose_pages(base: str, cfg: dict, project, explicit=None, max_pages: int = 5, fetch=None) -> list[str]:
    """Addresses on `base`: the ones asked for, else the home page plus pages that look different from each other, taken from the
    inventory, else the sitemap, else the brand scan's page list. At most `max_pages`; every address is checked against the live-site rule."""
    base = base.rstrip("/")
    urls = []
    if explicit:
        for p in explicit:
            urls.append(p if p.startswith("http") else base + (p if p.startswith("/") else "/" + p))
    else:
        cands = _candidates(base, cfg, project, fetch)
        seen_kinds, picked = set(), ["/"]
        for path, kind in cands:
            k = kind or (path.strip("/").split("/")[0] if path.strip("/") else "")
            if path in picked or k in seen_kinds:
                continue
            seen_kinds.add(k)
            picked.append(path)
            if len(picked) >= max_pages:
                break
        urls = [base + p for p in picked]
    urls = list(dict.fromkeys(urls))
    for u in urls:
        fetch_rule.assert_may_fetch(u, cfg)
    return urls


def _candidates(base, cfg, project, fetch) -> list[tuple[str, str]]:
    inv = Path(project) / "inventory" / "inventory.json"
    try:
        rows = json.loads(inv.read_text()).get("pages", [])
    except (OSError, ValueError):
        rows = []
    rows = [r for r in rows if r.get("status", "live") == "live" and r.get("path")]
    if rows:
        rows.sort(key=lambda r: (not r.get("money_page"), r["type"] if r.get("type") not in ("home",) else "~"))
        return [(r["path"], r.get("type", "")) for r in rows if r["path"] != "/"]
    get = fetch or _get
    try:
        entries = sitemaps.read(base + "/sitemap.xml", get=sitemaps.on_origin(base, lambda u: (fetch_rule.assert_may_fetch(u, cfg), get(u))[1]))
        paths = [urlsplit(loc).path or "/" for loc, _ in entries]
        return [(p, "") for p in paths if p != "/"]
    except sitemaps.SitemapError:
        pass
    scan = store.read_json(Path(project) / "docs" / "brand-scan.json", {}) or {}
    return [(p["path"], p.get("category", "")) for p in scan.get("pages", []) if p.get("path", "").startswith("/") and "." not in p["path"].rsplit("/", 1)[-1]]


def _get(url: str):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
            return r.status, r.read(2_000_000).decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return 0, ""


def save_logo(tree: dict, d: Path, base: str, cfg: dict, fetch_bytes=None) -> str:
    """Keep the logo image next to the kit (assets/logo.<ext>) when it is a file on this site and small, so the guidelines page can hold it."""
    node = ((tree.get("logo") or {}).get("primary")) or {}
    src = node.get("value") or ""
    if not src.startswith("http") or node.get("svg"):
        return ""
    local = on_base(src, base, cfg)
    if not local:
        return ""
    ext = Path(urlsplit(local).path).suffix.lower()
    if ext not in (".svg", ".png", ".jpg", ".jpeg", ".webp", ".gif"):
        return ""
    fetch_rule.assert_may_fetch(local, cfg)
    try:
        data = (fetch_bytes or _get_bytes)(local)
    except Exception:  # noqa: BLE001  a logo that cannot be fetched is only a missing asset
        return ""
    if not data or len(data) > MAX_ASSET:
        return ""
    (d / "assets").mkdir(parents=True, exist_ok=True)
    for old in (d / "assets").glob("logo.*"):
        old.unlink()
    (d / "assets" / f"logo{ext}").write_bytes(data)
    return f"assets/logo{ext}"


def inline_svg_images(svg: str, page_url: str, base: str, cfg: dict, fetch_bytes=None) -> str:
    """A logo svg that draws its wordmark with <image href="/logo-word.svg"> keeps working on its own: the file is read from the preview
    (small ones only) and put in as a data: address."""
    import base64
    from urllib.parse import urljoin

    def swap(m):
        local = on_base(urljoin(page_url, m.group(2)), base, cfg)
        ext = Path(urlsplit(local).path).suffix.lower() if local else ""
        mime = {".svg": "image/svg+xml", ".png": "image/png", ".webp": "image/webp", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}.get(ext)
        if not mime:
            return m.group(0)
        fetch_rule.assert_may_fetch(local, cfg)
        try:
            data = (fetch_bytes or _get_bytes)(local)
        except Exception:  # noqa: BLE001
            return m.group(0)
        if not data or len(data) > 120_000:
            return m.group(0)
        return f'{m.group(1)}="data:{mime};base64,{base64.b64encode(data).decode()}"'
    return re.sub(r"""(?i)\b((?:xlink:)?href)\s*=\s*["']([^"'#][^"']*)["'](?=[^>]*>)""", lambda m: swap(m) if svg[:m.start()].lower().rsplit("<", 1)[-1].startswith("image") else m.group(0), svg)


def _get_bytes(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
        return r.read(MAX_ASSET + 1)


def learn(project, cfg: dict, base: str, explicit=None, max_pages: int = 5, today: str = "", snapshots=None) -> dict:
    """Read the site and write brand/brand.generated.json and brand/brand.json (never the overrides). `snapshots` lets a test pass
    recorded data instead of opening a browser. Returns the generated brand."""
    base = base.rstrip("/")
    fetch_rule.assert_may_fetch(base + "/", cfg)
    if snapshots is None:
        urls = choose_pages(base, cfg, project, explicit, max_pages)
        snapshots = snapshot.snapshot_pages(urls, cfg)
    good = [s for s in snapshots if "error" not in s]
    if not good:
        why = "; ".join(f"{s['url']}: {s['error']}" for s in snapshots[:3]) or "no page was given"
        raise SystemExit(f"Could not read any page ({why}). Is the preview running at {base}?")
    proj = Path(project)
    scan = store.read_json(proj / "docs" / "brand-scan.json")
    try:
        brand_md = (proj / "BRAND.md").read_text(errors="replace")
    except OSError:
        brand_md = ""
    gen = extract.build_generated(snapshots, scan, brand_md, cfg, base, today)
    gen["schema"] = store.SCHEMA
    d = store.brand_dir(project)
    d.mkdir(parents=True, exist_ok=True)
    if gen.get("logo", {}).get("primary"):
        prim = gen["logo"]["primary"]
        if prim.get("svg") and "<image" in prim["svg"].lower():
            prim["svg"] = inline_svg_images(prim["svg"], good[0]["url"], base, cfg)
        f = save_logo(gen, d, base, cfg)
        if f:
            gen["logo"]["primary"]["file"] = f
    (d / "brand.generated.json").write_text(store.dump(gen))
    store.write_merged(project)
    return gen
