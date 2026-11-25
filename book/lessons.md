---
title: Lessons
version: 2.0.0
updated: 2026-11-18
license: CC BY 4.0
---

# Lessons: what went wrong, what it cost, and the guard

**Version 2.0.0 (generic edition) · 18 Nov 2026**

The mistakes teams made while growing real websites with an AI coding agent, what each one cost, and the guard that
stops it. They come from long runs of real work on several business websites and a large
multi-module app. Only lessons that apply to any website team are kept. Page names, tools, clients and people are left
out on purpose.

This file merges three sources and removes the repeats: the cross-project growth lessons (Part A), the publishing
lessons (Part B) and the short do's and don'ts (Part C).

- **Part A. Running the growth work.** Onboarding, choosing, building, measuring, and working with an agent.
- **Part B. Publishing lessons.** About 100 lessons in 13 themes, from facts to design process.
- **Part C. Do's and don'ts.** The short list.

Each lesson has two lines: **What went wrong** (and why), and **The guard**. A guard that says **you** has no automatic
check; the person or agent doing the work is the check. A guard that names a rule points to the
[page rulebook](03-page-rulebook.md). For the day-one checklist of a new project, see [foundation.md](foundation.md).

## How to use this file

- **Before a job,** read the parts that match your job. Search it: `grep -n -i "redirect" lessons.md`.
- **After a new mistake,** add a lesson here in the same change as its fix, with its date and what it cost, and add
  or change the rule in the rulebook. A mistake caught twice with no guard is a process failure.
- Where a small test would help, the lesson says "guard wanted". Adding one is a good next step.

---

# Part A. Running the growth work

Dates are when the owner gave the rule or the mistake was caught. "The owner" is the person who decides for the
business.

## A1. Onboarding: what each step needs that a checklist does not say

- **Helper agents cannot use the research browser** (24 Nov 2026). Claude in Chrome reached only the session where
  the owner typed `/chrome`; a research helper saw no browser at all, and the owner reconnected Chrome twice for
  nothing. Cost: half a research step lost and two owner round trips. Guard: the lead does every browser step (Google
  results, People Also Ask, AI answers) and saves each result to a file under `research/`; helpers work from those files.
- **Ask the primary market first** (17 Nov 2026). The first AI-answer checks ran from the wrong country. A re-run set
  to the real market gave a different answer: the product was named first with a full price table. Guard: record the
  market in `growth.json` before any search; Google with that market's `gl`, `hl` and `pws=0`; AI prompts name a place
  in the market (rule on "Primary market first").
