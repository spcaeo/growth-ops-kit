"""Calls to action: one booking path, one label with a reason, one colour, sticky bar, exit offer, hints,
call dialog, events, dialog backdrop, footer call row (rules 32, 32a, 32b, 35, 35b, 36a, 132-134, 140)."""
from __future__ import annotations

import re

from techseo.dom import find_all

from . import domx
from .core import Skip, check, short  # noqa: F401  (the Next.js adapter star-imports this module)

RAW_BOOKING = r"calendly\.com|zoom\.us/|cal\.com/|hubspot\.com/meetings|neetocal\.com"   # well-known booking hosts; growth.json booking_hosts adds more
BARE_LABELS = r"(book (an? )?(intro |free |discovery )?(call|demo)|book now|book a time|get started|schedule (a )?(call|demo))"
# What a reason line beside a booking button talks about (growth.json cta.reason_words replaces it).
REASON_WORDS = r"(?i)\b(call|minutes?|zoom|pric\w*|cost\w*|quotes?|visit|estimate|appointment)\b"
EVENTS = []                                          # growth.json cta.events: the dataLayer events the CTA components push


def cta(ctx):
    """growth.json "cta": label, path, reason_words, events, color ... (all optional)."""
    return ctx.cfg.get("cta") or {}


def reason_words(ctx):
    return r"(?i)\b(" + cta(ctx)["reason_words"] + r")\b" if cta(ctx).get("reason_words") else REASON_WORDS


def primaries(ctx, root, include_header=True):
    out = []
    for a in domx.booking_links(ctx, root):
        if not domx.is_primary(a) or domx.in_call_dialog(a):
            continue
        if not include_header and any(x.tag in ("header", "nav") or domx.has_cls(x, r"site-header") for x in a.ancestors()):
            continue
        out.append(a)
    return out


def reason_for(a, words=REASON_WORDS):
    """The reason line beside a booking button: text in its block (3 levels up) that is not a link or a button."""
    cur = a
    for _ in range(3):
        cur = cur.parent
        if cur is None:
            break
        parts = []
        for n in cur.iter():
            if n.tag in ("p", "span", "li", "small", "div") and not any(x.tag in ("a", "button") for x in [n, *n.ancestors()]):
                own = " ".join(c for c in n.children if isinstance(c, str)).strip()
                if own:
                    parts.append(own)
        txt = " ".join(parts)
        if len(txt.split()) >= 8 and re.search(words, txt):
            return txt
    return ""


def raw_booking(ctx):
    """The well-known booking hosts plus the project's own (growth.json booking_hosts)."""
    extra = [re.escape(h) for h in ctx.cfg.get("booking_hosts") or []]
    return "|".join([RAW_BOOKING] + extra)


@check("cta.one-path", "32", what="every call to action goes to the one booking path; no raw booking link", needs="live")
def one_path(ctx):
    root = ctx.root()
    probs = [f"raw booking link {a.get('href')[:60]}" for a in find_all(root, "a") if re.search(raw_booking(ctx), a.get("href"))]
    if not domx.booking_links(ctx, root):
        probs.append("no link to the booking path at all")
    ctx.verdict(probs, f"{len(domx.booking_links(ctx, root))} booking links, all through {sorted(ctx.booking_paths())}",
                f"link to {ctx.cfg.get('conversion_path', 'the booking path')} through the site's shared booking button, never a pasted booking URL (rule 32)")


@check("cta.label-same", "32a", types=("money", "hub", "core"), what="every primary booking button has the same label (growth.json cta.label when set)", needs="live")
def label_same(ctx):
    root = ctx.root()
    labels = {}
    for a in primaries(ctx, root):
        labels.setdefault(domx.label(a), []).append(a.get("href").split("cta=")[-1][:40])
    want = cta(ctx).get("label")
    if not labels:
        ctx.fail("no primary booking button found", "add the page's booking button (the shared button component) (rules 32, 32a)")
    elif len(labels) > 1:
        ctx.fail("primary buttons use " + str(len(labels)) + " labels: " + "; ".join(f"'{k}' ({', '.join(v)})" for k, v in labels.items()),
                 "use one benefit-led label on every primary booking button" + (f": '{want}'" if want else "") + " (rule 32a)")
    elif want and next(iter(labels)).strip().rstrip("→↗ ").strip().lower() != want.strip().lower():
        ctx.fail(f"the primary buttons say '{next(iter(labels))}', not the site's one label '{want}'",
                 f"use '{want}' (growth.json cta.label) on every primary booking button (rule 32a)")
    else:
        ctx.ok(f"one label on {sum(len(v) for v in labels.values())} primary buttons: '{next(iter(labels))}'")


