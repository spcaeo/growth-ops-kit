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

from gatelib import domx
from gatelib.core import ALL, Missing, Skip, check, run, short

SECRET = r"(AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY|SKALD_MCP_TOKEN\s*=|ghp_[A-Za-z0-9]{30,}|xox[bp]-[A-Za-z0-9-]{20,})"
MOTION_LIBS = ("framer-motion", "motion", "gsap", "animejs", "lottie-web", "lottie-react", "react-spring", "@react-spring/web", "aos")
CMS_LIBS = ("contentful", "@payloadcms/next", "@strapi/strapi", "@sanity/client", "tinacms", "@builder.io/react", "decap-cms")
SHARED = {"StickyCta": "components/sticky-cta", "CallDialog": "components/call-dialog", "ExitOffer": "components/exit-offer",
          "LinkCards": "components/link-cards", "CopyButton": "components/copy-button"}


def link_map(ctx, cmd):
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
    return [f"{f}: {t}" for f, t in link_check(ctx).get(ctx.need_path(), []) if f in names]


@check("links.cards", "36c", what="'+' link previews: data-link-cards on the content container, the shared LinkCards, its guard test", needs="nextjs")
def link_cards(ctx):
    root = ctx.root()
    probs = []
    m = domx.main(root)
    if not any(n.get("data-link-cards") is not None and "data-link-cards" in n.attrs for n in m.iter()):
        probs.append("no data-link-cards on the page's content container")
    if "<LinkCards" not in "\n".join(ctx.tree_sources().values()):
        probs.append("the page does not render the shared <LinkCards>")
    tests = [p for p in ctx.repo_files(("lib/*.test.ts", "components/*.test.ts")) if "link-card" in p.name]
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
    if marker and ctx.url:
        import urllib.parse
        import urllib.request
        sheets = re.findall(r'<link[^>]+rel="stylesheet"[^>]+href="([^"]+)"|<link[^>]+href="([^"]+\.css[^"]*)"[^>]+rel="stylesheet"',
                            ctx.need_html())
        served = ""
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
                         "app/link-cards.css is not loaded")
    ctx.verdict(probs, "link previews switched on, styled and guarded", "add data-link-cards to the content container and render <LinkCards>; "
                "load app/link-cards.css (best: the component imports it); "
                "skip only site chrome in SKIP_ZONE (a header or footer inside <main> is content) (rule 36c)")


@check("links.inbound", "88", what="at least two other pages link here from their content; a post links up to its hub, sits on its guide list and links to 2+ siblings", needs="nextjs")
def inbound(ctx):
    d = link_map(ctx, "inbound")
    srcs = {l["src"] for l in d.get("links", []) if l.get("where") in ("body", "hub-list") and l.get("src") != ctx.path}
    probs = flags_of(ctx, ("orphan", "weak", "no-hub", "not-on-hub", "siblings<2"))
    if len(srcs) < 2 and not probs:
        probs.append(f"only {len(srcs)} page(s) link here from their content")
    ctx.verdict(probs, f"{len(srcs)} pages link here from their content; link_map.py check: no orphan, weak or cluster flag",
                f"add content links from its cluster (growth link_map suggest {ctx.path}; check with link_map.py check {ctx.path}) (rule 88)")


@check("links.plan", "88a", types=("money", "hub"), what="the internal-link plan is filed: journal entries tagged internal-link against source pages", needs="nextjs")
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
    link_map(ctx, "suggest")
    ctx.verdict(probs, f"{len(planned)} planned links filed in the journal", f"growth link_map suggest {p}; file each with growth journal add --page <source> --tag internal-link (rule 88a)")


@check("links.no-redirect", "75", what="no internal link points at a redirect, a 410, a draft or an unknown address", needs="nextjs")
def no_redirect(ctx):
    d = link_map(ctx, "outbound")
    moved = [f"{l['to']} -> {l['final']}" for l in d.get("links", []) if l.get("moved") or (l.get("final") and l.get("final") != l.get("to"))]
    probs = sorted(set(moved)) + flags_of(ctx, ("to-redirect", "to-gone", "to-not-live", "to-unknown"))
    ctx.verdict(list(dict.fromkeys(probs)), f"{len(d.get('links', []))} outbound links, none through a redirect, 410, draft or unknown address",
                "point the link at its final, live address (growth link_map check <path>) (rule 75)")


