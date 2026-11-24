"""International sites (rule 162): a site with two or more locales (growth.json market.locales) tells Google which copy is for
whom, the way Google asks. Each check runs only when the project has 2+ locales (else "SKIP: one locale"), and reads the built
page; the copies of the page and the sitemap are read from the same preview address, never from the live site.

Google's guidance behind it: Search Central "Tell Google about localized versions of your page" (hreflang: a self-reference,
every version listed, absolute addresses, x-default, tags that point at each other) and "Managing multi-regional and
multilingual sites" (a separate address per language, no automatic redirect by the visitor's language, a canonical per copy).

  intl.lang              <html lang> equals the page's locale
  intl.copies            every other locale's copy of the page exists (a missing one is "missing translation", never a wrong tag)
  intl.hreflang          a self-reference, one tag per existing copy, absolute, pointing at the same page's copy, answered by a tag
                         back, and x-default on the primary locale's address
  intl.canonical         the canonical is the page itself, never another language's copy
  intl.no-auto-redirect  no script or meta refresh moves the visitor by language (a suggestion banner is fine)
  intl.sitemap           when the build has a sitemap, it lists xhtml:link alternates for the page

Settings (growth.json market): "missing_copy": "warn" (default) or "fail": whether a copy that does not exist yet is a WARN (the
page can still be READY while its copies are written: the board's localize jobs need the READY page) or a FAIL.
Tests give ctx.cache["intl_fetch"] (url -> (status, html)) and ctx.cache["intl_probe"] (url, accept_language -> status).
"""
from __future__ import annotations

import re
import urllib.error
import urllib.parse
import urllib.request
from xml.etree import ElementTree as ET

import locales
from techseo.dom import find, find_all, parse

from .core import ALL, Missing, Skip, check, short

GUIDE_TELL = "Google Search Central, 'Tell Google about localized versions of your page'"
GUIDE_MULTI = "Google Search Central, 'Managing multi-regional and multilingual sites'"
HREFLANG = re.compile(r"^(?:x-default|[A-Za-z]{2,3}(?:-[A-Za-z]{4})?(?:-(?:[A-Za-z]{2}|\d{3}))?)$")
READS_LANGUAGE = re.compile(r"navigator\s*\.\s*(?:languages?|userLanguage|browserLanguage|systemLanguage)\b|accept-language", re.I)
MOVES_VISITOR = re.compile(r"\blocation\s*(?:\.\s*(?:href|pathname)\s*)?=(?!=)|\blocation\s*\.\s*(?:replace|assign)\s*\(")
DATA_SCRIPTS = ("application/ld+json", "application/json", "importmap", "speculationrules")
PROBE_LIMIT = 3


# ---- what the page and the project say -------------------------------------------------------------------------------------
class Page:
    """What every intl check needs, built once per gate run: the locales, this page's locale, its path in the primary locale."""

    def __init__(self, ctx):
        try:
            self.locs = locales.from_cfg(ctx.cfg)
        except locales.LocaleError as e:
            raise Missing("a usable growth.json market.locales", str(e))
        if len(self.locs) < 2:
            raise Skip("this project has one locale (growth.json market.locales lists fewer than two): nothing to cross-link")
        self.path = "/" + (ctx.need_path() or "/").lstrip("/")
        self.loc, self.base = locales.locale_of_path(self.locs, self.path)
        u = urllib.parse.urlsplit(ctx.url or "")
        self.origin = f"{u.scheme}://{u.netloc}" if u.netloc else ""
        site = urllib.parse.urlsplit(ctx.site_origin()).netloc.lower().removeprefix("www.")
        self.hosts = {h for h in (u.netloc.lower(), site, "www." + site if site else "") if h}
        self.site = ctx.site_origin() or self.origin
        self.strict = str((ctx.cfg.get("market") or {}).get("missing_copy") or "warn").lower() == "fail"

    def path_of(self, loc) -> str:
        return locales.path_in(loc, self.base)

    def others(self):
        return [e for e in self.locs if e is not self.loc and e["locale"] != self.loc["locale"]]


def page(ctx) -> Page:
    if "intl" not in ctx.cache:
        ctx.cache["intl"] = Page(ctx)
    return ctx.cache["intl"]


def npath(value) -> str:
    """A path or an address as one comparable path: no query, no hash, no trailing slash (the root stays /)."""
    p = urllib.parse.urlsplit(str(value or "")).path or "/"
    return "/" + p.strip("/") if p.strip("/") else "/"


