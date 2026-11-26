"""Emails, phone numbers, booking links and social profiles found in a page."""
from __future__ import annotations

import html
import re
from urllib.parse import unquote, urlsplit

from .page import clean_url, host_of

# ---- emails -------------------------------------------------------------------------------------------------------
EMAIL = re.compile(r"(?<![\w.%+-])[A-Za-z0-9][A-Za-z0-9._%+-]{0,63}@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}(?![\w-])")
AT = r"(?:\s*[\[({]\s*at\s*[\])}]\s*|\s+AT\s+)"
DOT = r"(?:\s*[\[({]\s*dot\s*[\])}]\s*|\s+DOT\s+)"
OBFUSCATED = re.compile(rf"(?<![\w.%+-])([A-Za-z0-9][A-Za-z0-9._%+-]{{0,63}}){AT}((?:[A-Za-z0-9-]+(?:{DOT}|\.))+[A-Za-z]{{2,}})(?![\w-])")
NOT_EMAIL_TLD = {"png", "jpg", "jpeg", "gif", "webp", "svg", "css", "js", "ico", "avif", "woff", "woff2", "map", "mp4", "pdf"}
CF_LINK = re.compile(r"/cdn-cgi/l/email-protection#([0-9a-fA-F]{6,})")
CF_ATTR = re.compile(r"""data-cfemail=["']([0-9a-fA-F]{6,})["']""")

# label by the part before the @
LABELS = {
    "support": ("support", "help", "helpdesk", "customerservice", "customer-service", "customersupport", "customer-support", "care", "service", "assistance"),
    "sales": ("sales", "business", "biz", "bizdev", "bd", "partners", "partnership", "partnerships", "quotes", "quote", "enterprise", "demo", "orders"),
    "privacy": ("privacy", "dpo", "gdpr", "dataprotection", "data-protection", "datasubject"),
    "legal": ("legal", "compliance", "terms", "copyright", "dmca", "abuse", "trust"),
    "careers": ("careers", "career", "jobs", "job", "hr", "recruiting", "recruitment", "talent", "hiring", "people"),
    "info": ("info", "hello", "hi", "contact", "contactus", "contact-us", "enquiries", "enquiry", "inquiries", "inquiry", "mail", "office", "team", "general", "welcome", "connect"),
}
LABEL_OF = {w: label for label, words in LABELS.items() for w in words}


def decode_cloudflare(hexstr: str) -> str:
    """Cloudflare hides an address as hex: the first byte is the key, every other byte is xor-ed with it."""
    try:
        b = bytes.fromhex(hexstr)
        return bytes(c ^ b[0] for c in b[1:]).decode("utf-8", errors="strict")
    except (ValueError, UnicodeDecodeError, IndexError):
        return ""


def label_of(email: str) -> str:
    local = email.split("@", 1)[0].lower()
    if local in LABEL_OF:
        return LABEL_OF[local]
    plain = re.sub(r"[._+-]", "", local)
    for w, label in LABEL_OF.items():
        if plain == re.sub(r"[._+-]", "", w):
            return label
    return "other"


def group_of(email: str, company_domain: str) -> str:
    """"company" when the address is on the company's own domain (or a sub-domain of it), else "other"."""
    dom = email.rsplit("@", 1)[-1].lower()
    cd = (company_domain or "").lower().removeprefix("www.")
    return "company" if cd and (dom == cd or dom.endswith("." + cd)) else "other"


def _clean_email(e: str) -> str:
    e = e.strip().strip(".,;:()<>[]\"'").lower()
    tld = e.rsplit(".", 1)[-1]
    if "@" not in e or tld in NOT_EMAIL_TLD or re.search(r"@\d+x\.", e) or re.fullmatch(r"[0-9a-f]{24,}@.*", e):
        return ""                                  # an image name with an at sign (a 2x logo), a tracking id at a monitoring host
    return e


def find_emails(doc_html: str, text: str, hrefs: list[str]) -> list[str]:
    """Every address in the page, in order, no repeats: mailto: links, the text, written-out forms (written out with [at] and [dot])
    and Cloudflare's hidden ones."""
    found: list[str] = []

    def add(e):
        e = _clean_email(e)
        if e and e not in found:
            found.append(e)
    for h in hrefs:
        if h.lower().startswith("mailto:"):
            for part in unquote(html.unescape(h[7:])).split("?", 1)[0].split(","):
                add(part)
    for m in CF_LINK.finditer(doc_html or ""):
        add(decode_cloudflare(m.group(1)))
    for m in CF_ATTR.finditer(doc_html or ""):
        add(decode_cloudflare(m.group(1)))
    for m in EMAIL.finditer(text or ""):
        add(m.group(0))
    for m in OBFUSCATED.finditer(text or ""):
        dom = re.sub(DOT, ".", m.group(2))
        add(m.group(1) + "@" + re.sub(r"\s+", "", dom))
    return found


