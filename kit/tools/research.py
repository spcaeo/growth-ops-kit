#!/usr/bin/env python3
"""The structured research record of one page: research the gate READS, not paperwork (#53).

One JSON file per page, research/<key>-record.json. The brief and the plan are generated from it, the gate checks the
page against it, and the measure step (growth measure) uses its baseline numbers before and after a release.

  growth research init <path> --key K                       start a record (empty sections)
  growth research search <path> --key K [--days 28]         fill the search section from the page tracker (window recorded)
  growth research paa <path> --key K "question" --source <URL or saved file> [--declined "reason"] [--answered-in "words"]
  growth research ai <path> --key K --engine E --market US --query "..." --summary "..." --source <saved answer file or URL> [--seen-on D]
  growth research fact <path> --key K --vendor V --fact "..." --value '$12' --view Monthly --how raw|browser \\
        --source-url URL --quote "the vendor's own words" [--raw-file research/raw/x.txt] [--read-on D] [--shown-as "$12"]
                                                            --how raw needs --raw-file (growth vendor_page saves it): the
                                                            quote must be in it, its sha256 is stored
  growth research baseline <path> --key K [--refreeze --reason "..."]   freeze once; again only after growth approve baseline

Every row cites a source (a web address or a saved file), and no date may be after today (audit H9).
  growth research none <path> --key K paa|ai|vendor_facts "why there is none"
  growth research show|check|plan <path> --key K            print / check / write the plan generated from the record

Record layout (every date is YYYY-MM-DD):
  search        {scope: "page", source, window: {from, to}, definition, totals: {clicks, impressions, position},
                 queries: [{query, clicks, impressions, position}]}      the page's own numbers, never the site's
  site_search   the same shape with scope "site": site-wide numbers, kept apart so they are never shown as the page's
  ai_answers    [{engine, market, query, seen_on, summary}]           what an AI answer said when we looked
  paa           [{question, status: chosen|declined, reason, answered_in}]   People also ask questions
  vendor_facts  [{vendor, fact, value, shown_as, view, how_read: raw|browser|summary, source_url, quote, read_on}]
  *_none        a reason for an empty section ("paa_none": "no People also ask box for this search")
  other_numbers [{value, why}]  numbers on the page that are not a vendor fact (the business's own, a law's)
  baseline      the page's numbers before the change, taken from the search section when the baseline is frozen
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import atomic  # noqa: E402

SCHEMA = 1
HOW_OK = ("raw", "browser")                 # a summary tool is never the source of a number (#43)
HOW_ALL = HOW_OK + ("summary",)
SECTIONS = {"paa": "paa", "ai": "ai_answers", "vendor_facts": "vendor_facts"}
FACT_DAYS, SEARCH_DAYS, AI_DAYS = 30, 45, 45
FACT_KEYS = ("vendor", "fact", "value", "view", "how_read", "source_url", "quote", "read_on")


def record_path(project: Path, key: str) -> Path:
    return Path(project) / "research" / f"{key}-record.json"


def blank(page: str, key: str) -> dict:
    return {"schema": SCHEMA, "page": page, "key": key, "search": {}, "site_search": {}, "ai_answers": [], "paa": [],
            "vendor_facts": [], "other_numbers": [], "baseline": {}}


def load(project: Path, key: str) -> dict | None:
    p = record_path(project, key)
    try:
        d = json.loads(p.read_text())
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) else None


def save(project: Path, key: str, rec: dict) -> Path:
    p = record_path(project, key)
    atomic.write_json(p, rec, indent=1)
    return p


def settings(cfg: dict | None) -> dict:
    """growth.json "research": {"fact_days": 30, "search_days": 45, "ai_days": 45}"""
    r = (cfg or {}).get("research") or {}
    return {"fact_days": int(r.get("fact_days", FACT_DAYS)), "search_days": int(r.get("search_days", SEARCH_DAYS)),
            "ai_days": int(r.get("ai_days", AI_DAYS))}


def day(s):
    try:
        return dt.date.fromisoformat(str(s)[:10])
    except ValueError:
        return None


def age(s, today) -> int | None:
    d = day(s)
    return (today - d).days if d else None


def _project(project):
    if project:
        return Path(project)
    try:
        from config import find_project
        return find_project()
    except Exception:  # noqa: BLE001
        return None


def source_problem(src, project=None) -> str | None:
    """A row's source: a web address, or a saved file that exists in the project (by shape alone with no project)."""
    src = str(src or "").strip()
    if not src:
        return "no source (a web address or a saved file)"
    if src.startswith(("http://", "https://")):
        return None
    if project and not (Path(project) / src).is_file() and not Path(src).is_file():
        return f"source file {src} does not exist"
    return None if "." in Path(src).name else f"source '{src[:60]}' is neither a web address nor a file"


