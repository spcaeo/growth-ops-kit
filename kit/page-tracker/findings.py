"""Key findings (added 13 Nov 2026): 2 to 5 plain sentences at the top of Insights, of every cluster screen and of every
page screen. Built deterministically from the tracker's own computations (no AI): leads first, then search share
(competing pages, click-rate shortfall, Google before/after, index status), then engagement (time on page, AI
assistants, Google vs Skald), then context (Google updates in the window, too-early notes). Each finding: the
sentence with its numbers, a verdict word, a rank, and the dashboard state (URL keys) of the section that proves it.
Called from export.write; the result is data.json's `findings`."""
import datetime as dt
from collections import defaultdict

import insights as base

V = {"worse": "Worse", "better": "Better", "early": "Too early", "watch": "Watch", "fix": "Fix", "flat": "No clear change", "info": "Note", "yard": "Yardstick"}


def slug(p):
    return (p or "").rstrip("/").rsplit("/", 1)[-1] or "home"


def f(n, d=0):
    if n is None:
        return "–"
    return f"{n:,.{d}f}"


def day(s):
    return dt.date.fromisoformat(s[:10])


def short(d):
    d = d if isinstance(d, dt.date) else day(d)
    return d.strftime("%b ") + str(d.day)


def finding(rank, verdict, text, link):
    return dict(rank=rank, verdict=verdict, word=V[verdict], text=text, link=link)


def gs_sum(gs, frm, to):
    c = i = pw = 0; n = 0
    for d, cl, im, po, _f in gs or []:
        if frm <= d <= to:
            c += cl; i += im; pw += (po or 0) * im; n += 1
    return dict(clicks=c, impressions=i, position=round(pw / i, 1) if i else None, days=n)


def span(a, b):
    return short(a) if str(a)[:10] == str(b)[:10] else f"{short(a)}–{short(b)}"


def pct(b, a):
    return None if not b else round(100 * (a - b) / b)


def move(p):
    return "about the same" if p is None or abs(p) < 10 else (f"{abs(p)}% more" if p > 0 else f"{abs(p)}% fewer")