@check("links.anchor-unique", "90", what="no link words on this page also go to a different page anywhere on the site", needs="nextjs")
def anchor_unique(ctx):
    ctx.verdict(flags_of(ctx, ("dup-anchor",)), "every anchor on this page goes to one page only",
                "give each target its own words (growth link_map check --all lists every shared anchor) (rule 90)")


@check("links.up-across", "89", types=("money", "post"), what="a money page links down to 2+ of its posts; a post links up to its money page and across to 2+ siblings", needs="nextjs")
def up_across(ctx):
    d = link_map(ctx, "outbound")
    body = [l.get("final") or l.get("to") for l in d.get("links", []) if l.get("where") == "body"]
    silo = next((s for s in ctx.cfg.get("silos", {}) if ctx.need_path().startswith("/" + s)), None)
    if silo is None:
        ctx.fail(f"{ctx.path} is in no silo of growth.json", "add the page's silo to growth.json silos or check the path (rule 89)")
        return
    posts = {b for b in body if b and b.startswith(f"/{silo}/blog/") and b != ctx.path}
    probs = []
    if ctx.ptype == "money" and len(posts) < 2:
        probs.append(f"links to {len(posts)} of its own posts")
    if ctx.ptype == "post":
        if f"/{silo}" not in body:
            probs.append("no body link up to its money page")
        if len(posts) < 2:
            probs.append(f"links across to {len(posts)} sibling(s)")
    ctx.verdict(probs, f"links to {len(posts)} posts of its cluster", "add contextual links up/down/across from sentences that name the target (rule 89)")


@check("links.no-utm", "34", what="no utm_ on internal links, in the HTML or the page's source", needs="nextjs")
def no_utm(ctx):
    root = ctx.root()
    probs = [a.get("href")[:60] for a in find_all(root, "a") if ctx.internal_path(a.get("href")) and "utm_" in a.get("href")]
    probs += [f"{f.name}" for f, s in ctx.tree_sources().items() if re.search(r"utm_(source|medium|campaign)", s)]
    ctx.verdict(probs, "no utm_ on internal links", "name the CTA with a data attribute or event, not a utm_ parameter (rule 34)")


@check("copy.shared", "131", what="one shared copy component: no other file touches the clipboard; emails, phones and shown URLs have copy buttons", needs="nextjs")
def copy_shared(ctx):
    probs = []
    for f in ctx.repo_files():
        rel = str(f.relative_to(ctx.repo))
        if rel == "components/copy-button.tsx" or ".test." in f.name:
            continue
        if re.search(r"navigator\.clipboard|execCommand\(\s*['\"]copy", f.read_text(errors="replace")):
            probs.append(f"{rel} talks to the clipboard itself")
    if not (ctx.repo / "components" / "copy-button.test.ts").exists():
        probs.append("no guard test components/copy-button.test.ts")
    root = ctx.root()
    for a in find_all(domx.body(root), "a"):
        h = a.get("href")
        if h.startswith(("mailto:", "tel:")):
            box = a.parent
            if box is None or not any(re.search(r"(?i)copy", b.get("aria-label")) for b in find_all(box, "button")):
                probs.append(f"{h[:40]} has no copy button")
    ctx.verdict(probs, "one shared copy component, every email/phone has a copy button", "use components/copy-button.tsx (rule 131)")


@check("state.url", "79", types=("money", "hub"), what="the page's own interactive element keeps its state in the URL", needs="nextjs")
def state_url(ctx):
    src = "\n".join(ctx.tree_sources().values())
    if re.search(r"useSearchParams|URLSearchParams|history\.(replaceState|pushState)|router\.(replace|push)\(", src):
        ctx.ok("the page's tool reads/writes its state in the address")
    else:
        ctx.fail("no URL state in the page's components", "keep the tool's state in the query string (useSearchParams/replaceState) (rule 79)")


@check("motion.no-libs", "58", what="motion with CSS and a little script: no animation library; reduced motion respected", needs="nextjs")
def no_libs(ctx):
    pkg = ctx.need_file(ctx.need_repo() / "package.json", "check --repo")
    deps = json.loads(pkg.read_text())
    all_deps = {**deps.get("dependencies", {}), **deps.get("devDependencies", {})}
    probs = [f"dependency {d}" for d in MOTION_LIBS if d in all_deps]
    if "prefers-reduced-motion" not in ctx.css_text():
        probs.append("no prefers-reduced-motion rule in the CSS")
    ctx.verdict(probs, "no animation library; reduced motion handled", "build motion with CSS + IntersectionObserver; honor prefers-reduced-motion (rule 58)")


