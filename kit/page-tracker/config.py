"""The tracker's settings. The tracker is part of the kit; the project it tracks is a folder (growth.json at its root).

Where things live:
  CODE_DIR  this folder (kit/page-tracker): the code and the dashboard's html, css and js. Never written to.
  DATA_DIR  <project>/page-tracker: tracker.db, data.json, insights*.json, diffs/, logs, the sitemap copy. Git-ignored.

Where the values come from: the project's growth.json (site_url, sitemap_url, site_repo, timezone, silos, core_pages,
connectors, keys_file ...), then the optional "page_tracker" block of growth.json, then the optional
<project>/page-tracker/config.json (same shape as the block). A source (Skald, Search Console, GA4) is on only when growth.json
"connectors" switches it on AND its keys are in the keys file (growth.json keys_file, outside git): without a key the tracker
prints one plain note and goes on with the sources that are free (the sitemap, the site's git history, Google's status feed).
No secret is ever kept in any config file."""
import json, os, sys  # noqa: F401
from zoneinfo import ZoneInfo

CODE_DIR = os.path.dirname(os.path.abspath(__file__))
import importlib.util  # noqa: E402

# The kit's project discovery (kit/tools/config.py) has the same file name as this module: load it under its own name.
_spec = importlib.util.spec_from_file_location("growth_project_config", os.path.join(os.path.dirname(CODE_DIR), "tools", "config.py"))
_project = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_project)

PROJECT = str(_project.require_project())
GROWTH = _project.load_cfg(_project.Path(PROJECT))
DATA_DIR = os.path.join(PROJECT, "page-tracker")
os.makedirs(DATA_DIR, exist_ok=True)
HERE = DATA_DIR                      # modules write their output next to the data, never next to the code


def _merge(a, b):
    out = dict(a)
    for k, v in (b or {}).items():
        out[k] = _merge(out[k], v) if isinstance(out.get(k), dict) and isinstance(v, dict) else v
    return out


def _load_local():
    f = os.path.join(DATA_DIR, "config.json")
    return json.load(open(f, encoding="utf-8")) if os.path.exists(f) else {}


def _kit_version():
    f = os.path.join(os.path.dirname(CODE_DIR), "VERSION")
    return open(f).read().strip() if os.path.exists(f) else "0.0.0"


def _derive():
    """Tracker settings derived from growth.json."""
    g = GROWTH
    silos = g.get("silos") or {}
    core = list((g.get("core_pages") or {}).keys()) or ["/"]
    clusters = [dict(id="core", name="Core pages", exact=core)]
    clusters += [dict(id=s, name=label, prefix="/" + s) for s, label in silos.items()]
    clusters += [dict(id="other", name="Other pages", prefix="/")]
    conn = g.get("connectors") or {}
    on = lambda n: bool((conn.get(n) or {}).get("on"))  # noqa: E731
    return dict(
        product=g.get("product") or g.get("name") or "the site", version=_kit_version(),
        site_url=g.get("site_url", ""), sitemap_url=g.get("sitemap_url") or g.get("site_url", "").rstrip("/") + "/sitemap.xml",
        site_repo=g.get("site_repo") or "", site_branch=g.get("site_branch", "main"), timezone=g.get("timezone", "UTC"),
        port=int(g.get("tracker_port", 18700)), db_path="tracker.db", tracking_start=g.get("search_console_history_start"),
        changes_since=None, path_variants=[""], content_dirs=g.get("content_dirs") or {}, page_sources=g.get("page_sources") or {},
        clusters=clusters,
        sources={"sitemap": {"on": True}, "google_updates": {"on": on("google_updates") if "google_updates" in conn else True},
                 "skald": {"on": on("skald"), "key_file": os.path.basename(g.get("keys_file", "") or "keys.env")},
                 "search_console": {"on": on("search_console"), "via": (conn.get("search_console") or {}).get("via", "skald"),
                                    "history_start": g.get("search_console_history_start")},
                 "ga4": {"on": on("ga4"), "via": (conn.get("ga4") or {}).get("via", "skald")},
                 "bing": {"on": on("bing")}},
        ai_summary={"on": False, "mode": "mock", "model": "claude-haiku-5-5"})


CFG = _merge(_merge(_derive(), GROWTH.get("page_tracker") or {}), _load_local())


