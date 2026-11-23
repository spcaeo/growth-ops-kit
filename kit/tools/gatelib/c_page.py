"""What the rendered page shows: the answer-first passage, FAQ, structured data, frame, folds, motion
(rules 12, 18, 25, 30, 36b, 43, 48-51, 56, 57, 96, 97, 103, 111, 135, 139, 141, 147, 150, 151, 159)."""
from __future__ import annotations

import json
import datetime as dt
import re
import sqlite3

import paths  # kit/tools/paths.py: one form of a site path
from techseo.c_schema import main_types
from techseo.dom import find, find_all

from . import design, domx
from .core import ALL, Missing, Skip, check, short  # noqa: F401  (the Next.js adapter star-imports this module)



def org_id_of(ctx):
    """The one Organization @id of the site: <site_url>/#organization (rule 150)."""
    return ctx.site_origin() + "/#organization"


def product(ctx):
    return ctx.cfg.get("product") or ctx.cfg.get("name") or "the business"


PRONOUN_OPENERS = r"(this|it|that|these|those|they)\b"
EMOJI = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000026FF\U00002700-\U000027BF]")


@check("page.renders", "111", what="the URL answers 200 with an H1 before anyone is asked to look", needs="live")
def renders(ctx):
    root = ctx.root()
    h1 = find(root, "h1")
    if ctx.status != 200 or h1 is None:
        ctx.fail(f"status {ctx.status}, H1 {'found' if h1 is not None else 'missing'}", "start the server and fix the page before showing it (rule 111)")
    else:
        ctx.ok(f"200 with H1 '{short(domx.text(h1), 60)}'")


def first_passage(ctx):
    sec = domx.first_section(ctx.root())
    if sec is None:
        return None, []
    ps = [domx.text(p) for p in find_all(sec, "p")]
    return sec, ps


@check("geo.answer-passage", "36b", types=("money", "hub", "core"), what="the first screen holds one quotable 40-60 word answer that names the product", needs="live")
def answer_passage(ctx):
    sec, ps = first_passage(ctx)
    if sec is None:
        ctx.fail("no first screen (no H1 inside <main>)", "put the H1 and its answer in the first section (rules 18, 36b)")
        return
    counts = [(len(p.split()), p) for p in ps]
    good = [p for n, p in counts if 40 <= n <= 60]
    if not good:
        near = max(counts, default=(0, ""))
        ctx.fail(f"no 40-60 word passage in the first screen (longest is {near[0]} words: '{short(near[1], 70)}')",
                 "rewrite the lead as one self-contained 40-60 word answer: what it is, who it is for, the one difference (rule 36b)")
    elif not any(re.search(r"(?i)" + re.escape(product(ctx)), p) for p in good):
        ctx.fail(f"the 40-60 word passage does not name {product(ctx)}", f"name the business in the passage: '{product(ctx)} is ...' (rule 36b)")
    else:
        ctx.ok(f"answer passage of {len(good[0].split())} words naming {product(ctx)}")


@check("geo.no-pronoun-openers", "36b", types=("money", "hub", "core"), what="no passage opens with 'This', 'It', 'That', 'These' (passages stand alone)", needs="live")
def pronoun_openers(ctx):
    m = domx.main(ctx.root())
    probs = []
    for p in find_all(m, "p") + find_all(m, "li"):
        if domx.in_chrome(p):
            continue
        t = domx.text(p)
        if len(t.split()) >= 8 and re.match(r"(?i)" + PRONOUN_OPENERS, t):
            probs.append(f"'{short(t, 60)}'")
    ctx.verdict(probs, "every passage names its subject", "start the passage with the thing it is about, not 'This' or 'It' (rule 36b)")


@check("geo.updated", "12", types=("money", "hub", "post", "core"), what="a visible 'Updated' date with the publisher, true and equal to dateModified", needs="live")
def updated(ctx):
    root = ctx.root()
    # The shown date is the <time> design.py finds for "updated_date" (the one equal to dateModified, or the one the
    # words "Updated" introduce), never simply the first date in the byline (that is often the publish date).
    vis = design.find(ctx, "updated_date")
    if not vis:
        # A page never changed after it went up says "Published <date>", not "Updated": the word must be true.
        times = [t for t in find_all(domx.main(root), "time") if t.get("datetime")]
        vis = [t for t in times if re.search(r"(?i)updated|published", domx.text(t.parent) + domx.text(t))]
    if not vis:
        ctx.fail("no visible 'Updated <date>' (or 'Published <date>' if never changed) with a <time datetime>", "show 'Updated <date> · by <publisher>' near the H1 (rules 12, 36b)")
        return
    t = vis[0]
    probs = []
    try:
        stamp = dt.datetime.fromisoformat(t.get("datetime").replace("Z", "+00:00"))
        if stamp.tzinfo is not None:   # a UTC time is judged on the project's own calendar day (growth.json timezone)
            from zoneinfo import ZoneInfo
            stamp = stamp.astimezone(ZoneInfo(ctx.cfg.get("timezone") or "UTC"))
        d = stamp.date()
        if d > ctx.today:
            probs.append(f"updated date {d} is in the future")
    except ValueError:
        probs.append(f"datetime '{t.get('datetime')}' is not ISO")
    by = {id(a) for a in design.find(ctx, "byline")}
    if not (re.search(r"(?i)\bby\b|" + re.escape(product(ctx)), domx.text(t.parent))
            or any(id(n) in by for a in [t.parent, t.parent.parent] if a is not None for n in a.iter())):
        probs.append("no publisher or byline beside the date")
    mods = [n.get("dateModified") for n in domx.jsonld(root) if n.get("dateModified")]
    if not mods:
        probs.append("no dateModified in the structured data")
    elif not str(mods[0]).startswith(t.get("datetime")[:10]):
        probs.append(f"dateModified {mods[0]} differs from the shown {t.get('datetime')}")
    ctx.verdict(probs, f"updated {t.get('datetime')} shown with publisher, equal to dateModified", "fix the date as listed (rules 12, 36b)")


