"""2.4.3: hub.cards judges only the hub's post cards; layout.folds-distinct ignores wrapper-only markup."""
from pathlib import Path

from gatelib import CHECKS
from gatelib.core import Ctx, run_check


def last(cid, html, path="/hub-x/", ptype="hub"):
    c = Ctx(project=Path("/nonexistent"), path=path, key="x", ptype=ptype, cfg={}, html=html, url="http://127.0.0.1:9" + path, status=200)
    run_check(c, CHECKS[cid])
    return c.lines[-1]


def page(body):
    return f"<html><body><main>{body}</main></body></html>"


def test_hub_cards_only_post_cards_in_the_cluster():
    posts = "".join(f"<div class='post-card'><img src='c{i}.png' alt=''><a href='/hub-x/post-{i}/'>P{i}</a></div>" for i in range(3))
    other = ("<div class='service-card'><a href='/other-hub/'>Other</a></div><div class='ask-card'><a href='/contact/'>Ask</a></div>"
             "<div class='form-card'><a href='/contact/'>Form</a></div>")
    ln = last("hub.cards", page(posts + other))
    assert ln.level == "OK" and "3 cards" in ln.what, ln.what
    bare = "<div class='post-card'><a href='/hub-x/post-9/'>P9</a></div>"
    assert last("hub.cards", page(posts + other + bare)).level == "FAIL"


def test_folds_that_differ_only_by_wrappers_are_the_same():
    a = "<section><h2>A</h2><p>One.</p><p>Two.</p></section>"
    b = "<section><h2>B</h2><div><p>One.</p></div><aside><p>Two.</p></aside></section>"
    ln = last("layout.folds-distinct", page(a + b), path="/x/", ptype="money")
    assert ln.level == "FAIL", ln.what
    c = "<section><h2>C</h2><ul><li>x</li><li>y</li><li>z</li></ul></section>"
    assert last("layout.folds-distinct", page(a + c), path="/x/", ptype="money").level == "OK"


def test_drawn_cover_counts():
    """#73: an inline svg or sprite <use> is the post's cover on a drawn theme."""
    cards = ("<div class='post-card'><svg><use href='/s.svg#a'></use></svg><a href='/hub-x/a/'>A</a></div>"
             "<div class='post-card'><span data-cover></span><a href='/hub-x/b/'>B</a></div>")
    assert last("hub.cards", page(cards)).level == "OK"
