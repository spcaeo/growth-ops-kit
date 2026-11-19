---
title: Playbook - a money page
version: 2.0.0
updated: 2026-11-18
license: CC BY 4.0
---

# Playbook: a money page (the pages that sell)

**Version 2.0.0 (generic edition) · 18 Nov 2026**

For the pages that bring buyers to the one conversion: the main service pages, pricing and the home page. For
Brightline Lawn Care (https://brightline.example) that is `/lawn-mowing`, `/lawn-aeration`, `/leaf-cleanup`,
`/pricing` and `/`, and the conversion is its one CTA, "Get a quote". The project's `SETUP.md` says which files hold
their text and code.

**No shortcuts** ([02-owner-rules.md](../02-owner-rules.md) section 1): every step below, in order, with both owner
check-ins. Where this sits in the whole process: [01-flow.md](../01-flow.md) stage C.

These pages do **not** go through the parallel lanes. One page at a time, slowly, with two owner check-ins. Each page
must be unique: its own reader, its own problem, no copying of what the guides and posts already say.

---

## Step 0: inventory and snapshot (always first)

**Archive the live page first** (rule 36i): `growth page_archive capture <path> --stage before` (full-page images at
1366 and 390 plus the HTML, for the owner's talks and demos). After release: `--stage after`.

1. `growth inventory`: the full inventory must be current (today). It says which page group, pillar and cluster the
   page belongs to and how it compares with its siblings.
2. Money pages first: pick from the "Money pages" table in `inventory/INVENTORY.md` unless the owner names a page.
3. `growth page_snapshot <path> --task <T#> --action "<what>"`: page elements plus all its Search Console data (every
   query with clicks, impressions, click rate, position; daily; countries) and analytics data. This is the baseline;
   take it again after the change goes live.

## Part 1. The questioning guide

Every money page answers all of these, in writing, **before** anything is designed. Each answer carries its evidence
(a search figure, a quote with a link, a competitor page read on a date, a line on an approved live page). "We think"
is not an answer; an open question goes to "Questions for the owner".

### A. The search: why anyone lands here
1. Which searches show this page today (Search Console), with impressions, clicks, click rate and position, for the
   last 90 days and the last 28?
2. Which of them are buying searches ("service", "pricing", "best ... for ...") and which are learning searches a
   guide should own?
3. For each buying search, what does Google show in the top 10, by page type (company page, review list, directory,
   forum, video, AI answer)? Can a company page win it at all?
4. Where do we rank, and why there and not higher (Part 1 E)?
5. Which of our own pages compete for the same search? Which page should own each search?
6. Which countries and regions do the impressions come from? Check before assuming the audience is only the primary
   market in `growth.json`.

### B. The buyer: who, at what level, and why now
7. Who are the three to five buyer types (role, size, what they need done, the tool or mess they have now)? Which is
   the most common and which the most valuable?
8. How far along is each: not looking yet; comparing; switching from another provider; setting up something new?
9. Who reads (owner, office manager, a family member), and who signs?
10. What happened this week that made them search (a failed job, a busy season, a move, a renewal)?
11. What pushes them out of today's way, what pulls them toward us, what makes them anxious, what habit keeps them?
12. The jobs: get the work done (functional); stop the worry (emotional); not be the person who chose badly (social).
13. In their own words: the strongest real quotes (forums, reviews, People Also Ask) with links.
14. What do they fear about choosing a new provider (a long wait, a hidden price, a bad first visit)?
15. The inside sale: what does the person who found us need to bring to the person who decides?

### C. The competition: read 10 to 20 pages in full, one at a time
16. For each result: who they are, the promise on the first screen, every fold in order, depth, proof, the ask, any
    interaction, what they do well, what they leave unanswered.
17. Across all of them: what everyone says (so it is worth nothing), what nobody answers (our opening).

### D. Us: why this business, shown not claimed
18. What can we truthfully claim? Only what `BRAND.md` words: the hook, the features, the pricing words, the one
    conversion path. List each claim with its `BRAND.md` section.
19. What can we show instead of claim: the first step by step, who they talk to, a worked example built on entered
    numbers (for Brightline: a lawn size), the real screens or photos the owner approves.
20. What may we never say (`BRAND.md` "never claim" list): prices or amounts not on record, customer names, logos,
    quotes or results without a row in the permission log, "free" or "no obligation" unless allowed, invented reviews
    or awards. Say what the first step does cover.

### E. Why we rank where we rank
21. Per buying search, the top 5 against us: title and H1 match, first screen, depth, proof, freshness, structured
    data, speed, links and authority.
22. Our page: title, H1, description, length, topics, internal links in and their words, index status and last crawl,
    how long since a real rewrite.
23. The reasons, ranked, each with its fix, split into "the page rebuild fixes this" and "needs something off the
    page" (directory listings, links, reviews) for the owner to decide.

### F. The content map: no duplication
24. What our posts and feature pages already cover that this buyer needs: each becomes one line and a link on the
    money page, never a copy.
25. What only this page says.
26. Which FAQ questions this page answers that no other page asks (no FAQ question repeated across pages).
26a. **Internal links (from a real project; rule 88a):** inbound body links today (`growth journal show` and
     `growth link_map inbound <path>`), the cluster's hub and spokes, and the ranked list of pages that should link
     here from `growth link_map suggest <path>` (Search Console overlap, unlinked mentions, buyer questions). The plan
     goes into the journal against each source page; the top links ship with the page. Start from the site link
     graph (`growth link_graph page <path>`: every link in and out by zone, with anchors and the page's real Search
     Console queries next to them; playbook [link-graph](link-graph.md)). After the release, run
     `growth link_graph update <path>` (and on each page that got a new link) so the graph and its before and after
     are current.

### G. The page we will build
27. The hook: two or three options, one sentence each, and why each beats the competitors' first screens.
28. The journey: eight to twelve folds; per fold the buyer's question, the answer, the proof, the small step, the
    picture or interaction.
29. The one interaction unique to this page (for Brightline's mowing page: a "what will my lawn cost" check on an
    entered lawn size), what it asks, what it shows, how it leads to the CTA.
30. The ask ladder: the right next step for each buyer type. The main ask stays the project's one CTA label.
31. The target searches (title, H1, first-screen promise) and the searches we leave to other pages.
32. The voice: plain, concrete, written by someone who does the work. No filler (seamless, unlock, leverage, empower,
    streamline, cutting-edge, robust, world-class).

**Conversion parts every money page gets** (from a real project; rules 32a, 32b, 32c, 35, 35b, 36a, 36c, 36d): a
reason to act on every booking button, one bright call-to-action colour with a soft glow (32c), the scroll-in sticky
bar that replaces the menu, a relevant exit offer built from what the reader did on the page, a hand or arrow hint on
every interactive control, "+" preview cards on every prose link, and a clean technical SEO check
(`growth tech_seo_check`, no FAIL).

**Search data, engagement and AI answers** (from a real project):
33. Every query with real impressions, from this page AND every page that will redirect to it, mapped to the element
    that answers it (title, meta, H1, H2, first 100 words, FAQ, body). High impressions with a low click rate: the
    title and description that win the click, in the queries' own words.
34. Engagement: time on page, scroll, next pages, journeys (analytics). What do they say about the first screen?
35. AI search: the 10 to 15 questions a buyer types into ChatGPT, Perplexity or Google's AI answers; who gets cited
    and which passage shapes win (definitions, lists, tables, numbers); AI crawler visits; robots.txt and llms.txt.
    **AI answers check (from a real project):** the lead runs 2 to 3 buyer prompts in ChatGPT and 2 to 3 Google
    searches in the owner's own browser: ChatGPT in a temporary chat, one specific prompt (naming the page's unique
    job) and one generic ("best ... compare pricing"); Google: the head term, the "best for small" search, and the
    page's how-to question. **Use the primary market** (`growth.json` `market`): Google with that market's `gl`, `hl`
    and `pws=0`, ChatGPT prompts that name a place in that market. Store each as a run with `growth journal run`
    (query, market, settings, full answer, named yes or no, re-check date) and summarise in
    `research/<page>-ai-answers-<date>.md`. Read the page's journal (`growth journal show <page>`) before step 1.
    Never click through to our own site (it counts as a visit). Re-run the same prompts at day 28 and 56 after
    release (flow stage E).
36. GEO/AEO plan (rule 36b): the quotable answer in the first screen, direct first sentences in every FAQ, the
    structured data, the liftable table, and a text version of anything that only lives in a tool or a picture.

---

## Part 2. How we do it

1. **Dossier** (one researcher, read only): Part 1 answered in `research/<page>-dossier-<date>.md`.
2. **Lead review:** read the whole dossier, check every claim about the business against approved pages, cut anything
   generic.
3. **Owner check-in 1, short questions only** (from a real project: the owner reviews screens, never documents). The
   lead decides the hook, journey and interaction from the evidence; the concept file is the builder's input, not
   something the owner reads. In chat, ask only what the owner alone can answer (claims, offers, old pages to merge),
   in a few one-click questions with a safe default each; build on the defaults while the answers come in.
3a. **Fold plan before any build** (rule 36h): `growth fold_plan init <path> --url <local URL> --key <key>`, then
   answer all 14 detail fields for every fold and the 7 shared elements in `research/plans/<key>.json`. The builder
   works from it and `growth fold_plan check` must say "plan complete" before the build starts.
3b. **Pre-flight: nothing is built until everything is set** (rule 0a; from a real project: "when you start a new page
   the planning and preparation should be done in depth and all checkpoints clear set"). `growth preflight <path>
   --type ... --key ...` must say PASS. It finds the shared site problems that would fail the page at the end (fix
   them first, as their own commit), checks the planning evidence (the AI baseline is taken NOW, before the build),
   and writes `research/<key>-checkpoints.md`: every check sorted by when it runs. The brief (`growth brief`) and the
   checkpoints go to the builder together.
4. **Build inside the real site** on a branch, in a worktree, previewed locally (never a separate mock-up), phone and
   desktop. **Check as you go:** after every fold commit, run the gate on the preview and fix its FAILs before the
   next fold. The end of the build is a confirmation, not a repair session.
4a. **Independent review, then fixes** (rule 109): the reviewer is a different model from whoever built each part
   (for example builders on a mid model, reviewers on a stronger one; `growth agent_models` blocks a wrong model).
   Every finding is fixed or skipped with a one-line reason in `research/<key>-review-fixes-<date>.md`.
4b. **Clean-up before the final evidence** (from a real project: "clear all your dead codes, non used codes"): the
   gate's `repo.no-dead-files` and `repo.no-unused-code` pass; a scan for files nothing imports finds none the page
   left behind. Dead code that was already on the production branch goes on its own branch (`chore/...`), never into a
   page branch. Do this BEFORE shots and the click-test: any commit after them makes the page's evidence stale.
5. **GOLDEN RULE before check-in 2** (from a real project: "never share a URL before it is 100% approved and checked;
   this cannot be broken"). Step 6's checks run FIRST, all of them: research cross-check, CRO audit, independent
   review, fresh shots and click-test, share preview, AI baseline (speed is measured after publishing, on the
   production site). Then `growth ready <path> --type ... --key ...` must say READY (the full gate, 0 FAIL, at the
   current commit). Only then does the owner get the URL; the Stop hook (`url_guard`) blocks any reply that shows a
   page URL that is not READY.
5b. **Owner check-in 2, the prototype on the project's one preview address** (`growth.json` `preview_url`; owner,
   17 Nov 2026: "it should be on the same one"). Page branches stack in release order and the top of the stack serves
   that one address; a helper's own working port is never sent to the owner. The owner's first real look. Change until
   the owner is happy.
   **Stacked copies cost re-checks** (18 Nov 2026): a fix in a lower page's branch is rebased up the stack, and every
   page on that copy needs fresh shots and click-tests (evidence must be newer than the last commit). Moving the
   preview to the copy with a new page means one final evidence round for every page on it. Plan one round per move,
   not one per page; ask the owner before moving the preview they may be looking at.
6. **Finish (runs before 5, see the golden rule):** the research cross-check (the built page against the dossier and
   concept, item by item: every search to own, buyer fear, competitor gap and fold DELIVERED, WEAK or MISSING; owner,
   17 Nov 2026), then the CRO audit ([cro-audit](cro-audit.md)) against the prototype, only the checks the change
   touches (`growth checks`, rule 105), unique title, H1 and description, FAQ text equal to the FAQ data, no FAQ
   question asked on another page.
7. **Release alone** (then `growth page_archive capture <path> --stage after`, rule 36i), not in a batch
   ([release](release.md)); then check the live title, structured data and canonical.
8. **Ask Google to re-read it:** the owner requests indexing in Search Console the same day.
9. **Measure** (Part 3) and act (Part 4).

The owner's check-ins are the only waits. Everything else is the lead's call from evidence, reported after.

---

### Running it as workflows (optional)

If your agent tool runs scripted workflows, the job splits in two so the owner sees each step tick off:

- Steps 1 to 3: research (three researchers side by side), dossier, fact check (up to 2 rounds), concept file for
  check-in 1.
- Steps 4 and 6 to 7, after the owner's OK: prototype in its own worktree (a real redesign: new UI and UX from the
  research, its own interactive element, animation that honors reduced motion), checks, CRO audit of the prototype,
  fixes, independent review by a different model. It stops at check-in 2; the lead starts the local preview for the
  owner. Release alone, indexing and measuring are the lead's, after the owner's yes.

Without workflows, one agent follows the same steps and ticks each in the task.

## Part 3. Measuring after go-live

**Before launch, save the baseline** (the page tracker keeps the change date from git; Search Console and analytics
numbers join it when the owner switches them on): per target search, impressions, clicks, click rate, position (28 and
90 days); for the page, readers a day, visitors who leave at once, time on page, where readers go next, and
conversions that start from the page; index status and last crawl.

**The day it goes live:** check title, description, H1, canonical, structured data, no console errors, the CTA opens
the booking path. Owner requests indexing.

| When | What | Why |
| --- | --- | --- |
| Day 1 to 3 | has Google re-crawled it (last crawl date after the release)? | an uncrawled page cannot move |
| Day 7 | first look only: indexed, new snippet shown, impressions holding | Google re-ranks a changed page for 1 to 2 weeks |
| Day 14 | first verdict on click rate and position | the same length of days before and after |
| Day 28 | verdict on rankings, clicks, engagement and conversions | enough for a page with low search volume |
| Day 56 | verdict on conversions | buyers take weeks |

Google's numbers are final only 2 to 3 days late. A Google core update inside the window makes a verdict "too early"
until it has finished.

**The numbers that decide:** position and click rate per target search; impressions (new searches the page now shows
for); engagement (fewer who leave at once, more who reach the interaction and the ask); conversions per 100 readers.

## Part 4. Acting on the numbers

| What we see | Likely cause | What we do |
| --- | --- | --- |
| Not re-crawled by day 7 | weak internal links | request indexing again; add links from posts and the home page |
| Impressions up, click rate flat | the snippet does not win the click | rewrite title and description for the searches we now show for |
| Position flat after day 28 | authority or page type, not the page | the off-page list (Part 1 E); owner decides |
| Readers land and leave | the first screen misses the search promise | change the first screen only; measure again |
| Readers stay, nobody converts | the ask does not fit their stage | change the ask ladder (for example a self-check before the call) |
| Many use the interaction, few convert | it answers too much or leads nowhere | end it on the ask, with their answers carried to the next step |
| A sibling page takes the search | cannibalization | sharpen both pages, link the right one |

One change at a time, each logged with its date, so we can tell which change moved which number. A report to the owner
at day 14, 28 and 56: what moved, why, what next.

## Questions for the owner (typical first ones)

These go in the project's `docs/tasks.json`, not here.

- Which claims about the business are approved for money pages beyond `BRAND.md`?
- May a money page show real product screens or photos, and which?
- May the pages say anything about set-up time, or about who the first call is with?
