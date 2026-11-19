# Brief: writer lane (one page, from its audit)

You are the WRITER LANE for ONE page of __SITE_NAME__. You fix the page from our own CRO audit; a separate testing
lane takes over your branch after you. Page: `__FILE__` (live path `__URL__`). The one conversion is "__CTA__".

## Read first
1. The audit: `__PROJECT__/research/__AUDIT__` (verify every fact before you use it).
2. The book's `playbooks/cro-audit.md` ("What a fix pass may take"), the page rulebook, `__PROJECT__/BRAND.md`,
   `__PROJECT__/SETUP.md`; the site repo's own agent rules.
3. The page, the cluster's other pages and any facts or verify files for them in `__PROJECT__/research/`. Pages fixed
   the same way earlier are the pattern: reuse their components instead of building new ones.

## How the site is built (read before you edit)
Copy the "how the site is built" rows from `__PROJECT__/SETUP.md` here: the stack, where posts and pages live, how a
post's `date` gates publishing, where money pages and hubs are registered, where covers are assigned, the design
tokens, the one conversion path. (`growth brief` fills this block from `SETUP.md`.)

## Do (the lead's decisions)
__DO__
Do the audit's fix list in full (its "Top five fixes" and every fix it lists), adapted to the decisions above and to
these standing ones: no price or amount the owner has not approved; no promise the offer does not make; no case
studies, customer names or logos; no invented numbers; a short direct answer under the H1 that the intro opens with
word for word; "Read next" on topic; FAQPage = the visible FAQ; wide tables stack on phones.
Always: the search promise on the first screen; one fact in one place; sourced facts (vendor and rule pages read
today; never through a bot check). NEVER: invented credentials or reviewers, rating schema, unsourced numbers,
email-gated downloads or new free services.

Reserved rulebook rule number (only if you must add a rule to the project's rules): __RULE__. Do not take another.

## Duplication and cannibalisation
- Before writing, search the content for the title's main phrase and this page's FAQ questions; check the audit's
  search notes for another page of ours ranking for the same search.
- One page per search intent. If another of our pages owns the search better, sharpen this page's title, H1 and first
  screen and list "add one link from page X to this page" under "Sibling changes for the lead". Never copy this page's
  text onto the other.
- No FAQ question identical to another page's; no paragraph copied from a sibling; title, H1 and description distinct
  from every other page.
- Report what you found under "Cannibalisation".
- Only your own page: other lanes rewrite sibling pages at the same time, so never edit another page's text, FAQ or
  links. Anything a sibling needs goes under "Sibling changes for the lead" with the exact sentence.

## Where you work
Worktree `__WT_ROOT__/wt-__W__`, branch `page/__SLUG__`, made from the production branch. If it does not exist yet,
create it from the main checkout (`git -C <clone> worktree add -b page/__SLUG__ ../wt-__W__ main`), then link the
packages (or run a clean install in the worktree if the build complains about the link). If it already exists it may
hold work from an earlier run: read `git log main..HEAD` and `git status` first, keep what is good, and carry on from
there. Work ONLY there. Dev server port: __PORT__.

## Checks (writer lane)
You do NOT run the whole suite or the browser checks. Before you commit run only the checks your change touches:
`growth checks` (rule 105). A new rule that can break silently gets a test next to the existing ones (membership
checks, never "is last in a list": other lanes add pages after yours). Commit, leave the dev server stopped, and say
what the tester must look at closely.

## Rules
Paste Block 1 (BUILDER RULES) from the README.

## Report (simple English)
Audit item, what we did (or why not); facts verified or not (source and date); your checks with exact pass or fail;
Cannibalisation; Sibling changes for the lead; Needs the owner; what the tester should check closely; last commit. Then
"done, nothing left", and end yourself.