def raw_problem(f, project=None) -> str | None:
    """A vendor fact read 'raw' must carry the saved raw page (raw_file), its quote must be in it and its hash unchanged."""
    import hashlib
    rf = str(f.get("raw_file") or "")
    if not rf:
        return "read 'raw' but no raw_file (save the page with growth vendor_page and pass --raw-file)"
    if not project:
        return None
    path = Path(project) / rf
    if not path.is_file():
        return f"raw_file {rf} does not exist"
    data = path.read_bytes()
    if f.get("raw_sha256") and hashlib.sha256(data).hexdigest() != f["raw_sha256"]:
        return f"raw_file {rf} changed after the fact was filed"
    import html as _html
    text = norm(_html.unescape(re.sub(r"(?s)<(script|style)\b.*?</\1>|<[^>]+>", " ", data.decode(errors="replace"))))
    parts = [norm(x) for x in re.split(r"\.{3}|…", str(f.get("quote", "")))]      # a quote may skip words with "..."
    if not any(parts) or any(x and x not in text for x in parts):
        return f"the quote is not in {rf}"
    return None


# ---- reading the record ---------------------------------------------------------------------------------------------
def problems(rec, today: dt.date, cfg: dict | None = None, project=None) -> list[str]:
    """What is wrong with the record itself: missing sections, facts without proof, stale reads, summary-only numbers, dates
    after today, rows with no source (project: the folder saved sources are read from; default: the current project)."""
    if not isinstance(rec, dict):
        return ["no research record"]
    project = _project(project)
    s, out = settings(cfg), []
    for what, v in (("search window from", ((rec.get("search") or {}).get("window") or {}).get("from")),
                    ("search window to", ((rec.get("search") or {}).get("window") or {}).get("to")),
                    ("baseline window to", ((rec.get("baseline") or {}).get("window") or {}).get("to"))):
        if day(v) and day(v) > today:
            out.append(f"{what} {v} is after today: a date in the future is never fresh research")
    sr = rec.get("search") or {}
    w = sr.get("window") or {}
    if not (day(w.get("from")) and day(w.get("to"))) or not sr.get("queries"):
        out.append("search: no window (from, to) and queries; fill it with growth research search")
    elif sr.get("scope") != "page":
        out.append("search: scope must be 'page' (site-wide numbers go in site_search)")
    elif age(w.get("to"), today) is None or age(w["to"], today) > s["search_days"]:
        out.append(f"search: window ends {w.get('to')}, older than {s['search_days']} days")
    if rec.get("site_search") and rec["site_search"].get("scope") != "site":
        out.append("site_search: scope must be 'site'")
    for sec, rows, date_key, days in (("ai_answers", rec.get("ai_answers"), "seen_on", s["ai_days"]),
                                      ("paa", rec.get("paa"), None, 0), ("vendor_facts", rec.get("vendor_facts"), "read_on", s["fact_days"])):
        none = {"ai_answers": "ai_none", "paa": "paa_none", "vendor_facts": "vendor_facts_none"}[sec]
        if not rows and len(str(rec.get(none, "")).strip()) < 8:
            out.append(f"{sec}: no rows and no '{none}' reason (growth research none <path> --key K {sec} \"why\")")
        for i, r in enumerate(rows or []):
            if date_key and day(r.get(date_key)) and day(r[date_key]) > today:
                out.append(f"{sec}[{i}]: {date_key} '{r.get(date_key)}' is after today")
            elif date_key and (age(r.get(date_key), today) is None or age(r[date_key], today) > days):
                out.append(f"{sec}[{i}]: {date_key} '{r.get(date_key)}' missing or older than {days} days")
            if sec != "vendor_facts" and isinstance(r, dict):
                why = source_problem(r.get("source"), project)
                if why:
                    out.append(f"{sec}[{i}]: {why}")
    for i, f in enumerate(rec.get("vendor_facts") or []):
        miss = [k for k in FACT_KEYS if not str(f.get(k, "")).strip()]
        if miss:
            out.append(f"vendor_facts[{i}] ({f.get('vendor', '?')}): missing {', '.join(miss)}")
        elif f["how_read"] not in HOW_OK:
            out.append(f"vendor_facts[{i}] ({f['vendor']} {f['value']}): read by '{f['how_read']}'; a summary is not the source, "
                       "confirm it in the page's raw text or a real browser and record how_read raw|browser")
        elif not str(f["source_url"]).startswith(("http://", "https://")):
            out.append(f"vendor_facts[{i}]: source_url is not a web address")
        elif f["how_read"] == "raw" and raw_problem(f, project):
            out.append(f"vendor_facts[{i}] ({f['vendor']} {f['value']}): {raw_problem(f, project)}")
    for i, q in enumerate(rec.get("paa") or []):
        if q.get("status") not in ("chosen", "declined") or not str(q.get("question", "")).strip():
            out.append(f"paa[{i}]: needs a question and a status chosen|declined")
        elif q["status"] == "declined" and len(str(q.get("reason", "")).strip()) < 8:
            out.append(f"paa[{i}] '{q['question'][:50]}': declined with no reason")
    return out


