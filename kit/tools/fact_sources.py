"""Fact sources: which web addresses are never a source, and which sentences of a page state a fact that needs one.

The owner's rule: every fact on a page (a number, a stat, a regulation, a study) is checked on its real web page, found
through Google, and recorded with the source address, a quote and the date read (research record, `growth research fact`).
A chat (ChatGPT, Perplexity, Gemini, Copilot, Claude) and a Google results page or AI Overview are never a source.

Used by `research.py` (refuses a banned address when a fact is filed) and by the gate check ev.fact-sources.
growth.json "research": {"fact_max_age_days": 90, "banned_sources": [...replaces the default list...],
"banned_sources_extra": [...added to it...]}. An entry is a host ("perplexity.ai", covers its subdomains) or a host and a
path ("google.com/search", "openai.com/chat")."""
from __future__ import annotations

import re
from urllib.parse import urlsplit

FACT_MAX_AGE_DAYS = 90

BANNED_SOURCES = ("chatgpt.com", "chat.openai.com", "openai.com/chat", "perplexity.ai", "gemini.google.com", "bard.google.com",
                  "copilot.microsoft.com", "claude.ai", "google.com/search")
_NAMES = {"chatgpt.com": "ChatGPT", "chat.openai.com": "ChatGPT", "openai.com/chat": "ChatGPT", "perplexity.ai": "Perplexity",
          "gemini.google.com": "Gemini", "bard.google.com": "Gemini", "copilot.microsoft.com": "Copilot", "claude.ai": "Claude",
          "google.com/search": "A Google results page or AI Overview"}


def research_cfg(cfg):
    return (cfg or {}).get("research") or {}


def max_age_days(cfg) -> int:
    try:
        return int(research_cfg(cfg).get("fact_max_age_days", FACT_MAX_AGE_DAYS))
    except (TypeError, ValueError):
        return FACT_MAX_AGE_DAYS


def banned_list(cfg) -> list[str]:
    r = research_cfg(cfg)
    base = r.get("banned_sources")
    base = list(BANNED_SOURCES) if base is None else [str(x) for x in base]
    return base + [str(x) for x in r.get("banned_sources_extra") or []]


def _split(entry: str):
    e = re.sub(r"^[a-z]+://", "", entry.strip().lower()).lstrip("/")
    host, _, path = e.partition("/")
    return host.removeprefix("www."), ("/" + path.strip("/")) if path.strip("/") else ""


def banned_entry(url, cfg=None) -> str | None:
    """The banned-list entry this web address falls under, or None. A host covers its subdomains; a path covers what is under it."""
    u = str(url or "").strip()
    if not u:
        return None
    parts = urlsplit(u if "://" in u else "https://" + u)
    host, path = (parts.hostname or "").lower().removeprefix("www."), "/" + (parts.path or "").strip("/").lower()
    for entry in banned_list(cfg):
        h, p = _split(entry)
        if not h or not (host == h or host.endswith("." + h)):
            continue
        if not p or path == p or path.startswith(p + "/"):
            return entry
    return None


def banned_problem(url, cfg=None) -> str | None:
    """A plain message when the address is a chat or a results page, else None."""
    entry = banned_entry(url, cfg)
    if not entry:
        return None
    name = _NAMES.get(entry)
    if name:
        return f"{name} is not a source: open the real page and quote it ({entry} is on the banned list)"
    return f"{entry} is not a source: open the real page and quote it (it is on the project's banned list)"


