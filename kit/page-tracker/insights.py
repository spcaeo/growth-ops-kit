"""Insights for the dashboard's Insights view (and the digest the daily AI summary reads).

Every comparison is before vs after, with same-length windows and the change day itself left out. The verdict rules
are the same as the dashboard's Impact tab (dashboard.js, VERDICT_RULES); keep both in step:
  - too early: fewer than 7 whole days after, or Google days in the after window that are still provisional;
  - counts per day (readers, clicks, impressions): no clear change when the move is under 20% or under a small floor
    (1 reader, 1 click, 10 impressions a day);
  - CTR: no clear change under 20% or under 0.1 percentage point;
  - average position: no clear change under 1.0 position; a lower number is better;
  - bounce: no clear change under 5 points; too early under 20 landings on either side; lower is better.
Overall: no verdicts -> too early to tell; only "no clear change" -> no clear change; better at least twice worse ->
mostly positive; worse at least twice better -> mostly negative; else mixed.
"""
import json, datetime as dt
from collections import defaultdict

D = dt.date.fromisoformat
N_MAX = 14
FLOOR = {"readers": 1, "clicks": 1, "impressions": 10, "ctr": 0.001, "leads": 0.3}
LOWER_BETTER = {"position", "bounce"}
RULES = ("Before vs after use same-length windows (up to 14 days) and skip the change day. Too early = fewer than 7 whole "
         "days after, or provisional Google days in the after window. No clear change = a move under 20% (or under 1 reader, "
         "1 click or 10 impressions a day; 0.1 point of CTR), position moving under 1.0, bounce moving under 5 points. "
         "Lower position and lower bounce are better. Google re-ranks pages for 1 to 2 weeks after big changes.")
SECTION_RULES = {
    "groups": "Split at the first change; same-length windows each side, change day left out; per-day averages; "
              "under 20% (or the small floors) = no clear change; position must move 1.0 or more.",
    "pages": "Each page against itself: same-length windows around its biggest change (most words added or removed), "
             "ranked by the move in Google impressions a day; the verdict uses the impressions rule.",
    "queries": "Google's top 10 searches per changed page in the before and after windows of the first change; "
               "a search 'new' or 'gone' may only have entered or left a page's top 10.",
    "countries": "Google's top 10 countries for the whole site in the same two windows; impressions rule; "
                 "countries in only one window are named, not compared.",
    "ai": "Skald visits where an AI assistant fetched a tracked page to answer someone; readers rule "
          "(20% and at least 1 a day; 7 whole days after needed).",
    "bounce": "Skald page journeys, up to 7 days each side of each page's main change; share of landings that left "
              "without another page; 5 points or more is a clear move; 20+ landings and 7 after days needed.",
    "index": "Latest Google URL inspection per tracked page (no verdict: a status, not a comparison).",
    "trend": "Whole site, by week (Mon to Sun); the last 4 complete final weeks vs the 4 before (28 days each side); "
             "impressions and clicks rules.",
}


def iso(d):
    return d.isoformat()


def gwin(d0, last, lastfinal, n_max=N_MAX):
    """Google window around change day d0 (dates). Prefer final days once 7 or more final days exist after d0."""
    a_to = min(d0 + dt.timedelta(days=n_max), last)
    if a_to > lastfinal and (lastfinal - d0).days >= 7:
        a_to = min(d0 + dt.timedelta(days=n_max), lastfinal)
    n = (a_to - d0).days
    if n < 1:
        return None
    return dict(n=n, b_from=iso(d0 - dt.timedelta(days=n)), b_to=iso(d0 - dt.timedelta(days=1)),
                a_from=iso(d0 + dt.timedelta(days=1)), a_to=iso(a_to), prov=max(0, (a_to - lastfinal).days))


def rwin(d0, newest, n_max=N_MAX):
    """Readers (Skald) window: whole days only, up to Skald's newest whole day."""
    a_to = min(d0 + dt.timedelta(days=n_max), newest)
    n = (a_to - d0).days
    if n < 1:
        return None
    return dict(n=n, b_from=iso(d0 - dt.timedelta(days=n)), b_to=iso(d0 - dt.timedelta(days=1)),
                a_from=iso(d0 + dt.timedelta(days=1)), a_to=iso(a_to), prov=0)


