"""What the site code and its branch show: links, shared components, the branch, commits, build safety
(rules 34, 36c, 41, 42, 52, 58, 67, 73, 75, 76, 79, 88, 88a, 89, 99, 100, 102, 104, 107, 110, 112, 114, 118-120,
122-124, 131, 148, 157)."""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

from techseo.dom import find_all

from gatelib import components, domx
from gatelib.core import ALL, Missing, Skip, check, run, short

SECRET = r"(AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY|SKALD_MCP_TOKEN\s*=|ghp_[A-Za-z0-9]{30,}|xox[bp]-[A-Za-z0-9-]{20,})"
MOTION_LIBS = ("framer-motion", "motion", "gsap", "animejs", "lottie-web", "lottie-react", "react-spring", "@react-spring/web", "aos")
CMS_LIBS = ("contentful", "@payloadcms/next", "@strapi/strapi", "@sanity/client", "tinacms", "@builder.io/react", "decap-cms")
SHARED = {"StickyCta": "components/sticky-cta", "CallDialog": "components/call-dialog", "ExitOffer": "components/exit-offer",
          "LinkCards": "components/link-cards", "CopyButton": "components/copy-button"}
# the same shared components by the name growth.json "components" and ctx.component() use (2.6.0)
SHARED_KEY = {"StickyCta": "sticky_cta", "CallDialog": "call_dialog", "ExitOffer": "exit_offer", "LinkCards": "link_cards",
              "CopyButton": "copy"}


def link_map(ctx, cmd):
    if ctx.stack() != "nextjs":      # no app/ folder: the same answers from the crawled link graph (2.6.0)
        from gatelib import graph_links
        return graph_links.link_map(ctx, cmd)
    key = "lm-" + cmd
    if key not in ctx.cache:
        tool = ctx.kit_dir / "adapters" / "nextjs" / "link_map.py"
        if not tool.exists():
            raise Missing("growth link_map", "restore growth link_map (rule 88a)")
        code, out = run([sys.executable, str(tool), cmd, ctx.need_path(), "--repo", str(ctx.need_repo()), "--json"], timeout=240)
        try:
            ctx.cache[key] = json.loads(out[out.index("{"):])
        except ValueError:
            raise Missing(f"link_map.py {cmd} output", f"run growth link_map {cmd} {ctx.path} --json and fix it ({short(out, 80)})")
    return ctx.cache[key]


def link_check(ctx, whole_site=False):
    """growth link_map check <path> | --all (orphan, weak, no-hub, not-on-hub, siblings<2, to-redirect, to-gone,
    to-not-live, to-unknown, dup-anchor) as {path: [(flag, detail)]}."""
    if ctx.stack() != "nextjs":
        from gatelib import graph_links
        return graph_links.link_check(ctx, whole_site)
    key = "lm-check-all" if whole_site else "lm-check"
    if key not in ctx.cache:
        tool = ctx.kit_dir / "adapters" / "nextjs" / "link_map.py"
        if not tool.exists():
            raise Missing("growth link_map", "restore growth link_map (rules 75, 88, 90)")
        target = ["--all"] if whole_site else [ctx.need_path()]
        code, out = run([sys.executable, str(tool), "check", *target, "--repo", str(ctx.need_repo()), "--json"], timeout=240)
        try:
            d = json.loads(out[out.index("{"):])
        except ValueError:
            raise Missing("link_map.py check output", f"run growth link_map check {' '.join(target)} --repo <worktree> ({short(out, 80)})")
        ctx.cache[key] = {r["path"]: [(f["flag"], f["detail"]) for f in r["flags"]] for r in d["rows"]}
    return ctx.cache[key]


def flags_of(ctx, names):
    checked = link_check(ctx)
    return [f"{f}: {t}" for f, t in checked.get(ctx.need_path(), checked.get(ctx.key_path(), [])) if f in names]


