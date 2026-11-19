"""Links (LNK) and in-page anchors."""
from __future__ import annotations

import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor


GENERIC = {"click here", "here", "read more", "learn more", "more", "this", "this page", "link", "details", "click", "view", "go", "continue"}
CHROME = ("header", "nav", "footer")


def accessible_name(a):
    t = a.all_text()
    if t:
        return t
    if a.get("aria-label").strip():
        return a.get("aria-label").strip()
    for n in a.iter():
        if n.tag == "img" and n.get("alt").strip():
            return n.get("alt").strip()
        if n.tag == "title" and n.all_text():
            return n.all_text()
    return a.get("title").strip()


def run_links(p, max_links=80, check_status=True, migration=None):
    rep = p.rep
    anchors = p.links()
    withhref = [a for a in anchors if "href" in a.attrs]
    nohref = [a for a in anchors if "href" not in a.attrs and not a.get("id") and not a.get("name")]
    internal, external, other = [], [], []
    for a in withhref:
        h = a.get("href").strip()
        if h.startswith(("mailto:", "tel:", "sms:")):
            other.append(a)
        elif h.startswith("#") or h in ("", "javascript:void(0)") or h.lower().startswith("javascript:"):
            other.append(a)
        elif p.is_internal(h):
            internal.append(a)
        else:
            external.append(a)
    uniq = {p.abs(a.get("href")).split("#")[0] for a in internal + external}
    rep.info("LNK-01", f"{len(anchors)} links: {len(internal)} internal, {len(external)} external, {len(other)} other "
             f"(# / mailto / tel); {len(uniq)} unique targets")
    # LNK-06 placeholder or missing href
    bad = [a for a in withhref if a.get("href").strip() in ("", "#", "#!") or a.get("href").lower().startswith("javascript:")]
    if bad or nohref:
        rep.fail("LNK-06", f"{len(bad)} link(s) with an empty or placeholder href, {len(nohref)} <a> without href "
                 f"(first: '{(bad or nohref)[0].all_text()[:40]}')", "every <a> needs a real href; use <button> for actions")
    else:
        rep.ok("LNK-06", "no placeholder or missing hrefs")
    # LNK-03 / LNK-04 anchor text
    empty = [a for a in withhref if not accessible_name(a)]
    if empty:
        rep.fail("LNK-03", f"{len(empty)} link(s) with no readable name, first href: {empty[0].get('href')}",
                 "add visible text or an aria-label naming the target")
    else:
        rep.ok("LNK-03", "every link has a name (text, aria-label or image alt)")
    gen = [a for a in withhref if accessible_name(a).strip().lower().rstrip(".→ ") in GENERIC]
    if gen:
        rep.warn("LNK-04", f"{len(gen)} generic link text, e.g. '{accessible_name(gen[0])}' -> {gen[0].get('href')}",
                 "name what the reader gets, e.g. 'See how we price a lawn'")
    else:
        rep.ok("LNK-04", "no 'click here' / 'read more' style anchors")
    # LNK-05 utm on internal, LNK-13 nofollow internal
    utm = [a for a in internal if re.search(r"[?&]utm_", a.get("href"))]
    (rep.fail if utm else rep.ok)("LNK-05", f"{len(utm)} internal link(s) carry utm_ (first: {utm[0].get('href')})" if utm else "no utm_ on internal links",
                                  "name the call to action with a data attribute, not a utm_ parameter")
    nf = [a for a in internal if "nofollow" in a.get("rel").lower()]
    (rep.warn if nf else rep.ok)("LNK-13", f"{len(nf)} internal link(s) marked nofollow" if nf else "no internal nofollow",
                                 "internal links should pass link value; remove nofollow")
    # LNK-07 external rel
    nb = [a for a in external if a.get("target") == "_blank" and "noopener" not in a.get("rel").lower() and "noreferrer" not in a.get("rel").lower()]
    hosts = sorted({urllib.parse.urlsplit(a.get("href")).netloc for a in external})
    if nb:
        rep.warn("LNK-07", f"{len(nb)} external link(s) open a new tab without rel=noopener (first: {nb[0].get('href')})", "add rel='noopener'")
    else:
        rep.ok("LNK-07", f"external links safe; hosts: {', '.join(hosts[:8]) or 'none'}")
    unfollowed = [a for a in external if not re.search(r"nofollow|sponsored|ugc", a.get("rel").lower())]
    if unfollowed:
        rep.info("LNK-07b", f"{len(unfollowed)} external link(s) pass link value; check each is one we vouch for ({', '.join(sorted({urllib.parse.urlsplit(a.get('href')).netloc for a in unfollowed})[:5])})")
    # LNK-08 old hosts, http
    host = re.escape(p.site_host.removeprefix("www."))
    retired = [h for h in p.old_hosts if h]
    # the non-canonical twin: the bare host when the site lives on www., the www. host when it does not. A full link
    # to the canonical host itself is fine (a copy/open URL component prints it on purpose; friction 50).
    twin = host if p.site_host.startswith("www.") else rf"www\.{host}"
    old = [a for a in withhref if re.search(rf"^http://(www\.)?{host}(?=[/:?#]|$)|^https?://{twin}(?=[/:?#]|$)", a.get("href"))
           or any(h in a.get("href").lower() for h in retired)]
    (rep.fail if old else rep.ok)("LNK-08", f"{len(old)} link(s) to an old or non-canonical host (first: {old[0].get('href')})" if old else "no links to retired or non-canonical hosts",
                                  f"link to {p.site_origin}/... or a relative path")
    # LNK-09 contextual internal links inside <main> but outside header/nav/footer
    ctx = [a for a in internal if a.in_tag("main") and not a.in_tag(*CHROME)]
    (rep.ok if len(ctx) >= 3 else rep.warn)("LNK-09", f"{len(ctx)} contextual internal link(s) inside the main copy",
                                            "link up to the hub and across to 2 or 3 related pages (rule 89)")
    # LNK-10 same anchor, different targets
    by_anchor = {}
    for a in internal:
        k = accessible_name(a).strip().lower()
        if k:
            by_anchor.setdefault(k, set()).add(p.site_path(a.get("href")).rstrip("/") or "/")
    amb = {k: v for k, v in by_anchor.items() if len(v) > 1 and k not in GENERIC and len(k) > 3}
    (rep.warn if amb else rep.ok)("LNK-10", f"same anchor text to different pages: {list(amb)[:3]}" if amb else "no anchor text points at two different pages",
                                  "give each target its own words")
    # LNK-12 in-page anchors resolve
    ids = {n.get("id") for n in p.root.iter() if n.get("id")} | {n.get("name") for n in p.root.iter() if n.tag == "a" and n.get("name")}
    miss = sorted({a.get("href")[1:] for a in withhref if a.get("href").startswith("#") and len(a.get("href")) > 1 and urllib.parse.unquote(a.get("href")[1:]) not in ids})
    (rep.fail if miss else rep.ok)("LNK-12", f"in-page link(s) with no matching id: {miss[:4]}" if miss else "every #anchor lands on an id", "add the id or fix the link")
    # LNK-02 status of internal targets
    if not check_status:
        rep.skip("LNK-02", "link status check switched off (--no-link-status)")
        return
    if p.f.allow_live:
        rep.skip("LNK-02", "live site: links are not fetched (only the page, robots.txt and sitemap.xml)")
        return
    all_targets = sorted({p.abs(a.get("href")).split("#")[0] for a in internal})
    targets = all_targets[:max_links]
    def probe(u):
        r = p.f.head_or_get(u)
        return u, p.f.settle(u, r)
    with ThreadPoolExecutor(max_workers=3) as ex:
        res = list(ex.map(probe, targets))
    redirects = [(u, r) for u, r in res if 300 <= r.status < 400]
    broken = [(u, r) for u, r in res if r.status >= 400 or r.status == 0]
    if migration:       # "not migrated yet": a 404 to a page the old live site has (its inventory) is a WARN, not a FAIL
        import paths
        parked = [(u, r) for u, r in broken if r.status == 404 and paths.normalize(urllib.parse.urlsplit(u).path) in migration["paths"]]
        broken = [x for x in broken if x not in parked]
        if parked:
            rep.warn("LNK-02", f"{len(parked)} internal link(s) go to pages not migrated yet (migration task {migration['task']}): "
                     + "; ".join(urllib.parse.urlsplit(u).path for u, r in parked[:5]),
                     f"they are in the live site's inventory; they stop being a warning when task {migration['task']} moves them, or turn migration off in growth.json")
    if broken:
        rep.fail("LNK-02", f"{len(broken)} internal link(s) broken: " + "; ".join(f"{urllib.parse.urlsplit(u).path} -> {r.status or r.error[:30]}" for u, r in broken[:5]),
                 "fix or remove each link")
    if redirects:
        rep.warn("LNK-02", f"{len(redirects)} internal link(s) go through a redirect: " + "; ".join(f"{urllib.parse.urlsplit(u).path} -> {r.status} {r.h('location')}" for u, r in redirects[:5]),
                 "point the link at the final address")
    if not broken and not redirects and not (migration and parked):
        rep.ok("LNK-02", f"all {len(res)} unique internal targets answer 200 ({len(res)} of {len(all_targets)} unique internal targets checked"
                         + ("; raise growth.json link_check_cap to check the rest" if len(res) < len(all_targets) else "") + ")")
