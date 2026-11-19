"""The rule gate's core: the check registry, the page context and the result lines.

Every check is a plain function registered with @check. It gets a Ctx and calls ctx.ok(...) or ctx.fail(...).
A check that cannot read its input (no page HTML, no site checkout, no journal) must not pass: the context's
need_* helpers raise Missing, and run_check turns that into a FAIL that names the missing input and the fix.
"""
from __future__ import annotations

import datetime as dt
import inspect
import json
import os
import re
import subprocess
import sys
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import KIT_DIR  # noqa: E402

PAGE_TYPES = ("money", "hub", "post", "core")
ALL = PAGE_TYPES                    # a check for every page type ("site" scope)
CHECKS: dict = {}                   # check id -> Check


class Missing(Exception):
    """An input a check needs is not there. Missing input is a FAIL, never an OK."""

    def __init__(self, what, fix):
        super().__init__(what)
        self.what, self.fix = what, fix


class Skip(Exception):
    """The check does not apply to this project (an adapter for another stack, a house feature that is switched off).
    It is printed as 'SKIP <id>: <why>' and counted apart from OK: never a fake OK."""

    def __init__(self, why):
        super().__init__(why)
        self.why = why


class NeedsPage(Missing):
    """The check reads the rendered page. In static mode (no --url: the site pre-commit hook) it is skipped, not failed."""


@dataclass
class Check:
    cid: str
    rule: str                       # the rulebook rule the line is printed under
    types: tuple                    # page types it runs for; ("process",) for process checks
    what: str
    fn: object
    file: str
    stage: str = "build"            # build: before release; release: after the merge (gate.py page --stage release)
    needs: str = "live"             # what it reads: live (the served page), project (the project folder), nextjs (the site's code)
    where: str = ""                 # the file that defines it, relative to the kit folder (e.g. tools/gatelib/c_seo.py)


def check(cid, rule, types=ALL, what="", stage="build", needs="live"):
    def deco(fn):
        if cid in CHECKS:
            raise ValueError(f"duplicate check id {cid}")
        src = Path(inspect.getsourcefile(fn)).resolve()
        f = src.name
        CHECKS[cid] = Check(cid, rule, tuple(types), what or (fn.__doc__ or "").strip().splitlines()[0], fn, f, stage, needs,
                            src.relative_to(KIT_DIR).as_posix())
        return fn
    return deco


@dataclass
class Line:
    level: str                      # FAIL / WARN / OK
    rule: str
    cid: str
    what: str
    fix: str = ""

    def text(self):
        if self.level == "SKIP":
            return f"SKIP {self.cid}: {self.what}"
        s = f"{self.level:<4} {self.rule:<5} [{self.cid}] {self.what}"
        return s + (f" -> {self.fix}" if self.fix and self.level != "OK" else "")


def run(cmd, cwd=None, timeout=300):
    """Run a command; return (exit code, stdout+stderr). Never raises."""
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as e:  # noqa: BLE001
        return 99, f"{type(e).__name__}: {e}"