@check("links.cards", "36c", what="'+' link previews: data-link-cards on the content container, the shared LinkCards, its guard test", needs="repo")
def link_cards(ctx):
    root = ctx.root()
    probs = []
    m = domx.main(root)
    nx = ctx.stack() == "nextjs"
    comp = ctx.component("link_cards")
    prefix = components.css_prefix(ctx)
    if nx:
        if not any(n.get("data-link-cards") is not None and "data-link-cards" in n.attrs for n in m.iter()):
            probs.append("no data-link-cards on the page's content container")
        if "<LinkCards" not in "\n".join(ctx.tree_sources().values()):
            probs.append("the page does not render the shared <LinkCards>")
        tests = [p for p in ctx.repo_files(("lib/*.test.ts", "components/*.test.ts")) if "link-card" in p.name]
    else:
        # the site's own marker (growth.json components.link_cards_marker, e.g. data-lc) or the component's own element in the page
        marker = (ctx.cfg.get("components") or {}).get("link_cards_marker")
        drawn = re.search(r"""class=["'][^"']*(?<![\w-])""" + re.escape(prefix) + r"""(?![\w-])""", ctx.need_html())
        if marker:
            drawn = drawn or re.search(r"(?<![\w-])" + re.escape(marker) + r"(?![\w-])", ctx.need_html())
        if not (comp and comp.is_file()):
            probs.append("no shared link-preview component found (set growth.json components.link_cards)")
        elif not drawn:
            probs.append(f"the page does not render the shared {comp.stem} (no element with class .{prefix})")
        if comp and comp.is_file() and not components.in_tree(ctx, comp) and not drawn:
            probs.append(f"the page's source does not import {comp.stem}")
        tests = [t for t in ctx.test_files() if "linkcard" in components.flat(t.stem)]
    if not tests:
        probs.append("no link-cards guard test in the site repo")
    # The component must agree with the gate on what is chrome: a fold's own <header>/<footer> inside <main> is content
    # (domx.in_chrome). A blanket "header"/"footer" in SKIP_ZONE silently strips the "+" and the blue from heading-block
    # links (found once when a page had worked around it page by page).
    lc = (ctx.need_repo() / "components" / "link-cards.tsx")
    zone = re.search(r'SKIP_ZONE\s*=\s*"([^"]*)"', lc.read_text()) if lc.exists() else None
    blanket = zone and any(t.strip() in ("header", "footer") for t in zone.group(1).split(","))
    if blanket:
        hit = [a for a in find_all(m, "a") if (ctx.internal_path(a.get("href")) or "").startswith("/")
               and domx.up(a.parent, lambda x: x.tag in ("header", "footer")) is not None and not domx.in_chrome(a)]
        if hit:
            probs.append(f"{len(hit)} content link(s) sit in a fold's <header>/<footer>, which LinkCards' SKIP_ZONE skips as "
                         f"site chrome (no '+', not blue), e.g. '{short(domx.text(hit[0]), 50)}'")
    # The page must also SHIP the previews' styles: the author page rendered <LinkCards> without app/link-cards.css, so its
    # "+" buttons were 0 x 0 Tab stops and a card opened unstyled at the foot of the page (evidence helper, 18 Nov 2026).
    css_src = ctx.need_repo() / "app" / "link-cards.css"
    # every class the file defines must ship (another stylesheet may mention one of them in an override)
    marker = sorted(set(re.findall(r"\.(lcx-[a-z0-9-]+)", css_src.read_text()))) if css_src.exists() else []
    if not nx and comp and comp.is_file():       # the component's block class must be styled in what the page loads
        marker = [prefix]
    if marker and ctx.url:
        import urllib.parse
        import urllib.request
        sheets = re.findall(r'<link[^>]+rel="stylesheet"[^>]+href="([^"]+)"|<link[^>]+href="([^"]+\.css[^"]*)"[^>]+rel="stylesheet"',
                            ctx.need_html())
        served = "\n".join(re.findall(r"(?s)<style\b[^>]*>(.*?)</style>", ctx.need_html()))
        for a, b in sheets:
            u = urllib.parse.urljoin(ctx.url, a or b)
            if urllib.parse.urlsplit(u).netloc != urllib.parse.urlsplit(ctx.url).netloc:
                continue
            try:
                served += urllib.request.urlopen(u, timeout=60).read().decode("utf-8", "replace")
            except Exception as e:  # noqa: BLE001
                probs.append(f"stylesheet {a or b} did not load ({e})")
        lack = [c for c in marker if f".{c}" not in served]
        if lack:
            probs.append(f"the page renders LinkCards but its stylesheets lack {', '.join('.' + c for c in lack[:4])}: "
                         "the link-card stylesheet is not loaded")
    ctx.verdict(probs, "link previews switched on, styled and guarded", "add data-link-cards to the content container and render <LinkCards>; "
                "load app/link-cards.css (best: the component imports it); "
                "skip only site chrome in SKIP_ZONE (a header or footer inside <main> is content) (rule 36c)")


@check("links.inbound", "88", what="at least two other pages link here from their content; a post links up to its hub, sits on its guide list and links to 2+ siblings", needs="repo")
def inbound(ctx):
    d = link_map(ctx, "inbound")
    srcs = {l["src"] for l in d.get("links", []) if l.get("where") in ("body", "hub-list") and l.get("src") != ctx.key_path()}
    probs = flags_of(ctx, ("orphan", "weak", "no-hub", "not-on-hub", "siblings<2"))
    if len(srcs) < 2 and not probs:
        probs.append(f"only {len(srcs)} page(s) link here from their content")
    ctx.verdict(probs, f"{len(srcs)} pages link here from their content; link_map.py check: no orphan, weak or cluster flag",
                f"add content links from its cluster (growth link_map suggest {ctx.path}; check with link_map.py check {ctx.path}) (rule 88)")


@check("links.plan", "88a", types=("money", "hub"), what="the internal-link plan is filed: journal entries tagged internal-link against source pages", needs="repo")
def link_plan(ctx):
    p = ctx.need_path()
    ents = [e for e in ctx.journal() if "internal-link" in (e.get("tags") or [])]
    planned = [e for e in ents if p in (e.get("title", "") + " " + e.get("text", "")) and (e.get("pages") or []) != [p]]
    research = ctx.research(r"internal-link")
    silo = next((k for k in ctx.cfg.get("silos", {}) if p.strip("/") == k), None)
    probs = []
    if silo:  # the plan covers the whole cluster: no post of the silo left orphan, weak, off the hub or unlinked
        for q, fl in sorted(link_check(ctx, whole_site=True).items()):
            if q.startswith(f"/{silo}/"):
                probs += [f"{q}: {f}" for f, _ in fl if f in ("orphan", "weak", "no-hub", "not-on-hub", "siblings<2")]
    if len(planned) < 3:
        probs.append(f"{len(planned)} planned link(s) filed against source pages (3 or more needed)")
    if not research:
        probs.append(f"no research/*{ctx.key}*internal-link* plan file")
    link_map(ctx, "suggest")         # the link source must be readable (Next.js: link_map.py; any other stack: a fresh link graph)
    ctx.verdict(probs, f"{len(planned)} planned links filed in the journal", f"growth link_map suggest {p}; file each with growth journal add --page <source> --tag internal-link (rule 88a)")


@check("links.no-redirect", "75", what="no internal link points at a redirect, a 410, a draft or an unknown address", needs="repo")
def no_redirect(ctx):
    d = link_map(ctx, "outbound")
    moved = [f"{l['to']} -> {l['final']}" for l in d.get("links", []) if l.get("moved") or (l.get("final") and l.get("final") != l.get("to"))]
    probs = sorted(set(moved)) + flags_of(ctx, ("to-redirect", "to-gone", "to-not-live", "to-unknown"))
    ctx.verdict(list(dict.fromkeys(probs)), f"{len(d.get('links', []))} outbound links, none through a redirect, 410, draft or unknown address",
                "point the link at its final, live address (growth link_map check <path>) (rule 75)")


