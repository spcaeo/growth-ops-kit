"""Which pages of a site hold brand facts: the legal pages, contact, about, pricing, booking and the like."""
from __future__ import annotations

import re
from urllib.parse import urlsplit

# category -> (pattern on the address's words or the link text, weight: higher is read first)
CATEGORIES = [
    ("terms", r"terms|tos|t-c|t&c|conditions|eula|user-agreement|service-agreement|terms-of-(?:use|service|sale)", 10),
    ("privacy", r"privacy|gdpr|ccpa|data-protection|data-policy|personal-data", 10),
    ("contact", r"contact|contact-us|get-in-touch|reach-us|write-to-us|enquir(?:y|ies)|inquir(?:y|ies)", 9),
    ("about", r"about|about-us|company|who-we-are|our-story|our-company|team|mission", 8),
    ("demo", r"demo|book|booking|schedule|appointment|consult(?:ation)?|get-quote|quote|estimate|talk-to|free-call|discovery", 8),
    ("pricing", r"pricing|plans|prices|price", 7),
    ("legal", r"legal|disclaimer|compliance|acceptable-use|aup|dpa|sub-?processors?", 6),
    ("imprint", r"imprint|impressum", 6),
    ("security", r"security|trust|hipaa|soc-?2|iso-?27001", 5),
    ("cookie", r"cookies?|cookie-policy", 5),
    ("support", r"support|help|help-center|customer-service", 5),
    ("careers", r"careers?|jobs|join-us|hiring", 4),
    ("accessibility", r"accessibility|wcag|ada", 3),
    ("press", r"press|media|newsroom|press-kit", 3),
]
RX = [(name, re.compile(rf"(?<![a-z0-9])(?:{pat})(?![a-z0-9])", re.I), w) for name, pat, w in CATEGORIES]
LEGAL = {"terms", "privacy", "cookie", "legal", "imprint", "security", "accessibility"}
ADDRESS_PAGES = {"home", "contact", "about", "terms", "privacy", "imprint", "legal", "cookie"}
NAME_PAGES = LEGAL | {"home", "contact", "about"}
POSTS = re.compile(r"(?i)^/(?:blog|news|posts?|articles?|insights?|resources|case-stud(?:y|ies)|portfolio|podcast|webinars?|ebooks?|guides?|tag|category|author)/")
FILES = re.compile(r"(?i)\.(?:pdf|png|jpe?g|gif|svg|webp|zip|xml|json|css|js|mp4|mp3|ico|docx?|xlsx?)$")
WEIGHT = {n: w for n, _, w in CATEGORIES}


def category_of(url: str, text: str = "") -> str:
    """The category of a page from its address's words (the path only) and from a link's own words; the heavier of the two wins
    ("" when neither says anything). A link "Privacy Policy" to /legal/p is privacy, not just legal."""
    path = urlsplit(url).path.lower().strip("/")
    words = re.sub(r"[/_.]+", "-", path)
    found = []
    if path:
        found += [name for name, rx, _w in RX if rx.search(words)][:1]
    t = re.sub(r"\s+", " ", text or "").strip().lower()
    if 1 < len(t) <= 40:
        found += [name for name, rx, _w in RX if rx.search(re.sub(r"\s+", "-", t))][:1]
    return max(found, key=lambda n: WEIGHT[n]) if found else ""


def score(url: str, category: str, region: str = "", from_sitemap: bool = False) -> int:
    path = urlsplit(url).path
    depth = len([s for s in path.split("/") if s])
    s = WEIGHT.get(category, 0) * 10 + (30 if region in ("footer", "header", "nav") else 0) - depth * 4
    return s - (10 if from_sitemap else 0)


def worth_reading(url: str, region: str = "") -> bool:
    """False for a file, and for a blog post or any page more than two folders deep (an article about "privacy" or "contact" is
    not the privacy or contact page), unless a header or footer links to it."""
    path = urlsplit(url).path
    linked = region in ("footer", "header", "nav")
    deep = len([s for s in path.split("/") if s]) > 2
    return not FILES.search(path) and (linked or not (POSTS.search(path) or deep))
