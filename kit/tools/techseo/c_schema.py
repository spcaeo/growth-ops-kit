"""Structured data (SCH): JSON-LD and microdata."""
from __future__ import annotations

import re
import urllib.parse

from .dom import SKIP_TEXT, find_all

# Required (R) and recommended (r) properties. A tuple means "one of these".
# Source: the SEO Pro extension's types.js (1 = required, 2 = recommended) plus Google's
# structured-data docs for Organization, WebSite, WebPage, Article, SoftwareApplication, FAQ.
REQ = {
    "Organization": (["name", "url"], ["logo", "sameAs", "contactPoint"]),
    "WebSite": (["url"], ["name", "potentialAction"]),
    "WebPage": (["name", "url"], ["description", "isPartOf", "datePublished", "dateModified"]),
    "Article": (["headline", "image", "datePublished", "author"], ["dateModified", "publisher"]),
    "BlogPosting": (["headline", "image", "datePublished", "author"], ["dateModified", "publisher"]),
    "SoftwareApplication": (["name", "applicationCategory", "operatingSystem"], ["offers", "aggregateRating", "review"]),
    "Product": (["name", "image"], ["offers", "aggregateRating", "review"]),
    "FAQPage": (["mainEntity"], []),
    "Question": (["name", "acceptedAnswer"], []),
    "Answer": (["text"], []),
    "BreadcrumbList": (["itemListElement"], []),
    "ListItem": (["position", "name"], ["item"]),
    "HowTo": (["name", "step"], ["description"]),
    "ItemList": (["itemListElement"], []),
    "LocalBusiness": (["name", "address"], ["geo", "aggregateRating"]),
    "Review": (["author", "itemReviewed", "reviewRating"], ["datePublished"]),
    "AggregateRating": (["ratingValue", "ratingCount|reviewCount", "itemReviewed"], ["bestRating", "worstRating"]),
    "VideoObject": (["name", "description", "thumbnailUrl", "uploadDate"], ["contentUrl", "duration"]),
    "Offer": (["price", "priceCurrency"], []),
    "Person": (["name"], []),
    "Event": (["name", "startDate", "location"], ["description", "endDate"]),
    "Course": (["name", "description"], []),
    "Dataset": (["name", "description"], []),
    "QAPage": (["mainEntity"], []),
    "HowToStep": (["text|itemListElement"], []),
    "HowToSection": (["name", "itemListElement"], []),
    "JobPosting": (["title", "description", "datePosted", "validThrough", "hiringOrganization", "jobLocation"], []),
}
EXPECT = {
    "money": [("SoftwareApplication", "Product", "Service"), ("FAQPage",), ("BreadcrumbList",)],
    "article": [("Article", "BlogPosting"), ("BreadcrumbList",)],
    "hub": [("CollectionPage", "WebPage"), ("BreadcrumbList",)],
    "other": [("WebPage", "CollectionPage", "AboutPage", "ContactPage")],
}
# Types that sit on every page (the site's Organization, WebSite, the trail, the page node): they never count as a page's
# main type, or a page with nothing but the site's own nodes would pass.
NEVER_MAIN = {"Organization", "WebSite", "BreadcrumbList", "WebPage", "ItemList", "ListItem", "FAQPage", "Question", "Answer"}
DEFAULT_MONEY = ("Product", "Service", "SoftwareApplication")


def main_types(configured):
    """The types that count as a money page's main node: growth.json schema_types.money (a "A|B" string or a list) with
    the site-wide types removed; the default is Product, Service and SoftwareApplication."""
    given = configured.split("|") if isinstance(configured, str) else list(configured or [])
    kept = [t.strip() for t in given if t.strip() and t.strip() not in NEVER_MAIN]
    return tuple(kept) or DEFAULT_MONEY


SOFT = {"money": ["Organization", "WebPage"], "article": ["Organization"], "hub": ["Organization"]}
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?)?$")


def dom_text(node):
    out = []
    def walk(n):
        if n.tag in SKIP_TEXT - {"title"}:
            return
        for c in n.children:
            walk(c) if not isinstance(c, str) else out.append(c)
    walk(node)
    return norm("".join(out))


