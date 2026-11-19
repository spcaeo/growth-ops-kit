"""Titles, descriptions, headings, language, content (TTL, CNT)."""
from __future__ import annotations

import datetime
import re

from .dom import find_all

PLACEHOLDER = re.compile(r"lorem ipsum|\bTODO\b|\bFIXME\b|\bXXX\b|\{\{[^}]*\}\}|\[Your [A-Za-z ]+\]|\bundefined\b|\bNaN\b|\[object Object\]", re.I)
NARROW, WIDE = set("ijlrtf.,:;'|! I"), set("mwMW@%")


def est_px(text, size=20):
    """Rough pixel width of a title in Arial 20px (Google's title font); a guide, not a measurement."""
    w = 0.0
    for ch in text:
        w += (0.28 if ch in NARROW else 0.84 if ch in WIDE else 0.66 if ch.isupper() else 0.5) * size
    return int(w)


def run_meta(p):
    rep = p.rep
    titles = p.title_nodes()
    t = p.title()
    # TTL-01 / TTL-02 / TTL-03
    if len(titles) != 1:
        rep.fail("TTL-01", f"{len(titles)} <title> tags" if titles else "no <title>", "exactly one title per page")
    else:
        rep.ok("TTL-01", "exactly one <title>")
    if t:
        n, px = len(t), est_px(t)
        if n > 60 and px > 580:
            rep.fail("TTL-02", f"title is {n} characters (about {px}px): cut off in results", "shorten to 30 to 60 characters")
        elif n > 60 or n < 30:
            rep.warn("TTL-02", f"title is {n} characters (about {px}px)", "aim for 30 to 60 characters and 580px or less")
        else:
            rep.ok("TTL-02", f"title is {n} characters (about {px}px)")
        if p.keyword:
            pos = t.lower().find(p.keyword)
            (rep.ok if 0 <= pos <= 35 else rep.warn)("TTL-03", f"keyword '{p.keyword}' " + (f"at character {pos} of the title" if pos >= 0 else "is not in the title"),
                                                      "put the main phrase near the start of the title")
        else:
            rep.skip("TTL-03", "pass --keyword to check the title for the main phrase")
    # TTL-05 / 06 / 07 description
    ds = p.metas("name", "description")
    d = ds[0].get("content").strip() if ds else None
    if len(ds) != 1:
        rep.fail("TTL-05", f"{len(ds)} meta descriptions", "exactly one meta description")
    else:
        rep.ok("TTL-05", "exactly one meta description")
    if d:
        n = len(d)
        bad = bool(re.search(r"<[a-z/]|\*\*|\]\(|^#", d))
        if n > 160 or n < 70 or bad:
            rep.fail("TTL-06", f"description is {n} characters" + (", with markup" if bad else ""), "120 to 155 characters, plain sentence")
        elif n < 120 or n > 155 or not re.search(r"[.!?]$", d):
            rep.warn("TTL-06", f"description is {n} characters" + ("" if re.search(r"[.!?]$", d) else ", not a full sentence"),
                     "120 to 155 characters, ending as a full sentence")
        else:
            rep.ok("TTL-06", f"description is {n} characters, full sentence")
        og_t, og_d = p.meta_content(prop="og:title"), p.meta_content(prop="og:description")
        if t and d.lower() == t.lower():
            rep.warn("TTL-07", "description is the same as the title", "write its own sentence")
        else:
            rep.ok("TTL-07", "description differs from the title")
    # TTL-08 placeholders, stale year
    year = datetime.date.today().year
    stale = [y for y in re.findall(r"\b(20[12]\d)\b", t or "") if int(y) < year]
    found = [x for x in (t, d, " ".join(h.all_text() for h in p.headings())) if x and PLACEHOLDER.search(x)]
    if found or stale:
        rep.fail("TTL-08", "placeholder or old year in title, description or headings" + (f" (year {stale[0]})" if stale else ""),
                 "remove placeholder text; a title may carry the current year only")
    else:
        rep.ok("TTL-08", "no placeholder text or old year in title, description, headings")
    # headings
    hs = p.headings()
    h1 = [h for h in hs if h.tag == "h1"]
    if len(h1) == 1:
        rep.ok("TTL-09", "exactly one H1")
    else:
        rep.fail("TTL-09", f"{len(h1)} H1 tags", "exactly one H1 per page")
    if h1:
        h = h1[0].all_text()
        bad = not h or len(h) > 70
        if bad:
            rep.warn("TTL-10", f"H1 is {len(h)} characters: '{h[:60]}'", "a clear H1 of 70 characters or fewer")
        elif p.keyword and p.keyword not in h.lower():
            rep.warn("TTL-10", f"H1 lacks the keyword '{p.keyword}': '{h}'", "name the main topic in the H1")
        else:
            rep.ok("TTL-10", f"H1: '{h}'")
    levels = [int(h.tag[1]) for h in hs]
    skips = [(levels[i - 1], levels[i]) for i in range(1, len(levels)) if levels[i] > levels[i - 1] + 1]
    first = levels[0] if levels else None
    if skips or (first not in (None, 1)):
        rep.fail("TTL-11", f"heading order breaks: {skips[:3] or 'first heading is H' + str(first)}", "never skip a level (H2 then H4); start with H1")
    else:
        rep.ok("TTL-11", f"{len(hs)} headings in order ({', '.join(f'H{i}:{levels.count(i)}' for i in range(1, 7) if levels.count(i))})")
    texts = [h.all_text().strip().lower() for h in hs]
    empties = sum(1 for x in texts if not x)
    dups = {x for x in texts if x and texts.count(x) > 1 and not x.isdigit()}
    if empties or dups:
        rep.warn("TTL-12", f"{empties} empty heading(s), repeated: {sorted(dups)[:3]}", "give each heading its own words; a big number is emphasis, not a heading")
    else:
        rep.ok("TTL-12", "no empty or repeated headings")
    ids = sum(1 for h in hs if h.get("id"))
    rep.info("TTL-13", f"{ids} of {len(hs)} headings have an id (old #section links need their ids kept)")
    # language, charset
    html = next((n for n in p.root.iter() if n.tag == "html"), None)
    lang = html.get("lang") if html else ""
    (rep.ok if re.fullmatch(r"[a-z]{2,3}(-[A-Za-z0-9]+)*", lang or "") else rep.fail)("TTL-14", f"<html lang='{lang}'>", "set lang='en' on <html>")
    cs = any(m.get("charset") for m in find_all(p.root, "meta")) or "charset" in p.resp.h("content-type").lower()
    first_k = p.html[:1024].lower()
    (rep.ok if cs and ("charset" in first_k or "charset" in p.resp.h("content-type").lower()) else rep.warn)(
        "TTL-15", "charset declared early" if cs else "no charset declared", "<meta charset='utf-8'> in the first 1024 bytes")


