"""One form of a site path for matching, shared by every tool and gate check.

The sitemap and the inventory keep the site's own form (/blog/post/ on a site whose addresses end in "/"), the page
tracker and the command line often drop the slash (/blog/post). Compare through key(); name per-page folders with
snapshot_slug() so page_snapshot and the gate agree on where a snapshot lives.
"""


def key(path: str) -> str:
    """The path without a trailing slash, "/" for the home page."""
    return (path or "").rstrip("/") or "/"


def snapshot_slug(path: str) -> str:
    """The folder name under inventory/pages/ for a page's snapshots (page_snapshot writes it, ev.snapshot reads it)."""
    k = key(path)
    return "home" if k == "/" else k.strip("/").replace("/", "__")


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