@check("hero.unique", "157", types=("money", "hub"), what="the page's hero component is used by no sibling page", needs="nextjs")
def hero_unique(ctx):
    tree = ctx.tree_sources()
    heroes = [f for f in tree if re.search(r"hero", f.name, re.I)]
    if not heroes:
        ctx.fail("no hero component in the page's source tree", "give the page its own hero component (rules 147, 157)")
        return
    probs = []
    repo = ctx.repo
    for h in heroes:
        rel = str(h.relative_to(repo)).rsplit(".", 1)[0]
        users = [str(f.relative_to(repo)) for f in ctx.repo_files(("app/**/page.tsx", "components/**/*.tsx"))
                 if f not in tree and (("@/" + rel) in f.read_text(errors="replace"))]
        if users:
            probs.append(f"{rel} also used by {users[:3]}")
    ctx.verdict(probs, f"hero {', '.join(h.name for h in heroes)} is this page's own", "build a hero for this page; never share a sibling's (rule 157)")


@check("css.scroll-padding", "99", what="html { scroll-padding-top } is set for the sticky header", needs="nextjs")
def scroll_padding(ctx):
    if re.search(r"html\s*\{[^}]*scroll-padding-top\s*:", ctx.css_text()):
        ctx.ok("scroll-padding-top is set on html")
    else:
        ctx.fail("no html { scroll-padding-top }", "set it to the sticky header height plus a gap in app/globals.css (rule 99)")


@check("repo.file-size", "124", what="no source file of the page or the branch is over 1,000 lines", needs="nextjs")
def file_size(ctx):
    repo = ctx.need_repo()
    files = set(ctx.tree_sources()) | {repo / f for f in ctx.branch_files() if (repo / f).is_file() and f.endswith((".ts", ".tsx", ".css", ".mjs", ".py"))}
    probs = [f"{f.relative_to(repo)} {n} lines" for f in sorted(files) if (n := len(f.read_text(errors='replace').splitlines())) > 1000]
    ctx.verdict(probs, f"{len(files)} files, all under 1,000 lines", "split the file into smaller modules (rule 124)")


@check("repo.no-secrets", "119", what="no key, token or old export file in the branch", needs="nextjs")
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


@check("repo.commit-identity", "118", what="every commit on the branch uses the repo's noreply identity", needs="nextjs")
def commit_identity(ctx):
    want = ctx.commit_email()
    out = ctx.git("log", ctx.base_ref() + "..HEAD", "--format=%h %ae %ce")
    bad = [l for l in out.splitlines() if l.strip() and (l.split()[1] != want or l.split()[2] != want)]
    n = len([l for l in out.splitlines() if l.strip()])
    ctx.verdict(bad, f"{n} branch commit(s), all by {want}", f"commit with -c user.email={want} (rule 118); fix with git rebase --exec 'git commit --amend --reset-author --no-edit'")


@check("repo.commit-style", "123", what="every branch commit has a one-line subject and the co-author line", needs="nextjs")
def commit_style(ctx):
    out = ctx.git("log", ctx.base_ref() + "..HEAD", "--format=%h%x1f%s%x1f%b%x1e")
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


@check("repo.branch", "114", what="the work is on a page/article/fix/design branch that is not merged into the production branch", needs="nextjs")
def branch(ctx):
    b = ctx.git("rev-parse", "--abbrev-ref", "HEAD").strip()
    base = ctx.base_ref()
    prod = base.split("/", 1)[-1]
    probs = []
    if not re.match(r"(article|page|fix|design)/", b):
        probs.append(f"branch '{b}' is not article/, page/, fix/ or design/")
    code, _ = run(["git", "-C", str(ctx.repo), "merge-base", "--is-ancestor", "HEAD", base])
    if code == 0 and b != prod:
        probs.append(f"the branch is already in {base}")
    ctx.verdict(probs, f"on branch {b}, not merged", "work on a page/... branch; merge only on the owner's yes (rule 114)")


