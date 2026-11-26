#!/usr/bin/env python3
"""Collect the brand and contact facts a site states about itself, so BRAND.md is written from the site and not from memory.

  growth brand-scan [--base ADDRESS] [--max-pages N]
  growth brand-scan --base http://127.0.0.1:3801          # a preview or local copy (needed when live_site_rule is no-crawl)

It finds the pages itself: the home page, robots.txt, the sitemap, llms.txt and llms-full.txt (also under /.well-known/), and the
legal, contact, about, pricing and booking pages named in the header, the footer and the sitemap (default 25 pages). Plain
requests, one per second at most, with a generic User-Agent. With growth.json live_site_rule "no-crawl" the live host is
refused, so give --base.

What it reads, each finding with the page it came from and the day it was read:
  company     legal name (Inc., LLC, Ltd, Pvt Ltd, GmbH ...), postal address, governing law, when the terms and privacy pages
              were last updated, the privacy contact, the laws they name, the Organization data (JSON-LD)
  contact     every email (mailto links, text, written out with [at] and [dot], hidden ones), grouped on the company's domain or
              not, each labelled support, sales, privacy, legal, careers, info or other; phone numbers
  booking     Calendly, Cal.com, HubSpot meetings, SavvyCal, TidyCal, Acuity, YouCanBook.me, Zcal, Chili Piper, Google Calendar
              appointment pages, Microsoft Bookings
  CTA         the wording of the buttons and links that ask for action, counted by page; the most common strong one is the main CTA
  AI files    llms.txt and llms-full.txt: title, summary, sections and links
  social      LinkedIn, X, Facebook, Instagram, YouTube, GitHub, Clutch, G2

Writes docs/brand-scan.json and docs/brand-scan.md (a draft of the BRAND.md lines, each with its source). It never changes
BRAND.md and never stores a secret. `growth doctor` (A2) compares BRAND.md with the scan.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_rule  # noqa: E402
import sitemaps  # noqa: E402
from brandscan import contacts, ctas, legal, llms, pick  # noqa: E402
from brandscan.page import Page, absolute, clean_url, host_of  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (compatible; growth-ops-kit brand-scan)", "Accept": "text/html,text/plain,application/xml,*/*;q=0.8"}
MAX_BYTES = 2_000_000
SITEMAP_REQUESTS = 12            # a sitemap index with many children is read only this far
SOURCES_KEPT = 5                 # page addresses stored per finding (the count of pages is kept too)
LOOPBACK = {"127.0.0.1", "localhost", "::1"}
AI_FILES = [("llms_txt", ["/llms.txt", "/.well-known/llms.txt"]), ("llms_full_txt", ["/llms-full.txt", "/.well-known/llms-full.txt"])]


# ---- the one place that asks the network -------------------------------------------------------------------------
class NoLiveRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect from the preview to the live host is not followed when live_site_rule is no-crawl."""
    cfg: dict = {}

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if fetch_rule.blocked(newurl, self.cfg):
            return None
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class HttpFetcher:
    """fetch(url) -> (status, body). One request at a time, `delay` seconds apart (main() never lets it fall under one second
    except for this computer's own addresses)."""

    def __init__(self, cfg: dict, delay: float = 1.0, timeout: int = 20):
        self.delay, self.timeout, self.last = delay, timeout, 0.0
        handler = type("Guard", (NoLiveRedirect,), {"cfg": cfg})
        self.opener = urllib.request.build_opener(handler())

    def __call__(self, url: str):
        wait = self.last + self.delay - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self.last = time.monotonic()
        try:
            with self.opener.open(urllib.request.Request(url, headers=UA), timeout=self.timeout) as r:
                return r.status, r.read(MAX_BYTES).decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            return e.code, ""
        except Exception:  # noqa: BLE001  (DNS, TLS, timeouts)
            return 0, ""


# ---- what one scan keeps ------------------------------------------------------------------------------------------
class Bag:
    """Findings of one kind, each with the pages it was seen on: add(value, source, **extra)."""

    def __init__(self, today: str):
        self.today, self.items = today, {}

    def add(self, key, source: str, **extra):
        rec = self.items.setdefault(key, {**extra, "sources": [], "pages": 0, "read_on": self.today})
        if source and source not in rec["sources"]:
            rec["pages"] += 1
            if len(rec["sources"]) < SOURCES_KEPT:
                rec["sources"].append(source)
        for k, v in extra.items():
            if v and not rec.get(k):
                rec[k] = v
        return rec

    def values(self):
        return list(self.items.values())