@check("links.anchor-unique", "90", what="no link words on this page also go to a different page anywhere on the site", needs="repo")
def anchor_unique(ctx):
    ctx.verdict(flags_of(ctx, ("dup-anchor",)), "every anchor on this page goes to one page only",
                "give each target its own words (growth link_map check --all lists every shared anchor) (rule 90)")


@check("links.up-across", "89", types=("money", "post"), what="a money page links down to 2+ of its posts; a post links up to its money page and across to 2+ siblings", needs="repo")
def up_across(ctx):
    d = link_map(ctx, "outbound")
    body = [l.get("final") or l.get("to") for l in d.get("links", []) if l.get("where") == "body"]
    silo = next((s for s in ctx.cfg.get("silos", {}) if ctx.need_path().startswith("/" + s)), None)
    me = ctx.key_path()
    if silo is None and me.strip("/") == "":
        # the home page sits above every silo: it links down to each silo's top page from its content (2.6.1)
        hubs = [s for s in ctx.cfg.get("silos", {}) if not any((b or "").rstrip("/") == "/" + s for b in body)]
        ctx.verdict([f"no body link down to /{h}" for h in hubs], f"home links down to all {len(ctx.cfg.get('silos', {}))} silo pages",
                    "link each silo's top page from the home page's content (rule 89)")
        return
    if silo is None:
        ctx.fail(f"{ctx.path} is in no silo of growth.json", "add the page's silo to growth.json silos or check the path (rule 89)")
        return
    # Next.js: a silo's posts live under /<silo>/blog/. Any other stack: every page of the silo below its top page.
    prefix = f"/{silo}/blog/" if ctx.stack() == "nextjs" else f"/{silo}/"
    posts = {b for b in body if b and b.startswith(prefix) and b != me}
    probs = []
    if ctx.ptype == "money" and len(posts) < 2:
        probs.append(f"links to {len(posts)} of its own posts")
    if ctx.ptype == "post":
        if f"/{silo}" not in body:
            probs.append("no body link up to its money page")
        if len(posts) < 2:
            probs.append(f"links across to {len(posts)} sibling(s)")
    ctx.verdict(probs, f"links to {len(posts)} posts of its cluster", "add contextual links up/down/across from sentences that name the target (rule 89)")


def strip_comments(src):
    """Source without // line comments, /* block */ comments, <!-- html --> comments and # comment lines (2.7.4): a
    comment that remembers an old utm-tagged link adds nothing to any link."""
    src = re.sub(r"/\*.*?\*/|<!--.*?-->", "", src, flags=re.S)
    return re.sub(r"(?m)(^|[^:\\\w])//[^\n]*|^\s*#[^\n]*", r"\1", src)


@check("links.no-utm", "34", what="no utm_ on internal links, in the HTML or the page's source", needs="repo")
def no_utm(ctx):
    root = ctx.root()
    probs = [a.get("href")[:60] for a in find_all(root, "a") if ctx.internal_path(a.get("href")) and "utm_" in a.get("href")]
    # 2.7.3: only code that WRITES a utm_ tag into an address counts (?utm_source= / &utm_medium=); reading the landing
    # URL's tags for first-touch attribution (params.get("utm_source")) adds nothing to any link
    probs += [f"{f.name}" for f, s in ctx.tree_sources().items() if re.search(r"[?&]utm_(source|medium|campaign)=", strip_comments(s))]
    ctx.verdict(probs, "no utm_ on internal links", "name the CTA with a data attribute or event, not a utm_ parameter (rule 34)")


@check("copy.shared", "131", what="one shared copy component: no other file touches the clipboard; emails, phones and shown URLs have copy buttons", needs="repo")
def copy_shared(ctx):
    probs = []
    shared = ctx.component("copy")
    nx = ctx.stack() == "nextjs"
    if not nx and not (shared and shared.is_file()):
        probs.append("no shared copy component found (set growth.json components.copy)")
    for f in ctx.repo_files():
        rel = str(f.relative_to(ctx.repo))
        if rel == "components/copy-button.tsx" or ".test." in f.name:
            continue
        if not nx and shared and (f == shared or components.flat(f.stem) == components.flat(shared.stem)):
            continue          # the component and its script helper (CopyOpen.astro + copy-open.ts) are the one place
        if re.search(r"navigator\.clipboard|execCommand\(\s*['\"]copy", f.read_text(errors="replace")):
            probs.append(f"{rel} talks to the clipboard itself")
    if nx:
        if not (ctx.repo / "components" / "copy-button.test.ts").exists():
            probs.append("no guard test components/copy-button.test.ts")
    elif shared and not any("copy" in components.flat(t.stem) for t in ctx.test_files()):
        probs.append(f"no guard test for {shared.stem} (a test file with 'copy' in its name)")
    root = ctx.root()
    for a in find_all(domx.body(root), "a"):
        h = a.get("href")
        if h.startswith(("mailto:", "tel:")):
            if re.match(r"(?i)(mailto|tel):\s*(\?|$)", h):
                continue          # "Email it" / share actions with no address or number: nothing to copy (2.7.3)
            box = a.parent
            if box is None or not any(re.search(r"(?i)copy", b.get("aria-label")) for b in find_all(box, "button")):
                probs.append(f"{h[:40]} has no copy button")
    ctx.verdict(probs, "one shared copy component, every email/phone has a copy button", f"use {'components/copy-button.tsx' if ctx.stack() == 'nextjs' else (shared.relative_to(ctx.repo).as_posix() if shared else 'one shared copy component')} (rule 131)")


@check("state.url", "79", types=("money", "hub"), what="the page's own interactive element keeps its state in the URL", needs="repo")
def state_url(ctx):
    src = "\n".join(ctx.tree_sources().values())
    if re.search(r"useSearchParams|URLSearchParams|history\.(replaceState|pushState)|router\.(replace|push)\(", src):
        ctx.ok("the page's tool reads/writes its state in the address")
    else:
        ctx.fail("no URL state in the page's components", "keep the tool's state in the query string (useSearchParams/replaceState) (rule 79)")


