"""2.4.8: growth.json evidence.fresh_on "page_html" keeps evidence fresh when only the shared CSS/JS bundles changed."""
import fingerprint

PAGE = '<html><head><link rel="stylesheet" href="/_astro/site.{h}.css"><script src="/_astro/app.{h}.js"></script></head><body><h1>{t}</h1></body></html>'


def fp(h, t, css):
    html = PAGE.format(h=h, t=t)
    return fingerprint.make(html, lambda href: css.encode(), "build")


def test_bundle_rebuilt_page_same():
    a, b = fp("AAA", "Title", "a{}"), fp("BBB", "Title", "a{} b{}")
    assert not fingerprint.same(a, b)                       # strict: the bundle changed
    assert fingerprint.same(a, b, "page_html")              # the page's own markup did not


def test_page_changed_is_stale_in_both_modes():
    a, b = fp("AAA", "Title", "a{}"), fp("AAA", "New title", "a{}")
    assert not fingerprint.same(a, b) and not fingerprint.same(a, b, "page_html")


def test_old_fingerprint_without_page_falls_back_to_html():
    a = fp("AAA", "Title", "a{}")
    old = {k: v for k, v in a.items() if k != "page"}
    assert fingerprint.same(old, a, "page_html")