def day(cfg_tz=None) -> str:
    return datetime.now(cfg_tz).strftime("%Y-%m-%d") if cfg_tz else datetime.now().strftime("%Y-%m-%d")


def scan(base: str, cfg: dict, max_pages: int = 25, fetch=None, today: str = "") -> dict:
    """Read the site at `base` and return the findings (see the module text). `fetch(url) -> (status, body)` defaults to plain HTTP;
    the live-site rule is checked before every request whatever the fetcher is."""
    base = base.rstrip("/")
    today = today or day()
    raw_fetch = fetch or HttpFetcher(cfg)
    live_host = host_of(cfg.get("site_url") or "")
    own = {host_of(base)} | ({live_host} if live_host else set())
    company_domain = live_host or host_of(base)
    requests = {"n": 0}
    log = {"pages": [], "not_read": []}

    def get(url: str):
        fetch_rule.assert_may_fetch(url, cfg)
        requests["n"] += 1
        return raw_fetch(url)

    def on_base(url: str) -> str:
        """A link to this site, as an address on `base` (a link to the live host becomes a link to the preview)."""
        u = urllib.parse.urlsplit(url)
        return base + (u.path or "/") if host_of(url) in own else ""

    def site_address(url: str) -> str:
        """A link to this site as the live address (a call to action points at the live page, whatever address was read)."""
        u = urllib.parse.urlsplit(url)
        return (cfg.get("site_url") or base).rstrip("/") + (u.path or "/") if host_of(url) in own else url

    emails, phones, booking, social = Bag(today), Bag(today), Bag(today), Bag(today)
    names, copyright_, addresses, law, juris = Bag(today), Bag(today), Bag(today), Bag(today), Bag(today)
    laws, privacy_contacts, dpos = Bag(today), [], []
    updated, orgs, cta_pages, ai = [], [], [], {}
    home = {}

    def see_text_facts(url: str, text: str, doc_html: str, hrefs: list[str]):
        for e in contacts.find_emails(doc_html, text, hrefs):
            emails.add(e, url, email=e, group=contacts.group_of(e, company_domain), label=contacts.label_of(e))
        for ph in contacts.find_phones(text, hrefs):
            phones.add(contacts.phone_key(ph), url, phone=ph)

    def read_page(url: str, status: int, body: str, category: str):
        pg = Page(body, url)
        links = []
        for ln in pg.links:
            ln["href_abs"] = clean_url(absolute(ln["href"], url)) if absolute(ln["href"], url) else ""
            ln["target"] = site_address(ln["href_abs"]) if ln["href_abs"] else ""
            links.append(ln)
        for b in pg.buttons:
            b["href_abs"] = clean_url(absolute(b["href"], url)) if b.get("href") and absolute(b["href"], url) else ""
            b["target"] = site_address(b["href_abs"]) if b["href_abs"] else ""
        hrefs = [ln["href"] for ln in pg.links] + [b["href"] for b in pg.buttons if b.get("href")]
        text = pg.text + ("\n" + "\n".join(pg.addresses) if pg.addresses else "")
        see_text_facts(url, text, body, hrefs)
        for bk in contacts.find_booking(body, [absolute(h, url) or h for h in hrefs]):
            booking.add(bk["url"], url, url=bk["url"], provider=bk["provider"])
        for ln in links:                                     # a profile counts from a header, a footer, or the home, contact and about pages only
            net, prof = contacts.social_of(ln["href_abs"] or ln["href"])
            if net and (ln["region"] in ("header", "footer", "nav", "aside") or category in ("home", "contact", "about")):
                social.add(prof.lower(), url, network=net, url=prof)
        for org in llms.organizations(pg.jsonld):
            orgs.append({**org, "source": url})
        if category == "home":
            home.update(title=re.sub(r"\s+", " ", pg.title).strip(), description=pg.meta.get("description", ""), h1=re.sub(r"\s+", " ", pg.h1).strip(),
                        site_name=pg.meta.get("og:site_name", ""), url=url)
        holder = legal.copyright_holder(pg.text)
        if holder:
            copyright_.add(holder.lower(), url, name=holder)
        if category in pick.NAME_PAGES:
            for rec in legal.legal_names(pg.text):
                r = names.add(re.sub(r"[^a-z0-9]", "", rec["name"].lower()), url, name=rec["name"], context=rec["context"])
                if len(rec["name"]) > len(r["name"]):
                    r["name"] = rec["name"]                      # "Ltd." beats "Ltd" (a footer that runs into the next word)
                r["strong"] = r.get("strong") or rec["strong"]
                r["mentions"] = r.get("mentions", 0) + rec["count"]
        if category in pick.ADDRESS_PAGES:
            for a in legal.postal_addresses(text):
                addresses.add(re.sub(r"\W+", "", a.lower()), url, address=a)
        if category in pick.LEGAL:
            when = legal.last_updated(pg.text)
            if when and category in ("terms", "privacy", "cookie", "legal"):
                updated.append({"document": category, "date": when, "source": url, "read_on": today})
            gl = legal.governing_law(pg.text)
            for place in gl["law"]:
                law.add(place.lower(), url, place=place, sentence=next((s for s in gl["sentences"] if place in s), ""))
            for place in gl["jurisdiction"]:
                juris.add(place.lower(), url, place=place, sentence=next((s for s in gl["sentences"] if place in s), ""))
            for name in legal.named_laws(pg.text):
                laws.add(name, url, law=name)
            if category in ("privacy", "cookie"):
                found = contacts.find_emails(body, text, hrefs)
                d = legal.dpo(pg.text, found)
                if d:
                    dpos.append({**d, "source": url, "read_on": today})
                for e in found:
                    if contacts.label_of(e) == "privacy" or d.get("emails") and e in d["emails"]:
                        privacy_contacts.append({"email": e, "source": url, "read_on": today})
        cta_pages.append({"url": url, "links": links, "buttons": pg.buttons})
        return pg, links

    # 1. the home page
    status, body = get(base + "/")
    if status != 200 or not body:
        raise SystemExit(f"Could not read {base}/ (http {status}). Is the site or preview running? Use --base <address> for a preview.")
    log["pages"].append({"url": base + "/", "path": "/", "category": "home", "status": status})
    pg, home_links = read_page(base + "/", status, body, "home")

    # 2. text files: robots, security.txt, llms
    robots = {"url": base + "/robots.txt", "found": False, "sitemaps": []}
    st, txt = get(base + "/robots.txt")
    if st == 200 and llms.looks_like_text(txt):
        robots.update(found=True, sitemaps=re.findall(r"(?im)^\s*sitemap:\s*(\S+)", txt))
    sec_url = base + "/.well-known/security.txt"
    st, txt = get(sec_url)
    if st == 200 and llms.looks_like_text(txt):
        see_text_facts(sec_url, txt, txt, [])
        log["pages"].append({"url": sec_url, "path": "/.well-known/security.txt", "category": "security.txt", "status": st})
    for key, paths in AI_FILES:
        ai[key] = {"found": False}
        for p in paths:
            st, txt = get(base + p)
            if st == 200 and llms.looks_like_text(txt):
                parsed = llms.parse_llms(txt) if key == "llms_txt" else llms.parse_llms_full(txt)
                ai[key] = {"found": True, "source": base + p, "read_on": today, **parsed}
                log["pages"].append({"url": base + p, "path": p, "category": key.replace("_", "."), "status": st})
                if key == "llms_txt":
                    see_text_facts(base + p, txt, txt, [])
                break
            log["not_read"].append({"url": base + p, "status": st})

    # 3. the sitemap(s)
    sm_requests = {"n": 0}

    def sm_get(url):
        if sm_requests["n"] >= SITEMAP_REQUESTS:
            return 0, ""
        sm_requests["n"] += 1
        return get(url)
    sm_urls: list[str] = []
    sources = [urllib.parse.urlsplit(s).path for s in robots["sitemaps"][:2] if host_of(s) in own] or []
    sources += [urllib.parse.urlsplit(cfg.get("sitemap_url") or "/sitemap.xml").path or "/sitemap.xml", "/sitemap.xml", "/sitemap_index.xml"]
    tried = set()
    for sp in sources:
        if sp in tried or sm_urls or len(tried) >= 3:
            continue
        tried.add(sp)
        try:
            sm_urls = [loc for loc, _lm in sitemaps.read(base + sp, get=sitemaps.on_origin(base, sm_get))]
        except sitemaps.SitemapError:
            continue

    # 4. the pages worth reading: from the links of the home page, the sitemap, then the links of every page read
    queue: dict[str, tuple[int, str, str]] = {}   # address without its slash -> (score, category, address as linked)
    norm = lambda u: u.rstrip("/").lower()        # noqa: E731  /terms and /terms/ are one page
    done = {norm(base + "/")}                     # the home page is read already

    def offer(url: str, text: str = "", region: str = "", from_sitemap: bool = False):
        u = on_base(url)
        if not u or norm(u) in done or not pick.worth_reading(u, region):
            return
        cat = pick.category_of(u, text)
        if not cat:
            return
        sc = pick.score(u, cat, region, from_sitemap)
        if norm(u) not in queue or queue[norm(u)][0] < sc:       # the form a page links to wins over the sitemap's form
            queue[norm(u)] = (sc, cat, u)

    for ln in home_links:
        offer(ln["href_abs"], ln["text"], ln["region"])
    for loc in sm_urls:
        offer(loc, from_sitemap=True)
    taken: dict[str, int] = {}
    read_count = 1
    while queue and read_count < max_pages:
        k, (sc, cat, url) = max(queue.items(), key=lambda kv: (kv[1][0], -len(kv[0])))
        del queue[k]
        if taken.get(cat, 0) >= 3 or k in done:
            continue
        taken[cat] = taken.get(cat, 0) + 1
        done.add(k)
        st, doc = get(url)
        if st == 404 and not url.endswith("/"):                  # a server that wants the slash
            st, doc = get(url + "/")
            url = url + "/" if st == 200 else url
        read_count += 1
        if st != 200 or not doc:
            log["not_read"].append({"url": url, "status": st})
            continue
        log["pages"].append({"url": url, "path": urllib.parse.urlsplit(url).path or "/", "category": cat, "status": st})
        _pg, links = read_page(url, st, doc, cat)
        if cat in pick.LEGAL | {"contact", "demo", "about"}:
            for ln in links:
                offer(ln["href_abs"], ln["text"], ln["region"])

    # 5. put it together
    cta_list = ctas.collect(cta_pages)
    top = next((t for t in ("strong", "medium", "weak") if any(c["strength"] == t for c in cta_list)), "")
    leaders = [c for c in cta_list if c["strength"] == top]
    for o in orgs:                                                    # the Organization data counts as a source too
        if o.get("email"):
            e = o["email"].lower()
            emails.add(e, o["source"] + " (JSON-LD)", email=e, group=contacts.group_of(e, company_domain), label=contacts.label_of(e))
        if o.get("telephone"):
            phones.add(contacts.phone_key(o["telephone"]), o["source"] + " (JSON-LD)", phone=o["telephone"])
        for s in o.get("sameAs", []):
            net, prof = contacts.social_of(s)
            if net:
                social.add(prof.lower(), o["source"] + " (JSON-LD sameAs)", network=net, url=prof)
    em = sorted(emails.values(), key=lambda e: (e["group"] != "company", ["support", "sales", "info", "privacy", "legal", "careers", "other"].index(e["label"]), e["email"]))
    findings = {
        "company": {
            "home": home,
            "legal_names": sorted(names.values(), key=lambda n: (not n.get("strong"), -n.get("mentions", 0), -n["pages"])),
            "copyright_holders": sorted(copyright_.values(), key=lambda n: -n["pages"]),
            "organization_data": orgs,
            "addresses": sorted(addresses.values(), key=lambda a: -a["pages"]),
            "governing_law": law.values(), "jurisdiction": juris.values(), "last_updated": updated,
            "laws": sorted(laws.values(), key=lambda x: -x["pages"]),
            "privacy_contacts": privacy_contacts, "data_protection_officer": dpos,
        },
        "emails": em,
        "phones": phones.values(),
        "booking_links": booking.values(),
        "ctas": cta_list[:30],
        "main_cta": leaders[0] if leaders else None,
        "llms_txt": ai.get("llms_txt", {}), "llms_full_txt": ai.get("llms_full_txt", {}),
        "social": sorted(social.values(), key=lambda s: (s["network"], s["url"])),
        "robots": robots,
    }
    result = {"tool": "growth brand-scan", "read_on": today, "base": base, "company_domain": company_domain, "max_pages": max_pages,
              "requests": requests["n"], "pages": log["pages"], "not_read": log["not_read"], "findings": findings}
    result["conflicts"] = conflicts(findings)
    result["not_found"] = not_found(findings)
    return result


