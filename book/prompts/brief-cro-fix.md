# Brief: fix ONE page from its CRO audit (stand-alone)

Use this when you do not run the lane workflow. It is the writer-lane brief ([lane-write.md](lane-write.md)) with its
own checks, so one agent fixes and checks the page.

You fix ONE page of __SITE_NAME__ from our own CRO audit: `__FILE__` (live path `__URL__`). Branch `page/__SLUG__`
(worktree `__W__`, port `__PORT__`). The one conversion is "__CTA__".

## Read first
Same as lane-write.md: the audit `__PROJECT__/research/__AUDIT__`, the CRO-audit playbook, the page rulebook,
`BRAND.md`, `SETUP.md`, the site repo's agent rules, the cluster's other pages and their fact files.

## Do
__DO__
Do the audit's fix list in full, adapted to the lead's decisions above. Standing rules are the same as in
lane-write.md ("Do", "Duplication and cannibalisation").

## Checks (you run them, because no tester follows)
1. `growth checks` (rule 105): only what the change touches.
2. `growth gate page __URL__ --url http://127.0.0.1:__PORT__ --repo . --type <type>`: no FAIL.
3. Only if layout or design changed, a browser look (headless): the page at 1366 and 390 wide; the first screen
   answers the search promise; no sideways scroll; no console errors; every image loads; every internal link works;
   the CTA opens the booking path; the FAQ matches the FAQPage markup.
4. `growth tech_seo_check http://127.0.0.1:__PORT____URL__`: no FAIL.

## Rules
Paste Block 1 (BUILDER RULES) from the README.

## Report (simple English)
Audit item, what we did (or why not); facts verified or not; checks with exact pass or fail; Cannibalisation; Sibling
changes for the lead; Needs the owner; last commit. Then "done, nothing left" and end yourself.