@check("cta.reason-line", "32a", types=("money", "hub", "core"), what="every primary booking button has a reason line in its block", needs="live")
def reason_line(ctx):
    root = ctx.root()
    btns = primaries(ctx, root, include_header=False)
    if not btns:
        ctx.fail("no primary booking button in the page body", "add the page's booking button with its reason line (rule 32a)")
        return
    probs = [f"'{domx.label(a)}' ({a.get('href').split('cta=')[-1][:40]})" for a in btns if not reason_for(a, reason_words(ctx))]
    ctx.verdict(probs, f"all {len(btns)} body booking buttons have a reason line beside them",
                "add one line beside the button from what the visit or call offers: what the reader gets, how long it takes, what it costs (rule 32a)")


@check("cta.no-bare-book", "32a", what="no booking link says only 'Book a call', 'Book now' or 'Get started'", needs="live")
def no_bare(ctx):
    root = ctx.root()
    probs = []
    for a in domx.booking_links(ctx, root):
        lab = domx.label(a).strip().rstrip("→↗ ").strip()
        if re.fullmatch(r"(?i)" + BARE_LABELS + r"[.!]?", lab):
            where = "footer" if any(domx.has_cls(x, r"site-footer") or x.tag == "footer" for x in a.ancestors()) else "page"
            probs.append(f"'{lab}' in the {where}")
    ctx.verdict(probs, "no bare booking label", f"say what the reader gets, e.g. '{cta(ctx).get('label') or 'Get my quote'}' (rule 32a)")


CONTROL_EXCLUDE = r"(nav-|faq|sticky|exit-offer|call-dialog|site-)"


def controls(root):
    m = domx.main(root)
    out = []
    for n in m.iter():
        if domx.in_chrome(n) or any(x.tag == "details" for x in n.ancestors()):
            continue
        is_ctl = (n.tag == "input" and n.get("type") not in ("hidden", "submit")) or n.tag in ("select", "textarea") \
            or n.get("role") in ("slider", "switch", "tab", "radio") \
            or (n.tag == "button" and (n.get("aria-pressed") or re.search(r"(?i)copy|approve", n.get("class") + " " + n.get("aria-label") + " " + domx.text(n))))
        if is_ctl and not domx.has_cls(n, CONTROL_EXCLUDE + r".*"):
            out.append(n)
    return out


@check("hints.present", "36a", types=("money", "hub"), what="every block of interactive controls has a hint marker (aria-hidden)", needs="live")
def hints(ctx):
    ctx.feature("hints")
    root = ctx.root()
    ctls = controls(root)
    if not ctls:
        ctx.fail("no interactive control found on the page", "a money page has its own interactive element (book/02-owner-rules.md 'Money pages are unique')")
        return
    groups = {}
    for c in ctls:
        sec = domx.up(c, lambda x: x.tag == "section") or domx.main(root)
        groups.setdefault(id(sec), (sec, []))[1].append(c)
    probs = []
    for sec, cs in groups.values():
        marks = [n for n in sec.iter() if domx.has_cls(n, r"(.*-)?hint") or n.get("data-hint")]
        if not marks:
            name = sec.get("aria-labelledby") or sec.get("id") or sec.get("data-fold") or " ".join(domx.classes(sec)[:2])
            probs.append(f"{len(cs)} control(s) in '{name}' without a hint")
        elif not all(m.get("aria-hidden") == "true" for m in marks if domx.has_cls(m, r"(.*-)?hint")):
            probs.append(f"a hint in '{sec.get('id') or domx.classes(sec)[:1]}' is not aria-hidden")
    ctx.verdict(probs, f"{len(groups)} control block(s), each with an aria-hidden hint",
                "add the shared <Hint> (2-4 words, CTA colour, aria-hidden) beside each control block (rule 36a)")