def _distinct(values, norm=lambda v: re.sub(r"\W+", "", v.lower())):
    out, seen = [], set()
    for v in values:
        if norm(v) not in seen:
            seen.add(norm(v))
            out.append(v)
    return out


def conflicts(f: dict) -> list[dict]:
    """Places where the site says two different things, for the owner to settle."""
    out = []
    by_label: dict[str, list[str]] = {}
    for e in f["emails"]:
        if e["group"] == "company":
            by_label.setdefault(e["label"], []).append(e["email"])
    for label, vals in by_label.items():
        if len(vals) > 1 and label != "other":
            out.append({"what": f"{len(vals)} different {label} emails on the company domain", "values": vals})
    if len(f["booking_links"]) > 1:
        out.append({"what": "more than one booking link", "values": [b["url"] for b in f["booking_links"]]})
    names = _distinct([n["name"] for n in f["company"]["legal_names"] if n.get("strong")] +
                      [o["legalName"] for o in f["company"]["organization_data"] if o.get("legalName")])
    if len(names) > 1:
        out.append({"what": "more than one legal name", "values": names})
    laws = _distinct([x["place"] for x in f["company"]["governing_law"]])
    if len(laws) > 1:
        out.append({"what": "more than one governing law", "values": laws})
    m = f["main_cta"]
    tie = [c["text"] for c in f["ctas"] if m and c["strength"] == m["strength"] and len(c["pages"]) == len(m["pages"])]
    if len(tie) > 1:
        out.append({"what": "two calls to action are equally common, so the main one is unclear", "values": tie[:4]})
    return out


