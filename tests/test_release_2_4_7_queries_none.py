"""2.4.7: a page whose Search Console queries are all anonymised passes the search section with a queries_none reason."""
import datetime as dt

import research

TODAY = dt.date(2026, 11, 22)


def rec(**extra):
    r = {"search": {"scope": "page", "window": {"from": "2026-08-24", "to": "2026-11-21"}, "queries": []}}
    r.update(extra)
    return r


def search_probs(r):
    return [p for p in research.problems(r, TODAY, {}) if p.startswith("search:")]


def test_no_queries_and_no_reason_fails():
    assert search_probs(rec())


def test_queries_none_reason_passes():
    assert not search_probs(rec(queries_none="8 impressions, every query anonymised by Search Console"))


def test_a_short_reason_is_not_enough():
    assert search_probs(rec(queries_none="none"))