@check("geo.liftable", "36b", types=("money",), what="one comparison table (caption, header cells) or definition list an AI can lift", needs="live")
def liftable(ctx):
    m = domx.main(ctx.root())
    tables = [t for t in find_all(m, "table") if find(t, "caption") is not None and find(t, "th") is not None]
    dls = [d for d in find_all(m, "dl") if len(find_all(d, "dt")) >= 2 and not domx.in_chrome(d)]
    if tables or dls:
        ctx.ok(f"{len(tables)} captioned table(s), {len(dls)} definition list(s)")
    else:
        ctx.fail("no captioned table or definition list", "add one real <table> with <caption> and <th scope> (rule 36b)")


@check("geo.table-sources", "25", types=ALL, what="every table carries a source and a check date", needs="live")
def table_sources(ctx):
    m = domx.main(ctx.root())
    probs = []
    for t in find_all(m, "table"):
        has_src, has_date = design.table_sourced(ctx, t)   # its box, its component (data-checked/data-source), its section
        if not (has_src and has_date):
            cap = find(t, "caption")
            probs.append(f"table '{short(domx.text(cap) if cap is not None else '', 50)}' lacks a {'source' if not has_src else 'check date'}")
    if not find_all(m, "table"):
        ctx.ok("no tables on the page")
        return
    ctx.verdict(probs, "every table names its source and check date", "add a source line with a link and 'Checked <date>' under the table, or data-checked and data-source on its component (rule 25)")


def faq_items(ctx, root=None):
    """(container, [(question, answer)]) for the page's FAQ, found by design.py: the questions under the FAQ heading or
    the FAQPage microdata, else growth.json design.faq_question; never a contents list or a fold."""
    qs = design.find(ctx, "faq_question", root)
    box = None
    if qs:   # the smallest element that holds every question (the FAQ's own section or box)
        box = next((a for a in qs[0].ancestors() if all(a in list(q.ancestors()) for q in qs[1:])), None)
        sec = next((a for a in ([box] if box is not None else []) + list(box.ancestors() if box is not None else [])
                    if a.tag == "section"), None)
        box = sec if sec is not None and sum(1 for d in find_all(sec, "details")) == len(qs) else box
    return box, design.faq_items(ctx, root)


def faq_schema(root):
    for n in domx.jsonld(root):
        if "FAQPage" in domx.types_of(n):
            ents = n.get("mainEntity") or []
            return [(e.get("name", "").strip(), (e.get("acceptedAnswer") or {}).get("text", "").strip()) for e in ents]
    return None


def norm(s):
    return re.sub(r"\s+", " ", s.replace("’", "'")).strip()


@check("faq.box", "139", types=("money", "hub", "post", "core"), what="one numbered FAQ box: 'N questions', Expand all, Collapse all, each question an <h3> in <summary>", needs="live")
def faq_box(ctx):
    root = ctx.root()
    sec, items = faq_items(ctx, root)
    if sec is None:
        if ctx.ptype == "money":
            ctx.fail("no FAQ box on a money page", "add the shared FAQ box with FAQPage markup (house features, rule 139)")
        else:
            ctx.ok("no FAQ on this page")
        return
    probs = []
    t = domx.text(sec)
    if not re.search(rf"\b{len(items)} questions\b", t):
        probs.append(f"no '{len(items)} questions' count")
    for lab in ("Expand all", "Collapse all"):
        if not any(domx.text(b).strip() == lab for b in find_all(sec, "button")):
            probs.append(f"no '{lab}' button")
    no_h3 = [d for d in find_all(sec, "details") if find(find(d, "summary") or d, "h3") is None]
    if no_h3:
        probs.append(f"{len(no_h3)} question(s) not an <h3> inside <summary>")
    if not find(sec, "ol"):
        probs.append("the questions are not a numbered list (<ol>)")
    ctx.verdict(probs, f"FAQ box with {len(items)} numbered questions", "use the shared FAQ box (rule 139)")