@check("motion.no-libs", "58", what="motion with CSS and a little script: no animation library; reduced motion respected", needs="repo")
def no_libs(ctx):
    pkg = ctx.need_file(ctx.need_repo() / "package.json", "check --repo")
    deps = json.loads(pkg.read_text())
    all_deps = {**deps.get("dependencies", {}), **deps.get("devDependencies", {})}
    probs = [f"dependency {d}" for d in MOTION_LIBS if d in all_deps]
    if "prefers-reduced-motion" not in ctx.css_text():
        probs.append("no prefers-reduced-motion rule in the CSS")
    ctx.verdict(probs, "no animation library; reduced motion handled", "build motion with CSS + IntersectionObserver; honor prefers-reduced-motion (rule 58)")


@check("css.scroll-padding", "99", what="html { scroll-padding-top } is set for the sticky header", needs="repo")
def scroll_padding(ctx):
    if re.search(r"html\s*\{[^}]*scroll-padding-top\s*:", ctx.css_text()):
        ctx.ok("scroll-padding-top is set on html")
    else:
        ctx.fail("no html { scroll-padding-top }", "set it to the sticky header height plus a gap in app/globals.css (rule 99)")


@check("repo.file-size", "124", what="no source file of the page or the branch is over 1,000 lines", needs="repo")
def file_size(ctx):
    repo = ctx.need_repo()
    code = (".ts", ".tsx", ".css", ".mjs", ".js", ".jsx", ".py", ".astro", ".svelte", ".vue")
    files = {f for f in ctx.tree_sources() if f.suffix in code} | {repo / f for f in ctx.branch_files() if (repo / f).is_file() and f.endswith(code)}
    probs = [f"{f.relative_to(repo)} {n} lines" for f in sorted(files) if (n := len(f.read_text(errors='replace').splitlines())) > 1000]
    ctx.verdict(probs, f"{len(files)} files, all under 1,000 lines", "split the file into smaller modules (rule 124)")


@check("repo.no-secrets", "119", what="no key, token or old export file in the branch", needs="repo")
def no_secrets(ctx):
    repo = ctx.need_repo()
    probs = []
    for f in ctx.branch_files():
        p = repo / f
        if re.search(r"(?i)(^|/)[\w.-]*(export|dump|backup)[\w.-]*\.(json|xml|csv|zip|sql|tar|gz)$|\.env($|\.)", f) and not f.endswith(".example"):
            probs.append(f"{f} (secrets or an old export file)")
        elif p.is_file() and p.stat().st_size < 2_000_000 and re.search(SECRET, p.read_text(errors="replace")):
            probs.append(f"{f} holds a key-shaped string")
    ctx.verdict(probs, f"{len(ctx.branch_files())} changed files, no secrets", "remove the secret, rotate the key, keep keys in ~/.config only (rule 119)")


@check("repo.commit-identity", "118", what="every commit on the branch uses the repo's commit identity (growth.json commit_identity.email; else a noreply address)", needs="repo")
def commit_identity(ctx):
    out = ctx.git("log", ctx.base_ref() + "..HEAD", "--format=%h %ae %ce")
    rows = [l.split() for l in out.splitlines() if l.strip()]
    bad = [" ".join(r) for r in rows if not ctx.identity_ok(r[1], r[2])]
    want = ctx.commit_email()
    if (ctx.cfg.get("commit_identity") or {}).get("email_sha256"):       # named by its hash: the address is never printed
        fix = "commit with the project's identity (growth.json commit_identity.email_sha256 holds the sha256 of its address) (rule 118)"
    else:
        fix = (f"commit with -c user.email={want} (rule 118)" if want else "commit with your GitHub noreply address, or set growth.json commit_identity.email (rule 118)")
    ctx.verdict(bad, f"{len(rows)} branch commit(s), all {ctx.identity_rule()}", fix + "; fix with git rebase --exec 'git commit --amend --reset-author --no-edit'")


@check("repo.commit-style", "123", what="every branch commit has a one-line subject and the co-author line", needs="repo")
def commit_style(ctx):
    since = str((ctx.cfg.get("commit_style") or {}).get("since") or "")      # commits before it are history: not rewritten (2.6.0)
    out = ctx.git("log", ctx.base_ref() + "..HEAD", *(["--since=" + since] if since else []), "--format=%h%x1f%s%x1f%b%x1e")
    probs = []
    for rec in out.split("\x1e"):
        if not rec.strip():
            continue
        h, s, b = (rec.strip().split("\x1f") + ["", ""])[:3]
        if len(s) > 120:
            probs.append(f"{h} subject {len(s)} chars")
        if "Co-Authored-By:" not in b:
            probs.append(f"{h} has no Co-Authored-By line")
    ctx.verdict(probs, "branch commits are one plain sentence with the co-author line", "commit by path with one sentence and the co-author line (rule 123)")


@check("repo.branch", "114", what="the work is on a branch with an allowed prefix (growth.json branch_prefixes; default page/, article/, fix/, design/) that is not merged into the production branch", needs="repo")
def branch(ctx):
    b = ctx.git("rev-parse", "--abbrev-ref", "HEAD").strip()
    base = ctx.base_ref()
    prod = base.split("/", 1)[-1]
    probs = []
    prefixes = ctx.branch_prefixes()
    if not any(b.startswith(p) for p in prefixes):
        probs.append(f"branch '{b}' does not start with " + ", ".join(prefixes))
    code, _ = run(["git", "-C", str(ctx.repo), "merge-base", "--is-ancestor", "HEAD", base])
    if code == 0 and b != prod:
        probs.append(f"the branch is already in {base}")
    ctx.verdict(probs, f"on branch {b}, not merged", "work on a branch with an allowed prefix (growth.json branch_prefixes); merge only on the owner's yes (rule 114)")


