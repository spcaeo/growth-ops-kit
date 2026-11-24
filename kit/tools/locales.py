"""The project's locales (kit 3.0, micro kit core; a library, not a command): one place that knows which languages and
countries the site serves, where each one lives (its folder prefix), and which Google parameters its searches use.

growth.json `market.locales` is a list, the first form being the one a person writes:

    "market": {"locales": [
        {"locale": "en-US", "primary": true},                                  prefix "/", country US, language en
        {"locale": "en-CA", "prefix": "/en-ca/"},                              country CA, language en
        {"locale": "fr-CA", "prefix": "/fr-ca/", "google_params": "gl=ca&hl=fr&pws=0"},
        {"locale": "es-US"}                                                    prefix defaults to "/es-us/"
    ]}

Each entry: locale (a BCP 47 tag such as en-US, fr-CA, es-419), country (two letters; default: the tag's region),
language (default: the tag's language), prefix (the folder the copy lives in; the primary's is "/"), primary (exactly one),
google_params (default: gl=<country>&hl=<language>&pws=0). A plain tag string is the same as {"locale": tag}; the first
entry of a list with no "primary" flag is the primary.

A project with no `locales` has ONE locale, built from the old single-market fields (primary_country, language,
google_params), so every old growth.json works unchanged. This module is the only reader of those fields where a locale
matters; the old fields stay in the file as the primary locale's values (the wizard keeps both forms in step).

  from locales import from_cfg, from_market, validate, locale_of_path, path_in, find, primary, is_multi

Library only; the plain-words problems of a bad list come from validate() (and LocaleError when a tool needs a good one).
"""
from __future__ import annotations

import re

# language (2-3 letters), optional script (Latn), optional region (US or 419): the shape hreflang and `lang` accept
_TAG = re.compile(r"^([A-Za-z]{2,3})(?:-([A-Za-z]{4}))?(?:-([A-Za-z]{2}|\d{3}))?$")


class LocaleError(ValueError):
    """The locales in growth.json are not usable; the message says what to change, in plain words."""


def normalize_tag(tag) -> str:
    """The tag in its usual case (en-US, fr-CA, zh-Hans-CN, es-419). LocaleError when it is not a BCP 47 language tag."""
    t = str(tag or "").strip()
    m = _TAG.match(t)
    if not m:
        raise LocaleError(f"'{t}' is not a language tag: write it like en-US or fr-CA (language, a dash, the country), with a dash, not an underscore")
    lang, script, region = m.groups()
    out = [lang.lower()]
    if script:
        out.append(script.title())
    if region:
        out.append(region.upper() if region.isalpha() else region)
    return "-".join(out)


def language_of(tag: str) -> str:
    return normalize_tag(tag).split("-")[0]


def region_of(tag: str) -> str:
    """The country part of a tag (US, CA), or "" when it has none or a numeric region (es-419)."""
    for part in normalize_tag(tag).split("-")[1:]:
        if len(part) == 2 and part.isalpha():
            return part
    return ""


def google_params(country: str, language: str) -> str:
    """The Google search parameters of one market: results of that country, in that language, not personalised."""
    return f"gl={str(country).lower()}&hl={(language or 'en').split('-')[0].lower()}&pws=0"


def _prefix(p) -> str:
    p = str(p or "").strip()
    if not p:
        return ""
    return "/" + p.strip("/") + "/" if p.strip("/") else "/"


def default_prefix(tag: str) -> str:
    return f"/{normalize_tag(tag).lower()}/"


def _entry(raw, first: bool, any_primary: bool) -> dict:
    """One list entry in full: every default filled. LocaleError when it cannot be read at all."""
    if isinstance(raw, str):
        raw = {"locale": raw}
    if not isinstance(raw, dict):
        raise LocaleError(f"a locale must be a tag like en-US or an object with a \"locale\" key, not {raw!r}")
    tag = normalize_tag(raw.get("locale") or raw.get("tag") or raw.get("hreflang"))
    country = str(raw.get("country") or region_of(tag)).strip().upper()
    language = str(raw.get("language") or language_of(tag)).strip().lower()
    primary = bool(raw["primary"]) if "primary" in raw else (first and not any_primary)
    prefix = _prefix(raw.get("prefix")) or ("/" if primary else default_prefix(tag))
    out = {"locale": tag, "country": country, "language": language, "prefix": prefix, "primary": primary,
           "google_params": str(raw.get("google_params") or "").strip() or (google_params(country, language) if country else "")}
    return out


