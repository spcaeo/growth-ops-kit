# Brief: build one money page as a prototype for the owner

Build the new __PAGE__ money page INSIDE the real site, on a local URL, for the owner's OK. Nothing ships without the
owner's yes. The research dossier is done; you build from it.

Worktree `__W__`, branch `page/__SLUG__`, port `__PORT__`.

## What to learn from earlier work (read this twice)
__HISTORY__
Do not reuse a layout the owner rejected. One strong design, not two. The bar to meet or beat is what the owner has
already approved: __APPROVED__ (look at each in your dev server before you design).

## Read first
- The dossier: `__PROJECT__/research/__SLUG__-dossier-__DATE__.md`: especially the buyer types, the pain, the internal
  sale, the hook options, the sample first screens, the journey fold by fold, the signature interaction, the ask
  ladder, and the searches to own and to leave. Refresh only what is stale; never read a page behind a bot check.
- `__PROJECT__/BRAND.md`, the page rulebook, `__PROJECT__/SETUP.md`, the book's `playbooks/money-page.md`; the site
  repo's agent rules.
- The fold plan: `__PROJECT__/research/plans/__SLUG__.json` and the checkpoints file
  `__PROJECT__/research/__SLUG__-checkpoints.md` (rules 36h, 0a). Build from them.
- The owner's standing answers (from `BRAND.md` and the steps log). Open owner questions in the dossier stay out of
  the page until the owner answers; write around them.

## Build
1. A unique page for THIS buyer, with its own hook, its own signature interaction (the dossier's, or better), and its
   own journey; reuse existing components and the site's look where they fit. Animated where it helps (rule 141),
   deep but not long.
2. Every state of the interaction is kept in the URL and survives reload and Back and Forward; keyboard reachable;
   respects reduced motion. Every call to action goes through the one conversion path (rule 32).
3. No empty space, no hollow cards, no placeholder-looking buttons, no lone column with an empty half. First screen:
   the answer, the proof that the business is the right partner (only sourced proof), one clear ask.
4. Shared components only when general, with a test; every other page must look the same (check the sibling money
   pages and the home page).
5. SEO: title 60 characters or fewer for the searches the dossier says to own; description about 150 characters; one
   H1; FAQ = FAQPage; no rating schema. Keep the route registered in the hub list and the sitemap.
6. Run the gate after every fold commit (`growth gate page ...`) and fix its FAILs before the next fold.

## Show it
Screenshots of EVERY section at 1366 and 390 to `__PROJECT__/research/__W__-shots/` (you keep these). Look at each as
a demanding art director who knows the owner rejects empty-looking pages; fix until you would show it to the owner.
Then, if the lead asked for it, LEAVE the dev server running at `http://127.0.0.1:__PORT__<path>` and give the URL.
(The lead gives the owner a link only after `growth ready` says READY: the golden rule.)

## Checks
Only `growth checks` (rule 105); a browser look only if layout or design changed. Do NOT write a ready line: this
waits for the owner.

## Rules
Paste Block 1 (BUILDER RULES) from the README.

## Report (simple English)
The hook and the idea and why it fits this buyer; what each section does; what is new versus before; open owner
questions you wrote around; the review URL; the screenshot folder; checks with exact pass or fail; last commit. Then
end yourself.