@check("faq.schema-equal", "96", types=("money", "hub", "post", "core"), what="FAQPage markup equals the visible FAQ word for word, in order; no repeated question", needs="live")
def faq_equal(ctx):
    root = ctx.root()
    _, items = faq_items(ctx, root)
    sch = faq_schema(root)
    if not items and sch is None:
        if ctx.ptype == "money":
            ctx.fail("no FAQ and no FAQPage markup on a money page", "add the FAQ box and build its FAQPage markup from the same list (rules 96, 151)")
        else:
            ctx.ok("no FAQ on this page")
        return
    probs = []
    if sch is None:
        probs.append("visible FAQ has no FAQPage markup")
    elif not items:
        probs.append("FAQPage markup but no visible FAQ")
    else:
        if len(sch) != len(items):
            probs.append(f"{len(items)} visible vs {len(sch)} in markup")
        for i, ((q, a), (sq, sa)) in enumerate(zip(items, sch), 1):
            if norm(q) != norm(sq):
                probs.append(f"Q{i} differs: '{short(q, 40)}' vs '{short(sq, 40)}'")
            if norm(a) != norm(sa):
                probs.append(f"A{i} differs from the markup")
    qs = [set(re.findall(r"[a-z0-9]+", q.lower())) for q, _ in items]
    for i in range(len(qs)):
        for j in range(i + 1, len(qs)):
            u = qs[i] | qs[j]
            if u and len(qs[i] & qs[j]) / len(u) >= 0.6:
                probs.append(f"Q{i + 1} and Q{j + 1} share 60%+ of their words")
    ctx.verdict(probs, f"FAQPage markup equals the {len(items)} visible questions", "build the markup from the same list as the box (rules 96, 151)")


@check("faq.answer-first", "36b", types=("money", "hub", "post", "core"), what="every FAQ answer opens with a one-sentence direct answer (3-30 words, no 'This/It' opener)", needs="live")
def faq_first(ctx):
    _, items = faq_items(ctx)
    if not items:
        if ctx.ptype == "money":
            ctx.fail("no FAQ on a money page", "add the FAQ box (rule 139)")
        else:
            ctx.ok("no FAQ on this page")
        return
    probs = []
    for i, (q, a) in enumerate(items, 1):
        sents = re.split(r"(?<=[.!?])\s+", a.strip()) if a else [""]
        first = sents[0]
        if re.fullmatch(r"(?i)(yes|no|not quite|it depends)[.!,]?", first) and len(sents) > 1:
            first = first + " " + sents[1]          # "Yes. Free planners exist ..." answers in its first two beats
        n = len(first.split())
        if not 3 <= n <= 30:
            probs.append(f"A{i} first sentence {n} words")
        elif re.match(r"(?i)" + PRONOUN_OPENERS, first):
            probs.append(f"A{i} opens with '{first.split()[0]}'")
    ctx.verdict(probs, f"all {len(items)} answers open with a direct sentence", "start each answer with a one-sentence direct answer of at most 30 words (rule 36b)")


@check("faq.ask-card", "135", types=("money", "hub", "post", "core"), what="after the FAQ: one ask card with 'Ask your question'", needs="live")
def ask_card(ctx):
    root = ctx.root()
    sec, items = faq_items(ctx, root)
    if sec is None:
        if ctx.ptype == "money":
            ctx.fail("no FAQ, so no ask card", "add the FAQ box and the ask card after it (rules 135, 139)")
        else:
            ctx.ok("no FAQ on this page")
        return
    btns = [b for b in find_all(sec, "button") + find_all(sec, "a") if domx.text(b).strip() == "Ask your question"]
    t = domx.text(sec)
    if btns and re.search(r"(?i)still have a question", t):
        ctx.ok("ask card follows the FAQ")
    else:
        ctx.fail("no ask card ('Still have a question...' + 'Ask your question') after the FAQ", "add the shared ask card after the FAQ (rule 135)")


@check("schema.org-id", "150", what="one Organization node with @id <site_url>/#organization; every publisher/provider points to it", needs="live")
def org_id(ctx):
    ORG_ID = org_id_of(ctx)
    nodes = domx.jsonld(ctx.root())
    if not nodes:
        ctx.fail("no structured data on the page", "add the page's JSON-LD with the shared Organization node (rule 150)")
        return
    probs = []
    # the brand's parent company (parentOrganization) is a different company with its own id; it is not a copy
    parents = {id(x.get("parentOrganization")) for n in nodes for x in domx.walk_json(n) if isinstance(x.get("parentOrganization"), dict)}
    orgs = [x for n in nodes for x in domx.walk_json(n) if "Organization" in domx.types_of(x) and id(x) not in parents]
    ids = {o.get("@id") for o in orgs}
    if ORG_ID not in ids:
        probs.append(f"no Organization with @id {ORG_ID}")
    if ids - {ORG_ID}:
        probs.append(f"other Organization ids: {sorted(str(i) for i in ids - {ORG_ID})}")
    for n in nodes:
        for x in domx.walk_json(n):
            for k in ("publisher", "provider"):
                v = x.get(k)
                if isinstance(v, dict) and v.get("@id") != ORG_ID:
                    probs.append(f"{k} does not point at {ORG_ID}")
    ctx.verdict(probs, "one Organization node, every publisher points to it", f"use {{'@id': '{ORG_ID}'}} everywhere (rule 150)")