def absolute(href) -> bool:
    u = urllib.parse.urlsplit(str(href or ""))
    return u.scheme in ("http", "https") and bool(u.netloc)


def host_ok(pg: Page, href) -> bool:
    return urllib.parse.urlsplit(str(href or "")).netloc.lower() in pg.hosts


def alternates(root) -> list:
    """[(hreflang, href)] of every <link rel="alternate" hreflang=...> in the page."""
    return [(l.get("hreflang").strip(), l.get("href").strip()) for l in find_all(root, "link")
            if "alternate" in l.get("rel").lower().split() and l.get("hreflang").strip()]


def fetch(ctx, url):
    """(status, html) of a page from the preview; follows redirects; (0, "") when it cannot be read. Kept per run."""
    seen = ctx.cache.setdefault("intl_pages", {})
    if url not in seen:
        f = ctx.cache.get("intl_fetch")
        if f:
            seen[url] = f(url)
        else:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "GrowthGate/1.0 (read-only)"})
                with urllib.request.urlopen(req, timeout=20) as r:
                    seen[url] = (r.status, r.read(3_000_000).decode("utf-8", errors="replace"))
            except urllib.error.HTTPError as e:
                seen[url] = (e.code, "")
            except Exception:  # noqa: BLE001
                seen[url] = (0, "")
    return seen[url]


def copies(ctx, pg: Page) -> dict:
    """{locale tag: {"url", "status", "root"}} for every other locale: the copy of this page read from the preview."""
    if "intl_copies" not in ctx.cache:
        out = {}
        for e in pg.others():
            url = pg.origin + pg.path_of(e) if pg.origin else ""
            status, html = fetch(ctx, url) if url else (0, "")
            out[e["locale"]] = {"url": url, "status": status, "root": parse(html) if status == 200 and html else None, "path": pg.path_of(e)}
        ctx.cache["intl_copies"] = out
    return ctx.cache["intl_copies"]


def exists(c) -> bool:
    return c["status"] == 200


def missing(c) -> bool:
    return c["status"] in (404, 410)


def finish(ctx, problems, ok_what):
    """problems: [(what, fix)]. One FAIL line per problem, each with its own fix; an OK line when there is none."""
    if not problems:
        ctx.ok(ok_what)
    for what, fix in problems:
        ctx.fail(what, fix)


# ---- the checks ------------------------------------------------------------------------------------------------------------
@check("intl.lang", "162", ALL, "<html lang> is the page's own locale (en-US on the en-US copy, fr-CA on the fr-CA copy)", needs="live")
def lang(ctx):
    pg = page(ctx)
    html = find(ctx.root(), "html")
    have = (html.get("lang") if html is not None else "").strip()
    want = pg.loc["locale"]
    if not have:
        ctx.fail(f"this page is the {want} copy but <html> has no lang attribute", f'set <html lang="{want}"> on every {want} page')
    elif have.lower() != want.lower():
        hint = " (a dash, not an underscore)" if "_" in have else ""
        ctx.fail(f'<html lang="{have}"> but this page is the {want} copy (folder {pg.loc["prefix"]}){hint}',
                 f'set <html lang="{want}">: the page\'s language and country are read from the tag and its folder, and must agree ({GUIDE_MULTI})')
    else:
        ctx.ok(f'<html lang="{have}"> is the page\'s locale ({want})')


@check("intl.copies", "162", ALL, "every other locale has its copy of this page (a missing translation is its own finding)", needs="live")
def copies_exist(ctx):
    pg = page(ctx)
    ctx.need_html()
    if not pg.origin:
        raise Missing("the page's address (--url), to look for its copies", "run the gate with --url <the preview address of the page>")
    found = copies(ctx, pg)
    bad = False
    for e in pg.others():
        c = found[e["locale"]]
        if exists(c):
            continue
        bad = True
        if missing(c):
            say = ctx.fail if pg.strict else ctx.warn
            say(f"missing translation: the {e['locale']} copy of {pg.base} does not exist yet (the preview answers {c['status']} at {c['path']})",
                f"write it at {c['path']} (the board's localize job for {e['locale']}); until it exists leave its hreflang out. A copy is never made by "
                f"pointing its tag or canonical at another language ({GUIDE_TELL})")
        else:
            ctx.warn(f"could not read the {e['locale']} copy of {pg.base} at {c['path']} (the preview answered {c['status'] or 'nothing'})",
                     "start the preview server for the whole site, then run the gate again")
    if not bad:
        ctx.ok(f"every locale has its copy of {pg.base} ({', '.join(e['locale'] for e in pg.others())})")


