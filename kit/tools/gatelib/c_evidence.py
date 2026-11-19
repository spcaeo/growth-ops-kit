"""Code proxies for the judgment rules: a person must look, check or decide, and the program checks that the
evidence of it exists and is fresh (screenshots newer than the page's last change, journal entries, research files)."""
from __future__ import annotations

import datetime as dt
import json
import re
from zoneinfo import ZoneInfo

from .core import ALL, Missing, check, mtime
import paths  # noqa: E402  kit/tools/paths.py: one form of a site path

FRESH_DAYS = 30
# One naming rule for research files, the same in book/playbooks/cluster-redesign.md. The page key comes first and the
# pattern is matched on the rest of the name: "-audit-<date>" or "-review-<date>" for the independent review (a date is
# required, so a page key that merely contains "review" does not pass); "-research-check", "-fact-check", "-claims" or
# "-research-<date>" for the fact check.
DATE = r"\d{4}-\d{2}-\d{2}"
REVIEW_NAME = rf"-(audit|review)-.*{DATE}"
RESEARCH_NAME = rf"-(research-check|fact-check|claims)\b|-research-{DATE}"


def at(e, tz):
    """A journal entry's time as an aware datetime."""
    try:
        return dt.datetime.strptime(e.get("at", "")[:16], "%Y-%m-%d %H:%M").replace(tzinfo=tz)
    except ValueError:
        return None


def tz(ctx):
    return ZoneInfo(ctx.cfg.get("timezone", "UTC"))


def shots(ctx):
    rdir = ctx.need_file(ctx.project / "research", "mkdir research")
    key = ctx.need_key()
    dirs = [d for d in rdir.iterdir() if d.is_dir() and key in d.name and d.name.endswith("-shots")]
    if not dirs:
        raise Missing(f"research/*{key}*-shots/", "take the screenshots into research/<page>-shots/<name>-<width>.png")
    return [p for d in dirs for p in d.rglob("*.png")]  # subfolders too (e.g. sketch/), per style round


def fresh_widths(ctx, widths):
    since = ctx.last_change_time()
    files = shots(ctx)
    have = {}
    for p in files:
        m = re.search(r"-(\d{3,4})\.png$", p.name)
        if m and mtime(p) >= since:
            have.setdefault(int(m.group(1)), []).append(p.name)
    return [w for w in widths if w not in have], have


def tagged_after_commit(ctx, tag):
    # journal times are kept to the minute; compare at the minute, so an entry filed in the commit's minute counts
    t0 = dt.datetime.fromtimestamp(ctx.last_change_time(), tz(ctx)).replace(second=0, microsecond=0)
    return [e for e in ctx.page_entries() if tag in (e.get("tags") or []) and (at(e, tz(ctx)) or t0) >= t0]


@check("ev.shots-1366-390", "158", ALL, "screenshots at 1366 and 390 px, newer than the page's last change (the designer's look)", needs="project")
def shots_158(ctx):
    miss, have = fresh_widths(ctx, (1366, 390))
    ctx.verdict([f"no {w}px shot newer than the page's last change" for w in miss],
                f"{len(have.get(1366, []))} shots at 1366 and {len(have.get(390, []))} at 390, newer than the page's last change",
                "look at every screen at 1366 and 390 as a demanding designer and save the shots in research/<page>-shots/ (rule 158)")


@check("ev.shots-widths", "106", ALL, "screenshots at 360, 390, 820, 1280 and 1920 px, newer than the page's last change", needs="project")
def shots_106(ctx):
    miss, _ = fresh_widths(ctx, (360, 390, 820, 1280, 1920))
    ctx.verdict([f"no {w}px shot" for w in miss], "shots at all five widths, newer than the page's last change",
                "check the page at 360, 390, 820, 1280 and 1920 and save <name>-<width>.png (rules 106, 68, 39)")


@check("ev.decision", "116", ALL, "the owner's check-in or yes for this page is filed as a journal decision", needs="project")
def decision(ctx):
    d = [e for e in ctx.page_entries() if e.get("kind") == "decision"]
    if d:
        ctx.ok(f"{len(d)} decision(s), latest {d[-1]['id']}: {d[-1].get('title', '')[:60]}")
    else:
        ctx.fail("no owner decision filed for this page", "file the owner's answer: growth journal add --page <path> --kind decision ... (rules 0, 116)")


