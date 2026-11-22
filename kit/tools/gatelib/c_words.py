"""Words on the page: banned words, claims, placeholders, the call's length, spelling (rules 1-4, 11, 14, 16, 20, 36, 93)."""
from __future__ import annotations

import json
import re

import paths  # kit/tools/paths.py: one form of a site path

from techseo.dom import find, find_all

from . import design, domx, spelling
from .core import Skip, check, short

# The words a page may not use about its own offer, the claims it may never make and the customers it may not name are the
# business's own: growth.json "words" holds them (see templates/project/growth.json). What follows is only the generic part.
# "free" is allowed only when it describes another product ("a free planner", "free route planners").
FREE_OK_NEXT = {"planner", "planners", "tool", "tools", "app", "apps", "software", "routing", "route", "maps", "spreadsheet",
                "spreadsheets", "version", "versions"}
NEGATIONS = {"not", "no", "without", "never", "isn't", "isnt", "isn’t"}
# Plain voice, no hype words (every site; growth.json words.hype replaces the list).
HYPE = [r"revolutionary", r"game[- ]chang\w*", r"cutting[- ]edge", r"best[- ]in[- ]class", r"world[- ]class", r"unparalleled",
        r"next[- ]generation", r"state[- ]of[- ]the[- ]art", r"supercharge\w*", r"skyrocket\w*", r"seamless\w*", r"synerg\w*",
        r"unleash\w*", r"disrupt\w*"]
# Implied proof nobody approved: customer lists, awards, star symbols (every site; growth.json words.hidden_customers adds names).
IMPLIED_PROOF = [r"trusted by", r"teams like yours", r"customers love", r"case stud(y|ies)", r"award[- ]winning",
                 r"\d+\s*\+?\s*(customers|clients|businesses) (use|trust)", r"★"]
UK_US = {"colour": "color", "colours": "colors", "favourite": "favorite", "optimise": "optimize", "optimised": "optimized",
         "optimising": "optimizing", "optimisation": "optimization", "organise": "organize", "organised": "organized",
         "organisation": "organization", "centre": "center", "centres": "centers", "analyse": "analyze", "analysed": "analyzed",
         "behaviour": "behavior", "licence": "license", "cheque": "check", "tyre": "tire", "tyres": "tires", "programme": "program",
         "catalogue": "catalog", "travelling": "traveling", "travelled": "traveled", "modelling": "modeling", "labelled": "labeled",
         "fulfil": "fulfill", "enrol": "enroll", "defence": "defense", "grey": "gray", "metre": "meter", "metres": "meters",
         "litre": "liter", "litres": "liters", "kilometre": "kilometer", "summarise": "summarize", "prioritise": "prioritize",
         "recognise": "recognize", "minimise": "minimize", "maximise": "maximize", "utilise": "utilize", "routeing": "routing"}
NUMWORDS = {5: "five", 10: "ten", 15: "fifteen", 20: "twenty", 30: "thirty", 45: "forty-five", 60: "sixty", 90: "ninety"}
NUM = r"(\d+|one|two|five|ten|fifteen|twenty|thirty|forty|forty[- ]five|sixty|ninety)"


def wcfg(ctx, key, default=None):
    """growth.json words.<key>: the business's own word lists and numbers."""
    v = (ctx.cfg.get("words") or {}).get(key)
    return default if v is None else v


CASE_STUDY = r"case stud(y|ies)"


def case_study_page(ctx) -> bool:
    """A page about case studies may use the words in its own name: its path holds "case-stud", or fits words.no_customers_allow_paths."""
    from fnmatch import fnmatch
    p = paths.normalize(ctx.path or "/")
    return "case-stud" in p.lower() or any(fnmatch(x, g) for g in wcfg(ctx, "no_customers_allow_paths", []) for x in (p, p + "/", p.rstrip("/")))


def text_without(ctx, drop):
    """The page's body text with every element for which drop(element, in_chrome) is true cut out (on a private copy of the tree)."""
    from techseo.dom import parse
    root = parse(ctx.need_html())
    for n in list(root.iter()):
        if getattr(n, "children", None):
            n.children = [c for c in n.children if isinstance(c, str) or not drop(c)]
    return domx.text(domx.body(root))


