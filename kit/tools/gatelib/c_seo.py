"""Bridge to the technical SEO checker (tools/techseo): its checks run once per gate run and their
results are mapped onto the rulebook rules they enforce. No check is duplicated here."""
from __future__ import annotations

from techseo import c_images, c_index, c_links, c_map, c_meta, c_perf, c_schema, c_social
from techseo.net import Fetcher
from techseo.page import Page
from techseo.report import Report

from .core import ALL, Missing, Skip, check

# check id -> (rule, technical SEO ids, what)
BRIDGE = {
    "seo.all": ("36d", None, "the whole technical SEO check passes (no FAIL)"),
    "seo.title-desc": ("81", ["TTL-02", "TTL-06"], "title 30-60 chars / 580px; description 120-155 chars, a sentence"),
    "seo.unique-meta": ("82", ["TTL-07", "SOC-05"], "the description is its own; og text follows the meta text"),
    "seo.basics": ("83", ["TTL-01", "TTL-05", "TTL-09", "SOC-01", "IMG-14"], "title, description, one H1, share image, a main picture"),
    "seo.headings": ("84", ["TTL-09", "TTL-11", "TTL-12"], "exactly one H1; no skipped or repeated heading"),
    "seo.heading-ids": ("85", ["TTL-13", "LNK-12"], "heading ids kept; every #anchor lands"),
    "seo.canonical": ("80", ["URL-02", "URL-03", "URL-04", "URL-05", "URL-06"], "one self canonical in the site's address style"),
    "seo.sitemap": ("87", ["MAP-01", "MAP-02", "MAP-03", "MAP-05"], "the sitemap lists only real landing pages, this one included"),
    "seo.old-host": ("78", ["URL-11", "LNK-08", "SCH-09"], "no retired host, old IP or localhost in links or markup"),
    "seo.utm": ("34", ["LNK-05", "URL-09"], "no utm_ on internal links; a utm address canonicalizes to the clean one"),
    "seo.placeholder-links": ("92", ["LNK-06", "JSR-10", "IMG-10"], "no <a> without href, no placeholder href, no <img> without src"),
    "seo.external-links": ("91", ["LNK-07"], "external links are noopener; nofollow/sponsored where we do not vouch"),
    "seo.anchor-text": ("90", ["LNK-03", "LNK-04", "LNK-10"], "link text names its target; one text, one target"),
    "seo.jsonld": ("95", ["SCH-01", "SCH-02", "SCH-03", "SCH-04", "SCH-06", "SCH-08", "SCH-10", "SCH-11", "SCH-15"], "JSON-LD parses and says what the page shows"),
    "seo.jsonld-first": ("98", ["SCH-14"], "JSON-LD is never the page's first node"),
    "seo.faq-markup": ("151", ["SCH-05"], "FAQPage markup equals the visible FAQ"),
    "seo.breadcrumbs": ("50", ["SCH-07"], "BreadcrumbList positions, names and URLs are right"),
    "seo.share-image": ("65", ["SOC-01", "SOC-02", "SOC-03", "SOC-04", "SOC-06", "SOC-08", "SOC-09"], "share image real, sized, og and twitter agree"),
    "seo.alt": ("62", ["IMG-02", "IMG-03"], "every image has a fitting alt; decoration is marked"),
    "seo.img-weight": ("63", ["IMG-04", "IMG-07", "IMG-08", "IMG-11"], "images sized, light (<=200 KiB) and modern"),
    "seo.img-ext": ("64", ["IMG-09", "IMG-12"], "image files keep their extension and type"),
    "seo.first-screen-lazy": ("66", ["IMG-05"], "nothing in the first screen loads lazily"),
    "seo.hreflang": ("94", ["INT-01", "TTL-14"], "lang set; no lone hreflang"),
    "seo.render": ("100", ["JSR-01", "JSR-02", "JSR-05", "JSR-06"], "title, copy and metadata are in the served HTML"),
    "seo.speed-static": ("101", ["PERF-05", "PERF-06", "PERF-07", "PERF-08", "PERF-09"], "no render-blocking scripts, few fonts and hints"),
    "seo.contextual-links": ("89", ["LNK-09"], "three or more internal links inside the main copy"),
}


