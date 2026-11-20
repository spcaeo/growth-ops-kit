"""2.3.0: sticky bar, exit offer and fold surfaces are checked on every stack (they were Next.js only), and a house
feature switched off without a fit reason fails house.features (rule 161)."""
from pathlib import Path

from gatelib import CHECKS
from gatelib.core import Ctx, run_check

CFG = {"stack": "static", "conversion_path": "/contact/", "cta": {"contact_path": "/contact/", "label": "Book a call"},
       "features": {"sticky_cta": True, "exit_offer": True}}


def lines(html, cid, cfg=CFG, path="/service/"):
    c = Ctx(project=Path("/nonexistent"), path=path, key="x", ptype="money", cfg=cfg, html=html, url="http://127.0.0.1:9" + path, status=200)
    run_check(c, CHECKS[cid])
    return c.lines


def page(body, style=""):
    return f"<html><head><style>{style}</style></head><body><header class='site-header'></header><main>{body}</main></body></html>"


def test_three_checks_run_on_a_static_site():
    for cid in ("sticky.present", "exit.present", "page.surfaces"):
        assert CHECKS[cid].needs == "live"
    assert lines(page("<p>x</p>"), "sticky.present")[-1].level == "FAIL"
    assert lines(page("<p>x</p>"), "exit.present")[-1].level == "FAIL"


def test_surfaces_read_from_the_served_page():
    good = "".join(f'<section data-fold="f{i}" data-surface="{s}" data-job="{j}"></section>'
                   for i, (s, j) in enumerate([("plain", "hook"), ("tint", "show"), ("warm", "prove"), ("plain", "act")]))
    assert lines(page(good), "page.surfaces")[-1].level == "OK"
    bad = '<section data-fold="a" data-surface="plain" data-job="hook"></section>' * 3
    ln = lines(page(bad), "page.surfaces")[-1]
    assert ln.level == "FAIL" and "share the surface" in ln.what


def test_sticky_bar_found_with_served_css():
    bar = ("<div class='sticky-cta'><p class='sticky-cta-text'>Get your plan in one call</p>"
           "<a class='btn btn--primary' href='/contact/'>Book a call</a><button aria-label='Close'>x</button>"
           "<span class='sticky-cta-progress'></span></div>")
    css = "html[data-sticky-cta] .site-header{display:none}"
    ln = lines(page(bar, css), "sticky.present")[-1]
    assert "no CSS rule hides" not in ln.what and "no close x" not in ln.what and "progress" not in ln.what


def test_feature_off_without_reason_fails_house(monkeypatch):
    from gatelib import c_house
    monkeypatch.setitem(c_house.HOUSE, "money", ["sticky.present"])
    cfg = {"stack": "static", "features": {"sticky_cta": False}}
    out = lines(page("<p>x</p>"), "sticky.present", cfg)
    assert out[-1].level == "SKIP"
    c = Ctx(project=Path("/nonexistent"), path="/s/", key="x", ptype="money", cfg=cfg, html=page("<p>x</p>"), url="http://127.0.0.1:9/s/", status=200)
    run_check(c, CHECKS["sticky.present"])
    run_check(c, CHECKS["house.features"])
    assert "features.sticky_cta is off with no reason" in c.lines[-1].what
    cfg2 = {**cfg, "features_dropped": {"sticky_cta": "no booking path on this site"}}
    c2 = Ctx(project=Path("/nonexistent"), path="/s/", key="x", ptype="money", cfg=cfg2, html=page("<p>x</p>"), url="http://127.0.0.1:9/s/", status=200)
    run_check(c2, CHECKS["sticky.present"])
    run_check(c2, CHECKS["house.features"])
    assert "features.sticky_cta" not in c2.lines[-1].what