@check("repo.content-reader", "104", what="only the one named module reads the content files (growth.json content_reader)", needs="nextjs")
def content_reader(ctx):
    reader = ctx.nx("content_reader")
    if not reader:
        raise Skip("growth.json content_reader is not set: name the one module that reads the content files to switch this check on")
    folders = "|".join(re.escape(d.strip("/")) for d in (ctx.nx("posts_dir", "content/posts"), ctx.nx("pages_dir", "content/pages")))
    probs = []
    for f in ctx.repo_files(("app/**/*.ts", "app/**/*.tsx", "components/**/*.tsx", "lib/**/*.ts")):
        rel = str(f.relative_to(ctx.repo))
        if rel == reader or ".test." in f.name:
            continue
        s = f.read_text(errors="replace")
        if re.search(r"readFileSync|readdirSync|fs/promises", s) and re.search(r"['\"`][^'\"`]*(" + folders + ")", s):
            probs.append(rel)
    ctx.verdict(probs, f"only {reader} reads the content files", f"read content through {reader} (rule 104)")


@check("repo.static-build", "100", what="the page builds statically: no force-dynamic, no revalidate 0, no cookies()/headers() in its tree", needs="nextjs")
def static_build(ctx):
    probs = []
    for f, s in ctx.tree_sources().items():
        if re.search(r"dynamic\s*=\s*['\"]force-dynamic|revalidate\s*=\s*0\b|\bcookies\(\)|\bheaders\(\)", s):
            probs.append(str(f.relative_to(ctx.repo)))
    ctx.verdict(probs, f"{len(ctx.tree_sources())} source files, all static-safe", "remove the dynamic call; the build stays fully static (rule 100)")


@check("repo.no-random-ids", "102", what="no random ids in the page's markup (Math.random, randomUUID)", needs="nextjs")
def no_random(ctx):
    probs = [str(f.relative_to(ctx.repo)) for f, s in ctx.tree_sources().items() if re.search(r"Math\.random\(|randomUUID\(", s)]
    ctx.verdict(probs, "no random ids", "use React useId() or a stable key (rule 102)")


@check("repo.scroll-test", "107", what="a regression test asserts scrollY === 0 after navigation", needs="nextjs")
def scroll_test(ctx):
    tests = ctx.repo_files(("tests/**/*.ts", "e2e/**/*.ts", "**/*.spec.ts"))
    if any("scrollY" in t.read_text(errors="replace") for t in tests):
        ctx.ok("navigation scroll test present")
    else:
        ctx.warn("no Playwright test asserting window.scrollY === 0", "add it once the owner allows Playwright in the site repo (rule 107; open)")


@check("repo.guard-tests", "156", types=("money", "hub", "post"), what="a test checks the page's house features and its FAQ markup", needs="nextjs")
def guard_tests(ctx):
    tests = ctx.repo_files(("lib/*.test.ts", "components/**/*.test.ts", "tests/**/*.ts"))
    key = ctx.need_key()
    mine = [t for t in tests if key in t.name or key in t.read_text(errors="replace")]
    hf = [t for t in mine if re.search(r"(?i)house features|rule 156", t.read_text(errors="replace"))]
    probs = [] if hf else [f"no house-features test naming {key}"]
    if not any(re.search(r"FAQPage", t.read_text(errors="replace")) for t in mine):
        probs.append("no FAQ-markup test (rule 151)")
    ctx.verdict(probs, f"house-features test: {hf[0].name if hf else ''}", "add lib/<page>-house-features.test.ts (rules 110, 151, 156)")


@check("repo.logo-untouched", "42", what="the branch does not change the approved logo files", needs="nextjs")
def logo(ctx):
    probs = [f for f in ctx.branch_files() if re.search(r"(?i)(^public/brand/|logo)", f)]
    ctx.verdict(probs, "logo files unchanged", "revert the logo change; the lockup is approved as is (rule 42)")


@check("repo.tokens", "41", what="changed CSS uses tokens: no raw hex colour outside a custom property", needs="nextjs")
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


@check("repo.url-frozen", "73", what="the branch renames or deletes no route or content slug", needs="nextjs")
def url_frozen(ctx):
    out = ctx.git("diff", "--name-status", ctx.base_ref() + "...HEAD")
    dirs = "|".join(re.escape(d.strip("/")) for d in (ctx.nx("posts_dir", "content/posts"), ctx.nx("pages_dir", "content/pages")))
    probs = [l for l in out.splitlines() if re.match(r"^(D|R\d*)\s", l) and re.search(r"(app/.*/page\.tsx|(" + dirs + ")/)", l)]
    ctx.verdict(probs, "no route or slug renamed or deleted", "keep the URL; a move needs one 301 and the owner's yes (rule 73)")


