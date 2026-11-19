# Brief: rebuild ONE "best list" or "alternatives" post

You are rebuilding ONE list post of __SITE_NAME__: `__FILE__` (live path `__URL__`), for example "best lawn care
software" or "alternatives to <vendor>". If the business is itself one of the tools a list may rank, these pages are
where readers trust it least: they must be visibly fair, sourced, and useful even to a reader who should pick another
tool or none.

## Read first
0. `__PROJECT__/BRAND.md`, the page rulebook and the book's playbooks; `__PROJECT__/SETUP.md`; the site repo's agent
   rules.
1. The current post and the other lists and comparisons of the same cluster. Never contradict a live page; reuse its
   facts; re-read a vendor page only for what it does not cover.
2. Search results for "__KW__": `__SERP__`. Filter by intent first. Note what list-style results promise in their
   titles and what none of them offers.
3. Mistakes to avoid: every `__PROJECT__/research/*-verify-*.md` (the independent checks: learn their kinds,
   especially unfair comparisons, prices shown as if the vendor's, unsourced numbers).

## Deliver, in order (commit after each step, by path)
0. Plan and fact check: `__PROJECT__/research/__SLUG__-plan-__DATE__.md` (who lands here and why; the reader paths;
   why people leave the current page; the new page top to bottom; the tool list with stated criteria, at most 9, plus
   an "also looked at" row with reasons) and `__PROJECT__/research/__SLUG__-facts-__DATE__.md` (every claim checked
   against each vendor's OWN pages, read today, one request at a time: claim, source, date, confidence). __STEP0__
A. Rebuild section by section: an answer-first head (who should pick which kind of tool, in plain words; the reader
   paths), a visible disclosure ("This list is by <business>, which makes one of the tools below", rule 16), the
   criteria stated up front, a short "do you need a tool at all" part (staying on what they have is a real answer),
   the tools as compact cards (what it is for, works, missing, price only as the vendor publishes it, with the date),
   a lineup at the top (rule 143), a FAQ of at most 7, one closing next step.
B. Logos (rule 143): every tool named in a heading, table head, card or list shows its logo or icon, taken from the
   company's own site (downloaded into an empty scratch folder, cleaned, saved with the source URL and date noted in
   your fact file). A tool with no usable image goes in your report with the reason.
C. Internal links: the cluster's money page, the related guide and posts; every link works.
D. Title (the lead's call, 60 characters or fewer): "__TITLE__"; description about 150 characters; one H1 that says who
   the page is for; FAQPage = visible FAQ; `updated` is today; no rating schema.
E. Your own independent re-read against the fact file and the verify files' kinds of mistake.
F. Checks: only `growth checks` (rule 105); a browser look only if layout or design changed.

## Where you work
Worktree `wt-__W__`, branch `page/__SLUG__`. Dev server port: __PORT__.

## Rules
Paste Block 1 (BUILDER RULES) from the README.

## Report (simple English)
By step; calls you made; links INTO your page the lead must add; tools with no logo and why; what you could not
verify; Needs the owner; checks with exact pass or fail; reading minutes before and after; last commit. Then "done,
nothing left" and end.