@check("dialog.call", "132", types=("money", "hub", "core"), what="the shared call dialog: its links, its points, its length line, its named host (growth.json features.call_dialog)", needs="live")
def call_dialog(ctx):
    f = ctx.feature("call_dialog")
    root = ctx.root()
    cls = f.get("class", "call-dialog")
    d = [x for x in find_all(root, "dialog") if domx.has_cls(x, cls)]
    off = f.get("not_on", [ctx.cfg.get("conversion_path", ""), (ctx.cfg.get("cta") or {}).get("contact_path", "")])
    if ctx.need_path() in off:
        ctx.verdict(["call dialog present"] if d else [], "no call dialog on this page (correct)", "remove it here (rule 132)")
        return
    if not d:
        ctx.fail(f"no shared call dialog (dialog.{cls})", "render the call dialog with the page's reason line (rule 132)")
        return
    d, probs = d[0], []
    t = domx.text(d)
    links = {domx.label(a): ctx.internal_path(a.get("href")) for a in find_all(d, "a")}
    pick, msg = f.get("pick_label"), f.get("message_label")
    if pick and (links.get(pick) or "").rstrip("/") != ctx.cfg.get("conversion_path", ""):
        probs.append(f"no '{pick}' link to {ctx.cfg.get('conversion_path')}")
    if msg and (links.get(msg) or "").rstrip("/") != (ctx.cfg.get("cta") or {}).get("contact_path", ""):
        probs.append(f"no '{msg}' link to {(ctx.cfg.get('cta') or {}).get('contact_path')}")
    if f.get("points") and len([li for li in find_all(d, "li")]) != int(f["points"]):
        probs.append(f"{len(find_all(d, 'li'))} points ({f['points']} required)")
    for rx in f.get("must_say", []):
        if not re.search(rx, t, re.I):
            probs.append(f"missing text matching '{rx}'")
    # only the dialog's own pictures count (a staff photo elsewhere on the page is not the dialog's host)
    host = ctx.cfg.get("call_host", "")
    if f.get("host_check"):
        for img in find_all(d, "img"):
            alt = img.get("alt") or ""
            if re.search(f["host_check"], alt + (img.get("src") or ""), re.I) and (not host or host.lower() not in alt.lower()):
                probs.append(f"shows a person who is not the named host ({alt or img.get('src')}); host: {host or 'not named'}")
    ctx.verdict(probs, "call dialog complete", "fix the call dialog as listed (rule 132)")


@check("footer.call-row", "140", what="the footer has a call row (button + reason line), the topic links and Back to top (growth.json features.footer_call_row)", needs="live")
def footer(ctx):
    ctx.feature("footer_call_row")
    root = ctx.root()
    f = next((n for n in root.iter() if n.tag == "footer" or domx.has_cls(n, r"site-footer")), None)
    if f is None:
        ctx.fail("no footer", "render the shared footer (rule 51)")
        return
    probs = []
    bk = domx.booking_links(ctx, f)
    if not any(domx.is_primary(a) for a in bk):
        probs.append(f"no booking button in the footer (only {len(bk)} text link(s))")
    elif not any(reason_for(a, reason_words(ctx)) for a in bk if domx.is_primary(a)):
        probs.append("the footer booking button has no reason line")
    if not any(re.search(r"(?i)back to top", domx.text(a)) for a in find_all(f, "a")):
        probs.append("no 'Back to top' link")
    hrefs = {ctx.internal_path(a.get("href")) for a in find_all(f, "a")}
    miss = [s for s in ctx.cfg.get("silos", {}) if "/" + s not in hrefs]
    if miss:
        probs.append(f"topic links missing: {', '.join(miss)}")
    ctx.verdict(probs, "footer call row, topic links and Back to top present", "fix the shared footer as listed (rule 140)")
