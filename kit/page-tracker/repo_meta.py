"""Read-only facts from the site repo (growth.json: site_repo) for every page: which content file it is built from,
and the title and description Google shows. Nothing is ever written to the repo.

How a Next.js site that keeps Markdown in content/ builds an address (growth.json content_dirs, blog_path), mirrored here:
  post  content/posts/<slug>.md   -> /<vertical>/<blog>/<slug>   (or /<blog>/<slug> when it has no vertical)
  page  content/pages/<slug>.md   -> /<vertical>/<slug>        (or /<slug> when it has no vertical)
Pages with no markdown file (home, pricing, topic pages) are built from files listed in growth.json page_tracker.page_sources, or
`page_sources`. Frontmatter: title, slug, vertical, date, updated, excerpt, metaTitle, metaDescription, draft.
Any other layout (Astro, Hugo, JSON pages): growth.json page_tracker.content_globs, see glob_docs().
"""
import glob, json, os, subprocess
import yaml
import config

REPO = config.REPO


def git(*args):
    return subprocess.run(["git", "-C", REPO, *args], capture_output=True, text=True, check=True).stdout


def repo_ok():
    return os.path.isdir(os.path.join(REPO, ".git")) or os.path.isfile(os.path.join(REPO, ".git"))


def branch_ref():
    """The branch to read history from: the configured one, else HEAD."""
    for ref in (config.BRANCH, "origin/" + config.BRANCH):
        try:
            git("rev-parse", "--verify", "-q", ref)
            return ref
        except subprocess.CalledProcessError:
            continue
    return "HEAD"


def split_md(text):
    """(frontmatter dict, body) of a markdown file."""
    if text.startswith("---"):
        parts = text.split("\n---", 1)
        if len(parts) == 2:
            try:
                fm = yaml.safe_load(parts[0][3:]) or {}
            except yaml.YAMLError:
                fm = {}
            return (fm if isinstance(fm, dict) else {}), parts[1].lstrip("-\n")
    return {}, text


def parse(text, rel):
    """(fields dict, body text) for a content file at any commit: markdown frontmatter, or code (no fields)."""
    return split_md(text)


def docs():
    """Every markdown content file: [{kind, rel, fm, url}]."""
    out = []
    for kind in ("posts", "pages"):
        d = config.CONTENT_DIRS.get(kind)
        if not d:
            continue
        for f in sorted(glob.glob(os.path.join(REPO, d, "*.md"))):
            try:
                fm, _ = split_md(open(f, encoding="utf-8").read())
            except OSError:
                continue
            slug = fm.get("slug") or os.path.basename(f)[:-3]
            v = fm.get("vertical")
            if kind == "posts":
                url = f"/{v}{config.BLOG}/{slug}" if v else f"{config.BLOG}/{slug}"
            else:
                url = f"/{v}/{slug}" if v else f"/{slug}"
            out.append(dict(kind=kind, rel=os.path.relpath(f, REPO), fm=fm, url=url))
    return out


class _Missing(dict):
    def __missing__(self, k):
        raise KeyError(k)


def glob_docs():
    """Content files mapped by growth.json page_tracker.content_globs, for any stack: each entry is
    {"glob": "src/content/blog/*.md", "address": "/{cluster}/{slug}/", "values": {"cluster": {"id": "folder"}}}; the
    address is filled from the file's own
    fields (Markdown front matter or the top level of a JSON file). A file missing a field, or marked draft, is skipped.
    Addresses are kept without their trailing slash, as the tracker stores paths."""
    out = []
    for g in config.CONTENT_GLOBS:
        pattern, template = g.get("glob"), g.get("address")
        if not pattern or not template:
            continue
        for f in sorted(glob.glob(os.path.join(REPO, pattern))):
            try:
                text = open(f, encoding="utf-8").read()
                fm = json.loads(text) if f.endswith(".json") else split_md(text)[0]
            except (OSError, ValueError):
                continue
            if not isinstance(fm, dict) or fm.get("draft"):
                continue
            fields = dict(fm)
            fields.setdefault("slug", os.path.splitext(os.path.basename(f))[0])
            for k, m in (g.get("values") or {}).items():   # a field whose address part differs, e.g. cluster id -> folder
                if fields.get(k) in m:
                    fields[k] = m[fields[k]]
            try:
                url = template.format_map(_Missing({k: v for k, v in fields.items() if isinstance(v, (str, int))}))
            except (KeyError, ValueError):
                continue
            url = "/" + url.strip("/") if url.strip("/") else "/"
            out.append(dict(kind="posts" if f.endswith(".md") else "pages", rel=os.path.relpath(f, REPO), fm=fm, url=url))
    return out


def files():
    """path -> content file (relative to the repo) for every page the repo can tell us about."""
    out = {}
    for p, srcs in config.PAGE_SOURCES.items():
        if srcs:
            out[p] = srcs[0]
    for d in docs() + glob_docs():
        out.setdefault(d["url"], d["rel"])
    return out


def sources(path):
    """All repo files a page is built from (for change history)."""
    f = files().get(path)
    extra = config.PAGE_SOURCES.get(path)
    if extra:
        return list(extra)
    return [f] if f else []


def meta(rel):
    """The title and description Google is given for a content file, as it is in the working tree now."""
    try:
        fields, _ = parse(open(os.path.join(REPO, rel), encoding="utf-8").read(), rel)
    except OSError:
        return {}
    return dict(title=fields.get("metaTitle") or fields.get("title"),
                description=fields.get("metaDescription") or fields.get("excerpt"), h1=fields.get("title"))