def norm(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace(" ", " ")
    return re.sub(r"\s+", " ", s).strip().lower()


def has(node, prop):
    return any(node.get(x) not in (None, "", [], {}) for x in prop.split("|"))


def urls_in(obj, out=None):
    out = [] if out is None else out
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and v.startswith(("http://", "https://")) and k != "@context":
                out.append(v)
            else:
                urls_in(v, out)
    elif isinstance(obj, list):
        for v in obj:
            urls_in(v, out)
    return out


def run_schema(p, page_type="money", money_types=None):
    """money_types: the schema.org types that count as a money page's product or service node (growth.json schema_types.money)."""
    rep = p.rep
    scripts = p.jsonld_scripts()
    nodes, errors = p.jsonld_nodes()
    micro = len([n for n in p.root.iter() if "itemscope" in n.attrs])
    if not scripts:
        rep.fail("SCH-01", "no JSON-LD found", "add structured data (SoftwareApplication, FAQPage, BreadcrumbList)")
        return
    if errors:
        rep.fail("SCH-01", f"{len(errors)} JSON-LD block(s) do not parse: {errors[0]}", "fix the JSON (the extension shows these as 'Parsing Error')")
    else:
        rep.ok("SCH-01", f"{len(scripts)} JSON-LD block(s), all parse; {len(nodes)} node(s)")
    ctx_bad = [s for s in scripts if "schema.org" not in s.own_text()[:200]]
    notype = [n for n in nodes if not n.get("@type")]
    (rep.fail if (ctx_bad or notype) else rep.ok)("SCH-02", "a block has no schema.org @context or a node has no @type" if (ctx_bad or notype) else "every block has @context and every node has @type",
                                                   "add @context https://schema.org and @type")
    types = {t for n in nodes for t in p.types(n)}
    rep.info("SCH-02b", "types found: " + ", ".join(sorted(types)))
    # SCH-03 expected types
    expect = [main_types(money_types) if (i == 0 and page_type == "money") else g for i, g in enumerate(EXPECT.get(page_type, []))]
    missing = [" or ".join(g) for g in expect if not any(t in types for t in g)]
    (rep.fail if missing else rep.ok)("SCH-03", f"missing structured data type(s) for a {page_type} page: {', '.join(missing)}" if missing else f"expected types for a {page_type} page are present",
                                      "add the missing JSON-LD node")
    # SCH-04 required and recommended properties on every node of a known type
    miss_req, miss_rec = [], []
    nested_types = set()
    def walk(obj, path):
        if isinstance(obj, dict):
            for t in p.types(obj):
                nested_types.add(t)
                if t in REQ:
                    req, rec = REQ[t]
                    r = [x for x in req if not has(obj, x)]
                    if t == "ListItem" and obj.get("position") == obj.get("_last"):
                        r = [x for x in r if x != "item"]
                    miss_req.extend(f"{t}.{x}" for x in r)
                    if not path:  # recommended properties matter on the page's own nodes, not on nested publisher stubs
                        # a product brand with no profiles of its own is identified through its parent company's
                        # profiles (parentOrganization.sameAs); sameAs on the brand itself would claim it IS the parent
                        par = obj.get("parentOrganization") if t == "Organization" else None
                        own = lambda x: has(obj, x) or (x == "sameAs" and isinstance(par, dict) and has(par, "sameAs"))
                        miss_rec.extend(f"{t}.{x}" for x in rec if not own(x))
            for k, v in obj.items():
                walk(v, path + [k])
        elif isinstance(obj, list):
            for v in obj:
                walk(v, path)
    for n in nodes:
        walk(n, [])
    soft = [t for t in SOFT.get(page_type, []) if t not in nested_types]
    (rep.warn if soft else rep.ok)("SCH-03b", f"no {', '.join(soft)} node on the page" if soft else "Organization (or publisher) and page node present",
                                   "rule 36b: name the publisher (Organization) and rule 95: every indexable page has its page node (WebPage)")
    soft_offers = [x for x in miss_rec if x.startswith("SoftwareApplication.")]
    miss_rec = [x for x in miss_rec if not x.startswith("SoftwareApplication.")]
    if miss_req:
        rep.fail("SCH-04", "required properties missing: " + ", ".join(sorted(set(miss_req))[:8]), "add them (list from the extension's required set and Google's docs)")
    else:
        rep.ok("SCH-04", "every known node has its required properties")
    if miss_rec:
        rep.warn("SCH-04b", "recommended properties missing: " + ", ".join(sorted(set(miss_rec))[:8]), "add the ones that are true and shown on the page")
    if soft_offers and any(t == "SoftwareApplication" for t in types):
        rep.info("SCH-04c", "SoftwareApplication has no offers/aggregateRating/review. Google's rich result needs one of them; if the business quotes price on request and shows no ratings (BRAND.md) this is by design: do not invent them")
    # SCH-05 FAQ equals visible text
    page_text = dom_text(p.body)
    if not any("FAQPage" in p.types(n) for n in nodes):
        # A page with no FAQ has no markup that could differ from it; say so, so the gate has a result to read (rule 151).
        rep.ok("SCH-05", "no FAQPage markup on this page, so there is no FAQ to compare")
    for n in nodes:
        if "FAQPage" in p.types(n):
            qs = n.get("mainEntity", [])
            qs = qs if isinstance(qs, list) else [qs]
            bad, last, order_bad, seen = [], -1, False, []
            for q in qs:
                qn = norm(q.get("name", ""))
                ans = q.get("acceptedAnswer", {})
                an = norm(ans.get("text", "") if isinstance(ans, dict) else "")
                if not qn or not an:
                    bad.append(f"empty Q/A '{qn[:30]}'")
                    continue
                pos = page_text.find(qn)
                if pos < 0:
                    bad.append(f"question not shown: '{qn[:50]}'")
                elif an not in page_text:
                    bad.append(f"answer differs from the page: '{qn[:40]}'")
                if pos >= 0 and pos < last:
                    order_bad = True
                last = max(last, pos)
                words = set(qn.split())
                if any(len(words & set(s.split())) / max(len(words | set(s.split())), 1) >= 0.6 for s in seen):
                    bad.append(f"near-duplicate question '{qn[:40]}'")
                seen.append(qn)
            if bad or order_bad:
                rep.fail("SCH-05", f"FAQPage markup does not equal the page ({len(qs)} questions): " + "; ".join(bad[:3]) + ("; order differs" if order_bad else ""),
                         "make each question and answer in the markup the same words as the visible FAQ, same order")
            else:
                rep.ok("SCH-05", f"FAQPage: all {len(qs)} questions and answers match the page word for word, in order, no duplicates")
    # SCH-06 says what the page shows
    h1 = next((h.all_text() for h in p.headings() if h.tag == "h1"), "")
    canon = (p.canonicals() or [None])[0]
    cu = canon.get("href") if canon else ""
    probs = []
    for n in nodes:
        ts = p.types(n)
        if any(t in ts for t in ("WebPage", "SoftwareApplication", "Product", "Article", "BlogPosting", "CollectionPage")):
            u = n.get("url")
            if u and cu and u.rstrip("/") != cu.rstrip("/"):
                probs.append(f"{ts[0]}.url {u} != canonical")
            nm = n.get("name") or n.get("headline") or ""
            if not nm:
                probs.append(f"{ts[0]} has no name")
            if not n.get("description"):
                probs.append(f"{ts[0]} has no description")
    (rep.warn if probs else rep.ok)("SCH-06", "; ".join(probs[:3]) if probs else f"main node url equals the canonical; page H1: '{h1[:50]}'", "make url = canonical and fill name and description from the page")
    # SCH-07 breadcrumbs
    for n in nodes:
        if "BreadcrumbList" in p.types(n):
            items = n.get("itemListElement", [])
            items = items if isinstance(items, list) else [items]
            pos_ok = [i.get("position") for i in items] == list(range(1, len(items) + 1))
            no_item = [i for i in items[:-1] if not (i.get("item") if isinstance(i.get("item"), str) else (i.get("item") or {}).get("@id"))]
            last = items[-1] if items else {}
            lasturl = last.get("item") if isinstance(last.get("item"), str) else (last.get("item") or {}).get("@id", "")
            last_ok = (not lasturl) or (cu and lasturl.rstrip("/") == cu.rstrip("/"))
            crumbs = [a for a in find_all(p.root, "nav") if "breadcrumb" in a.get("aria-label").lower()]
            vis = norm(crumbs[0].all_text()) if crumbs else ""
            names_ok = all(norm(i.get("name", "")) in vis for i in items) if crumbs else None
            bad = []
            if not pos_ok:
                bad.append("positions are not 1..n")
            if no_item:
                bad.append(f"{len(no_item)} step(s) without item URL")
            if not last_ok:
                bad.append("last crumb is not the current page")
            if names_ok is False:
                bad.append("names differ from the visible breadcrumb")
            if names_ok is None:
                bad.append("no visible breadcrumb nav (aria-label='Breadcrumb') found")
            (rep.fail if bad else rep.ok)("SCH-07", "; ".join(bad) if bad else f"BreadcrumbList: {len(items)} steps, in order, last = this page, same names as the visible breadcrumb",
                                          "build markup and visible crumbs from the same data (rule 50)")
    # SCH-08 @id references resolve
    ids = {n.get("@id") for n in nodes if n.get("@id")}
    dangling = []
    def refs(o):
        if isinstance(o, dict):
            if set(o.keys()) == {"@id"} and o["@id"] not in ids:
                dangling.append(o["@id"])
            for v in o.values():
                refs(v)
        elif isinstance(o, list):
            for v in o:
                refs(v)
    for n in nodes:
        refs({k: v for k, v in n.items() if k != "@id"})
    (rep.fail if dangling else rep.ok)("SCH-08", f"@id reference(s) to nothing on the page: {dangling[:3]}" if dangling else "every @id reference points at a node on the page",
                                       "remove the reference or add the node")
    # SCH-09 hosts, SCH-10 dates
    hosts = {urllib.parse.urlsplit(u).netloc.lower() for u in urls_in(nodes)}
    foreign = sorted(h for h in hosts if (p.site_host.removeprefix("www.").split(".")[0] in h and h != p.site_host) or any(x in h for x in ("localhost", "127.0.0.1")))
    (rep.fail if foreign else rep.ok)("SCH-09", f"structured data names a wrong host: {foreign}" if foreign else f"all URLs in the structured data use {p.site_host} (or other sites we cite): {sorted(hosts)[:4]}",
                                      f"use {p.site_origin}/... only")
    baddate = []
    def dates(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("datePublished", "dateModified", "uploadDate", "startDate", "endDate", "datePosted") and isinstance(v, str) and not ISO.match(v):
                    baddate.append(f"{k}={v}")
                dates(v)
        elif isinstance(o, list):
            for v in o:
                dates(v)
    dates(nodes)
    (rep.fail if baddate else rep.ok)("SCH-10", f"dates not in ISO 8601: {baddate[:3]}" if baddate else "dates (if any) are ISO 8601", "use YYYY-MM-DD or a full ISO date-time")
    # SCH-11 ratings need visible ratings
    rated = any(t in types for t in ("AggregateRating", "Review", "Rating"))
    if rated and not re.search(r"\b\d(\.\d)?\s*(/|out of)\s*5\b|\breviews?\b", page_text):
        rep.fail("SCH-11", "ratings or reviews in the markup, none shown on the page", "remove them: markup must say only what the page shows (never invent proof)")
    else:
        rep.ok("SCH-11", "no ratings or reviews in the markup without matching visible text")
    # SCH-13 microdata
    (rep.info if micro else rep.ok)("SCH-13", f"{micro} microdata item(s) also present: keep them consistent with the JSON-LD" if micro else "JSON-LD only (no microdata mixed in)")
    # SCH-14 first-node rule (a Next.js client-side navigation scrolls to a leading <script>, so JSON-LD goes in a block)
    main_kids = p.main.elements()
    first = main_kids[0] if main_kids else None
    bad = []
    if first is not None and first.tag in ("script", "style", "link", "template", "noscript"):
        bad.append(f"the page's first node is <{first.tag}>")
    for s in scripts:
        par = s.parent
        if par is None or par.tag in ("main", "body", "html"):
            bad.append("a JSON-LD script sits directly in <main>/<body>")
        elif par.tag == "div" and any(c.tag != "script" for c in par.elements()):
            bad.append("a JSON-LD script shares its <div> with other elements (use an empty block <div>)")
    (rep.fail if bad else rep.ok)("SCH-14", "; ".join(sorted(set(bad))) if bad else "JSON-LD sits inside an empty block <div>, never the page's first node",
                                  "wrap it: <div><script type='application/ld+json'>...</script></div> in the shared JsonLd component")
    # SCH-15 duplicate nodes
    dup = [t for t in ("Organization", "WebSite") if sum(1 for n in nodes if t in p.types(n)) > 1]
    (rep.warn if dup else rep.ok)("SCH-15", f"more than one {', '.join(dup)} node on the page" if dup else "no duplicate Organization or WebSite nodes", "one per page, same data site-wide")