@check("repo.content-reader", "104", what="only the one named module reads the content files (growth.json content_reader)", needs="repo")
def content_reader(ctx):
    reader = ctx.nx("content_reader")
    if not reader:
        raise Skip("growth.json content_reader is not set: name the one module that reads the content files to switch this check on")
    folders = "|".join(re.escape(d.strip("/")) for d in (ctx.nx("posts_dir", "content/posts"), ctx.nx("pages_dir", "content/pages")))
    probs = []
    for f in ctx.repo_files(("app/**/*.ts", "app/**/*.tsx", "components/**/*.tsx", "lib/**/*.ts") if ctx.stack() == "nextjs" else None):
        rel = str(f.relative_to(ctx.repo))
        if rel == reader or ".test." in f.name:
            continue
        s = f.read_text(errors="replace")
        if re.search(r"readFileSync|readdirSync|fs/promises", s) and re.search(r"['\"`][^'\"`]*(" + folders + ")", s):
            probs.append(rel)
    ctx.verdict(probs, f"only {reader} reads the content files", f"read content through {reader} (rule 104)")


@check("repo.static-build", "100", what="the page builds statically: no force-dynamic, no revalidate 0, no cookies()/headers() in its tree", needs="repo")
def static_build(ctx):
    probs = []
    for f, s in ctx.tree_sources().items():
        if re.search(r"dynamic\s*=\s*['\"]force-dynamic|revalidate\s*=\s*0\b|\bcookies\(\)|\bheaders\(\)", s):
            probs.append(str(f.relative_to(ctx.repo)))
    ctx.verdict(probs, f"{len(ctx.tree_sources())} source files, all static-safe", "remove the dynamic call; the build stays fully static (rule 100)")


@check("repo.no-random-ids", "102", what="no random ids in the page's markup (Math.random, randomUUID)", needs="repo")
def no_random(ctx):
    probs = [str(f.relative_to(ctx.repo)) for f, s in ctx.tree_sources().items() if re.search(r"Math\.random\(|randomUUID\(", s)]
    ctx.verdict(probs, "no random ids", "use React useId() or a stable key (rule 102)")


@check("repo.scroll-test", "107", what="a regression test asserts scrollY === 0 after navigation", needs="repo")
def scroll_test(ctx):
    tests = ctx.repo_files(("tests/**/*.ts", "e2e/**/*.ts", "**/*.spec.ts")) + ctx.test_files()
    if any("scrollY" in t.read_text(errors="replace") for t in tests):
        ctx.ok("navigation scroll test present")
    else:
        ctx.warn("no Playwright test asserting window.scrollY === 0", "add it once the owner allows Playwright in the site repo (rule 107; open)")


@check("repo.guard-tests", "156", types=("money", "hub", "post"), what="a test checks the page's house features and its FAQ markup", needs="repo")
def guard_tests(ctx):
    # growth.json guard_tests.all_pages: ONE data-driven test that loops over every built page and asserts its house
    # features and FAQPage markup counts for every page (2.7.5). It must name both, and fail when one page loses one.
    allp = ((ctx.cfg.get("guard_tests") or {}).get("all_pages") or "").strip()
    if allp:
        f = ctx.need_repo() / allp
        t = f.read_text(errors="replace") if f.is_file() else ""
        miss = [] if f.is_file() else [f"{allp} not found"]
        if t and not re.search(r"(?i)house features|rule 156", t):
            miss.append(f"{allp} does not test the house features")
        if t and not re.search(r"FAQPage", t):
            miss.append(f"{allp} does not test FAQPage markup (rule 151)")
        ctx.verdict(miss, f"one data-driven house-features test covers every page: {allp}",
                    "point growth.json guard_tests.all_pages at a test that loops over every built page (rules 110, 151, 156)")
        return
    tests = sorted(set(ctx.repo_files(("lib/*.test.ts", "components/**/*.test.ts", "tests/**/*.ts")) + ctx.test_files()))
    key = ctx.need_key()
    mine = [t for t in tests if key in t.name or key in t.read_text(errors="replace")]
    hf = [t for t in mine if re.search(r"(?i)house features|rule 156", t.read_text(errors="replace"))]
    probs = [] if hf else [f"no house-features test naming {key}"]
    if not any(re.search(r"FAQPage", t.read_text(errors="replace")) for t in mine):
        probs.append("no FAQ-markup test (rule 151)")
    ctx.verdict(probs, f"house-features test: {hf[0].name if hf else ''}", "add a <page>-house-features test (lib/<page>-house-features.test.ts, or tests/<page>.test.mjs) naming the page and its FAQPage markup (rules 110, 151, 156)")


LABEL_ATTR = re.compile(r"""(aria-label|title)\s*=\s*("[^"]*"|'[^']*'|\{[^}]*\})""", re.I)
LABEL_SWAP = re.compile(r"""\.replace\(\s*(['"])(?:aria-label|title)=\1\s*,\s*(['"])(?:aria-label|title)=\2\s*\)""", re.I)


def label_free(line):
    """A diff line without the text of its aria-label / title (and a .replace() that only swaps one, and a trailing comment)."""
    line = LABEL_ATTR.sub(lambda m: m.group(1).lower() + "=", line)
    line = LABEL_SWAP.sub("", line)
    line = re.sub(r"<title>.*?</title>", "<title></title>", line, flags=re.I)
    line = re.sub(r"\s//\s.*$|<!--.*?-->|/\*.*?\*/", "", line)
    return re.sub(r"\s+", "", line)


def accessible_name_only(ctx, f):
    """True when the branch's diff of the logo file changes only an aria-label or title text (an accessibility-name fix):
    no path, shape or image changes (2.6.0). A binary file or any other changed line is never allowed."""
    code, mb = run(["git", "-C", str(ctx.need_repo()), "merge-base", ctx.base_ref(), "HEAD"], timeout=60)
    base = mb.strip() if code == 0 and mb.strip() else ctx.base_ref()
    code, out = run(["git", "-C", str(ctx.need_repo()), "diff", "-U0", base, "--", f], timeout=60)
    if code != 0 or not out.strip() or "Binary files" in out or "GIT binary patch" in out:
        return False
    old = [l[1:] for l in out.splitlines() if l.startswith("-") and not l.startswith("---")]
    new = [l[1:] for l in out.splitlines() if l.startswith("+") and not l.startswith("+++")]
    return "".join(map(label_free, old)) == "".join(map(label_free, new))


