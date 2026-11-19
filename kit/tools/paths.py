"""One form of a site path for matching, shared by every tool and gate check.

The sitemap and the inventory keep the site's own form (/blog/post/ on a site whose addresses end in "/"), the page
tracker and the command line often drop the slash (/blog/post). Compare through key(); name per-page folders with
snapshot_slug() so page_snapshot, page_archive, the journal and the gate agree on where a page's files live.
"""


import re
import unicodedata
from urllib.parse import unquote, urlsplit


def normalize(path: str) -> str:
    """The one form of a page path: no origin, query or fragment; percent-decoded; Unicode NFC; one leading "/"; no
    repeated or trailing "/"; "/" for the home page. https://x.example/Caf%C3%A9/?a=1#b and "cafe\u0301" forms agree."""
    s = (path or "").strip()
    if "://" in s or s.startswith("//"):
        s = urlsplit(s if "://" in s else "https:" + s).path
    s = s.split("#", 1)[0].split("?", 1)[0]
    s = unicodedata.normalize("NFC", unquote(s))
    s = "/" + re.sub(r"/{2,}", "/", s.replace("\\", "/")).strip("/")
    return s


def key(path: str) -> str:
    """The matching key of a page: normalize(path) ("/blog/post", "/" for the home page). Compare pages only through this."""
    return normalize(path)


def snapshot_slug(path: str) -> str:
    """THE folder name for a page, used by every tool (page_snapshot, page_archive, the journal notes, the gate):
    "home" for "/", else the key without its leading slash, "/" written "__", lower case, and anything a file name
    should not hold (spaces, punctuation) written "-"."""
    k = key(path)
    if k == "/":
        return "home"
    return re.sub(r"[^\w.~-]+", "-", k.strip("/").replace("/", "__").lower()).strip("-") or "home"


def default_key(path: str) -> str:
    """The page key when none is given: the page's whole snapshot slug, so two different paths never share a key
    (the old "first two words" key gave /blog/pricing-guide and /blog/pricing-tips the same one)."""
    return snapshot_slug(path)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__ + "\n  growth paths <path> [...]   # each path's matching key and snapshot folder")
        sys.exit(0)
    for p in sys.argv[1:]:
        print(f"{p}\tkey {key(p)}\tsnapshot inventory/pages/{snapshot_slug(p)}/")
