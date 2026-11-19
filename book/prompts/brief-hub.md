# Brief: rebuild one cluster HUB page

You rebuild the HUB page of one topic cluster of __SITE_NAME__. A hub is the cluster's main page, often also its money
page (for Brightline: `/lawn-aeration`). Every post in the cluster may have been rebuilt since the hub was last
touched; the hub must catch up and read as a reader's map. Be fair: a hub that is useful to a reader who is not ready
to buy is the one that earns the conversion.

## Read first
0. The model: another hub that is already good (the lead names it; otherwise the page with the most depth). Learn from
   it, but do NOT copy its layout: each cluster's readers differ.
1. Every post in the cluster: titles, descriptions, key takeaways, who each page is for. The hub must agree with them
   on facts and send each reader to the right post. One fact, one place: the hub states no limit, number or rule that
   a post owns; it links the post.
2. `__PROJECT__/BRAND.md`, the page rulebook, `__PROJECT__/SETUP.md`, the site repo's agent rules.
3. Search data for the hub (Search Console through your connector, or the page tracker, else `research/serp/`; never
   guess traffic). Design for the searches people use to reach the hub.

## Deliver (commit after each step, by path)
0. A short CRO audit of the current hub (first screen, paths, repeats, dead text, calls to action, mobile) and a fact
   check of every claim: `__PROJECT__/research/__CLUSTER__-hub-audit-__DATE__.md`.
A. Rebuild as a reader's map for THIS cluster (rule 26): a first screen that answers the search in one line; "start
   here" paths by the reader's real situation; every post grouped with a one-line note that matches the post; at most
   6 FAQ (FAQPage equal to the visible FAQ; no question that repeats a post's own FAQ word for word); the cluster's one
   closing call.
B. Every post card on the hub carries its cover picture (rule 144). Never strip pictures to shorten the page; cut
   repeated text instead.
C. Every cluster post is linked at least once; every link works; varied, natural anchor words. Mark the hub "spokes
   linked" only when every post in the cluster links back to the hub in its body (the site's test checks it).
D. SEO: title 60 characters or fewer matching the hub's real searches; description about 150 characters; one H1 in the
   first screen; FAQPage; no rating schema.
E. A fresh-eyes look at 1366 and 390: no empty card, no big empty space, no unfinished-looking card, no sideways
   scroll, no console errors. Fix what looks weak (rule 158).
F. Checks: only `growth checks` (rule 105); a browser look only if layout or design changed. When green, append one
   line `__W__ ready <last commit>` (or `__W__ blocked <reason>`) to `__PROJECT__/research/raw/lanes-ready.txt` with
   `>>` (never rewrite the file).

A hub waits for the owner's OK: leave the dev server RUNNING at the end if the lead asked for it, give its URL, and
write no "ready" line in that case. Otherwise stop it.

## Where you work
Worktree `wt-__W__`, branch `page/__SLUG__`. Dev server port: __PORT__.

## Rules
Paste Block 1 (BUILDER RULES) from the README.

## Report (simple English)
By step; your design idea for this hub and why it fits its readers; calls you made; what you could not verify; Needs
the owner; checks with exact pass or fail; last commit; sibling changes for the lead. Then end yourself.