def normalize(raw: list) -> list:
    """The list as the kit reads it: every entry in full. Raises LocaleError for an entry that is not readable."""
    if not isinstance(raw, list) or not raw:
        raise LocaleError("market.locales must be a list with at least one locale, for example [\"en-US\"]")
    any_primary = any(isinstance(r, dict) and r.get("primary") for r in raw)
    return [_entry(r, i == 0, any_primary) for i, r in enumerate(raw)]


def validate(locales: list) -> list:
    """What is wrong with a (normalized) list, each problem as one plain sentence with its fix. [] when it is good."""
    out = []
    seen_tag, seen_prefix = {}, {}
    for e in locales:
        t = e["locale"]
        if t.lower() in seen_tag:
            out.append(f"locale {t} is listed twice: keep one entry for it")
        seen_tag[t.lower()] = e
        if not re.fullmatch(r"[A-Z]{2}", e["country"] or ""):
            out.append(f"locale {t} has no country: write the tag with a country (en-US) or set \"country\": \"US\" on it")
        if e["language"] != language_of(t):
            out.append(f"locale {t}: language \"{e['language']}\" does not match the tag's language \"{language_of(t)}\"; fix the tag or the language")
        if e["google_params"] and e["country"] and f"gl={e['country'].lower()}" not in e["google_params"].lower().split("&"):
            out.append(f"locale {t}: google_params \"{e['google_params']}\" must carry gl={e['country'].lower()} (its country); "
                       f"write {google_params(e['country'], e['language'])}")
        if e["google_params"] and "pws=0" not in e["google_params"].split("&"):
            out.append(f"locale {t}: google_params \"{e['google_params']}\" must carry pws=0 (results that are not personalised)")
        if e["prefix"] in seen_prefix:
            out.append(f"locales {seen_prefix[e['prefix']]} and {t} share the folder {e['prefix']}: give each locale its own prefix, for example {default_prefix(t)}")
        seen_prefix[e["prefix"]] = t
    prim = [e for e in locales if e["primary"]]
    if len(prim) != 1:
        out.append("exactly one locale must be the primary (\"primary\": true)" + (f"; now {len(prim)}: {', '.join(e['locale'] for e in prim)}" if prim else "; none is"))
    for e in prim:
        if e["prefix"] != "/":
            out.append(f"the primary locale {e['locale']} lives at the site's root: its prefix must be \"/\" (now \"{e['prefix']}\")")
    for e in locales:
        if not e["primary"] and e["prefix"] == "/":
            out.append(f"locale {e['locale']} is not the primary but its prefix is \"/\": give it a folder such as {default_prefix(e['locale'])}")
    pre = [e for e in locales if e["prefix"] != "/"]
    for a in pre:
        for b in pre:
            if a is not b and b["prefix"].startswith(a["prefix"]):
                out.append(f"the folder of {a['locale']} ({a['prefix']}) holds the folder of {b['locale']} ({b['prefix']}): the folders must not nest")
    return out


def from_market(market: dict | None) -> list:
    """Every locale of a market block. `locales` when it is there (read and checked: LocaleError with the problems when it is bad),
    else ONE locale built from the old single-market fields (primary_country, language, google_params). [] when the market
    names no country at all (nothing set yet)."""
    m = market or {}
    if m.get("locales") not in (None, []):
        locs = normalize(m["locales"])
        bad = validate(locs)
        if bad:
            raise LocaleError("market.locales in growth.json is not right: " + "; ".join(bad))
        return locs
    code = str(m.get("primary_country") or "").strip().upper()
    if not code:
        return []
    lang = str(m.get("language") or "en").split("-")[0].lower() or "en"
    tag = f"{lang}-{code}"
    gp = str(m.get("google_params") or "").strip()
    return [{"locale": tag, "country": code, "language": lang, "prefix": "/", "primary": True,
             "google_params": gp or google_params(code, lang)}]