def page_text_without_own_name(ctx):
    """The page's text without its H1, nav and breadcrumb, where a case-study page names itself (customer names are still caught elsewhere)."""
    return text_without(ctx, lambda n: n.tag in ("h1", "nav") or domx.has_cls(n, r".*crumb.*") or "breadcrumb" in (n.get("aria-label") or "").lower()
                        or section_link(n))


def section_link(n) -> bool:
    """An internal link whose words name a site section: in the site's nav, header or footer, any short internal link; elsewhere
    a link whose words are the section's own address (text "Case Studies" to /case-studies/). Such a label is no customer claim."""
    if n.tag != "a":
        return False
    href = (n.get("href") or "").strip()
    if not href.startswith("/") or href.startswith("//"):
        return False
    label = domx.text(n)
    if not label or len(label.split()) > 4:
        return False
    if domx.in_chrome(n):
        return True
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
    path = "/" + href.split("#")[0].split("?")[0].strip("/").lower()
    return bool(slug) and (slug in path or path.rsplit("/", 1)[-1] in slug and path != "/")


def allow_path(ctx, glob) -> bool:
    """Does this page's path fit a words.never_claims_allow glob ("*/companies/")? Tried with and without the trailing slash."""
    from fnmatch import fnmatch
    p = paths.normalize(ctx.path or "/")
    return any(fnmatch(x, glob) for x in (p, p + "/", p.rstrip("/")))


def product(ctx):
    return ctx.cfg.get("product") or ctx.cfg.get("name") or "the business"


def page_text(ctx):
    return domx.text(domx.body(ctx.root()))


def unquoted_text(ctx):
    """The page's text without anything inside <blockquote> or <q> (and so its <p> and <cite> children): a client's own words,
    which we never edit. Style checks (hype, banned offer words, spelling) read this; words.never-claim and the claims read page_text."""
    if "unquoted" not in ctx.cache:
        from techseo.dom import parse
        root = parse(ctx.need_html())
        for n in list(root.iter()):
            if getattr(n, "children", None):
                n.children = [c for c in n.children if isinstance(c, str) or c.tag not in ("blockquote", "q")]
        ctx.cache["unquoted"] = domx.text(domx.body(root))
    return ctx.cache["unquoted"]


def ctx_window(t, m, before=70, after=50):
    return short(t[max(0, m.start() - before):m.end() + after], 140)


def word_hits(t, pattern):
    return [ctx_window(t, m) for m in re.finditer(r"(?i)(?<![\w-])" + pattern + r"(?![\w-])", t)]


def cta_texts(ctx):
    """Every call-to-action text: booking link labels, button labels, the sticky bar, dialogs, reason lines."""
    root = ctx.root()
    out = [domx.label(a) for a in domx.booking_links(ctx, root)]
    out += [domx.text(b) for b in find_all(root, "button")]
    for n in root.iter():
        if n.tag == "dialog" or domx.has_cls(n, r"sticky-cta|.*cta-reason|.*-reason"):
            out.append(domx.text(n))
    return [t for t in out if t]


