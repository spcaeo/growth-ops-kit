"""2.2.0 fixes: K/M/B in head figures (friction 47), the root canonical slash style (48), no breadcrumb check on home, and the
"not migrated yet" mode for 404 links (LNK-02). A fake fetcher answers from memory: no network, no server."""
import json
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from techseo import c_index, c_links, c_schema  # noqa: E402
from techseo.net import Resp  # noqa: E402
from techseo.page import Page  # noqa: E402
from techseo.report import Report  # noqa: E402

from gatelib import CHECKS  # noqa: E402
from gatelib.c_release import money_figures, number_values  # noqa: E402
from gatelib.core import Ctx, run_check  # noqa: E402

ORIGIN = "https://example.com"


class Fake:
    allow_live = False

    def __init__(self, pages):
        self.pages = pages          # {path: (status, body)}

    def get(self, url, method="GET", **kw):
        path = url.replace(ORIGIN, "")
        st, body = self.pages.get(path, (404, "nope"))
        return Resp(url, st, {"content-type": "text/html; charset=utf-8"}, body.encode())

    def head_or_get(self, url, **kw):
        return self.get(url)

    def settle(self, url, r):
        return r


def page(path, html, pages=None):
    rep = Report(url=ORIGIN + path, mode="dev")
    f = Fake({path: (200, html), **(pages or {})})
    return Page(f, rep, ORIGIN + path, mode="dev", site_origin=ORIGIN), rep


def level(rep, cid):
    return [r.level for r in rep.results if r.cid == cid]


# ---- 1: K, M and B in head figures ------------------------------------------------------------------------------------------
def test_number_values_reads_k_m_b_like_money_figures():
    assert number_values("$40K to $600K+") == {Decimal(40000).normalize(), Decimal(600000).normalize()}
    assert number_values("40k, 1.5M, 2B, 3 million") >= {Decimal(40000).normalize(), Decimal(1500000).normalize(), Decimal(2_000_000_000).normalize(), Decimal(3_000_000).normalize()}
    assert list(money_figures("$40K"))[0] in number_values("budgets of 40K and up")
    assert number_values("5 minutes, 12.50, 1,200") == {Decimal(5), Decimal("12.5"), Decimal(1200).normalize()}


def test_head_figures_in_k_are_found_in_the_body():
    html = ("<html><body><main><h1>Budgets</h1><p>Plans run $40K to $600K+ a year.</p><h2>Detail</h2>"
            "<p>Small plans start at $40,000 and large ones reach 600K.</p></main></body></html>")
    ctx = Ctx(project=Path("/nonexistent-x"), path="/x/", url="http://127.0.0.1:9/x/", ptype="post", cfg={}, html=html, status=200)
    run_check(ctx, CHECKS["claims.head-figures"])
    assert ctx.lines[0].level == "OK", ctx.lines[0].what


# ---- 2: the root canonical matches either slash style -----------------------------------------------------------------------
HOME = '<html><head><title>Home</title><link rel="canonical" href="{}"></head><body><main><h1>Home</h1></main></body></html>'


def sitemap(slash):
    locs = "".join(f"<url><loc>{ORIGIN}/{n}{'/' if slash else ''}</loc></url>" for n in ("a", "b", "c"))
    return f'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{locs}</urlset>'


def test_root_canonical_matches_a_trailing_slash_sitemap_and_a_plain_one():
    for slash in (True, False):
        for href in (ORIGIN + "/", ORIGIN):
            p, rep = page("/", HOME.format(href), {"/sitemap.xml": (200, sitemap(slash))})
            c_index.run_url(p)
            assert level(rep, "URL-05") == ["OK"], (slash, href, [(r.cid, r.level, r.msg) for r in rep.results if r.cid == "URL-05"])


def test_an_inner_page_with_the_wrong_slash_style_still_fails():
    p, rep = page("/a", HOME.format(ORIGIN + "/a/").replace("Home", "A"), {"/sitemap.xml": (200, sitemap(False))})
    c_index.run_url(p)
    assert level(rep, "URL-05") == ["FAIL"]


