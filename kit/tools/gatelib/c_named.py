"""One named phrase in one place (2.8.3; rule 28): a multi-word name or standard pair ("HL7 FHIR R4 and SMART on FHIR") said in
three or more folds. words.fact-repeats counts numbers and listed terms; this reads capitalised and technical phrases.
Limits come from growth.json words (repeat_folds, repeat_ok)."""
from __future__ import annotations

import re

from techseo.dom import find_all

from . import domx, mainwalk
from .c_repeats import _drop_for_facts, allowed
from .c_words import wcfg
from .core import Skip, check

CONNECT = {"and", "on", "of", "for", "to", "with", "&", "in", "by", "or"}
NOT_NAMED = {"i", "a", "we", "our", "the", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
             "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec", "january", "february", "march",
             "april", "june", "july", "august", "september", "october", "november", "december"}
EDGE = ",;:.!?)(\"“”‘’"


def _strong(t):
    """A technical token: it has a digit among letters (HL7, R4, Web3) or is all capitals (FHIR, SMART, EHR)."""
    return bool(re.search(r"[A-Za-z]", t)) and (bool(re.search(r"\d", t)) or (len(re.sub(r"[^A-Za-z]", "", t)) >= 2 and t.upper() == t))


def _tokens(sentence):
    """[(clean token, breaks before, breaks after)]: whitespace tokens; a bracket or punctuation at an edge breaks a phrase."""
    out = []
    for raw in sentence.split():
        lead, trail = raw[:1] in EDGE, raw[-1:] in EDGE
        t = raw.strip(EDGE).strip("'")
        if t:
            out.append((t, lead, trail))
    return out


def is_title_case(sentence):
    """A heading or title line: 3 or more real words (small connecting words not counted) and 70% or more start with a capital.
    Read the same way in every sentence: in a title line a capital means nothing, only technical tokens (HL7, FHIR, R4) are names."""
    words = [w for w in (t for t, _, _ in _tokens(sentence)) if w.lower() not in CONNECT and re.search(r"[A-Za-z]", w)]
    return len(words) >= 3 and sum(w[:1].isupper() for w in words) >= 0.7 * len(words)


def phrases(sentence, title_case=False):
    """Every named phrase of a sentence: runs of named tokens (capitalised, technical) joined by small words, as all
    contiguous sub-phrases. A phrase has 3 or more named tokens, or 2 side-by-side technical
    tokens of which one has a digit (FHIR R4, HL7 v2): two all-capital words (AI ML) and a joined list (HL7 and FHIR) are no pair (2.8.5). Sentence-initial words are not named by case."""
    toks = _tokens(sentence)
    named = []
    for i, (t, _, _) in enumerate(toks):
        low = t.lower()
        cap = t[:1].isupper() and not t.isdigit() and low not in NOT_NAMED and i > 0 and not title_case and not t.endswith("'s")
        named.append(low not in NOT_NAMED and bool(re.search(r"[A-Za-z]", t)) and (_strong(t) or cap))
    out, i, n = [], 0, len(toks)
    while i < n:
        if not named[i]:
            i += 1
            continue
        j = i                                    # grow the run: named tokens, with connectors between two named tokens
        while True:
            if toks[j][2] or j + 1 >= n:
                break
            if named[j + 1] and not toks[j + 1][1]:
                j += 1
            elif toks[j + 1][0].lower() in CONNECT and j + 2 < n and named[j + 2] and not toks[j + 2][1]:
                j += 2
            else:
                break
        run = toks[i:j + 1]
        for a in range(len(run)):
            for b in range(a + 1, len(run) + 1):
                sub = run[a:b]
                w = [t for t, _, _ in sub]
                if w[0].lower() in CONNECT or w[-1].lower() in CONNECT:
                    continue
                nm = [x for x in w if x.lower() not in CONNECT]
                if len(nm) >= 3 or (len(w) == 2 and any(re.search(r"\d", x) for x in nm) and all(_strong(x) for x in nm)):
                    out.append(" ".join(w))
        i = j + 1
    return out


def topic_terms(ctx):
    """The page's own subject: the words of its H1, its <title>, the last item of its breadcrumb and growth.json words.topic_terms.
    A phrase made only of these words is the topic of the page, never a repeat (2.8.5)."""
    root, texts = ctx.root(), []
    h1 = next(iter(find_all(root, "h1")), None)
    t = domx.page_title(root)
    for n in (h1, t):
        if n is not None:
            texts.append(domx.text(n))
    nav = next((n for n in root.iter() if n.tag in ("nav", "ol") and re.search(r"(?i)breadcrumb", n.get("aria-label") + n.get("class"))), None)
    if nav is not None:
        items = [domx.text(i) for i in find_all(nav, "li")] or [domx.text(i) for i in find_all(nav, "a")]
        texts.append(items[-1] if items else domx.text(nav))
    texts += [str(x) for x in wcfg(ctx, "topic_terms", []) or []]
    return {w.lower() for tx in texts for w in (x.strip(EDGE).strip("'") for x in tx.split()) if w}


@check("words.named-repeats", "28", what="one named phrase in one place: no capitalised or technical phrase (HL7 FHIR R4 and SMART on FHIR) in three folds (rule 28)", needs="live")
def named_repeats(ctx):
    """A multi-word name or standard pair (3 or more words, or 2 technical tokens such as HL7 FHIR) shown in 3 or more folds fails (the same
    limit as words.fact-repeats: growth.json words.repeat_folds). Headers, footer, nav, forms, buttons, a call to action's reason line and
    drawn examples are not read; growth.json words.repeat_ok lists phrases that may repeat (the firm's own name)."""
    most = int(wcfg(ctx, "repeat_folds", 3))
    ok, _ = allowed(ctx)
    okp = [re.sub(r"\s+", " ", str(e.get("fact") if isinstance(e, dict) else e)).strip() for e in wcfg(ctx, "repeat_ok", []) or []]
    okrx = re.compile("|".join(re.escape(o).replace(r"\ ", r"\s+") for o in sorted(filter(None, okp), key=len, reverse=True)), re.I) if any(okp) else None
    where, units = {}, mainwalk.units(ctx, _drop_for_facts)
    if not units:
        raise Skip("no text runs found in <main> to read")
    topic = topic_terms(ctx)
    for fold, text in units:
        for sent in mainwalk.sentences(text):
            title = is_title_case(sent)
            pieces = okrx.split(sent) if okrx else [sent]       # a phrase listed in repeat_ok is cut out of the text
            for ph in {x for piece in pieces for x in phrases(piece, title)}:
                low = ph.lower()
                if low in ok or all(w in topic for w in low.split() if w not in CONNECT):
                    continue
                where.setdefault(low, {"raw": ph, "folds": []})
                if fold not in where[low]["folds"]:
                    where[low]["folds"].append(fold)
    hit = {k: v for k, v in where.items() if len(v["folds"]) >= most}
    keep = {k: v for k, v in hit.items()          # the longest phrase wins over the pieces of it said in the same folds
            if not any(k != o and k in o and set(v["folds"]) <= set(ov["folds"]) for o, ov in hit.items())}
    probs = [f"'{v['raw']}' in {len(v['folds'])} folds ({', '.join(v['folds'])})" for v in keep.values()]
    ctx.verdict(probs, f"no named phrase in {most} or more folds ({len(units)} text runs read)",
                "name it once, in the fold that owns it; the others say what it does without repeating the name (rule 28; "
                "growth.json words.repeat_ok lists a phrase that may repeat)")