# ---- the stat sentences of a page -------------------------------------------------------------------------------------------
BLOCKS = {"p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "td", "th", "dd", "dt", "blockquote", "figcaption", "caption", "summary"}
BYLINE_CLS = re.compile(r"byline|author|posted|published|updated|post-meta|entry-meta|breadcrumb|copyright", re.I)
BYLINE_TEXT = re.compile(r"^\s*(by|posted|published|updated|last (updated|reviewed|modified)|reviewed by|written by|©|copyright)\b", re.I)
COPYRIGHT = re.compile(r"©|\bcopyright\b|\ball rights reserved\b", re.I)
UNITS = r"(?:year|month|week|day|hour|minute)s?"
NUM = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
STAT_PATTERNS = (
    ("regulation", re.compile(r"\b\d+\s+(?:CFR|C\.F\.R\.|U\.S\.C\.|USC)\b|\b(?:HIPAA|GDPR|CCPA)\s*§|§\s?\d[\d.()a-z-]*|\bHTI-\d\b|\b21st Century Cures\b", re.I)),
    ("percent", re.compile(rf"(?<![\w.])({NUM})\s?(?:%|percent\b)", re.I)),
    ("plus", re.compile(rf"(?<![\w.])({NUM})\+")),
    ("times", re.compile(rf"(?<![\w.])({NUM})\s?[x×](?![a-z0-9])", re.I)),
    ("duration", re.compile(rf"(?<![\w.])({NUM})[- ]{UNITS}\b", re.I)),
    ("year", re.compile(r"(?<![\w.$,])((?:19|20)\d{2})(?![\w,]\d|\d)")),
    ("count", re.compile(rf"(?<![\w.$,#-])((?:\d{{1,3}}(?:,\d{{3}})+|\d{{2,}})(?:\.\d+)?)\s+(?!(?:am|pm|and|or|of|to|in|on|at|by)\b)[a-z]{{3,}}", re.I)),
    ("source", re.compile(r"\baccording to\b|(?<!case )(?<!case-)\bstud(?:y|ies)\b|\bsurvey(?:s|ed)?\b|\breports? (?:that|shows?|showed|found|says|stated)\b|\b(?:annual|industry) reports?\b", re.I)),
)
MONEY_RE = None  # filled lazily from research.MONEY


def _money():
    global MONEY_RE
    if MONEY_RE is None:
        import research
        MONEY_RE = research.MONEY
    return MONEY_RE


SENTENCE_MIN_WORDS = 8          # "study", "survey" and "report" name a source only inside a sentence of at least this many words


# Postal addresses and phone numbers hold numbers that are no stat: a street number, a ZIP code, a phone number.
CONTACT_PATTERNS = (
    re.compile(r"\+\d[\d\s().-]{7,}\d"),                                         # +1 (623) 555-0100, +44 20 555 0100
    re.compile(r"\(\d{3}\)\s?\d{3}[-.\s]\d{4}"),                                  # (623) 555-0100
    re.compile(r"(?<![\w.])\d{3}[-.\s]\d{3}[-.\s]\d{4}(?![\w])"),                  # 623-555-0100
    re.compile(r"\b[A-Z]{2}\s+\d{5}(?:-\d{4})?\b"),                                 # AZ 85201 (state code, then a US ZIP)
    re.compile(r"\b[A-Z]\d[A-Z]\s?\d[A-Z]\d\b"),                                    # K1A 0B1 (Canadian postal code)
    re.compile(r"\b\d{1,6}\s+(?:[A-Za-z.]+\s+){0,3}?(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Dr|Drive|Ln|Lane|Way|Ct|Court|Pl|Place|Pkwy|Parkway|Hwy|Highway)\b\.?"),  # 222 East Main St
    re.compile(r"\b(?:Suite|Ste|Unit|Floor|Room|Rm)\.?\s*#?[\w-]+", re.I),                  # Suite B-2, Suite 200
)


def without_contact(sentence: str) -> str:
    """The sentence with postal addresses and phone numbers blanked (same length), so their numbers are never read as stats."""
    for rx in CONTACT_PATTERNS:
        sentence = rx.sub(lambda m: " " * len(m.group(0)), sentence)
    return sentence


def page_sentences(root, domx) -> list[tuple[str, bool]]:
    """[(sentence, is_prose)] of the page's main text: no nav, header or footer chrome, no breadcrumb, no byline, no copyright
    line, no hidden text, and nothing that is only link text (a sitemap list, a menu). A heading is not prose."""
    main = domx.main(root)
    picked = []
    for n in main.iter():
        if n.tag not in BLOCKS or domx.in_chrome(n):
            continue
        if any(a.tag == "address" for a in [n, *n.ancestors()]):
            continue                        # a postal address: street number, ZIP and phone are no stats
        if any(a.tag == "time" or BYLINE_CLS.search(a.get("class") or "") or BYLINE_CLS.search(a.get("id") or "") for a in [n, *n.ancestors()]):
            continue
        if any(c is not n and c.tag in BLOCKS for c in n.iter()):
            continue                        # an outer block (a list item that holds paragraphs): its inner blocks are read instead
        t = domx.text(n)
        for a in n.iter():
            if a.tag == "a" and (a.get("href") or "").strip().lower().startswith("tel:") and domx.text(a):
                t = t.replace(domx.text(a), " ")          # a phone link is no stat
        links = " ".join(domx.text(a) for a in n.iter() if a.tag == "a")
        if links and re.sub(r"\W+", "", links) == re.sub(r"\W+", "", t):
            continue                        # only link text: a menu or sitemap entry names a section, it states no fact
        if t and not (BYLINE_TEXT.match(t) and len(t) < 90):
            picked.append((t, not n.tag.startswith("h") or len(n.tag) != 2))
    if not picked:
        picked = [(domx.text(main), True)]
    out = []
    for t, prose in picked:
        for s in re.split(r"(?<=[.!?])\s+(?=[A-Z\"“(])", t):
            s = s.strip()
            if s and not COPYRIGHT.search(s):
                out.append((s, prose))
    return out


def num_key(s) -> str | None:
    m = re.search(NUM, str(s))
    if not m:
        return None
    n = m.group(0).replace(",", "")
    return n.rstrip("0").rstrip(".") if "." in n else n


def numbers_in(text: str) -> set[str]:
    """Every number written in the text, 1,000 and 1000 alike, 12.50 and 12.5 alike."""
    t = re.sub(r"(?<=\d),(?=\d{3})", "", str(text))
    return {num_key(m.group(0)) for m in re.finditer(r"\d+(?:\.\d+)?", t)}


DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.? \d{1,2},? \d{4}\b|\b\d{1,2} (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]* \d{4}\b")


def stats_in(sentence: str, prose: bool = True) -> list[dict]:
    """[{text, num, kind}] for every stat in one sentence (a sentence with a stat word but no number has num None).
    A full date ("2026-11-10", "Nov 10, 2026") is a date, not a stat, and is left out."""
    out, spans = [], []
    sentence = without_contact(DATE.sub(lambda m: " " * len(m.group(0)), sentence))

    def add(kind, m, num):
        if any(m.start() < e and s < m.end() for s, e in spans) and kind in ("year", "count", "duration"):
            return
        spans.append((m.start(), m.end()))
        out.append({"text": re.sub(r"\s+", " ", m.group(0)).strip(), "num": num, "kind": kind})
    for m in _money().finditer(sentence):
        add("money", m, num_key(m.group(0)))
    for kind, rx in STAT_PATTERNS:
        for m in rx.finditer(sentence):
            if kind == "source" and not (prose and len(sentence.split()) >= SENTENCE_MIN_WORDS):
                continue                    # a label or heading that is just a name ("Case Studies") is not a claim
            if kind in ("regulation", "source"):
                add(kind, m, num_key(m.group(0)) if kind == "regulation" else None)
            else:
                add(kind, m, num_key(m.group(1)))
    return out


def page_stats(root, domx) -> list[dict]:
    """[{sentence, stats}] for each sentence that holds at least one stat."""
    res = []
    for s, prose in page_sentences(root, domx):
        st = stats_in(s, prose)
        if st:
            res.append({"sentence": s, "stats": st})
    return res


# ---- ours: the project's own claims ---------------------------------------------------------------------------------------
NEVER_LINE = re.compile(r"\bnever\b|\bdo not\b|\bdon'?t\b|\bno claims?\b|\bmay not\b|\bnot allowed\b|\bbanned\b|\bforbidden\b", re.I)


def own_claims_text(project, rec=None, cfg=None) -> str:
    """The text the project may state as its own: the lines of BRAND.md that are not a 'never ...' line, the strings in
    growth.json research.own_claims, and the record's other_numbers rows (a number listed there with a why)."""
    parts = []
    try:
        for ln in (project / "BRAND.md").read_text().splitlines():
            if ln.strip() and not NEVER_LINE.search(ln):
                parts.append(ln)
    except (OSError, AttributeError):
        pass
    parts += [str(x) for x in research_cfg(cfg).get("own_claims") or []]
    for o in (rec or {}).get("other_numbers") or []:
        if isinstance(o, dict):
            parts.append(f"{o.get('value', '')} {o.get('what', '')} {o.get('why', '')}")
    t = "\n".join(parts).lower()
    return re.sub(r"(?<=\d),(?=\d{3})", "", re.sub(r"[-–—]", " ", t))


def is_ours(stat: dict, own_text: str) -> bool:
    """A stat is ours when its number, with the same unit word, is written in BRAND.md (a line that is not a 'never' line)."""
    if not own_text:
        return False
    if stat["num"] is None:
        return stat["text"].lower() in own_text
    after = re.sub(rf"^.*?{re.escape(stat['num'])}", "", re.sub(r"(?<=\d),(?=\d{3})", "", stat["text"].lower()).replace("$", ""), count=1).strip(" -+x×")
    stem = re.sub(r"s$", "", after.split(" ")[0]) if after else ""
    pre = r"\$\s?" if stat["kind"] == "money" else ""
    return bool(re.search(rf"(?<![\d.]){pre}{re.escape(stat['num'])}(?![\d])[\s-]*" + (re.escape(stem[:5]) if stem and stat["kind"] not in ("money", "regulation") else ""), own_text))


# ---- the research record's fact rows ---------------------------------------------------------------------------------------
def row_problem(f, today, cfg=None) -> str | None:
    """Why a fact row does not count as a source (None when it does): banned source, not raw or browser, no address, stale, future."""
    import research
    if not isinstance(f, dict):
        return "not a fact row"
    url = str(f.get("source_url") or "")
    if not url.startswith(("http://", "https://")):
        return "no web address as the source"
    b = banned_problem(url, cfg)
    if b:
        return b
    if f.get("how_read") not in research.HOW_OK:
        return f"read by '{f.get('how_read')}': only browser or raw counts"
    d = research.day(f.get("read_on"))
    days = max_age_days(cfg)
    if d is None:
        return "no read_on date"
    if d > today:
        return f"read_on {f.get('read_on')} is after today"
    if (today - d).days > days:
        return f"read {f.get('read_on')}, {(today - d).days} days ago (the limit is {days}); read the page again"
    return None


def _covers(f, st, sent) -> bool:
    """Does this fact row speak to this stat? A number: it is in the row's quote. No number: the stat's words are in the
    quote or value, or the row's value is in the sentence."""
    if st["num"] is not None:
        return st["num"] in numbers_in(f.get("quote", ""))
    flat = lambda x: re.sub(r"\W+", " ", str(x).lower()).strip()
    val = flat(f.get("value", ""))
    return flat(st["text"]) in flat(f.get("quote", "")) + " " + val or (len(val) >= 4 and val in flat(sent))


def stat_problems(stats_by_sentence, rec, own_text, today, cfg=None) -> list[str]:
    """One line per unsourced stat, with its sentence. A stat is covered when it is ours (BRAND.md) or a fact row has its
    number in its quote and passes row_problem. A stat with no number (a study, a regulation name) needs a row whose value
    or quote holds the stat's words."""
    rows = [f for f in (rec or {}).get("vendor_facts") or [] if isinstance(f, dict)]
    out = []
    for item in stats_by_sentence:
        sent = item["sentence"]
        for st in item["stats"]:
            if is_ours(st, own_text):
                continue
            hits = [f for f in rows if _covers(f, st, sent)]
            bad = [row_problem(f, today, cfg) for f in hits]
            if any(b is None for b in bad):
                continue
            why = ("no fact row has it in its quote" if not hits else "; ".join(dict.fromkeys(b for b in bad if b)))
            out.append(f"'{st['text']}' in \"{sent[:160]}{'…' if len(sent) > 160 else ''}\": {why}")
    return out
