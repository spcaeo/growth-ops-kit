"""One fact in one place, and no internal wording on the page (2.8.0; rules 28 and 11).

words.fact-repeats: the same fact (a time, a price, a percent, a "50+") shown in three or more folds, or the same long
sentence in two folds. words.internal-labels: the team's own process words ("dossier", "fold plan", "this rebuild") that
reached the visible text. Both were found by an independent reviewer, by hand, round after round; now a program finds them.
Lists and limits come from growth.json "words" (repeat_ok, repeat_terms, repeat_folds, repeat_sentence, internal, internal_ok)."""
from __future__ import annotations

import re

from . import domx, mainwalk
from .c_words import wcfg
from .core import check, short

# ---- fact phrases ------------------------------------------------------------------------------------------------------
_N = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
_TO = r"\s*(?:to|-|–|—)\s*"
_UNIT = (r"business days?|working days?|calendar days?|hours?|hrs?|h|minutes?|mins?|seconds?|secs?|days?|weeks?|wks?|months?|mos?|"
         r"years?|yrs?|sprints?")
FACT = re.compile(
    rf"(?P<money>(?P<cur>[$€£])\s?(?P<ma>{_N})(?P<mak>\s?[KkMmBb](?![A-Za-z]))?(?P<map>\+)?"
    rf"(?:{_TO}[$€£]?\s?(?P<mb>{_N})(?P<mbk>\s?[KkMmBb](?![A-Za-z]))?(?P<mbp>\+)?)?)"
    rf"|(?<![\w.,$/])(?P<pa>{_N})(?:{_TO}(?P<pb>{_N}))?\s?(?:%|percent\b)"
    rf"|(?<![\w.,$/-])(?P<da>{_N})(?:{_TO}(?P<db>{_N}))?(?P<dp>\+)?\s*-?\s*(?P<du>{_UNIT})\b"
    rf"|(?<![\w.,$/])(?P<xa>{_N})\+(?![\w+])"
    rf"|(?<![\w.,$/])(?P<ka>\d+(?:\.\d+)?)(?P<kk>[KkMm])\+(?![\w+])"
    rf"|(?<![\w.,$/])(?P<ma2>\d+(?:\.\d+)?)[x×](?![A-Za-z0-9])")
UNIT_NAME = {"h": "hr", "hr": "hr", "hour": "hr", "min": "min", "minute": "min", "sec": "sec", "second": "sec", "wk": "week",
             "mo": "month", "yr": "year"}
# Offer promises that carry no number (growth.json words.repeat_terms adds the business's own).
DEFAULT_TERMS = [(r"free replacements?|replace(?:d|ment)? (?:at|for) no (?:extra |additional )?(?:cost|charge)|no[- ]cost replacements?",
                  "free replacement"),
                 (r"money[- ]back guarantee", "money-back guarantee"), (r"satisfaction guarantee", "satisfaction guarantee"),
                 (r"no lock[- ]in|cancel any ?time", "no lock-in")]


def _num(s):
    return s.replace(",", "")


def _unit(u):
    u = re.sub(r"\s+", " ", u.lower()).strip()
    parts = u.split(" ")
    last = parts[-1].rstrip("s") if parts[-1] not in ("hrs", "mos", "secs", "mins", "wks", "yrs") else parts[-1][:-1]
    last = UNIT_NAME.get(last, last)
    return " ".join(parts[:-1] + [last])


def fact_phrases(text):
    """[(canonical, as written)] for every fact in the text: money ("$30", "$50k-$2m+"), percent, a number with a time unit
    ("24 to 48 hours" and "24-48 h" are one fact: "24-48 hr"), "50+", "10k+", "3x". A bare number is never a fact."""
    out = []
    for m in FACT.finditer(text):
        g = m.groupdict()
        if g["money"]:
            a = f"{g['cur']}{_num(g['ma'])}{(g['mak'] or '').strip().lower()}{g['map'] or ''}"
            b = f"{g['cur']}{_num(g['mb'])}{(g['mbk'] or '').strip().lower()}{g['mbp'] or ''}" if g["mb"] else ""
            canon = a + ("-" + b if b else "")
        elif g["pa"]:
            canon = _num(g["pa"]) + ("-" + _num(g["pb"]) if g["pb"] else "") + "%"
        elif g["da"]:
            canon = _num(g["da"]) + ("-" + _num(g["db"]) if g["db"] else "") + (g["dp"] or "") + " " + _unit(g["du"])
        elif g["xa"]:
            canon = _num(g["xa"]) + "+"
        elif g["ka"]:
            canon = g["ka"] + g["kk"].lower() + "+"
        else:
            canon = g["ma2"] + "x"
        out.append((canon, m.group(0).strip()))
    return out


def term_patterns(ctx):
    """[(regex, canonical)]: the offer promises that count as facts: the kit's short list plus growth.json words.repeat_terms
    (a regex, or {"pattern": regex, "as": name})."""
    out = [(re.compile(p, re.I), c) for p, c in DEFAULT_TERMS]
    for e in wcfg(ctx, "repeat_terms", []) or []:
        pat, name = (e.get("pattern"), e.get("as")) if isinstance(e, dict) else (e, None)
        if pat:
            out.append((re.compile(pat, re.I), (name or str(pat)).lower()))
    return out