# ---- 3: no breadcrumb trail on home -----------------------------------------------------------------------------------------
def test_sch_07_skips_on_the_home_page_and_the_check_skips_with_a_plain_line():
    p, rep = page("/", HOME.format(ORIGIN + "/"))
    c_schema.run_schema(p, "other")
    ln = [r for r in rep.results if r.cid == "SCH-07"]
    assert [r.level for r in ln] == ["SKIP"] and ln[0].msg == "home is the root: no breadcrumb trail"
    ctx = Ctx(project=Path("/nonexistent-x"), path="/", url=ORIGIN + "/", cfg={}, html="<html></html>", status=200)
    ctx.cache["tseo"] = rep.results
    run_check(ctx, CHECKS["seo.breadcrumbs"])
    assert ctx.lines[-1].level == "SKIP" and "home is the root" in ctx.lines[-1].what


# ---- 4: LNK-02 "not migrated yet" -------------------------------------------------------------------------------------------
LINKS = ('<html><head><title>T</title></head><body><main><h1>H</h1><p><a href="/old-a/">Old A</a> <a href="/old-b">Old B</a> '
         '<a href="/typo-page">Typo</a> <a href="/ok">Fine</a></p></main></body></html>')
OK_PAGE = (200, "<html><body>ok</body></html>")


def lnk(migration):
    p, rep = page("/x", LINKS, {"/ok": OK_PAGE})
    c_links.run_links(p, check_status=True, migration=migration)
    return [r for r in rep.results if r.cid == "LNK-02"]


def test_a_404_to_a_page_the_live_site_has_is_a_warn_that_names_the_task():
    mig = {"task": "T4", "paths": {"/old-a", "/old-b"}}
    res = lnk(mig)
    assert [r.level for r in res] == ["WARN", "FAIL"]
    warn, fail = res
    assert "T4" in warn.msg and "2 internal link" in warn.msg and "/old-a" in warn.msg and "/typo-page" not in warn.msg
    assert "/typo-page" in fail.msg and "/old-a" not in fail.msg


def test_all_parked_means_a_warn_and_no_ok_or_fail_and_off_changes_nothing():
    assert [r.level for r in lnk({"task": "T4", "paths": {"/old-a", "/old-b", "/typo-page"}})] == ["WARN"]
    res = lnk(None)
    assert [r.level for r in res] == ["FAIL"] and "/old-a" in res[0].msg and "T4" not in res[0].msg


def test_migration_info_reads_the_inventory_json_or_csv(tmp_path):
    from gatelib.c_seo import migration_info
    (tmp_path / "inventory").mkdir()
    (tmp_path / "inventory" / "inventory.json").write_text(json.dumps({"pages": [{"path": "/Old-A/"}, {"path": "/old-b"}]}))
    ctx = Ctx(project=tmp_path, cfg={"migration": {"on": True, "task": "T4"}})
    assert migration_info(ctx) == {"task": "T4", "paths": {"/Old-A", "/old-b"}}
    assert migration_info(Ctx(project=tmp_path, cfg={"migration": {"on": False, "task": "T4"}})) is None
    assert migration_info(Ctx(project=tmp_path, cfg={})) is None
    (tmp_path / "inventory" / "inventory.json").unlink()
    (tmp_path / "inventory" / "inventory.csv").write_text("path,status\n/from-csv,live\n")
    assert migration_info(ctx)["paths"] == {"/from-csv"}


# ---- 6: words.never_claims_allow ---------------------------------------------------------------------------------------------
def never(path, html, allow):
    cfg = {"words": {"never_claims": [r"\$\d+/hr"], "never_claims_allow": allow}}
    ctx = Ctx(project=Path("/nonexistent-x"), path=path, url="http://127.0.0.1:9" + path, cfg=cfg, html=html, status=200)
    run_check(ctx, CHECKS["words.never-claim"])
    return ctx.lines[0]


ROW = '<html><body><main><h1>Top firms</h1><p>Acme: $50/hr as Clutch states it.</p></main></body></html>'
ALLOW = [{"pattern": "Clutch", "paths": "*/companies/", "why": "our row on a Clutch list shows Clutch's rate"}]


def test_a_never_claim_on_an_allowed_path_with_an_allowed_pattern_is_a_warn_with_the_why():
    ln = never("/blog/companies/", ROW, ALLOW)
    assert ln.level == "WARN" and "our row on a Clutch list" in ln.what