# ---- phone numbers ------------------------------------------------------------------------------------------------
PHONE_WORD = re.compile(r"(?i)\b(?:tel|telephone|phone|call|mobile|cell|whatsapp|toll[- ]?free|sales|support|contact)\b[^\n]{0,30}$")
FAX_WORD = re.compile(r"(?i)\bfax\b[^\n]{0,12}$")
PHONE_TEXT = re.compile(r"(?<![\w.+/-])(\+\d[\d\s().-]{6,18}\d|\(\d{2,4}\)\s?\d[\d\s.-]{5,12}\d|\d{3}[ .-]\d{3}[ .-]\d{4}|\b1-8(?:00|33|44|55|66|77|88)-\d{3}-\d{4})(?![\w-])")
DATE_LIKE = re.compile(r"^\d{4}[-./]\d{1,2}[-./]\d{1,2}$|^\d{1,2}[-./]\d{1,2}[-./]\d{2,4}$")


def _phone_ok(raw: str, before: str) -> bool:
    digits = re.sub(r"\D", "", raw)
    if not 8 <= len(digits) <= 15 or DATE_LIKE.match(raw.strip()) or FAX_WORD.search(before):
        return False
    if re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", raw.strip()):
        return False                                # an IP address
    return raw.strip().startswith("+") or "(" in raw or bool(PHONE_WORD.search(before)) or bool(re.search(r"\d[ .-]\d", raw)) and len(digits) in (10, 11)


def phone_key(raw: str) -> str:
    plus = "+" if raw.strip().startswith("+") else ""
    d = re.sub(r"\D", "", raw)
    return plus + d


def find_phones(text: str, hrefs: list[str]) -> list[str]:
    """Phone numbers as written: tel: links first, then numbers in the text that look like phones (a + prefix, brackets, or
    a phone word just before them). Dates, IP addresses and fax numbers are left out."""
    out: dict[str, str] = {}
    for h in hrefs:
        if h.lower().startswith("tel:"):
            raw = unquote(html.unescape(h[4:])).split(";", 1)[0].strip()
            if 7 <= len(re.sub(r"\D", "", raw)) <= 15:
                out.setdefault(phone_key(raw), raw)
    for line in (text or "").splitlines():
        for m in PHONE_TEXT.finditer(line):
            raw = m.group(1).strip()
            if _phone_ok(raw, line[max(0, m.start() - 40):m.start()]):
                out.setdefault(phone_key(raw), raw)
    return list(out.values())


# ---- booking links ------------------------------------------------------------------------------------------------
# provider -> (host test, first path words that are the provider's own marketing pages, not a person's booking page)
MARKETING = {"", "pricing", "features", "blog", "integrations", "about", "customers", "resources", "legal", "privacy", "terms", "help",
             "solutions", "enterprise", "product", "products", "partners", "careers", "login", "signup", "sign-up", "app", "docs", "api",
             "security", "support", "contact", "demo", "templates", "use-cases", "compare", "scheduling", "meeting-scheduling", "home", "tour",
             "learn", "ebooks", "webinars", "academy", "book-a-demo", "request-demo", "download"}
PROVIDERS = [
    ("Calendly", re.compile(r"^(?:[\w-]+\.)?calendly\.com$")),
    ("Cal.com", re.compile(r"^(?:app\.|[\w-]+\.)?cal\.com$")),
    ("HubSpot meetings", re.compile(r"^meetings(?:-[a-z0-9]+)?\.hubspot\.com$")),
    ("SavvyCal", re.compile(r"^(?:[\w-]+\.)?savvycal\.com$")),
    ("TidyCal", re.compile(r"^(?:[\w-]+\.)?tidycal\.com$")),
    ("Acuity Scheduling", re.compile(r"^(?:[\w-]+\.)?acuityscheduling\.com$|^[\w-]+\.as\.me$")),
    ("YouCanBook.me", re.compile(r"^(?:[\w-]+\.)?youcanbook\.me$")),
    ("Zcal", re.compile(r"^(?:[\w-]+\.)?zcal\.co$")),
    ("Chili Piper", re.compile(r"^(?:[\w-]+\.)?chilipiper\.com$")),
    ("Google Calendar appointments", re.compile(r"^calendar\.(?:google\.com|app\.google)$")),
    ("Microsoft Bookings", re.compile(r"^(?:outlook\.office365\.com|outlook\.office\.com|outlook\.live\.com|bookings\.microsoft\.com)$|^[\w-]+\.setmore\.com$")),
]
URL_IN_TEXT = re.compile(r"""https?:(?://|\\/\\/)[^\s"'<>\\)\]]+(?:\\/[^\s"'<>\\)\]]*)*""")


