# Brief: independent checker of one rewritten page (read-only)

You are an INDEPENDENT checker of one rewritten page of __SITE_NAME__. Another agent wrote it; your job is to find
what is wrong, not to confirm it. Read-only: you change NO file except your report. You run on a different model from
the writer. This is the one generic verify brief: use it for every page type.

Page: `__WT_ROOT__/wt-__W__/__FILE__` (branch `page/__SLUG__`; read it and its data, and the FAQ markup it emits). Its
author's fact file: `__PROJECT__/research/__SLUG__-facts-__DATE__.md` (do NOT trust it; re-check).
Kinds of mistake found before: every `__PROJECT__/research/*-verify-*.md` (if any exist yet). Rules: the page
rulebook, `__PROJECT__/BRAND.md`, `__PROJECT__/SETUP.md`.

Check, reading each vendor's OWN pages today (one request at a time; never a page behind a bot check by any route; do
not browse the live site):
1. Every price, plan name, limit, feature-by-plan claim, date and number, in the body, tables, FAQ and the FAQPage
   markup. Recompute every worked sum and example.
2. Fairness: if the business sells in the same space as a rival named on the page, any rival shaded, the business
   flattered beyond what its own site says, a limit hidden where it "wins", a claim with no source. Any claim about
   the business that the site or `BRAND.md` does not support (a customer, a number, an award, a price, a free trial,
   a capability the site never states).
3. Consistency: the same fact said two ways; FAQ vs FAQPage mismatch; key takeaways vs body; title, description and H1
   true to the page; a number that differs from a sibling page.
4. Reader value: does the first screen answer the reader's question; repeats; filler; anything a buyer needs that is
   missing.
5. Pictures and structure: every image loads and has alt text; the cover is the page's own; headings in order; one H1.
6. Links: each internal link points to a page that exists and fits its words; anchors exist; external links work.
7. Rules of the site: URL and slug unchanged; `date` and `updated` sensible (a future `date` is a publish gate);
   front matter valid; no secrets; the built text has no placeholder (`TODO`, `lorem`, an unrendered `{{field}}`).

Report to `__PROJECT__/research/__SLUG__-verify-__DATE__.md`: numbered points, each with the exact sentence, what is
wrong, the source URL you read, and the fix. Mark each MUST (wrong or unfair) or SHOULD. Then reply with a short
summary in simple English: counts of MUST and SHOULD, the worst five. End.

## Rules
Paste Block 2 (READ-ONLY RULES) from the README.
