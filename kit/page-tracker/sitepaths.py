"""Every public page of the site: from the live sitemap (growth.json: sitemap_url), else the last copy of it, else the
site repo's own content. One plain GET, at most once a day (kept in sitemap-cache.json). Nothing else is fetched.
Each page: path (no trailing slash, "/" for the home page) and its <lastmod> when the sitemap gives one.
  python3 sitepaths.py [--force]
"""
import json, os, re, sys, urllib.error, urllib.request, datetime as dt
import config, repo_meta

sys.path.insert(0, os.path.join(os.path.dirname(config.CODE_DIR), "tools"))
import sitemaps  # noqa: E402  (the kit's one sitemap reader)

HERE = config.HERE
CACHE = os.path.join(HERE, "sitemap-cache.json")
UA = "page-tracker/1.0 (local dashboard; sitemap read once a day)"


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/xml,text/xml,*/*"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def _status_get(url):
    try:
        return 200, _get(url)
    except urllib.error.HTTPError as e:
        return e.code, ""


def to_path(loc):
    for pre in (config.SITE, config.SITE.replace("https://", "https://www."), config.SITE.replace("https://", "http://")):
        if loc.startswith(pre):
            p = loc[len(pre):].split("#", 1)[0].split("?", 1)[0] or "/"
            if not p.startswith("/"):
                p = "/" + p
            return p if p == "/" else p.rstrip("/")
    return None  # another host: not ours


def repo_pages():
    """The pages the repo would publish today: published (not draft, date reached) posts and pages, plus the app pages."""
    today = dt.date.today().isoformat()
    paths = {}
    for d in repo_meta.docs():
        fm = d["fm"]
        if fm.get("draft"):
            continue
        if str(fm.get("date") or "0000") > today:
            continue
        paths[d["url"]] = str(fm.get("updated") or fm.get("date") or "") or None
    for p in config.PAGE_SOURCES:
        paths.setdefault(p, None)
    return [dict(path=p, lastmod=lm) for p, lm in sorted(paths.items())]


def fetch(force=False):
    """{fetched, source: 'sitemap'|'cache'|'repo', pages: [{path, lastmod}], error, stale}."""
    now = dt.datetime.now(config.TZ)
    today = now.date().isoformat()
    cached = None
    if os.path.exists(CACHE):
        try:
            cached = json.load(open(CACHE, encoding="utf-8"))
        except ValueError:
            cached = None
    if config.source_on("sitemap"):
        if cached and not force and cached.get("source") == "sitemap" and cached.get("fetched", "")[:10] == today and cached.get("pages"):
            return cached
        try:
            pages, seen = [], set()
            for loc, lm in sitemaps.read(config.SITEMAP_URL, get=_status_get):   # follows a sitemap index
                p = to_path(loc)
                if p and p not in seen:
                    seen.add(p); pages.append(dict(path=p, lastmod=lm))
            if not pages:
                raise ValueError("the sitemap lists no page")
            out = dict(fetched=now.isoformat(timespec="minutes"), source="sitemap", pages=pages, error=None)
            json.dump(out, open(CACHE, "w", encoding="utf-8"), indent=1)
            return out
        except Exception as e:
            err = f"{type(e).__name__}: {e}"[:300]
            if cached and cached.get("pages"):
                cached["stale"] = err
                return cached
    else:
        err = "sitemap source is off"
    out = dict(fetched=now.isoformat(timespec="minutes"), source="repo", pages=repo_pages(), error=err)
    return out


def all_paths():
    return sorted(p["path"] for p in fetch()["pages"])


if __name__ == "__main__":
    r = fetch(force="--force" in sys.argv)
    print("source", r["source"], "fetched", r.get("fetched"), "error", r.get("error"), "stale", r.get("stale"))
    print(len(r["pages"]), "pages")