def not_found(f: dict) -> list[str]:
    c, out = f["company"], []
    for ok, what in [(c["legal_names"] or c["copyright_holders"], "legal company name"), (c["addresses"], "postal address"),
                     (c["governing_law"] or c["jurisdiction"], "governing law"), (c["last_updated"], "last-updated date of the terms or privacy page"),
                     (any(e["group"] == "company" for e in f["emails"]), "email on the company's own domain"), (f["phones"], "phone number"),
                     (f["booking_links"], "booking link (Calendly and the like)"), (f["main_cta"], "call to action"),
                     (f["llms_txt"].get("found"), "llms.txt"), (f["llms_full_txt"].get("found"), "llms-full.txt"), (f["social"], "social profiles")]:
        if not ok:
            out.append(what)
    return out


# ---- the draft of BRAND.md -----------------------------------------------------------------------------------------
def short(url: str) -> str:
    """A page address as its path, for a source cell."""
    u = urllib.parse.urlsplit(re.sub(r" \(.*\)$", "", url))
    return (u.path or "/") + (" (JSON-LD)" if "(JSON-LD" in url else "")


def src(rec: dict) -> str:
    srcs = rec.get("sources") or rec.get("pages") or []
    total = rec["pages"] if isinstance(rec.get("pages"), int) else len(srcs)
    return ", ".join(f"`{short(x)}`" for x in srcs[:3]) + (f" +{total - 3} more" if total > 3 else "")