@check("repo.redirects-untouched", "75", what="the branch does not touch the redirect config without a journal decision", needs="nextjs")
def redirects(ctx):
    watched = set(ctx.nx("redirect_files", [])) | {"middleware.ts", "next.config.ts", "next.config.js", "next.config.mjs", "vercel.json", "netlify.toml"}
    touched = [f for f in ctx.branch_files() if f in watched]
    dec = [e for e in ctx.page_entries() if e.get("kind") == "decision" and "redirect" in (e.get("tags") or [])]
    ctx.verdict(touched if touched and not dec else [], "redirect config untouched (or approved)",
                "ask first; file the owner's yes with growth journal add --kind decision --tag redirect (rule 75)")


@check("repo.retired-410", "76", what="retired page groups still answer 410 (growth.json retired_paths)", needs="nextjs")
def retired_410(ctx):
    paths = ctx.nx("retired_paths", [])
    if not paths:
        raise Skip("this site has no retired page groups listed (growth.json retired_paths)")
    repo = ctx.need_repo()
    code = "\n".join(f.read_text(errors="replace") for n in ("middleware.ts", "middleware.js", "next.config.ts", "next.config.js", "next.config.mjs", "vercel.json", "netlify.toml")
                     for f in [repo / n] if f.is_file())
    code += "\n".join((repo / r).read_text(errors="replace") for r in ctx.nx("redirect_files", []) if (repo / r).is_file())
    lost = [p for p in paths if p.rstrip("/") not in code or not re.search(r"\b(410|gone|GONE)\b", code)]
    ctx.verdict(lost, f"{len(paths)} retired group(s) still answer 410", "restore the 410 for the retired group (rule 76)")


@check("repo.bulk-backup", "120", what="a bulk change (20+ content files or shared components) has a backup tag", needs="nextjs")
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


@check("repo.no-migration", "122", what="the branch does not run or change one-off migration scripts", needs="nextjs")
def no_migration(ctx):
    probs = [f for f in ctx.branch_files() if re.search(r"(?i)scripts/.*(migrat|import)", f)]
    ctx.verdict(probs, "migration scripts untouched", "never re-run a one-off migration script over live content (rule 122)")


@check("repo.temp-clean", "112", what="no leftover temp folders (test-results, playwright-report, .tmp) in the worktree", needs="nextjs")
def temp_clean(ctx):
    repo = ctx.need_repo()
    probs = [p.name for p in repo.iterdir() if p.name in ("test-results", "playwright-report", ".tmp", "tmp", "coverage")]
    ctx.verdict(probs, "no temp folders left", "remove the temp folder your check made (rule 112)")


@check("repo.shared-components", "52", types=("money", "hub", "core"), what="the page uses the shared components, never its own copy", needs="nextjs")
def shared(ctx):
    tree = ctx.tree_sources()
    src = "\n".join(tree.values())
    probs = []
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


@check("js.no-autoscroll", "67", what="nothing scrolls the page on load (no scrollTo/scrollIntoView in a mount effect)", needs="nextjs")
def autoscroll(ctx):
    probs = []
    for f, s in ctx.tree_sources().items():
        for m in re.finditer(r"useEffect\(\s*\(\)\s*=>\s*\{(.{0,400}?)\},\s*\[\s*\]\s*\)", s, re.S):
            if re.search(r"scrollTo\(|scrollIntoView\(", m.group(1)):
                probs.append(str(f.relative_to(ctx.repo)))
    ctx.verdict(probs, "no scroll on mount", "scroll only on a reader's action (rule 67)")


@check("owner.waits-148", "148", what="no Markdown copies or llms.txt until the owner says yes", needs="nextjs")
def waits_148(ctx):
    added = [f for f in ctx.branch_files() if re.search(r"(^public/llms\.txt$|^app/llms\.txt|\.md/route\.ts$)", f)]
    ctx.verdict(added, "nothing built for rule 148 (waits for the owner)", "remove it until the owner answers open question 1 (rule 148)")


@check("site.no-cms", "OR-site-stays", types=ALL, what="the site keeps its Markdown content in files: no CMS package added", needs="nextjs")
def no_cms(ctx):
    pkg = json.loads(ctx.need_file(ctx.need_repo() / "package.json", "check --repo").read_text())
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    bad = [d for d in CMS_LIBS if d in deps]
    ctx.verdict(bad, "no CMS package", "remove the CMS package; content stays Markdown in the repo (a project rule: the site stays as it is)")




