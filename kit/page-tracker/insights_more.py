"""More insights (added 13 Nov 2026), called from insights.compute; the same verdict rules as insights.py.
- competing(c): searches where two or more of our pages get Google impressions (cannibalization), which page Google
  shows most, and which page should own the search, with a plain suggestion.
- ctr_check(c): pages whose click rate is far below what their positions usually get on this site (the site's own
  click-rate-by-position curve from its own Search Console days, no outside benchmark): title and description
  rewrite candidates, with the current title and description from the repo.
- experiments(c): the experiment log. One row per change: its aim (from the commit messages), an expectation (left
  for the lead), and the result filled in automatically once 7 and 14 whole, final Google days exist after it.
"""
import json, re, datetime as dt
from collections import defaultdict

import insights as base
import repo_meta

STOP = {"vs", "versus", "the", "a", "an", "for", "and", "or", "to", "of", "in", "is", "with", "best", "top", "which", "what",
        "how", "com", "2026", "2025", "free", "app", "software", "tool", "tools"}
INTENT = [("alternative", "alternatives"), ("competitor", "alternatives"), ("review", "review"), ("pricing", "review"),
          ("cost", "review"), ("price", "review"), (" vs ", "-vs-"), ("versus", "-vs-")]


INTENT_WORDS = {"alternative", "alternatives", "review", "reviews", "pricing", "price", "prices", "cost", "costs", "competitor",
                "competitors", "compared", "comparison", "vs"}


def _words(s):
    return [w for w in re.split(r"[^a-z0-9]+", s.lower()) if w and w not in STOP]


def owner_for(query, paths):
    """The page made for this search: its address holds the search's intent word (vs, alternatives, review, pricing)
    and its names (for a 'vs' search, every name), with the fewest other names. None when no page fits."""
    q = " " + query.lower() + " "
    want = next((part for word, part in INTENT if word in q), None)
    names = [w for w in _words(query) if w not in INTENT_WORDS]
    def score(p):
        parts = p.rstrip("/").rsplit("/", 1)[-1].split("-")
        hit = sum(1 for w in names if w in parts)
        extra = sum(1 for w in parts if w not in names and w not in INTENT_WORDS and w not in STOP)
        return (1 if want and want in "-".join(parts) else 0, hit, -extra)
    ok = [p for p in paths if score(p)[1] and (want != "-vs-" or score(p)[1] >= len(names))]
    return max(ok, key=score) if ok else None


def competing(c):
    snaps = [s for (s,) in c.execute("SELECT DISTINCT snapshot FROM search_queries ORDER BY snapshot")]
    if not snaps:
        return dict(searches=[], note="No search snapshot yet.")
    last = snaps[-1]
    rows = defaultdict(lambda: defaultdict(lambda: {"clicks": 0, "impressions": 0, "pw": 0.0}))
    hist = defaultdict(lambda: defaultdict(list))
    for path, snap, q, cl, im, po in c.execute("SELECT path, snapshot, query, clicks, impressions, position FROM search_queries WHERE path != '*'"):
        key = q[5:] if q.startswith("[us] ") else q
        if snap == last:
            r = rows[key][path]
            r["clicks"] += cl or 0; r["impressions"] += im or 0; r["pw"] += (po or 0) * (im or 0)
        hist[key][path].append([snap, im or 0, po])
    win = defaultdict(dict)  # before/after the first change: Google's top searches per page (search_window_top)
    for scope, frm, til, name, im, po in c.execute("SELECT scope, frm, til, name, impressions, position FROM search_window_top WHERE kind='query' AND scope != '*'"):
        key = name[5:] if name.startswith("[us] ") else name
        win[(key, scope)].setdefault(frm, [frm, til, im or 0, po])
    out = []
    for q, pages in rows.items():
        ps = [p for p, r in pages.items() if r["impressions"] > 0]
        if len(ps) < 2:
            continue
        items = []
        for p in ps:
            r = pages[p]
            items.append(dict(path=p, clicks=r["clicks"], impressions=r["impressions"],
                              position=round(r["pw"] / r["impressions"], 1) if r["impressions"] else None,
                              history=hist[q][p], windows=sorted(win.get((q, p), {}).values())))
        items.sort(key=lambda x: (-x["impressions"], x["position"] or 99))
        shown = items[0]["path"]
        owner = owner_for(q, ps)
        slug = lambda p: p.rstrip("/").rsplit("/", 1)[-1]
        others = [slug(x["path"]) for x in items if x["path"] != owner]
        if not owner:
            tip = f"No page of ours is made for \"{q}\" (a brand or broad search); nothing to fix, leave it to Google."
        elif owner == shown:
            tip = (f"Google already shows {slug(owner)} most. Let it own \"{q}\": link {', '.join(others)} to it with these words, "
                   f"and keep {'them' if len(others) > 1 else 'it'} on {'their' if len(others) > 1 else 'its'} own topic.")
        else:
            tip = (f"Google shows {slug(shown)} most, but {slug(owner)} is the page made for \"{q}\". Point {slug(shown)} to "
                   f"{slug(owner)} with a link using these words, and keep {slug(shown)} on its own topic.")
        out.append(dict(query=q, pages=items, google_prefers=shown, owner=owner, suggestion=tip,
                        impressions=sum(x["impressions"] for x in items)))
    out.sort(key=lambda x: -x["impressions"])
    return dict(snapshot=last, snapshots=len(snaps), searches=out[:60],
                note=("Google's top 10 searches per page (page copies added together), latest snapshot; the history grows by one "
                      "snapshot a day, and 'before/after' rows come from the windows around each page's first change. The owner is the "
                      "page whose address holds the search's intent (vs, alternatives, review or pricing) and names; Google's choice is "
                      "the page with the most impressions."))


