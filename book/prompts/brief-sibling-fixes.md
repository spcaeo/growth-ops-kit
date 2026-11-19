# Brief: clean-up lane for the sibling-page changes the page lanes left for the lead

Page lanes (writers and testers) finished pages and, by rule, did NOT edit other pages. They listed the changes other
pages need ("Sibling changes for the lead", "open problems", "Needs the owner", the writer's notes) in their reports.
Your job: collect every such request, check each against the live content, and apply the ones that are right,
properly.

## Where the requests are
- The workflow journals of this session: every `journal.jsonl` under `__JOURNALS__` (one JSON line per agent result;
  read the "result" values: writer reports are plain text, tester reports are JSON with "open_problems" and
  "report"). Read them with a small script (write it with your file tool into `__PROJECT__/research/raw/`, run it in
  isolated mode).
- The list in `__PROJECT__/research/raw/followups.txt` if it exists.

## What to do
1. Build a table in `__PROJECT__/research/sibling-fixes-__DATE__.md`: page to change, the change asked, who asked
   (which lane), and your decision (apply / already done / wrong or out of date / needs the owner) with one line why.
   Anything that needs the owner (prices, claims, case studies, new offers) is listed under "Needs the owner" and not
   applied.
2. Apply the "apply" ones: links back to new or rebuilt pages (varied, natural anchor words, never the exact title
   every time), stale facts (an old number a newer page corrected), duplicate FAQ questions (reword the weaker page's
   question or cut it to one line plus a link), titles and descriptions another lane asked to sharpen, and the hub's
   "spokes linked" flag (true only when every post in the cluster links back to its hub).
3. Posts keep their slugs and URLs; never rename. A change to a post's `date` is a publish-gate change: do not make
   one.

## Checks
Only `growth checks` (rule 105); a browser look only if layout or design changed. Small commits, one theme each. When
green, append `sibling-fixes ready <last commit>` to `__PROJECT__/research/raw/lanes-ready.txt` with `>>`.

## Rules
Paste Block 1 (BUILDER RULES) from the README.

## Report (simple English)
How many requests you found, applied, skipped and why; what needs the owner; checks with exact pass or fail; last
commit. Then end yourself.
