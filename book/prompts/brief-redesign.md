# Brief: redesign ONE page with its own UI and journey

You are building ONE redesigned page of __SITE_NAME__: `__FILE__` (live path `__URL__`). This is NOT a copy of another
page. Each page gets the layout its reader needs, built on in-depth research, with the reader, the buyer stage, the
first screen and the path to "__CTA__" thought through. Reviewers see it on a local URL first; nothing ships without
the owner's yes.

## Read first (all of it, in this order)
1. The page's design brief: __BRIEF__ (the lead's one-paragraph spec for who reads it, the hook, the first screen, the
   signature element).
2. The research: `__PROJECT__/research/__SLUG__-research-__DATE__.md` (your evidence: facts with sources, gaps, pain
   points, interactive ideas, outline). Every fact on the page comes from it or from a source you read today and
   record in a fact file.
3. `__PROJECT__/BRAND.md`, the page rulebook, `__PROJECT__/SETUP.md`; the site repo's agent rules and design notes
   (tokens and shared styles).
4. How existing components work, and one finished page of the same kind as yours.
__EXTRA__

## How the site is built
Copy the "how the site is built" rows from `__PROJECT__/SETUP.md` here.

## Where you work
Worktree `wt-__W__`, branch `page/__SLUG__` (see lane-write.md "Where you work"). Dev server port: __PORT__.

## Deliver (commit after each step, by path)
0. Fact file: `__PROJECT__/research/__SLUG__-facts-__DATE__.md` (every claim on the new page: source URL, date,
   confidence).
A. Build the page to the design brief: the first screen as the brief says; the signature element as a real working
   component (state kept in the URL where it helps, keyboard reachable, phone width, respects reduced motion);
   reader-stage order; one fact in one place; the main path short with detail in folds; FAQ at most 7 and FAQPage
   equal to the visible FAQ; one conversion path with the one offer, "__CTA__", tied to the reader's answer. Fair to
   every named alternative: a rival, a do-it-yourself way or "keep what you have" can be the right answer for some
   readers.
B. Pictures: every card or section that shows a picture has one; new article covers are original and registered with
   provenance. No third-party art or copy.
C. Internal links: the cluster's money page, the hub, two or three sibling posts, and the feature pages where
   relevant. Every link works.
D. SEO: title (the lead's call, 60 characters or fewer): "__TITLE__"; description about 150 characters; one H1
   written for the reader; FAQPage; dates true; no rating schema.
E. Your own re-read against the fact file: unsourced numbers, unfair statements about rivals, anything the site cannot
   support.
F. Checks (all must pass):
   - Only the checks this change touches: `growth checks` (rule 105). Never the whole suite "to be safe".
   - Only if the layout or design changed, a browser look (headless): the page at 1366 and 390 wide, light and dark
     where the site has a dark mode. The first screen answers the search promise; no sideways scroll; no console
     errors; every image loads; every internal link works; the CTA opens the booking path; the FAQ matches the FAQPage
     markup.
   - Two screenshots (1366 and 390) to `__PROJECT__/research/__W__-shots/` for the owner. These you keep.

Shared components: change them only when the change is general, and then add or extend a test and re-check two other
pages that use the component. No page names inside a component.

## Rules
Paste Block 1 (BUILDER RULES) from the README.

## Report (simple English)
What the reader sees from top to bottom; the signature element and how it works; calls you made; links INTO the page
that other pages should add (not edited by you); what you could not verify; Needs the owner; checks with exact pass or
fail; screenshot paths; last commit. Then "done, nothing left", and end yourself.