# ---- the page against the record --------------------------------------------------------------------------------------
MONEY = re.compile(r"(?<![\w.])(?:(?:US|CA|AU|C|A)\s?)?([$€£])\s?(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?"
                   r"|(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?\s?(USD|CAD|EUR|GBP|AUD)\b")


def num_key(s) -> str | None:
    """'$1,200.50' -> '1200.5'; the number a money string or a fact value stands for. None when it holds no number."""
    m = re.search(r"(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?", str(s))
    if not m:
        return None
    frac = (m.group(2) or "").rstrip("0")
    return m.group(1).replace(",", "") + ("." + frac if frac else "")


def money_on_page(text: str) -> list[tuple[str, str]]:
    """[(as written, number key)] for every amount of money in the text."""
    return [(m.group(0).strip(), num_key(m.group(0))) for m in MONEY.finditer(text)]


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9$€£%. ]", " ", str(s).lower())).strip()


def vendor_number_problems(rec, text: str, today: dt.date, cfg: dict | None = None) -> list[str]:
    """Every amount of money on the page is a vendor fact row (or listed in other_numbers), read within fact_days; every
    other fact row whose words appear on the page is fresh too."""
    days = settings(cfg)["fact_days"]
    facts = [f for f in rec.get("vendor_facts") or [] if isinstance(f, dict)]
    known = {num_key(f.get("value")): f for f in facts if num_key(f.get("value"))}
    own = {num_key(o.get("value")) for o in rec.get("other_numbers") or [] if isinstance(o, dict)}
    out, seen = [], set()
    for raw, k in money_on_page(text):
        if not k or k in seen:
            continue
        seen.add(k)
        f = known.get(k)
        if k in own:
            continue
        if not f:
            out.append(f"'{raw}' is on the page but no vendor fact row has that value (add it with growth research fact, or list it in other_numbers with a why)")
        elif age(f.get("read_on"), today) is None or age(f["read_on"], today) > days:
            out.append(f"'{raw}' ({f.get('vendor')}, view {f.get('view')}) was read {f.get('read_on')}, older than {days} days")
    low = norm(text)
    for f in facts:
        shown = norm(f.get("shown_as") or "")
        if shown and shown in low and (age(f.get("read_on"), today) is None or age(f["read_on"], today) > days):
            out.append(f"'{f.get('shown_as')}' ({f.get('vendor')}) was read {f.get('read_on')}, older than {days} days")
    return out


def paa_problems(rec, text: str) -> list[str]:
    """Every chosen People-also-ask question is answered on the page: its words appear, or the words in answered_in do."""
    low = norm(text)
    out = []
    for q in rec.get("paa") or []:
        if not isinstance(q, dict) or q.get("status") != "chosen":
            continue
        question, mark = norm(q.get("question", "")), norm(q.get("answered_in", ""))
        if question and question in low:
            continue
        if len(mark) >= 12 and mark in low:
            continue
        out.append(f"'{str(q.get('question'))[:70]}' is chosen but neither the question nor its answered_in words are on the page")
    return out