def test_any_other_never_claim_still_fails():
    assert never("/blog/companies/", ROW.replace("as Clutch states it", "from us"), ALLOW).level == "FAIL"      # text not allowed
    assert never("/pricing/", ROW, ALLOW).level == "FAIL"                                                       # path not allowed
    assert never("/blog/companies/", ROW, []).level == "FAIL"                                                   # nothing allowed


# ---- 7: core.service-links with trailing slashes; 8: words.no-customers on a case-studies page --------------------------------
def test_service_links_compares_normalised_paths():
    html = '<html><body><main><p><a href="/lawn-care/">Lawn care</a> and <a href="/tree-work">Trees</a></p></main></body></html>'
    ctx = Ctx(project=Path("/nonexistent-x"), path="/about", url="http://127.0.0.1:9/about", ptype="core", html=html, status=200,
              cfg={"silos": {"lawn-care": "Lawn care", "tree-work": "Trees"}, "trust_paths": ["/about"]})
    run_check(ctx, CHECKS["core.service-links"])
    assert ctx.lines[0].level == "OK", ctx.lines[0].what
    ctx2 = Ctx(project=Path("/nonexistent-x"), path="/about", url="http://127.0.0.1:9/about", ptype="core", html=html, status=200,
               cfg={"silos": {"lawn-care": "x", "hedges": "y"}, "trust_paths": ["/about"]})
    run_check(ctx2, CHECKS["core.service-links"])
    assert ctx2.lines[0].level == "FAIL" and "hedges" in ctx2.lines[0].what


CS = ('<html><head><title>Case studies</title></head><body><nav><a href="/case-studies/">Case studies</a></nav><main>'
      '<nav aria-label="Breadcrumb">Home / Case studies</nav><h1>Case studies</h1><p>{}</p></main></body></html>')


def customers(path, html, words=None):
    ctx = Ctx(project=Path("/nonexistent-x"), path=path, url="http://127.0.0.1:9" + path, cfg={"words": words or {}}, html=html, status=200)
    run_check(ctx, CHECKS["words.no-customers"])
    return ctx.lines[0]


def test_a_case_studies_page_may_name_itself_but_customer_names_stay_banned():
    assert customers("/case-studies/", CS.format("How we work.")).level == "OK"
    assert customers("/case-studies/", CS.format("Read our case study on Acme.")).level == "FAIL"      # body use is still a claim
    assert customers("/case-studies/", CS.format("Trusted by Zorbo Inc.")).level == "FAIL"
    assert customers("/case-studies/", CS.format("We did work for Zorbo."), {"hidden_customers": ["Zorbo"]}).level == "FAIL"
    assert customers("/about/", CS.format("How we work.")).level == "FAIL"                                # not a case-study path
    assert customers("/proof/", CS.format("How we work."), {"no_customers_allow_paths": ["*/proof/"]}).level == "OK"


# ---- 9: a client's quote is not edited, so style checks skip it; claims still read it --------------------------------------------
def words_check(cid, body, words):
    html = f"<html><body><main><h1>Reviews</h1>{body}</main></body></html>"
    ctx = Ctx(project=Path("/nonexistent-x"), path="/x", url="http://127.0.0.1:9/x", cfg={"words": words, "spelling": "en-US"}, html=html, status=200)
    run_check(ctx, CHECKS[cid])
    return ctx.lines[0]


def test_style_checks_skip_blockquote_and_q_but_not_the_rest_of_the_page():
    quote = "<blockquote><p>A revolutionary, seamless colour tool.</p><cite>A client</cite></blockquote>"
    assert words_check("words.hype", quote, {}).level == "OK"
    assert words_check("words.hype", "<p>A <q>revolutionary</q> tool.</p>", {}).level == "OK"
    assert words_check("words.hype", quote + "<p>Our revolutionary tool.</p>", {}).level == "FAIL"
    assert words_check("words.banned", quote, {"banned_offer": ["seamless"]}).level == "OK"
    assert words_check("words.banned", quote + "<p>Seamless work.</p>", {"banned_offer": ["seamless"]}).level == "FAIL"


def test_never_claims_still_read_inside_a_quote():
    quote = "<blockquote><p>They promised $50/hr.</p></blockquote>"
    assert words_check("words.never-claim", quote, {"never_claims": [r"\$\d+/hr"]}).level == "FAIL"