@check("schema.house-types", "95", types=("money", "hub", "post", "core"), what="the page type's markup: money = a product, service or software node (never only the site's Organization) + BreadcrumbList (+ FAQPage with a FAQ); growth.json schema_types.money names the types", needs="live")
def house_types(ctx):
    root = ctx.root()
    have = {t for n in domx.jsonld(root) for x in domx.walk_json(n) for t in domx.types_of(x)}
    money = "|".join(main_types((ctx.cfg.get("schema_types") or {}).get("money")))   # never Organization: every page has it
    need = {"money": [money, "BreadcrumbList"], "post": ["Article|BlogPosting", "BreadcrumbList"],
            "hub": ["CollectionPage|WebPage", "BreadcrumbList"], "core": ["WebPage|AboutPage|ContactPage"]}[ctx.ptype]
    if ctx.need_path() == "/":
        need = [n for n in need if n != "BreadcrumbList"]   # home has no breadcrumbs (crumbs.visible); 2.6.3
    if faq_items(ctx, root)[1]:
        need.append("FAQPage")
    miss = [n for n in need if not set(n.split("|")) & have]
    ctx.verdict(miss, f"markup types present: {', '.join(sorted(have))}", "add the missing node built from what the page shows (rule 95)")


@check("schema.people", "97", what="structured data names no company or login as a Person; every Person has a url", needs="live")
def people(ctx):
    probs = []
    for n in domx.jsonld(ctx.root()):
        for x in domx.walk_json(n):
            if "Person" in domx.types_of(x):
                nm = str(x.get("name", ""))
                if re.search(r"(?i)" + re.escape(product(ctx)) + r"|admin|team|editor|staff|^$", nm):
                    probs.append(f"Person '{nm}'")
                elif not x.get("url"):
                    probs.append(f"Person '{nm}' has no url to an author page")
    if not domx.jsonld(ctx.root()):
        probs.append("no structured data")
    ctx.verdict(probs, "no wrong Person nodes", "make the company the publisher (Organization), never a Person (rule 97)")


THIN = 10  # views of the most-shown tracked search below which Search Console cannot choose a title's words


def gsc_top(ctx, n=2):
    db = ctx.project / "page-tracker" / "tracker.db"
    if not db.exists():
        raise Skip("no Search Console data yet (page tracker connector is off or has not synced: growth page-tracker sync)")
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rows = c.execute("select query, impressions from search_queries where path=? and snapshot="
                     "(select max(snapshot) from search_queries where path=?) order by impressions desc limit ?",
                     (paths.key(ctx.need_path()), paths.key(ctx.path), n * 4)).fetchall()   # the tracker stores paths without the slash
    c.close()
    # the '[us] ' tag marks the same search on a second copy of the page (page_tracker.path_variants): one search
    merged = {}
    for q, imp in rows:
        k = q[5:] if q.startswith("[us] ") else q
        merged[k] = merged.get(k, 0) + (imp or 0)
    return sorted(merged.items(), key=lambda kv: -kv[1])[:n]


def norm_title(s):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", (s or "").lower())).strip()


def live_title(ctx):
    """The page's title on the live site, from inventory/inventory.json (growth inventory), or "" when unknown."""
    try:
        inv = json.loads((ctx.project / "inventory" / "inventory.json").read_text())
    except (OSError, ValueError):
        return ""
    want = paths.normalize(ctx.need_path())
    return next((p.get("title") or "" for p in inv.get("pages", []) if paths.normalize(p.get("path", "")) == want), "")


@check("seo.title-query", "81", types=("money", "hub", "post"), what="the title holds one of the page's top-2 Search Console queries and fits 60 characters", needs="live")
def title_query(ctx):
    hold = (ctx.cfg.get("holds") or {}).get("title")
    if isinstance(hold, dict) and hold.get("why"):
        # the owner has frozen titles (e.g. while a Google core update rolls out): report, never block on it
        ctx.warn(f"titles are held ({hold['why']}; until {hold.get('until', 'lifted')}): title query not judged now",
                 "queue the new title in the research file; it ships as its own change when the hold lifts")
        return
    root = ctx.root()
    t = domx.text(domx.page_title(root)) if domx.page_title(root) is not None else ""
    # Too little data to choose from (one real case: 3 tracked searches with 1 view each, one a rival's domain, the rest
    # hidden by Google): use the target searches the page's plan names (dossier section 31).
    plan = ctx.project / "research" / "plans" / f"{ctx.key}.json"
    pj = json.loads(plan.read_text()) if ctx.key and plan.exists() else {}
    # The page's Search Console searches belong to another page by the duplication register (a hire page that ranks for
    # its hub's search): the plan names the page's own targets with a reason (2.4.2).
    use = pj.get("use_target_searches") or {}
    planned = bool(pj.get("target_searches")) and isinstance(use, dict) and len(str(use.get("why") or "")) >= 10
    if planned:
        top, src = [(q, "plan") for q in pj["target_searches"][:2]], f"plan: {short(str(use['why']), 60)}"
    else:
        top, src = gsc_top(ctx), "Search Console"
    if not planned and (not top or max(i for _, i in top) < THIN):
        tgt = pj.get("target_searches", [])
        if not tgt:
            ctx.fail(f"Search Console has too little data (top search under {THIN} views) and the plan names no target_searches",
                     f"add \"target_searches\": [...] (from the dossier's target searches) to research/plans/{ctx.key}.json (rule 81)")
            return
        top, src = [(q, "plan") for q in tgt[:2]], "plan"
    probs = []
    if len(t) > 60:
        probs.append(f"title is {len(t)} chars (max 60)")
    tl = re.sub(r"[^a-z0-9 ]", " ", t.lower())
    if not any(re.sub(r"\s+", " ", q.lower()) in re.sub(r"\s+", " ", tl) for q, _ in top):
        probs.append("title holds neither " + " nor ".join(f"'{q}' ({i} impr.)" for q, i in top))
    # Rule 74 keeps a live page's title unless the owner approves a change. When the page still shows its live title, a
    # missing query is a proposal for the owner, not a fault of the build (2.4.9).
    live = live_title(ctx)
    if probs and live and norm_title(live) == norm_title(t) and all(p.startswith("title holds neither") for p in probs):
        ctx.warn(f"title kept from the live page (rule 74): '{t}'; " + probs[0],
                 f"propose a title that starts with '{top[0][0]}' to the owner; it ships only with their yes (rules 74, 81)")
        return
    ctx.verdict(probs, f"title '{t}' ({len(t)} chars) holds a top query ({src})",
                f"rewrite the title to start with '{top[0][0]}' and stay at or under 60 characters (rule 81)")