def plan_markdown(rec) -> str:
    """The brief's research section, written from the record, so what the helper is told IS the research."""
    sr, w = rec.get("search") or {}, (rec.get("search") or {}).get("window") or {}
    t = sr.get("totals") or {}
    out = [f"## Research record for {rec.get('page')} (research/{rec.get('key')}-record.json)", "",
           f"Search Console, the page's own numbers, {w.get('from')} to {w.get('to')} ({sr.get('definition', 'definition not recorded')}): "
           f"{t.get('clicks')} clicks, {t.get('impressions')} impressions, position {t.get('position')}. "
           "The before and after of this job use these same numbers (growth measure).", "", "Target searches (top first):"]
    out += [f"- {q['query']}: {q.get('impressions')} impressions, position {q.get('position')}" for q in (sr.get("queries") or [])[:10]]
    out += ["", "People also ask. Answer every CHOSEN one on the page; the gate checks it:"]
    out += [f"- [{q.get('status')}] {q.get('question')}" + (f" (declined: {q.get('reason')})" if q.get("status") == "declined" else "")
            for q in rec.get("paa") or []] or [f"- none: {rec.get('paa_none', '')}"]
    out += ["", "AI answers seen:"]
    out += [f"- {a.get('engine')} ({a.get('market')}), {a.get('seen_on')}: {a.get('query')} -> {str(a.get('summary'))[:160]}"
            for a in rec.get("ai_answers") or []] or [f"- none: {rec.get('ai_none', '')}"]
    out += ["", "Vendor facts. A number about another product goes on the page ONLY as a row here, read in the view shown:"]
    out += [f"- {f.get('vendor')}: {f.get('fact')} = {f.get('value')} (view {f.get('view')}, read {f.get('read_on')} by {f.get('how_read')}, {f.get('source_url')})"
            for f in rec.get("vendor_facts") or []] or [f"- none: {rec.get('vendor_facts_none', '')}"]
    return "\n".join(out) + "\n"


def target_searches(rec, n=3) -> list[str]:
    return [q["query"] for q in ((rec.get("search") or {}).get("queries") or [])[:n] if q.get("query")]


# ---- the tracker's numbers -----------------------------------------------------------------------------------------------
def tracker_window(db: Path, path_key: str, frm: str, to: str) -> dict | None:
    """Daily Search Console rows summed over [frm, to] for one page path ('*' = the whole site), position weighted by impressions."""
    import sqlite3
    if not Path(db).exists():
        return None
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        cl, im, pw, n, fin = c.execute("SELECT sum(clicks), sum(impressions), sum(position * impressions), count(*), sum(final) FROM search "
                                       "WHERE path=? AND day BETWEEN ? AND ?", (path_key, frm, to)).fetchone()
    finally:
        c.close()
    if not n:
        return None
    return {"clicks": cl or 0, "impressions": im or 0, "position": round(pw / im, 1) if im and pw else None,
            "days_with_data": n, "final_days": fin or 0}


def tracker_queries(db: Path, path_key: str, n=25) -> list[dict]:
    import sqlite3
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = c.execute("SELECT query, clicks, impressions, position FROM search_queries WHERE path=? AND snapshot="
                         "(SELECT max(snapshot) FROM search_queries WHERE path=?) ORDER BY impressions DESC LIMIT ?",
                         (path_key, path_key, n * 2)).fetchall()
    finally:
        c.close()
    merged = {}
    for q, cl, im, po in rows:
        k = q[5:] if q.startswith("[us] ") else q       # the same search on a second copy of the page counts once
        m = merged.setdefault(k, [0, 0, 0.0])
        m[0] += cl or 0; m[1] += im or 0; m[2] += (po or 0) * (im or 0)
    out = [{"query": k, "clicks": v[0], "impressions": v[1], "position": round(v[2] / v[1], 1) if v[1] else None} for k, v in merged.items()]
    return sorted(out, key=lambda r: -r["impressions"])[:n]