@check("repo.logo-untouched", "42", what="the branch does not change the approved logo files", needs="repo")
def logo(ctx):
    # a logo file: its name says logo, lockup or wordmark (a brand folder also holds icons such as a tick, which are not the logo)
    probs = [f for f in ctx.branch_files() if re.search(r"(?i)(logo|lockup|wordmark|brand-mark)[^/]*$", f) and not accessible_name_only(ctx, f)]
    ctx.verdict(probs, "logo files unchanged (a change of only an aria-label or title text is allowed)", "revert the logo change; the lockup is approved as is; only an aria-label or title text may change (rule 42)")


@check("repo.tokens", "41", what="changed CSS uses tokens: no raw hex colour outside a custom property", needs="repo")
def tokens(ctx):
    repo = ctx.need_repo()
    probs = []
    for f in ctx.branch_files():
        if not f.endswith(".css") or not (repo / f).is_file():
            continue
        n = 0
        for line in (repo / f).read_text(errors="replace").splitlines():
            if re.search(r"^\s*--[\w-]+\s*:", line) or line.strip().startswith(("/*", "*")):
                continue
            n += len(re.findall(r"(?<![\w-])#[0-9a-fA-F]{3,8}\b", line))
        if n:
            probs.append(f"{f}: {n} raw hex")
    ctx.verdict(probs, "changed CSS uses tokens only", "move the colour into a token (--name: #hex) and use var(--name) (rule 41)")


@check("repo.url-frozen", "73", what="the branch renames or deletes no route or content slug", needs="repo")
def url_frozen(ctx):
    out = ctx.git("diff", "--name-status", ctx.base_ref() + "...HEAD")
    dirs = "|".join(re.escape(d.strip("/")) for d in (ctx.nx("posts_dir", "content/posts"), ctx.nx("pages_dir", "content/pages")))
    probs = [l for l in out.splitlines() if re.match(r"^(D|R\d*)\s", l) and re.search(r"(app/.*/page\.tsx|(" + dirs + ")/)", l)]
    ctx.verdict(probs, "no route or slug renamed or deleted", "keep the URL; a move needs one 301 and the owner's yes (rule 73)")


@check("repo.redirects-untouched", "75", what="the branch does not touch the redirect config without a journal decision", needs="repo")
def redirects(ctx):
    watched = set(ctx.nx("redirect_files", [])) | {"middleware.ts", "next.config.ts", "next.config.js", "next.config.mjs", "vercel.json", "netlify.toml"}
    touched = [f for f in ctx.branch_files() if f in watched]
    dec = [e for e in ctx.page_entries() if e.get("kind") == "decision" and "redirect" in (e.get("tags") or [])]
    ctx.verdict(touched if touched and not dec else [], "redirect config untouched (or approved)",
                "ask first; file the owner's yes with growth journal add --kind decision --tag redirect (rule 75)")


@check("repo.retired-410", "76", what="retired page groups still answer 410 (growth.json retired_paths)", needs="repo")
def retired_410(ctx):
    paths = ctx.nx("retired_paths", [])
    if not paths:
        raise Skip("this site has no retired page groups listed (growth.json retired_paths)")
    repo = ctx.need_repo()
    code = "\n".join(f.read_text(errors="replace") for n in ("middleware.ts", "middleware.js", "next.config.ts", "next.config.js", "next.config.mjs", "vercel.json", "netlify.toml")
                     for f in [repo / n] if f.is_file())
    code += "\n".join((repo / r).read_text(errors="replace") for r in ctx.nx("redirect_files", []) if (repo / r).is_file())
    lines = code.splitlines()

    def answers_410(p):
        """The group's name and a 410 within 5 lines of each other (2.7.3): an nginx rule names groups in one pattern,
        ^/(wp-admin|wp-json)(/|$) { return 410; }, so the path with its slash is not a substring of the file."""
        name = p.strip("/")
        hits = [i for i, ln in enumerate(lines) if name and re.search(r"(?<![\w-])" + re.escape(name) + r"(?![\w-])", ln)]
        return any(re.search(r"\b(410|gone|GONE)\b", "\n".join(lines[max(0, i - 5):i + 6])) for i in hits)
    lost = [p for p in paths if not answers_410(p)]
    ctx.verdict(lost, f"{len(paths)} retired group(s) still answer 410", "restore the 410 for the retired group (rule 76)")


@check("repo.bulk-backup", "120", what="a bulk change (20+ content files or shared components) has a backup tag", needs="repo")
def bulk(ctx):
    files = ctx.branch_files()
    content = [f for f in files if f.startswith("content/")]
    shared = [f for f in files if re.match(r"components/[^/]+\.tsx$", f)]
    if len(content) < 20 and len(shared) < 5:
        ctx.ok(f"not a bulk change ({len(content)} content, {len(shared)} shared component files)")
        return
    tags = ctx.git("tag", "-l", "backup*").split()
    ctx.verdict([] if tags else [f"{len(content)} content + {len(shared)} shared component files, no backup tag"],
                f"backup tag {tags[:1]}", "git tag backup-<date> <production branch> before the rollout; try one page first (rule 120)")


@check("repo.no-migration", "122", what="the branch does not run or change one-off migration scripts", needs="repo")
def no_migration(ctx):
    probs = [f for f in ctx.branch_files() if re.search(r"(?i)scripts/.*(migrat|import)", f)]
    ctx.verdict(probs, "migration scripts untouched", "never re-run a one-off migration script over live content (rule 122)")


@check("repo.temp-clean", "112", what="no leftover temp folders (test-results, playwright-report, .tmp) in the worktree", needs="repo")
def temp_clean(ctx):
    repo = ctx.need_repo()
    probs = [p.name for p in repo.iterdir() if p.name in ("test-results", "playwright-report", ".tmp", "tmp", "coverage")]
    ctx.verdict(probs, "no temp folders left", "remove the temp folder your check made (rule 112)")