@check("crumbs.visible", "50", types=("money", "hub", "post", "core"), what="visible breadcrumbs (except home) that match the BreadcrumbList", needs="live")
def crumbs(ctx):
    root = ctx.root()
    if ctx.need_path() == "/":
        ctx.ok("home has no breadcrumbs (correct)")
        return
    nav = next((n for n in root.iter() if n.tag in ("nav", "ol") and re.search(r"(?i)breadcrumb", n.get("aria-label") + n.get("class"))), None)
    sch = next((n for n in domx.jsonld(root) if "BreadcrumbList" in domx.types_of(n)), None)
    probs = []
    if nav is None:
        probs.append("no visible breadcrumb trail (nav aria-label='Breadcrumb')")
    if sch is None:
        probs.append("no BreadcrumbList markup")
    if nav is not None and sch is not None:
        names = [str(i.get("name", "")).strip() for i in sch.get("itemListElement", [])]
        vis = domx.text(nav)
        miss = [nm for nm in names if nm and nm not in vis]
        if miss:
            probs.append(f"markup crumbs not shown: {miss}")
    ctx.verdict(probs, "breadcrumbs shown and equal to the markup", "render the shared Breadcrumbs from the same data as the BreadcrumbList (rule 50)")


@check("layout.shared-frame", "43", what="one shared header, one <main>, one shared footer", needs="live")
def frame(ctx):
    root = ctx.root()
    hdr = design.find(ctx, "site_header")     # <header>/role=banner outside main, else growth.json design.site_header
    ftr = design.find(ctx, "site_footer")
    mains = design.find(ctx, "main")
    probs = []
    for name, got in (("site header", hdr), ("main", mains), ("site footer", ftr)):
        if len(got) != 1:
            probs.append(f"{len(got)} {name}")
    ctx.verdict(probs, "one site header, one main, one site footer", "render the page inside the shared layout (rules 43, 51)")


@check("layout.frame-type", "49", what="the page's frame fits its type (money full width, never a blog look; legal plain)", needs="live")
def frame_type(ctx):
    root = ctx.root()
    cls = " ".join(n.get("class") for n in root.iter())
    probs = []
    if ctx.ptype == "money" and re.search(r"\b(journal-page|editorial-post|post-article)\b", cls):
        probs.append("a money page uses the blog frame")
    if ctx.ptype == "post" and not re.search(r"\b(journal|post|article)", cls):
        probs.append("a post without the article frame")
    if re.search(r"(privacy|terms|thank)", ctx.path) and re.search(r"\bsticky-cta\b|\bexit-offer\b", cls):
        probs.append("a legal/thank-you page carries sales furniture")
    ctx.verdict(probs, f"frame fits a {ctx.ptype} page", "use the frame of the page's type (rule 49)")


WRAPPERS = {"div", "span", "aside", "nav"}


def signature(sec):
    """A fold's shape: its child tags three levels down, ignoring text. Markup that changes nothing for the reader does
    not count (2.4.3): a wrapper with one element child collapses into that child, and plain wrapper tags (div, span,
    aside, nav) are one generic box, so wrapping sentences in extra tags cannot make two look-alike folds 'distinct'."""
    def solid(n):
        while len(n.elements()) == 1 and (n.tag in WRAPPERS or n is not sec and not (n.own_text() or "").strip()):
            n = n.elements()[0]
        return n

    def sig(n, d):
        n = solid(n) if n is not sec else n
        tag = "box" if n.tag in WRAPPERS else n.tag
        if d == 0:
            return tag
        return tag + "(" + ",".join(sig(c, d - 1) for c in n.elements()[:8]) + ")"
    return sig(sec, 5)


@check("layout.folds-distinct", "30", types=("money", "hub"), what="no two folds of the page share the same structure", needs="live")
def folds(ctx):
    secs = domx.top_sections(ctx.root())
    if len(secs) < 2:
        ctx.fail(f"{len(secs)} fold(s) found (top-level <section> in main)", "build the page as folds, each a <section> with its own job (rule 30)")
        return
    seen, probs = {}, []
    for i, s in enumerate(secs, 1):
        k = signature(s)
        if k in seen:
            probs.append(f"fold {i} has the same shape as fold {seen[k]}")
        seen.setdefault(k, i)
    ctx.verdict(probs, f"{len(secs)} folds, all with their own shape", "give each fold its own shape and job (rule 30)")


