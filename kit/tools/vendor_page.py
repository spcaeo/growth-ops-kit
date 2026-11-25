#!/usr/bin/env python3
"""Read a vendor's page itself, with no summarising model, and keep the vendor's own words as evidence (#43).

A fetch tool that summarises a page through a small model can report a banner ("we recommend at least 25 users") as the
plan's minimum, and can miss prices that sit in the page's embedded data. A number that would change a page is confirmed on
the page itself: the raw HTML text, or a real browser. This tool fetches the raw HTML, finds a word (a plan name) in the
visible text AND in the embedded data (JSON in script tags), prints the exact line around it with a view hint, and lists
the page's toggles (monthly/yearly, currency, cloud/self-hosted) so every view is read and recorded.

  growth vendor_page <url> --find "Basic"                      # exact quoted lines, URL, time, toggles
  growth vendor_page --file saved.html --find "Basic"          # a page saved from a real browser (rendered view)
  growth vendor_page <url> --find "Basic" --record <path> --key K --vendor Acme --fact "Basic, per user a month" \\
        --value '$12' --view Monthly                           # file it as a research fact (how_read raw)

--record refuses when the value is not inside the quoted line: the evidence must be the vendor's own words. A toggle that
changes the numbers is not in the raw HTML unless the page ships every view; the output says so, and the other view is read
in a real browser and filed with: growth research fact ... --how browser --view <the view>.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html as htmllib
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

UA = "growth-ops-kit vendor_page (read-only, raw text, no model)"
VIEW_WORDS = {"billing": r"\b(monthly|yearly|annual(?:ly)?|billed (?:monthly|annually|yearly)|per month|per year|/\s?mo|/\s?yr)\b",
              "currency": r"\b(usd|cad|eur|gbp|aud|currency|region)\b",
              "deployment": r"\b(cloud|self[- ]hosted|on[- ]prem(?:ises)?|enterprise|dedicated)\b"}


def fetch(url: str, timeout=30) -> str:
    if urllib.parse.urlparse(url).scheme not in ("http", "https"):
        raise SystemExit("only http and https addresses")
    import fetch_rule
    from config import find_project
    if find_project():                       # a vendor page is another host: only the site's own live host is refused
        fetch_rule.assert_may_fetch(url)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:   # noqa: S310  a vendor's public page, plain GET
        return r.read().decode("utf-8", "replace")


def split_page(raw: str) -> tuple[str, list[str]]:
    """(visible text, [embedded data blobs]): the text of the page, and the JSON/JS data inside script tags."""
    blobs = [htmllib.unescape(m) for m in re.findall(r"(?is)<script\b[^>]*(?:type=[\"']application/(?:ld\+)?json[\"']|id=[\"']__NEXT_DATA__[\"'])[^>]*>(.*?)</script>", raw)]
    blobs += [htmllib.unescape(m) for m in re.findall(r"(?is)<script\b[^>]*>(\s*(?:window\.[\w.]+|var \w+|const \w+)\s*=\s*[{\[].*?)</script>", raw)]
    body = re.sub(r"(?is)<(script|style|noscript|template)\b.*?</\1>|<!--.*?-->", " ", raw)
    text = htmllib.unescape(re.sub(r"(?s)<[^>]+>", " ", re.sub(r"(?i)</?(p|div|li|tr|h[1-6]|br|section|button)\b[^>]*>", "\n", body)))
    return re.sub(r"[ \t\r\f\v]+", " ", text), blobs


def contexts(text: str, term: str, width=120) -> list[str]:
    out = []
    for m in re.finditer(re.escape(term), text, re.I):
        a, b = max(0, m.start() - width), min(len(text), m.end() + width)
        out.append(re.sub(r"\s+", " ", text[a:b]).strip())
    return out


def view_hint(snippet: str) -> str:
    s = snippet.lower()
    if re.search(r"billed monthly|per month|/\s?mo\b|monthly", s) and not re.search(r"yearly|annual", s):
        return "Monthly"
    if re.search(r"yearly|annual|billed annually|/\s?yr", s) and not re.search(r"monthly|per month", s):
        return "Yearly"
    return ""


def find(raw: str, term: str, width=120) -> list[dict]:
    text, blobs = split_page(raw)
    rows = [{"from": "page text", "quote": c, "view_hint": view_hint(c)} for c in contexts(text, term, width)]
    for b in blobs:
        rows += [{"from": "embedded data", "quote": c, "view_hint": view_hint(c)} for c in contexts(b, term, width)]
    seen, out = set(), []
    for r in rows:
        if r["quote"] not in seen:
            seen.add(r["quote"])
            out.append(r)
    return out


def toggles(raw: str) -> list[dict]:
    """The page's controls that can change a number: tabs, switches, radios, selects whose words name a billing period,
    a currency or region, or a deployment."""
    found, seen = [], set()
    ctl = re.findall(r"(?is)<(button|label|option|a|li|span)\b([^>]*)>(.*?)</\1>", raw)
    for tag, attrs, inner in ctl:
        if re.search(r"(?i)<(button|label|a|option|li|select)\b", inner):
            continue                                    # a wrapper of controls: its children are read on their own
        label = re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", inner))).strip()
        if not label or len(label) > 40:
            continue
        marks = re.search(r"role=[\"'](?:tab|switch|radio)|aria-pressed|aria-selected|aria-checked|data-(?:billing|period|interval|currency|region|plan)", attrs, re.I)
        for kind, rx in VIEW_WORDS.items():
            if (marks or tag in ("button", "option", "label")) and re.search(rx, label, re.I) and (kind, label.lower()) not in seen:
                seen.add((kind, label.lower()))
                found.append({"kind": kind, "label": label})
    return found


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url", nargs="?", default="")
    ap.add_argument("--file", help="read a saved page instead (for example the rendered page saved from a real browser)")
    ap.add_argument("--find", required=True, action="append", help="a plan name or word to find (repeat for several)")
    ap.add_argument("--width", type=int, default=120)
    ap.add_argument("--record", help="the page path: file the first quote as a research fact (how_read raw)")
    ap.add_argument("--key")
    ap.add_argument("--source-url", default="", help="with --file: the address the saved page came from")
    for f in ("vendor", "fact", "value", "view"):
        ap.add_argument("--" + f, default="")
    a = ap.parse_args(argv)
    if bool(a.url) == bool(a.file):
        sys.exit("give one of: a URL, or --file")
    raw = Path(a.file).read_text(errors="replace") if a.file else fetch(a.url)
    when = dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    src = a.url or a.file
    result = {"source": src, "read_at": when, "how_read": "raw", "finds": {t: find(raw, t, a.width) for t in a.find}, "toggles": toggles(raw)}
    for t, rows in result["finds"].items():
        print(f"== {t}: {len(rows)} place(s) in {src}, read {when}, raw text, no model")
        for r in rows:
            print(f"  [{r['from']}{', view ' + r['view_hint'] if r['view_hint'] else ''}] {r['quote']}")
    if result["toggles"]:
        print("== this page has controls that can change the numbers; read EVERY view and record which one each number came from:")
        for t in result["toggles"]:
            print(f"  {t['kind']}: {t['label']}")
        print("  the raw HTML shows one view unless the page ships all of them; read the other views in a real browser "
              "(growth research fact ... --how browser --view <view>)")
    elif not any(result["finds"].values()):
        print("nothing found in the raw HTML: the page may build its prices in the browser; read it in a real browser instead")
    if a.record:
        import research
        from config import PROJECT
        rows = next((r for t in a.find for r in result["finds"][t]), None)
        if not (a.key and a.vendor and a.fact and a.value and a.view):
            sys.exit("--record needs --key --vendor --fact --value --view")
        if not rows:
            sys.exit("nothing to record: the word was not found")
        quote = next((r["quote"] for t in a.find for r in result["finds"][t] if a.value in r["quote"]), None)
        if not quote:
            sys.exit(f"the value '{a.value}' is not inside any quoted line; the evidence must be the vendor's own words")
        if not (a.url or a.source_url.startswith("http")):
            sys.exit("with --file, --source-url <the page's address> is needed so the fact names its source")
        rec = research.load(PROJECT, a.key)
        if rec is None:
            sys.exit(f"no record: growth research init {a.record} --key {a.key}")
        # the raw text is saved and hashed, so the gate can check the quote is really in it (audit H9)
        import hashlib
        import re as _re
        # one file per page read: the source address is part of the name, so a second page of the same vendor on the
        # same day never overwrites the first one's evidence (24 Nov 2026: 17 rows went stale at once)
        src = a.url or a.source_url
        tag = hashlib.sha256(src.encode()).hexdigest()[:8]
        rf = PROJECT / "research" / "raw" / f"{a.key}-{_re.sub(r'[^a-z0-9]+', '-', a.vendor.lower()).strip('-')}-{dt.date.today().isoformat()}-{tag}.txt"
        rf.parent.mkdir(parents=True, exist_ok=True)
        rf.write_text(raw)
        rec["vendor_facts"].append({"vendor": a.vendor, "fact": a.fact, "value": a.value, "shown_as": a.value, "view": a.view, "how_read": "raw",
                                    "source_url": a.url or a.source_url, "quote": quote, "read_on": dt.date.today().isoformat(),
                                    "raw_file": str(rf.relative_to(PROJECT)), "raw_sha256": hashlib.sha256(rf.read_bytes()).hexdigest()})
        research.save(PROJECT, a.key, rec)
        print(f"recorded in research/{a.key}-record.json (view {a.view}, raw)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
