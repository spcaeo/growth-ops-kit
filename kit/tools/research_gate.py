"""The research-browser gate: no job with a research step starts until the research browser (Claude in Chrome) is
connected and Google is set to the target country, both confirmed (library, used by doctor A14, preflight and tasks).

The code cannot connect Chrome or change Google's region itself; the wizard turns each into a guided step and records the
confirmation in setup-state.json: the browser's name, and the region Google REPORTED (read from Google's settings page,
never assumed), confirmed by the owner. A project that has not switched the gate on (growth.json research_browser.required)
is never blocked.
"""
from __future__ import annotations

import re

import locales
import wizard_state

# code -> (name Google shows, default language)
COUNTRIES = {
    "US": ("United States", "en"), "CA": ("Canada", "en"), "GB": ("United Kingdom", "en"), "AU": ("Australia", "en"),
    "NZ": ("New Zealand", "en"), "IE": ("Ireland", "en"), "IN": ("India", "en"), "ZA": ("South Africa", "en"),
    "SG": ("Singapore", "en"), "AE": ("United Arab Emirates", "en"), "DE": ("Germany", "de"), "FR": ("France", "fr"),
    "ES": ("Spain", "es"), "IT": ("Italy", "it"), "NL": ("Netherlands", "nl"), "SE": ("Sweden", "sv"),
    "MX": ("Mexico", "es"), "BR": ("Brazil", "pt"), "JP": ("Japan", "ja"), "PH": ("Philippines", "en"),
}
NOT_A_REGION = ("current region", "current location", "auto", "automatic", "unknown", "")
REGION_FIX = "Google Search settings > Other settings > Language & region > Results region, choose {country}, save"


def norm(s) -> str:
    return re.sub(r"[^a-z]+", " ", str(s or "").lower()).strip()


def country_name(market: dict) -> str:
    code = str(market.get("primary_country") or "").upper()
    return market.get("country_name") or COUNTRIES.get(code, (code, ""))[0]


def google_params(code: str, lang: str) -> str:
    return locales.google_params(code, lang)


def region_matches(seen, market: dict) -> bool:
    """True when the region Google reported is the target country (by name or by code). "Current Region" is not a country."""
    s = norm(seen)
    if s in NOT_A_REGION:
        return False
    code = str(market.get("primary_country") or "").upper()
    return s in (norm(country_name(market)), norm(code))


def required(cfg: dict) -> bool:
    return bool((cfg.get("research_browser") or {}).get("required"))


def fix_browser(name: str = "") -> str:
    return (f"in Claude Code type /chrome, choose {name or 'the browser named in SETUP.md'}, check \"By default: on\"; then "
            f"growth wizard confirm browser --name \"{name or 'Browser 1'}\", and the owner runs growth approve browser in their own terminal")


def approval_problem(project, step: str, content) -> str | None:
    """None when the owner approved exactly this confirmation (docs/approvals.jsonl); else the plain problem. A status of
    "done" typed into setup-state.json by hand is not an approval."""
    import approvals
    from pathlib import Path
    state, info = approvals.status(Path(project) / "docs", step, step, content)
    if state == "ok":
        return None
    return approvals.explain(state, info, f"the {'research browser' if step == 'browser' else 'Google region'} confirmation",
                             f"growth approve {step}")


def problems(project, cfg: dict) -> list[str]:
    """What is missing, in plain words with the fix. [] when the gate is off or everything is confirmed."""
    if not required(cfg):
        return []
    market = cfg.get("market") or {}
    out = []
    if not market.get("primary_country"):
        out.append("target market not set (growth.json market.primary_country): growth wizard answer market --country US --language en")
    import approvals
    browser = wizard_state.get(project, "browser")
    bname = (browser.get("answer") or {}).get("name", "") if isinstance(browser.get("answer"), dict) else ""
    if browser.get("status") != "done":
        out.append("research browser not connected: " + fix_browser(bname))
    else:
        p = approval_problem(project, "browser", approvals.browser_content(bname))
        if p:
            out.append(p)
    region = wizard_state.get(project, "region")
    seen = (region.get("answer") or {}).get("seen") if isinstance(region.get("answer"), dict) else None
    if market.get("primary_country"):
        want = country_name(market)
        if region.get("status") != "done":
            if seen and not region_matches(seen, market):
                out.append(f"Google's region reads \"{seen}\", not {want}: " + REGION_FIX.format(country=want)
                           + "; then growth wizard confirm region --seen \"" + want + "\", and the owner runs growth approve region")
            else:
                out.append(f"Google region for {want} not verified and confirmed by the owner: growth wizard confirm region --seen "
                           f"\"<what Google's settings page says>\", then the owner runs growth approve region in their own terminal")
        elif not region_matches(seen, market):
            out.append(f"recorded region \"{seen}\" is not the target market {want}: re-check it")
        else:
            p = approval_problem(project, "region", approvals.region_content(seen, want))
            if p:
                out.append(p)
        params = market.get("google_params", "")
        if "pws=0" not in params or f"gl={str(market['primary_country']).lower()}" not in params:
            out.append(f"market.google_params must carry gl={str(market['primary_country']).lower()} and pws=0 (now \"{params}\")")
        out += locales.problems(cfg)                         # every locale: its tag, folder, and its own gl= and pws=0
    return out


def plain_problems(project, cfg: dict) -> list[str]:
    """The same problems as `problems`, each as one plain sentence with no command in it (the commands come second)."""
    if not required(cfg):
        return []
    market = cfg.get("market") or {}
    if not market.get("primary_country"):
        return ["I do not know your target country yet."]
    out = []
    if wizard_state.get(project, "browser").get("status") != "done":
        out.append("The research browser is not connected yet.")
    region = wizard_state.get(project, "region")
    want = country_name(market)
    seen = (region.get("answer") or {}).get("seen") if isinstance(region.get("answer"), dict) else None
    if region.get("status") != "done" or not region_matches(seen, market):
        out.append(f"Google shows \"{seen}\", not {want}." if seen and not region_matches(seen, market)
                   else f"Google's results region is not confirmed as {want} yet.")
    if not out and problems(project, cfg):
        out.append("You have not confirmed the research browser and Google's region in your own terminal yet (growth approve).")
    return out


def problem(project, cfg: dict) -> str | None:
    p = problems(project, cfg)
    return "; ".join(p) if p else None


RESEARCH_WORDS = re.compile(r"research|people also ask|ai overview|chatgpt|dossier|serp", re.I)
ALWAYS_RESEARCH = {"new-post", "update-post", "money-page", "cluster-redesign"}      # their research steps sit in the pages they point to


def playbook_has_research(name: str) -> bool | None:
    """True when the kit's playbook (book/playbooks/<name>.md) has a research step; None when there is no such playbook."""
    from config import BOOK
    f = BOOK / "playbooks" / f"{name.removesuffix('.md')}.md"
    return (f.stem in ALWAYS_RESEARCH or bool(RESEARCH_WORDS.search(f.read_text(errors="replace")))) if f.is_file() else None