@check("words.banned", "36", what="none of the business's banned offer words (growth.json words.banned_offer) and no old brand words", needs="live")
def banned(ctx):
    banned_offer = wcfg(ctx, "banned_offer", [])
    old = ctx.cfg.get("old_brand_words")
    if not banned_offer and not old and not wcfg(ctx, "free_banned") and not wcfg(ctx, "demo_banned"):
        raise Skip("no banned offer words in growth.json (words.banned_offer, words.free_banned, old_brand_words)")
    t = unquoted_text(ctx)
    for tb in find_all(ctx.root(), "table"):          # a comparison whose caption names a free tool prices THAT tool
        cap = find(tb, "caption")
        if cap is not None and re.search(r"(?i)\bfree\b(\s+\w+){0,2}\s+(planners?|tools?|apps?)\b", domx.text(cap)):
            t = t.replace(domx.text(tb), " ")
    probs = []
    for p in banned_offer:
        probs += [f"'{h}'" for h in word_hits(t, p)]
    if wcfg(ctx, "free_banned"):
        for m in re.finditer(r"(?i)\bfree\b", t):
            nxt = {w.lower().strip(".,;:?!") for w in t[m.end():m.end() + 40].split()[:4]}
            if not nxt & FREE_OK_NEXT:
                probs.append(f"'free' in '{ctx_window(t, m)}'")
    if wcfg(ctx, "demo_banned"):
        for m in re.finditer(r"(?i)\bdemo(nstration)?s?\b", t):
            prev = {w.lower().strip(".,;:") for w in t[max(0, m.start() - 45):m.start()].split()[-5:]}
            if not prev & NEGATIONS:
                probs.append(f"'demo' in '{ctx_window(t, m)}'")
    if old:
        probs += [f"old brand word '{h}'" for h in word_hits(t, f"({old})")]
    ctx.verdict(probs, "no banned offer words and no old brand words",
                "reword with the offer's real words (BRAND.md; growth.json words.banned_offer lists what is banned) (rule 36)")


@check("words.cta-banned", "32a", what="CTA labels, reason lines, sticky bar and dialogs never use a banned offer word (growth.json words.banned_cta)", needs="live")
def cta_banned(ctx):
    pats = wcfg(ctx, "banned_cta", [])
    if not pats:
        raise Skip("no banned CTA words in growth.json (words.banned_cta)")
    probs = []
    for s in cta_texts(ctx):
        for p in pats:
            for m in re.finditer(r"(?i)\b(" + p + r")\b", s):
                probs.append(f"'{m.group(1).lower()}' in '{short(s, 70)}'")
    ctx.verdict(sorted(set(probs)), "no CTA text uses a banned offer word",
                "rewrite the CTA text from the offer's real words (rules 32a, 35b, 36)")


@check("words.hype", "29", what="no hype words (BRAND voice)", needs="live")
def hype(ctx):
    t = unquoted_text(ctx)
    probs = [f"'{h}'" for p in wcfg(ctx, "hype", HYPE) for h in word_hits(t, p)]
    ctx.verdict(probs, "no hype words", "use plain words (BRAND.md voice): name the unit, the place, the problem")


def implied_allow(ctx):
    """([(pattern, why)], problems): growth.json words.implied_proof_allow, the implied-proof wording the owner approved for
    this site (logged in BRAND.md). "pattern" is one of the IMPLIED_PROOF patterns or a regex for the matched words; "why" is
    required. Customer names stay banned (words.hidden_customers), so an allowed "trusted by" never covers a hidden name."""
    allow, probs = [], []
    for e in wcfg(ctx, "implied_proof_allow", []) or []:
        pat = (e.get("pattern") or "").strip() if isinstance(e, dict) else ""
        why = (e.get("why") or "").strip() if isinstance(e, dict) else ""
        if not pat or not why:
            probs.append(f"growth.json words.implied_proof_allow entry {e!r} needs a 'pattern' and a 'why' (the reason, in words)")
        else:
            allow.append((pat, why))
    return allow, probs


@check("words.no-customers", "2", what="no hidden case-study customers, 'trusted by' or implied customer lists (BRAND proof rules)", needs="live")
def no_customers(ctx):
    sitemap = "sitemap" in (ctx.path or "").lower()      # a sitemap page headlines each section by its name
    t = text_without(ctx, lambda n: section_link(n) or (sitemap and re.fullmatch(r"h[2-6]", n.tag or "") and len(domx.text(n).split()) <= 4))
    own = page_text_without_own_name(ctx) if case_study_page(ctx) else t
    allow, probs = implied_allow(ctx)
    for p in IMPLIED_PROOF:
        for m in re.finditer(r"(?i)(?<![\w-])" + p + r"(?![\w-])", own if p == CASE_STUDY else t):
            if not any(a == p or re.search(a, m.group(0), re.I) for a, _ in allow):
                probs.append(f"'{ctx_window(own if p == CASE_STUDY else t, m)}'")
    probs += [f"'{h}'" for p in wcfg(ctx, "hidden_customers", []) for h in word_hits(t, p)]       # customer names are never allowed
    rated = [a for a, _ in allow if re.search(a, "aggregateRating", re.I) or re.fullmatch(a, "review", re.I)]            # a separate allow, as before it was always a FAIL
    for n in domx.jsonld(ctx.root()):
        for x in domx.walk_json(n):
            if any(k in x for k in ("aggregateRating", "review")) and not rated:
                probs.append("structured data carries a rating or review")
    ctx.verdict(probs, "no customer names, ratings or 'trusted by' claims",
                "remove it, or add the customer to BRAND.md (permission log) with the owner's yes first")