@check("motion.reveal", "141", types=("money", "hub", "core"), what="every fold reveals as it scrolls in (reveal marker on each fold)", needs="live")
def reveal(ctx):
    secs = domx.top_sections(ctx.root())
    if not secs:
        ctx.fail("no folds found", "build the page as <section> folds (rule 141)")
        return
    bad = []
    hero = domx.first_section(ctx.root())
    # growth.json features.reveal_from: the first fold number that reveals (a site whose design keeps the first two
    # folds still, for a calm first screen, sets 3); default: every fold after the first screen
    rf = (ctx.cfg.get("features") or {}).get("reveal_from")
    start = int(rf) if isinstance(rf, int) and rf > 1 else 0
    for i, s in enumerate(secs, 1):
        if s is hero or i < start:
            continue                                  # the first screen is on view at load: nothing to reveal
        marks = list(s.iter())                       # the fold itself or a block inside it reveals
        # an empty attribute (<div data-reveal>) counts: its presence is the marker, not its value
        if not any(domx.has_cls(n, r".*(reveal|fold-in|fade|motion|animate).*") or "data-reveal" in n.attrs for n in marks):
            bad.append(f"fold {i} ({s.get('data-fold') or ' '.join(domx.classes(s)[:2])})")
    ctx.verdict(bad, f"all {len(secs) - 1} folds below the first screen carry a reveal marker", "wrap the fold in the shared Reveal (rule 141; rule 58 for how)")


@check("hero.split", "147", types=("money",), what="the first screen is split: words with the H1, and the page's own picture or tool beside them", needs="live")
def hero_split(ctx):
    sec = domx.first_section(ctx.root())
    if sec is None:
        ctx.fail("no first screen", "put the H1 in the first section (rule 147)")
        return
    kids = [c for c in sec.iter() if c is not sec and c.parent is not None]
    has_media = any(c.tag in ("svg", "img", "picture", "canvas", "form", "input", "video") for c in kids)
    cols = [c for c in sec.elements()]
    while len(cols) == 1:
        cols = cols[0].elements()
    h1col = [c for c in cols if find(c, "h1") is not None]
    other = [c for c in cols if find(c, "h1") is None and any(x.tag in ("svg", "img", "picture", "canvas", "form", "input") for x in c.iter())]
    if has_media and h1col and other:
        ctx.ok("first screen has a words column and a picture/tool column")
    else:
        ctx.fail("the first screen is not split into words + the page's own picture or tool",
                 "set the H1 and answer on the left, the page's own picture or tool on the right at 1280-1920 px (rule 147)")


def text_without_node(ctx, index):
    """The main text of the page with the index-th element of main (in document order) cut out, on a private copy of the tree."""
    from techseo.dom import parse
    m2 = domx.main(parse(ctx.need_html()))
    nodes = list(m2.iter())
    target = nodes[index]
    if target is m2:
        return ""
    target.parent.children = [c for c in target.parent.children if c is not target]
    return domx.text(m2)


@check("claims.box-numbers", "10", what="every number in a takeaway, stat or side box also appears in the page text", needs="live")
def box_numbers(ctx):
    m = domx.main(ctx.root())
    boxes = [n for n in m.iter() if (n.tag == "aside" or domx.has_cls(n, r".*(takeaway|stat|sidenote|side-note|callout|highlight).*"))
             and not design.ignored(ctx, n) and not domx.in_example(n)]   # computed (data-calculator), shared components (box_ignore) or a drawn example
    if not boxes:
        ctx.ok("no takeaway, stat or side boxes")
        return
    order = list(m.iter())
    probs = []
    for b in boxes:
        bt = domx.text(b, skip_examples=True)
        rest = text_without_node(ctx, order.index(b))          # the page's text without THIS box only: a copy of its number in the prose still counts
        for num in {x.rstrip(".,") if not x.endswith("%") else x for x in re.findall(r"\b\d[\d,.]*%?", bt)}:
            if num not in rest:
                probs.append(f"'{num}' only in a box")
    ctx.verdict(sorted(set(probs)), "box numbers are all in the text", "keep the number and state it in the text too, with its source; never delete a true, approved number to pass this check (rule 10)")


@check("icons.no-emoji", "57", what="no emoji in the interface or tables", needs="live")
def no_emoji(ctx):
    t = domx.text(domx.body(ctx.root()))
    hits = sorted(set(EMOJI.findall(t)))
    ctx.verdict([f"'{h}'" for h in hits], "no emoji", "use the one icon family with a word for screen readers (rules 57, 138)")


@check("embeds.lazy", "56", what="no iframe or third-party embed loads before the reader acts", needs="live")
def embeds(ctx):
    root = ctx.root()
    probs = [f"iframe {i.get('src')[:60]}" for i in find_all(root, "iframe") if i.get("src") and i.get("loading") != "lazy"
             and not i.in_tag("noscript")]   # a <noscript> iframe never loads while JavaScript is on
    ctx.verdict(probs, "no eager embeds", "load the embed on click or with loading=lazy (rule 56)")


