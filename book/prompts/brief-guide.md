# Brief: rebuild ONE buyer's guide

You are rebuilding ONE guide post of __SITE_NAME__: `__FILE__` (live path `__URL__`). Guides are the hub-level,
long-form posts of a cluster (for Brightline: "the complete guide to lawn aeration"). The guide must agree with the
cluster's other posts and money page and send readers to the right one. Be visibly fair to alternatives (doing it
yourself, other providers).

## Read first
0. `__PROJECT__/BRAND.md`, the page rulebook, `__PROJECT__/SETUP.md`; the site repo's agent rules.
1. Every live post in the same cluster and the cluster's money page. Their facts are checked: never contradict them;
   reuse their numbers and link to them. Terms the site already defines keep one meaning.
2. Fact files in `__PROJECT__/research/` for this cluster.
3. Search results for "__KW__": `__SERP__`. Filter by intent first: forums, vendor landing pages and directories
   serve a different purpose.

## Where you work
Worktree `wt-__W__`, branch `page/__SLUG__` (see lane-write.md "Where you work"). Dev server port: __PORT__.
4. Comparison rule (rule 109, `kit/checklists/review.md` R1 to R3): for every price sum or "cheaper" claim, name the
   feature the sum is about, then price the cheapest plan on each side that HAS that feature. Every number in the head
   and the verdict is also stated in the body with its source. No two answers (FAQ, body, verdict) say different things.

## Deliver (commit after each step, by path)
0. Fact-check every claim of the current post (body, tables, FAQ, structured data) and write
   `__PROJECT__/research/__SLUG__-facts-__DATE__.md` (claim, source URL, date, confidence). __STEP0__
A. Rebuild for the reader's stages: an answer-first head (who this guide is for, the short answer, the reader's
   paths), the one tool, table or worked example that answers the guide's question (for Brightline: a worked cost
   example on a stated lawn size), short summaries of related posts that each LINK to the post instead of repeating
   it, a FAQ of at most 7 (same set in the FAQPage markup), one closing next step ("__CTA__"), and a short "how we
   wrote this". Cut repeats and invented examples. Worked examples are recomputed.
B. Pictures: tables and diagrams that help; the cover is original and registered.
C. Internal links to every relevant live page; every link works.
D. Title (the lead's call, 60 characters or fewer): "__TITLE__"; description about 150 characters; one H1; FAQPage
   equals the visible FAQ; `updated` set to today; no rating schema.
E. Your own re-read: all arithmetic recomputed, nothing contradicts a live page, nothing flatters the business beyond
   what the site supports.
F. Checks: only `growth checks` (rule 105); a browser look only if layout or design changed (1366 and 390, first
   screen, no sideways scroll, no console errors, images load, links work, the CTA opens the booking path, FAQ equals
   FAQPage).

## Rules
Paste Block 1 (BUILDER RULES) from the README.

## Report (simple English)
By step; calls you made; links into the page the lead must add; what you could not verify; Needs the owner; reading
minutes before and after; checks with exact pass or fail; last commit. Then "done, nothing left".