def hreflang_problems(ctx, pg: Page) -> list:
    root, out = ctx.root(), []
    alts = alternates(root)
    if not alts:
        return [(f"no hreflang tags on a page of a site with {len(pg.locs)} locales", f"add one <link rel=\"alternate\" hreflang=... href=...> for this page and "
                 f"each of its copies, and an x-default ({GUIDE_TELL})")]
    by = {}
    for tag, href in alts:
        by.setdefault(tag.lower(), []).append(href)
        if not HREFLANG.match(tag):
            out.append((f"hreflang \"{tag}\" is not a language tag", "write it like en-US or fr-CA (a dash, not an underscore) or x-default"))
    known = {e["locale"].lower() for e in pg.locs} | {"x-default"}
    for tag in sorted(set(by) - known):
        if HREFLANG.match(tag):
            out.append((f"hreflang \"{tag}\" is not one of this site's locales ({', '.join(e['locale'] for e in pg.locs)})",
                        "remove the tag, or add the locale to growth.json market.locales (growth wizard answer market ...)"))
    found = copies(ctx, pg)
    me = pg.loc["locale"]
    own = npath(pg.path)
    # a self-reference
    s = by.get(me.lower(), [])
    if not s:
        out.append((f"no self-referencing hreflang: this {me} page does not list itself", f"add hreflang=\"{me}\" with this page's own absolute address ({GUIDE_TELL})"))
    elif not any(npath(h) == own for h in s):
        out.append((f"the hreflang {me} on the {me} page points at {npath(s[0])}, not at this page ({own})", f"point hreflang=\"{me}\" at this page's own address"))
    # one tag per locale, pointing at the same page's copy
    for e in [x for x in pg.locs if x["locale"] != me]:
        tag, c = e["locale"], found.get(e["locale"])
        hrefs = by.get(tag.lower(), [])
        want = npath(pg.path_of(e))
        if not hrefs:
            if c is not None and exists(c):
                out.append((f"no hreflang for {tag}, but its copy exists at {pg.path_of(e)}", f"add <link rel=\"alternate\" hreflang=\"{tag}\" href=\"{pg.site}{pg.path_of(e)}\">"))
            continue
        if len({npath(h) for h in hrefs}) > 1:
            out.append((f"two different addresses for hreflang {tag}: {', '.join(sorted(set(hrefs)))}", "keep one tag for each language and country"))
        for h in hrefs[:1]:
            if not absolute(h):
                out.append((f"hreflang {tag} is not an absolute address (\"{short(h, 50)}\")", "write the full address with https:// and the host: Google ignores relative hreflang addresses"))
            elif not host_ok(pg, h):
                out.append((f"hreflang {tag} points at another host ({urllib.parse.urlsplit(h).netloc})", "use the site's own address (growth.json site_url)"))
            if npath(h) != want:
                out.append((f"hreflang {tag} points at {npath(h)}, but the {tag} copy of this page is {want}", f"point it at the same page in the {tag} folder: {want}"))
    # the copies must point back
    for e in pg.others():
        c = found.get(e["locale"])
        if not c or not exists(c) or c["root"] is None:
            continue
        back = [h for t, h in alternates(c["root"]) if t.lower() == me.lower()]
        if not back or not any(npath(h) == own for h in back):
            out.append((f"not reciprocal: the {e['locale']} copy ({c['path']}) does not link back to this page with hreflang {me}" + (f" (it points at {npath(back[0])})" if back else ""),
                        f"add hreflang=\"{me}\" with this page's address to the {e['locale']} copy: every version must list all the others, or Google ignores the tags ({GUIDE_TELL})"))
    # x-default: the primary locale's address
    prim = locales.primary(pg.locs)
    xs = by.get("x-default", [])
    if not xs:
        out.append(("no x-default hreflang", f"add <link rel=\"alternate\" hreflang=\"x-default\" href=...> with the {prim['locale']} address of this page ({pg.path_of(prim)}): the page for visitors no locale fits"))
    else:
        if len({npath(h) for h in xs}) > 1:
            out.append((f"two different x-default addresses: {', '.join(sorted(set(xs)))}", "keep one x-default"))
        if not absolute(xs[0]):
            out.append((f"x-default is not an absolute address (\"{short(xs[0], 50)}\")", "write the full address with https:// and the host"))
        if npath(xs[0]) != npath(pg.path_of(prim)):
            out.append((f"x-default points at {npath(xs[0])}, not at the primary locale's address {pg.path_of(prim)}", f"point x-default at the {prim['locale']} copy of this page"))
    return out