ANALYTICS_HOSTS = (r"googletagmanager\.com|google-analytics\.com|analytics\.google\.com|doubleclick\.net|clarity\.ms|"
                   r"analytics\.ahrefs\.com|facebook\.(net|com)/tr|connect\.facebook|hotjar|segment\.(io|com)|plausible\.io|"
                   r"posthog|bat\.bing\.com|snap\.licdn|linkedin\.com/(px|li)|tiktok")


def watched_requests(url, wait_ms=4000):
    """Every request a page makes in a headless browser within wait_ms, one scroll and one click on the body (the
    usual delays before a tag manager loads). The browser always closes."""
    from playwright.sync_api import sync_playwright
    seen = []
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        try:
            pg = b.new_page()
            pg.on("request", lambda r: seen.append(r.url))
            pg.goto(url, wait_until="load", timeout=60000)
            pg.wait_for_timeout(wait_ms)
            pg.mouse.wheel(0, 1200)
            pg.mouse.click(5, 5)
            pg.wait_for_timeout(1500)
        finally:
            b.close()
    return seen


def host_guarded(inline, site_url):
    """True when the inline code tests location.hostname against this site's own host (e.g. a regex for example.com)."""
    host = re.sub(r"^https?://(www\.)?", "", (site_url or "").rstrip("/")).split("/")[0]
    if not host or "location.hostname" not in inline:
        return False
    return host in inline or re.escape(host) in inline or host.replace(".", "\\.") in inline


@check("tags.not-local", "103", what="no analytics or ad tag runs on a local or preview build", needs="live")
def tags_local(ctx):
    root = ctx.root()                      # the page first: with no page this check is SKIP, never an OK
    host = ctx.url.split("/")[2] if ctx.url.count("/") >= 2 else ""
    if not host.startswith(("127.0.0.1", "localhost")):
        ctx.ok("not a local build: tags allowed on the real domain")
        return
    fix = f"load tags only when the host is {ctx.cfg.get('site_url', 'the real domain')} (rule 103)"
    # 1. the truth: the requests the page really makes in a browser
    try:
        from .c_links import browser_failed, need_browser
        need_browser(ctx)
        try:
            hits = sorted({u.split("?")[0][:70] for u in watched_requests(ctx.url) if re.search(ANALYTICS_HOSTS, u)})
        except Exception as e:  # noqa: BLE001
            if not browser_failed(e):
                raise
            raise Skip("no headless browser")
        ctx.verdict([f"request to {h}" for h in hits], "no analytics request from the local build (headless browser, 5 s, a scroll and a click)", fix)
        return
    except Skip:
        pass
    # 2. without a browser: the page's markup, where a loader behind a hostname guard for this site counts as off
    srcs = [s.get("src") for s in find_all(root, "script") if s.get("src")]
    inline = " ".join(s.own_text() for s in find_all(root, "script"))
    bad = [s[:60] for s in srcs if re.search(ANALYTICS_HOSTS, s)]
    if re.search(r"googletagmanager\.com/gtm\.js", inline) and not host_guarded(inline, ctx.cfg.get("site_url")):
        bad.append("inline GTM loader")
    ctx.verdict(bad, "no analytics tags on the local build (markup read: no browser)", fix)


@check("form.bot-guard", "37", what="every lead form has a honeypot or bot check", needs="live")
def bot_guard(ctx):
    # a lead form sends something: an action, a POST, or a field for an email, phone or message. A calculator or a
    # filter form that posts nowhere is not a lead form and needs no bot check.
    def sends(f):
        return bool(f.get("action")) or f.get("method").lower() == "post" or any(
            n.tag == "textarea" or (n.tag == "input" and n.get("type").lower() in ("email", "tel")) for n in f.iter())
    def prefill_only(f):
        """A GET form whose action is an in-page anchor or the conversion path only prefills the real lead form."""
        act = f.get("action").strip()
        if (f.get("method") or "get").lower() != "get" or not act:
            return False
        return act.startswith("#") or (ctx.internal_path(act) or "").rstrip("/") in ctx.booking_paths()
    forms = [f for f in find_all(domx.main(ctx.root()), "form") if sends(f) and not prefill_only(f)]
    probs = []
    for f in forms:
        hidden = [i for i in find_all(f, "input") if i.get("tabindex") == "-1" or i.get("aria-hidden") == "true"
                  or re.search(r"(?i)honeypot|website|url_|hp", i.get("name"))]
        bot = re.search(r"(?i)turnstile|recaptcha|hcaptcha", " ".join(n.get("class") + n.get("src") for n in f.iter()))
        if not hidden and not bot:
            probs.append(f"form {f.get('action')[:40] or f.get('id') or '(no id)'} has no honeypot or bot check")
    ctx.verdict(probs, f"{len(forms)} form(s), each guarded" if forms else "no lead form on the page",
                "add a hidden honeypot field and an origin check (rule 37)")


@check("img.capture-date", "159", what="every product screenshot has its capture date in its file name", needs="live")
def capture_date(ctx):
    imgs = [i.get("src") for i in find_all(ctx.root(), "img")]
    shots = [s for s in imgs if re.search(r"(?i)screenshot|/product/|app-screen|/screens?/", s)]
    probs = [s[:70] for s in shots if not re.search(r"20\d\d-?\d\d-?\d\d", s)]
    ctx.verdict(probs, f"{len(shots)} product screenshot(s), all dated", "name the file with its capture date, e.g. dashboard-2026-11-17.webp (rule 159)")


