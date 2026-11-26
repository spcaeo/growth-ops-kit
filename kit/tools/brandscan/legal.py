"""Facts from terms, privacy and similar pages: the legal name, the postal address, the governing law, the date the page was
last updated, the privacy contact and the named laws. Every reader takes the page's text (one line per block) and returns
what it found with the sentence it came from, so the owner can check the wording."""
from __future__ import annotations

import re

SUFFIX = (r"(?:Incorporated|Pvt\.?\s*Ltd\.?|Private\s+Limited|Pty\.?\s+Ltd\.?|Co\.,?\s*Ltd\.?|Inc\.?|LLC|L\.L\.C\.|Ltd\.?|Limited|GmbH|Corp\.?|Corporation|LLP|PLC|"
          r"S\.A\.|S\.L\.|B\.V\.|N\.V\.|AG|Oy|ApS|SAS|SARL)")
NAME_WORD = r"[A-Z0-9][\w&'’\-]*"
LEGAL_NAME = re.compile(rf"(?<![\w&])((?:{NAME_WORD}\s+){{0,5}}{NAME_WORD}),?\s+({SUFFIX})(?![A-Za-z]{{2}})")   # "Ltd.v1.0" (a footer that runs on) still ends at "Ltd."
NAME_NOISE = {"the", "this", "these", "our", "us", "we", "terms", "term", "service", "services", "privacy", "policy", "agreement", "welcome", "by", "and",
              "of", "to", "for", "with", "website", "site", "company", "legal", "notice", "conditions", "use", "page", "read", "please", "between",
              "operated", "owned", "provided", "contact", "address", "copyright", "all", "rights", "reserved", "from", "at", "in", "on", "or", "if",
              "any", "your", "you", "is", "are", "as", "an", "a", "any", "each", "such", "its", "their", "other", "no", "not", "may", "will", "shall"}
CONTEXT = re.compile(r"(?i)operated by|owned by|provided by|run by|registered|incorporated|company number|©|copyright|\(\s*[“\"']?(?:the\s+)?(?:company|we|us|our)|a company|d/b/a|doing business|trading as|controller|entity|legal name")


def legal_names(text: str) -> list[dict]:
    """Company names that end in Inc., LLC, Ltd, Pvt Ltd, GmbH, Corp and the like: [{name, count, context, strong}].
    A name beside "operated by", "©", "registered" and the like is strong."""
    found: dict[str, dict] = {}
    for line in (text or "").splitlines():                 # a line is one block of the page; "Pvt. Ltd." must not split a sentence
        for m in LEGAL_NAME.finditer(line):
            words = m.group(1).split()
            while words and (words[0].lower().strip("’'") in NAME_NOISE or re.fullmatch(r"\d{4}(?:-\d{4})?", words[0])):
                words.pop(0)                                # "Welcome to", "2026" (a copyright year) are not part of the name
            if not words:
                continue
            name = f"{' '.join(words)} {m.group(2)}".replace(" ,", ",")
            key = re.sub(r"[^a-z0-9]", "", name.lower())
            around = line[max(0, m.start() - 110):m.end() + 110].strip()
            rec = found.setdefault(key, {"name": name, "count": 0, "context": around, "strong": False})
            rec["count"] += 1
            if CONTEXT.search(around) and not rec["strong"]:
                rec.update(strong=True, context=around)
    return sorted(found.values(), key=lambda r: (-r["strong"], -r["count"], len(r["name"])))


COPYRIGHT = re.compile(r"(?i)(?:©|&copy;|\(c\)|copyright)\s*(?:\d{4}(?:\s*[-–]\s*\d{4})?)?[\s,.:-]*([A-Z0-9][^|\n]{2,70}?)(?=\.?\s*(?:All rights|Rights reserved|$|\||\n|—|-\s|Made|Designed|Built|Powered))")


def copyright_holder(text: str) -> str:
    """The name on a footer's "© 2026 Name" line, or ""."""
    for line in (text or "").splitlines():
        m = COPYRIGHT.search(line)
        if m:
            name = re.sub(r"(?i)\ball rights reserved\b.*$", "", m.group(1)).strip(" .,-–—")
            if 2 < len(name) <= 70 and not re.match(r"(?i)(all rights|rights)", name):
                return name
    return ""