def verdict(metric, b, a, n, prov=0, landings=None):
    if b is None or a is None:
        return "too early"
    if n < 7 or prov:
        return "too early"
    if metric == "bounce" and landings is not None and min(landings) < 20:
        return "too early"
    diff = a - b
    if metric == "position":
        clear = abs(diff) >= 1.0
    elif metric == "bounce":
        clear = abs(diff) >= 5
    else:
        rel = abs(diff) / b if b else (1 if diff else 0)
        clear = rel >= 0.2 and abs(diff) >= FLOOR.get(metric, 0)
    if not clear:
        return "no clear change"
    good = diff < 0 if metric in LOWER_BETTER else diff > 0
    return "better" if good else "worse"


def overall(verdicts):
    v = [x for x in verdicts if x != "too early"]
    if not v:
        return "Too early to tell"
    b, w = v.count("better"), v.count("worse")
    if not b and not w:
        return "No clear change"
    if b and b >= 2 * w:
        return "Mostly positive"
    if w and w >= 2 * b:
        return "Mostly negative"
    return "Mixed"


def pct(b, a):
    return round(100 * (a - b) / b, 1) if b else None


def gsum(rows, frm, to):
    """rows: {day: (clicks, impressions, position_x_impressions, final)} -> totals."""
    c = i = pw = 0
    n = 0
    for d, (cl, im, p, _f) in rows.items():
        if frm <= d <= to:
            c += cl; i += im; pw += p; n += 1
    return dict(clicks=c, impressions=i, position=round(pw / i, 2) if i else None, ctr=round(c / i, 5) if i else None, days=n)


def load_search(c, paths):
    out = defaultdict(dict)
    q = "SELECT path, day, clicks, impressions, position, final FROM search"
    for path, day, cl, im, po, fi in c.execute(q):
        if path in paths:
            out[path][day] = (cl or 0, im or 0, (po or 0) * (im or 0), fi or 0)
    return out


def bundle(tot, n):
    return dict(clicks=round(tot["clicks"] / n, 2), impressions=round(tot["impressions"] / n, 1),
                ctr=tot["ctr"], position=tot["position"])


def compare(b, a, n, prov, metrics=("clicks", "impressions", "ctr", "position")):
    rows = []
    for m in metrics:
        bv, av = b.get(m), a.get(m)
        rows.append(dict(metric=m, before=bv, after=av, change_pct=pct(bv, av) if bv is not None and av is not None else None,
                         verdict=verdict(m, bv, av, n, prov)))
    return rows


