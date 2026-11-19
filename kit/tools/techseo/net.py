"""Plain HTTP fetching (no browser). Never follows redirects on its own.

Live-site guard: the real site (the host of site_origin) is fetched ONLY when --allow-live is given,
and then only robots.txt, sitemap.xml and the one page's HTML. Everything else about
the real host is mapped onto the local server instead.
"""
from __future__ import annotations

import gzip
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from dataclasses import dataclass, field

UA = "TechSEO/1.0 (read-only checker)"
GOOGLEBOT = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


_opener = urllib.request.build_opener(_NoRedirect)


@dataclass
class Resp:
    url: str
    status: int = 0
    headers: dict = field(default_factory=dict)   # lower-case keys
    body: bytes = b""
    seconds: float = 0.0
    error: str = ""
    wire_len: int = 0                              # bytes on the wire (compressed size)

    def h(self, k, d=""):
        return self.headers.get(k.lower(), d)

    def text(self):
        ct = self.h("content-type")
        enc = "utf-8"
        if "charset=" in ct:
            enc = ct.split("charset=")[-1].split(";")[0].strip() or "utf-8"
        try:
            return self.body.decode(enc, errors="replace")
        except LookupError:
            return self.body.decode("utf-8", errors="replace")


class Fetcher:
    def __init__(self, local_origin, site_origin="https://example.com", allow_live=False,
                 ua=UA, timeout=20):
        self.local = local_origin.rstrip("/")
        self.site = site_origin.rstrip("/")
        host = urllib.parse.urlsplit(self.site).netloc.lower().removeprefix("www.")
        self.live_hosts = {host, "www." + host}          # the real site: never fetched without allow_live
        self.allow_live = allow_live
        self.ua = ua
        self.timeout = timeout
        self.cache: dict = {}
        self.log: list = []            # every request made, for the report footer

    def local_url(self, url):
        """Map a production-host URL onto the local server (or keep a local URL)."""
        p = urllib.parse.urlsplit(url)
        if p.netloc.lower() in self.live_hosts or url.startswith(self.site):
            return self.local + (p.path or "/") + (("?" + p.query) if p.query else "")
        return url

    def is_live_url(self, url):
        return urllib.parse.urlsplit(url).netloc.lower() in self.live_hosts

    def get(self, url, method="GET", headers=None, ua=None, max_bytes=6_000_000, fresh=False):
        url = self.local_url(url) if not self.allow_live else url
        if self.is_live_url(url) and not self.allow_live:
            return Resp(url, error="live site not fetched (no --allow-live)")
        key = (method, url, ua or self.ua, tuple(sorted((headers or {}).items())))
        if key in self.cache and not fresh:
            return self.cache[key]
        req = urllib.request.Request(url, method=method, headers={
            "User-Agent": ua or self.ua, "Accept-Encoding": "gzip", "Accept": "*/*", **(headers or {})})
        t0 = time.time()
        r = Resp(url)
        try:
            resp = _opener.open(req, timeout=self.timeout)
            r.status, raw = resp.status, resp.read(max_bytes) if method != "HEAD" else b""
            r.headers = {k.lower(): v for k, v in resp.getheaders()}
        except urllib.error.HTTPError as e:
            r.status = e.code
            r.headers = {k.lower(): v for k, v in e.headers.items()}
            raw = e.read(max_bytes) if method != "HEAD" else b""
        except Exception as e:  # network error, timeout, refused
            r.error = f"{type(e).__name__}: {e}"
            raw = b""
        r.seconds = time.time() - t0
        r.wire_len = len(raw)
        enc = r.headers.get("content-encoding", "")
        try:
            if enc == "gzip":
                raw = gzip.decompress(raw)
            elif enc == "deflate":
                raw = zlib.decompress(raw)
        except Exception:
            pass
        r.body = raw
        self.log.append(f"{method} {url} -> {r.status or r.error}")
        self.cache[key] = r
        return r

    def head_or_get(self, url, **kw):
        r = self.get(url, "HEAD", **kw)
        if r.status in (0, 405, 501) or r.error:
            r = self.get(url, "GET", **kw)
        return r

    def settle(self, url, r):
        """A dev server can answer 404 or 500 while it compiles a page or hot-reloads. Ask again once, after a pause."""
        if r.status in (0, 404) or r.status >= 500:
            time.sleep(1.5)
            return self.get(url, "GET", fresh=True)
        return r