def fill_search(rec, db: Path, path_key: str, days: int, today: dt.date, definition: str = "") -> bool:
    """Fill search (page) and site_search (site) for the last `days` settled days, from the tracker. False when it has none."""
    last = None
    import sqlite3
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True) if Path(db).exists() else None
    if c:
        last = c.execute("SELECT max(day) FROM search WHERE path=? AND final=1", (path_key,)).fetchone()[0]
        c.close()
    if not last:
        return False
    to = day(last)
    frm = to - dt.timedelta(days=days - 1)
    page = tracker_window(db, path_key, frm.isoformat(), to.isoformat())
    if not page:
        return False
    d = definition or f"page's own Search Console rows, all countries, {days} settled days; the page's old addresses added (growth.json page_aliases)"
    rec["search"] = {"scope": "page", "source": "page tracker (Search Console)", "window": {"from": frm.isoformat(), "to": to.isoformat()},
                     "definition": d, "totals": {k: page[k] for k in ("clicks", "impressions", "position")},
                     "queries": tracker_queries(db, path_key)}
    site = tracker_window(db, "*", frm.isoformat(), to.isoformat())
    if site:
        rec["site_search"] = {"scope": "site", "source": "page tracker (Search Console)", "window": rec["search"]["window"],
                              "definition": "the whole site, every page", "totals": {k: site[k] for k in ("clicks", "impressions", "position")}}
    return True


def future(s, today) -> str | None:
    d = day(s) if s else None
    return f"the date {s} is after today" if d and d > today else None


# ---- command line ------------------------------------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["init", "search", "paa", "ai", "fact", "none", "show", "check", "plan", "baseline"])
    ap.add_argument("path")
    ap.add_argument("rest", nargs="*")
    ap.add_argument("--key", required=True)
    ap.add_argument("--days", type=int, default=28)
    ap.add_argument("--declined", default="")
    ap.add_argument("--answered-in", default="")
    ap.add_argument("--refreeze", action="store_true")
    for f in ("source", "raw-file", "reason", "engine", "market", "query", "summary", "seen-on", "vendor", "fact", "value", "view", "how", "source-url", "quote", "read-on", "shown-as"):
        ap.add_argument("--" + f, default="")
    a = ap.parse_args(argv)
    from config import PROJECT
    with atomic.locked(record_path(PROJECT, a.key)):      # load, change and save of one record under one lock
        return _command(a)