def _path(p):
    p = os.path.expanduser(p)
    return p if os.path.isabs(p) else os.path.abspath(os.path.join(PROJECT, p))


PRODUCT = CFG.get("product", "the site")
SITE = CFG["site_url"].rstrip("/")
SITE_HOST = CFG.get("site_host") or SITE.split("//", 1)[-1]
SITEMAP_URL = CFG["sitemap_url"]
REPO = _path(CFG["site_repo"]) if CFG.get("site_repo") else os.path.join(DATA_DIR, "no-site-repo")
BRANCH = CFG.get("site_branch", "main")
BLOG = GROWTH.get("blog_path", "/blog").rstrip("/")
TZ = ZoneInfo(CFG.get("timezone", "UTC"))
PORT = int(CFG.get("port", 18700))
DB = os.path.join(DATA_DIR, CFG.get("db_path", "tracker.db"))
KEYS_FILE = _project.resolve_in(_project.Path(PROJECT), GROWTH["keys_file"]) if GROWTH.get("keys_file") else None
SECRETS_DIR = str(KEYS_FILE.parent) if KEYS_FILE else os.path.join(DATA_DIR, "no-secrets")
TRACKING_START = CFG.get("tracking_start")        # first day the tracker's history is meant to cover
CHANGES_SINCE = CFG.get("changes_since")          # None = every change in the repo's git history counts
VARIANTS = list(CFG.get("path_variants") or [""])  # page copies added together ("" = the page itself)
CONTENT_DIRS = CFG.get("content_dirs", {})
PAGE_SOURCES = CFG.get("page_sources", {})
CLUSTERS = CFG.get("clusters", [])
SOURCES = CFG.get("sources", {})
AI = CFG.get("ai_summary", {})


def source_on(name):
    """True when a data source is switched on in growth.json "connectors". A source read through Skald is on only when Skald is too."""
    s = SOURCES.get(name) or {}
    if not s.get("on"):
        return False
    if s.get("via") == "skald" and not (SOURCES.get("skald") or {}).get("on"):
        return False
    return True


def trailing_slash():
    """Does the site's own address of a page end in "/" (/blog/post/)? growth.json page_tracker.trailing_slash, else what
    the sitemap showed (sitemap-cache.json). Analytics tools key pages by the exact address, so /x and /x/ differ."""
    if CFG.get("trailing_slash") is not None:
        return bool(CFG["trailing_slash"])
    try:
        return bool(json.load(open(os.path.join(DATA_DIR, "sitemap-cache.json"), encoding="utf-8")).get("trailing_slash"))
    except (OSError, ValueError):
        return False


def variants(path):
    """The copies of a page that are added together (just the page itself by default), each in the site's own address
    form: the tracker keeps paths without a trailing slash, the site (and Search Console) may use one."""
    out = [v + path if v else path for v in VARIANTS]
    if trailing_slash():
        out = [x if x == "/" or x.endswith("/") else x + "/" for x in out]
    return out


def cluster_of(path):
    """Cluster id for a page path, from the rules (first match wins; exact beats prefix, the longest prefix wins)."""
    p = path.rstrip("/") or "/"
    for cl in CLUSTERS:
        if p in [x.rstrip("/") or "/" for x in cl.get("exact", [])]:
            return cl["id"]
    best, best_len = None, -1
    for cl in CLUSTERS:
        pre = cl.get("prefix")
        if not pre:
            continue
        pn = pre.rstrip("/")
        if (p == pn or p.startswith(pn + "/")) and len(pn) > best_len:
            best, best_len = cl["id"], len(pn)
    return best or CLUSTERS[0]["id"]


def cluster_names():
    return {cl["id"]: cl["name"] for cl in CLUSTERS}


def cluster_order():
    return [cl["id"] for cl in CLUSTERS]


def public():
    """The few values the dashboard needs (written into data.json; nothing secret)."""
    return dict(product=PRODUCT, site_url=SITE, site_host=SITE_HOST, timezone=CFG.get("timezone"),
                tracking_start=TRACKING_START, variants=VARIANTS,
                conversion_path=GROWTH.get("conversion_path") or "",
                sources={k: source_on(k) for k in SOURCES}, ai_summary=bool(AI.get("on")))