def research_fresh(ctx, pattern, what, fix, min_lines=1):
    files = ctx.research(pattern)
    cut = (dt.datetime.now() - dt.timedelta(days=FRESH_DAYS)).timestamp()
    fresh = [f for f in files if mtime(f) >= cut and len(f.read_text(errors="replace").splitlines()) >= min_lines]
    if fresh:
        ctx.ok(f"{what}: {fresh[-1].name}")
    else:
        ctx.fail(f"no {what} in research/ within {FRESH_DAYS} days", fix)


@check("ev.research-check", "5", ALL, "a fact check of the page's claims against official sources, within 30 days", needs="project")
def research_check(ctx):
    research_fresh(ctx, RESEARCH_NAME, "fact check",
                   "check every claim against its official source and save research/<page>-research-check-<date>.md, or the researcher's "
                   "research/<page>-research-<date>.md (rules 5, 6)")


@check("ev.dossier", "27", ("money", "hub"), "the page's research dossier (32 questions, competitors) exists", needs="project")
def dossier(ctx):
    files = ctx.research(r"dossier")
    if not files:
        ctx.fail("no dossier in research/", "run the money-page research (32-question dossier) first (rule 27; book/02-owner-rules.md 'Money pages are unique')")
        return
    n = len(re.findall(r"(?m)^#{2,4}\s*(Q|Question\s*)?\d{1,2}\b", files[-1].read_text(errors="replace")))
    ctx.verdict([f"{files[-1].name} answers {n} of 32 questions"] if n < 32 else [], f"{files[-1].name}: {n} questions",
                "answer all 32 dossier questions (money-page playbook)")


def checklist_ids(ctx):
    """The ids (R1, R2 ...) of kit/checklists/review.md: the fixed list every independent review answers."""
    f = ctx.kit_dir / "checklists" / "review.md"
    return re.findall(r"(?m)^- \*\*(R\d+)\b", f.read_text()) if f.is_file() else []


VERDICT = r"(?mi)^[\s>*_`|-]*(?:\[.\]\s*)?(R\d+)\b[\s:.)*_`|-]*(pass(?:ed)?|fixed|n/a)\b"


def review_problems(text, ids):
    """What an independent review file still lacks: a verdict (pass, fixed, n/a) for every checklist id, and a reviewer
    who is not the builder."""
    got = {m.group(1).upper() for m in re.finditer(VERDICT, text)}
    out = [f"{i} has no verdict (pass, fixed or n/a)" for i in ids if i not in got]
    rev = re.search(r"(?mi)^[\s*_-]*reviewer\b[\s*_]*:\s*(.+)$", text)
    bld = re.search(r"(?mi)^[\s*_-]*builder\b[\s*_]*:\s*(.+)$", text)
    if not rev or not rev.group(1).strip().strip("*_ "):
        out.append("no 'Reviewer: <model>' line")
    elif bld and bld.group(1).strip().lower() == rev.group(1).strip().lower():
        out.append("the reviewer is the builder (a different model must review)")
    return out


@check("ev.review", "109", ALL, "an independent review of the built page, within 30 days, that answers every item of the review checklist", needs="project")
def review(ctx):
    files = ctx.research(REVIEW_NAME)
    cut = (dt.datetime.now() - dt.timedelta(days=FRESH_DAYS)).timestamp()
    fresh = [f for f in files if mtime(f) >= cut]
    fix = ("have a reviewer (a different model from the builder) review the page against kit/checklists/review.md: growth review new "
           f"{ctx.key or '<page>'} writes research/<page>-review-<date>.md; answer every item (rule 109)")
    if not fresh:
        ctx.fail(f"no independent review in research/ within {FRESH_DAYS} days", fix)
        return
    ids = checklist_ids(ctx)
    if not ids:
        raise Missing("kit/checklists/review.md", "restore the kit's review checklist")
    probs = review_problems(fresh[-1].read_text(errors="replace"), ids)
    ctx.verdict([f"{fresh[-1].name}: " + "; ".join(probs[:6]) + (f"; +{len(probs) - 6} more" if len(probs) > 6 else "")] if probs else [],
                f"independent review: {fresh[-1].name} answers all {len(ids)} checklist items", fix)