def booking_provider(url: str) -> str:
    """The booking tool a web address belongs to, or "" (also "" for the tool's own home and marketing pages)."""
    u = urlsplit(url)
    host = (u.hostname or "").lower()
    first = (u.path.strip("/").split("/") or [""])[0].lower()
    for name, rx in PROVIDERS:
        if not rx.match(host):
            continue
        if name == "Google Calendar appointments":
            return name if "/appointments" in u.path or host == "calendar.app.google" and first else ""
        if name == "Microsoft Bookings":
            return name if host == "bookings.microsoft.com" or re.search(r"/(?:book|bookwithme|bookings)\b|/calendar/", u.path, re.I) else ""
        labels = host.split(".")
        own_subdomain = len(labels) > 2 and labels[0] not in ("www", "app", "meetings") and not host.endswith(".hubspot.com")
        return name if first not in MARKETING or (own_subdomain and first == "") else ""
    return ""


def find_booking(doc_html: str, hrefs: list[str]) -> list[dict]:
    """[{url, provider}] from links, embeds and scripts: every web address in the HTML whose host is a booking tool."""
    seen: dict[str, str] = {}
    cands = list(hrefs) + [m.group(0).replace("\\/", "/") for m in URL_IN_TEXT.finditer(doc_html or "")]
    for c in cands:
        c = html.unescape(c).replace("\\/", "/").rstrip(".,;")
        if not c.lower().startswith("http"):
            continue
        prov = booking_provider(c)
        if prov:
            seen.setdefault(clean_url(c), prov)
    return [{"url": u, "provider": p} for u, p in seen.items()]


# ---- social profiles ----------------------------------------------------------------------------------------------
SHARE = re.compile(r"(?i)/share|sharer|/intent/|shareArticle|/sharing|/dialog/|/login|/signup|/tr\?|/plugins/|/hashtag/|/search\b|/embed/|/watch\?|/policies|/legal|/help")
SOCIAL = [
    ("LinkedIn", re.compile(r"^(?:[\w-]+\.)?linkedin\.com$"), re.compile(r"^/(company|in|school|showcase)/[^/]+")),
    ("X", re.compile(r"^(?:mobile\.)?(?:x|twitter)\.com$"), re.compile(r"^/(?!home|i/|search|share|intent|hashtag|login|signup|explore|settings|privacy|tos)[A-Za-z0-9_]{1,15}/?$")),
    ("Facebook", re.compile(r"^(?:[\w-]+\.)?(?:facebook|fb)\.com$"), re.compile(r"^/(?!sharer|share|dialog|plugins|tr|login|policies|help|groups/?$)[^/]+")),
    ("Instagram", re.compile(r"^(?:www\.)?instagram\.com$"), re.compile(r"^/(?!p/|reel/|explore|accounts|about|legal|developer)[A-Za-z0-9_.]+/?$")),
    ("YouTube", re.compile(r"^(?:www\.|m\.)?youtube\.com$"), re.compile(r"^/(@[\w.-]+|channel/[\w-]+|c/[\w.-]+|user/[\w.-]+)")),
    ("GitHub", re.compile(r"^(?:www\.)?github\.com$"), re.compile(r"^/(?!features|pricing|login|join|about|sponsors|topics|marketplace|enterprise|orgs/?$)[A-Za-z0-9_.-]+/?$")),
    ("Clutch", re.compile(r"^(?:www\.)?clutch\.co$"), re.compile(r"^/profile/[^/]+")),
    ("G2", re.compile(r"^(?:www\.)?g2\.com$"), re.compile(r"^/(products|sellers)/[^/]+")),
]


def social_of(url: str) -> tuple[str, str]:
    """(network, clean address) for a profile link, ("", "") for a share button or anything else."""
    u = urlsplit(url or "")
    host = (u.hostname or "").lower().removeprefix("www.")
    if not u.scheme.startswith("http") or SHARE.search(u.path + ("?" + u.query if u.query else "")):
        return "", ""
    for name, hrx, prx in SOCIAL:
        if hrx.match(u.hostname.lower() if u.hostname else "") and prx.match(u.path):
            segs = [s for s in u.path.split("/") if s]
            n = 2 if name in ("LinkedIn", "Clutch", "G2") or name == "YouTube" and not segs[0].startswith("@") else 1
            return name, f"https://{host}/" + "/".join(segs[:n])
    return "", ""
