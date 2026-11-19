"""LNK-08 flags only the non-canonical twin host (friction 50); a title hold turns seo.title-query into a warning."""
from pathlib import Path

from techseo import c_links
from techseo.page import Page
from techseo.report import Report


class Resp:
    def __init__(self, html):
        self._h, self.status, self.headers, self.url = html, 200, {}, ""

    def text(self):
        return self._h


class Fetch:
    def __init__(self, html):
        self.html = html

    def get(self, url, **k):
        return Resp(self.html)


def lnk08(links, origin="https://www.example.com"):
    html = "<html><body><main>" + "".join(f'<a href="{h}">x</a>' for h in links) + "</main></body></html>"
    rep = Report(url=origin + "/x", mode="dev")
    p = Page(Fetch(html), rep, origin + "/x", site_origin=origin)
    c_links.run_links(p, check_status=False)
    return next(r.level for r in rep.results if r.cid == "LNK-08")


def test_a_full_link_to_the_canonical_www_host_is_fine():
    assert lnk08(["https://www.example.com/a/", "/b/"]) == "OK"


def test_the_bare_twin_and_plain_http_still_fail():
    assert lnk08(["https://example.com/a/"]) == "FAIL"
    assert lnk08(["http://www.example.com/a/"]) == "FAIL"
    assert lnk08(["https://www.example.com.evil.io/"]) == "OK"           # another host entirely: not ours to judge here


def test_a_site_without_www_flags_the_www_twin():
    assert lnk08(["https://www.example.com/a/"], origin="https://example.com") == "FAIL"
    assert lnk08(["https://example.com/a/"], origin="https://example.com") == "OK"


def test_title_query_is_a_warning_while_titles_are_held():
    from gatelib import CHECKS
    from gatelib.core import Ctx, run_check
    cfg = {"holds": {"title": {"why": "Google core update rolling out", "until": "the update ends"}}}
    c = Ctx(project=Path("/nonexistent"), path="/x", key="x", ptype="money", cfg=cfg,
            html="<html><head><title>T</title></head><body></body></html>", url="http://127.0.0.1/x", status=200)
    run_check(c, CHECKS["seo.title-query"])
    assert c.lines[-1].level == "WARN"