@check("ev.ai-baseline", "152", ("money",), "AI-answer baseline: 10+ journal runs for the page in the US market within 30 days", needs="project")
def ai_baseline(ctx):
    cut = dt.datetime.now(tz(ctx)) - dt.timedelta(days=FRESH_DAYS)
    market = (ctx.cfg.get("market") or {}).get("primary_country", "US")
    runs = [e for e in ctx.page_entries() if e.get("kind") == "run" and e.get("market") == market and (at(e, tz(ctx)) or cut) >= cut]
    ctx.verdict([f"{len(runs)} {market} runs (10 needed)"] if len(runs) < 10 else [], f"{len(runs)} {market} AI-answer runs",
                f"run the buyer's 10-15 AI questions with a {market} place and file them: growth journal run --market {market} (money-page.md 35)")


@check("ev.snapshot", "OR-snapshot", ALL, "a before snapshot of the page exists (inventory/pages/<slug>/<date>.md)", needs="project")
def snapshot(ctx):
    if paths.key(ctx.need_path()) in {paths.key(p) for p in ctx.cfg.get("new_pages", [])}:
        ctx.ok("new page: no live snapshot yet (growth.json new_pages)")
        return
    d = ctx.project / "inventory" / "pages" / paths.snapshot_slug(ctx.need_path())
    snaps = sorted(d.glob("*.md")) if d.exists() else []
    if snaps:
        ctx.ok(f"snapshot {snaps[-1].name}")
    else:
        ctx.fail("no page snapshot", f"growth page_snapshot {ctx.path} (book/02-owner-rules.md 'Snapshot every page we touch')")


def step_order(s):
    """(number, letter, list position) from a step's label 'Step 16a. ...'; a step with no label keeps its place."""
    m = re.match(r"\s*(?:Playbook |Pipeline |Part )?step\s*(\d+)([a-z]?)", s.get("what", ""), re.I)
    return (int(m.group(1)), m.group(2), s.get("n", 0)) if m else (s.get("n", 0), "", s.get("n", 0))


@check("ev.task-steps", "0", ALL, "the page's task in docs/tasks.json lists the playbook steps; none skipped", needs="project")
def task_steps(ctx):
    t = json.loads(ctx.need_file(ctx.need_docs() / "tasks.json", "growth tasks add ...").read_text())
    # the path as a whole token: "/pricing" must not match "page/pricing" in another
    # page's task title (a real mistake: one page read another page's task, found by its path inside a longer path)
    tok = re.compile(r"(?<![\w/-])" + re.escape(paths.key(ctx.need_path())) + r"/?(?![\w/-])")   # with or without its slash
    # a title may name the page by its full address: drop the site's own origin first (https://www.example.com/x/ -> /x/)
    site = re.sub(r"^https?://(www\.)?", "", (ctx.cfg.get("site_url") or "").rstrip("/"))
    own = re.compile(r"https?://(?:www\.)?" + re.escape(site.removeprefix("www.")), re.I) if site else None
    mine = [x for x in t["tasks"] if tok.search(own.sub("", x.get("title", "")) if own else x.get("title", ""))]
    if not mine:
        ctx.fail("no task names this page", "growth tasks add '<job>: <path>' and copy the playbook steps in (rule 0)")
        return
    task = mine[-1]
    steps = task.get("steps", [])
    probs = []
    if len(steps) < 5:
        probs.append(f"{task['id']} has {len(steps)} steps")
    probs += [f"{task['id']} step {s.get('n')} skipped" for s in steps if s.get("status") == "skipped"]
    # A step still "todo" while a later step is done was either skipped or done and never ticked (from a real project,
    # 30 such steps once sat on five finished pages). Steps that only happen after the release may wait.
    after = re.compile(r"(?i)release|index|re-read|measure|day 7")
    # judge order by the step's own label ("Step 16a" comes after "Step 16"), not by where it sits in the list:
    # steps can only be appended, so a step added later would otherwise make every earlier step look skipped
    steps = sorted(steps, key=step_order)
    last_done = max((i for i, s in enumerate(steps) if s.get("status") == "done"), default=-1)
    stale = [s for s in steps[:max(last_done, 0)] if s.get("status") == "todo" and not after.search(s.get("what", ""))]   # none done yet: nothing is stale
    probs += [f"{task['id']} step {s.get('n')} still todo while later steps are done: {s.get('what', '')[:60]}" for s in stale]
    # growth.json proof_required_since ("YYYY-MM-DD" or "YYYY-MM-DD HH:MM"): steps ticked done before it may lack proof (a
    # project that adopted proofs later); with no setting every done step needs its proof
    since = str(ctx.cfg.get("proof_required_since") or "")
    probs += [f"{task['id']} step {s.get('n')} done with no proof" for s in steps
              if s.get("status") == "done" and not s.get("output") and (not since or s.get("at", "")[:len(since)] >= since)]
    # a proof must name something checkable that exists (audit H1): "x", "abc" or a made-up commit is not proof;
    # proof_required_since grandfathers older steps here too
    import checkpoints
    repos = [ctx.repo] if ctx.repo else []
    for s in steps:
        if s.get("status") == "done" and s.get("output") and (not since or s.get("at", "")[:len(since)] >= since):
            why = checkpoints.proof_problem(s["output"], ctx.project, repos)
            if why:
                probs.append(f"{task['id']} step {s.get('n')} proof is not checkable: {why[:110]}")
    probs += [f"{task['id']} was closed with open steps {f.get('open_steps')} (forced: {f.get('reason', '')[:60]})"
              for f in task.get("forced") or [] if task.get("status") == "done"]
    ctx.verdict(probs, f"{task['id']}: {len(steps)} steps, none skipped or left open",
                "do the step, or tick it with its proof: growth tasks tick <task> <n> --output <proof>; raise a step with the owner before skipping it (rule 0)")


