"""Social cards (SOC): Open Graph and X (Twitter) tags, and the share image file."""
from __future__ import annotations

import urllib.parse

from .image_size import image_size


def run_social(p):
    rep = p.rep
    og = {k: p.meta_content(prop="og:" + k) for k in ("title", "description", "url", "type", "site_name", "image", "image:width", "image:height", "image:alt", "locale")}
    tw = {k: p.meta_content(name="twitter:" + k) for k in ("card", "title", "description", "image")}
    need = ["title", "description", "url", "type", "site_name", "image"]
    miss = [k for k in need if not og[k]]
    (rep.fail if miss else rep.ok)("SOC-01", f"missing Open Graph tag(s): og:{', og:'.join(miss)}" if miss else "og:title, description, url, type, site_name and image are all present",
                                   "set the Open Graph tags (title, description, url, type, site_name, image) in the page <head>")
    t, d = p.title(), p.meta_content(name="description")
    if og["title"] and og["description"]:
        if (t and og["title"].lower() != t.lower()) or (d and og["description"].lower() != d.lower()):
            rep.info("SOC-05", "og title/description differ from the meta text (allowed if on purpose: a separate social line)")
        else:
            rep.ok("SOC-05", "og title/description follow the meta text")
    for k, mx in (("title", 70), ("description", 200)):
        v = og[k] or ""
        if len(v) > mx:
            rep.warn("SOC-08", f"og:{k} is {len(v)} characters", f"keep og:{k} under {mx}")
    c = (p.canonicals() or [None])[0]
    if og["url"] and c:
        (rep.ok if og["url"].rstrip("/") == c.get("href").rstrip("/") else rep.fail)("SOC-04", "og:url equals the canonical" if og["url"].rstrip("/") == c.get("href").rstrip("/") else
                                                                                   f"og:url {og['url']} differs from canonical {c.get('href')}", "make them identical")
    # X card
    probs = []
    if tw["card"] != "summary_large_image":
        probs.append(f"twitter:card is '{tw['card']}' (want summary_large_image)")
    if not tw["image"]:
        probs.append("no twitter:image")
    elif og["image"] and tw["image"] != og["image"]:
        probs.append("twitter:image differs from og:image")
    if not tw["title"] and not og["title"]:
        probs.append("no twitter:title or og:title")
    # A card's words must match on every network: X falls back to og when twitter:* is absent, so a set twitter
    # line that differs from og means the same share reads two ways.
    diff = [k for k in ("title", "description") if tw[k] and og[k] and tw[k].strip() != og[k].strip()]
    (rep.fail if diff else rep.ok)("SOC-09", "; ".join(f"twitter:{k} differs from og:{k}" for k in diff) if diff else
                                   "twitter title and description match og (or fall back to it)",
                                   "drop the twitter text or set it to the og text (rule 65)")
    (rep.warn if probs else rep.ok)("SOC-06", "; ".join(probs) if probs else "twitter card is summary_large_image, image equals og:image",
                                    "set the twitter: tags (card, title, description, image) in the page <head>")
    # share image file
    img = og["image"]
    if not img:
        return
    iu = urllib.parse.urlsplit(img)
    if iu.scheme != "https" or iu.netloc.lower() != p.site_host:
        (rep.fail if p.live else rep.warn)("SOC-02", f"og:image is not an absolute https URL on {p.site_host}: {img}", "use the full https address")
    if p.f.allow_live:
        rep.skip("SOC-02", "live site: share image not fetched")
        return
    r = p.f.get(img)
    if r.status != 200 or not r.h("content-type").startswith("image/"):
        rep.fail("SOC-02", f"share image {img} answers {r.status} {r.h('content-type')}", "the file must exist in the build and be served as an image")
        return
    ct = r.h("content-type")
    size = int(r.h("content-length") or 0) or len(r.body)
    dims = image_size(r.body if r.body else p.f.get(img, "GET").body)
    issues = []
    if ct in ("image/gif", "image/svg+xml"):
        issues.append(f"type {ct} is not accepted by most cards")
    if size > 5 * 1024 * 1024:
        issues.append(f"{size // 1024} KiB is over 5 MB")
    if dims:
        w, h = dims
        if w < 1200 or h < 600:
            issues.append(f"{w}x{h} is under 1200x630")
        elif abs(w / h - 1.91) > 0.15:
            issues.append(f"{w}x{h} is not close to 1.91:1")
        if og["image:width"] and og["image:height"] and (str(w), str(h)) != (og["image:width"], og["image:height"]):
            issues.append(f"og:image:width/height say {og['image:width']}x{og['image:height']} but the file is {w}x{h}")
    else:
        issues.append("could not read the image size")
    (rep.fail if issues else rep.ok)("SOC-02", f"share image {dims[0] if dims else '?'}x{dims[1] if dims else '?'} {ct}, {size // 1024} KiB" if not issues else "share image problems: " + "; ".join(issues),
                                     "1200x630 JPEG/PNG/WebP under 5 MB, tags equal to the file's real size")
    (rep.ok if og["image:alt"] else rep.warn)("SOC-03", "og:image:alt present" if og["image:alt"] else "no og:image:alt", "describe the share image")
    if tw["image"] and tw["image"] != img:
        pass
    loc = og["locale"]
    rep.info("SOC-07", f"og:locale is {loc or 'not set'} (optional on a one-language site)")