@dataclass
class Ctx:
    """Everything a check may read. Built once per gate run; every input is optional so the
    missing-input path can be tested, and every need_* helper raises Missing when it is absent."""
    project: Path                               # the project folder (growth.json, journal/, research/, ...)
    path: str = ""                              # site path, e.g. /lawn-mowing
    url: str = ""                               # local URL of the page
    repo: Path | None = None                    # site checkout or worktree
    kit_dir: Path = field(default_factory=lambda: KIT_DIR)   # the kit's own files (tools, rules, adapters)
    ptype: str = "money"
    docs: Path | None = None                    # project docs folder (steps log, tasks.json)
    cfg: dict = field(default_factory=dict)     # growth.json
    key: str = ""                               # research file key, e.g. lawn-mowing
    today: dt.date = field(default_factory=dt.date.today)
    html: str | None = None                     # set by load_page(); None = not fetched
    status: int = 0
    lines: list = field(default_factory=list)
    cache: dict = field(default_factory=dict)
    static: bool = False                        # no page to read: only source checks run (pre-commit hook)
    skipped: list = field(default_factory=list)  # checks skipped in static mode (they need the page)
    _cur: Check | None = None

    # ---- result helpers ------------------------------------------------------------------
    def skip(self, why):
        self.lines.append(Line("SKIP", self._cur.rule, self._cur.cid, why))

    def stack(self):
        return (self.cfg.get("stack") or "static").lower()

    def feature(self, name):
        """The settings of a house feature switched on in growth.json "features" ({} when it is on without settings).
        Raises Skip when it is off: a rule about a part this site does not have is not applicable, not passed."""
        f = (self.cfg.get("features") or {}).get(name)
        if not f:
            raise Skip(f"feature '{name}' is off in growth.json (features.{name})")
        return f if isinstance(f, dict) else {}

    def ok(self, what):
        self.lines.append(Line("OK", self._cur.rule, self._cur.cid, what))

    def fail(self, what, fix):
        self.lines.append(Line("FAIL", self._cur.rule, self._cur.cid, what, fix))

    def warn(self, what, fix):
        self.lines.append(Line("WARN", self._cur.rule, self._cur.cid, what, fix))

    def verdict(self, problems, ok_what, fix):
        """One FAIL line listing up to 6 problems, or one OK line."""
        if problems:
            shown = "; ".join(str(p) for p in problems[:6]) + (f"; +{len(problems) - 6} more" if len(problems) > 6 else "")
            self.fail(f"{len(problems)} problem(s): {shown}", fix)
        else:
            self.ok(ok_what)

    # ---- inputs (each raises Missing when absent) ------------------------------------------
    def need_html(self):
        if not self.html:
            raise NeedsPage("page HTML (the page did not load)",
                          f"start the dev server and pass --url (got {self.url or 'no URL'}, status {self.status})")
        return self.html

    def root(self):
        if "root" not in self.cache:
            from techseo.dom import parse
            self.cache["root"] = parse(self.need_html())
        return self.cache["root"]

    def need_repo(self):
        if not self.repo or not (self.repo / ".git").exists():
            raise Missing("site checkout (--repo)", "pass --repo <site folder> or set site_repo in growth.json")
        return self.repo

    def need_path(self):
        if not self.path:
            raise Missing("page path", "pass the page path, e.g. /lawn-mowing")
        return self.path

    def need_docs(self):
        if not self.docs or not self.docs.exists():
            raise Missing("project docs folder", "create docs/ in the project folder (growth new-project makes it)")
        return self.docs

    def need_file(self, p: Path, fix):
        if not p.exists():
            raise Missing(str(p), fix)
        return p

    def git(self, *args, repo=None):
        r = repo or self.need_repo()
        code, out = run(["git", "-C", str(r), *args], timeout=60)
        if code != 0:
            raise Missing(f"git {' '.join(args)} in {r.name}", f"fix the checkout ({out.strip()[:120]})")
        return out

    def journal(self):
        """Journal entries (list of dicts) from the kit's journal/entries.jsonl."""
        if "journal" not in self.cache:
            f = self.need_file(self.project / "journal" / "entries.jsonl", "growth journal add ... (no journal yet)")
            self.cache["journal"] = [json.loads(l) for l in f.read_text().splitlines() if l.strip()]
        return self.cache["journal"]

    def page_entries(self):
        p = self.need_path()
        return [e for e in self.journal() if p in (e.get("pages") or [])]

    def last_commit_time(self):
        """Unix time of the newest commit in the worktree."""
        return int(self.git("log", "-1", "--format=%ct").strip())

    def last_change_time(self):
        """Unix time of the page's last change, so evidence (screenshots, click-through, share preview) can be checked
        for being newer. With a site checkout: its newest commit. With none (a static site): the newest file in the
        folder growth.json site_dir names, else the newest "before" capture of this page in archive/pages/. Raises Skip,
        saying what to set, when none of these exists, so a static site can still reach READY."""
        if self.repo and (self.repo / ".git").exists():
            return self.last_commit_time()
        newest = 0
        sd = self.cfg.get("site_dir")
        if sd:
            d = Path(sd).expanduser()
            d = d if d.is_absolute() else (self.project / d)
            newest = max((os.stat(f).st_mtime for f in d.rglob("*") if f.is_file() and not any(x.startswith(".") for x in f.relative_to(d).parts)), default=0)
        if not newest:
            slug = self.path.strip("/").replace("/", "-") or "home"
            snaps = self.project / "archive" / "pages" / slug
            newest = max((os.stat(f).st_mtime for f in snaps.rglob("*") if f.is_file() and f.parent.name.endswith("-before")), default=0) if snaps.is_dir() else 0
        if not newest:
            raise Skip("no way to date this page's last change (no site checkout): set growth.json site_repo or site_dir, or archive the page first (growth page_archive capture <path> --stage before)")
        return int(newest)

    def research(self, pattern):
        """Research files whose name contains the page key and matches pattern (a regex)."""
        rdir = self.need_file(self.project / "research", "mkdir research (research files live there)")
        key = self.need_key()
        return sorted(f for f in rdir.iterdir() if key in f.name and re.search(pattern, f.name))

    def need_key(self):
        if not self.key:
            raise Missing("page key", "pass --key, e.g. lawn-mowing")
        return self.key

    def tree_sources(self):
        """Source files of the page: its app route file plus every local import it pulls in, followed recursively."""
        if "tree" in self.cache:
            return self.cache["tree"]
        repo = self.need_repo()
        route = repo / "app" / self.need_path().strip("/") / "page.tsx"
        if self.path == "/":
            route = repo / "app" / "page.tsx"
        if not route.exists():
            raise Missing(f"route file {route.relative_to(repo)}", "check --repo and the page path")
        seen, todo = {}, [route]
        while todo:
            f = todo.pop()
            if f in seen or not f.exists():
                continue
            src = f.read_text(errors="replace")
            seen[f] = src
            for m in re.finditer(r"""(?:import|from)\s*['"]([^'"]+)['"]|import\(\s*['"]([^'"]+)['"]""", src):
                spec = m.group(1) or m.group(2)
                if spec.startswith("@/"):
                    base = repo / spec[2:]
                elif spec.startswith("."):
                    base = (f.parent / spec).resolve()
                else:
                    continue
                for cand in (base, *(base.with_name(base.name + ext) for ext in (".tsx", ".ts", ".css")),
                             base / "index.tsx", base / "index.ts"):
                    if cand.is_file():
                        todo.append(cand)
                        break
        self.cache["tree"] = seen
        return seen

    def repo_files(self, globs=("app/**/*.tsx", "app/**/*.ts", "components/**/*.tsx", "components/**/*.ts", "lib/**/*.ts")):
        repo = self.need_repo()
        out = []
        for g in globs:
            out += [p for p in repo.glob(g) if "node_modules" not in p.parts and ".next" not in p.parts]
        return sorted(set(out))

    def css_text(self):
        if "css" not in self.cache:
            repo = self.need_repo()
            files = sorted(p for p in (repo / "app").rglob("*.css")) + sorted((repo / "components").rglob("*.css"))
            if not files:
                raise Missing("site CSS files", "check --repo")
            self.cache["css"] = "\n".join(f.read_text(errors="replace") for f in files)
        return self.cache["css"]

    def nx(self, key, default=None):
        """A setting of growth.json "nextjs" (how this site's code is laid out); `default` when it is not set."""
        v = (self.cfg.get("nextjs") or {}).get(key)
        return default if v in (None, "", [], {}) else v

    def base_ref(self, repo=None):
        """The ref a branch is compared with (see base_ref_of); Missing, naming the setting, when there is none."""
        r = repo or self.need_repo()
        ref = base_ref_of(r, self.cfg)
        if not ref:
            raise Missing(f"the production branch (growth.json nextjs.production_branch, default main) in {r.name}",
                          "set growth.json nextjs.production_branch (and nextjs.remote) to the branch the site is published from")
        return ref

    def branch_files(self):
        """Files changed on the worktree's branch vs the production branch, plus uncommitted and untracked ones."""
        if "bfiles" not in self.cache:
            a = self.git("diff", "--name-only", self.base_ref() + "...HEAD").split()
            b = self.git("diff", "--name-only", "HEAD").split()
            c = self.git("ls-files", "--others", "--exclude-standard").split()
            self.cache["bfiles"] = sorted(set(a + b + c))
        return self.cache["bfiles"]

    def commit_email(self):
        """The git identity commits must carry: growth.json commit_identity.email (older name: committer_email)."""
        return (self.cfg.get("commit_identity") or {}).get("email") or self.cfg.get("committer_email", "")

    def site_origin(self):
        return self.cfg.get("site_url", "").rstrip("/")

    def booking_paths(self):
        """The paths a call to action may go to: the conversion path and the contact path (growth.json)."""
        return {p for p in (self.cfg.get("conversion_path"), (self.cfg.get("cta") or {}).get("contact_path")) if p}

    def internal_path(self, href):
        """Site path of an internal href, or None for an external/other link."""
        if not href or href.startswith(("mailto:", "tel:", "javascript:")):
            return None
        p = urllib.parse.urlsplit(urllib.parse.urljoin(self.url or self.site_origin() + "/", href))
        host = p.netloc.lower()
        local = urllib.parse.urlsplit(self.url).netloc.lower() if self.url else ""
        site = urllib.parse.urlsplit(self.site_origin()).netloc.lower()
        if host in (local, site, "www." + site):
            return p.path or "/"
        return None