@check("ev.click-test", "160", ALL, "every control was clicked in a real browser after the page's last change (journal tag click-test)", needs="project")
def click_test(ctx):
    e = tagged_after_commit(ctx, "click-test")
    if e:
        ctx.ok(f"click-through filed: {e[-1]['id']}")
    else:
        ctx.fail("no click-through after the page's last change",
                 "click every button, tab, slider and toggle; file it: growth journal add --page <path> --kind note --tag click-test (rule 160)")


@check("ev.speed", "154", ALL, "after publishing: the page's Lighthouse run on the production site is filed (speed is tested on the production server)", stage="release", needs="project")
def speed(ctx):
    setup = ctx.need_file(ctx.project / "SETUP.md", "restore SETUP.md").read_text()
    probs = []
    if not re.search(r"(?i)lighthouse[^\n]*\n(\|[^\n]*\d{2}[^\n]*\n){3,}", setup):
        probs.append("SETUP.md has no Lighthouse baseline table (home, a money page, blog, post, contact)")
    if not tagged_after_commit(ctx, "speed"):
        probs.append("no Lighthouse run for this page after the page's last change (journal tag speed)")
    ctx.verdict(probs, "speed baseline and this page's run filed", "run Lighthouse; record the baseline in SETUP.md and file the page run: growth journal run --page <path> --engine lighthouse --tag speed, with analytics hosts blocked (rules 101, 154)")


@check("ev.share-preview", "108", ALL, "the share preview and search snippet were looked at after the page's last change (journal tag share-preview)", needs="project")
def share_preview(ctx):
    e = tagged_after_commit(ctx, "share-preview")
    ctx.verdict([] if e else ["no share-preview look after the page's last change"], "share preview looked at",
                "open the share preview and the snippet; file it: growth journal add --page <path> --kind note --tag share-preview (rule 108)")


@check("ev.journal-page", "OR-journal", ALL, "the page has journal entries within 30 days", needs="project")
def journal_page(ctx):
    cut = dt.datetime.now(tz(ctx)) - dt.timedelta(days=FRESH_DAYS)
    ents = [e for e in ctx.page_entries() if (at(e, tz(ctx)) or cut) >= cut]
    ctx.verdict([] if ents else ["no journal entry for this page in 30 days"], f"{len(ents)} journal entries in 30 days",
                "file findings, questions and decisions with growth journal (book/02-owner-rules.md 'Keep a page journal')")


