"""Spelling locales for rule 93 (#54): en-US, en-CA and en-GB word lists, the locale of each path, and a reviewed allowlist.

One table of word families gives each locale's spelling. A page in locale L is flagged for every word that is another
locale's spelling and not L's own. A word with a "?" is also a real word in the other locales (check, meter, license), so it is never
flagged. growth.json:

  "spelling": "en-US"                                   the whole site
  "spelling": {"/": "en-CA", "/en-us/": "en-US"}        the longest matching path prefix decides
  "spelling": {"/": "html_lang"}                        read each page's own <html lang="...">
  "spelling_allow": ["colourway"]                       words never flagged (brand and trade words: a reviewed list)
  "spelling_allow_file": "docs/spelling-allow.txt"      the same, one word per line, # comments (file in the project)
"""
from __future__ import annotations

import re
from pathlib import Path

LOCALES = ("en-US", "en-CA", "en-GB")


def fam(us, ca, gb, suffixes=("",)):
    return [(us + s, ca + s, gb + s) for s in suffixes]


ROWS: list[tuple[str, str, str]] = []
for stem in (("color", "colour", "colour"), ("favor", "favour", "favour"), ("honor", "honour", "honour"), ("labor", "labour", "labour"),
             ("neighbor", "neighbour", "neighbour"), ("behavior", "behaviour", "behaviour"), ("flavor", "flavour", "flavour"),
             ("humor", "humour", "humour"), ("harbor", "harbour", "harbour"), ("rumor", "rumour", "rumour")):
    ROWS += fam(*stem, ("", "s", "ed", "ing", "ful", "less", "able"))
ROWS += fam("favorite", "favourite", "favourite", ("", "s"))
for stem in (("optimiz", "optimiz", "optimis"), ("organiz", "organiz", "organis"), ("summariz", "summariz", "summaris"),
             ("prioritiz", "prioritiz", "prioritis"), ("recogniz", "recogniz", "recognis"), ("minimiz", "minimiz", "minimis"),
             ("maximiz", "maximiz", "maximis"), ("utiliz", "utiliz", "utilis"), ("customiz", "customiz", "customis"),
             ("standardiz", "standardiz", "standardis"), ("categoriz", "categoriz", "categoris"), ("realiz", "realiz", "realis"),
             ("personaliz", "personaliz", "personalis"), ("authoriz", "authoriz", "authoris")):
    ROWS += fam(*stem, ("e", "es", "ed", "ing", "er", "ers", "ation", "ations"))
ROWS += fam("analyz", "analyz", "analys", ("e", "es", "ed", "ing", "er", "ers"))
ROWS += [("center", "centre", "centre"), ("centers", "centres", "centres"), ("centered", "centred", "centred"), ("centering", "centring", "centring"),
         ("?meter", "metre", "metre"), ("?meters", "metres", "metres"), ("liter", "litre", "litre"), ("liters", "litres", "litres"),
         ("kilometer", "kilometre", "kilometre"), ("kilometers", "kilometres", "kilometres"),
         ("defense", "defence", "defence"), ("offense", "offence", "offence"), ("gray", "grey", "grey"),
         ("?check", "cheque", "cheque"), ("?checks", "cheques", "cheques"), ("?tire", "?tire", "tyre"), ("?tires", "?tires", "tyres"),
         ("?program", "?program", "programme"), ("?programs", "?programs", "programmes"),
         ("catalog", "catalogue", "catalogue"), ("catalogs", "catalogues", "catalogues"),
         ("traveling", "travelling", "travelling"), ("traveled", "travelled", "travelled"), ("traveler", "traveller", "traveller"),
         ("travelers", "travellers", "travellers"), ("modeling", "modelling", "modelling"), ("modeled", "modelled", "modelled"),
         ("labeled", "labelled", "labelled"), ("labeling", "labelling", "labelling"), ("canceled", "cancelled", "cancelled"),
         ("canceling", "cancelling", "cancelling"), ("fulfill", "fulfil", "fulfil"), ("fulfillment", "fulfilment", "fulfilment"),
         ("enroll", "enrol", "enrol"), ("enrollment", "enrolment", "enrolment"), ("jewelry", "jewellery", "jewellery"),
         ("plow", "plough", "plough"), ("skeptic", "sceptic", "sceptic"), ("skeptical", "sceptical", "sceptical"),
         ("aluminum", "aluminum", "aluminium"), ("mold", "mould", "mould"), ("pajamas", "pyjamas", "pyjamas"),
         ("?routing", "?routing", "routeing"), ("?license", "licence", "licence"), ("?licenses", "licences", "licences")]