def inventory_paths(project):
    """The normalised paths of the live site's inventory (growth inventory writes inventory/inventory.json and .csv)."""
    import csv
    import json

    import paths
    base = project / "inventory"
    try:
        rows = json.loads((base / "inventory.json").read_text()).get("pages") or []
    except (OSError, ValueError, AttributeError):
        try:
            with open(base / "inventory.csv", newline="") as f:
                rows = list(csv.DictReader(f))
        except OSError:
            rows = []
    return {paths.normalize(r["path"]) for r in rows if isinstance(r, dict) and r.get("path")}


def migration_info(ctx):
    """growth.json "migration": {"on": true, "task": "T4"} -> {"task", "paths"} (None when off): a 404 internal link to a path the
    live site's inventory lists is a WARN while the pages are not migrated yet (LNK-02)."""
    m = ctx.cfg.get("migration") or {}
    if not (isinstance(m, dict) and m.get("on")):
        return None
    return {"task": str(m.get("task") or "the migration task"), "paths": inventory_paths(ctx.project)}


def techseo(ctx):
    """Run the technical SEO checks once (dev mode) and keep the results."""
    if "tseo" not in ctx.cache:
        ctx.need_html()
        import urllib.parse
        u = urllib.parse.urlsplit(ctx.url)
        f = Fetcher(f"{u.scheme}://{u.netloc}", ctx.site_origin(), allow_live=False)
        rep = Report(url=ctx.url, mode="dev")
        mig = migration_info(ctx)
        p = Page(f, rep, ctx.url, mode="dev", site_origin=ctx.site_origin(), old_hosts=ctx.cfg.get("old_hosts") or [])
        if c_index.run_index(p) and p.resp.status == 200:
            c_index.run_url(p)
            c_meta.run_meta(p)
            c_meta.run_content(p)
            c_links.run_links(p, int(ctx.cfg.get("link_check_cap") or 200), not ctx.cache.get("no_link_status"), mig)
            c_images.run_images(p)
            c_schema.run_schema(p, {"money": "money", "post": "article", "hub": "hub"}.get(ctx.ptype, "other"),
                                (ctx.cfg.get("schema_types") or {}).get("money"))
            c_social.run_social(p)
            c_perf.run_perf(p)
            c_perf.run_mobile(p)
            c_map.run_map(p, False)
            c_map.run_intl(p)
            c_map.run_js(p)
            c_index.run_security(p)
        ctx.cache["tseo"] = rep.results
    return ctx.cache["tseo"]


def make(cid, rule, ids, what):
    @check(cid, rule, ALL, what)
    def _bridge(ctx):
        res = techseo(ctx)
        sel = [r for r in res if ids is None or r.cid in ids]
        if not sel:
            raise Missing(f"technical SEO results for {', '.join(ids or ['any check'])}",
                          f"run growth tech_seo_check {ctx.url} and fix why it stopped")
        if not ctx.cache.get("no_link_status") and any(r.cid == "LNK-02" and r.level == "SKIP" for r in sel):
            raise Skip("internal link status was not fetched (the run did not allow it)", blocked=True)
        if all(r.level == "SKIP" for r in sel) and ids is not None:
            raise Skip(sel[0].msg)
        fails = [r for r in sel if r.level == "FAIL"]
        warns = [r for r in sel if r.level == "WARN"]
        if fails:
            ctx.fail("; ".join(f"{r.cid} {r.msg}" for r in fails[:4]) + (f"; +{len(fails) - 4} more" if len(fails) > 4 else ""),
                     " | ".join(dict.fromkeys(r.fix for r in fails[:4] if r.fix)) or "see growth tech_seo_check output")
        elif warns:
            ctx.warn("; ".join(f"{r.cid} {r.msg}" for r in warns[:3]), " | ".join(dict.fromkeys(r.fix for r in warns[:3] if r.fix))
                     or "see the technical SEO playbook")
        else:
            ctx.ok(f"{len(sel)} technical SEO line(s) pass ({', '.join(sorted({r.cid for r in sel})[:6])})"
                   + "".join(f"; {r.msg}" for r in sel if r.cid == "LNK-02" and r.level == "OK"))
    return _bridge


for _cid, (_rule, _ids, _what) in BRIDGE.items():
    make(_cid, _rule, _ids, _what)
