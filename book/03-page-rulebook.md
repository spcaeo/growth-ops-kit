---
title: The page rulebook
version: 2.4.2
updated: 2026-11-19
license: CC BY 4.0
---

# The page rulebook

**Version 2.4.2 (generic edition) · 19 Nov 2026.**

The standing rules for creating, changing and publishing any page of a website. Most of them started as a correction
an owner made after a real mistake. Each rule says why it exists.

The rule numbers and the `[code: ...]` tags are the same as in the kit's rules registry (`kit/rules/registry.json`).
Never renumber a rule. A test in the kit fails when a rule here and the registry disagree.

Facts about one business never appear here. They come from the project: the one CTA label, the words to avoid, the
author and the proof allowed are in `BRAND.md`; the market, site address and settings are in `growth.json`. The
examples use one made-up business: **Brightline Lawn Care** (https://brightline.example), a lawn-care service
company. Its one CTA is "Get a quote".

## How to use

- **Rule 0. No shortcuts:** every step of the job's playbook, in order, with every owner check-in ([02-owner-rules.md](02-owner-rules.md) section 1; the order of work is [01-flow.md](01-flow.md)). [code: ev.task-steps, proc.tasks, ev.brief]
- **Rule 0a. Pre-flight before the build** (from a real project: "when you start a new page the planning and preparation should be done in depth and all checkpoints clear set as part of that playbook and workflow"). Before the first line of page code, `growth preflight <path> --type ... --key ...` must say PASS. Shared site problems that would fail every page (files over 1,000 lines, raw colour codes, animation libraries) are fixed first, on their own. The planning evidence must exist: inventory, snapshot, dossier, generated brief, task steps, fold plan, link plan, AI baseline, archive. And `research/<key>-checkpoints.md` lists every check by when it runs. The gate then runs after every fold commit, so nothing is left for the end. [code: ev.preflight]
- **Read order.** Read `SETUP.md` (the stack, how publishing works, the analytics) and `BRAND.md` (who the business is, the one CTA, pricing words, proof, what is never claimed) first. This file holds the rules for putting those facts on a page. If they disagree on a fact, `BRAND.md` or `SETUP.md` wins. If they disagree on how a page is built, this file wins. Then fix the other one.
- **Rules are code** (from a real project: "py runs become rules"). Every rule ends with its tag. `[code: <check>]` means `growth gate` decides it. `[judgment: proxy <check>]` means a person decides it and the gate checks that the evidence exists (fresh screenshots, a journal entry, a research file). A page ships only when `growth gate page <path> --url <local URL> --repo <worktree> --type <money|hub|post|core>` shows no FAIL.
- **Run the checklist below for every page** you create, change or publish. The numbers point to the rules after it.
- **Stack.** Rules marked "(Next.js adapter)" read the site's code and run only when `growth.json` has `"stack": "nextjs"`. On any other stack the gate prints "SKIP: no adapter for <stack>" and the rule is checked by hand. All other rules read the live page and apply to any site.
- **Rules from one owner are defaults.** A project owner can change any of them in the project's own `OWNER-RULES.md`. Where a rule needs an owner decision, it goes to the open questions in `docs/tasks.json`.
- **Keep it current.** When the owner corrects something, or a new kind of page, check or rule appears, change the rule in its one home, bump the version (MAJOR: a rule reversed; MINOR: a rule added; PATCH: wording) and add a change-log row.
- **Words.** A "money page" is a page meant to bring a buyer to the one conversion (home, pricing, a service page). An "article" is a blog post. A "hub" is a page that maps a group of related pages. A "canonical" is the one address you tell search engines is the real one for a page. "Indexable" means search engines may list it. A "fold" is one section of a page, about one screen tall.

## Per-page checklist

Tick every line for every page you create, change or publish.

**1. Before you start**
- [ ] Read the page as it is now, live and on a local build. Know which file renders it.
- [ ] Write down the reader's question for this page in one line (rule 18). Is there already a page that answers it (rule 19)?
- [ ] Is the page true today? Check its core claims against official sources before you redesign or promote it (rules 5, 6).
- [ ] Redesign or bulk change: backup tag first, test it on one real page, roll out only on the owner's yes (rule 120).
- [ ] Same words: a design change must not change the wording unless the owner approved it (rule 121).

**2. Claims and offers**
- [ ] No invented number, customer, award, price or guarantee (rules 1, 2).
- [ ] Every self-claim matches `BRAND.md` (rules 3, 4).
- [ ] Every fact about another product or a rule cites its official source and date (rules 5, 7).
- [ ] The first screen answers the question before any pitch; the offer fits the reader (rules 18, 22, 23).
- [ ] If you review or compare, you say who you are first (rule 16).
- [ ] No placeholder text or leftovers (rule 11).

**3. Layout, components and design**
- [ ] The shared components and tokens are used; the logo lockup is untouched (rules 41, 42, 52).
- [ ] One header, footer and reading column; one right edge; no horizontal scroll at 360 to 1920 (rules 43, 44, 68).
- [ ] Tables scroll in their box; cards in a row share the row; contrast passes (rules 48, 46, 59).
- [ ] FAQ, call to action and read-next follow their rules (rules 96, 32, 54).
- [ ] Every house feature of the page's type is there, or the pull request says why not (House features, rule 156).
- [ ] The cover is original, has alt text and no title drawn in it; images are light and sized (rules 61, 62, 63).

**4. SEO**
- [ ] One H1; title 30 to 60, description 120 to 155; no skipped heading level (rules 81, 84).
- [ ] URL kept, or one 301; no internal link to a redirect; heading ids kept (rules 73, 75, 85).
- [ ] JSON-LD matches what is shown; FAQ markup equals the visible FAQ (rules 95, 96).
- [ ] The page is linked from two or more pages and links up to its money page and across to siblings (rules 88, 89).
- [ ] Link text names its target; no `utm_` on internal links; no placeholder href (rules 90, 34, 92).
- [ ] Share image exists and is the right size (rule 65).

**5. Verify**
```
growth checks                                                    # only the checks this change touches (rule 105)
growth gate page <path> --url <local URL> --repo . --type <type>   # every rule a program can decide; no FAIL
```
- [ ] Both pass. If one fails, say so; do not call the work done (rule 105).
- [ ] Look at the production build in a browser at 360, 390, 820, 1280 and 1920 wide; click the logo from a scrolled page and land at the top (rules 106, 107).
- [ ] Check the share preview and the search snippet (rule 108).
- [ ] Speed scores did not drop for a layout or script change (rule 101).

**6. Publish**
- [ ] Work is on a branch; the pull request lists what changed, why and the sources (rules 114, 17).
- [ ] The owner has said an explicit yes in this conversation; only then merge (rules 114, 116).
- [ ] Commit identity is the repo's own; no secrets in the diff (rules 118, 119).
- [ ] You know the undo (rule 127). After the merge, check the live page once.
- [ ] If the round taught anything new, update this file (rule 128).

## House features (rule 156)

Every feature the owner has agreed for a type of page. **A new or rebuilt page keeps all of them**; leaving one out
needs a reason in the pull request. "(waits)" marks a feature that waits for the owner's yes. Every page of every
type also keeps the shared header, footer and breadcrumbs (rules 43, 50, 51, 140), the "+" link previews (36c), copy
buttons on emails, phones and shown URLs (131), the one Organization node (150), call-to-action events (133) and the
technical SEO check (36d).

**Money page** (a service page, the home page, pricing, the booking page)
- [ ] First screen answers the question in one quotable 40 to 60 word passage (18, 36b); split hero at desktop (147)
- [ ] The page's own interactive element, with its state in the URL (02-owner-rules "Money pages are unique"; 79)
- [ ] Interaction hints on every control (36a)
- [ ] Booking buttons with a reason line, one primary button style (32a, 32b), opening the booking dialog (132, 134)
- [ ] Sticky call bar (35) and exit offer (35b), never on the booking page itself
- [ ] One comparison table or definition an AI can lift (36b)
- [ ] FAQ as one numbered box (139) with FAQPage markup from the same list (96, 151), then the ask card (135)
- [ ] Motion on every fold (141); no fold, hero or animation copied from a sibling page (30, 157)
- [ ] Visible updated date and publisher (36b); the page's main schema type and BreadcrumbList markup (95)
- [ ] Footer call row and Back to top (140)

**Hub** (a page that maps a group of posts)
- [ ] A map of where the reader is, not a copy of its posts (26)
- [ ] Its own interactive, animated element with its state in the URL (144)
- [ ] A cover thumbnail on every post card (144); a logo for every tool it names (143)
- [ ] One closing call for the cluster's offer through the booking dialog (26, 132)
- [ ] Motion (141); FAQ box and ask card if it has a FAQ (139, 135)

**Post** (an article)
- [ ] Original cover with no title drawn in it (61); "Key takeaways" when the frontmatter has them (137)
- [ ] Reading aids: heading copy links, progress line, "x min left", contents list (138, 53)
- [ ] Steps timeline, verdict shape and one mid-article read-next card where the Markdown has them (142)
- [ ] One ask card where the reader would want help (136); FAQ box and ask card if it has a FAQ (139, 135)
- [ ] A ranked list post opens with the lineup; every named tool shows its logo (143)
- [ ] Side notes where marked (145); one "Read next" section at the end (54)
- [ ] Author box linking the author's page (149, waits)

**Core page** (About, Contact, legal)
- [ ] Contact: the form first, the booking band, the About page's trust story (38, 146)
- [ ] About and Contact link every service page by name (146)
- [ ] The support email and any phone with copy buttons (131)
- [ ] Booking buttons open the booking dialog (132), except on the contact and booking pages
- [ ] Motion (141); legal and thank-you pages stay plain (49)

**Waiting for the owner:** the booking dialog's host photo (132), Markdown copies and `llms.txt` (148), the author page
and box (149).

## Rules

### A. Claims, proof and accuracy

1. **Proof by data. State no number, customer, price, award, case study or guarantee that the business has not already stated or the owner has not approved.** A made-up claim costs trust the first time a reader or a buyer checks it. A new claim goes to the owner first; only then does it go on a page. [judgment: proxy words.no-price, words.no-customers, ev.research-check]
2. **Name no customer, show no logo and quote nobody unless the owner confirms it is real and allowed.** If the project has no customer list on record, do not imply one ("trusted by", "teams like yours") without proof. The proof allowed is written in `BRAND.md`. [judgment: proxy words.no-customers]
3. **What the business says about itself reads the same on every page.** The one list of "facts we state about ourselves" lives in `BRAND.md` (who we are, the one offer and CTA, pricing words, proof, what we never claim, the permission log). Check a page against it before you change a self-claim. A new claim goes into `BRAND.md` with the owner's yes first. For Brightline Lawn Care that list holds, for example, "a 15-minute quote call" and "flat price per visit". [judgment: proxy words.never-claim, words.no-price]
4. **One length for the call (or the one booking step), everywhere.** The project's `BRAND.md` names it, for example "15-minute quote call". Search the whole content folder before you change it. A different number on one page looks like a mistake and breaks trust. [code: words.call-length]
5. **Every fact about another product, a law or a rule comes from its official source, checked today, and the page says where it came from.** Where the official source is silent, say "we check this on the call". Do not fill the gap with a guess. For a rule or law, link the regulator or the text itself, not a blog. [judgment: proxy ev.research-check, ev.research-record, ev.paa-answered, ev.fact-sources]
6. **A page must be true today before you promote, redesign or link to it.** Check its core claims against current official sources first. Fix false claims before you spend effort on the design. [judgment: proxy ev.research-check]
7. **Quote a vendor's price for the reader's size and billing, not for the size the vendor's page opens with.** Pricing pages open on a default size, so the first number is often wrong for the reader. Set the page to the size you write about, say the billing (monthly or yearly), the currency and the date you checked. [judgment: proxy ev.research-check, words.no-price, ev.vendor-numbers]
8. **Say plainly what is free, limited, metered or paid, where it is true, near the top and not under a price table.** A reader who finds the catch late stops trusting the whole page. [judgment: proxy ev.research-check]
9. **If a page contradicts itself, or a fact about the business is missing from the list, ask the owner.** Do not pick one of two figures yourself. [judgment: proxy ev.open-findings]
10. **Key takeaways, side boxes, stat highlights and calculators restate what the page already says.** A number that appears only in a box was never checked in the text. A checker or calculator shows its sums, its source and its check date. [judgment: proxy claims.box-numbers]
11. **Ship no placeholder text and no leftovers.** That means no `TODO`, `FIXME`, `XXX`, lorem, stray `{{field}}`, other firms' names, "[Your Company Name]" or an old year in a title. Search the page text before every pull request. [code: words.placeholders]
12. **Every page says when it was written and last changed, and the dates are true.** Set `date` and `updated` (in the frontmatter or the page's data) from facts, never made up. When a fact on the page changes, move `updated`. [code: geo.updated]
13. **A title must not tell a story the page cannot source.** If the page cannot prove "a platform change broke X", the title must not say it. Say what users report as their report, never as the vendor's word. [judgment: proxy ev.research-check]
14. **Do not promise user reviews, quotes or ratings the page cannot quote.** If a review site blocks you, drop the promise from the title and the page. [code: words.review-promise]
15. **About and Contact answer what a buyer asks before booking.** Cover the questions the owner knows come up (how pricing works, how long it takes, what happens to their data), using only facts the owner has approved. Leave a question out rather than guess. [judgment: proxy ev.research-check]
16. **When you review or compare, say who you are first.** If the business sells something in the same space, one plain line under the byline says so before the reader finds out another way. Then be fair: give the other side a real "when to stay" block and never count one strength as several wins. [code: words.disclosure]
17. **Every claim you audit gets an outcome, written in the pull request: fixed, removed, reworded, or kept with a reason and a source.** The pull request is the record: what changed, the before and after, why, and the source. [judgment: proxy ev.journal-page]

### B. Answer first, then sell

18. **Write down the reader's question before you write the page, and answer it in the first screen.** The answer comes before the cover picture and before any pitch. Read the first quarter of the page: a stranger must know what they get. Pages that bury the answer lose the reader after one screen. [code: geo.answer-passage]
19. **One page answers one question.** If two pages answer the same question, merge them: carry over each heading by name, move every link to the survivor, and 301 the loser. If a hub and a post compete for one search, the hub owns the head term and the post takes its own angle. [judgment: proxy ev.dossier]
20. **When the title is a question, the first line is the answer** (yes, no, or "yes, but only this way"), then the steps, then the limits. Where the answer is "it cannot", put every way that works today in one table. [code: words.question-title]
21. **Answer with the reader's own number where one exists** (lawn size, number of visits, volume), not with an invented customer size. A reader who finds their own case trusts the page. [judgment: proxy state.url, ev.dossier]
22. **Sell only to the reader who needs it.** A reader who is still choosing gets the neutral invitation to talk. A reader who has decided gets the next step. A reader who came to fix something gets no sales bar. A page whose readers are mostly not buyers asks them for nothing. [judgment: proxy ev.dossier, cta.reason-line]
23. **The offer's heading, button, body and form agree.** A title that says "choose" must not have a button that says "start your order". [judgment: proxy cta.label-same, cta.reason-line]
24. **When one page serves different readers, let the reader pick their case and give each a route.** For Brightline that is the service (mowing, aeration, leaf clean-up). Each route has its own offer or none. [judgment: proxy state.url]
25. **A table of limits, routes or prices has a source on every row, a check date, and what it means for the reader.** A table without sources is a claim. The source and the date may sit in the table's own box, on the component that holds it (`data-checked="YYYY-MM-DD"` with `data-source="<url>"` or a linked source inside it), or in a dated source sentence in the same section. [code: geo.table-sources]
26. **A hub is a map of where the reader is, not a second copy of its posts.** Show the stages or jobs first, the guides under them, no fact a post already owns, and one closing call for the cluster's own offer. When the hub lists every guide in its sections, its own closing list is a plain list of titles, not cards again. [code: hub.map]
27. **A new cluster or service starts with research, not a template.** One file per page before the design: the search intents, the gaps the top 20 results leave, a fact base with sources, the old post's claims judged, and the reader's real pain. Then one design brief with one signature element for that reader's question, then build, then an independent check. [judgment: proxy ev.dossier, ev.review]
28. **Depth, not length.** A page is as long as its answer needs. A page that repeats the same list as cards twice or answers in screen 17 is too long. [judgment: proxy layout.folds-distinct]
29. **An About page is a story that earns trust, not a list of buzzwords.** State the positioning first, the real reason to care, real proof, and who stands behind it. A reader who senses buzzwords leaves. [judgment: proxy words.hype]
30. **No two folds of a page look alike.** A page of the same card grid over and over feels like filler. Give each fold its own shape and its own job. [judgment: proxy layout.folds-distinct, ev.shots-1366-390]
31. **A money page states only what the site already states.** Its numbers, badges and trust words come from the facts in rule 3, nowhere else. [judgment: proxy words.no-price, words.no-customers, words.never-claim]

### C. Calls to action and forms

32. **Every call to action goes through the one conversion path the site uses (a booking, a quote form or the contact form).** Use the site's shared button or component. Never paste a raw booking link into a card, and never invent a second path. A site that opens its own booking page on purpose (for example from its booking dialog) lists that link in `growth.json` `booking_allowed` with the reason; the gate then prints a WARN naming the exception, and every other booking link still fails. [code: cta.one-path]
32a. **Every booking button gives a reason to act** (from a real project: "there is no advantage of why one needs to get on a call"). The label is the project's one CTA label (`BRAND.md`), and one line beside it says what the reader gets, taken from what the offer really includes (for Brightline: "Tell us your lawn size and get a price within one working day"). Never a bare "Book a call". Never "free" or "no obligation" until `BRAND.md` allows it. [code: cta.label-same, cta.reason-line, cta.no-bare-book, words.cta-banned]
32b. **One primary button style per page**: a dedicated call-to-action colour token that is clearly brighter and more inviting than anything else on screen (the project sets the value; AA contrast, soft shadow), solid, one radius, one arrow, the same in the header, the sticky bar and every section; secondary actions are outlines. The brand colour is not spent on decoration next to a button, so the action is the strongest colour on screen. [code: cta.one-color]
32c. **The primary CTA carries a soft glow in its own colour** (from a real project): a coloured shadow at rest, a little stronger on hover and focus; it pulses twice, gently, only at a moment of intent (the sticky bar first appears, a tool shows its result), then stays still. Never an endless pulse; reduced motion gets the static glow; the focus ring stays separate; secondary buttons never glow. [code: cta.glow]
33. **Link and button text names its one target.** The project's one CTA label always goes to the conversion path; "Read more" never goes to two different pages. A link that says "Source" or "click here" says nothing. [code: seo.anchor-text, cta.no-bare-book]
34. **No internal link carries `utm_` parameters.** They restart analytics mid-visit and create crawlable duplicate addresses. Name a call to action by where it sits (a data attribute or an analytics event), not by changing the link. [code: links.no-utm, seo.utm]
35. **Every money page has a scroll-in sticky call bar** (from a real project): the site's one shared component, with the page's own line and a clear button, on phones too. It **replaces** the top menu with one full-width bar (the reader's doubt plus the offer's benefit, three short checks, a high-contrast button with an arrow, a close x, a thin reading-progress line). It appears only after the first screen has scrolled away. Once shown it **stays**: it hides only when the top of the page or the footer is in view, and while the exit offer (35b) is open; never near mid-page blocks, offers or forms (that made it flicker). It must be dismissible (x or Escape, for the session) and never shows on contact, booking, thank-you or 404 pages. Its words repeat an offer the page already makes: a line of at most 70 characters and a button of at most 30, taken from the page, else its service, else the site default. It must not move the layout. [code: sticky.present]
35b. **Every money page has a relevant exit offer** (from a real project: "a very, very relevant exit popup that makes them book"). One shared dialog, page-aware: it uses what the reader did on the page (their own numbers from the page's tool) and offers the same offer with its reason line, plus a way to send the result to the person who decides. It opens on leaving intent only after real engagement (time or tool use), once per session, never after a booking click or a dismissal, never on the first screen. Accessible dialog (focus trap, x, Escape, backdrop), a bottom sheet on phones, the sticky bar hides while it is open, analytics events for view, click, copy and dismiss. Its words follow `BRAND.md` (its banned words stay banned). [code: exit.present, words.cta-banned]
36. **A trust line states only what the site states elsewhere.** What may be said is in `BRAND.md`. "Free" and "no obligation" are not used unless `BRAND.md` allows them; they wait for the owner's yes (rule 32a). Anything else needs the owner's yes. [code: words.banned]
36a. **Show the reader where to interact** (from a real project: "arrows or a finger pointing to users where they need to interact"). Every interactive control (inputs, sliders, toggles, approve and copy buttons) gets a first-time hint the moment it scrolls into view: a small animated hand or arrow with a 2 to 4 word label in the call-to-action colour. One hint at a time, a short nudge then rest, gone once the control is used (per session), never covering the control, `aria-hidden`, static under reduced motion, no layout shift, clear of sticky bars on phones. [code: hints.present]
36b. **Ready for AI answers (GEO/AEO)** (from a real project). The core question is answered in the first screen in one self-contained, quotable passage of 40 to 60 words: what it is, who it is for, the one difference. Every FAQ answer starts with a one-sentence direct answer. The product or service is named in plain text with what it is and who it is for. Passages stand alone (no "this" or "it" openings), numbers carry units. Structured data matches the visible text (the page's main type, Organization, FAQPage, BreadcrumbList). A visible updated date and publisher. One table or definition an AI can lift. Anything shown only by a tool or a picture also exists as text. Every query with impressions is answered by a named element (money-page playbook, questions 33 to 36). [code: geo.answer-passage, geo.no-pronoun-openers, geo.updated, geo.liftable, faq.answer-first, schema.house-types]
36c. **Every internal text link on the site previews its target with a small "+"** (from a real project). It covers every text area, not only posts: hero leads, card bodies, FAQ answers, About, Contact and footer text. The "+" never starts a line on its own (it carries the link's last word with it, a word joiner). A test lists every rich-text area and fails when a new one is missing from the link-card scope. Internal links get a small "+" that opens a light card with the target's type, title, description and cover, and an "Open" link, from a static index built from the site's own content (drafts and redirected pages never appear). External links show the domain and full address with the shared copy and open buttons. None on fragment, same-page, phone or email, image-only, button-style or call-to-action links. Lazy (first hover, focus or tap), one at a time, Escape and outside click close it, keyboard reachable, a bottom sheet on phones, no layout shift. One shared component. **Colour and glow:** in-text links and their "+" use one link-blue token (suggested #1a5fd0 on light and #6ea8ff on dark; the project may set its own; contrast 4.5:1 or more), underlined, never the brand or CTA colour, so a link never looks like a button and a button never looks like a link. The open preview card has a clear soft glow in the same blue (a 1 to 2 px ring plus a blur of 24 px or more), not only a grey shadow. **Spacing:** every in-text link keeps its normal space before and after it; in JSX a line break between text and a link is dropped, so write `{" "}`. **Punctuation:** the order is link words, then the "+", then the punctuation, with no space before the punctuation; the last word, the "+" and a following `, . ; : ! ? )` form one group that never breaks across lines. [code: links.cards, links.blue, links.card-glow, links.spacing, links.punct]
36d. **Every page passes the technical SEO check before release** (from a real project): `growth tech_seo_check <local URL>` with no FAIL, following the [technical SEO playbook](playbooks/technical-seo.md). [code: seo.all]
36e. **Every list tick is a tick inside a circle** (from a real project). Benefit lists, proof rows, checklists and comparison cells use one shared `Tick` component: a tick inside a circle (outlined, or filled for emphasis), in one green "yes" colour token (for example `--color-yes`), sized to the text's cap height and aligned to the first line. No bare ticks (a lone check mark or a tick character) anywhere, except the copy button's "copied" state. [code: icons.check-circle]
36f. **Every fold has its own surface, chosen by its job in the reader's mind** (from a real project: "think of the principles of how a good brochure or marketing ad page is created"). Like a brochure spread, the page has rhythm: each fold (a `section` with `data-fold`) declares `data-surface` from one shared set (`plain`, `tint`, `warm`, `geo-grid`, `geo-lines`, `geo-contour`, `geo-hatch`, `dark`) and `data-job` from the reader's journey (`hook`, `show`, `compare`, `reassure`, `prove`, `relief`, `act`, `read`, `answer`). Light geometry is themed on the subject and stays faint (opacity 0.08 at most) so text keeps its contrast. No two folds in a row share a surface; 3 or more kinds per page; 2 dark folds at most, used to reset attention before a turn in the story; the folds whose job is `act` are set apart from their neighbours so the eye lands there. Psychology works only through true things: contrast, rhythm, isolation, progress and relief, never fake urgency, fake scarcity or guilt (rules 7, 31). The surfaces live in one shared CSS file, and each label must match what the fold really paints (checked in a browser). [code: page.surfaces, page.surfaces-paint]
36g. **Every picture and chart reads in 3 seconds** (from a real project, on a first chart that was "very bold, hard to understand and too busy"). One idea per picture; nothing in it the reader cannot name; at most the ink colour, the brand colour and one neutral, plus the green "yes"; line weight in proportion to the size shown (about 2 px at card size), with detail only where the picture is shown large; repeated items collapse ("+6 more") rather than crowd. The chosen illustration style (`BRAND.md`) gives the look, never the busyness. Test: show the screenshot for 3 seconds and say what it shows; if you can't, simplify. Judged on fresh 1366 and 390 screenshots. [judgment: proxy ev.shots-1366-390]
36h. **A fold-by-fold detail plan comes before any page work** (from a real project: "the AI needs to pay attention to the smallest details for each page element and each fold"). Before the build, `growth fold_plan init <path> --url <local URL> --key <key>` writes `research/plans/<key>.json`: one entry per fold (named as its `data-fold`) answering 14 detail fields (job, surface, headline, copy, visual, edge cases, links, CTA, controls, icons, motion, mobile, analytics, check) and 7 shared elements (header, sticky bar, exit offer, link previews, footer, schema, speed). Every field gets a real answer or "n/a: <reason>". The builder works from it; the gate fails while a fold on the page is missing from the plan or a field is empty. [code: ev.fold-plan]
36i. **Every page is archived live before and after it changes** (from a real project: a full copy of the page before, stored like one full image, so old and new can be shown side by side). Before any change to a live page ships (and before the build starts), `growth page_archive capture <path> --stage before`; after the release is live, `--stage after`. Each capture keeps one full-page image at 1366 and one at 390, the served HTML and its details, in `archive/pages/<slug>/<date>-before|after/`, kept for good. A brand-new page has no "before": its first capture is "after". The capture blocks every analytics request, so it is never counted as a visit. [code: ev.archive-before, ev.archive-after]
36j. **Every control reads in every state: at rest, on hover and on keyboard focus** (from a real project, on a footer button whose dark text sat on orange and went darker still on hover). For every link, button and control, the text colour against the colour actually painted behind it is at least 4.5:1 (3:1 for large text, 24px+ or 18.66px+ bold) in all three states, and a focus ring is at least 3:1 against what it sits on. A hover changes one thing the reader can see (a deeper fill, an underline, a lift) and never the text into the fill's colour; a filled button keeps light text in every state; a surrounding rule (footer, nav, card links) must never reach a filled button. Colours come from paired tokens (fill + text-on-fill). Measured in a real browser at 1366 and 390 by `growth contrast_check`. [code: ui.contrast-states]
36k. **Never state where the business or its people are, when `BRAND.md` says not to** (from a real project). Some businesses must not name a country, region or city (for example for legal or trade reasons). When the project lists such words in `growth.json` `never_say_location`, no page may use them: no "based in", no flag, no city on a person card, no address, location or areaServed in structured data. A blog post may quote a competitor's own reach. [code: words.no-location]
36l. **Every page has one named author, linked** (from a real project: each page needs to follow Google's E-E-A-T rules and link to one author). Every page shows "Updated <date> by <author name, role>" through the shared byline, the name links to the author's page (`growth.json` `default_author`, the person in `BRAND.md`), and the page's WebPage or Article node names the same Person as `author` (one Person node site-wide). Never "by the team". The author page lists everything that person wrote and links their real profiles. [code: words.named-author]
37. **A form that creates a lead must prove a person sent it** (a hidden honeypot field, a bot check, a check on the origin). Bots will find any open form. Never send test data to the live form. [code: form.bot-guard]
38. **The contact page puts the form first and does not leave half the screen empty.** The booking option is a clear horizontal band, not a tall box that pushes the form down. [code: core.contact-form-first]
39. **At desktop width there is no empty half, no tiny logos and no stretched illustration.** Look at the page at 1280 and 1920. [judgment: proxy ev.shots-widths]

### D. Layout, design and components

40. **Stay in your lane in the site repo.** Design, CSS, layout, components and images belong to one lane at a time (see [04-lanes-and-releases.md](04-lanes-and-releases.md)). Do not rewrite files you do not own right now; another agent may have work in progress. [judgment: proxy repo.branch]
41. **Use the site's design system: its tokens, its shared layout styles and its content look.** Use tokens for colour, spacing and radius; add no ad hoc value where a token exists. Current owner direction beats older design specs. (Next.js adapter: the token files named in `growth.json`.) [code: repo.tokens]
42. **Keep the approved logo lockup as it is.** The owner approved it; do not redraw, recolour or crop it. (Next.js adapter: the logo files named in `growth.json`.) [code: repo.logo-untouched]
43. **One header, one footer and one reading column on every page of a kind.** Going from one page to another must not move the logo, the menu or the column, and the page content starts and ends on the header's lines. Measure at several widths. [judgment: proxy layout.shared-frame, ev.shots-widths]
44. **Everything in an article ends on one right edge, at one reading width** (breadcrumbs, title, cover, takeaways, text, tables, FAQ, author box, related cards). Wide blocks use one width rule, and a wide block inside a wide block never grows again. [judgment: proxy ev.shots-widths]
45. **Body text is 60 to 80 characters a line.** Much longer lines tire the eye. [judgment: proxy ev.shots-widths]
46. **Cards in a row share the row.** Two are halves, three are thirds. Never one card left with an empty slot. A before/after pair keeps its own height. [judgment: proxy ev.shots-widths]
47. **A popover, menu or sticky bar never covers something the reader needs to click.** [judgment: proxy ev.shots-1366-390, ev.click-test]
48. **Wide tables scroll inside their own box, keep the first column sticky, show an edge shadow and cut nothing off.** Highlight your own column only if the page is about you. Numbers in a column line up on the right. [code: layout.table-scroll]
49. **Every page has a type, and the type sets its frame:** full width for money, service and landing pages; one reading column for articles; plain for legal and thank-you pages. Do not give a money page the look of a blog post. [code: layout.frame-type]
50. **Breadcrumbs sit on every page except home, and come from the same data as the BreadcrumbList markup.** The last crumb is the current page. [code: crumbs.visible, seo.breadcrumbs]
51. **One footer, full width, on every page.** Give it room to breathe. [code: layout.shared-frame]
52. **Build components and apply them by pattern; do not build one-off code for one page.** If you need a new block, make it reusable, so every similar page improves. [judgment: proxy repo.shared-components]
53. **The contents list is built from the article's H2s.** Keep H2 text under 60 characters and meaningful, because it is the label readers see. An article with fewer than four H2s goes without one. [code: post.toc-h2]
54. **One "Read next" section under each post, with relevant stories and no duplicate sections.** Rank by the same topic group, then shared topics, then date. Every post is reachable from at least one such box. Give a story of another group a slot, so topics stay linked. [code: post.read-next]
55. **Engagement blocks (pickers, quizzes, calculators, checklists) are built from the page's own content.** They add no claim. They show their source and date. They work without a mouse and respect reduced motion. [judgment: proxy motion.no-libs, claims.box-numbers]
56. **Embeds (maps, videos, widgets) load on a click or when needed, and send nothing to a third party before the reader acts.** It protects privacy and speed. [code: embeds.lazy]

### E. Icons, motion, type and images

57. **One icon family, no emoji in the interface or in tables.** Pick an icon that means the thing. Status is an icon plus a word, never colour alone. Never ship an empty icon. [code: icons.no-emoji]
58. **Motion is made with CSS and a little script, not with animation libraries.** It respects `prefers-reduced-motion`, and it must not cost speed or move the layout (no layout shift). Home-page films and animations get the same test. [code: motion.no-libs]
59. **Readable beats pretty.** No see-through panel or effect that makes text harder to read. No dark text on a dark ground or light on light. Check the themes the site really has (light only, or light and dark). Text meets WCAG AA contrast. [judgment: proxy ev.shots-1366-390]
60. **A link inside running text is underlined, not shown by colour alone.** [judgment: proxy ev.shots-1366-390]
61. **Every article has its own original cover, and no picture has the page's title drawn into it.** Covers are distinct per article; a coverage test checks names, files and hashes. Add original artwork with every new article. The page draws the title, so it shows once and follows every edit. [judgment: proxy post.cover]
62. **Every image has alt text. A decorative image is marked decorative.** The cover's alt is the post title if nothing better is set. An image that is a link's only content, or wider than 200px, needs a real alt. [code: seo.alt]
63. **No picture served is heavier than 200 KiB, and each has width and height.** Use the framework's image component and modern formats where the site already does. [code: seo.img-weight]
64. **Every image file keeps its extension in its name.** A file served without a type may not show at all. [code: seo.img-ext]
65. **A page's share image exists, is the real size it says, and is never a loader, a sprite or a GIF.** `og:image` and `twitter:image` match. Look at the share preview. [code: seo.share-image]
66. **Nothing on the first screen loads lazily, and the main picture has priority.** Lazy loading above the fold slows the first paint and trips checks. [code: seo.first-screen-lazy]
67. **Nothing scrolls by itself while a page loads.** A script that scrolls before the first paint can stop the browser recording its Largest Contentful Paint (the time the main content shows). [code: js.no-autoscroll]
68. **A phone screen holds the page in every state, not only the settled one.** At 360, 390, 820 and 1024 px nothing runs past the screen: long labels wrap, grids use `minmax(0, 1fr)`, and a part that moves into place stays inside the screen while it moves. [judgment: proxy ev.shots-widths, ui.phone]
69. **No picture is drawn over text that is not its own.** Check badges, logos and cards at 390px, where a wide picture can cover the words beside it. [judgment: proxy ev.shots-1366-390]
70. **On phones no small label is under 12px and each footer or menu link is at least a 24px tap target.** Measured by `growth phone_check` at 360, 390, 820 and 1024. [code: ui.phone]
71. **A nested list stays visibly nested.** A nested item starts at least 12px right of its parent. [judgment: proxy ev.shots-widths]
72. **A separator (dot, slash, bar) never starts or ends a wrapped line.** [judgment: proxy ev.shots-widths]

### F. SEO: titles, headings, addresses

73. **The URL scheme is frozen.** The project's scheme (for example posts at `/blog/<slug>`, core pages at `/<slug>`) is written in `SETUP.md`. Never rename a slug or change a route path without a redirect plan. Backlinks and rankings depend on them. (Next.js adapter: the route files.) [code: repo.url-frozen]
74. **Keep every live URL, title, description, canonical, robots rule, H1 and heading outline, and every JSON-LD type, unless the owner approves the change.** A "small" tidy of a ranking page can lose its rankings. [code: seo.kept]
75. **A moved or merged page gets one 301 straight to its final address, never a chain.** Internal links point at the final address, never at a redirect or an old host. Redirects live in the site's redirect config; ask before touching it. When a post is renamed or moved, update every file that names it: related and hub lists, the artwork map, stored structured data, and links. [code: links.no-redirect, repo.redirects-untouched]
76. **Retired page groups answer 410 on purpose.** If the project retired a group of pages (for example old tag pages), they answer 410, and design work does not bring them back. The project lists them in `SETUP.md`. [code: repo.retired-410]
77. **A page that is gone answers 301 or 410, never a plain 404 for a URL people still ask for.** When a list page vanishes (page 12 of a list that now has 10), send it to the list's page 1. Read the 404s you can see (host logs, Search Console once it is connected) and fix the ones real crawlers ask for. [judgment: proxy ev.release-check]
78. **No address on a retired host appears anywhere the site shows or gives Google.** Search the built pages, JSON-LD, sitemaps and feeds for the old host names and old server addresses listed in `growth.json` `old_hosts`. [code: seo.old-host]
79. **Every state a reader can reach has its own URL:** a filtered list, a page of a list, a section by `#id`. Use opaque ids only: no email, name or secret in a URL. [code: state.url]
80. **Every indexable page names its own canonical, in the site's one address style** (trailing slash or not, as the site already does). [code: seo.canonical]
81. **A title is 30 to 60 characters and 580px wide or less; a meta description is 120 to 155 characters and 990px or less, a full sentence, with no Markdown or HTML.** A title cut off mid-word in a result loses clicks. Do the check on the real text (`metaTitle`, `metaDescription`); if they are empty the site falls back to the title and the excerpt, so check those too. The title holds one of the page's top 2 Search Console searches; when the most-shown one has under 10 views (too little data), it holds one of the first 2 `target_searches` in the page's plan (`research/plans/<key>.json`, from the dossier). [code: seo.title-desc, seo.title-query]
82. **Each title and description is its own.** Never copy another page's description into this one, and never leave one stale after you changed the page. `og:title` and `og:description` follow the meta text unless there is a reason. [code: seo.unique-meta]
83. **Every indexable page has a meta description, a title that fits, exactly one H1 and a share image.** A hub, a money page or a list page shows a main picture at least 480px wide as well. [code: seo.basics]
84. **Exactly one H1.** A line that looks like a heading is a heading; body headings under the H1 start at H2 and never skip a level. A key figure drawn big ("19 min") is emphasis, not a heading. [code: seo.headings]
85. **Keep old heading ids so old `#section` links still land.** Heading ids are an address too. [code: seo.heading-ids]
86. **A page of a list after the first has its own title, description and H1** ("Blog, page 2 of 6"). Every list page is one click from page 1, and its previous and next links are in the page. A list that repeats another list is not indexed twice: canonical to the first or noindex. Page 1 of an indexable list opens with a short intro (150 to 250 words) that says what it covers, who it is for and where to start, and links its best posts, using only facts the site already holds. [judgment: proxy seo.title-desc, seo.canonical]
87. **The sitemap lists only pages you want as search landing pages:** status 200, indexable, its own canonical, no `.md` or JSON file. Note how many URLs the sitemap lists today (in `SETUP.md`) and check the count before and after a change. [code: seo.sitemap]
88. **Every indexable page is linked from the content of at least two other pages.** A page reachable only through a menu or a pager is weak. After a content round, list the pages with fewer than two inbound links and fix them. [code: links.inbound]
88a. **Every money page and hub has an internal-link plan built from its cluster and its data** (from a real project). Before a page is built or rebuilt, `growth link_map inbound|suggest <path>` lists its inbound body links and ranks the pages that must link to it: same cluster (hub and spokes), Search Console queries that overlap, sentences that already name the topic without a link, and the buyers' AI questions. A money page gets contextual inbound links in body text (not only menus) from its cluster's strongest pages, with descriptive, varied anchors in the searchers' own words, and links out to its spokes and up to its hub. Every planned link is filed in the page journal against the **source** page (`growth journal add --tag internal-link`), so whoever works on that page next finds it; the top links are added with the page's release; the rest are added when their page is next touched. Inbound counts before and after are re-checked at day 28. Playbook: [internal-linking](playbooks/internal-linking.md). [code: links.plan]
88b. **A money page carries contextual links inside its prose** (from a real project: "I did not see any internal links on that page"). Every content fold has at least one link in its running text, and FAQ answers link where a guide answers more; 10 to 14 in total, each on words already in the sentence, every anchor different, never on a CTA or heading, each with the "+" preview (36c). Shelves and cards at the bottom do not count. [code: links.in-folds]
89. **A post links up to its money page and across to two or three siblings, and they link back, with varied words.** Do not use one anchor for most links to a page. The home page links every main service or topic group. Link from a sentence that already talks about the target. [code: links.up-across, seo.contextual-links]
90. **Link text names the page it goes to, and the same text never goes to two different pages.** A crawler and a screen reader read the text alone. A link to an outside source names the source ("the agency's guidance"), never "Source". [code: seo.anchor-text, links.anchor-unique]
91. **A link to another site is `noopener`; add `nofollow` or `sponsored` on any link you do not vouch for or that is paid.** Follow only official sources and real certificates. [code: seo.external-links]
92. **No `<a>` without an `href`, and no placeholder `href` such as `about:blank`. No `<img>` without `src`.** A crawler resolves them against the page and asks for addresses that do not exist (one site got hundreds of such requests). [code: seo.placeholder-links]
93. **One spelling for the whole site.** The project picks one (for example US English: "color", "optimize"; Canadian: "colour", "optimize"; British: "colour", "optimise") in `growth.json` `spelling`: `en-US`, `en-CA` or `en-GB`, or a locale per path (`{"/": "en-CA", "/en-us/": "en-US"}`), or `html_lang` to read each page's own `<html lang>`. Words that are real in the other locales (check, meter, program) are never flagged. Keep it in titles, descriptions, alt text and body. A real product name goes on the reviewed allowlist (`spelling_allow`, or the file named in `spelling_allow_file`) only after you read it in place; never add a misspelling to pass a check. [code: words.us-spelling]
94. **If a language or region is added later, every locale copy needs reciprocal hreflang, its own canonical, and the right `lang`.** A one-language site needs none. [code: seo.hreflang]

### G. Structured data

95. **JSON-LD says what the page shows, and nothing else.** An article's node is built from its own fields: headline = the H1, dates = `date` and `updated`, image = the cover, author = a real person's page. A node must not point at an object that is not on the page. Every indexable page, list pages included, has its page node. [code: seo.jsonld, schema.house-types]
96. **A FAQ has an answer for every question, never asks the same thing twice, and its FAQPage markup is the visible questions and answers, word for word, in the same order.** Questions are headings. A mismatch can cost the rich result and misleads readers. [code: faq.schema-equal, seo.faq-markup]
97. **Structured data names only this site and the real people who write for it.** Never a login name, a placeholder or the company as a Person. [code: schema.people]
98. **(Next.js adapter) Render JSON-LD (and any inline script a page emits first) inside an empty block `<div>`, never as the page's first child.** Next scrolls the new page into view node by node, last to first. A hidden `<script>` first leaves the window part-way down after a client-side navigation. Put it in the shared `JsonLd` component. [code: seo.jsonld-first]
99. **With a sticky header, set `html { scroll-padding-top }` to the header height plus a gap.** Anchors and navigation then clear it. [code: css.scroll-padding]

### H. Speed and build

100. **(Next.js adapter) The build stays fully static where the site is static: the build must succeed with every route generated at build time.** Bad frontmatter fails the build on purpose: fix the Markdown, never suppress the error. [code: repo.static-build, seo.render]
101. **Keep the speed scores where they are today.** Before a layout or script change, run Lighthouse on home, a money page, the blog, a post and contact, and put the scores in the pull request. No layout shift, a quick main paint. [judgment: proxy ev.speed, seo.speed-static]
102. **The build output is the same twice.** No random ids in the markup. Random output causes hydration errors and noisy diffs. [code: repo.no-random-ids]
103. **Analytics and ad tags run only on the real domain, not on previews or localhost, and heavy tags wait for the first interaction or a short delay.** New tags need the owner's yes. [code: tags.not-local]
104. **Only one module reads the content files.** The project names it in `SETUP.md` (for example `lib/content.ts`). It is the one swap point if the content store ever changes. (Next.js adapter.) [code: repo.content-reader]

### I. Testing before a pull request

105. **Run only the checks the change touches; never the whole suite "to be safe".** (From a real project: work fast and lean; no hours of tests a change cannot affect.) Run `growth checks` in the site checkout: it maps what changed to the tests that can be affected (copy or layout edits: the host's build is the gate, then check the page live; content, covers and artwork: the content tests; library code, scripts and middleware: related tests and one build; routes, sitemap, config and packages: one build). A browser look only when layout changed. Always confirm the change on the live page after deploy. If a check fails, say so with its output. [judgment: proxy proc.checks-script]
106. **Look at the production build in a real browser at 360, 390, 820, 1280 and 1920 wide.** Check the overflow, the right edge, and that a click on the logo or Home from a scrolled page lands at the top with the menu in place. Take screenshots to check yourself; show the owner only a before/after they must approve. The gate and READY run on the production build served locally (`growth serve <dist>`, or the site's own preview command in `growth.json` `preview_cmd`), never on a dev server: a dev page has no sitemap, a missing share image and a tag loader that are not the page's faults. [judgment: proxy ev.shots-widths, ev.prod-build]
107. **Keep a regression test: from a scrolled page, navigate to several routes and click the logo, and assert `window.scrollY === 0`; also check one hash link.** The Next.js scroll bug comes back whenever a page's first node changes. If the repo has no Playwright yet, adding the test needs the owner's yes for the new dependency. (Next.js adapter.) [code: repo.scroll-test]
108. **Check the page the way readers' tools show it:** the share preview, and the search snippet. A broken share image once reached an owner. [judgment: proxy ev.share-preview, seo.share-image]
109. **The lead checks every page an agent produces** before accepting it: the checks, a browser pass, and each claim against the source. The owner reviews no batches of unchecked pages. Every content change has an independent review by a different model, written from the kit's fixed checklist (`kit/checklists/review.md`, `growth review new <key>`): comparisons are like for like (the same feature on both sides of a price sum), every number in the head or verdict is stated in the body with its source, and no two answers contradict. Fields the site holds on purpose (titles, descriptions, H1s in a freeze) keep their proposals in the page plan (`growth held`); a proposal that quotes a fact a review changed is stale until rewritten. [judgment: proxy ev.review, claims.head-figures, ev.held-proposals]
110. **Fix the bug, then add a guard for its whole class and sweep for siblings.** A fix without a guard comes back. Put the guard in the project's test suite; a guard that cannot run there goes into `growth gate`. [judgment: proxy repo.guard-tests]
111. **Before you tell the owner to look, make sure the page renders.** Give them a URL to open, not a file path. Say what changed. [code: page.renders]
112. **A check that makes a temp folder removes it, pass or fail.** [code: repo.temp-clean]
113. **Reviews happen on localhost previews from branch worktrees.** Never ask the owner to review on the code host or in the hosting dashboard. [judgment: proxy repo.branch]

### J. Release and process

114. **Never push to the production branch and never merge without the owner's explicit yes in the current conversation.** On many hosts a push to the production branch is an instant deploy. All work goes on a branch (`article/...`, `page/...`, `fix/...`, `design/...`) and then a pull request. [code: repo.branch, proc.no-push-main]
115. **Production deploys only from a clean, up-to-date production branch.** Never run a manual deploy unless the owner asks. A deploy of a stale copy can bring old versions of other pages back. [judgment: proxy proc.no-push-main]
116. **A yes covers what it names.** Once the owner says yes to a change and every check passes, merge it without asking again. A wider or different change needs a new yes. A failed check, DNS, money, accounts, deleting data, or a fact only the owner knows always waits. [judgment: proxy ev.decision]
117. **Scheduled content publishes by its date, and the schedule really runs.** Approved future-dated posts switch on only at the next build on or after their date. Know how that build is triggered (a scheduled redeploy, a queue job) and check it exists before you rely on it: a missing deploy hook or secret means the post does not appear on time. A draft is never built. The project's daily limit (for example at most two articles a day) is in `SETUP.md`. [judgment: proxy proc.no-push-main]
118. **Commit with the repo's local identity** (`growth.json` `commit_identity`). Another address can make the host block the deploy. [code: repo.commit-identity, proc.commit-identity]
119. **Never commit secrets, tokens or old export files.** Keys live only in git-ignored files, never in a template, a log, a message or a commit. [code: repo.no-secrets]
120. **Before a redesign or a bulk change, make a backup tag, test the change on one real page first, and roll it out only on the owner's yes.** [code: repo.bulk-backup]
121. **Components change markup, not wording, unless the owner approved the copy change.** Redesign must not lose words that rank. [judgment: proxy seo.kept, ev.decision]
122. **Do not re-run one-off migration scripts over live content.** A script written for a past move (a platform change, an import) can overwrite later edits. Mark each one as used, and keep it out of the normal tools. [code: repo.no-migration]
123. **Commit by path, with one plain sentence and the co-author line.** No `git add -A` that sweeps in unrelated files, no bare `git stash`. [code: repo.commit-style]
124. **Files stay under 1,000 lines.** Split before they grow. [code: repo.file-size]
124a. **A rework removes what it replaced** (from a real project: do cleanup and housekeeping of your own created dead code and test files). A component, library file or stylesheet the branch adds or changes must still be used by something, and a test must test something that exists. Scratch files, screenshots outside `research/`, spare dev servers and finished worktrees are removed when the work ends. No unused import, variable or parameter is left in a file the branch changed (from a real project: "clear all your dead codes, non used codes"). [code: repo.no-dead-files, repo.no-unused-code]
125. **No commands that trigger permission prompts for nothing:** no `rm -rf` with a variable or a glob, no `cd` chains; use absolute paths and `git -C`. Write scratch files only in the scratchpad. [judgment: proxy repo.temp-clean]
126. **At most the project's agent limit at a time (default 4), none that starts its own agents, each closes its browsers, and a finished agent ends.** [judgment: proxy proc.worktrees]
127. **Know the undo before you merge:** the merge commit to revert, or the earlier deployment to promote. Say it in the pull request. After a merge, check the live page with one request, not a crawl of the live site. [judgment: proxy ev.release-check]
128. **Keep this rulebook and `BRAND.md` current.** When the owner corrects something, add or change a rule in the same pull request, bump the version and add a change-log row. [code: proc.rulebook-current]
129. **Write to the owner in simple English, answer first, one question at a time.** Text they will paste goes in its own plain code block. Do not mix topics. [judgment: proxy proc.plain-report]
130. **Find things yourself rather than asking, and when the owner points at a problem, fix the real page now.** Do not queue it. [judgment: proxy ev.open-findings]
131. **Every URL and every text value someone may paste gets copy buttons, on the public site too** (from a real project). That means the support email in the footer and on Contact, every phone number (a `tel:` link plus copy), and every URL shown in a sources list (copy and open in a new tab). Hover or focus reveals the icons at the value's end; a copy turns the icon into a green tick for 1.5 s; keyboard reachable with an `aria-label`; always visible on touch screens. One shared component, guarded by a test that fails when a screen builds its own copy button. **Never on a form field or a secret.** The same rule applies to every tool and dashboard built for the project (such as the page tracker). [code: copy.shared]

### K. Reader features, structured data and process

These rules were once dropped by mistake from a first draft because "the notes did not have them". The owner kept
finding the features missing, so they are rules. A rule marked **waits for the owner** is not built until the owner
says yes; until then the page simply goes without it.

**K1. Reader features**

132. **Every booking button opens the one shared booking dialog.** It is page-aware: its title is the page's reason line (rule 32a), then the offer's three real points, the time it takes, a primary button that opens the booking tool and a secondary "Send a question" that opens the contact page. Ctrl, Cmd, Shift and middle clicks keep the normal link. Not on the booking or contact pages themselves. **The host** is the person named in `growth.json` `call_host`: the dialog may show their photo and name, and no one else. [code: dialog.call]
133. **Every call to action reports itself.** Booking buttons, the booking dialog, the sticky bar and the exit offer push named events to the dataLayer (`cta_click`, `cta_dialog_open`, `cta_dialog_book`, `cta_dialog_message`, `sticky_cta_view`, `sticky_cta_click`, `exit_offer_view`, `exit_offer_click`, `exit_offer_dismiss`) with the page and the button's place. The tag manager has a Custom Event trigger for each, or none of them reach analytics. New tags still need the owner's yes (rule 103). [code: cta.events]
134. **Every dialog and bottom sheet opens over a dimmed backdrop, on a solid panel.** Tokens only; any blur has a solid fallback; the text on it passes AA (rule 59). [code: dialog.backdrop]
135. **After every FAQ comes one ask card:** "Still have a question? Ask it, or send it in writing." Its button opens the booking dialog (rule 132) with "Send a question" offered first. [code: faq.ask-card]
136. **A call to action inside a post is the shared ask card:** an icon, one line from the post's own topic, and the booking button. Never a bare link or a pasted booking URL. One per post, placed where the reader would want help, never as the answer to a fairness question. [code: post.ask-card]
137. **A post may carry `takeaways:` in its frontmatter: 3 to 5 one-line points.** The post layout draws them under the cover as a "Key takeaways" box with check icons. Each point restates the post's own text (rule 10); a point that is not in the text is not a takeaway. [code: post.takeaways]
138. **Every article has its reading aids:** a copy-link button on each H2 and H3 (the shared copy component, the `#id` URL); a thin reading-progress line; "x min left" beside "On this page" in a sticky side column from 1280px; yes and no marks in the text drawn as icons with words for screen readers. Reading time comes from one function: the main path's words at 230 a minute. [code: post.reading-aids]
139. **Every FAQ is one numbered box:** "N questions" with Expand all and Collapse all, a smooth open, the open item marked, the "+" turning into "x". Each question is an `<h3>` inside its `<summary>`. [code: faq.box]
140. **The footer has a call row and Back to top:** the page's reason line with the booking button, the brand line, the service links, the legal links, and a "Back to top" link. [code: footer.call-row]
141. **Motion is wanted on every page:** folds reveal as they scroll in, cards stagger in, key numbers count up, cards lift 2px on hover, timelines draw as you scroll. Durations come from tokens. How it is built stays rule 58: CSS and a little script, no libraries, reduced motion respected, no layout shift. [code: motion.reveal, motion.no-libs]
142. **A post's own Markdown gets its shapes by pattern:** a numbered how-to list is drawn as a steps timeline that draws as you scroll; a paragraph the post already labels "Bottom line:" or "Verdict:" gets a verdict shape, with no new words; one read-next card sits mid-article (halfway into a how-to, a third of the way into a list post) with the post's first related post: title, excerpt and minutes. [code: post.shapes]
143. **A ranked list post ("best ... software") opens with a lineup, and every tool named on a page shows its own logo.** The lineup has one row per pick: rank, logo, name and its own "best for" line, linking to its section. Logos come from the company's own site and live in one map (name, aliases, logo, source URL, date). Never a letter tile: a test fails on one. If no usable logo exists, show the name as text and tell the owner. [code: post.logos]
144. **Every list of posts and every hub card shows the post's cover as a thumbnail, and every hub has its own interactive, animated element with its state in the URL.** Never strip pictures to shorten a page; cut repeated text instead. [code: hub.cards, state.url]
145. **A post may mark a definition, a stat or a tip as a side note,** with one Markdown directive the content library reads. From 1280px it sits in the right margin beside its paragraph; below that it is an inline box. It restates the text (rule 10). [judgment: proxy claims.box-numbers]
146. **Contact carries the About page's trust story, and About and Contact link every service page by name.** The trust story uses only `BRAND.md` facts: who is behind the business, how the call or booking works, the plan terms. [code: core.service-links]
147. **A money page's first screen at 1280 to 1920 px is split: the words on the left, the page's own picture or tool on the right.** No empty half, no logo smaller than its row allows, no excerpt cut with "...". Look at the whole first screen at 1366 (rule 158) before handing it over. [code: hero.split, ev.shots-1366-390]
148. **Markdown copies of pages and `llms.txt` (waits for the owner).** If the owner says yes: every indexable page has a Markdown copy at `/<path>.md`, named in its head as `rel="alternate" type="text/markdown"` with the HTML page as its canonical, and every copy is listed in `/llms.txt`. Drafts and redirected pages never get one. [code: owner.waits-148]
149. **A real author page and a compact author box on every post (waits for the owner).** If the owner and the author say yes: every post ends with a compact author box (photo, name, a three-line bio, a link to the author's page); every byline and every Person node points at that page; the company is never a Person (rule 97). [judgment: proxy schema.people]

**K2. Search and structured data**

150. **One Organization node for the whole site:** `@id` `<site>/#organization`, defined once in the shared layout. Every page's structured data points to it (the publisher of an article, the provider and publisher of a service or software page). [code: schema.org-id]
151. **Tests guard the FAQ markup:** a test fails when the FAQPage markup is not built from the same list as the visible FAQ, or when two questions in one FAQ share 60% or more of their words. [code: faq.schema-equal, seo.faq-markup, repo.guard-tests]
152. **If AI answers or the top search results state a wrong fact on the page's topic (a price model, a limit), the page states the right one in its first screen, with its source.** It goes with rule 36b. [judgment: proxy ev.ai-baseline]
153. **The words-only rules get their checks:** `growth checks` or `growth tech_seo_check` measures title and description width (rule 81: 30 to 60 characters and 580 px or less; 120 to 155 characters and 990 px or less), spelling on titles, descriptions and alt text (rule 93), contrast on the built CSS (rule 59), and the 360, 390, 820 and 1024 px overflow (rule 68). [code: seo.title-desc, words.us-spelling]
154. **The speed baseline is written down and kept:** the Lighthouse scores of home, a money page, the blog, a post and contact are recorded in `SETUP.md`. A release that lowers a score or adds layout shift (CLS above 0.01) waits. The sticky bar, the exit offer and the interaction hints keep CLS at 0. [code: ev.speed] Measured on the production website after publishing, at the release stage (from a real project: speed can be tested later, once live on the production server).
155. **After each release, read the host's server errors (5xx) and the cron and API routes once.** Your own change never causes a server error. [judgment: proxy ev.release-check]

**K3. Process**

156. **A new or rebuilt page keeps every house feature of its type.** The list per page type is "House features" below the checklist. Before a page is called done, tick each one; a feature left out needs a reason in the pull request. A test per page type checks the built page for each feature's marker. [code: house.features, repo.guard-tests]
157. **No two sibling pages share a hero, a fold design or an animation.** Rule 30 covers the folds inside one page; this covers the service pages, hubs and posts of one kind. Compare siblings side by side before showing any of them. [judgment: proxy hero.unique, layout.folds-distinct]
158. **Before showing any page, look at every screen at 1366 and 390 px as a demanding designer:** no big blank gaps, no hollow cards, no empty state that looks broken, no picture shown larger than its file (blurry), and every card that sells has its own next step. Green tests are not good design. [judgment: proxy ev.shots-1366-390]
158a. **The look of a page is measured in a real browser at 1440x900 and 390x844, and these limits fail the gate.** Limits live in `growth.json` `layout` (defaults here). **White space (rule 158):** the gap between the content of two neighbouring folds is at most 2 x the section step + 24 px (step 80, so 184 px); a fold's empty bottom is at most the step + 24 px (104 px); the hero is at most its content + 66 px, and at most 1,100 px tall at 390 (not on `layout.legal_paths`, default `/terms*`, `/privacy*`, `/cookie*`). **Balance (rule 158):** two columns side by side (each at least 200 px wide, tops within 60 px) differ in content height by at most 1.30 times, a column under 25% of the other is nearly empty, and their tops are within 8 px (not on legal paths); a picture next to a text block has at least 60% of the text block's area (money and core pages); the last row of a card grid is full, centred or one wide card. **Buttons (rule 32b, 49):** at most one primary button (`.book-cta`, or a `.btn` in the colour of `cta.color_token`) on any screen, counting in steps of the viewport height and not counting dialogs or the sticky bar; no two primary buttons in neighbouring folds (the sticky bar and the footer do not count); a legal page has no primary button and no sticky bar. **Mechanics (rule 30):** one mechanic class (`layout.mechanics`, default flip, tabs, accordion, slider) appears in at most 2 folds. A page that cannot be measured (no Playwright, no server) is BLOCKED-SKIP, never a pass. [code: layout.fold-gap, layout.hero-height, layout.column-ratio, layout.picture-text, layout.card-orphan, cta.one-per-view, cta.spacing, cta.legal-quiet, engage.one-mechanic]
159. **Every product screenshot on a page has its capture date in the repo** (in its file name or the image map), **and when the product changes, its pictures change in the same round.** [code: img.capture-date]
160. **Click every button, tab, slider and toggle on the page in a real browser before you show it.** A control that does nothing on click is a broken page. [judgment: proxy ev.click-test]
161. **No rule is dropped because it is "not in our notes".** A rule is dropped only for a fit reason: it is tied to a tool, editor or server the project does not run, to another business's facts, brand or vendor, or to a kind of page the project does not have (say which). A feature the reader sees is never dropped for having been absent; it is adapted. Every drop is a row in the project's own "Dropped rules" table (see the end of this file) with its fit reason. [code: proc.dropped-reasons]

## Mistakes already caught, and the guard

Each row is a mistake that reached an owner once. Read it before you change a page.

| # | What was missed | The guard |
| --- | --- | --- |
| 0 | On a first money page the lead ran one audit and then built a quick-wins pass, skipping the money-page pipeline (dossier, owner concept check-in, prototype with an interaction, independent review). The owner caught it. | Rule 0: open the job's playbook first, copy its steps into the task, follow every one; a skipped step is raised with the owner before, never after. |
| 1 | The owner was told to look at a page before the server was running. | Rule 111. |
| 2 | An answer mixed topics and pointed at file paths. | Rule 129. |
| 3 | A share image was broken in social previews. | Rules 65, 108. |
| 4 | A comparison table lost a column off the screen. | Rules 48, 68. |
| 5 | A wide card inside a wide box ran off the screen. | Rule 44. |
| 6 | Clicking Home from an article moved the logo and menu, or landed part-way down. | Rules 43, 107, 98. |
| 7 | A page's main claim and a takeaway box were false because nobody checked the source. | Rules 5, 6, 10. |
| 8 | An agent shipped placeholder text. | Rule 11. |
| 9 | Work in progress for a redesign leaked onto every page. | Rule 120. |
| 10 | A design agent started its own helper agents. | Rule 126. |
| 11 | Repeated permission prompts and asking again for approved work. | Rules 125, 116. |
| 12 | The same question appeared three times in one FAQ; the FAQ markup did not match the page. | Rule 96. |
| 13 | A page's description was copied from another page. | Rule 82. |
| 14 | Dark text on a dark ground. | Rule 59. |
| 15 | The contact page left half the screen empty. | Rules 38, 39. |
| 16 | An About page read as buzzwords, so the owner could not trust it. | Rule 29. |
| 17 | A vendor price was copied from a pricing page opened on a default team size. | Rule 7. |
| 18 | A crawler asked for hundreds of addresses that did not exist, because of a placeholder link. | Rule 92. |
| 19 | A real key was saved in a template file. | Rule 119. |
| 20 | Checks left temporary folders until the disk filled. | Rule 112. |
| 21 | Features the owner had agreed (the sticky call bar, the "+" link previews, and more) were dropped from a first rulebook as "not in our notes"; the owner kept finding them missing. | Rules 156, 161 and "House features"; section K. |

## Open questions for the owner

Open questions belong to the project, not to the book. Keep them in the project's `docs/tasks.json` (`growth tasks
question "<text>"`), one decision each, with a safe default so work never waits. Typical ones: may pages say "free"
or "no obligation" (rule 36); whose photo may the booking dialog show (rule 132); may the blog have an author page
(rule 149); do you want `llms.txt` and Markdown copies (rule 148).

## Dropped rules

A project that leaves a rule out records it in its own `PAGE-RULEBOOK.md` or `OWNER-RULES.md` as a row: the rule
number, and the fit reason (rule 161). Examples of a good reason: "this site has no blog, so rules 53 and 54 do not
apply" or "the stack has no adapter yet, so rule 98 is checked by hand". "Not in our notes" is never a reason.

## Change log

| Date | Version | What changed |
| --- | --- | --- |
| 2026-11-20 | 2.4.2 | Rule 158a leaves out a tool's or a menu's own rows and grids (a table of contents beside the text, a calculator's options); the contact page keeps its form first (38) without a hero limit. |
| 2026-11-19 | 2.4.1 | Legal pages (rule 49) are exempt from the booking-button rules (32a) and the act fold and surface rhythm of 36f; the footer call row (140) accepts a secondary button and matches topic links with or without the trailing slash. |
| 2026-11-19 | 2.4.0 | New rule 158a: measured design limits (white space between folds, hero height, column balance, picture size, card orphans, one primary button per screen, spacing of asks, quiet legal pages, one mechanic per page), read from a real browser by `layout.*`, `cta.*` and `engage.one-mechanic`. A design audit of a real site found these on pages that passed every other check. |
| 2026-11-18 | 2.0.1 | Review fixes: fold attribute is `data-fold` and the surface is `geo-lines` (as the gate reads them); the page's main type can never be only the site's Organization (rule 36b, 95); checks renamed `repo.retired-410` (rule 76), `proc.remote-private` (a project may have a private remote) and `core.service-links` (rule 146); every rule text in the registry is copied from this file's headings. |
| 2026-11-18 | 2.0.0 | Generic edition for any website: project facts moved to `BRAND.md` and `growth.json`; tool commands are `growth <tool>`; rules that read code are marked "(Next.js adapter)". Rule numbers and check tags unchanged. |
| 2026-11-18 | 1.6.16 | Rule 124a adds `repo.no-unused-code`: tsc `--noUnusedLocals --noUnusedParameters` on the files the branch changed. A sweep found unused names left by page rebuilds, one of them a fix helper imported but never called. |
| 2026-11-18 | 1.6.15 | Rule 81: when Search Console has too little data for a page (its most-shown search under 10 views), `seo.title-query` uses the first 2 `target_searches` in the page's plan. A page had 3 tracked searches of 1 view each, one a rival's domain; no honest title could pass. |
| 2026-11-17 | 1.6.14 | Rule 70 is measured in code (`ui.phone`, `phone_check`): text under 12 px on screen, header, menu and footer targets under 24 x 24 px, clipped text and scroll boxes with no cue at 360, 390, 820 and 1024. Found by eye in a final look; now caught by the gate. |
| 2026-11-17 | 1.6.13 | Rule 0a: pre-flight before the build (`ev.preflight`); the gate runs after every fold commit. |
| 2026-11-17 | 1.6.12 | Rule 154 (speed) runs at the release stage, on the production site. |
| 2026-11-17 | 1.6.11 | New rule 124a: a rework removes what it replaced (`repo.no-dead-files`). |
| 2026-11-17 | 1.6.10 | New rule 36l: every page has one named, linked author (`words.named-author`). |
| 2026-11-17 | 1.6.9 | New rule 36k: never state where the business or its people are, when told not to (`words.no-location`). |
| 2026-11-17 | 1.6.8 | New rule 36j: AA contrast in every state, measured in a real browser (`ui.contrast-states`). |
| 2026-11-17 | 1.6.7 | New rule 36i: every page archived live before and after it changes (`ev.archive-before`, `ev.archive-after`). |
| 2026-11-17 | 1.6.6 | New rule 36h: a fold-by-fold detail plan before any page work (`ev.fold-plan`). |
| 2026-11-17 | 1.6.5 | New rule 36g: every picture and chart reads in 3 seconds. |
| 2026-11-17 | 1.6.4 | New rule 36f: every fold has its own surface, chosen by its job (`page.surfaces`). |
| 2026-11-17 | 1.6.3 | Rule 36c punctuation after the "+" (`links.punct`); new rule 36e, ticks inside a circle (`icons.check-circle`). |
| 2026-11-17 | 1.6.2 | Rule 36c spacing: every in-text link keeps its space before and after (`links.spacing`). |
| 2026-11-17 | 1.6.1 | Rule 36c colour and glow: one link-blue token, underlined; the preview card glows in the same blue (`links.blue`, `links.card-glow`). |
| 2026-11-17 | 1.6.0 | Rules are code: every rule carries `[code: <check>]` or `[judgment: proxy <check>]` from the registry, enforced by `gate`. Loose words replaced by numbers or must and never. Includes rules 32c and 88b. |
| 2026-11-17 | 1.5.0 | Section K restored: rules 132 to 161, "House features" per page type, rule 161 (no rule dropped for "not in our notes"). |
| 2026-11-17 | 1.4.0 | Rules 35b (exit offer), 36a (interaction hints), 36b (GEO/AEO), 36c ("+" link previews), 36d (technical SEO check). |
| 2026-11-17 | 1.3.0 | Rules 32a (a reason to act on every booking button), 32b (one primary button style), 35 (sticky bar). |
| 2026-11-17 | 1.2.0 | Rule 0 added: never take shortcuts; follow every step of the job's playbook. |
| 2026-11-17 | 1.1.0 | Rule 105 rewritten: only the checks the change touches. |
