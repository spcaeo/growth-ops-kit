"""Rule 156: a page keeps every house feature of its type. Each feature is a check of its own; this one
reads their results (it runs last) and fails when any feature of the page's type is missing."""
from __future__ import annotations

import re

from .core import check

EVERY = ["layout.shared-frame", "crumbs.visible", "links.cards", "copy.shared", "schema.org-id", "cta.events", "seo.all", "footer.call-row"]
HOUSE = {
    "money": EVERY + ["geo.answer-passage", "hero.split", "state.url", "hints.present", "cta.reason-line", "cta.label-same",
                      "cta.one-color", "dialog.call", "sticky.present", "exit.present", "geo.liftable", "faq.box", "faq.schema-equal",
                      "faq.ask-card", "motion.reveal", "hero.unique", "geo.updated", "schema.house-types"],
    "hub": EVERY + ["hub.map", "state.url", "hub.cards", "post.logos", "dialog.call", "motion.reveal", "faq.box", "faq.ask-card"],
    "post": EVERY + ["post.cover", "post.takeaways", "post.reading-aids", "post.toc-h2", "post.shapes", "post.ask-card",
                     "faq.box", "faq.ask-card", "post.logos", "post.read-next"],
    "core": EVERY + ["core.contact-form-first", "core.service-links", "copy.shared", "dialog.call", "motion.reveal"],
}

# Features the rulebook asks for only where their content exists ("where the Markdown has them", "if it has a FAQ",
# "Contact: ..."); on a page without that content their check prints an explicit "not applicable" OK.
CONDITIONAL = {"hub": {"faq.box", "faq.ask-card", "post.logos"},
               "post": {"faq.box", "faq.ask-card", "post.takeaways", "post.toc-h2", "post.logos"},
               "core": {"faq.box", "faq.ask-card", "core.contact-form-first", "core.service-links"},
               "money": set()}


@check("house.features", "156", what="every house feature of the page's type is present (runs last, reads the feature checks)", needs="live")
def house(ctx):
    from .core import CHECKS
    wanted = ctx.cache.get("needs_filter") or set()       # gate --needs live: only the checks that were asked for count
    need = [c for c in HOUSE[ctx.ptype] if not wanted or CHECKS[c].needs in wanted]
    got = {}
    for line in ctx.lines:
        if line.cid in need and line.cid != "house.features":
            got[line.cid] = "FAIL" if "FAIL" in (got.get(line.cid), line.level) else line.level
    notrun = [c for c in need if c not in got]
    missing = [c for c in need if got.get(c) == "FAIL"]
    skipped = [c for c in need if got.get(c) == "SKIP"]       # not applicable here (no adapter, feature off): counted apart
    # Rule 161: a reader-visible house feature is never dropped silently. A feature switched off in growth.json
    # "features" counts as missing unless growth.json "features_dropped" gives the fit reason for it (2.3.0).
    dropped = ctx.cfg.get("features_dropped") or {}
    whys = {line.cid: line.what for line in ctx.lines if line.level == "SKIP"}
    for c in list(skipped):
        m = re.match(r"feature '([\w-]+)' is off", whys.get(c, ""))
        if m and not str(dropped.get(m.group(1), "")).strip():
            skipped.remove(c)
            missing.append(f"{c} (features.{m.group(1)} is off with no reason in growth.json features_dropped)")
    unchecked = [c for c in skipped if "no adapter for" in whys.get(c, "")]
    if unchecked:          # a reader-visible feature this stack cannot check yet: say so, never count it as present (2.5.0)
        ctx.warn(f"not checked on this stack ({ctx.stack()}): {', '.join(unchecked)}",
                 "check these by eye on the shots until the kit reads them from the served page (rule 161)")
    ctx.verdict([f"not run: {c}" for c in notrun] + [f"missing: {c}" for c in missing],
                f"all {len(need) - len(skipped)} applicable house features of a {ctx.ptype} page present"
                + (f" ({len(skipped)} skipped: not applicable to this site)" if skipped else ""),
                "add each missing feature (its own FAIL line above has the fix), or give the reason in the pull request (rule 156)")