def _command(a):
    from config import CFG, PROJECT
    import paths
    pk = paths.key(a.path)
    rec = load(PROJECT, a.key)
    today = dt.date.today()
    if a.cmd == "init":
        if rec:
            sys.exit(f"research/{a.key}-record.json exists; edit it with the other commands")
        print(f"wrote {save(PROJECT, a.key, blank(pk, a.key)).relative_to(PROJECT)}")
        return 0
    if rec is None:
        sys.exit(f"no record for {a.key}: growth research init {a.path} --key {a.key}")
    if a.cmd == "search":
        if not fill_search(rec, PROJECT / "page-tracker" / "tracker.db", pk, a.days, today):
            sys.exit("the page tracker has no settled Search Console days for this page (growth page_tracker sync)")
    elif a.cmd == "baseline":
        if not rec.get("search"):
            sys.exit("fill the search section first: growth research search")
        old = rec.get("baseline") or {}
        approval = None
        if old.get("frozen_on"):            # frozen once: again only with the owner's approval, used once (audit H9)
            if not (a.refreeze and len(a.reason.strip()) >= 10):
                sys.exit(f"the baseline was frozen on {old['frozen_on']}; re-freezing it needs --refreeze --reason \"why\" and the "
                         f"owner's approval first: growth approve baseline {a.key} --reason \"<the same reason>\"")
            import approvals
            st, e = approvals.status(PROJECT / "docs", "baseline", a.key, approvals.baseline_content(a.key, a.reason.strip()))
            used = {x.get("approval") for x in [old] + list(old.get("history") or [])}
            if st != "ok" or e.get("id") in used or str(e.get("at", "")) < str(old.get("frozen_at", "")):
                sys.exit("no fresh owner approval for this re-freeze: " + (approvals.explain(st, e, "the re-freeze", f"growth approve baseline {a.key} --reason \"...\"")
                         if st != "ok" else f"{e.get('id')} was already used or is older than the current baseline"))
            approval = e["id"]
        history = list(old.get("history") or []) + ([{k: v for k, v in old.items() if k != "history"}] if old else [])
        rec["baseline"] = {"frozen_on": today.isoformat(), "frozen_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
                           **{k: rec["search"][k] for k in ("window", "definition", "totals", "queries")},
                           "site_totals": (rec.get("site_search") or {}).get("totals"),
                           **({"approval": approval, "reason": a.reason.strip(), "history": history} if approval else {})}
        print("baseline frozen: growth measure compares against these numbers")
    elif a.cmd == "paa":
        q = " ".join(a.rest).strip()
        if not q:
            sys.exit("give the question")
        why = source_problem(a.source, PROJECT)
        if why:
            sys.exit(f"--source: {why} (where you saw the question: the results page address or a saved capture)")
        rec["paa"].append({"question": q, "status": "declined" if a.declined else "chosen", "reason": a.declined, "answered_in": a.answered_in,
                           "source": a.source})
    elif a.cmd == "ai":
        why = source_problem(a.source, PROJECT) or future(a.seen_on, today)
        if why:
            sys.exit(f"refused: {why} (save the AI's full answer to a file, e.g. with growth journal run, and pass it as --source)")
        row = {"engine": a.engine, "market": a.market, "query": a.query, "summary": a.summary, "seen_on": a.seen_on or today.isoformat(),
               "source": a.source}
        if (PROJECT / a.source).is_file():
            import hashlib
            row["source_sha256"] = hashlib.sha256((PROJECT / a.source).read_bytes()).hexdigest()
        rec["ai_answers"].append(row)
    elif a.cmd == "fact":
        row = {"vendor": a.vendor, "fact": a.fact, "value": a.value, "shown_as": a.shown_as or a.value, "view": a.view, "how_read": a.how,
               "source_url": a.source_url, "quote": a.quote, "read_on": a.read_on or today.isoformat()}
        bad = [k for k in FACT_KEYS if not str(row.get(k, "")).strip()]
        if bad or row["how_read"] not in HOW_ALL:
            sys.exit(f"a fact needs {', '.join(bad) or 'how_read raw|browser|summary'} (the vendor's own words in --quote, the view in --view)")
        if future(row["read_on"], today):
            sys.exit("refused: " + future(row["read_on"], today))
        if row["how_read"] == "raw":
            import hashlib
            row["raw_file"] = a.raw_file
            if a.raw_file and (PROJECT / a.raw_file).is_file():
                row["raw_sha256"] = hashlib.sha256((PROJECT / a.raw_file).read_bytes()).hexdigest()
            why = raw_problem(row, PROJECT)
            if why:
                sys.exit("refused: " + why)
        rec["vendor_facts"].append(row)
    elif a.cmd == "none":
        sec, why = (a.rest + [""])[0], " ".join(a.rest[1:])
        if sec not in SECTIONS:
            sys.exit("name the section: paa, ai or vendor_facts")
        rec[{"paa": "paa_none", "ai": "ai_none", "vendor_facts": "vendor_facts_none"}[sec]] = why
    elif a.cmd == "show":
        print(json.dumps(rec, indent=1, ensure_ascii=False))
        return 0
    elif a.cmd == "check":
        probs = problems(rec, today, CFG)
        print("\n".join(probs) or f"record OK: {len(rec.get('vendor_facts') or [])} vendor facts, {len(rec.get('paa') or [])} PAA questions")
        return 1 if probs else 0
    elif a.cmd == "plan":
        out = PROJECT / "research" / "plans" / f"{a.key}-from-research.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(plan_markdown(rec))
        pj = PROJECT / "research" / "plans" / f"{a.key}.json"
        def fill(plan):
            plan["target_searches"] = target_searches(rec)
            plan["research_paa"] = [q["question"] for q in rec.get("paa") or [] if q.get("status") == "chosen"]
        atomic.update_json(pj, fill, default={"page": pk, "goal": "", "folds": []}, indent=1)
        print(f"wrote {out.relative_to(PROJECT)} and target_searches in {pj.relative_to(PROJECT)}")
        return 0
    print(f"saved {save(PROJECT, a.key, rec).relative_to(PROJECT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