@check("repo.shared-components", "52", types=("money", "hub", "core"), what="the page uses the shared components, never its own copy", needs="repo")
def shared(ctx):
    tree = ctx.tree_sources()
    src = "\n".join(tree.values())
    probs = []
    if ctx.stack() != "nextjs":
        return shared_any_stack(ctx, tree, src)
    for comp, path in SHARED.items():
        if f"<{comp}" in src and f"@/{path}" not in src:
            probs.append(f"{comp} not imported from {path}")
    for f, s in tree.items():
        rel = str(f.relative_to(ctx.repo))
        if rel.startswith("components/") and "/" in rel[len("components/"):] and re.search(r"position:\s*sticky|class(Name)?=\"sticky-cta", s):
            probs.append(f"{rel} builds its own sticky bar")
    if ctx.ptype == "money" and "<StickyCta" not in src:
        probs.append("no shared StickyCta in the page tree")
    ctx.verdict(probs, "shared components used", "use the shared component from components/ (rule 52)")


def shared_any_stack(ctx, tree, src):
    """repo.shared-components on a stack with no "@/components/..." imports (Astro, Vite, SvelteKit): the shared component
    is the file growth.json components.<name> names, else the one found by name under src/. The page's source tree (its
    route file and every file it imports, layouts included) must hold that file, and no other file may build the same part."""
    probs = []
    held = {}
    for comp, name in SHARED_KEY.items():
        f = ctx.component(name)
        held[name] = f
        if not f or not f.is_file():
            if name != "copy" and f"<{comp}" in src:
                probs.append(f"{comp} is used but no shared component file is found (set growth.json components.{name})")
        elif f"<{f.stem}" in src and not components.in_tree(ctx, f):
            probs.append(f"{f.stem} is used but not imported from {f.relative_to(ctx.repo)}")
    for f, text in tree.items():
        if f == held.get("sticky_cta") or f.suffix not in (".astro", ".tsx", ".jsx", ".vue", ".svelte"):
            continue
        if re.search(r"""class(?:Name)?=["'][^"']*\bsticky-cta\b""", text):
            probs.append(f"{f.relative_to(ctx.repo)} builds its own sticky bar")
    if ctx.ptype == "money":
        sticky = held.get("sticky_cta")
        if not sticky or not sticky.is_file():
            probs.append("no shared sticky bar component found (set growth.json components.sticky_cta)")
        elif not components.in_tree(ctx, sticky):
            probs.append(f"no shared {sticky.stem} in the page tree")
    ctx.verdict(probs, "shared components used", "use the shared component from components/ (rule 52)")


@check("js.no-autoscroll", "67", what="nothing scrolls the page on load (no scrollTo/scrollIntoView in a mount effect)", needs="repo")
def autoscroll(ctx):
    probs = []
    for f, s in ctx.tree_sources().items():
        for m in re.finditer(r"useEffect\(\s*\(\)\s*=>\s*\{(.{0,400}?)\},\s*\[\s*\]\s*\)", s, re.S):
            if re.search(r"scrollTo\(|scrollIntoView\(", m.group(1)):
                probs.append(str(f.relative_to(ctx.repo)))
        if ctx.stack() != "nextjs":      # a page script (Astro, Svelte, plain JS): a load handler that scrolls
            for m in re.finditer(r"addEventListener\(\s*['\"](?:DOMContentLoaded|load|astro:page-load)['\"]\s*,(.{0,400}?)\}\s*\)", s, re.S):
                if re.search(r"scrollTo\(|scrollIntoView\(|scrollTop\s*=", m.group(1)):
                    probs.append(str(f.relative_to(ctx.repo)))
    ctx.verdict(probs, "no scroll on mount", "scroll only on a reader's action (rule 67)")


@check("owner.waits-148", "148", what="no Markdown copies or llms.txt until the owner says yes", needs="repo")
def waits_148(ctx):
    added = [f for f in ctx.branch_files() if re.search(r"(^public/llms\.txt$|^app/llms\.txt|\.md/route\.ts$)", f)]
    ctx.verdict(added, "nothing built for rule 148 (waits for the owner)", "remove it until the owner answers open question 1 (rule 148)")


@check("site.no-cms", "OR-site-stays", types=ALL, what="the site keeps its Markdown content in files: no CMS package added", needs="repo")
def no_cms(ctx):
    pkg = json.loads(ctx.need_file(ctx.need_repo() / "package.json", "check --repo").read_text())
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    bad = [d for d in CMS_LIBS if d in deps]
    ctx.verdict(bad, "no CMS package", "remove the CMS package; content stays Markdown in the repo (a project rule: the site stays as it is)")




def unused_runner(ctx, repo):
    """(command, label, source suffixes) of the site's own unused-name checker. Next.js: tsc. Any other stack: `astro check`
    when @astrojs/check is installed, else tsc with a tsconfig.json; with neither, a blocked Skip naming what is missing."""
    tsc, astro = repo / "node_modules" / ".bin" / "tsc", repo / "node_modules" / ".bin" / "astro"
    flags = ["--noEmit", "-p", ".", "--noUnusedLocals", "--noUnusedParameters"]
    if ctx.stack() == "nextjs":
        if not tsc.exists():
            raise Missing("node_modules/.bin/tsc in the site repo", "link or install the site's node_modules")
        return [str(tsc), *flags], "tsc", (".ts", ".tsx")
    if astro.exists() and (repo / "node_modules" / "@astrojs" / "check").exists() and any(repo.glob("astro.config.*")):
        return [str(astro), "check", "--minimumSeverity", "hint"], "astro check", (".astro", ".ts", ".tsx")
    if tsc.exists() and (repo / "tsconfig.json").exists():
        return [str(tsc), *flags], "tsc", (".ts", ".tsx", ".js", ".jsx")
    raise Skip("no type checker for this stack in the site repo: needs node_modules/.bin/astro with @astrojs/check (and typescript), "
               "or node_modules/.bin/tsc with a tsconfig.json; this check cannot run until the site has one", blocked=True)


