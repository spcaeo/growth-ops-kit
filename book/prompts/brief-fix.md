# Brief: fix a set of pages after an audit

You tighten and fix live pages of __SITE_NAME__ after an audit against the owner's standard. Pages: __PAGES__. Branch
`page/__SLUG__` (worktree `__W__`).

## Read first
1. The owner's standard for pages: `__PROJECT__/BRAND.md`, the page rulebook, `__PROJECT__/SETUP.md`, and the site
   repo's own agent rules.
2. The audit: `__PROJECT__/research/__AUDIT__`, the sections for these pages and its cross-page notes.
3. Each page's earlier fact and verify reports in `__PROJECT__/research/` (facts are already checked; reuse them).

## How the site is built
Copy the "how the site is built" rows from `__PROJECT__/SETUP.md` here.

## Do, for each page
A. Fix every MUST in the audit and every SHOULD that holds up when you re-read the source. A tool, company or rule you
   newly name is checked first on its OWN pages, read today, one request at a time (never a page behind a bot check),
   and added to the page's fact file as a dated note: `__PROJECT__/research/<slug>-facts-__DATE__.md`.
B. Cut and move to reach the length the audit asks for: one fact in one place; cut text that repeats the intro,
   repeats a sibling page, or says nothing. No fact is lost: a fact that lived only in a cut part moves to the one
   place it belongs.
C. Keep title, description and H1 true to the page and distinct from every other page. Keep the FAQ and its FAQPage
   markup identical.
D. Internal links: every link points to a live path; varied, natural anchor words.

## Where you work
Worktree `wt-__W__`, branch `page/__SLUG__`, from the production branch (see lane-write.md "Where you work"). Dev
server port: __PORT__.

## Checks
- Only the checks this change touches: `growth checks` (rule 105). Never the whole suite "to be safe".
- Only if the layout or design changed, a browser look (headless): the page at 1366 and 390 wide, light and dark
  where the site has a dark mode. The first screen answers the search promise; no sideways scroll; no console errors;
  every image loads; every internal link works; the CTA opens the booking path; the FAQ matches the FAQPage markup.

## Rules
Paste Block 1 (BUILDER RULES) from the README.

## Report (simple English)
Per page: MUSTs fixed, SHOULDs fixed or rejected (with the reason), words or reading minutes before and after, things
newly named and where their facts came from, checks with exact pass or fail, last commit. Sibling changes for the
lead. Needs the owner. Then "done, nothing left" and end yourself.