@check("words.no-price", "1", what="no price or plan amount on the page when the business does not publish prices (growth.json words.no_price)", needs="live")
def no_price(ctx):
    if not wcfg(ctx, "no_price"):
        raise Skip("this business may show prices (growth.json words.no_price is off)")
    t = page_text(ctx)
    probs = [f"'{h}'" for h in word_hits(t, r"\$\s?\d[\d,.]*\s*(k|/mo|/month|per month|a month|/yr|per year)?")]
    probs += [f"'{h}'" for h in word_hits(t, r"\d+\s?% off")]
    ctx.verdict(probs, "no prices, plan amounts or discounts",
                "say how pricing works in words (BRAND.md pricing line), without an amount")


@check("words.never-claim", "3", what="none of the claims the business never makes (growth.json words.never_claims)", needs="live")
def never_claim(ctx):
    pats = wcfg(ctx, "never_claims", [])
    if not pats:
        raise Skip("no never-claims in growth.json (words.never_claims)")
    t = page_text(ctx)
    allow = [a for a in wcfg(ctx, "never_claims_allow", []) if isinstance(a, dict) and a.get("pattern") and a.get("paths") and a.get("why")]
    probs, allowed = [], []
    for p in pats:
        for h in word_hits(t, p):
            why = next((a["why"] for a in allow if allow_path(ctx, a["paths"]) and re.search(a["pattern"], h, re.I)), None)
            (allowed.append(f"'{h}' ({why})") if why else probs.append(f"'{h}'"))
    if allowed and not probs:
        ctx.warn(f"{len(allowed)} never-claim match(es) allowed on this page by words.never_claims_allow: " + "; ".join(allowed[:4]),
                 "keep the wording exactly as the third party states it; the owner reviews the allow entry's reason")
        return
    ctx.verdict(probs, "none of BRAND.md's never-claims", "remove the claim or get the owner's yes into BRAND.md first (rule 3)")


@check("words.placeholders", "11", what="no TODO, FIXME, XXX, lorem, {{field}}, [Your ...], undefined, NaN or old year in the title", needs="live")
def placeholders(ctx):
    t = page_text(ctx)
    pats = [r"TODO", r"FIXME", r"XXX", r"lorem( ipsum)?", r"\{\{[^}]*\}\}", r"\[your [^\]]*\]", r"undefined", r"NaN",
            r"\[object Object\]"]
    probs = [f"'{h}'" for p in pats for h in [ctx_window(t, m) for m in re.finditer(p, t)]]
    title = find(ctx.root(), "title")
    tt = domx.text(title) if title is not None else ""
    for y in re.findall(r"\b(20\d\d)\b", tt):
        if int(y) < ctx.today.year:
            probs.append(f"old year {y} in the title")
    ctx.verdict(probs, "no placeholder text or leftovers", "replace the placeholder with the real text (rule 11)")


@check("words.call-length", "4", what="every mention of the call's length says the same number of minutes (growth.json words.call_minutes)", needs="live")
def call_length(ctx):
    want = wcfg(ctx, "call_minutes")
    if not want:
        raise Skip("no call length in growth.json (words.call_minutes)")
    words = wcfg(ctx, "call_words", "call|zoom|intro|visit|meeting")
    t = page_text(ctx)
    probs = []
    for m in re.finditer(r"(?i)\b" + NUM + r"[- ]minutes?\b", t):
        tail = t[m.end():m.end() + 45]
        if not re.search(r"(?i)\b(" + words + r")\b", tail.split(".")[0]):
            continue
        if m.group(1).lower() not in (str(want), NUMWORDS.get(int(want), "")):
            probs.append(f"'{ctx_window(t, m)}'")
    ctx.verdict(probs, f"the call is always {want} minutes", f"say '{want}-minute call' (rule 4; BRAND.md)")