@check("repo.no-unused-code", "124a", what="no unused import, variable or parameter in the files the branch changed (the site's own type checker: tsc --noUnusedLocals, or astro check)", needs="repo")
def no_unused_code(ctx):
    """Rule: clear dead and unused code. A sweep once found an import the
    branch left unused and a fix whose helper was imported but never called (the edit had not been saved): both are
    unused names, so the type checker's unused check catches them."""
    repo = ctx.need_repo()
    cmd, label, suffixes = unused_runner(ctx, repo)
    mine = {p for p in ctx.branch_files() if p.endswith(suffixes)}
    if not mine:
        ctx.ok(f"the branch changed no source file the checker reads ({label})")
        return

    def unused(cwd):
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=600)
        if "TS5057" in r.stdout or "TS18003" in r.stdout:
            raise Skip(f"{label} found no tsconfig.json or no source file in the site repo; this check cannot run until it has one", blocked=True)
        out = []
        for line in r.stdout.splitlines():
            m = re.match(r"(.+?)\((\d+),\d+\): error TS61(?:33|96): (.+)", line) or re.match(r"(.+?):(\d+):\d+ - \w+ ts\(61(?:33|96)\): (.+)", line)
            if m:
                f = m.group(1)
                f = pathlib.Path(f).resolve().relative_to(pathlib.Path(cwd).resolve()).as_posix() if pathlib.Path(f).is_absolute() else f
                out.append((f, m.group(2), m.group(3)))
        return out

    # only what the branch added: a name already unused on the production branch (the live site) belongs to a clean-up branch
    common = subprocess.run(["git", "-C", str(repo), "rev-parse", "--path-format=absolute", "--git-common-dir"],
                            capture_output=True, text=True).stdout.strip()
    main_dir = pathlib.Path(common).parent if common else None
    on_main = set()
    if main_dir and main_dir != repo.resolve() and subprocess.run(["git", "-C", str(main_dir), "rev-parse", "--abbrev-ref", "HEAD"],
                                                                 capture_output=True, text=True).stdout.strip() == ctx.base_ref().split("/", 1)[-1]:
        on_main = {(f, msg) for f, _, msg in unused(main_dir)}
    probs = [f"{f}:{ln} {msg}" for f, ln, msg in unused(repo) if f in mine and (f, msg) not in on_main]
    ctx.verdict(probs, f"no unused names in the {len(mine)} source files the branch changed ({label})",
                "remove the unused import or variable, or use what was meant to be used (rule 124a)")


@check("repo.no-dead-files", "124a", what="every component, lib file and stylesheet the branch adds or changes is still used; every test's subject exists", needs="repo")
def no_dead_files(ctx):
    """From a real project: "do cleanup and housekeeping of your own created dead code and test files". A rework removes
    what it replaced in the same commit: a file the branch touched that nothing imports any more is dead code."""
    repo = ctx.need_repo()
    nx = ctx.stack() == "nextjs"
    if nx:
        touched = [p for p in ctx.branch_files() if re.match(r"(components|lib)/.+\.(tsx?)$|app/.+\.css$", p)
                   and ".test." not in p and (repo / p).exists()]
        globs = ("app/**/*.tsx", "app/**/*.ts", "app/**/*.css", "components/**/*.tsx", "components/**/*.ts", "lib/**/*.ts",
                 "lib/**/*.tsx", "middleware.ts", "next.config.ts", "scripts/**/*.*")
    else:       # Astro, Vite, SvelteKit: everything lives under src/; what a file is used by is any other file under src/ or scripts/
        touched = [p for p in ctx.branch_files() if re.match(r"src/(components|lib|layouts|styles|data)/.+\.(astro|vue|svelte|tsx?|jsx?|mjs|css)$", p)
                   and ".test." not in p and (repo / p).exists()]
        globs = ("src/**/*.*", "scripts/**/*.*", "astro.config.*", "vite.config.*", "svelte.config.*", "*.config.*")
    srcs = {}
    for g in globs:
        for p in repo.glob(g):
            if p.is_file() and "node_modules" not in p.parts and ".next" not in p.parts and ".test." not in p.name \
                    and p.suffix in (".astro", ".vue", ".svelte", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".css", ".scss", ".md", ".mdx", ".json", ".html", ".sh", ".py", ""):
                srcs[p.relative_to(repo).as_posix()] = p.read_text(errors="replace")
    probs = []
    for t in touched:
        stem, name = t.rsplit(".", 1)[0], pathlib.PurePosixPath(t).stem
        pats = (stem, f"/{name}\"", f"/{name}'", f"./{name}", f"{name}.css")
        if not nx:       # "../frame/Icon.astro" and "<Icon" name a component; "./copy-open" a module; "blocks/linkcard.css" a stylesheet
            ext = t.rsplit(".", 1)[1]
            pats += (f"/{name}.{ext}", f"<{name}[\\s/>]" if ext == "astro" else f"/{name}.{ext}")
        if t.startswith("app/") and t.endswith(".css") and name in ("globals",):
            continue
        if re.match(r"app/.+/(page|layout|route|not-found|error|loading|opengraph-image|sitemap|robots)\.", t):
            continue
        if not any(o != t and any((re.search(x, src) if x.startswith("<") else x in src) for x in pats) for o, src in srcs.items()):
            probs.append(f"{t} is not used by anything")
    for p in repo.glob("lib/**/*.test.ts"):
        subj = p.with_name(p.name.replace(".test.ts", ".ts"))
        rel = p.relative_to(repo).as_posix()
        if rel in ctx.branch_files() and not subj.exists() and not subj.with_suffix(".tsx").exists():
            body = p.read_text(errors="replace")
            if not re.search(r"from ['\"]@/|from ['\"]\.|import\(['\"](@/|\.)|readFileSync|readdirSync|globSync", body):  # guard tests read files
                probs.append(f"{rel} tests nothing that exists")
    ctx.verdict(probs, f"{len(touched)} touched files all in use", "delete what the rework replaced, in the same commit (rule 124a)")