@check("ev.open-findings", "130", ALL, "no open finding or question for the page older than 7 days", needs="project")
def open_findings(ctx):
    cut = dt.datetime.now(tz(ctx)) - dt.timedelta(days=7)
    old = [e["id"] for e in ctx.page_entries() if e.get("status") == "open" and e.get("kind") in ("finding", "question")
           and (at(e, tz(ctx)) or cut) < cut]
    ctx.verdict(old, "no stale open findings", "fix the real page now, then growth journal close <id> --output \"what was done and its proof\" (rule 130)")


@check("ev.inventory", "OR-inventory", ALL, "the inventory is fresh (7 days) and holds the page", needs="project")
def inventory(ctx):
    inv = json.loads(ctx.need_file(ctx.project / "inventory" / "inventory.json", "growth inventory").read_text())
    probs = []
    if inv["meta"]["generated"][:10] < (ctx.today - dt.timedelta(days=7)).isoformat():
        probs.append(f"inventory built {inv['meta']['generated'][:10]}")
    page = next((p for p in inv["pages"] if paths.key(p["path"]) == paths.key(ctx.need_path())), None)
    if page is None and paths.key(ctx.path) in {paths.key(p) for p in ctx.cfg.get("new_pages", [])}:
        pass
    elif page is None:
        probs.append("page not in the inventory")
    elif ctx.ptype == "money" and not page.get("money_page"):
        probs.append("the inventory does not mark it a money page")
    ctx.verdict(probs, "inventory fresh and holds the page", "growth inventory (book/02-owner-rules.md 'Inventory first')")


@check("ev.release-check", "127", ALL, "after the merge: the live page was checked once and the host's 5xx log read (journal tag release)", stage="release", needs="project")
def release_check(ctx):
    e = tagged_after_commit(ctx, "release")
    ctx.verdict([] if e else ["no release check filed after the merge"], "live check filed",
                "check the live page with one request, read the host's 5xx log; file --tag release (rules 127, 155, 77)")


@check("ev.rechecks", "OR-measure", ALL, "day 7, 14, 28 and 56 re-checks are scheduled for the released page", stage="release", needs="project")
def rechecks(ctx):
    r = [e for e in ctx.page_entries() if e.get("recheck_on")]
    ctx.verdict([] if len(r) >= 4 else [f"{len(r)} re-check(s) scheduled (4 needed)"], f"{len(r)} re-checks scheduled",
                "file the day 7/14/28/56 re-checks with --recheck (book/02-owner-rules.md 'Measure every release')")


@check("ev.brief", "0", ALL, "the helper's brief was generated by growth brief and is newer than the last owner instruction", needs="project")
def brief(ctx):
    """From a real project: "are your agents following the guide, SOP, background data, all of it 100%, not a single
    item missed?". A hand-written brief forgets things; growth brief copies every rule, step and instruction in."""
    b = ctx.project / "research" / "briefs" / f"{ctx.need_key()}.md"
    if not b.exists():
        ctx.fail("no generated brief", f"growth brief {ctx.need_path()} --type {ctx.ptype} --task <id> --out research/briefs/{ctx.key}.md")
        return
    log = ctx.need_docs() / "steps-log.md"
    ctx.verdict([] if mtime(b) >= mtime(log) - 1 else ["brief is older than the newest owner instruction"],
                f"brief {b.name} is current", f"regenerate it with growth brief and send the new rows to the helper (rule 0)")


@check("ev.preflight", "0a", ALL, "pre-flight passed before the build: planning complete, site health clean, checkpoint plan written", needs="project")
def preflight(ctx):
    """From a real project: "when you start a new page the planning and preparation should be done in depth and all
    checkpoints clear set as part of the playbook and workflow." growth preflight records the pass."""
    led = ctx.project / "journal" / "preflight.json"
    e = (json.loads(led.read_text()) if led.exists() else {}).get(ctx.need_path().rstrip("/") or "/")
    probs = ["no pre-flight run"] if not e else ([] if e.get("ok") else
            [f"pre-flight FAIL ({e.get('site_problems')} site problems, {e.get('plan_missing')} planning items missing)"])
    ctx.verdict(probs, f"pre-flight passed {e.get('at') if e else ''}",
                f"growth preflight {ctx.path} --type {ctx.ptype} --key {ctx.key} (rule 0a)")