def base_ref_of(repo, cfg):
    """<remote>/<production branch> (growth.json nextjs.remote, default origin; nextjs.production_branch, default main,
    else master), else the local production branch when there is no such remote. "" when none exists."""
    nx = cfg.get("nextjs") or {}
    branch, remote = nx.get("production_branch") or "", nx.get("remote") or "origin"
    for b in ([branch] if branch else ["main", "master"]):
        for cand in (f"{remote}/{b}", b):
            if run(["git", "-C", str(repo), "rev-parse", "--verify", "-q", cand + "^{commit}"])[0] == 0:
                return cand
    return ""


def run_check(ctx: Ctx, c: Check):
    ctx._cur = c
    n = len(ctx.lines)
    if c.needs not in ("live", "project") and c.needs != ctx.stack():
        ctx.skip(f"no adapter for {ctx.stack()} (this check reads {c.needs} code)")
        ctx._cur = None
        return
    try:
        c.fn(ctx)
    except Skip as m:
        del ctx.lines[n:]
        ctx.skip(m.why)
        ctx._cur = None
        return
    except NeedsPage as m:
        if ctx.static:
            del ctx.lines[n:]
            ctx.skipped.append(c.cid)
            ctx._cur = None
            return
        ctx.fail(f"input missing: {m.what}", m.fix)
    except Missing as m:
        ctx.fail(f"input missing: {m.what}", m.fix)
    except Exception as e:  # noqa: BLE001  a crashed check is a FAIL, never a silent pass
        ctx.fail(f"check crashed: {type(e).__name__}: {str(e)[:160]}", f"fix the check ({c.file})")
    if len(ctx.lines) == n:
        ctx.fail("check printed no result", f"fix {c.file}: every check must call ok() or fail()")
    ctx._cur = None


def short(s, n=90):
    s = re.sub(r"\s+", " ", s or "").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def words(s):
    return re.findall(r"[A-Za-z0-9][A-Za-z0-9'’$%.-]*", s or "")


def mtime(p: Path):
    return os.stat(p).st_mtime