# a spelling -> the locales it is right in, and whether it is also a real word elsewhere ("?")
FORMS: dict[str, dict[str, str]] = {}      # a spelling -> {"locales": {locales it is right in}, "ambiguous": bool}
for row in ROWS:
    clean = [w.lstrip("?") for w in row]
    for i, loc in enumerate(LOCALES):
        FORMS.setdefault(clean[i], {"locales": set(), "ambiguous": False})["locales"].add(loc)
        if row[i].startswith("?"):
            FORMS[clean[i]]["ambiguous"] = True


def correct_for(loc: str) -> dict[str, str]:
    """{wrong spelling: right spelling} for a page in locale `loc`."""
    out = {}
    i = LOCALES.index(loc)
    for row in ROWS:
        right = row[i].lstrip("?")
        for j, w in enumerate(row):
            w2 = w.lstrip("?")
            f = FORMS[w2]
            if w2 != right and loc not in f["locales"] and not (w.startswith("?") or f["ambiguous"]):
                out[w2] = right
    return out


def norm_locale(v) -> str | None:
    """'en_ca', 'EN-ca', 'en-CA' -> 'en-CA'; None when it is not a locale this module has a list for."""
    s = str(v or "").replace("_", "-").strip()
    for loc in LOCALES:
        if s.lower() == loc.lower():
            return loc
    return None


def html_lang(html: str | None) -> str:
    m = re.search(r"(?is)<html\b[^>]*\blang=[\"']?([A-Za-z_-]+)", html or "")
    return m.group(1) if m else ""


def choose(cfg: dict, path: str, html: str | None) -> tuple[str | None, str]:
    """(locale, why). Locale None when the chosen one has no list (the check skips and says so)."""
    sp = cfg.get("spelling") or (cfg.get("market") or {}).get("language") or "en-US"
    if isinstance(sp, dict):
        p = (path or "/").rstrip("/") + "/"
        best = max((k for k in sp if p.startswith(k if k.endswith("/") else k + "/") or k == "/"), key=len, default=None)
        sp = sp[best] if best is not None else "en-US"
        where = f"path rule {best!r}"
    else:
        where = "growth.json spelling"
    if str(sp).lower() in ("html_lang", "html-lang", "auto"):
        lang = html_lang(html)
        loc = norm_locale(lang)
        return loc, f"the page's <html lang=\"{lang}\">" if loc else f"the page's <html lang=\"{lang}\"> has no word list (en-US, en-CA, en-GB)"
    loc = norm_locale(sp)
    return loc, f"{where} {sp}" if loc else f"{where} {sp} has no word list (en-US, en-CA, en-GB)"


def allowlist(cfg: dict, project: Path | None) -> set[str]:
    out = {str(w).lower() for w in cfg.get("spelling_allow") or []}
    f = cfg.get("spelling_allow_file")
    if f and project:
        p = Path(f).expanduser()
        p = p if p.is_absolute() else Path(project) / p
        if p.is_file():
            out |= {l.split("#")[0].strip().lower() for l in p.read_text().splitlines() if l.split("#")[0].strip()}
    return out


def problems(text: str, loc: str, allow: set[str] = frozenset()) -> list[str]:
    bad = correct_for(loc)
    out, seen = [], set()
    for m in re.finditer(r"(?i)(?<![\w-])([a-z]+)(?![\w-])", text):
        w = m.group(1).lower()
        if w in bad and w not in allow:
            seen.add(w)
    for w in sorted(seen):
        n = len(re.findall(r"(?i)(?<![\w-])" + w + r"(?![\w-])", text))
        out.append(f"'{w}' x{n} ({loc}: {bad[w]})")
    return out