def cell(t: str) -> str:
    return str(t).replace("|", "/").replace("\n", " ").strip()


def render_md(r: dict) -> str:
    f, c = r["findings"], r["findings"]["company"]
    first = lambda items: items[0] if items else None  # noqa: E731
    L = ["# Brand scan: draft lines for BRAND.md", "",
         f"Read from {r['base']} on {r['read_on']} by `growth brand-scan` ({len(r['pages'])} pages). **A draft, not BRAND.md:** check every line, "
         "then paste what is right into BRAND.md section 1a and section 4. Each line shows the page it came from.", ""]
    if r["conflicts"]:
        L += ["## The site says two things (ask the owner)", ""] + [f"- {x['what']}: " + "; ".join(f"`{v}`" for v in x["values"]) for x in r["conflicts"]] + [""]
    L += ["## 1a. Company and contact facts", "", "| Field | Wording | Source |", "| --- | --- | --- |"]
    n = first(c["legal_names"])
    ch = first(c["copyright_holders"])
    org = first([o for o in c["organization_data"] if o.get("legalName")])
    L.append("| Legal name | " + (cell(n["name"]) if n else cell(org["legalName"]) if org else (cell(ch["name"]) + " (footer ©, not a legal name)") if ch else "not found") +
             " | " + (src(n) if n else f"`{short(org['source'])}` (JSON-LD)" if org else src(ch) if ch else "") + " |")
    a = first(c["addresses"])
    L.append("| Postal address | " + (cell(a["address"]) if a else "not found") + " | " + (src(a) if a else "") + " |")
    gl = first(c["governing_law"])
    jr = first(c["jurisdiction"])
    L.append("| Governing law | " + (cell(gl["place"]) if gl else "not found") + " | " + (src(gl) if gl else "") + " |")
    if jr:
        L.append(f"| Courts or jurisdiction | {cell(jr['place'])} | {src(jr)} |")
    for e in f["emails"]:
        if e["group"] == "company":
            L.append(f"| Email, {e['label']} | `{e['email']}` | {src(e)} |")
    others = [e for e in f["emails"] if e["group"] != "company"]
    if others:
        L.append("| Emails on other domains | " + ", ".join(f"`{e['email']}` ({e['label']})" for e in others[:8]) + " | " + src(others[0]) + " |")
    for ph in f["phones"]:
        L.append(f"| Phone | {cell(ph['phone'])} | {src(ph)} |")
    for pc in c["privacy_contacts"][:2]:
        L.append(f"| Privacy contact | `{pc['email']}` | `{short(pc['source'])}` |")
    for d in c["data_protection_officer"][:1]:
        L.append(f"| Data protection officer | {cell(d['sentence'][:160])} | `{short(d['source'])}` |")
    for b in f["booking_links"]:
        L.append(f"| Booking link ({b['provider']}) | {b['url']} | {src(b)} |")
    for s in f["social"]:
        L.append(f"| {s['network']} | {s['url']} | {src(s)} |")
    docs = {}
    for u in c["last_updated"]:
        docs.setdefault(u["document"], u)
    for doc, u in docs.items():
        L.append(f"| {doc.capitalize()} page last updated | {cell(u['date'])} | `{short(u['source'])}` |")
    if c["laws"]:
        L.append("| Laws and standards named | " + ", ".join(x["law"] for x in c["laws"]) + " | " + src(c["laws"][0]) + " |")
    L += ["", "## 4. How people buy: rows to add", "", "| Field | Wording | Source |", "| --- | --- | --- |"]
    m = f["main_cta"]
    L.append("| The one CTA label (the most common on the site) | " + (f"\"{cell(m['text'])}\" ({m['count']} times on {len(m['pages'])} pages)" if m else "not found") + " | " + (src(m) if m else "") + " |")
    if m and m["targets"]:
        L.append(f"| The one conversion path (where it points) | {m['targets'][0]} | {src(m)} |")
    bk = first(f["booking_links"])
    L.append("| Booking link | " + (bk["url"] if bk else "none found") + " | " + (src(bk) if bk else "") + " |")
    others = [x for x in f["ctas"] if x is not m][:8]
    L.append("| Other CTA wordings found on the site | " + ("; ".join(f"\"{cell(x['text'])}\" ({len(x['pages'])} page{'s' if len(x['pages']) != 1 else ''})" for x in others) or "none") + " | the pages listed in `docs/brand-scan.json` |")
    L += ["", "## What the site tells AI tools", ""]
    for key, label in (("llms_txt", "llms.txt"), ("llms_full_txt", "llms-full.txt")):
        d = f[key]
        if not d.get("found"):
            L.append(f"- {label}: not found.")
            continue
        L.append(f"- {label} (`{short(d['source'])}`): " + (f"title \"{d['title']}\"" if d.get("title") else "no title") +
                 (f"; summary: {d['summary']}" if d.get("summary") else "") + (f"; {d['links']} links in {len(d['sections'])} sections" if "sections" in d else f"; {d['chars']} characters, {d['heading_count']} headings"))
        for s in (d.get("sections") or [])[:8]:
            L.append(f"  - {s['heading']}: " + ", ".join(x["text"] for x in s["links"][:6]))
    h = c["home"]
    if h:
        L += ["", "## Home page words", "", f"- Title: {h.get('title', '')}", f"- Description: {h.get('description', '')}", f"- H1: {h.get('h1', '')}"]
    L += ["", "## Not found", ""] + ([f"- {x}" for x in r["not_found"]] or ["- nothing missing"])
    return "\n".join(L) + "\n"