- **Understand the site in ten minutes before asking the owner anything.** Fetch the home, about, pricing, robots,
  sitemap and llms.txt with a plain request (a 200 can be the site's own 404 page). From the HTML read the stack, the
  tracking ids, the booking tools, the schema types. From the sitemap read the page count, types, topics and pace.
- **Fill the config first, then the text.** Fill `growth.json`, then rewrite `SETUP.md`, `BRAND.md` and
  `OWNER-RULES.md`. A check greps the old-brand words left from a template; remove, do not adapt, any sample audit,
  old verify prompt or CMS tooling that came from another site. Respect "keep it as it is" calls from the owner.
- **Study the site repo end to end** before claiming to know it: every page type to its file, the exact publish path
  (branch, checks, approval, live), whether scheduled jobs really work (call their endpoints: one site's daily rebuild
  answered 503 for weeks), branches holding unshipped work, and who commits. Run the tests and the build; record the
  counts.
- **Analytics keys:** fetch setup steps with a plain command line client, never a web-fetch tool that might leak a
  one-time code; store keys once with a private file mode; test through a pipe so the token never shows on screen.
- **Prove control** with a one-character visible edit, only the checks it touches, the owner's look on the live page,
  then a revert on their word.
- **Inventory:** send a browser User-Agent for the sitemap (a CDN may block bare clients); build the site first so page
  elements are read; do not drop section headings inside `<header>` tags (a first version did, and reported "no H2s"
  on pages that had seven). Check that live rows equal the sitemap count.
- **Tracker backfill:** find Search Console's first stored day in three-month windows; look for dates or paths left
  from an old site (one overrode the config); give the tracker one portable start script and no start-up job.
- **Ask early how the owner means to publish** and learn their words. One owner said "production build" for the pages
  finished locally and "live" for the local preview. Never assume "live" means the public site; say which one.
- **Before asking the owner where a number came from, search the repo's git history** (`git log -S`): an "unknown"
  price was the site's own pricing page for four months.
- **Keep a session transcript out of the repo from the first commit.** It can hold a one-time code. Git-ignore the
  agent's transcript folder.
- **Archive every page live before you touch it** (from a real project, 17 Nov 2026: for talks and demos): the "before" can never be
  retaken (rule 36i).

## A2. Adapting a kit or a rulebook from another site

- **Never drop or soften an old rule without listing it** (17 Nov 2026). On one project the sticky call bar and the
  "+" link previews were dropped from the first rulebook as "not in our notes"; the owner caught both. Guard: run a
  rule-gap check as part of onboarding (every old rule: adopt, adapt or skip with a fit reason) and rule 161.
- **Before softening any rule, check why it existed.**
- **Engine files hold no project facts from day one** (from a real project, 17 Nov 2026: the engine will be open source). Project
  data (config, brand, journal, research, tracker database, steps log, keys) stays private.
- **Every claim already on the live site may be confirmed by the owner in one answer;** record it in `BRAND.md`.

## A3. Running the first money pages

- **An audit plus a quick wording pass is not the money-page job** (17 Nov 2026). The job is the full pipeline: a
  dossier of questions with 10 to 20 competitors read in full, a fact check, a concept for owner check-in 1, a real
  redesign in the site on a local URL, check-in 2, a CRO audit of the prototype, an independent review on a different
  model, a release alone, indexing, then measuring at day 7, 14, 28 and 56 (rule 0).
- **The owner wants to watch the work.** Run multi-step jobs as workflows where the tool supports them; workflow
  scripts take every path from arguments, so a new project reuses them unchanged and only the briefs carry project
  facts.
- **The micro-detail list the owner caught by eye on a first prototype** (all missed): a reason on every booking
  button; one bright CTA colour with a soft glow that pulses twice at moments of intent only; a sticky bar that
  replaces the menu and never flickers; a relevant exit offer; hints on every interactive control; link-blue
  in-text links with a "+" preview and a blue glow; a space before and after every link and the order words, "+",
  punctuation; circled ticks in one green; every fold with its own surface; pictures that read in 3 seconds (rules
  32a to 36l).
- **Plan at the level of the smallest detail before touching a page** (from a real project, 17 Nov 2026: "the AI needs to pay
  attention to the smallest details for each page element and each fold"). On a first money page the owner caught more
  than twenty small things by eye. None was hard; each was missed because nobody planned at that level. Guard: the
  fold plan (rule 36h): every fold and every shared element answers its detail fields before the build; the gate
  fails while a field is blank. Then build from the plan and check each line of it, not the page as a whole. Before
  showing anything, screenshot every fold at 1366 and 390 and read each one against its plan line.
- **Contrast in every state, automatically** (from a real project, 17 Nov 2026: "I should never speak about this again"). A footer
  button with dark text on orange went darker on hover. Guard: measure text against the colour actually painted behind
  it, at rest, hover and focus, in a real browser (rule 36j). Use paired tokens (fill and text-on-fill).
- **Clarity beats style** (from a real project, 17 Nov 2026, on a first bold chart: "very bold, hard to understand and too busy"):
  one idea per picture, few colours, line weight in proportion, detail only where the picture is large (rule 36g).
- **Choose the illustration style early, from a board** (from a real project, 17 Nov 2026: hand-coded art looked "very robotic").
  Show about eight options made with different techniques, all in the brand colours; a first board of four drawn from
  one skeleton was rejected ("all look the same"). Vary the technique, not the colour. Record the pick in `BRAND.md`,
  build one shared layered-SVG set, and never draw one-off art. A product object drawn on the site can carry the
  brand's name like a decal, built into the shared art component and tested.
- **Every About page shows the real people, linked.** An About page that named an invented founder persona was
  replaced with the real co-founders: photo, title, a few sourced lines, links to their public profiles, the parent
  company named, and `Organization.founder` as Person nodes with `sameAs`. Keep About a short company page with the
  founders in the first screen; product detail belongs on the money pages. People cards look like a set: same photo
  treatment, size, crop and card height.
- **One named author on every page** (from a real project, 17 Nov 2026: E-E-A-T). Pick the author with the owner on day one, build
  their page first, and give every page "Updated <date> by <Name>, <role>" linking there (rule 36l).
- **Where the owner says "never say where we are", ask before building** when a message about location reads two ways
  (rule 36k).
- **Internal links are part of every money page** (from a real project, 17 Nov 2026). A first money page was rebuilt with no inbound
  link plan and the owner caught it. Guard: a link map, a ranked list of pages that should link in, the top links
  shipped with the page, every other planned link filed in the journal against its source page (rules 88a, 88b).
- **The AI answers check is a "before" measure** (from a real project, 17 Nov 2026): two or three buyer prompts in ChatGPT (temporary
  chat) and two or three Google searches per money page, recorded as a baseline and re-run at day 28 and 56. On one
  page the assistant named the product first for a specific prompt but not for the generic "best plus pricing" prompt,
  and quoted a price the site never published; Google's AI overviews cited best-of guides and glossaries, not vendors.

## A4. Process and the agent

- **Rules are code** (from a real project, 17 Nov 2026: "any AI agent does not follow .md files fully and misses many things").
  Every workflow ends in a blocking gate (fix and re-run until zero FAIL), and git pre-commit hooks run the rule tests;
  an agent that skips a line in a .md file still cannot pass. Each project gets a rule registry, one gate script, a
  test that fails when a rule has no entry, and no loose words. Build this on day one.
- **No owner message unlogged** (from a real project, 17 Nov 2026): a script reads the session transcripts and fails on any owner
  message missing from the steps log. Run it before every report.
- **The golden rule: no URL before READY** (from a real project, 17 Nov 2026: "this cannot be broken"). A ready tool (full gate, 0
  FAIL, at the current commit) and a Stop hook that blocks any reply showing an unready local URL. Status goes in words
  until then.
- **Pre-flight before any page is built** (17 Nov 2026). Four pages were built first and checked at the end; the end
  became hours of repair (a 2,000-line shared stylesheet, an animation library, missing baselines, stale evidence) and
  the owner asked why. Guard: a pre-flight that scans the whole site for shared problems and fixes them first, requires
  every planning artefact (the AI baseline is a "before" measure by definition), writes the checkpoint list sorted by
  when each check runs; then the gate runs after every fold commit (rule 0a).
- **A rework removes what it replaced** (from a real project, 17 Nov 2026). Every redesign deletes the old components, CSS and tests
  in the same commit; a gate check fails when a file the branch touched is used by nothing (rule 124a).
- **A script that edits files must save and be checked** (18 Nov 2026). A Python edit replaced a line in memory and
  never wrote it; the tests passed because they tested the new helper, not the call. `tsc --noUnusedLocals` showed the
  helper "imported but never read". Guard: `repo.no-unused-code` on every page.
- **Records must match the work, and helper models are checked by code** (18 Nov 2026). An audit found 30 task steps
  shown open on five finished pages (the step tool re-added steps instead of ticking them) and a builder started on
  the lead's model instead of a mid model. Fix: a `tick` command that updates a step in place, a gate check that fails
  on a step left open behind done ones, and a Stop-hook guard on each helper's model. A promise to remember is not a
  fix; a check that blocks is.
- **Build each page on its own branch from the production branch, not stacked** (18 Nov 2026). Six pages stacked on
  each other meant one shared fix had to be rebased up the whole stack, every page above it lost its evidence, and
  moving the preview needed a re-check of all pages: about two hours of repeat screenshots and click-tests. Shared
  fixes go on their own branches first; a page branch holds only its page.
- **One preview address per project** (from a real project, 17 Nov 2026: "why a separate port for the same project?"). The owner
  gets one local link for everything. Helpers may use their own ports while working but never send them to the owner.
  Record the address in the project config.
- **One dev server per worktree; evidence checks its own assets first** (17 Nov 2026). A helper ran a second dev
  server in the worktree the preview served, then deleted the build folder in its cleanup. The preview kept running with
  empty chunk folders: four of five pages lost their CSS and scripts, and the first 24 evidence shots were unstyled.
  Guard: never a second dev server in the preview's worktree; never delete a build folder a server uses; before any
  shot or click-test, fetch the page's own script and stylesheet and stop on any non-200.
- **"Work overnight" needs a driver, not good intentions** (18 Nov 2026). The owner said "continue on your own, I'm
  taking a break". At 00:45 the lead was waiting on helper replies and a busy machine; nothing woke it again, and 11
  hours passed with no work. When the owner leaves the lead running: keep a queue of next pages that needs no owner
  input; never end a turn waiting on a helper without a background task or wake-up that will bring the lead back; if
  no such driver is allowed, say so before the owner leaves.
- **Helpers stall after a background run ends** (18 Nov 2026, twice in one afternoon). The lead keeps its own alarm (a
  wait on the helper's process, then on its journal entries) and nudges at once.
- **Shared scratch folders get wiped** (18 Nov 2026): a reviewer deleted `*.py` in the shared scratchpad and took
  another helper's scripts. Each helper uses `<scratchpad>/<name>/` and deletes only that.
- **"Fix the gap everywhere" stops at the owner's claims** (18 Nov 2026): reviewers called a line in 21 live posts
  unsupported, but the owner's rule counts the live site as true. Removing a claim site-wide is the owner's call; ask,
  with a default that changes nothing live.
- **A project must be able to move to another computer** (18 Nov 2026). Hooks, worktree links and package shortcuts
  named the laptop's own folders; keys and rules lived outside the project; copying 444 MB of packages over Wi-Fi took
  over an hour. Guard: paths relative to the project, a setup script that rebuilds packages, keys and notes and ends
  with checks, and a test run of the setup on a fresh user.

---

# Part B. Publishing lessons

These are the lessons from the content and page work itself, in 13 themes:

1. Facts, proof and claims
2. Words and voice
3. Design and layout
4. Phones and widths
5. Images and icons
6. Links and internal linking
7. SEO, structured data and sitemaps
8. Moves, redirects and lost pages
9. Builds, checks and testing
10. Release, safety and secrets
11. Agents and parallel work
12. Working with the owner
13. Design process

---

## 1. Facts, proof and claims

### 1.1 Old articles were full of wrong facts
**What went wrong.** An audit of a site's old articles flagged hundreds of claims: prices that had changed, plan names
that were renamed, limits quoted from memory, and rows from one product mixed into another's price table. The articles
were written once and never checked again.
**The guard.** Rules 5, 6. Check each price, plan name and limit on the official page on the
day you publish, and name the source in the pull request.

### 1.2 Made-up proof reached the site
**What went wrong.** Pages had a "how we tested" section with invented results, client stories with invented numbers, a
star rating column, quotes the cited page does not contain, and testimonials nobody could trace. Each one is a risk the
moment a reader or a buyer checks.
**The guard.** Rules 1, 2. Publish a result, quote, rating or story only with a real source you can
link, or with the owner's written yes. This has no automatic check: **you** are the check.

### 1.3 A fact was out of date the day after it was checked
**What went wrong.** A vendor changed a free-plan limit overnight. About forty-five places, FAQ answers included, still
carried the old figure, checked the day before.
**The guard.** Re-open the official page on publish day, even if the fact was checked last week, and write the check
date next to the fact (rule 7).

### 1.4 One change was fixed on some pages and not others
**What went wrong.** The owner changed a promise (a reply time). The contact and About pages were fixed. Five service
pages still had the old words nine days later, and the form's own reply message and the lead email still had other
promises. The first search covered only the shared strings, not every file.
**The guard.** After any wording change, search the whole repo (pages, posts, library files, JSON, form settings) for
the old words. Rule 3. Guard wanted: a test that fails on the old wording.

### 1.5 Our own facts read differently on different pages
**What went wrong.** The same client count appeared as "110 clients", "110+ teams" and "50+ teams". A parent company sat
in the client logo row. No file said where a number came from, so a reviewer flagged it.
**The guard.** One list of facts we state about ourselves, with the owner's yes next to each line (rule 3). A new
claim goes in that list first, then on a page.

### 1.6 A vendor's default price was copied
**What went wrong.** A pricing page opens set to a large team size. Six posts printed that size's price as the price.
For one to a hundred users the real price was higher.
**The guard.** Rule 7. Set the vendor's page to the size you write about, say the billing, and note the date.

### 1.7 Cost figures had no source
**What went wrong.** A set of cost pages gave figures with nothing behind them. Another page promised features of a
product that had not been confirmed.
**The guard.** Every figure has a source in the pull request, or the page says "quoted". A feature of our own product
goes on a page only after the owner or the product team confirms it (rules 1, 25).

### 1.8 Leftovers of another firm, and notes for the owner, nearly went live
**What went wrong.** Pages had another company's name, a misspelled brand, a "[Your Company Name]" placeholder, an
old email, and structured data pointing at a localhost address. Separately, notes for the owner written inside page
files would have shown on live pages.
**The guard.** Search a page for other companies' names and for `TODO`, `FIXME`, `[[`, lorem and `{{` before every
pull request (rule 11). Keep notes for the owner in the pull request, never in the page.

### 1.9 A page showed another article's body
**What went wrong.** Sixteen posts showed the body of a different article, one was in another language about another
product, and six titles named another article. A bulk edit had replaced the bodies.
**The guard.** Read the first two paragraphs against the title before you publish. After any bulk change, sample pages
from each group and compare title and body.

### 1.10 The same FAQ question was asked twice, and the markup lied
**What went wrong.** An FAQ asked the same thing in questions 2 and 9. Elsewhere the FAQ markup listed questions the
page did not show, two FAQ blocks sat on one page, and answers differed only by curly quotes.
**The guard.** Rule 96. Read the FAQ as one block. Change the visible text and the markup in the same edit.

### 1.11 A comparison said "no bias" while we were a partner
**What went wrong.** A comparison claimed no affiliations, though the company was a certified partner of one tool in
it. A review overclaimed ("wins in every meaningful way") with the disclosure at the bottom.
**The guard.** Rule 16. Say who we are in one line under the byline, be fair, and show where the other tool wins.

### 1.12 Titles had the wrong year, count or brand
**What went wrong.** Four titles still said last year. "Top 10" listed seven tools. An H1 had the wrong count.
**The guard.** When a page changes, recount its items and re-read the year in the title, the H1 and the meta title.

### 1.13 The check was wrong, not the site
**What went wrong.** On a sister project, tests were built from our assumptions, so they agreed with our code and not
with reality. A real run found seventy wrong values. A contrast alarm was the test's own mistake: it switched theme
with the answers closed, and the browser does not restyle closed answers.
**The guard.** Test against real observations or cited documents. Before you call a bug, reproduce it the way a visitor
would (fresh page, real browser). Point to the output that proves a claim before you say "done" (rule 105).

---

## 2. Words and voice

### 2.1 Old text was kept with its faults
**What went wrong.** A move kept the old text "as is", so a crawl showed hundreds of misspellings and weak titles. The
instruction to keep the facts and the URLs was read as "do not fix the words".
**The guard.** Keep old facts, values and URLs; fix spelling and SEO text to the site's standard (rules 93, 121).

### 2.2 The About page read as buzzwords
**What went wrong.** An About page said "creators, problem-solvers... revolutionize". The owner could not trust it. It
was an old text, only restyled.
**The guard.** Rule 29. Say who we are, what we have done and why to trust us, with facts from `BRAND.md`.

### 2.3 Messages a visitor sees were not read
**What went wrong.** A form answered "Data stored successfully". A lead email ended with a technical line naming a
config setting. Both were read only by a developer.
**The guard.** Read every form answer, thank-you text, error and email the way a visitor would. Remove anything technical.

### 2.4 A contact route went on the site without a yes
**What went wrong.** A personal link and a direct email were listed as possible site additions. The owner had decided
where each channel lives.
**The guard.** Use only the contact routes the owner has approved for the site (rule 32). A booking link points to the
one booking page and the one call length (rule 4); an old link had pointed to a 45-minute meeting.

### 2.5 Business questions went unanswered
**What went wrong.** About and Contact did not say how pricing works, whether an NDA is signed, or how estimates are made.
Buyers ask these first.
**The guard.** Rule 15. When you touch About, Contact or a money page, check it answers those questions with
approved facts only.

### 2.6 Headlines led with the method, not the result
**What went wrong.** Headlines named the technology. The owner's rule: promise the result, and mention the method only as
how it is done.
**The guard.** Write the headline as the outcome the reader wants; the method comes second.

### 2.7 All-capital text and a recycled template voice
**What went wrong.** Headings in full capitals were hard to read. Copy came from a template and read like one.
**The guard.** Add no new all-capital text. Read the page aloud once; cut any sentence that could sit on any site.

---

## 3. Design and layout

### 3.1 Parts of a page stopped short of the right edge
**What went wrong.** The cover and takeaways stopped short of the edge that lower blocks reached. Later, whole posts ended
far short of the header's right edge and side notes hung past it. The check measured only the text, not the whole frame.
**The guard.** Rule 44, 43. Measure every block, the header, the author box and the footer, at several
widths, after any layout change.

### 3.2 Going Home moved the logo
**What went wrong.** Clicking Home from an article moved the logo and menu. The margin lived in the article styles, so
other pages built the shell another way.
**The guard.** Define the shell once. After a layout change, click Home from three page types and check nothing moves
(rules 43, 107).

### 3.3 A wide block inside a wide block ran off the screen
**What went wrong.** Before/after cards inside a case box broke out twice and passed the screen.
**The guard.** A nested wide block never grows again. Sweep widths before every commit (rules 44, 68).

### 3.4 Cards in a row left an empty slot
**What went wrong.** Two cards sat on the left with an empty slot beside them: a three-column grid for two items.
**The guard.** Rule 46.

### 3.5 A money page looked like a blog post, and half of it was empty
**What went wrong.** Service pages used the article template, so they had a narrow column and looked like posts. On one
page the hero's right half was empty, an animation was stretched under the text, client logos were tiny specks and
excerpts were cut with "...".
**The guard.** Pick the page's frame first (rule 49). Look at the whole first screen at 1440 before you hand it
over (rule 39).

### 3.6 The contact page wasted space and fixes were too big
**What went wrong.** A tall booking box and a big empty block under the form. The first fix was too tight, then too loose,
because spacing was changed by eye in big steps.
**The guard.** Rule 38. Change spacing in small steps and report the before and after in pixels.

### 3.7 Every fold looked the same
**What went wrong.** A page was "boxes over boxes over boxes". Every section used the same card component.
**The guard.** Rule 30. List the page's folds; no two may share a layout.

### 3.8 An effect made text unreadable
**What went wrong.** A see-through "glass" panel made the page text bend behind the card, and the cards became hard to
read. It was shipped everywhere before readability was checked.
**The guard.** Rule 59. Show a new effect on one sample first; readable text wins.

### 3.9 Dark on dark, grey that failed contrast
**What went wrong.** A dark letter on a purple tile, dark logos nearly vanishing in dark mode, and a grey label at 4.46:1
against a 4.5 limit. The contrast check read text only, not logos or artwork.
**The guard.** Rule 59. Check every colour change in every theme, artwork and logos included.

### 3.10 Sticky parts covered buttons
**What went wrong.** A row of sticky chips covered the call-to-action card. A popover covered a form demo.
**The guard.** Rules 47, 35. Scroll the whole page once on desktop and on a phone; nothing sticky may cover
a button.

### 3.11 Text was cut or clipped
**What went wrong.** Excerpts and bios were cut with "..." in the middle of a sentence. A tab row showed "Permissio" at
desktop width because it scrolled instead of wrapping.
**The guard.** Cut text on a full sentence. Check tabbed pages at 1280, 1512 and 1920 after a content change.

### 3.12 Interactive parts did nothing when clicked
**What went wrong.** Filter buttons on a page did nothing, and one part ran off the page. It was shown without being used.
**The guard.** Click every button, tab and filter in a real browser before you show a page (rule 106).

### 3.13 Numbers were hard to compare
**What went wrong.** Number columns were left-aligned.
**The guard.** Rule 48. Money, percentages, counts and durations align right.

### 3.14 A big redesign leaked onto every page
**What went wrong.** Work in progress for a redesign leaked onto every page and deleted a call-to-action button. The owner
also found a page "boring" and asked how a fix would reach many pages.
**The guard.** Rules 120, 52. Backup tag, one real page behind a switch, a shared component, then a roll-out on
the owner's yes.

---

## 4. Phones and widths

### 4.1 Pages were wider than a phone
**What went wrong.** Long button text, a line set to never wrap, a fixed-size logo tile and tilted notes before they
settled each made a page wider than the screen (360 to 485px on a 360 to 390px phone). Only the settled page had been
measured.
**The guard.** Rule 68. A new "never wrap" rule needs a phone check. Use `minmax(0, 1fr)` in one-column grids.
Merge `main` into your branch before you measure, so you do not test an old fix. Guard wanted: an overflow test at four widths.

### 4.2 Small things broke at 390 wide
**What went wrong.** A meta row ended with a separator and the breadcrumb began with "/". Screen-reader-only labels
escaped a table's scroll box and pushed the page to 485px. An image sat on top of text. A side note covered another box.
**The guard.** Rules 72, 69, 48. Look at the top of a post and every changed page at 360 and 390.

### 4.3 "Desktop only" was a mix-up
**What went wrong.** A note meant for an internal desktop app was read as applying to the public site.
**The guard.** Every public page works on phones and tablets (rule 68).

---

## 5. Images and icons

### 5.1 Alt text was empty on thousands of images
**What went wrong.** A crawl found thousands of images with empty alt: badges, card covers, list pictures. A picture that
is a link's only content, or wide, counts as content.
**The guard.** Rule 62. Give every content image a real description. Decorative images are marked decorative.

### 5.2 Images were heavy, misnamed or late
**What went wrong.** Hundreds of pictures were over 200 KiB. A photo was served as `name.png.png`, and renaming it touched
hundreds of pages. Thumbnails in a first section were lazy-loaded. A shared icon file saved three KB and made Lighthouse
worse.
**The guard.** Rules 63, 64, 66. Measure with Lighthouse before and after a speed change, and keep
it only if it is better.

### 5.3 Files were removed or left behind
**What went wrong.** A removed favicon was still linked on every page. A merged page's cover still shipped, named by
nothing. An untracked logo folder inside `public/` would have been served live.
**The guard.** Before you delete a file in `public/`, search for its name. When a page goes, its cover goes too. Never park
scratch files in `public/`; everything in it ships. `git status` before every commit.

### 5.4 "Done" images were never looked at as the site shows them
**What went wrong.** We said the images were done after looking at the source files, not at the built pages. Pictures
were blurry or looked fake, and some cards had no reason to be there.
**The guard.** Review images on the built pages themselves, every page, at full size. A card that sells needs its own
next step.

### 5.5 Logo tiles and emoji
**What went wrong.** Comparison pages used letter tiles in coloured squares as a stopgap for logos, and hand-drawn icons
or emoji elsewhere.
**The guard.** Rule 57. Use the product's own logo from its own site; if there is none, show its name as text.

### 5.6 Share images broke in previews
**What went wrong.** A page showed a broken picture when shared. The tag pointed at a file not in the build. Later, loaders
and sprites were found used as share images.
**The guard.** Rules 65, 108.

---

## 6. Links and internal linking

### 6.1 Internal links had marketing markup
**What went wrong.** Seventy-nine internal links carried `nofollow` and opened a new tab. An exit pop-up's internal link
carried UTM tags on hundreds of pages. A first fix also stripped the button style from five buttons.
**The guard.** Rule 34. Internal links are plain links. After a link edit, check buttons still look like buttons.

### 6.2 Placeholder and empty links
**What went wrong.** A link card's "Read" link had no `href` on hundreds of pages, and a later fix set `href="about:blank"`.
A crawler resolves that against the page and asks for addresses that do not exist.
**The guard.** Rule 92. An element that is not yet a link is a span until it has an address.

### 6.3 Vague or double-meaning link text
**What went wrong.** Hundreds of links read "Read" or "Source". A bare URL was link text. One "Ask your question" went to
four different pages.
**The guard.** Rule 90. One link text, one target; say what the reader gets.

### 6.4 New links to addresses that do not exist
**What went wrong.** A link was typed from memory to an address that was not live. In-page links broke when heading ids
changed. A booking link went to the wrong call length.
**The guard.** Copy addresses from the built site or the sitemap, never from memory. After you change a heading, search for
links to its old `#id` (rule 85).

### 6.5 Pages nobody linked to
**What went wrong.** Several list pages had only one link in the content, because pager links count as navigation. New
pages linked to old ones, but old pages never learned about new ones.
**The guard.** Rules 88, 89. A new page joins its group, links up and across, and gets links back.

### 6.6 Too many followed links to other sites
**What went wrong.** Every outside link was followed, copied from old markup.
**The guard.** Rule 91. Name the source in the text; mark sponsored links as sponsored.

---

## 7. SEO, structured data and sitemaps

### 7.1 Titles and descriptions were cut
**What went wrong.** Dozens of titles were over 60 characters; descriptions were cut mid-sentence, and old share
descriptions linked to dead addresses.
**The guard.** Rule 81. Whole sentences, within the limits.

### 7.2 Fake headings and skipped levels
**What went wrong.** Over a hundred findings: paragraphs styled as headings, skipped levels, a figure drawn big that read
as a heading to a crawler, a page with two H1s.
**The guard.** Rule 84.

### 7.3 List pages copied each other
**What went wrong.** Author lists duplicated the blog's. Category lists were 85 to 93 percent the same as the blog. Page 2
and up of a list reused page 1's H1 and title, and were in the sitemaps.
**The guard.** Rules 86, 87. A list page has its own intro, title and H1, or points its canonical at the
list it copies.

### 7.4 What Google indexes was incomplete
**What went wrong.** Hubs, categories and the blog index had no main picture; list pages had no title of their own.
**The guard.** Rule 83.

### 7.5 Structured data copied from another tool
**What went wrong.** An old plugin's stored markup named an admin login as a Person, used avatar and localhost
addresses, gave an article node to pages that are not articles, had no dates on dozens of pages, and kept old
addresses after a page moved. FAQ markup said things the page did not.
**The guard.** Rules 95, 97, 96, 12. Never paste structured data from another tool; let the
build write it, and re-check it after a move.

### 7.6 A sitemap linked things that were gone
**What went wrong.** A page type left the XML sitemap, but the HTML sitemap still linked its file (a 404). A sitemap held
redirects and noindex pages.
**The guard.** One list builds both sitemaps. When a page type leaves a sitemap, check every place that lists it (rule 87).

### 7.7 The crawl was not the production build
**What went wrong.** A crawl on another host showed problems production did not have, and production problems the crawl
did not show. Speed tests ran without analytics, so they hid its cost.
**The guard.** State in every report which build and host a number came from, and whether analytics were loaded (rule 103).

### 7.8 A "done" report ignored the crawler
**What went wrong.** We were about to report done while the crawler still showed warnings. We had checked our own tests,
not the crawler's view.
**The guard.** Before "done", look at a crawl of the build. Report a false alarm to the tool; do not ignore it.

### 7.9 A side effect nobody asked for
**What went wrong.** A site-wide change added FAQ markup to seven pages that never had it.
**The guard.** Report every page a change touches beyond the one you meant (rule 110).

### 7.10 Private or tool paths could be indexed
**What went wrong.** The owner asked how editor and preview paths are kept out of Google. Nothing was written down.
**The guard.** A preview or tool host gets noindex headers before it is reachable. Write the answer in the rulebook.

---

## 8. Moves, redirects and lost pages

### 8.1 A move left a 404
**What went wrong.** Moving a post to another topic wrote no redirect. A rename left the topic list and the checks
pointing at the old name. A merge left the merged posts in the topic lists.
**The guard.** Rule 75. A move or rename adds its 301 in the same commit and updates every file that names the page.
Open the old address and see it redirect.

### 8.2 Redirects chained
**What went wrong.** An old address went to an old hub that then redirected again.
**The guard.** A redirect points at the final page. A merge keeps every old form of the address, in one hop.

### 8.3 Old addresses people and crawlers still ask for
**What went wrong.** Short addresses such as `/about/` gave a 404, and old review, price and author pages were lost.
Real crawlers asked for them every day.
**The guard.** Rule 77. Read the 404s you can see weekly and redirect each one to its closest page. Guard wanted.

### 8.4 Duplicate pages competed
**What went wrong.** Twenty groups of near-duplicate pages answered the same question.
**The guard.** Rule 19. Before a new page, check that none answers the same question.

### 8.5 A list page past the last one gave a 404
**What went wrong.** After posts left a list, a page number past the end was a 404.
**The guard.** Send it to page 1 (rule 77).

### 8.6 Move only what is needed
**What went wrong.** An import copied junk. The owner warned against it.
**The guard.** When importing, take only what a page uses.

---

## 9. Builds, checks and testing

### 9.1 A check passed when pages failed
**What went wrong.** A comparison tool exited 0 although URLs failed, and a lint section only printed. A matcher bug
inserted text between every letter of a page.
**The guard.** A new check must fail, not just print. Run a bulk-change tool on one page first (rule 110).

### 9.2 The tree under test was not the commit
**What went wrong.** An agent reported a false 404 and a big jump in differences because another agent's unfinished
edits sat in the shared tree. An unfinished file made three checks fail.
**The guard.** Verify on a clean checkout of the commit, never on a shared tree. Use `git status` before every commit.

### 9.3 Counts came from the source, not the build
**What went wrong.** Agents not allowed to build reported link counts from source files. The last build was older.
**The guard.** Say whether a number comes from the source or from the build, and from which commit.

### 9.4 A failing test was called "flaky"
**What went wrong.** One "flake" was a real race, found on run 17 of a loop. Real flakes came from a machine under heavy
load, port clashes and stale temp folders.
**The guard.** Re-run a failing test in a loop before you call it a flake, and note the machine load. Run browser checks
one at a time and close every browser.

### 9.5 Test folders filled the disk
**What went wrong.** Dozens of leftover test copies filled the temp disk. Three checks failed with "disk quota exceeded",
which looked like a code error.
**The guard.** Rule 112.

### 9.6 Two builds of one commit differed
**What went wrong.** Ids made with a random number changed every build, so output was never the same twice.
**The guard.** Rule 102.

### 9.7 Scroll on load stopped the speed score
**What went wrong.** A contents list scrolled itself on load. The browser then recorded no Largest Contentful Paint
(the time the main content shows), and the speed audit had no score.
**The guard.** Rule 67.

### 9.8 A test on the wrong host
**What went wrong.** A "404 for old uploads" finding was tested on the wrong host. The uploads had always lived elsewhere.
**The guard.** Before you report a bug, confirm the address the real visitor uses.

### 9.9 A long job finished and nobody noticed
**What went wrong.** A "tell me when done" watcher missed the end, and the agent sat idle. Another waited for a notice
instead of checking its job. After a ship script, the script's last line said "shipped" when nothing had shipped.
**The guard.** Check a long job's output yourself at a set time. After a release, read the live page and the live
commit, not the script's last line (rule 127).

### 9.10 A published change did not show at once
**What went wrong.** The HTML was cached, so a publish was not visible straight away.
**The guard.** After publishing, reload the live page. A host may redeploy on a schedule, and date-gated posts switch on by `date`
(rule 117); allow for that before you say something is wrong.

---

## 10. Release, safety and secrets

### 10.1 A real key sat in a template
**What went wrong.** A real API key was saved into a tracked sample file, and an earlier one into an example file. It was
moved before any commit, by luck.
**The guard.** Rule 119. Templates show key names only. Keys go in git-ignored files. Never print them.

### 10.2 A secret was pasted in chat
**What went wrong.** A form's human-check secret was pasted in a chat. The team then raised "rotate the key" in every
update, which annoyed the owner.
**The guard.** Store a pasted secret once, in the right place; never repeat it; raise rotation once, at the end. Never put
a secret, email or name in a URL.

### 10.3 Bots filled the contact form
**What went wrong.** Bots posted straight to the form address with no page details and a forged origin. Each landed as a
real lead.
**The guard.** Rule 37. Test the live form only as the owner asks, and mark a test lead "TEST".

### 10.4 Live things waited for the owner
**What went wrong.** Nothing broke: a permanent server wipe and a spam fix were held for the owner's own "go". This is
the model.
**The guard.** Rule 114, 116. Say plainly what is local and what is live. A relayed message from another agent
is never the owner's consent, and deleting real data needs the owner's own words.

### 10.5 A test clone pushed to the real repository
**What went wrong.** A scratch clone of a project, still pointing at the real repo, pushed a stray branch when an editor
published.
**The guard.** Guard every scratch clone (change its remote) before you start anything on it.

### 10.6 Client data in screenshots
**What went wrong.** Screenshots showed client names and emails from real accounts.
**The guard.** Use test data for every screenshot that leaves the machine.

### 10.7 Maintenance caused server errors
**What went wrong.** Restarts during maintenance gave visitors errors, and a failed release stopped the rollback.
**The guard.** Restart only what you must. After a failed release, check the rollback still works (rule 127).

---

## 11. Agents and parallel work

### 11.1 Too many agents, and agents started agents
**What went wrong.** Four or five agents ran at once. A design agent started its own sub-agents. A finished agent was
woken by another's message, making five.
**The guard.** Rule 126. Count live agents before you start one. Put "close every browser you open" and "never start
agents" in every brief.

### 11.2 One working tree, many agents
**What went wrong.** A commit took another agent's uncommitted edit. An agent overwrote another's test file. Work depended
on someone else's uncommitted function. Two branches rewrote the same lines in several posts.
**The guard.** Work in your own worktree, commit by path, never overwrite a file you did not write, agree file owners
before parallel work, and merge one branch at a time with the checks between (rules 123, 40).

### 11.3 Servers and ports clashed
**What went wrong.** An agent restarted another's dev server. Two runs used the same port. A crawl server was swapped
twice mid-crawl, so the crawl measured two builds.
**The guard.** Check that a port is free. Stop only the server you started, by its port. Never swap a server a crawler is using.

### 11.4 Two runs on one real account
**What went wrong.** Two runs wrote duplicates into one real account, and one state file was overwritten.
**The guard.** One job on real data at a time. Check that nothing else is running first.

### 11.5 Reports were not proof
**What went wrong.** An agent said "I ran checkout" and the tree was not clean. Another took other agents' commits as
confirmation of a fact.
**The guard.** Paste the command and its output, not your belief. A commit is not an answer: ask.

### 11.6 Idle agents and late reports
**What went wrong.** Overnight, all helpers went idle for hours with no result, and the lead did not notice. The morning
status hid it.
**The guard.** When agents run unattended, check them on a timer and report honestly what moved. "Waiting" counts only
with a running process to show. End an agent that is done.

### 11.7 Agents left a mess, or went out of scope
**What went wrong.** Many branches and copies of the code, test projects and tried tools left in the owner's folder. An
audit agent wrote a stray file outside its scope.
**The guard.** Rules 123, 125. Work on a short branch, merge it, delete it. Write only where the brief says.
Remove anything you tried and dropped.

### 11.8 Permission prompts for the owner
**What went wrong.** Commands such as `rm -rf` on a relative path after `cd` made the owner approve prompts again and again.
**The guard.** Rule 125. Absolute paths, `git -C`, no `rm -rf` with globs or variables, scratch work in the
scratchpad.

---

## 12. Working with the owner

### 12.1 Answers did not answer
**What went wrong.** Answers mixed topics and pointed at file paths. A status ended with an unrelated reminder, which
made the owner feel more lost. Lists of eighteen items came in one message.
**The guard.** Rule 129. The first line answers the question; give a URL, not a file path. One topic per
update. Explain each technical word the first time.

### 12.2 The URL was not ready
**What went wrong.** The owner was told to look at a local address before its server was running. Another address was
given without its trailing slash and showed a 404. A preview was shared while it still showed "404 Not Found".
**The guard.** Rule 111. Load the exact URL you are about to send and see the page render.

### 12.3 Too many screenshots, too many questions
**What went wrong.** Every small update came with screenshot paths. The owner also had to answer things already
approved.
**The guard.** Rule 116. Screenshots only for a sample the owner must approve, or when asked. Ask only about
production, real data, money and design choices the rules do not settle.

### 12.4 Asks were lost
**What went wrong.** After a day of many parallel threads the owner could not tell what to review or approve. One image
request was dropped while an unrelated question was answered.
**The guard.** Write each owner request into one written list the moment it arrives, and close it there when done.

### 12.5 A cheaper subset was offered
**What went wrong.** We suggested translating only a few key pages first, to save work.
**The guard.** Offer "now or later", never "smaller", unless the owner asks for a smaller job.

### 12.6 Access was missing late
**What went wrong.** We asked the owner for things we could have found, and said only late in a server job which access
was missing.
**The guard.** At the start of any job, check the access it needs and list what is missing in one message (rule 130).

### 12.7 The owner reviewed batches
**What went wrong.** Page batches were sent to the owner for review.
**The guard.** Rule 109. The lead checks every page; the owner sees one clear signal when it is all ready.

---

## 13. Design process

### 13.1 We built before showing options
**What went wrong.** The owner asked for mockups, and we started building pages.
**The guard.** For a new design, show options and wait for the pick.

### 13.2 Every option looked like the same template
**What went wrong.** Every option was the same SaaS layout with new colours. We admitted we started from the same
template each time.
**The guard.** Start each design from the reader and the business, not from a stock layout. Look at a few references
first.

### 13.3 Hero, folds and animations repeated across pages
**What went wrong.** Three pages got the same hero. Two guides used the same blocks and motion. We changed the picture and
kept the layout.
**The guard.** Compare sibling pages side by side before you show any of them (rule 30).

### 13.4 New pages lost the original's depth
**What went wrong.** New pages lost facts, logos and icons the original had, and lost features already agreed.
**The guard.** Keep the original page open and tick off every fact, picture and feature. A new cluster starts with
research (rule 27).

### 13.5 Screenshots and docs went stale
**What went wrong.** Marketing pages showed old screenshots after the product changed.
**The guard.** When the product changes, update its pictures and pages in the same round.

---

---

# Part C. Do's and don'ts

The short list. Each line names the rule in the [page rulebook](03-page-rulebook.md) (the number) it comes from.
When you are unsure, the rulebook wins; then fix this page. A **(guard wanted)** mark means a small test would be a
good next step.

## Facts and claims

| Do | Don't |
| --- | --- |
| Check every number, price, plan, rule and feature on the official page, today, and cite it on the page (rules 5, 6). | Copy a fact from another blog, from memory, or from an older post of ours. |
| Say the business's own facts in the one wording of `BRAND.md` (rules 3, 4). | Write a number, a plan name, a guarantee or a customer that is not in `BRAND.md` (rules 1, 2). |
| Say what a process does, in the words the site already uses. | Promise a result ("saves X percent") the owner has not approved (rule 1). |
| Ask the owner when a page contradicts itself, or when a fact about the business is not in the list (rule 9). | Pick one of two figures yourself. |
| Write "we check this on the call" where the official source is silent (rule 5). | Fill the gap with a guess. |
| Quote a price for the reader's size, with the billing, the currency and the date you checked (rule 7). | Copy the first price a vendor's page shows. |
| Keep takeaways and side boxes to numbers the article itself states (rule 10). | Put a new number only in a box. |
| Say who you are when you review or compare, and give the other side a fair "when to stay" (rule 16). | Count one strength as several wins. |

## Words and voice

| Do | Don't |
| --- | --- |
| Use one spelling on the whole site (rule 93). | Mix spellings on one page, or add a misspelling to an allowed list to pass a check. |
| Keep the title at 30 to 60 characters and the description at 120 to 155 (rule 81). | Change the title, H1, URL or description of a live page without the owner (rule 74). |
| Use the one length for the call and the project's one CTA label (rules 4, 32a). | Write another length, or a banned word, for the first step. |
| Answer the reader's question in the first screen (rule 18). | Open with a cover picture and a pitch. |
| Write each page in plain, short sentences with real facts (rule 29). | Use buzzwords ("revolutionize", "solutions") instead of proof. |
| Search for leftovers before every pull request (rule 11). | Ship `TODO`, lorem, `{{field}}`, other firms' names or an old year. |

## Changing content

| Do | Don't |
| --- | --- |
| Edit content on a branch, and list in the pull request what changed, why and the source (rules 17, 114). | Edit on the production branch, or change text with no record of why. |
| Keep the front matter valid; fix the content when the build fails (rule 100). | Suppress a front matter error to get the build through. |
| Move `updated` when a fact on the page changes (rule 12). | Make up a date, or leave an old date on a changed page. |
| Write the FAQ answer once in the page and keep the FAQ markup equal to it (rule 96). | Change the visible FAQ and leave the markup, or the reverse. |
| Keep a URL. If one must move, send one 301 straight to the new address and update every file that names it (rule 75). | Delete or rename a page with no redirect, or rename a slug (rule 73). |
| Read content only through the one content module (rule 104). | Read content files from anywhere else. |
| Commit by path, with one plain sentence and the co-author line (rule 123). | `git add -A`, a bare `git stash`, or a commit under the wrong email (rule 118). |
| Add original artwork with every new article (rule 61). | Reuse another article's cover, use a stock photo, or draw the title into the picture. |

## Links

| Do | Don't |
| --- | --- |
| Link to the final address (rule 75). | Link to an address that redirects, or to an old host (rule 78). |
| Link a new post up to its hub and across to two or three siblings, and link to it from them (rules 88, 89). | Leave a page that no other page links to. |
| Link out only to official sources, and say which source in the link text (rules 91, 90). | Write "Source" or "click here". |
| Send every call to action to the one conversion path (rule 32). | Paste a raw booking link into a card or a second form. |
| Name a call to action by where it sits (rule 34). | Put `utm_` on an internal link. |
| Give every link a real `href` (rule 92). | Use `about:blank` or an empty `href` as a placeholder. |

## Pages and design

| Do | Don't |
| --- | --- |
| Look at the built page at 360, 390, 820, 1280 and 1920 wide before you hand it over (rules 106, 68). | Tell the owner to look before the page renders (rule 111). |
| Click the logo from a scrolled page and check you land at the top (rule 107; guard wanted if there is no browser test yet). | Put JSON-LD as the page's first child in a Next.js site (rule 98). |
| Use the shared components and tokens (rules 41, 52). | Build a one-off component for one page. |
| Keep the logo lockup as approved (rule 42). | Redraw, recolour or crop it. |
| Test a new design on one real page first, behind a backup tag (rule 120). | Roll a new design out to every page at once. |
| Give every image alt text and a real size (rules 62, 63). | Leave an image without alt, or serve one over about 200 KiB. |
| Check contrast in every theme the site has (rule 59). | Put dark text on a dark ground. |
| Stay in your lane in the repo (rule 40). | Rewrite files another agent may be working in. |

## Release and safety

| Do | Don't |
| --- | --- |
| Work on a branch, open a pull request, wait for the owner's explicit yes, then merge (rule 114). | Push to the production branch, or merge your own pull request without that yes. |
| Run only the checks the change touches (`growth checks`) before every pull request (rule 105). | Say "done" while a check fails. |
| Merge only into a clean, current production branch, and know the undo (rules 115, 127). | Run a manual deploy, or deploy a stale copy. |
| Keep real keys in git-ignored files (rule 119). | Paste a key into a template, a commit, a message or a log. |
| Check one live page with one request after a merge. | Crawl the live site from your laptop. |
| Ask the owner about DNS, hosting settings, money, accounts, deleting data and design direction (rule 116). | Read a standing yes as covering those. |
| Keep to the agent cap, each closing its browsers and ending when it is done (rule 126). | Let an agent start more agents. |
| Remove temp folders and test results when you finish (rule 112). | Leave scratch files in the repo. |

## Change log

| Date | Version | What changed |
| --- | --- | --- |
| 2026-11-18 | 2.0.0 | Merged the cross-project growth lessons, the publishing lessons and the do's and don'ts into one file, with repeats removed and every project name taken out. |