BUCKETS = [(1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7), (7, 8), (8, 10), (10, 13), (13, 20), (20, 200)]


def ctr_check(c, last_final):
    lf = dt.date.fromisoformat(last_final)
    f90, f28 = (lf - dt.timedelta(days=89)).isoformat(), (lf - dt.timedelta(days=27)).isoformat()
    tot = {b: [0, 0] for b in BUCKETS}
    rows = c.execute("SELECT path, day, clicks, impressions, position FROM search WHERE path != '*' AND final=1 AND day BETWEEN ? AND ?",
                     (f90, last_final)).fetchall()
    bucket = lambda pos: next((b for b in BUCKETS if b[0] <= (pos or 199) < b[1]), BUCKETS[-1])
    for _p, _d, cl, im, po in rows:
        if im:
            t = tot[bucket(po)]; t[0] += cl or 0; t[1] += im
    curve = {b: (t[0] / t[1] if t[1] >= 300 else None) for b, t in tot.items()}
    page = defaultdict(lambda: {"clicks": 0, "impressions": 0, "pw": 0.0, "expected": 0.0})
    for p, d, cl, im, po in rows:
        if d < f28 or not im:
            continue
        x = page[p]; x["clicks"] += cl or 0; x["impressions"] += im; x["pw"] += (po or 0) * im
        cv = curve[bucket(po)]
        if cv is not None:
            x["expected"] += im * cv
    files = repo_meta.files()
    out = []
    for p, x in page.items():
        if x["impressions"] < 300 or x["expected"] < 5 or x["clicks"] >= 0.5 * x["expected"]:
            continue
        m = repo_meta.meta(files[p]) if p in files else {}
        out.append(dict(path=p, impressions=x["impressions"], clicks=x["clicks"], ctr=round(x["clicks"] / x["impressions"], 5),
                        position=round(x["pw"] / x["impressions"], 1), expected_clicks=round(x["expected"], 1),
                        ratio=round(x["clicks"] / x["expected"], 2), title=m.get("title"), description=m.get("description"),
                        file=files.get(p)))
    out.sort(key=lambda r: r["clicks"] - r["expected_clicks"])
    return dict(window=dict(frm=f28, to=last_final), curve_window=dict(frm=f90, to=last_final),
                curve=[dict(frm=b[0], to=b[1], ctr=round(curve[b], 5) if curve[b] is not None else None, impressions=tot[b][1]) for b in BUCKETS],
                pages=out[:40],
                rule=("A page is listed when its clicks over its last 28 final Google days are under half of what this site's own pages "
                      "usually get at the same positions (each day's impressions times the site's click rate at that day's position, "
                      "from the last 90 final days), with at least 300 impressions and 5 expected clicks."))


AIMS = [("cro", "CRO pass: more readers act (forms, calls)"), ("rebuild", "Rebuild: a deeper page for the buyer"),
        ("redesign", "Redesign of the page"), ("header", "New page header"), (" head ", "New page header"),
        ("verify", "Fixes after checks"), ("fix", "Fixes after checks"), ("title", "Title and description"),
        ("description", "Title and description"), ("link", "Internal links"), ("faq", "FAQ answers"), ("logo", "Tool logos"),
        ("pric", "Prices brought up to date"), ("schema", "Structured data"), ("jsonld", "Structured data")]