def summary(r: dict, wrote: list[str]) -> str:
    f, c = r["findings"], r["findings"]["company"]
    L = [f"Brand scan of {r['base']}: read {len(r['pages'])} pages ({len(r['not_read'])} could not be read), {r['requests']} requests."]
    n = c["legal_names"][0]["name"] if c["legal_names"] else (c["organization_data"][0]["legalName"] if [o for o in c["organization_data"] if o.get("legalName")] else "")
    L.append(f"Legal name: {n or 'not found'}" + (f" (footer says: {c['copyright_holders'][0]['name']})" if c["copyright_holders"] and not n else ""))
    L.append("Address: " + (c["addresses"][0]["address"] if c["addresses"] else "not found"))
    L.append("Governing law: " + ("; ".join(x["place"] for x in c["governing_law"][:2]) or "not found") +
             ("; courts: " + "; ".join(x["place"] for x in c["jurisdiction"][:2]) if c["jurisdiction"] else ""))
    if c["last_updated"]:
        L.append("Last updated: " + "; ".join(f"{u['document']} {u['date']}" for u in c["last_updated"][:3]))
    comp = [e for e in f["emails"] if e["group"] == "company"]
    L.append(f"Emails on the company's domain ({len(comp)}): " + (", ".join(f"{e['email']} ({e['label']})" for e in comp[:10]) or "none found"))
    other = [e for e in f["emails"] if e["group"] != "company"]
    if other:
        L.append(f"Emails on other domains ({len(other)}): " + ", ".join(e["email"] for e in other[:5]))
    L.append(f"Phones ({len(f['phones'])}): " + (", ".join(p["phone"] for p in f["phones"][:5]) or "none found"))
    L.append("Booking links: " + ("; ".join(f"{b['provider']} {b['url']}" for b in f["booking_links"][:4]) or "none found"))
    m = f["main_cta"]
    L.append("Main call to action: " + (f"\"{m['text']}\" (on {len(m['pages'])} pages)" if m else "none found") +
             (" | others: " + ", ".join(f"\"{x['text']}\"" for x in f["ctas"] if x is not m)[:140] if len(f["ctas"]) > 1 else ""))
    for key, label in (("llms_txt", "llms.txt"), ("llms_full_txt", "llms-full.txt")):
        d = f[key]
        L.append(f"{label}: " + (f"found, \"{d.get('title') or 'no title'}\"" if d.get("found") else "not found"))
    L.append("Social: " + (", ".join(f"{s['network']}" for s in f["social"]) or "none found"))
    if c["laws"]:
        L.append("Laws named: " + ", ".join(x["law"] for x in c["laws"][:8]))
    for x in r["conflicts"]:
        L.append(f"ASK THE OWNER: {x['what']}: " + "; ".join(x["values"][:4]))
    if r["not_found"]:
        L.append("Not found on the site: " + ", ".join(r["not_found"]) + ".")
    if wrote:
        L.append("Written: " + ", ".join(wrote) + ". BRAND.md was not changed.")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="", help="read the pages from this address (a preview or local copy). Default: growth.json site_url; refused when live_site_rule is no-crawl")
    ap.add_argument("--max-pages", type=int, default=25, help="most pages to read (default 25)")
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between requests (1 or more; a lower number is used only for this computer's own addresses)")
    ap.add_argument("--dry-run", action="store_true", help="print the summary and write no file")
    a = ap.parse_args(argv)
    import config
    cfg = config.CFG
    base = (a.base or config.SITE_URL).rstrip("/")
    if not base:
        sys.exit("growth.json has no site_url. Give --base <address>.")
    fetch_rule.assert_may_fetch(base + "/", cfg)                      # stop at once, in plain words, before any request
    fetcher = HttpFetcher(cfg, max(0.0, a.delay) if host_of(base) in LOOPBACK else max(1.0, a.delay))
    result = scan(base, cfg, max(1, a.max_pages), fetch=fetcher, today=day(config.TZ))
    wrote = []
    if not a.dry_run:
        config.DOCS.mkdir(parents=True, exist_ok=True)
        (config.DOCS / "brand-scan.json").write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n")
        (config.DOCS / "brand-scan.md").write_text(render_md(result))
        wrote = ["docs/brand-scan.json", "docs/brand-scan.md"]
    print(summary(result, wrote))
    return 0


if __name__ == "__main__":
    sys.exit(main())
