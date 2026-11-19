# Brief: rebuild ONE "X vs us" comparison

You are rebuilding ONE head-to-head comparison post of __SITE_NAME__: `__FILE__` (live path `__URL__`), comparing
__COMPETITOR__ with the business (or a method, such as "doing it yourself vs hiring a service"). The business makes or
sells one of the two, so this page type is where readers trust it least: it must be visibly fair, sourced, and useful
even to a reader who should pick __COMPETITOR__ or neither. Short, deep and unique.

## Read first
0. `__PROJECT__/BRAND.md`, the page rulebook and the book's playbooks; `__PROJECT__/SETUP.md`; the site repo's agent
   rules.
1. The live lists and guides of the same cluster. Never contradict a live page; reuse its facts; re-read a vendor page
   only for what it does not cover (one request at a time; never a page behind a bot check: write "not published on
   pages we could read").
2. Search results for "__KW__": `__SERP__`.
3. Mistakes to avoid: every `__PROJECT__/research/*-verify-*.md`.
4. Comparison rule (rule 109, `kit/checklists/review.md` R1 to R3): for every price sum or "cheaper" claim, name the
   feature the sum is about, then price the cheapest plan on each side that HAS that feature. Every number in the head
   and the verdict is also stated in the body with its source. No two answers (FAQ, body, verdict) say different things.

## Deliver (commit after each step, by path)
0. Fact check every claim of the current post (body, tables, FAQ, structured data) against the vendors' OWN pages and
   write `__PROJECT__/research/__SLUG__-facts-__DATE__.md` (claim, source URL, date, confidence). __STEP0__
A. Rebuild for the reader's stages: an answer-first head (who should pick __COMPETITOR__, who should pick the
   business, who should stay on what they have; the reader paths); the disclosure stated plainly under the byline
   (rule 16); ONE side-by-side table with a printed grading rule (Yes = in the cheapest plan or standard; Partly =
   only on a higher plan or with set-up, named; No = not offered; "not published" where a vendor publishes nothing),
   every row sourced and dated (rule 25); a short verdict; a FAQ of at most 7.
B. Logos (rule 143): each tool named as a label shows its logo, from the company's own site; a tool with none is
   named in your report with the reason.
C. Internal links: the cluster's money page, the related list and guide; every link works.
D. Title (the lead's call, 60 characters or fewer): "__TITLE__"; description about 150 characters; one H1; FAQPage =
   visible FAQ; `updated` is today; no rating schema.
E. Your own re-read. The mistakes independent checks find most often: a strength graded "Yes" for the business on a
   higher plan while the rival's is "Partly" on its cheapest; a rival's free plan or free option left out of a cost
   sum; a limit hidden where the business "wins"; a price crossover stated from a few picked sizes (compute every size
   and state the pattern); the verdict repeated word for word; a switch promised that the business does not offer.
F. Checks: only `growth checks` (rule 105); a browser look only if layout or design changed.

## Where you work
Worktree `wt-__W__`, branch `page/__SLUG__`. Dev server port: __PORT__.

## Rules
Paste Block 1 (BUILDER RULES) from the README.

## Report (simple English)
By step; calls you made; links INTO your page; what you could not verify; Needs the owner; checks with exact pass or
fail; reading minutes before and after; last commit. Then "done, nothing left" and end.