@check("intl.hreflang", "162", ALL, "hreflang: a self-reference, a tag for each copy that exists, absolute, the same page, tags answered by tags, x-default", needs="live")
def hreflang(ctx):
    pg = page(ctx)
    ctx.need_html()
    if not pg.origin:
        raise Missing("the page's address (--url), to read its copies", "run the gate with --url <the preview address of the page>")
    probs = hreflang_problems(ctx, pg)
    finish(ctx, probs, f"hreflang is right: itself, {len(pg.others())} other locale(s) and x-default, absolute, pointing at the same page, answered by tags back")


@check("intl.canonical", "162", ALL, "the canonical is the page itself, never another language's copy", needs="live")
def canonical(ctx):
    pg = page(ctx)
    cans = [l.get("href").strip() for l in find_all(ctx.root(), "link") if "canonical" in l.get("rel").lower().split() and l.get("href").strip()]
    own = npath(pg.path)
    if not cans:
        ctx.fail(f"the {pg.loc['locale']} page has no canonical", f"add <link rel=\"canonical\" href=\"...{pg.path}\"> with this page's own address")
        return
    probs = []
    if len({npath(c) for c in cans}) > 1:
        probs.append((f"two different canonicals: {', '.join(cans)}", "keep one canonical"))
    c = cans[0]
    if not absolute(c):
        probs.append((f"the canonical is not an absolute address (\"{short(c, 50)}\")", "write the full address with https:// and the host"))
    elif not host_ok(pg, c):
        probs.append((f"the canonical points at another host ({urllib.parse.urlsplit(c).netloc})", "use the site's own address (growth.json site_url)"))
    if npath(c) != own:
        other = next((e for e in pg.locs if npath(pg.path_of(e)) == npath(c) and e["locale"] != pg.loc["locale"]), None)
        probs.append((f"the {pg.loc['locale']} page's canonical points at the {other['locale']} copy ({npath(c)})" if other
                      else f"the canonical points at {npath(c)}, not at this page ({own})",
                      f"make each language copy its own canonical ({own}); a canonical to another language makes Google drop this copy, and hreflang only works between canonical pages ({GUIDE_MULTI})"))
    finish(ctx, probs, f"the {pg.loc['locale']} page is its own canonical ({own})")


def scripts_that_redirect(root) -> list:
    out = []
    for s in find_all(root, "script"):
        if s.get("src") or s.get("type").lower() in DATA_SCRIPTS:
            continue
        text = s.own_text()
        if READS_LANGUAGE.search(text) and MOVES_VISITOR.search(text):
            out.append(short(MOVES_VISITOR.search(text).group(0), 40))
    return out


def probe(ctx, url, accept_language) -> int:
    """The status a GET with that Accept-Language gets, WITHOUT following a redirect (0 when it cannot be read)."""
    f = ctx.cache.get("intl_probe")
    if f:
        return f(url, accept_language)

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GrowthGate/1.0 (read-only)", "Accept-Language": accept_language})
        with urllib.request.build_opener(NoRedirect).open(req, timeout=20) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:  # noqa: BLE001
        return 0


