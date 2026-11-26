"""Calls to action: the wording of the buttons and links that ask a visitor to do something (book, call, get a quote ...)."""
from __future__ import annotations

import re

STRONG = re.compile(r"(?i)\b(?:book|demo|schedule|appointment|quote|estimate|trial|get started|talk to|speak (?:to|with)|consult|call (?:us|now|me|today)|free call|discovery)\b")
MEDIUM = re.compile(r"(?i)\b(?:hire|request|get a|get an|get your|free)\b")
WEAK = re.compile(r"(?i)\b(?:contact|start|get in touch|reach out|sign up|try|join|learn how|apply)\b")
VERBS = {"book", "schedule", "get", "request", "start", "talk", "speak", "call", "contact", "hire", "try", "see", "watch", "download", "join",
         "sign", "claim", "reserve", "ask", "chat", "meet", "let's", "lets", "apply", "discuss", "connect", "send", "begin", "grab", "plan",
         "arrange", "set", "free", "my", "your", "consult", "demo", "quote", "reach", "write", "message", "email", "text", "whatsapp", "work"}
NOISE = re.compile(r"(?i)^(?:skip to|read more|learn more|view all|see all|show more|menu|close|open|previous|next|back|share|home|login|log in|sign in|accept|reject|cookie|privacy|terms|\d+)")


def clean_label(text: str) -> str:
    t = re.sub(r"[→›»>«←↗⟶➜➔▶►✓✔]+", " ", text or "")
    t = re.sub(r"\s+", " ", t).strip(" \t\n.:|-–—")
    return t


def is_cta(text: str) -> str:
    """"strong" (book a demo, get a quote), "medium" (hire developers, request ...), "weak" (contact us, start) or "" (not a call to action)."""
    t = clean_label(text)
    words = t.lower().replace("’", "'").split()
    if not t or len(t) > 45 or len(words) > 6 or NOISE.search(t) or not VERBS & set(w.strip("?!,.:;") for w in words[:2]):
        return ""                                  # "Appointment reminder app for clinics" is a page title, not a button
    if STRONG.search(t):
        return "strong"
    if MEDIUM.search(t):
        return "medium"
    return "weak" if WEAK.search(t) else ""


def collect(pages: list[dict]) -> list[dict]:
    """Count each wording over the pages. `pages`: [{url, links: [{text, href, region}], buttons: [{text, region, href}]}].
    Returns [{text, kind, strength, count, pages, regions, targets}] with the most common strong one first."""
    seen: dict[str, dict] = {}
    for pg in pages:
        for kind, items in (("link", pg.get("links") or []), ("button", pg.get("buttons") or [])):
            for it in items:
                label = clean_label(it.get("text", ""))
                strength = is_cta(label)
                if not strength:
                    continue
                rec = seen.setdefault(label.lower(), {"text": label, "kinds": set(), "strength": strength, "count": 0, "pages": [], "regions": set(), "targets": []})
                rec["count"] += 1
                rec["kinds"].add(kind)
                rec["regions"].add(it.get("region", "body"))
                if pg["url"] not in rec["pages"]:
                    rec["pages"].append(pg["url"])
                tgt = it.get("target") or it.get("href_abs") or ""
                if tgt and tgt not in rec["targets"] and len(rec["targets"]) < 3:
                    rec["targets"].append(tgt)
    out = []
    for r in seen.values():
        out.append({"text": r["text"], "strength": r["strength"], "kinds": sorted(r["kinds"]), "count": r["count"], "pages": r["pages"], "sources": r["pages"][:5],
                    "regions": sorted(r["regions"]), "targets": r["targets"]})
    tier = {"strong": 0, "medium": 1, "weak": 2}
    out.sort(key=lambda r: (tier[r["strength"]], -len(r["pages"]), -r["count"], r["text"].lower()))
    return out