POSTAL = re.compile(
    r"(?<![\w-])(?:[A-Z]{2}\s+\d{5}(?:-\d{4})?"                       # US: CA 94105
    r"|[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}"                             # UK: SW1A 1AA
    r"|[A-Z]\d[A-Z]\s?\d[A-Z]\d"                                      # Canada: M5V 3L9
    r"|\d{4}\s?[A-Z]{2}"                                              # NL: 1011 AB
    r"|(?<=[A-Za-z,]\s)\d{5,6}(?:-\d{4})?)(?![\w-])")                 # five or six digits after a place name
START = re.compile(r"\b\d{1,5}[A-Za-z]?(?:[-/]\d{1,4})?[,\s]+(?=[A-Z0-9#])|(?i:\b(?:suite|ste\.?|floor|unit|level|plot|building|block|p\.?\s?o\.?\s?box|office)\b)")
COUNTRY = re.compile(r"^[\s,.-]*(United States(?: of America)?|USA|U\.S\.A\.?|US|India|United Kingdom|UK|Canada|Australia|Germany|Ireland|Singapore|UAE|United Arab Emirates|Netherlands|France|Spain|Italy|Israel|Switzerland|Sweden|Denmark|Norway|Poland|Brazil|Mexico|South Africa|New Zealand|Japan)\b")


def postal_addresses(text: str, limit: int = 3) -> list[str]:
    """Street addresses in the text: a line that ends in a postal code, back to the street number or building word."""
    out: list[str] = []
    for line in (text or "").splitlines():
        for m in POSTAL.finditer(line):
            window = line[max(0, m.start() - 140):m.start()]
            starts = [s.start() for s in START.finditer(window)]
            if not starts or not re.search(r"[A-Za-z]{3,}", window):
                continue
            addr = window[starts[0]:] + m.group(0)
            tail = COUNTRY.match(line[m.end():m.end() + 40])
            if tail:
                addr += ", " + tail.group(1)
            addr = re.sub(r"\s+", " ", addr).strip(" ,;.")
            if addr.count(",") >= 1 and 12 <= len(addr) <= 200 and addr not in out and not re.search(r"(?i)\b(?:page|section|clause)\b", addr):
                out.append(addr)
    return out[:limit]


LAW_SENT = re.compile(
    r"(?i)((?:governed|construed|interpreted)\b[^.\n]{0,80}?\blaws?\s+of\s+(?:the\s+)?((?-i:[A-Z][A-Za-z.' -]{2,60}?))(?=[,.;]|\s+(?:without|excluding|applicable|including|with|in|as|that|when|regardless|notwithstanding|\(|and(?=\s+(?-i:[a-z])))|\s*$))")
LAW_SENT3 = re.compile(r"(?i)((?:in accordance with|subject to|under|pursuant to)\b[^.\n]{0,60}?\b(?:prevailing|applicable|governing)?\s*laws?\s+of\s+(?:the\s+)?((?-i:[A-Z][A-Za-z.' -]{2,50}?))(?=[,.;]|\s+(?:without|excluding|applicable|including|with|in|as|that|when|regardless|notwithstanding|\(|and(?=\s+(?-i:[a-z])))|\s*$))")
LAW_SENT2 = re.compile(r"(?i)(laws?\s+of\s+(?:the\s+)?(?:State|Province|Republic|Commonwealth)?\s*(?:of\s+)?([A-Z][A-Za-z.' -]{2,50}?)\s+(?:shall\s+)?(?:govern|apply|will govern)[^.\n]{0,80})")
JURIS = re.compile(r"(?i)((?:exclusive\s+)?(?:jurisdiction|venue)\s+(?:of|in)\s+(?:the\s+)?(?:(?:state\s+and\s+federal\s+|federal\s+|state\s+|competent\s+|courts?\s+(?:of|in|located in)\s+)+)?([A-Z][A-Za-z.,' -]{2,60}?)(?=[.;]|\s+(?:and|shall|will|to|for|over|in)\b|\s*$))")
COURTS = re.compile(r"(?i)(courts?\s+(?:of|in|located in|sitting in)\s+([A-Z][A-Za-z.,' -]{2,50}?)(?=[.;,]|\s+(?:shall|will|and|to|for|over|have|having)\b|\s*$))")
ARBITRATION = re.compile(r"(?i)(arbitration[^.\n]{0,100}?\b(?:seat|venue|place|held|conducted|located)\b[^.\n]{0,60}?\bin\s+([A-Z][A-Za-z.,' -]{2,50}?)(?=[.;,]|\s*$))")