def run_content(p):
    rep = p.rep
    vis = p.visible_text()
    w = p.words(vis)
    body_w = p.words(p.body.all_text(visible=True))
    if w < 300:
        rep.fail("CNT-01", f"{w} words in <main> ({body_w} in the whole body)", "a money page needs at least 300 words of real copy")
    elif w < 600:
        rep.warn("CNT-01", f"{w} words in <main> ({body_w} in the whole body)", "thin for a money page: answer the buyer's questions fully")
    else:
        rep.ok("CNT-01", f"{w} words in <main> ({body_w} in the whole body)")
    m = PLACEHOLDER.search(vis)
    (rep.fail if m else rep.ok)("CNT-03", f"placeholder text in the copy: '{m.group(0)}'" if m else "no placeholder text in the copy",
                                "remove TODO, lorem, {{field}} and similar before shipping")
    # CNT-04 answer-first passage: first real paragraph after the H1 should be 40 to 60 words
    h1 = next((h for h in p.headings() if h.tag == "h1"), None)
    para = None
    if h1:
        for n in p.root.iter():
            if n.idx > h1.idx and n.tag == "p" and len(n.all_text().split()) >= 12:
                para = n
                break
    if para:
        k = len(para.all_text().split())
        (rep.ok if 30 <= k <= 70 else rep.warn)("CNT-04", f"first paragraph after the H1 is {k} words: '{para.all_text()[:70]}...'",
                                                "open with one self-contained answer of 40 to 60 words (rule 36b)")
    else:
        rep.warn("CNT-04", "no paragraph of 12+ words after the H1", "answer the core question in the first screen")
    upd = re.search(r"(?i)\b(last )?(updated|reviewed|published)\b[^.]{0,30}\b(20\d\d)\b", vis) or any(
        t.get("datetime") for t in find_all(p.root, "time"))
    (rep.ok if upd else rep.warn)("CNT-05", "a visible date was found" if upd else "no visible updated or published date",
                                  "show 'Updated <date>' near the top (GEO rule 36b)")
