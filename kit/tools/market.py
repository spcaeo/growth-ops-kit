"""A page's figures for the target market, MEASURED from Search Console's country rows, next to any estimate.

Search Console lists only a page's top countries. Anything "cleaned" from the all-countries total has to say what it
assumes. Lessons from a real page (all countries 295,810 impressions at position 3.2; the target market measured
27,487 at position 5.2; an estimate of 68,106 that assumed the unlisted countries split like the listed ones, about 2.5x
too high):

  1. the measured target-market figure always sits next to the estimate, and the estimate states its assumption;
  2. the target market's OWN position is reported (3.2 overall can be 5.2 where it counts);
  3. one definition before and after a change: `definition` is stored with each snapshot, and a change is flagged.

growth.json: "target_markets": ["usa"]  (country codes the way the search tool lists them, any case).

Query noise (#19): some of a page's searches are not buyers: the business's own name (brand), spam and junk, and searches
about something else (off topic). growth.json "query_noise":
  {"brand": ["acme"], "spam": ["free download"], "off_topic": ["jobs"], "on_topic": ["board"]}
brand/spam/off_topic are words or phrases (whole words, any case); "on_topic", when given, makes every search that holds none
of its words off topic. Default spam: web addresses. A search counts once, in the first class that matches (brand, spam, off
topic). The share is measured on the searches Google lists (its top ones), so a "clean" figure is an estimate: it says so.
"""
from __future__ import annotations

import re


def _pos(rows):
    imp = sum(i for _c, i, _p in rows)
    return round(sum((p or 0) * i for _c, i, p in rows) / imp, 1) if imp else None


def definition(targets, noise_cfg=None) -> str:
    """The text recorded with every snapshot; equal text = the same definition (a changed noise list is a new definition)."""
    d = "target market " + ",".join(sorted(t.lower() for t in targets)) + ": measured from the listed country rows"
    n = {k: sorted(str(x).lower() for x in v) for k, v in (noise_cfg or {}).items() if k in NOISE_KEYS and v}
    return d + (f"; query noise {n}" if n else "")


NOISE_KEYS = ("brand", "spam", "off_topic", "on_topic")
DEFAULT_SPAM = [r"https?://", r"\bwww\.", r"\.(com|net|org|ru|cn)\b"]


def _has(terms, q):
    return any(re.search(r"(?<![\w])" + re.escape(str(t).lower()) + r"(?![\w])", q) for t in terms or [])


def classify(query, noise_cfg) -> str:
    """'brand', 'spam', 'off_topic' or 'buyer' for one search, using growth.json query_noise."""
    q = re.sub(r"^\[us\] ", "", str(query or "").lower())
    cfg = noise_cfg or {}
    if _has(cfg.get("brand"), q):
        return "brand"
    if _has(cfg.get("spam"), q) or any(re.search(p, q) for p in DEFAULT_SPAM):
        return "spam"
    if _has(cfg.get("off_topic"), q) or (cfg.get("on_topic") and not _has(cfg.get("on_topic"), q)):
        return "off_topic"
    return "buyer"


def noise(queries, noise_cfg) -> dict | None:
    """queries: [(query, clicks, impressions)] Google lists for the page. The share of impressions and clicks that is brand,
    spam and off topic, with the biggest example of each. None when there is nothing configured to filter by."""
    if not any((noise_cfg or {}).get(k) for k in NOISE_KEYS):
        return None
    tot = {"impressions": 0, "clicks": 0}
    by = {k: {"impressions": 0, "clicks": 0, "top": None} for k in ("brand", "spam", "off_topic", "buyer")}
    for q, cl, im in queries:
        k = classify(q, noise_cfg)
        im, cl = im or 0, cl or 0
        by[k]["impressions"] += im; by[k]["clicks"] += cl
        tot["impressions"] += im; tot["clicks"] += cl
        if im and (by[k]["top"] is None or im > by[k]["top"][1]):
            by[k]["top"] = (q, im)
    share = lambda k, m: round(by[k][m] / tot[m], 4) if tot[m] else None
    noisy = lambda m: round(sum(by[k][m] for k in ("brand", "spam", "off_topic")) / tot[m], 4) if tot[m] else None
    return dict(listed_impressions=tot["impressions"], listed_clicks=tot["clicks"],
                classes={k: dict(impressions=v["impressions"], clicks=v["clicks"], share_impressions=share(k, "impressions"),
                                 share_clicks=share(k, "clicks"), top=v["top"][0] if v["top"] else None) for k, v in by.items()},
                noise_share_impressions=noisy("impressions"), noise_share_clicks=noisy("clicks"),
                assumption="the share is measured on the searches Google lists (its top ones); the unlisted long tail is assumed to split the same way")


def measure(countries, total, targets, queries=None, noise_cfg=None) -> dict | None:
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
    nz = noise(queries or [], noise_cfg)
    out = dict(
        definition=definition(want, noise_cfg),
        all=dict(clicks=all_clicks, impressions=all_imp, position=all_pos),
        measured=dict(clicks=t_clicks, impressions=t_imp, position=_pos(tgt)),
        listed_impressions=listed, listed_share_of_all=round(listed / all_imp, 4) if all_imp else None,
        estimate=dict(impressions=round(all_imp * share_listed) if share_listed is not None else None,
                      assumption="assumes the countries Google does not list split like the listed ones; this is an upper "
                                 "bound, the measured figure is the floor"))
    if nz:
        keep = 1 - (nz["noise_share_impressions"] or 0)
        out["noise"] = nz
        # noise taken out of BOTH figures, each marked: the measured one is a floor minus an assumed share, the estimate an upper bound
        out["clean"] = dict(measured_impressions=round(t_imp * keep),
                            estimate_impressions=round(out["estimate"]["impressions"] * keep) if out["estimate"]["impressions"] is not None else None,
                            assumption="measured and estimated impressions x (1 - the noise share of the listed searches); " + nz["assumption"])
    return out