def compute(c):
    pages = [r[0] for r in c.execute("SELECT path FROM pages")]
    slug = dict(c.execute("SELECT path, slug FROM pages").fetchall())
    changes = defaultdict(list)
    for path, live, wb, wa in c.execute("SELECT path, live_at, words_before, words_after FROM changes ORDER BY live_at"):
        changes[path].append((live, wb or 0, wa or 0))
    main = {p: max(ch, key=lambda r: abs(r[2] - r[1]))[0] for p, ch in changes.items()}
    changed = sorted(main)
    S = min(D(v[:10]) for v in main.values()) if main else dt.date.today()
    # no Google figures yet (Search Console is off): "last" days = the split day, so every window is empty and every
    # verdict reads "too early to tell", the same shape the dashboard already draws
    _l = c.execute("SELECT max(day) FROM search WHERE path='*'").fetchone()[0]
    _f = c.execute("SELECT max(day) FROM search WHERE path='*' AND final=1").fetchone()[0]
    last = D(_l) if _l else S
    lastfinal = D(_f) if _f else last
    newest_ok = c.execute("SELECT max(day) FROM daily WHERE state='ok'").fetchone()[0]
    newest_ok = D(newest_ok) if newest_ok else S
    srch = load_search(c, set(pages) | {"*"})
    out = dict(built=dt.datetime.now().astimezone().isoformat(timespec="minutes"), rules=RULES, split=iso(S),
               last_google_day=iso(last), last_final_google_day=iso(lastfinal), newest_readers_day=iso(newest_ok),
               changed_pages=len(changed), tracked_pages=len(pages))

    # 1. changed pages vs the rest of the site vs the whole site, split at the first change
    w = gwin(S, last, lastfinal)
    groups = []
    if w:
        site_b, site_a = gsum(srch["*"], w["b_from"], w["b_to"]), gsum(srch["*"], w["a_from"], w["a_to"])
        ch_b = {"clicks": 0, "impressions": 0, "pw": 0}; ch_a = dict(ch_b)
        for p in changed:
            for tot, frm, to in ((ch_b, w["b_from"], w["b_to"]), (ch_a, w["a_from"], w["a_to"])):
                for d, (cl, im, pw, _f) in srch[p].items():
                    if frm <= d <= to:
                        tot["clicks"] += cl; tot["impressions"] += im; tot["pw"] += pw

        def fin(t):
            i = t["impressions"]
            return dict(clicks=t["clicks"], impressions=i, position=round(t["pw"] / i, 2) if i else None, ctr=round(t["clicks"] / i, 5) if i else None)
        site_pw = lambda s: (s["position"] or 0) * s["impressions"]
        rest_b = {"clicks": site_b["clicks"] - ch_b["clicks"], "impressions": site_b["impressions"] - ch_b["impressions"], "pw": site_pw(site_b) - ch_b["pw"]}
        rest_a = {"clicks": site_a["clicks"] - ch_a["clicks"], "impressions": site_a["impressions"] - ch_a["impressions"], "pw": site_pw(site_a) - ch_a["pw"]}
        n = w["n"]
        for name, b, a in ((f"Changed pages ({len(changed)})", fin(ch_b), fin(ch_a)), ("Rest of the site (approx.)", fin(rest_b), fin(rest_a)),
                           ("Whole site", site_b, site_a)):
            groups.append(dict(name=name, rows=compare(bundle(b, n), bundle(a, n), n, w["prov"]), before_total=b, after_total=a))
        # readers on the changed pages (Skald)
        rw = rwin(S, newest_ok)
        if rw:
            rb = c.execute("SELECT sum(readers), count(DISTINCT day) FROM daily WHERE state='ok' AND day BETWEEN ? AND ?", (rw["b_from"], rw["b_to"])).fetchone()
            ra = c.execute("SELECT sum(readers), count(DISTINCT day) FROM daily WHERE state='ok' AND day BETWEEN ? AND ?", (rw["a_from"], rw["a_to"])).fetchone()
            bv = round((rb[0] or 0) / rb[1], 1) if rb[1] else None; av = round((ra[0] or 0) / ra[1], 1) if ra[1] else None
            groups[0]["readers"] = dict(metric="readers", before=bv, after=av, change_pct=pct(bv, av) if bv and av is not None else None,
                                        verdict=verdict("readers", bv, av, rw["n"]), window=rw)
    out["groups"] = dict(window=w, groups=groups)

    # 2. winners and losers since each page's own main change (Google impressions per day)
    moves = []
    for p in changed:
        pw_ = gwin(D(main[p][:10]), last, lastfinal)
        if not pw_:
            continue
        b, a = gsum(srch[p], pw_["b_from"], pw_["b_to"]), gsum(srch[p], pw_["a_from"], pw_["a_to"])
        n = pw_["n"]
        rb = c.execute("SELECT avg(readers) FROM daily WHERE path=? AND state='ok' AND day BETWEEN ? AND ?", (p, pw_["b_from"], pw_["b_to"])).fetchone()[0]
        ra = c.execute("SELECT avg(readers) FROM daily WHERE path=? AND state='ok' AND day BETWEEN ? AND ?", (p, pw_["a_from"], min(pw_["a_to"], iso(newest_ok)))).fetchone()[0]
        moves.append(dict(path=p, slug=slug.get(p), change=main[p][:10], days=n, provisional_days=pw_["prov"],
                          impressions_per_day=[round(b["impressions"] / n, 1), round(a["impressions"] / n, 1)],
                          clicks_per_day=[round(b["clicks"] / n, 2), round(a["clicks"] / n, 2)],
                          position=[b["position"], a["position"]],
                          readers_per_day=[round(rb, 1) if rb is not None else None, round(ra, 1) if ra is not None else None],
                          verdict=verdict("impressions", b["impressions"] / n, a["impressions"] / n, n, pw_["prov"]),
                          delta=round((a["impressions"] - b["impressions"]) / n, 1)))
    moves.sort(key=lambda m: m["delta"], reverse=True)
    out["winners"] = [m for m in moves if m["delta"] > 0][:6]
    out["losers"] = [m for m in moves if m["delta"] < 0][::-1][:6]
    out["verdict_counts"] = {k: sum(1 for m in moves if m["verdict"] == k) for k in ("better", "worse", "no clear change", "too early")}

    # 3. queries and countries before vs after (top 10 per page and for the site, Google windows split at the first change)
    qs = {"before": defaultdict(lambda: [0, 0, 0.0]), "after": defaultdict(lambda: [0, 0, 0.0])}
    cs = {"before": {}, "after": {}}
    if w:
        for side, frm, to in (("before", w["b_from"], w["b_to"]), ("after", w["a_from"], w["a_to"])):
            for scope, kind, name, cl, im, po in c.execute(
                    "SELECT scope, kind, name, clicks, impressions, position FROM search_window_top WHERE frm=? AND til=?", (frm, to)):
                if kind == "query" and scope != "*":
                    m = qs[side][name]; m[0] += cl or 0; m[1] += im or 0; m[2] += (po or 0) * (im or 0)
                elif kind == "country" and scope == "*":
                    cs[side][name] = dict(clicks=cl, impressions=im, position=po)
    def qrow(name, m):
        return dict(query=name, clicks=m[0], impressions=m[1], position=round(m[2] / m[1], 1) if m[1] else None)
    bq, aq = qs["before"], qs["after"]
    out["queries"] = dict(
        note="Searches that led to the changed pages (Google's top 10 per page, root copy). 'New' can mean a search entered a page's top 10. Moved = both windows, 10+ impressions each.",
        new=sorted((qrow(k, v) for k, v in aq.items() if k not in bq), key=lambda r: -r["impressions"])[:10],
        gone=sorted((qrow(k, v) for k, v in bq.items() if k not in aq), key=lambda r: -r["impressions"])[:10],
        moved=sorted((dict(query=k, before=qrow(k, bq[k])["position"], after=qrow(k, aq[k])["position"],
                           impressions=[bq[k][1], aq[k][1]]) for k in aq if k in bq and bq[k][1] >= 10 and aq[k][1] >= 10),
                     key=lambda r: -abs((r["after"] or 0) - (r["before"] or 0)))[:10])
    n = w["n"] if w else 1
    # Google lists only the top 10 countries per window: a country missing from one window is unknown there, not 0
    both = set(cs["before"]) & set(cs["after"])
    out["countries"] = sorted((dict(country=k, impressions_per_day=[round(cs["before"][k]["impressions"] / n, 1), round(cs["after"][k]["impressions"] / n, 1)],
                                    clicks=[cs["before"][k]["clicks"], cs["after"][k]["clicks"]],
                                    change_pct=pct(cs["before"][k]["impressions"], cs["after"][k]["impressions"]),
                                    verdict=verdict("impressions", cs["before"][k]["impressions"] / n, cs["after"][k]["impressions"] / n,
                                                    n, w["prov"] if w else 0))
                               for k in both), key=lambda r: -max(r["impressions_per_day"]))
    out["countries_note"] = ("Site-wide, Google's top 10 countries in each window; only countries in both windows are compared. "
                             "Left the top 10: " + (", ".join(sorted(k.upper() for k in set(cs["before"]) - both)) or "none") +
                             ". Entered it: " + (", ".join(sorted(k.upper() for k in set(cs["after"]) - both)) or "none") + ".")

    # 4. AI assistants asking about our pages (Skald, tracked pages, whole days)
    ai_days = c.execute("SELECT day, sum(ai_asked), sum(ai_training) FROM daily WHERE state='ok' GROUP BY day ORDER BY day").fetchall()
    rw = rwin(S, newest_ok)
    ai = dict(daily=[[d, a or 0, t or 0] for d, a, t in ai_days])
    if rw:
        def side(frm, to):
            tot, who = 0, defaultdict(int)
            for a, js in c.execute("SELECT ai_asked, assistants FROM daily WHERE state='ok' AND day BETWEEN ? AND ?", (frm, to)):
                tot += a or 0
                for k, v in json.loads(js or "{}").items():
                    if isinstance(v, (int, float)): who[k] += v
            return tot, dict(sorted(who.items(), key=lambda x: -x[1]))
        tb, wb = side(rw["b_from"], rw["b_to"]); ta, wa = side(rw["a_from"], rw["a_to"])
        ai.update(window=rw, before_per_day=round(tb / rw["n"], 1), after_per_day=round(ta / rw["n"], 1),
                  verdict=verdict("readers", tb / rw["n"], ta / rw["n"], rw["n"]), assistants_before=wb, assistants_after=wa)
    out["ai"] = ai

    # 5. bounce before vs after each page's main change (7-day windows, Skald page journeys)
    bl = {"before": [0, 0], "after": [0, 0]}; per = []
    for p in changed:
        r = {s: c.execute("SELECT visits, landed, left_site, frm, til FROM bounce_window WHERE path=? AND change_at=? AND win=7 AND side=?",
                          (p, main[p], s)).fetchone() for s in ("before", "after")}
        if not r["after"] or not r["before"]:
            continue
        for s in ("before", "after"):
            v, l, left = r[s][:3]; bl[s][0] += l; bl[s][1] += max(0, l - (v - left))
        per.append(p)
    bounce_b = round(100 * bl["before"][1] / bl["before"][0], 1) if bl["before"][0] else None
    bounce_a = round(100 * bl["after"][1] / bl["after"][0], 1) if bl["after"][0] else None
    out["bounce"] = dict(pages=len(per), landed=[bl["before"][0], bl["after"][0]], bounce=[bounce_b, bounce_a],
                         note="Up to 7 days each side of each page's main change, from Skald's page journeys; after windows are still filling.",
                         verdict=verdict("bounce", bounce_b, bounce_a, 7 if per else 0, 0, landings=(bl["before"][0], bl["after"][0])))
    after_days = [c.execute("SELECT til, frm FROM bounce_window WHERE path=? AND change_at=? AND win=7 AND side='after'", (p, main[p])).fetchone() for p in per]
    if after_days:
        n_after = min((D(t) - D(f)).days + 1 for t, f in after_days)
        out["bounce"]["min_after_days"] = n_after
        if n_after < 7:
            out["bounce"]["verdict"] = "too early"

    # 6. index status
    st = defaultdict(list)
    for p in pages:
        r = c.execute("SELECT status FROM search_index WHERE path=? ORDER BY inspected_at DESC LIMIT 1", (p,)).fetchone()
        st[r[0] if r else "not checked"].append(slug.get(p))
    si = c.execute("SELECT snapshot, data FROM site_index ORDER BY snapshot DESC LIMIT 1").fetchone()
    out["index"] = dict(tracked={k: len(v) for k, v in st.items()}, unknown=sorted(st.get("unknown_to_google", [])),
                        site=json.loads(si[1]) if si else None, site_snapshot=si[0] if si else None)

    # 7. the long-term trend: weekly clicks and impressions since Search Console history starts (weeks run Mon to Sun)
    weeks = defaultdict(lambda: [0, 0, 0, 0, 0, 0])
    for d, (cl, im, _p, fi) in srch["*"].items():
        wk = iso(D(d) - dt.timedelta(days=D(d).weekday()))
        weeks[wk][0] += cl; weeks[wk][1] += im; weeks[wk][4] += 1; weeks[wk][5] += 0 if fi else 1
    for p in changed:
        for d, (cl, im, _p, _f) in srch[p].items():
            wk = iso(D(d) - dt.timedelta(days=D(d).weekday()))
            weeks[wk][2] += cl; weeks[wk][3] += im
    out["weekly"] = [dict(week=k, clicks=v[0], impressions=v[1], changed_clicks=v[2], changed_impressions=v[3], days=v[4], provisional_days=v[5])
                     for k, v in sorted(weeks.items())]
    full = [x for x in out["weekly"] if x["days"] == 7 and not x["provisional_days"]]
    if len(full) >= 8:
        last4, prev4 = full[-4:], full[-8:-4]
        s = lambda xs, k: sum(x[k] for x in xs)
        out["trend"] = dict(last4_impressions=s(last4, "impressions"), prev4_impressions=s(prev4, "impressions"),
                            last4_clicks=s(last4, "clicks"), prev4_clicks=s(prev4, "clicks"),
                            impressions_change_pct=pct(s(prev4, "impressions"), s(last4, "impressions")),
                            clicks_change_pct=pct(s(prev4, "clicks"), s(last4, "clicks")),
                            weeks=[last4[0]["week"], last4[-1]["week"], prev4[0]["week"], prev4[-1]["week"]],
                            impressions_verdict=verdict("impressions", s(prev4, "impressions") / 28, s(last4, "impressions") / 28, 28),
                            clicks_verdict=verdict("clicks", s(prev4, "clicks") / 28, s(last4, "clicks") / 28, 28))
    per_day = defaultdict(set)
    for p, ch in changes.items():
        for live, _wb, _wa in ch:
            per_day[live[:10]].add(p)
    out["change_days"] = [dict(day=d, pages=len(v)) for d, v in sorted(per_day.items())]
    out["clusters"] = by_cluster(c, main, S, last, lastfinal)
    out["cross_check"] = cross_check(c, changed, lastfinal, newest_ok)
    out["time_on_page"] = time_on_page(c, changed, S)
    out["conversions"] = conversions_block(c, changed, main, S, newest_ok)
    import insights_more
    out["competing"] = insights_more.competing(c)
    out["ctr_check"] = insights_more.ctr_check(c, iso(lastfinal))
    out["experiments"] = insights_more.experiments(c, main)
    out["section_rules"] = SECTION_RULES
    return out