@check("words.us-spelling", "93", what="the chosen spelling (en-US, en-CA or en-GB, per path) in the title, description, alt text and body", needs="live")
def us_spelling(ctx):
    loc, why = spelling.choose(ctx.cfg, ctx.need_path(), ctx.html)
    if loc is None:
        raise Skip(why)
    root = ctx.root()
    parts = [unquoted_text(ctx)] + [i.get("alt") for i in find_all(root, "img")]
    parts += [m.get("content") for m in find_all(root, "meta") if m.get("name") in ("description",)]
    t = " ".join(parts)
    probs = spelling.problems(t, loc, spelling.allowlist(ctx.cfg, ctx.project))
    ctx.verdict(probs, f"{loc} spelling throughout ({why})",
                f"change to the {loc} spelling shown, or add a reviewed brand or trade word to growth.json spelling_allow (rule 93)")


@check("words.review-promise", "14", what="a title that promises reviews, ratings or quotes shows them", needs="live")
def review_promise(ctx):
    root = ctx.root()
    head = " ".join(domx.text(n) for n in (domx.page_title(root), find(root, "h1")) if n is not None)
    if not head:
        ctx.fail("no title or H1 to read", "give the page a <title> and one H1 (rules 83, 84)")
        return
    if re.search(r"(?i)\b(reviews?|ratings?|testimonials?|quotes from)\b", head):
        q = find_all(domx.main(root), "blockquote") + find_all(domx.main(root), "q")
        if not q:
            ctx.fail(f"title/H1 '{short(head, 80)}' promises reviews but the page quotes none",
                     "quote the reviews with their source, or drop the promise from the title (rule 14)")
            return
    ctx.ok("the title promises nothing the page cannot show")


@check("words.disclosure", "16", types=("post", "hub", "money"), what="a review or comparison says who we are before the comparison", needs="live")
def disclosure(ctx):
    root = ctx.root()
    h1 = find(root, "h1")
    if h1 is None:
        ctx.fail("no H1", "add one H1 (rule 84)")
        return
    head = domx.text(h1) + " " + domx.text(domx.page_title(root))
    if not re.search(r"(?i)\b(vs\.?|versus|best|review|compare|comparison|alternatives?)\b", head):
        ctx.ok("not a review or comparison page")
        return
    m = domx.main(root)
    first = " ".join(domx.text(p) for p in find_all(m, "p")[:4])
    if design.find(ctx, "disclosure"):                 # growth.json disclosure_pattern (a partner, reseller ...)
        ctx.ok("the disclosure line (growth.json disclosure_pattern) comes before the comparison")
    elif re.search(r"(?i)\b(we (make|build|sell)|" + re.escape(product(ctx)) + r" (makes|is|sells)|our (own )?product)\b", first):
        ctx.ok("the disclosure line comes before the comparison")
    else:
        ctx.fail("a review/comparison page does not say who we are in its first paragraphs",
                 f"add one plain line under the byline: 'We make {product(ctx)}, one of the tools below.' (rule 16)")


@check("words.question-title", "20", what="when the H1 is a question, the first line answers it", needs="live")
def question_title(ctx):
    root = ctx.root()
    h1 = find(root, "h1")
    if h1 is None:
        ctx.fail("no H1", "add one H1 (rule 84)")
        return
    if not domx.text(h1).rstrip().endswith("?"):
        ctx.ok("the H1 is not a question")
        return
    sec = domx.first_section(root)
    # the first line under the H1: a byline, breadcrumb, kicker or reading-time line is not that line (2.4.9)
    meta = re.compile(r"(?i)byline|author|posted|published|updated|post-meta|entry-meta|breadcrumb|kicker|eyebrow|read-?time|reading-?time|\btoc\b")
    order = list(sec.iter()) if sec is not None else []
    after = order.index(h1) if h1 in order else 0
    ps = [domx.text(p) for p in order[after:] if p.tag == "p"
          and not any(meta.search((a.get("class") or "") + " " + (a.get("id") or "")) or a.tag in ("nav", "time", "address")
                      for a in [p, *p.ancestors()])]
    ps = [p for p in ps if len(p.split()) > 4]
    if ps and re.match(r"(?i)(yes|no|it depends|only|not)\b", ps[0]):
        ctx.ok("the first line answers the question")
    else:
        ctx.fail("the H1 is a question but the first line does not start with the answer",
                 "start the first line with yes, no, or 'yes, but only this way' (rule 20)")