def from_cfg(cfg: dict | None) -> list:
    """Every locale of a project (its growth.json dict): see from_market."""
    return from_market((cfg or {}).get("market"))


def problems(cfg: dict | None) -> list:
    """Plain problems with the project's locales ([] when good or when it has none); never raises."""
    try:
        locs = from_cfg(cfg)
    except LocaleError as e:
        return [str(e)]
    m = (cfg or {}).get("market") or {}
    old = str(m.get("primary_country") or "").upper()
    if m.get("locales") and locs and old and old != primary(locs)["country"]:
        return [f"market.primary_country is {old} but the primary locale {primary(locs)['locale']} is in {primary(locs)['country']}: "
                f"they must agree (growth wizard answer market '{{\"locales\": [...]}}' writes both)"]
    return []


def primary(locales: list) -> dict | None:
    return next((e for e in locales if e["primary"]), locales[0] if locales else None)


def is_multi(cfg: dict | None) -> bool:
    """True when the project serves two or more locales (a bad list counts as not multi: problems() reports it)."""
    try:
        return len(from_cfg(cfg)) >= 2
    except LocaleError:
        return False


def find(locales: list, tag: str | None = None) -> dict:
    """One locale by tag (any case; es_us and es-US are the same), the primary when `tag` is empty. LocaleError, with the
    tags that exist, when there is no such locale."""
    if not tag:
        p = primary(locales)
        if p is None:
            raise LocaleError("no market is set yet: growth wizard answer market '{\"country\": \"US\", \"language\": \"en\"}'")
        return p
    want = str(tag).strip().replace("_", "-").lower()
    for e in locales:
        if e["locale"].lower() == want:
            return e
    raise LocaleError(f"no locale {tag} in growth.json market.locales (known: {', '.join(e['locale'] for e in locales) or 'none'})")


def locale_of_path(locales: list, path: str) -> tuple:
    """(the locale a site path belongs to, the same page's path in the primary locale): the longest folder prefix that
    matches, else the primary. /fr-ca/pricing/ -> (fr-CA, /pricing/); /fr-ca -> (fr-CA, /)."""
    path = "/" + str(path or "/").split("#")[0].split("?")[0].lstrip("/")
    best = None
    for e in locales:
        pre = e["prefix"]
        if pre == "/":
            continue
        if (path + "/").startswith(pre) and (best is None or len(pre) > len(best["prefix"])):
            best = e
    if best is None:
        return primary(locales), path
    rest = path[len(best["prefix"]) - 1:] if path.startswith(best["prefix"]) else "/"
    return best, rest or "/"


def path_in(locale: dict, base_path: str) -> str:
    """The path of a page (given as its primary-locale path) inside a locale's folder: /pricing/ -> /fr-ca/pricing/."""
    base = "/" + str(base_path or "/").lstrip("/")
    return base if locale["prefix"] == "/" else locale["prefix"].rstrip("/") + base


def describe(locales: list) -> str:
    """One line for a person: every locale with its country, folder and Google parameters."""
    return "; ".join(f"{e['locale']}{' (primary)' if e['primary'] else ''} at {e['prefix']}, Google {e['google_params']}" for e in locales)


def market_fields(locales: list) -> dict:
    """The old single-market fields, as the primary locale's values (the wizard keeps them next to `locales`)."""
    p = primary(locales)
    others = []
    for e in locales:
        if e is not p and e["country"] != p["country"] and e["country"] not in others:
            others.append(e["country"])
    return {"primary_country": p["country"], "language": f"{p['language']}-{p['country']}", "google_params": p["google_params"],
            "secondary_countries": others}


def stored(locales: list) -> list:
    """The list as it is written to growth.json: every field in full, the primary first."""
    return sorted((dict(e) for e in locales), key=lambda e: not e["primary"])