def facts_in(ctx, text):
    out = fact_phrases(text)
    for rx, canon in term_patterns(ctx):
        out += [(canon, m.group(0)) for m in rx.finditer(text)]
    return out


def allowed(ctx):
    """(facts that may repeat anywhere, {fact: folds where it is not counted}): growth.json words.repeat_ok, a fact as written
    ("4.8", "24 to 48 hours") or {"fact": "60 days", "folds": ["rules"]} when the same words mean something else in those folds (a legal
    notice period beside the support period). The call's length (words.call_minutes) is always allowed: every mention of the call must
    say the same minutes (rule 4), so it is repeated on purpose."""
    ok, ok_in = set(), {}
    for e in wcfg(ctx, "repeat_ok", []) or []:
        phrase, folds = (e.get("fact") or e.get("phrase") or "", e.get("folds")) if isinstance(e, dict) else (e, None)
        keys = {c for c, _ in fact_phrases(str(phrase))} or {re.sub(r"\s+", " ", str(phrase).lower()).strip()}
        for k in keys:
            if folds:
                ok_in.setdefault(k, set()).update(str(f) for f in folds)
            else:
                ok.add(k)
    if wcfg(ctx, "call_minutes"):
        ok.add(f"{wcfg(ctx, 'call_minutes')} min")
    return ok, ok_in


def _is_cta(n):
    cl = n.get("class")
    return n.tag in ("a", "button") and bool(re.search(r"(?:^|[\s_-])(btn|button|cta)(?:$|[\s_-])", cl))


def _is_reason(n):
    """The reason line under a call-to-action ("30-minute call, reply within 24 hours"): every ask carries one, on purpose. A short line only."""
    return len(domx.text(n)) <= 160 and any(re.search(r"(?:^|[-_])(?:reason|why)$", c) for c in n.get("class").split())


def _drop_for_facts(n):
    """A form's labels and choices, a button, a nav, a dialog, the sticky bar and a drawn example are no statement of fact."""
    return (n.tag in ("nav", "dialog", "form", "select", "option", "textarea", "button") or _is_cta(n) or _is_reason(n)
            or domx.has_cls(n, r"sticky-cta|exit-offer") or domx.is_example(n))


def _shingles(s, k=5):
    w = re.findall(r"[a-z0-9]+", s.lower())
    return {" ".join(w[i:i + k]) for i in range(len(w) - k + 1)}, len(w)


@check("words.fact-repeats", "28", what="one fact in one place: no time, price or percent in three folds, no sentence twice (rule 28)", needs="live")
def fact_repeats(ctx):
    """A fact (a time, a price, a percent, a "50+") shown in 3 or more folds fails; so does a long sentence (10+ words) that two
    folds share (5-word shingle overlap of 0.6 or more). Header, footer, nav, the sticky bar, dialogs, forms, buttons and
    a call to action's reason line and drawn examples are not read. growth.json words.repeat_ok lists facts that may repeat (a rating)."""
    most = int(wcfg(ctx, "repeat_folds", 3))
    min_words, jac = 10, float(wcfg(ctx, "repeat_sentence", 0.6))
    ok, ok_in = allowed(ctx)
    units = mainwalk.units(ctx, _drop_for_facts)
    where, shown = {}, {}
    for fold, text in units:
        for canon, raw in facts_in(ctx, text):
            if canon in ok or raw.lower() in ok or fold in ok_in.get(canon, ()):
                continue
            where.setdefault(canon, [])
            if fold not in where[canon]:
                where[canon].append(fold)
            shown.setdefault(canon, raw)
    probs = [f"'{shown[c]}' in {len(f)} folds ({', '.join(f)})" for c, f in where.items() if len(f) >= most]
    sents = [(fold, s, *_shingles(s)) for fold, text in units for s in mainwalk.sentences(text)]
    sents = [(f, s, sh) for f, s, sh, n in sents if n >= min_words and sh]
    for i, (fa, sa, ha) in enumerate(sents):
        for fb, sb, hb in sents[i + 1:]:
            if fa == fb:
                continue
            if len(ha & hb) / len(ha | hb) >= jac:
                probs.append(f"the same sentence in '{fa}' and '{fb}': '{short(sa, 70)}'")
                break
    ctx.verdict(probs, f"no fact in {most} or more folds and no sentence shared by two folds ({len(units)} text runs read)",
                "say each fact once, in the fold that owns it, and let the others point to it or say it without the number; "
                "rewrite the repeated sentence for its own fold (rule 28; growth.json words.repeat_ok lists facts that may repeat)")