@check("words.no-location", "36k", what="no country or city for the business or its people, on the page or (Next.js) in the site's own code (growth.json never_say_location)", needs="live")
def no_location(ctx):
    """A business that must not name where it is (growth.json never_say_location, with never_say_location_why).
    Blog posts may quote a competitor's own reach, so on a post only the site's chrome (header, footer, byline, dialogs)
    is read; every other page is read whole. On the Next.js adapter the site's own code is scanned too, except lines
    that name the build clock's time zone (growth.json timezone)."""
    pat = ctx.cfg.get("never_say_location")
    if not pat:
        raise Skip("no places to avoid in growth.json (never_say_location)")
    probs = []
    root = ctx.root()
    if ctx.ptype == "post":
        parts = [n for n in root.iter() if n.tag in ("header", "footer", "dialog") or domx.has_cls(n, r".*byline.*")]
        t = " ".join(domx.text(n) for n in parts)
    else:
        t = page_text(ctx)
    probs += [f"page: '{h}'" for h in word_hits(t, f"({pat})")]
    if ctx.stack() == "nextjs" and ctx.repo and (ctx.repo / ".git").exists():
        tz = ctx.cfg.get("timezone", "")
        for p in ctx.repo_files():
            if ".test." in p.name:
                continue
            for i, line in enumerate(p.read_text(errors="replace").splitlines(), 1):
                if re.search(r"(?i)(?<![\w-])(" + pat + r")(?![\w-])", line) and not (tz and tz in line):
                    probs.append(f"{p.relative_to(ctx.repo)}:{i}")
    ctx.verdict(probs, f"no place named for {product(ctx)} or its people",
                f"remove it: the site never says where {product(ctx)} or its people are ({ctx.cfg.get('never_say_location_why', 'growth.json never_say_location_why')}) (rule 36k)")


@check("words.named-author", "36l", what="a named byline linking to the one author page, and the same Person as author in the structured data (E-E-A-T)", needs="live")
def named_author(ctx):
    """Every page links to one named author (growth.json default_author: name, role, path, slug), never "by the <product> team"."""
    a = ctx.cfg.get("default_author") or {}
    if not a.get("path"):
        raise Skip("no default author in growth.json (default_author)")
    if a.get("types") and ctx.ptype not in a["types"]:     # e.g. ["post"]: service pages carry the Organization instead
        raise Skip(f"named author is required on {', '.join(a['types'])} pages only (growth.json default_author.types)")
    if paths.key(ctx.need_path()) == paths.key(a["path"]):
        ctx.ok("this is the author page itself")
        return
    root, probs = ctx.root(), []
    links = [x for x in design.find(ctx, "byline") if a["name"].split()[0].lower() in domx.text(x).lower()]
    if not links:
        probs.append(f"no byline link '{a['name']}' to {a['path']}")
    t = page_text(ctx)
    probs += [f"team byline: '{h}'" for h in word_hits(t, r"by (the )?" + re.escape(product(ctx)) + r" team")]
    authors = [x.get("author") for n in domx.jsonld(root) for x in domx.walk_json(n) if x.get("author")]
    flat = json.dumps(authors)
    if not authors:
        probs.append("no author in the structured data")
    elif a["slug"] not in flat:
        probs.append(f"structured-data author is not {a['name']} ({short(flat, 80)})")
    ctx.verdict(probs, f"byline links to {a['path']} and the structured data names {a['name']} as author",
                "link the byline to the author page and set the page's author to that Person in the structured data (rule 36l)")
