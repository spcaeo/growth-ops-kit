"""Images and media (IMG)."""
from __future__ import annotations

import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

from .dom import find_all

STOCK = re.compile(r"^(img|image|dsc|screenshot|untitled|photo)[-_ ]?\d*\.", re.I)


def src_of(img):
    return img.get("src") or img.get("data-src") or ""


def real_target(src):
    """Next's optimiser URL (/_next/image?url=...) points at the real file."""
    q = urllib.parse.urlsplit(src)
    if q.path.startswith("/_next/image"):
        return urllib.parse.unquote(urllib.parse.parse_qs(q.query).get("url", [src])[0])
    return src


def num(v):
    m = re.match(r"\d+", v or "")
    return int(m.group(0)) if m else None


def run_images(p, max_images=40):
    rep = p.rep
    imgs = p.imgs()
    if not imgs:
        rep.info("IMG-01", "no <img> tags in the HTML")
        return
    no_alt = [i for i in imgs if "alt" not in i.attrs]
    empty_alt = [i for i in imgs if "alt" in i.attrs and not i.get("alt").strip()]
    rep.info("IMG-01", f"{len(imgs)} images: {len(imgs) - len(no_alt) - len(empty_alt)} with alt, {len(empty_alt)} decorative (alt=''), {len(no_alt)} with no alt attribute")
    # IMG-02 alt rules
    bad = list(no_alt)
    for i in empty_alt:
        in_link_only = i.parent is not None and i.parent.tag == "a" and not i.parent.all_text() and not i.parent.get("aria-label")
        wide = (num(i.get("width")) or 0) >= 200
        if in_link_only or wide:
            bad.append(i)
    if bad:
        rep.fail("IMG-02", f"{len(bad)} image(s) need a real alt (missing, or empty but a link's only content or 200px+ wide), first: {src_of(bad[0])[:60]}",
                 "write what the picture shows; keep alt='' only for pure decoration")
    else:
        rep.ok("IMG-02", "every image has an alt, or is marked decorative with alt=''")
    # IMG-03 alt quality
    alts = [(i, i.get("alt").strip()) for i in imgs if i.get("alt").strip()]
    q = [(i, a) for i, a in alts if len(a) > 125 or re.match(r"(?i)(image|picture|photo|graphic) of\b", a) or re.search(r"\.(png|jpe?g|webp|svg)$", a, re.I)]
    (rep.warn if q else rep.ok)("IMG-03", f"{len(q)} alt text(s) too long, 'image of...' or a file name, first: '{q[0][1][:60]}'" if q else "alt texts are short and descriptive",
                                "125 characters or fewer, no 'image of', no file names")
    # IMG-04 dimensions
    nodim = [i for i in imgs if not (i.get("width") and i.get("height")) and "aspect-ratio" not in i.get("style") and "fill" not in i.get("data-nimg")]
    (rep.warn if nodim else rep.ok)("IMG-04", f"{len(nodim)} image(s) without width and height, first: {src_of(nodim[0])[:60]}" if nodim else "every image has width and height (no layout shift from pictures)",
                                    "set width and height (or aspect-ratio) so the page does not jump")
    # IMG-05 / IMG-06 loading
    first = imgs[:2]
    lazy_top = [i for i in first if i.get("loading") == "lazy"]
    if lazy_top and lazy_top[0] is imgs[0]:
        rep.fail("IMG-05", f"the first image is lazy-loaded: {src_of(lazy_top[0])[:60]}", "remove loading=lazy from the top image; give the main picture priority")
    elif lazy_top:
        rep.warn("IMG-05", f"the second image is lazy-loaded: {src_of(lazy_top[0])[:60]}", "fine if it is below the first screen; if it is the hero picture, remove loading=lazy")
    else:
        pri = any(i.get("fetchpriority").lower() == "high" for i in imgs) or any(
            l.get("rel") == "preload" and l.get("as") == "image" and l.get("fetchpriority").lower() == "high"
            for l in find_all(p.root, "link"))
        (rep.ok if pri else rep.warn)("IMG-05", "top images are not lazy" + ("; one has fetchpriority=high" if pri else ""),
                                      "give the first-screen (LCP) picture fetchpriority='high' / priority")
    eager_late = [i for i in imgs[6:] if i.get("loading") != "lazy" and not i.get("src", "").startswith("data:")]
    (rep.warn if eager_late else rep.ok)("IMG-06", f"{len(eager_late)} image(s) after the 6th are not lazy" if eager_late else "later images are lazy-loaded",
                                         "add loading='lazy' below the first screen")
    # IMG-11 responsive
    big_nosrcset = [i for i in imgs if (num(i.get("width")) or 0) >= 600 and not i.get("srcset") and not src_of(i).endswith(".svg")]
    (rep.warn if big_nosrcset else rep.ok)("IMG-11", f"{len(big_nosrcset)} wide image(s) without srcset" if big_nosrcset else "wide images carry srcset (or are SVG)",
                                           "use the image component so phones get a smaller file")
    # IMG-12 names
    names = [i for i in imgs if STOCK.match(urllib.parse.urlsplit(real_target(src_of(i))).path.rsplit("/", 1)[-1])]
    (rep.warn if names else rep.ok)("IMG-12", f"{len(names)} image file name(s) like IMG_1234" if names else "image file names are descriptive", "name files for what they show")
    # IMG-14 main picture
    mainpic = [i for i in imgs if (num(i.get("width")) or 0) >= 480]
    (rep.ok if mainpic else rep.info)("IMG-14", f"main picture {num(mainpic[0].get('width'))}px wide: {src_of(mainpic[0])[:60]}" if mainpic else
                                      "no <img> 480px wide or more in the HTML (the page may draw its main picture with CSS or SVG)")
    # IMG-07..10 file checks via HEAD
    targets = []
    for i in imgs:
        s = real_target(src_of(i))
        if s and not s.startswith("data:") and s not in targets:
            targets.append(s)
    targets = targets[:max_images]
    if p.f.allow_live:
        rep.skip("IMG-08", "live site: image files are not fetched")
        return
    def probe(s):
        u = p.abs(s)
        return s, p.f.settle(u, p.f.head_or_get(u))
    with ThreadPoolExecutor(max_workers=3) as ex:
        res = list(ex.map(probe, targets))
    broken = [(s, r) for s, r in res if r.status != 200]
    (rep.fail if broken else rep.ok)("IMG-10", f"{len(broken)} image file(s) not found: {broken[0][0]} -> {broken[0][1].status}" if broken else f"all {len(res)} image files answer 200",
                                     "fix the path or add the file")
    nontype = [(s, r) for s, r in res if r.status == 200 and not r.h("content-type").startswith("image/")]
    noext = [(s, r) for s, r in res if r.status == 200 and not re.search(r"\.(avif|webp|png|jpe?g|svg|gif|ico)$", urllib.parse.urlsplit(s).path, re.I)]
    (rep.fail if nontype else rep.ok)("IMG-09", f"image URL served with a non-image type: {nontype[0][0]}" if nontype else "image files are served with an image content-type",
                                      "serve a proper image/* type and keep the extension in the file name")
    if noext:
        rep.warn("IMG-09", f"{len(noext)} image URL(s) with no file extension, first: {noext[0][0]}", "keep the extension in the name")
    heavy, fmt = [], []
    for s, r in res:
        size = int(r.h("content-length") or 0) or len(r.body)
        if size > 200 * 1024:
            heavy.append((s, size))
        ct = r.h("content-type")
        if ct in ("image/png", "image/jpeg") and size > 150 * 1024:
            fmt.append((s, ct, size))
    if heavy:
        lvl = rep.fail if any(sz > 300 * 1024 for _, sz in heavy) else rep.warn
        lvl("IMG-08", f"{len(heavy)} image(s) over 200 KiB: " + "; ".join(f"{s.rsplit('/', 1)[-1]} {sz // 1024} KiB" for s, sz in heavy[:4]),
            "compress, resize, or use WebP/AVIF; no picture above about 200 KiB")
    else:
        rep.ok("IMG-08", f"no image over 200 KiB (of {len(res)} checked)")
    if fmt:
        rep.warn("IMG-07", f"{len(fmt)} large PNG/JPEG file(s): " + "; ".join(f"{s.rsplit('/', 1)[-1]} {sz // 1024} KiB" for s, _, sz in fmt[:3]), "serve WebP or AVIF")
    else:
        rep.ok("IMG-07", "no large PNG/JPEG left in an old format")
    # IMG-15 video
    for v in find_all(p.root, "video"):
        problems = []
        if "autoplay" in v.attrs and not ("muted" in v.attrs and "playsinline" in v.attrs):
            problems.append("autoplay without muted + playsinline")
        if not v.get("poster"):
            problems.append("no poster")
        (rep.warn if problems else rep.ok)("IMG-15", f"video: {', '.join(problems) or 'poster and autoplay rules ok'}", "add poster; autoplay only muted and playsinline")