@check("intl.no-auto-redirect", "162", ALL, "no script, meta refresh or server rule moves a visitor to another language by the browser's language", needs="live")
def no_auto_redirect(ctx):
    pg = page(ctx)
    root = ctx.root()
    why = "Google's crawler sends no language, so it would only ever see one version, and visitors are locked out of the others"
    fix = ("show a banner that suggests the other language (a plain link) and remember the choice; never move the visitor on its own "
           f"({GUIDE_MULTI}: avoid automatically redirecting users based on their perceived language)")
    probs = []
    for m in find_all(root, "meta"):
        if m.get("http-equiv").lower() == "refresh":
            probs.append((f"a meta refresh (\"{short(m.get('content'), 40)}\") moves the visitor on its own: {why}", fix))
    for how in scripts_that_redirect(root):
        probs.append((f"a script reads the browser's language (navigator.language / Accept-Language) and then changes the address ({how}): {why}", fix))
    if pg.origin and not probs:
        for e in pg.others()[:PROBE_LIMIT]:
            code = probe(ctx, pg.origin + pg.path, f"{e['locale']},{e['language']};q=0.9")
            if 300 <= code < 400:
                probs.append((f"the server answers {code} (a redirect) when the browser asks for {e['locale']}: it moves visitors by language: {why}", fix))
                break
    banner = any(READS_LANGUAGE.search(s.own_text()) for s in find_all(root, "script") if not s.get("src") and s.get("type").lower() not in DATA_SCRIPTS)
    finish(ctx, probs, "no automatic language redirect (no meta refresh, no script that moves the visitor by language"
           + ("; a script reads the language only to suggest" if banner else "") + ", the server answers every language the same)")


def sitemap_entries(ctx, pg: Page):
    """({normalised path: {hreflang lower: href}}, None) from the build's sitemap (an index is followed, up to 20 files); (None, why) when there is none."""
    def entries(url):
        status, text = fetch(ctx, url)
        if status != 200 or not text.strip():
            return None, f"GET {urllib.parse.urlsplit(url).path} answered {status or 'nothing'}"
        try:
            return ET.fromstring(text.strip()), None
        except ET.ParseError as e:
            return None, f"the sitemap is not valid XML ({e})"
    root, why = entries(pg.origin + "/sitemap.xml")
    if root is None:
        return None, why
    docs = [root]
    if root.tag.endswith("sitemapindex"):
        docs = []
        for loc in [x.text.strip() for x in root.iter() if x.tag.endswith("}loc") or x.tag == "loc"][:20]:
            sub, _ = entries(pg.origin + urllib.parse.urlsplit(loc).path)
            if sub is not None:
                docs.append(sub)
    out = {}
    for d in docs:
        for u in d.iter():
            if not (u.tag.endswith("}url") or u.tag == "url"):
                continue
            loc = next((c.text.strip() for c in u if c.tag.endswith("loc") and c.text), "")
            alts = {c.get("hreflang", "").lower(): c.get("href", "") for c in u if c.tag.endswith("link") and c.get("rel", "") == "alternate" and c.get("hreflang")}
            if loc:
                out[npath(loc)] = alts
    return out, None


@check("intl.sitemap", "162", ALL, "when the build has a sitemap, it lists xhtml:link alternates for this page and each of its copies", needs="live")
def sitemap(ctx):
    pg = page(ctx)
    ctx.need_html()
    if not pg.origin:
        raise Missing("the page's address (--url), to read its sitemap", "run the gate with --url <the preview address of the page>")
    got, why = sitemap_entries(ctx, pg)
    if got is None:
        raise Skip(f"the build has no sitemap to read ({why}); rule 87 covers a missing sitemap")
    own = npath(pg.path)
    if own not in got:
        raise Skip(f"{own} is not in the sitemap (rule 87 covers that)")
    alts = got[own]
    found = copies(ctx, pg)
    want = [pg.loc] + [e for e in pg.others() if exists(found.get(e["locale"], {"status": 0}))]
    probs = []
    if not alts:
        probs.append((f"the sitemap lists {own} with no xhtml:link alternates", "give each <url> one <xhtml:link rel=\"alternate\" hreflang=... href=...> for every language version, itself included "
                                                                                    f"(add xmlns:xhtml=\"http://www.w3.org/1999/xhtml\"; {GUIDE_TELL}, the sitemap part)"))
    else:
        lacking = [e["locale"] for e in want if e["locale"].lower() not in alts]
        if lacking:
            probs.append((f"the sitemap entry for {own} lacks xhtml:link alternates for {', '.join(lacking)}", "list every language version of the page in its <url>, itself included"))
        for e in want:
            h = alts.get(e["locale"].lower())
            if h and npath(h) != npath(pg.path_of(e)):
                probs.append((f"the sitemap's alternate {e['locale']} points at {npath(h)}, not at {npath(pg.path_of(e))}", "point it at the same page's copy in that folder"))
    finish(ctx, probs, f"the sitemap lists {len(alts)} xhtml:link alternate(s) for {own}")
