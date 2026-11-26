"""One page of HTML read into the parts the brand scan needs: links, buttons, visible text, JSON-LD blocks, address tags."""
from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

BLOCK = {"p", "div", "li", "ul", "ol", "br", "tr", "td", "th", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article",
         "header", "footer", "nav", "main", "address", "table", "form", "dd", "dt", "blockquote", "hr"}
SKIP = {"script", "style", "noscript", "template", "svg"}
REGIONS = {"header", "footer", "nav", "main", "aside"}
VOID = {"br", "img", "input", "meta", "link", "hr", "area", "base", "col", "embed", "source", "track", "wbr"}


class Page(HTMLParser):
    """Read once with Page(html_text, url). Fields: links [{href, text, region}], buttons [{text, region, href}],
    text (visible text, one line per block), jsonld [raw strings], addresses [text of <address> tags], meta {name: content},
    title, h1, raw (the HTML as served)."""

    def __init__(self, doc: str, url: str = ""):
        super().__init__(convert_charrefs=True)
        self.url, self.raw = url, doc or ""
        self.links, self.buttons, self.jsonld, self.addresses, self.meta = [], [], [], [], {}
        self.title = self.h1 = ""
        self._lines, self._cur = [], []
        self._stack, self._skip = [], 0
        self._link = None            # {"href", "text", "region"} while inside an <a>
        self._btn = None
        self._in_title = self._in_h1 = False
        self._ld = None
        self._addr = None
        try:
            self.feed(self.raw)
            self.close()
        except Exception:  # noqa: BLE001  (broken HTML must never stop a scan)
            pass
        self._flush()
        self.text = "\n".join(self._lines)

    # -- helpers
    def region(self) -> str:
        for tag in reversed(self._stack):
            if tag in REGIONS:
                return tag
        return "body"

    def _flush(self):
        line = re.sub(r"\s+", " ", "".join(self._cur)).strip()
        if line:
            self._lines.append(line)
        self._cur = []

    # -- parser events
    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag == "meta":
            key = (a.get("name") or a.get("property") or a.get("itemprop") or "").lower()
            if key and "content" in a:
                self.meta.setdefault(key, a["content"].strip())
        if tag in BLOCK:
            self._flush()
        if tag == "script" and "ld+json" in a.get("type", "").lower():
            self._ld = []
        if tag in SKIP:
            self._skip += 1
        if tag not in VOID:
            self._stack.append(tag)
        if tag == "title":
            self._in_title = True
        elif tag == "h1" and not self.h1:
            self._in_h1 = True
        elif tag == "a" and a.get("href") and self._link is None:
            self._link = {"href": a["href"].strip(), "text": "", "region": self.region(), "aria": a.get("aria-label", "")}
        elif tag == "button" and self._btn is None:
            self._btn = {"text": "", "region": self.region(), "href": a.get("data-href") or a.get("data-url") or "", "aria": a.get("aria-label", "")}
        elif tag == "input" and a.get("type", "").lower() in ("submit", "button") and a.get("value"):
            self.buttons.append({"text": a["value"].strip(), "region": self.region(), "href": ""})
        elif tag == "address":
            self._addr = []

    def handle_endtag(self, tag):
        if tag in SKIP and self._skip:
            self._skip -= 1
        if tag == "script" and self._ld is not None:
            self.jsonld.append("".join(self._ld))
            self._ld = None
        if tag in self._stack:                      # close back to the matching open tag
            while self._stack and self._stack.pop() != tag:
                pass
        if tag in BLOCK:
            self._flush()
        if tag == "title":
            self._in_title = False
        elif tag == "h1":
            self._in_h1 = False
        elif tag == "a" and self._link is not None:
            self._link["text"] = re.sub(r"\s+", " ", self._link["text"]).strip() or self._link.pop("aria", "").strip()
            self.links.append(self._link)
            self._link = None
        elif tag == "button" and self._btn is not None:
            self._btn["text"] = re.sub(r"\s+", " ", self._btn["text"]).strip() or self._btn.get("aria", "").strip()
            self.buttons.append(self._btn)
            self._btn = None
        elif tag == "address" and self._addr is not None:
            t = re.sub(r"\s+", " ", " ".join(self._addr)).strip()
            if t:
                self.addresses.append(t)
            self._addr = None

    def handle_data(self, data):
        if self._ld is not None:
            self._ld.append(data)
            return
        if self._skip:
            return
        if self._in_title:
            self.title += data
        if self._in_h1:
            self.h1 += data
        if self._link is not None:
            self._link["text"] += data
        if self._btn is not None:
            self._btn["text"] += data
        if self._addr is not None:
            self._addr.append(data)
        self._cur.append(data)


def absolute(href: str, base: str) -> str:
    """The full address of a link, or "" for mailto:, tel:, javascript: and plain anchors."""
    href = html.unescape((href or "").strip())
    if not href or href.startswith(("#", "javascript:", "mailto:", "tel:", "data:", "sms:")):
        return ""
    try:
        full = urljoin(base, href)
    except ValueError:
        return ""
    return full.split("#", 1)[0] if urlsplit(full).scheme in ("http", "https") else ""


def host_of(url: str) -> str:
    return (urlsplit(url or "").hostname or "").lower().removeprefix("www.")


def clean_url(url: str) -> str:
    """An address without its query and fragment (tracking codes never belong in a finding)."""
    u = urlsplit(url)
    return f"{u.scheme}://{u.netloc}{u.path}".rstrip("/") if u.scheme else url