@check("repo.no-unused-code", "124a", what="no unused import, variable or parameter in the files the branch changed (tsc --noUnusedLocals)", needs="nextjs")
def no_unused_code(ctx):
    """Rule: clear dead and unused code. A sweep once found an import the
    branch left unused and a fix whose helper was imported but never called (the edit had not been saved): both are
    unused names, so the type checker's unused check catches them."""
    repo = ctx.need_repo()
    tsc = repo / "node_modules" / ".bin" / "tsc"
    if not tsc.exists():
        raise Missing("node_modules/.bin/tsc in the site repo", "link or install the site's node_modules")
    mine = {p for p in ctx.branch_files() if re.search(r"\.(tsx?)$", p)}

    def unused(cwd):
        r = subprocess.run([str(tsc), "--noEmit", "-p", ".", "--noUnusedLocals", "--noUnusedParameters"], cwd=cwd,
                           capture_output=True, text=True, timeout=600)
        return [m.groups() for m in (re.match(r"(.+?)\((\d+),\d+\): error TS61(?:33|96): (.+)", l) for l in r.stdout.splitlines()) if m]

    # only what the branch added: a name already unused on the production branch (the live site) belongs to a clean-up branch
    common = subprocess.run(["git", "-C", str(repo), "rev-parse", "--path-format=absolute", "--git-common-dir"],
                            capture_output=True, text=True).stdout.strip()
    main_dir = pathlib.Path(common).parent if common else None
    on_main = set()
    if main_dir and main_dir != repo.resolve() and subprocess.run(["git", "-C", str(main_dir), "rev-parse", "--abbrev-ref", "HEAD"],
                                                                 capture_output=True, text=True).stdout.strip() == ctx.base_ref().split("/", 1)[-1]:
        on_main = {(f, msg) for f, _, msg in unused(main_dir)}
    probs = [f"{f}:{ln} {msg}" for f, ln, msg in unused(repo) if f in mine and (f, msg) not in on_main]
    ctx.verdict(probs, f"no unused names in the {len(mine)} TypeScript files the branch changed",
                "remove the unused import or variable, or use what was meant to be used (rule 124a)")


@check("repo.no-dead-files", "124a", what="every component, lib file and stylesheet the branch adds or changes is still used; every test's subject exists", needs="nextjs")
def no_dead_files(ctx):
    """From a real project: "do cleanup and housekeeping of your own created dead code and test files". A rework removes
    what it replaced in the same commit: a file the branch touched that nothing imports any more is dead code."""
    repo = ctx.need_repo()
    touched = [p for p in ctx.branch_files() if re.match(r"(components|lib)/.+\.(tsx?)$|app/.+\.css$", p)
               and ".test." not in p and (repo / p).exists()]
    srcs = {}
    for g in ("app/**/*.tsx", "app/**/*.ts", "app/**/*.css", "components/**/*.tsx", "components/**/*.ts", "lib/**/*.ts",
              "lib/**/*.tsx", "middleware.ts", "next.config.ts", "scripts/**/*.*"):
        for p in repo.glob(g):
            if "node_modules" not in p.parts and ".next" not in p.parts and ".test." not in p.name:
                srcs[p.relative_to(repo).as_posix()] = p.read_text(errors="replace")
    probs = []
    for t in touched:
        stem, name = t.rsplit(".", 1)[0], pathlib.PurePosixPath(t).stem
        pats = (stem, f"/{name}\"", f"/{name}'", f"./{name}", f"{name}.css")
        if t.startswith("app/") and t.endswith(".css") and name in ("globals",):
            continue
        if re.match(r"app/.+/(page|layout|route|not-found|error|loading|opengraph-image|sitemap|robots)\.", t):
            continue
        if not any(o != t and any(x in src for x in pats) for o, src in srcs.items()):
            probs.append(f"{t} is not used by anything")
    for p in repo.glob("lib/**/*.test.ts"):
        subj = p.with_name(p.name.replace(".test.ts", ".ts"))
        rel = p.relative_to(repo).as_posix()
        if rel in ctx.branch_files() and not subj.exists() and not subj.with_suffix(".tsx").exists():
            body = p.read_text(errors="replace")
            if not re.search(r"from ['\"]@/|from ['\"]\.|import\(['\"](@/|\.)|readFileSync|readdirSync|globSync", body):  # guard tests read files
                probs.append(f"{rel} tests nothing that exists")
    ctx.verdict(probs, f"{len(touched)} touched files all in use", "delete what the rework replaced, in the same commit (rule 124a)")