def by_cluster(c, main, S, last, lastfinal):
    """The site's sitemap clusters (clusters.py): Google before vs after each cluster's first change, same-length
    windows, change day skipped; a cluster with no change is compared around the site's first change instead."""
    try:
        import clusters as cmod
        cur, names, order = cmod.current(c), cmod.cluster_names(), cmod.ORDER
    except Exception:
        return []
    members = defaultdict(list)
    for path, cl, _t in cur:
        members[cl].append(path)
    srch = load_search(c, {p for p, _c, _t in cur})
    out = []
    for cl in sorted(members, key=lambda k: order.index(k) if k in order else 99):
        ps = members[cl]
        ch = [p for p in ps if p in main]
        d0 = min(D(main[p][:10]) for p in ch) if ch else S
        w = gwin(d0, last, lastfinal)
        r = dict(cluster=cl, name=names.get(cl) or cl, pages=len(ps), changed=len(ch), first_change=iso(d0) if ch else None, window=w)
        if w:
            tb = {"clicks": 0, "impressions": 0, "pw": 0.0}
            ta = dict(tb)
            for p in ps:
                for d, (cl_, im, pw, _f) in srch[p].items():
                    for tot, frm, to in ((tb, w["b_from"], w["b_to"]), (ta, w["a_from"], w["a_to"])):
                        if frm <= d <= to:
                            tot["clicks"] += cl_; tot["impressions"] += im; tot["pw"] += pw
            fin = lambda t: dict(clicks=t["clicks"], impressions=t["impressions"], ctr=round(t["clicks"] / t["impressions"], 5) if t["impressions"] else None,
                                 position=round(t["pw"] / t["impressions"], 2) if t["impressions"] else None)
            r["rows"] = compare(bundle(fin(tb), w["n"]), bundle(fin(ta), w["n"]), w["n"], w["prov"], ("clicks", "impressions", "position"))
            r["overall"] = overall([x["verdict"] for x in r["rows"]])
        else:
            r["overall"] = "Too early to tell"
        out.append(r)
    return out