@check("core.contact-form-first", "38", types=("core",), what="on Contact the form comes first", needs="live")
def contact_first(ctx):
    contact = (ctx.cfg.get("cta") or {}).get("contact_path")
    if not contact:
        raise Skip("no contact path in growth.json (cta.contact_path)")
    if ctx.need_path() != contact:
        ctx.ok("not the contact page")
        return
    secs = domx.top_sections(ctx.root())
    if secs and find(secs[0], "form") is not None:
        ctx.ok("the form is in the first fold")
    else:
        ctx.fail("the contact form is not in the first fold", "put the form first and the booking option in a band below (rule 38)")


@check("core.service-links", "146", types=("core",), what="About and Contact link every topic-cluster page by name (growth.json silos)", needs="live")
def service_links(ctx):
    if not ctx.cfg.get("silos"):
        raise Skip("no topic clusters in growth.json (silos)")
    if ctx.need_path() not in ctx.cfg.get("trust_paths", ["/about", (ctx.cfg.get("cta") or {}).get("contact_path", "")]):
        ctx.ok("not About or Contact")
        return
    m = domx.main(ctx.root())
    hrefs = {paths.normalize(h) for h in (ctx.internal_path(a.get("href")) for a in find_all(m, "a")) if h}     # "/x/" and "/x" are one page
    miss = [s for s in ctx.cfg.get("silos", {}) if paths.normalize("/" + s) not in hrefs]
    ctx.verdict(miss, "every topic page linked in the main text", "link each topic page by name in the text (rule 146)")


def prose_links(ctx, node):
    """Internal text links inside running text (<p>/<li>/<dd>), never buttons, headings or booking links."""
    out = []
    for a in find_all(node, "a"):
        p = ctx.internal_path(a.get("href"))
        if not p or domx.in_chrome(a) or domx.has_cls(a, r"button.*|.*-button|.*cta.*"):
            continue
        if p.rstrip("/") in ctx.booking_paths() or a.get("href").startswith("#"):
            continue
        if any(x.tag in ("h1", "h2", "h3", "h4", "summary") for x in a.ancestors()):
            continue
        if any(domx.has_cls(x, r".*(card|shel(f|ves)|tile|crumb).*") for x in a.ancestors()) or domx.has_cls(a, r".*card.*"):
            continue                                  # cards, shelves and breadcrumbs are not prose
        if any(x.tag in ("p", "li", "dd", "td") for x in a.ancestors()):
            out.append(a)
    return out


@check("links.in-folds", "88b", types=("money",), what="every content fold links from its running text; 10 to 14 prose links, every anchor different", needs="live")
def in_folds(ctx):
    root = ctx.root()
    secs = domx.top_sections(root)
    if not secs:
        ctx.fail("no folds found", "build the page as <section> folds (rule 88b)")
        return
    probs, total = [], []
    for i, s in enumerate(secs, 1):
        if re.search(r"shel(f|ves)|closing", s.get("class")):
            continue                                  # shelves and the closing call do not count (rule 88b)
        words_ = sum(len(domx.text(p).split()) for p in find_all(s, "p"))
        links = prose_links(ctx, s)
        total += links
        if words_ >= 40 and not links:
            probs.append(f"fold {i} ({s.get('data-fold') or ' '.join(domx.classes(s)[:2])}) has no prose link")
    anchors = [domx.text(a).lower() for a in total]
    dup = sorted({x for x in anchors if anchors.count(x) > 1})
    if not 10 <= len(total) <= 14:
        probs.append(f"{len(total)} prose links (10 to 14 needed)")
    if dup:
        probs.append(f"repeated anchors: {dup[:3]}")
    ctx.verdict(probs, f"{len(total)} prose links across the folds, all anchors different",
                "link words already in each fold's sentences to the guide that answers more (growth link_map suggest) (rule 88b)")


@check("seo.kept", "74", types=ALL, what="a changed title, description or H1 vs the live page has a journal entry with the reason", needs="project")
def kept(ctx):
    inv = ctx.need_file(ctx.project / "inventory" / "inventory.json", "growth inventory")
    live = next((p for p in json.loads(inv.read_text())["pages"] if paths.key(p["path"]) == paths.key(ctx.need_path())), None)
    if live is None:
        ctx.ok("a new page: nothing live to keep")
        return
    from techseo.dom import find
    root = ctx.root()
    now = {"title": domx.text(domx.page_title(root)) if domx.page_title(root) is not None else "",
           "meta_description": next((m.get("content") for m in find_all(root, "meta") if m.get("name") == "description"), ""),
           "h1": domx.text(find(root, "h1")) if find(root, "h1") is not None else ""}
    changed = [k for k, v in now.items() if (live.get(k) or "").strip() != v.strip()]
    why = [e for e in ctx.page_entries() if e.get("kind") in ("decision", "finding") and set(e.get("tags") or []) & {"title", "seo", "geo"}]
    if changed and not why:
        ctx.fail(f"changed vs live: {', '.join(changed)}, no journal reason", "file the evidence: growth journal add --page <path> --kind decision --tag title (rule 74)")
    else:
        ctx.ok(f"changed: {', '.join(changed) or 'nothing'}" + (f"; reason {why[0]['id']}" if changed else ""))
