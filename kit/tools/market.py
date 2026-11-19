"""A page's figures for the target market, MEASURED from Search Console's country rows, next to any estimate.

Search Console lists only a page's top countries. Anything "cleaned" from the all-countries total has to say what it
assumes. Lessons from a real page (all countries 295,810 impressions at position 3.2; the target market measured
27,487 at position 5.2; an estimate of 68,106 that assumed the unlisted countries split like the listed ones, about 2.5x
too high):

  1. the measured target-market figure always sits next to the estimate, and the estimate states its assumption;
  2. the target market's OWN position is reported (3.2 overall can be 5.2 where it counts);
  3. one definition before and after a change: `definition` is stored with each snapshot, and a change is flagged.

growth.json: "target_markets": ["usa"]  (country codes the way the search tool lists them, any case).
"""
from __future__ import annotations


def _pos(rows):
    imp = sum(i for _c, i, _p in rows)
    return round(sum((p or 0) * i for _c, i, p in rows) / imp, 1) if imp else None


def definition(targets) -> str:
    """The text recorded with every snapshot; equal text = the same definition."""
    return "target market " + ",".join(sorted(t.lower() for t in targets)) + ": measured from the listed country rows"


def measure(countries, total, targets) -> dict | None:
    """countries: [(code, clicks, impressions, position)] (the listed top countries); total: (clicks, impressions, position)
    for ALL countries over the same period; targets: country codes. None when no target market is set."""
    want = {t.lower() for t in targets or []}
    if not want:
        return None
    rows = [(n, c or 0, i or 0, p) for n, c, i, p in countries]
    tgt = [(c, i, p) for n, c, i, p in rows if (n or "").lower().removeprefix("[us] ") in want]
    t_clicks, t_imp = sum(c for c, _i, _p in tgt), sum(i for _c, i, _p in tgt)
    listed = sum(i for _n, _c, i, _p in rows)
    all_clicks, all_imp, all_pos = total
    share_listed = t_imp / listed if listed else None
    return dict(
        definition=definition(want),
        all=dict(clicks=all_clicks, impressions=all_imp, position=all_pos),
        measured=dict(clicks=t_clicks, impressions=t_imp, position=_pos(tgt)),
        listed_impressions=listed, listed_share_of_all=round(listed / all_imp, 4) if all_imp else None,
        estimate=dict(impressions=round(all_imp * share_listed) if share_listed is not None else None,
                      assumption="assumes the countries Google does not list split like the listed ones; this is an upper "
                                 "bound, the measured figure is the floor"))