GAP_NOTE = ("Google clicks and Skald's search-engine visits never match exactly: Skald also counts Bing, DuckDuckGo and "
            "other engines; Skald counts days in New York time and Google in Pacific time (3 hours apart); Google's last "
            "2 to 3 days are provisional; some visitors block Skald's tracking. A gap is unusual when it is 50% or more "
            "with at least 20 visits on the bigger side.")


def _median(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    m = len(xs) // 2
    return xs[m] if len(xs) % 2 else round((xs[m - 1] + xs[m]) / 2, 1)


def cross_check(c, changed, lastfinal, newest_ok):
    """Google clicks vs Skald search-engine visits vs all Skald readers, over the 7 whole days that both have final
    (ending at the older of Google's last final day and Skald's newest verified day), and the 7 days before."""
    try:
        import clusters as cmod
        everyone = [p for p, _c, _t in cmod.current(c)]
    except Exception:
        everyone = []
    tracked = {p for (p,) in c.execute("SELECT path FROM pages")}
    end = min(lastfinal, newest_ok)
    wins = [(end - dt.timedelta(days=6), end), (end - dt.timedelta(days=13), end - dt.timedelta(days=7))]
    def sums(paths, frm, to):
        f, t = iso(frm), iso(to)
        clicks = se = rd = 0
        for p in paths:
            clicks += c.execute("SELECT coalesce(sum(clicks),0) FROM search WHERE path=? AND day BETWEEN ? AND ?", (p, f, t)).fetchone()[0]
            if p in tracked:
                for r, src in c.execute("SELECT readers, sources FROM daily WHERE path=? AND state='ok' AND day BETWEEN ? AND ?", (p, f, t)):
                    rd += r or 0; se += json.loads(src or "{}").get("Search engine", 0)
            else:
                for r, e in c.execute("SELECT readers, se FROM site_daily WHERE path=? AND state='ok' AND day BETWEEN ? AND ?", (p, f, t)):
                    rd += r or 0; se += e or 0
        gap = round(100 * (se - clicks) / clicks, 1) if clicks else None
        return dict(google_clicks=clicks, skald_search_visits=se, skald_readers=rd, gap_pct=gap,
                    unusual=bool(gap is not None and abs(gap) >= 50 and max(clicks, se) >= 20))
    out = dict(window=dict(frm=iso(wins[0][0]), to=iso(wins[0][1])), prev_window=dict(frm=iso(wins[1][0]), to=iso(wins[1][1])), note=GAP_NOTE, scopes=[])
    for name, paths in ((f"Changed pages ({len(changed)})", changed), (f"All sitemap pages ({len(everyone)})", everyone)):
        if paths:
            out["scopes"].append(dict(name=name, last7=sums(paths, *wins[0]), prev7=sums(paths, *wins[1])))
    return out


def conversions_block(c, changed, main, S, newest_ok):
    """Leads and conversions (Skald, counts only): the whole site's completed actions a day before vs after our first
    change (same-length windows of whole days, change day skipped), and on the changed pages the visits proven to have
    sent a form, in each page's own 7-day windows around its main change (page_journeys)."""
    try:
        rows = dict((r[0], r[1:]) for r in c.execute("SELECT day, completed, leads, by_page FROM conversions_daily WHERE withheld=0"))
        st = c.execute("SELECT leads_available, leads_note FROM conversions_status ORDER BY at DESC LIMIT 1").fetchone()
    except Exception:
        return None
    if not rows:  # Skald is off or has no conversions yet: say nothing rather than "0 leads"
        return None
    w = rwin(S, min(newest_ok, dt.date.today() - dt.timedelta(days=1)))
    site = None
    if w:
        def side(frm, to):
            ds = [v for d, v in rows.items() if frm <= d <= to]
            return dict(days=len(ds), completed=sum(x[0] or 0 for x in ds), leads=sum(x[1] or 0 for x in ds))
        b, a = side(w["b_from"], w["b_to"]), side(w["a_from"], w["a_to"])
        per = lambda x: round(x["leads"] / x["days"], 2) if x["days"] else None
        site = dict(window=w, before=b, after=a, before_per_day=per(b), after_per_day=per(a),
                    verdict=verdict("leads", per(b), per(a), w["n"]))
    known = sum(sum(v for k, v in json.loads(r[2] or "{}").items() if k not in ("page not known", "Not recorded")) for r in rows.values())
    pl = {"before": 0, "after": 0, "visits_before": 0, "visits_after": 0, "pages": 0}
    for p in changed:
        got = c.execute("SELECT side, data FROM journey_window WHERE path=? AND change_at=? AND win=7", (p, main[p])).fetchall()
        if got:
            pl["pages"] += 1
        for sd, data in got:
            d = json.loads(data or "{}")
            pl[sd] += d.get("lead") or 0; pl["visits_" + sd] += d.get("visits") or 0
    return dict(site=site, total_leads=sum(r[1] or 0 for r in rows.values()), leads_tied_to_a_page=known,
                changed_pages_proven_leads=pl, leads_db_available=bool(st and st[0]), leads_db_note=st[1] if st else None,
                rule="Leads a day: the same 20% rule, and at least 0.3 a day; 7 whole days after the change at least.")


def time_on_page(c, changed, S):
    """Time on page (Skald, root copy): the median of the daily medians on the changed pages before and after the first
    change, with how many visits were measured, plus Skald's latest rolling median per page."""
    try:
        rows = c.execute("SELECT path, day, median_s, measured FROM time_on_page WHERE variant='root'").fetchall()
    except Exception:
        return None
    ch = set(changed)
    b = [r for r in rows if r[0] in ch and r[1] < iso(S)]
    a = [r for r in rows if r[0] in ch and r[1] > iso(S)]
    snap = c.execute("SELECT max(snapshot) FROM time_on_page_window").fetchone()[0]
    wins = c.execute("SELECT path, median_s, measured FROM time_on_page_window WHERE variant='root' AND snapshot=?", (snap,)).fetchall() if snap else []
    wch = [w for w in wins if w[0] in ch and w[1] is not None]
    return dict(rule="Median of the daily medians (seconds); Skald gives a day's median only once enough visits were measured. A visit is not measured when the page was its last.",
                before=dict(median_s=_median([r[2] for r in b]), measured=sum(r[3] or 0 for r in b), days=len({r[1] for r in b})),
                after=dict(median_s=_median([r[2] for r in a]), measured=sum(r[3] or 0 for r in a), days=len({r[1] for r in a})),
                latest=dict(snapshot=snap, pages_with_median=len(wch), median_of_page_medians=_median([w[1] for w in wch]),
                            measured=sum(w[2] or 0 for w in wch)))


def digest(ins, gu=None):
    """A compact version for the AI summary: only numbers the dashboard shows, plus the context for 'why':
    the days our changes went live and Google's own updates (Search Status Dashboard) since 8 weeks before them."""
    g = ins.get("groups", {})
    since = iso(D(ins["split"]) - dt.timedelta(days=56))
    gups = [dict(name=u["name"], kind=u["kind"], began=u["begin"][:10], ended=(u["end"] or "")[:10] or "still rolling out")
            for u in (gu or {}).get("updates", []) if (u["end"] or u["begin"])[:10] >= since and u["kind"] != "issue"]
    return dict(today=ins["built"][:10], rules=ins["rules"], split_day=ins["split"], last_google_day=ins["last_google_day"],
                last_final_google_day=ins["last_final_google_day"], changed_pages=ins["changed_pages"],
                window=g.get("window"), groups=g.get("groups"), page_verdicts=ins.get("verdict_counts"),
                winners=[{k: m[k] for k in ("slug", "change", "days", "impressions_per_day", "clicks_per_day", "position", "verdict")} for m in ins.get("winners", [])[:5]],
                losers=[{k: m[k] for k in ("slug", "change", "days", "impressions_per_day", "clicks_per_day", "position", "verdict")} for m in ins.get("losers", [])[:5]],
                queries={k: ins["queries"][k][:6] for k in ("new", "gone", "moved")}, countries=ins.get("countries", [])[:6], countries_note=ins.get("countries_note"),
                ai={k: v for k, v in ins.get("ai", {}).items() if k != "daily"}, bounce=ins.get("bounce"),
                index={k: v for k, v in ins.get("index", {}).items()}, trend=ins.get("trend"),
                last_weeks=ins.get("weekly", [])[-6:], our_change_days=ins.get("change_days"),
                cross_check=ins.get("cross_check"), time_on_page=ins.get("time_on_page"), conversions=ins.get("conversions"),
                competing_pages=[dict(search=x["query"], google_shows=x["google_prefers"].rstrip("/").rsplit("/", 1)[-1],
                                      should_own=(x["owner"] or "no page made for it").rstrip("/").rsplit("/", 1)[-1], impressions=x["impressions"], pages=len(x["pages"]))
                                 for x in (ins.get("competing") or {}).get("searches", [])[:8]],
                low_click_rate=[{k: x[k] for k in ("path", "impressions", "clicks", "expected_clicks", "position")}
                                for x in (ins.get("ctr_check") or {}).get("pages", [])[:8]],
                experiments_filled=dict(at_7_days=sum(1 for x in (ins.get("experiments") or {}).get("rows", []) if x["r7"]),
                                        at_14_days=sum(1 for x in (ins.get("experiments") or {}).get("rows", []) if x["r14"]),
                                        total=len((ins.get("experiments") or {}).get("rows", []))),
                clusters=[{k: x.get(k) for k in ("name", "pages", "changed", "first_change", "window", "rows", "overall")} for x in ins.get("clusters", [])],
                google_updates=gups if gu and gu.get("ok") else "could not read Google's Search Status Dashboard")
