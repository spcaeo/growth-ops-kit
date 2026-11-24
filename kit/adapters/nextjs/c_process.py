"""Next.js adapter: the checks of gatelib/c_process.py that read the site's code (CSS, components, sources).
They run only when growth.json "stack" is "nextjs"; on any other stack the gate prints SKIP for each."""
from __future__ import annotations

from gatelib.c_process import *  # noqa: F401,F403
from gatelib.core import Skip, check, run  # noqa: F401


@check("proc.commit-identity", "118", P, "every unmerged commit in every site worktree uses the commit identity (growth.json commit_identity.email; else a noreply address)", needs="repo")
def commit_identity(ctx):
    probs = []
    for w in worktrees(ctx):
        out = ctx.git("-C", w["worktree"], "log", ctx.base_ref(site_repo(ctx)) + "..HEAD", "--format=%h %ae %ce", repo=site_repo(ctx))
        for line in out.splitlines():
            h, a, c = line.split()
            if not ctx.identity_ok(a, c):
                probs.append(f"{w['worktree'].rsplit('/', 1)[-1]} {h} {a}")
    ctx.verdict(probs, f"all unmerged commits in {len(worktrees(ctx))} worktrees are {ctx.identity_rule()}",
                "commit with the identity in growth.json commit_identity.email, or a GitHub noreply address when none is set (rule 118)")


def project_start(ctx, repo):
    """The date the project began: the I-1 row of the steps log, else growth.json nextjs.start_date, else the date of the
    project folder's first commit, else the site repo's first commit. Raises Skip when none can be found."""
    import records
    fix = "growth tasks / docs/steps-log.md (the project's start date is read from them)"
    log = ctx.need_file(ctx.need_docs() / "steps-log.md", fix).read_text()
    docs = ctx.need_docs()
    ctx.need_file(records.tasks_path(docs.parent, docs), fix)
    log += records.tasks_text(docs.parent)
    m = re.search(r"\| I-1 \| (\d{4}-\d\d-\d\d)", log)
    if m:
        return m.group(1), log
    if ctx.nx("start_date"):
        return str(ctx.nx("start_date")), log
    for r in (ctx.project, repo):
        code, out = run(["git", "-C", str(r), "log", "--reverse", "--format=%as"], timeout=30)
        if code == 0 and out.strip():
            return out.split()[0], log
    raise Skip("no start date: set growth.json nextjs.start_date (the project's first commit could not be read)")


@check("proc.no-push-main", "114", P, "every commit on the production branch since the project began is logged with the owner's yes; local branch not ahead", needs="repo")
def no_push(ctx):
    repo = site_repo(ctx)
    base = ctx.base_ref(repo)
    since, log = project_start(ctx, repo)
    out = ctx.git("log", base, f"--since={since}", "--format=%h %s", repo=repo)
    probs = [l for l in out.splitlines() if l.split()[0][:7] not in log]
    if "/" in base:                                   # a remote branch: the local one must not be ahead of it
        local = base.split("/", 1)[1]
        if run(["git", "-C", str(repo), "rev-parse", "--verify", "-q", local])[0] == 0:
            ahead = ctx.git("rev-list", "--count", f"{base}..{local}", repo=repo).strip()
            if ahead != "0":
                probs.append(f"local {local} is {ahead} commit(s) ahead of {base}")
    ctx.verdict(probs, "every production-branch commit since the start is logged with the owner's yes", "never push to the production branch without the owner's yes; log the yes and the commit (rule 114)")


@check("proc.checks-script", "105", P, "adapters/nextjs/checks.sh exists and maps changes to the only checks they touch", needs="nextjs")
def checks_script(ctx):
    f = ctx.need_file(ctx.kit_dir / "adapters" / "nextjs" / "checks.sh", "restore adapters/nextjs/checks.sh")
    s = f.read_text()
    ctx.verdict([] if "vitest related" in s and "npm run build" in s else ["checks.sh lost its change -> check map"],
                "checks.sh present with its change map", "restore adapters/nextjs/checks.sh (rule 105)")


@check("proc.worktrees", "126", P, "at most 4 site worktrees open (one per live agent)", needs="repo")
def wt_count(ctx):
    n = len(worktrees(ctx)) - 1
    ctx.verdict([] if n <= ctx.cfg.get("agent_cap", 4) else [f"{n} worktrees open"], f"{n} worktree(s) open",
                "remove finished worktrees (git worktree remove), keep the branch (rule 126)")


@check("proc.one-page-branch", "OR-one-page", P, "each page/ branch changes one page route only", needs="repo")
def one_page(ctx):
    probs = []
    for w in worktrees(ctx):
        b = w.get("branch", "").replace("refs/heads/", "")
        if not b.startswith("page/"):
            continue
        out = ctx.git("-C", w["worktree"], "diff", "--numstat", ctx.base_ref(site_repo(ctx)) + "...HEAD", repo=site_repo(ctx))
        own = f"app/{b[len('page/'):]}/page.tsx"
        others = []
        for line in out.splitlines():
            add, dele, f = (line.split("\t") + ["", "", ""])[:3]
            if f != own and (re.match(r"app/.+/page\.tsx$", f) or f == "app/page.tsx"):
                n = (int(add) if add.isdigit() else 99) + (int(dele) if dele.isdigit() else 99)
                if n > 10:                             # up to 10 lines = the release's inbound links (rule 88a)
                    others.append(f"{f} ({n} lines)")
        if others:
            probs.append(f"{b} also rebuilds {', '.join(others)}")
    ctx.verdict(probs, "every page branch holds one page", "split the branch: one page per release (book/02-owner-rules.md 'Release one page at a time')")
