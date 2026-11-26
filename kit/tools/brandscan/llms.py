"""llms.txt and llms-full.txt: what the site tells AI tools about itself, and the JSON-LD organisation data."""
from __future__ import annotations

import json
import re

LINK = re.compile(r"^\s*[-*+]\s*\[([^\]]+)\]\(([^)\s]+)\)\s*(?:[:\-–—]\s*(.*))?$")


def looks_like_text(body: str) -> bool:
    """False for an HTML page served where a text file should be (a site that answers every address with its home page)."""
    head = (body or "").lstrip()[:200].lower()
    return bool(head) and not head.startswith(("<!doctype", "<html", "<head", "<?xml", "<body"))


def parse_llms(body: str) -> dict:
    """{title, summary, intro, sections: [{heading, links: [{text, url, note}]}], headings} from an llms.txt (the llmstxt.org shape:
    a # title, a > summary, notes, then ## sections of - [name](url): note lines)."""
    title, summary, intro, sections, cur = "", [], [], [], None
    for raw in (body or "").splitlines():
        line = raw.rstrip()
        if line.startswith("# ") and not title:
            title = line[2:].strip()
        elif line.startswith("## "):
            cur = {"heading": line[3:].strip(), "links": []}
            sections.append(cur)
        elif line.lstrip().startswith(">") and cur is None:
            summary.append(line.lstrip()[1:].strip())
        elif cur is None and line.strip() and not line.startswith("#"):
            intro.append(line.strip())
        elif cur is not None:
            m = LINK.match(line)
            if m:
                cur["links"].append({"text": m.group(1).strip(), "url": m.group(2).strip(), "note": (m.group(3) or "").strip()})
    return {"title": title, "summary": " ".join(summary).strip(), "intro": " ".join(intro)[:600], "sections": sections,
            "links": sum(len(s["links"]) for s in sections)}


def parse_llms_full(body: str) -> dict:
    """llms-full.txt is the site's text in one file: its title, size and top headings (the text itself stays on the site)."""
    heads = [m.group(2).strip() for m in re.finditer(r"^(#{1,2})\s+(.+)$", body or "", re.M)]
    first = next((m.group(1).strip() for m in re.finditer(r"^#\s+(.+)$", body or "", re.M)), "")
    return {"title": first, "chars": len(body or ""), "headings": heads[:40], "heading_count": len(heads)}


ORG_TYPES = re.compile(r"(?i)(?:organi[sz]ation|business|corporation|company|agency|store|service|firm|studio|institution)$|^(?:NGO|Brand|LocalBusiness)$")


def _walk(node):
    if isinstance(node, list):
        for x in node:
            yield from _walk(x)
    elif isinstance(node, dict):
        yield node
        for k, v in node.items():
            if k in ("@graph", "mainEntity", "publisher", "provider", "parentOrganization", "author", "brand", "about") or isinstance(v, (list, dict)):
                yield from _walk(v)


def _as_list(v):
    return v if isinstance(v, list) else [v] if v not in (None, "") else []


def _address(a) -> str:
    if isinstance(a, str):
        return a.strip()
    if isinstance(a, dict):
        parts = [a.get(k) for k in ("streetAddress", "addressLocality", "addressRegion", "postalCode", "addressCountry")]
        return ", ".join(str(p.get("name") if isinstance(p, dict) else p) for p in parts if p)
    return ""


def organizations(jsonld_blocks: list[str]) -> list[dict]:
    """Organisation and LocalBusiness data from JSON-LD blocks: name, legalName, url, email, telephone, address, sameAs, contact points ..."""
    found: dict[str, dict] = {}
    for raw in jsonld_blocks:
        try:
            data = json.loads(raw.strip())
        except ValueError:
            try:
                data = json.loads(re.sub(r",\s*([}\]])", r"\1", raw.strip()))       # a trailing comma is a common slip
            except ValueError:
                continue
        for node in _walk(data):
            types = [str(t) for t in _as_list(node.get("@type"))]
            if not any(ORG_TYPES.search(t) for t in types) or not (node.get("name") or node.get("legalName")):
                continue
            addr = _address(node.get("address")) or "; ".join(a for a in (_address(x) for x in _as_list(node.get("location"))) if a)
            cps = []
            for cp in _as_list(node.get("contactPoint")):
                if isinstance(cp, dict):
                    cps.append({k: cp.get(k) for k in ("contactType", "email", "telephone", "areaServed") if cp.get(k)})
            rec = {"types": types, "name": str(node.get("name") or ""), "legalName": str(node.get("legalName") or ""), "url": str(node.get("url") or ""),
                   "email": str(node.get("email") or "").replace("mailto:", ""), "telephone": str(node.get("telephone") or ""), "address": addr,
                   "sameAs": [str(s) for s in _as_list(node.get("sameAs")) if isinstance(s, str)], "contactPoints": cps,
                   "description": str(node.get("description") or "")[:400], "slogan": str(node.get("slogan") or ""),
                   "foundingDate": str(node.get("foundingDate") or ""), "vatID": str(node.get("vatID") or ""), "taxID": str(node.get("taxID") or "")}
            key = (rec["legalName"] or rec["name"]).lower()
            old = found.get(key)
            if old is None or sum(bool(v) for v in rec.values()) > sum(bool(v) for v in old.values()):
                found[key] = rec
    return list(found.values())