def governing_law(text: str) -> dict:
    """{"law": [place], "jurisdiction": [place], "sentences": [the sentences]}: only what the page says."""
    flat = re.sub(r"\s+", " ", text or "")
    law, juris, sents = [], [], []

    def take(rx, bucket, group=2):
        for m in rx.finditer(flat):
            place = m.group(group).strip(" ,.")
            if place and place not in bucket:
                bucket.append(place)
            s = m.group(1).strip()
            if s[:200] not in sents:
                sents.append(s[:200])
    take(LAW_SENT, law)
    take(LAW_SENT2, law)
    take(LAW_SENT3, law)
    take(JURIS, juris)
    take(COURTS, juris)
    take(ARBITRATION, juris)

    def fold(places):                       # "Wilmington" inside "Wilmington, Delaware" is the same place: keep the longer
        keep = [p for p in places if not any(p != q and p.lower() in q.lower() for q in places)]
        return list(dict.fromkeys(keep))
    return {"law": fold(law)[:3], "jurisdiction": fold(juris)[:3], "sentences": sents[:4]}


MONTH = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
DATE = rf"(?:{MONTH}\.?\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}}|\d{{1,2}}(?:st|nd|rd|th)?\s+{MONTH}\.?,?\s+\d{{4}}|{MONTH}\.?\s+\d{{4}}|\d{{4}}-\d{{2}}-\d{{2}}|\d{{1,2}}/\d{{1,2}}/\d{{2,4}})"
UPDATED = re.compile(rf"(?i)(?:last\s+(?:updated|modified|revised|reviewed)|effective(?:\s+date)?|updated|revised|date\s+of\s+(?:last\s+)?revision|version\s+date)\s*(?:on|:|-|–|—|as of)?\s*({DATE})")


def last_updated(text: str) -> str:
    """The date a terms or privacy page says it was last updated or took effect, as written ("November 3, 2025"), or ""."""
    flat = re.sub(r"\s+", " ", text or "")
    m = UPDATED.search(flat)
    return m.group(1) if m else ""


LAWS = [
    ("GDPR", r"\bGDPR\b|General Data Protection Regulation"), ("UK GDPR", r"\bUK GDPR\b"), ("CCPA", r"\bCCPA\b|California Consumer Privacy Act"),
    ("CPRA", r"\bCPRA\b"), ("HIPAA", r"\bHIPAA\b"), ("COPPA", r"\bCOPPA\b"), ("PIPEDA", r"\bPIPEDA\b"), ("LGPD", r"\bLGPD\b"),
    ("India DPDP Act", r"Digital Personal Data Protection Act|\bDPDP\b"), ("India IT Act", r"Information Technology Act"),
    ("SOC 2", r"\bSOC\s?2\b"), ("ISO 27001", r"\bISO\s?/?\s?(?:IEC\s)?27001\b"), ("PCI DSS", r"\bPCI[- ]DSS\b"), ("FERPA", r"\bFERPA\b"),
    ("GLBA", r"\bGLBA\b|Gramm-Leach-Bliley"), ("ePrivacy", r"\bePrivacy\b"), ("CAN-SPAM", r"CAN-SPAM"), ("DMCA", r"\bDMCA\b|Digital Millennium Copyright Act"),
    ("Virginia VCDPA", r"\bVCDPA\b"), ("Australian Privacy Act", r"Privacy Act 1988"), ("POPIA", r"\bPOPIA\b"), ("EU AI Act", r"EU AI Act|Artificial Intelligence Act"),
]
LAW_RX = [(n, re.compile(rx)) for n, rx in LAWS]


def named_laws(text: str) -> list[str]:
    return [n for n, rx in LAW_RX if rx.search(text or "")]


def dpo(text: str, emails: list[str]) -> dict:
    """The data protection officer or privacy contact: the sentence that names one, and the addresses near it."""
    flat = re.sub(r"\s+", " ", text or "")
    m = re.search(r"(?i)(?:[^.]|\.(?=\S)){0,120}\b(?:data protection officer|DPO|privacy officer|privacy team|privacy contact|grievance officer)\b(?:[^.]|\.(?=\S)){0,200}", flat)
    if not m:
        return {}
    near = [e for e in emails if e.lower() in m.group(0).lower()]
    return {"sentence": m.group(0).strip()[:300], "emails": near}