def aim_of(commits):
    text = " " + " ".join(x[8:] for x in commits).lower() + " "
    return next((a for k, a in AIMS if k in text), "Content update")


def experiments(c, main_of):
    c.execute("""CREATE TABLE IF NOT EXISTS experiments(path TEXT, sha TEXT, live_at TEXT, aim TEXT, expectation TEXT,
        r7 TEXT, r14 TEXT, filled7 TEXT, filled14 TEXT, PRIMARY KEY(path, sha))""")
    _lf = c.execute("SELECT max(day) FROM search WHERE path='*' AND final=1").fetchone()[0]
    lf = dt.date.fromisoformat(_lf) if _lf else dt.date.fromisoformat("1970-01-01")  # no Google days yet: nothing can fill in
    newest = c.execute("SELECT max(day) FROM daily WHERE state='ok'").fetchone()[0]
    newest = dt.date.fromisoformat(newest) if newest else lf
    srch = base.load_search(c, {p for (p,) in c.execute("SELECT path FROM pages")})
    now = dt.datetime.now().astimezone().isoformat(timespec="minutes")
    for path, sha, live, commits in c.execute("SELECT path, sha, live_at, commits FROM changes").fetchall():
        aim = aim_of(json.loads(commits or "[]"))
        old = c.execute("SELECT expectation, r7, r14, filled7, filled14 FROM experiments WHERE path=? AND sha=?", (path, sha)).fetchone()
        exp_, r7, r14, f7, f14 = old if old else (None, None, None, None, None)
        d0 = dt.date.fromisoformat(live[:10])
        for N in (7, 14):
            if (N == 7 and r7) or (N == 14 and r14) or (lf - d0).days < N:
                continue
            bf, bt, af, at = d0 - dt.timedelta(days=N), d0 - dt.timedelta(days=1), d0 + dt.timedelta(days=1), d0 + dt.timedelta(days=N)
            b, a = base.gsum(srch[path], base.iso(bf), base.iso(bt)), base.gsum(srch[path], base.iso(af), base.iso(at))
            rows = {r["metric"]: r for r in base.compare(base.bundle(b, N), base.bundle(a, N), N, 0, ("clicks", "impressions", "position"))}
            if (newest - d0).days >= N:
                rb = c.execute("SELECT avg(readers) FROM daily WHERE path=? AND state='ok' AND day BETWEEN ? AND ?", (path, base.iso(bf), base.iso(bt))).fetchone()[0]
                ra = c.execute("SELECT avg(readers) FROM daily WHERE path=? AND state='ok' AND day BETWEEN ? AND ?", (path, base.iso(af), base.iso(at))).fetchone()[0]
                rows["readers"] = dict(metric="readers", before=rb, after=ra, verdict=base.verdict("readers", rb, ra, N))
            res = json.dumps(dict(overall=base.overall([r["verdict"] for r in rows.values()]), window=[base.iso(bf), base.iso(at)],
                                  rows={k: dict(before=v["before"], after=v["after"], verdict=v["verdict"]) for k, v in rows.items()}))
            if N == 7:
                r7, f7 = res, now
            else:
                r14, f14 = res, now
        c.execute("INSERT OR REPLACE INTO experiments VALUES(?,?,?,?,?,?,?,?,?)", (path, sha, live, aim, exp_, r7, r14, f7, f14))
    c.commit()
    out = []
    for path, sha, live, aim, exp_, r7, r14, f7, f14 in c.execute("SELECT * FROM experiments ORDER BY live_at DESC"):
        d0 = dt.date.fromisoformat(live[:10])
        out.append(dict(path=path, sha=sha, live_at=live, aim=aim, expectation=exp_, main=live == main_of.get(path),
                        r7=json.loads(r7) if r7 else None, r14=json.loads(r14) if r14 else None,
                        due7=base.iso(d0 + dt.timedelta(days=7)), due14=base.iso(d0 + dt.timedelta(days=14))))
    return dict(rows=out, last_final=base.iso(lf) if _lf else None,
                rule="The result fills in by itself once 7 (and 14) whole, final Google days exist after the change (the change day left out, the same number of days before); the same verdict rules as the Impact tab. Expectations are added by the lead.")
