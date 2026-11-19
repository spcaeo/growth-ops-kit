"""Audit M6: one form of a page path and one folder name per page, whatever the caller typed."""
import itertools

import paths

FORMS = ["/café/menu", "/caf%C3%A9/menu", "/café/menu/", "caf%C3%A9/menu", "https://shop.example/caf%C3%A9/menu/?a=1#top",
         "//shop.example/caf%C3%A9/menu", "/caf%C3%A9//menu?x=%2F"]


def test_every_spelling_of_a_page_gives_one_key_and_one_folder():
    assert {paths.key(f) for f in FORMS} == {"/café/menu"}
    assert len({paths.snapshot_slug(f) for f in FORMS}) == 1
    for a, b in itertools.permutations(FORMS, 2):
        assert paths.key(a) == paths.key(b)


def test_plain_cases():
    assert paths.key("x") == paths.key("/x") == paths.key("/x/") == "/x"
    assert paths.key("") == paths.key("/") == paths.key("https://shop.example") == paths.key("https://shop.example/?q=1") == "/"
    assert paths.key("https://shop.example/x/") == "/x"
    assert paths.key("/a#frag") == "/a"
    assert paths.snapshot_slug("/") == "home"
    assert paths.snapshot_slug("/blog/best-mowing-height/") == "blog__best-mowing-height"
    assert paths.snapshot_slug("/a b/C") == "a-b__c"


def test_key_is_stable_when_applied_again():
    for f in FORMS + ["/x/", "x", "/"]:
        assert paths.key(paths.key(f)) == paths.key(f)


def test_archive_journal_and_snapshot_name_a_page_the_same(demo_project, monkeypatch):
    monkeypatch.setenv("GROWTH_PROJECT", str(demo_project))
    import journal
    import page_archive
    for f in ("/blog/a-post/", "blog/a-post", "https://shop.example/blog/a-post?x=1"):
        assert page_archive.slug_of(f) == journal.slug(paths.key(f)) == paths.snapshot_slug(f) == "blog__a-post"