def build(ins, pages, clusters, gu, last, lastfinal, conv_days=()):
    """ins: insights.compute's output; pages / clusters: export's lists; gu: google_updates.export; last, lastfinal: dates."""
    comp = (ins.get("competing") or {}).get("searches", [])
    ctr = {x["path"]: x for x in (ins.get("ctr_check") or {}).get("pages", [])}
    conv = ins.get("conversions") or {}
    ups = [u for u in (gu or {}).get("updates", []) if u.get("kind") != "issue"]
    rolling = [u for u in ups if not u.get("end")]
    by_path = {p["path"]: p for p in pages}

    def update_in(frm, to):
        return [u for u in ups if u["begin"][:10] <= to and (not u.get("end") or u["end"][:10] >= frm)]

    def comp_sentence(x, rank):
        shown = next(p for p in x["pages"] if p["path"] == x["google_prefers"])
        own = next((p for p in x["pages"] if p["path"] == x["owner"]), None)
        t = (f"For the search \"{x['query']}\", Google mostly shows {slug(shown['path'])}: {f(shown['impressions'])} impressions at "
             f"position {shown['position']}. The page made for that search, {slug(own['path'])}, gets only {f(own['impressions'])} at "
             f"position {own['position']}. So our pages compete with each other.")
        c = ctr.get(shown["path"])
        if c:
            t += f" {slug(shown['path'])} also gets very few clicks: {c['clicks']}, where about {round(c['expected_clicks'])} would be normal for its position."
        return finding(rank, "fix", t, {"page": own["path"], "tab": "google"})

    def ctr_sentence(c, rank):
        return finding(rank, "fix", f"{slug(c['path'])} gets very few clicks from Google: {c['clicks']} from {f(c['impressions'])} impressions at "
                       f"position {c['position']}, where about {round(c['expected_clicks'])} would be normal for that position on this site. "
                       "Its title and description are the first thing to rewrite.", {"page": c["path"], "tab": "google"})

    def wrong_owner(paths=None):
        return [x for x in comp if x.get("owner") and x["owner"] != x["google_prefers"]
                and (paths is None or any(p["path"] in paths for p in x["pages"]))]

    # ---------- the whole site (Insights) ----------
    site = []
    days = (conv.get("site") or {})
    if conv.get("total_leads") is not None:
        cd = [(d[0], d[2]) for d in conv_days]
        byd = dict(cd)
        best = max(((d, v + byd.get((day(d) + dt.timedelta(days=1)).isoformat(), 0)) for d, v in cd), key=lambda x: x[1], default=None)
        t = f"Leads: {conv['total_leads']} forms on the whole site since Skald was switched on"
        one = max(cd, key=lambda x: x[1], default=None)
        if one and one[1] >= max(3, conv["total_leads"] * 0.5):
            t += f", {one[1]} of them on {short(one[0])} alone and {sum(v for d_, v in cd if d_ > one[0])} since"
        elif best and best[1] >= max(3, conv["total_leads"] * 0.5):
            t += f", {best[1]} of them on {span(best[0], day(best[0]) + dt.timedelta(days=1))}"
        t += (f"; Skald tied {conv.get('leads_tied_to_a_page', 0)} of them to a page, so no lead can be credited to a page or a change yet."
              if not conv.get("leads_tied_to_a_page") else ".")
        site.append(finding(100, "watch" if days.get("verdict") in (None, "too early") else ("better" if days["verdict"] == "better" else "worse"), t, {"view": "insights"}))
    w = wrong_owner()
    if w:
        site.append(comp_sentence(w[0], 90))
    for c in list(ctr.values())[:1]:
        if not w or c["path"] != w[0]["google_prefers"]:
            site.append(ctr_sentence(c, 80))
    g = (ins.get("groups") or {})
    ch = next((x for x in g.get("groups", []) if x["name"].startswith("Changed")), None)
    if ch and g.get("window"):
        r = {x["metric"]: x for x in ch["rows"]}
        wn = g["window"]
        v = r["impressions"]["verdict"]
        site.append(finding(70, "early" if v == "too early" else {"better": "better", "worse": "worse"}.get(v, "flat"),
                            f"Since our first changes on {short(ins['split'])}, the {ins['changed_pages']} changed pages get "
                            f"{move(round(r['impressions']['change_pct'] or 0))} Google impressions a day ({span(wn['b_from'], wn['b_to'])} vs "
                            f"{span(wn['a_from'], wn['a_to'])})" + (f"; {wn['prov']} of the after days are still provisional, so it is too early to call."
                                                                          if wn.get("prov") else "."), {"view": "google"}))
    unk = (ins.get("index") or {}).get("unknown") or []
    if unk:
        site.append(finding(75, "fix", f"{len(unk)} changed pages have a main address Google's URL Inspection does not know yet ({', '.join(unk[:3])}{' and more' if len(unk) > 3 else ''}): "
                            "ask Google to index them in Search Console.", {"view": "pages", "sort": "google"}))
    for u in rolling[:1]:
        same = u["begin"][:10] == ins.get("split")
        site.append(finding(20, "watch", f"Google's {u['name']} started on {short(u['begin'])}{', the same day as our first changes,' if same else ''} and is still rolling out: "
                            "rankings move for every site until it ends, so no change can be judged on rankings before then.", {"view": "google"}))
    out = {"site": sorted(site, key=lambda x: -x["rank"])[:5], "clusters": {}, "pages": {}}

    # ---------- clusters ----------
    crow = {x["cluster"]: x for x in ins.get("clusters", [])}
    for cl in clusters:
        paths = set(cl["paths"])
        items, r = [], crow.get(cl["id"]) or {}
        lead = sum((jw.get("lead") or 0) for p in pages if p["path"] in paths for jw in p.get("jw", []) if jw["side"] == "after" and jw["win"] == 7)
        if lead:
            items.append(finding(100, "better", f"{lead} visits that read pages in {cl['name']} were proven to have sent a form after our changes.", {"view": "clusters", "cluster": cl["id"]}))
        w = wrong_owner(paths)
        if w:
            items.append(comp_sentence(w[0], 90))
        cc = [c for c in ctr.values() if c["path"] in paths]
        if cc and (not w or cc[0]["path"] != w[0]["google_prefers"]):
            items.append(ctr_sentence(cc[0], 80))
        rows = {x["metric"]: x for x in r.get("rows", [])}
        if rows.get("impressions") and r.get("window"):
            wn, im = r["window"], rows["impressions"]
            v = im["verdict"]
            if r.get("changed"):
                t = (f"Since our first change in {cl['name']} on {short(r['first_change'])} ({r['changed']} of {r['pages']} pages changed), it gets "
                     f"{move(round(im['change_pct'] or 0))} Google impressions a day ({f(im['before'])} → {f(im['after'])}; {span(wn['b_from'], wn['b_to'])} vs "
                     f"{span(wn['a_from'], wn['a_to'])})" + ("; too early to call." if v == "too early" else "."))
            else:
                t = (f"We have not changed {cl['name']}. Over the same days as our first changes it got {move(round(im['change_pct'] or 0))} Google impressions "
                     f"a day ({f(im['before'])} → {f(im['after'])}): that is what Google did on its own.")
            items.append(finding(70, ("early" if v == "too early" else {"better": "better", "worse": "worse"}.get(v, "flat")) if r.get("changed") else "yard", t,
                                 {"view": "clusters", "cluster": cl["id"]}))
        un = [p for p in pages if p["path"] in paths and p.get("index") and p["index"]["status"] == "unknown_to_google"]
        if un:
            items.append(finding(75, "fix", f"{len(un)} of its pages have a main address Google does not know yet ({', '.join(slug(p['path']) for p in un[:3])}{' and more' if len(un) > 3 else ''}).",
                                 {"page": un[0]["path"], "tab": "google"}))
        if r.get("changed") and r.get("window"):
            for u in update_in(r["window"]["b_from"], r["window"]["a_to"])[:1]:
                items.append(finding(20, "watch", f"Google's {u['name']} ran during this comparison ({short(u['begin'])} → {short(u['end']) if u.get('end') else 'still rolling out'}), "
                                     "so part of any move is Google's.", {"view": "clusters", "cluster": cl["id"]}))
        if r.get("changed") and not r.get("window"):
            items.append(finding(15, "early", f"Our first change in {cl['name']} went live on {short(r['first_change'])}; Google has no whole day after it yet, so there is nothing to compare.",
                                 {"view": "clusters", "cluster": cl["id"]}))
        if len(items) < 2:
            frm28 = (last - dt.timedelta(days=27)).isoformat()
            g28 = gs_sum(cl["gs"], frm28, last.isoformat())
            items.append(finding(10, "info", f"Google, last 28 days: {cl['name']} got {f(g28['clicks'])} clicks from {f(g28['impressions'])} impressions across its {len(paths)} pages"
                                 + (f" (average position {g28['position']})." if g28["position"] else "."), {"view": "clusters", "cluster": cl["id"]}))
        if len(items) < 2:
            frm28 = (last - dt.timedelta(days=27)).isoformat()
            tops = sorted(((gs_sum(p["gs"], frm28, last.isoformat()), p) for p in pages if p["path"] in paths), key=lambda x: -x[0]["impressions"])
            if tops and tops[0][0]["impressions"]:
                g0, p0 = tops[0]
                items.append(finding(9, "info", f"Its strongest page in Google is {slug(p0['path'])}: {f(g0['impressions'])} impressions and {f(g0['clicks'])} clicks in the last 28 days.",
                                     {"page": p0["path"], "tab": "google"}))
        out["clusters"][cl["id"]] = sorted(items, key=lambda x: -x["rank"])[:5]

    # ---------- pages ----------
    for p in pages:
        items, path = [], p["path"]
        lb = sum(jw.get("lead") or 0 for jw in p.get("jw", []) if jw["change_at"] == p.get("main") and jw["win"] == 7 and jw["side"] == "before")
        la = sum(jw.get("lead") or 0 for jw in p.get("jw", []) if jw["change_at"] == p.get("main") and jw["win"] == 7 and jw["side"] == "after")
        if lb or la:
            items.append(finding(100, "better" if la > lb else "worse" if la < lb else "flat",
                                 f"Visits that read {slug(path)} and were proven to send a form: {lb} in the 7 days before its main change, {la} after.", {"page": path, "tab": "readers"}))
        for x in [x for x in comp if x.get("owner") and x["owner"] != x["google_prefers"] and any(q["path"] == path for q in x["pages"])][:1]:
            items.append(comp_sentence(x, 90))
        c = ctr.get(path)
        if c and not any(it["rank"] == 90 and slug(path) + " also gets" in it["text"] for it in items):
            items.append(ctr_sentence(c, 80))
        ix = p.get("index")
        if ix and ix.get("status") == "unknown_to_google":
            items.append(finding(85, "fix", (f"Google's URL Inspection does not know the main address of {slug(path)} yet" + (f", although it got {f(gs_sum(p['gs'], (last - dt.timedelta(days=27)).isoformat(), last.isoformat())['impressions'])} impressions in the last 28 days" if gs_sum(p['gs'], (last - dt.timedelta(days=27)).isoformat(), last.isoformat())['impressions'] else ", so it cannot rank") + ": ask for indexing in Search Console (URL Inspection)."), {"page": path, "tab": "google"}))
        elif ix and ix.get("last_crawl") and p.get("main") and ix["last_crawl"][:10] < p["main"][:10]:
            items.append(finding(60, "fix", f"Google last crawled {slug(path)} on {short(ix['last_crawl'])}, before its main change on {short(p['main'])}: "
                                 "its results still show the old version until Google crawls it again.", {"page": path, "tab": "google"}))
        if p.get("main"):
            d0 = day(p["main"])
            wn = base.gwin(d0, last, lastfinal, 7)
            if wn:
                b, a = gs_sum(p["gs"], wn["b_from"], wn["b_to"]), gs_sum(p["gs"], wn["a_from"], wn["a_to"])
                n = wn["n"]
                v = base.verdict("impressions", b["impressions"] / n, a["impressions"] / n, n, wn["prov"])
                t = (f"Since its main change on {short(d0)}, {slug(path)} gets {move(pct(b['impressions'], a['impressions']))} Google impressions a day "
                     f"({f(b['impressions'] / n)} → {f(a['impressions'] / n)}; {span(wn['b_from'], wn['b_to'])} vs {span(wn['a_from'], wn['a_to'])})")
                if v == "too early":
                    t += f"; too early to call: look again around {short(d0 + dt.timedelta(days=10))}."
                else:
                    t += f", and its position went from {b['position']} to {a['position']}."
                items.append(finding(70, "early" if v == "too early" else {"better": "better", "worse": "worse"}.get(v, "flat"), t, {"page": path, "tab": "impact"}))
                for u in update_in(wn["b_from"], wn["a_to"])[:1]:
                    items.append(finding(20, "watch", f"Google's {u['name']} ran during this comparison ({short(u['begin'])} → {short(u['end']) if u.get('end') else 'still rolling out'}), "
                                         "so part of any move is Google's.", {"page": path, "tab": "impact"}))
            else:
                items.append(finding(15, "early", f"The main change on {slug(path)} went live on {short(d0)}; Google has no whole day after it yet, so there is nothing to compare.", {"page": path, "tab": "impact"}))
        newest = max((d["day"] for d in p.get("days", []) if d.get("state") == "ok"), default=None)
        if newest:
            end = min(lastfinal.isoformat(), newest); frm = (day(end) - dt.timedelta(days=6)).isoformat()
            gc = gs_sum(p["gs"], frm, end)["clicks"]
            se = sum(d.get("se") or 0 for d in p.get("days", []) if d.get("state") == "ok" and frm <= d["day"] <= end)
            gap = pct(gc, se)
            if gap is not None and abs(gap) >= 50 and max(gc, se) >= 20:
                items.append(finding(30, "watch", f"Google counted {gc} clicks to {slug(path)} over {span(frm, end)}, but Skald saw {se} visits from search engines ({'+' if gap > 0 else ''}{gap}%): "
                                     "an unusually large gap; Bing and other engines, time zones or blocked tracking explain some of it.", {"page": path, "tab": "google"}))
        tw = (p.get("top") or {}).get("window")
        if tw and tw.get("median_s") is not None and (tw.get("measured") or 0) >= 5:
            items.append(finding(40, "info", f"Readers stay on {slug(path)} a median of {round(tw['median_s'])} seconds ({tw['measured']} visits measured over Skald's last {tw.get('days')} days).",
                                 {"page": path, "tab": "readers"}))
        ai = defaultdict(int)
        for d in p.get("days", []):
            if d["day"] >= (last - dt.timedelta(days=13)).isoformat():
                for k, v in (d.get("assistants") or {}).items():
                    ai[k] += v
        if sum(ai.values()) >= 2:
            items.append(finding(35, "info", f"AI assistants sent {sum(ai.values())} visitors to {slug(path)} in the last 14 days ({', '.join(f'{k} {v}' for k, v in sorted(ai.items(), key=lambda x: -x[1])[:3])}).",
                                 {"page": path, "tab": "readers"}))
        if len(items) < 2:
            g28 = gs_sum(p["gs"], (last - dt.timedelta(days=27)).isoformat(), last.isoformat())
            items.append(finding(10, "info", f"Google, last 28 days: {slug(path)} got {f(g28['clicks'])} clicks from {f(g28['impressions'])} impressions"
                                 + (f" at an average position of {g28['position']}." if g28["position"] else "."), {"page": path, "tab": "google"}))
        if len(items) < 2 and not p.get("main"):
            items.append(finding(5, "info", f"We have not changed {slug(path)} in the site's git history, so its numbers show what Google and readers do without us.",
                                 {"page": path, "tab": "google"}))
        out["pages"][path] = sorted(items, key=lambda x: -x["rank"])[:5]
    out["cluster_digests"] = {cl["id"]: dict(name=cl["name"], cluster=crow.get(cl["id"]), findings=[x["text"] for x in out["clusters"][cl["id"]]],
                                             competing=[dict(search=x["query"], google_shows=slug(x["google_prefers"]), should_own=slug(x["owner"]))
                                                        for x in wrong_owner(set(cl["paths"]))[:3]],
                                             google_updates=[dict(name=u["name"], began=u["begin"][:10], ended=(u.get("end") or "still rolling out")[:10]) for u in rolling])
                              for cl in clusters}
    return out