# ---- internal wording --------------------------------------------------------------------------------------------------
INTERNAL_CASE = [r"BRAND", r"FACTS", r"OWNER-RULES"]
# The bare word "checkpoint" is ordinary software vocabulary (sprint checkpoints, compliance checkpoints, model checkpoints): only the
# process forms are caught by default (growth.json words.internal adds the bare word for a site that never uses it that way).
INTERNAL = [r"dossier", r"fold plan", r"(?:research|plan|fold) checkpoints?", r"checkpoints? (?:file|list|plan|notes?|log|status|\d+)",
            r"checkpoints\.md", r"this rebuild", r"before this rebuild", r"the old page", r"growth\.json", r"rule \d+"]
# Editor notes (2.8.3): wording that points at the page's own structure or the team's checking, never at the buyer's question.
_MONTH = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
_DATE = rf"(?:\d{{4}}-\d{{2}}-\d{{2}}|{_MONTH}\.? \d{{1,2}}(?:st|nd|rd|th)?,? \d{{4}}|\d{{1,2}}(?:st|nd|rd|th)? {_MONTH}\.?,? \d{{4}}|{_MONTH}\.? \d{{4}})"
EDITOR_NOTES = [r"the (?:[\w'-]+ ){0,4}folds? (?:above|below)", r"see the (?:[\w'-]+ ){0,3}fold", r"this section",
                rf"as of {_DATE} \(internal\)"]
# A stamp that stands alone as its whole block ("Checked 2026-11-10", "Verified on March 3, 2026 by the team") is an editor note. The same words
# inside a source line ("Source: our cost pages. Checked November 22, 2026.", "4.8 on Clutch, checked ...") tell the reader how fresh a fact is
# (rule 11: name a source by what it is and its date) and stay.
STAMP = re.compile(rf"(?:checked|verified)(?: on)? {_DATE}(?: by (?:[\w'.-]+ ?){{1,4}})?\.?", re.I)
# A visible byline ("Updated 12 May 2026", "Last reviewed May 2026") is for the reader; a note that overlaps one is not an editor note.
BYLINE = [rf"(?:last )?(?:updated|published|reviewed|posted|modified)(?: on)?:? {_DATE}"]


def internal_patterns(ctx):
    """[(compiled regex, label)]: the kit's list plus growth.json words.internal (a regex, or {"pattern", "case_sensitive"})."""
    out = [(re.compile(r"(?<![\w-])" + p + r"(?![\w-])"), p) for p in INTERNAL_CASE]
    out += [(re.compile(r"(?<![\w-])" + p + r"(?![\w-])", re.I), p) for p in INTERNAL + EDITOR_NOTES]
    for e in wcfg(ctx, "internal", []) or []:
        pat, cs = (e.get("pattern"), bool(e.get("case_sensitive"))) if isinstance(e, dict) else (e, False)
        if pat:
            out.append((re.compile(r"(?<![\w-])(?:" + pat + r")(?![\w-])", 0 if cs else re.I), pat))
    return out


def byline_patterns(ctx):
    """Regexes of a visible byline that is no editor note: the kit's plus growth.json words.byline (regexes, any case)."""
    return [re.compile(p, re.I) for p in BYLINE + [str(x) for x in wcfg(ctx, "byline", []) or []]]


@check("words.internal-labels", "11", what="no internal process wording (dossier, fold plan, checkpoint, this rebuild, BRAND, rule 28, editor notes like the X fold above or Checked <date>) in the page text", needs="live")
def internal_labels(ctx):
    """The page speaks to the reader, not to the team: words from the build process must never reach the visible text of <main>.
    growth.json words.internal adds the project's own; words.byline adds a visible byline form that is no note; words.internal_ok lists wording that is fine here (a real use of a word)."""
    pats = internal_patterns(ctx)
    bylines = byline_patterns(ctx)
    notes = {p for p in EDITOR_NOTES}
    okay = [str(x).lower() for x in wcfg(ctx, "internal_ok", []) or []]
    probs, seen = [], set()
    for _, text in mainwalk.units(ctx):
        if STAMP.fullmatch(text.strip()) and not any(x in text.lower() for x in okay):
            if (text, "stamp") not in seen:
                seen.add((text, "stamp"))
                probs.append(f"'{text.strip()}' stands alone as a block")
            continue
        for sent in mainwalk.sentences(text):
            if any(x in sent.lower() for x in okay):
                continue
            by = [b for rx in bylines for b in rx.finditer(sent)]
            hits = [m for rx, lab in pats for m in rx.finditer(sent)
                    if not (lab in notes and any(b.start() < m.end() and m.start() < b.end() for b in by))]
            hits = [m for m in hits if not any(o is not m and o.start() <= m.start() and m.end() <= o.end() and o.end() - o.start() > m.end() - m.start()
                                               for o in hits)]
            for m in hits:
                if (sent, m.group(0).lower()) not in seen:
                    seen.add((sent, m.group(0).lower()))
                    probs.append(f"'{m.group(0)}' in \"{short(sent, 110)}\"")
    ctx.verdict(probs, "no internal process wording in the page text",
                "say it to the reader in plain words: name the source and its date, never the team's own labels (rule 11; "
                "growth.json words.internal adds words, words.internal_ok allows a real use)")
