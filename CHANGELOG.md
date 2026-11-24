# Changelog

The kit and the book share one version number. Dates are written year-month-day.

## Unreleased

## 2.8.5 - 2026-11-23

Finding classes an independent reviewer kept finding on pages the gate passed (#99, #100).
- `layout.folds-distinct` (rule 30): two folds whose cards have the same form (tag, classes, inner shape) fail on any surface and at any distance; the message says whether the surface is the same. `layout.card_repeat_ok` allows a pair with a reason.
- `words.internal-labels` (rule 11): editor notes such as "the cost fold above", "see the X fold", "this section", a "Checked/Verified <date>" stamp standing alone, "as of <date> (internal)". `words.internal` and `words.byline` are configurable; an "Updated <date>" byline and a source line's check date are not notes.
- New check `words.named-repeats` (rule 28): a named phrase (3+ capitalised or technical words, or 2 technical tokens such as "HL7 FHIR") in `repeat_folds` or more folds. Skips what fact-repeats skips; honours `repeat_ok`.
- `layout.card-orphan` (rule 158a): a lone pill on the last wrapped row at 390 px after a row of 3 or more, in the hero and first fold.
- New checks `layout.text-overflow` (text past its card or drawn box at 1024, 1440 and 390), `layout.under-header` (text under the sticky header at scroll 0) and `layout.breadcrumb-390` (first crumb clipped or scrolled out). (#100)
- `growth ready`: a preview worktree with uncommitted or untracked (not ignored) changes is NOT READY: the build may hold an edit HEAD does not. (#100)

## 2.8.4 - 2026-11-23

- New check `words.own-copy` (rule 157a, also under "Money pages are unique"): a page's folds must not copy another page of the site word for word. An independent reviewer found a "hire experts" page whose 3 folds copied a sibling page (68 to 88% of their 7-word runs); the gate had no cross-page wording check. Each fold of 40+ words is compared, run by run, with every fold of every other page in the built output (`build_dir`): FAIL from 50% shared with one other fold, WARN from 30%; it names the other page and fold and quotes one shared run. Header, nav, footer, forms, buttons, client reviews and runs that 3+ pages share in short blocks are left out. No build is a SKIP. Set it in `growth.json` `words.own_copy` (`fail`, `warn`, `min_words`, `shared_pages`, `shared_max_words`); exceptions go in `words.own_copy_ok` as `{path, fold, reason}` (a reason is required). (#97)
- `growth ready`: a fresh check on a build older than the code is NOT READY. With `build_dir` set, the page's built file must be newer than the moment HEAD last moved, and the page must be in the build; before, a build step that silently did not run let the gate check the old build while the ledger named the new commit. (#98)
- Book 04: a checklist from past verdicts (`research/reviews/pre-review-checklist.md`) is run by the builder before a page goes to review, until each finding class has its check.
- Tests: `tests/test_release_2_8_4_own_copy.py`, `tests/test_release_2_8_0_core.py::test_a_fresh_check_on_a_stale_build_is_not_ready`.

## 2.8.3 - 2026-11-23

- words.fact-repeats (rule 28): Key takeaways, a contents list and FAQ answers are not read as second statements of a fact (rules 137, 96).
- links.anchor-unique (rule 90): a language switch to the page's own copy ("View the US site") is not an anchor to another page.
- Test: `tests/test_release_2_8_3_repeats_switch.py`.

## 2.8.2 - 2026-11-23

- links.anchor-unique (rule 90): a page and its language copy under a locale folder (`/en-us/`, `/fr-ca/`) count as one page, so the same anchor to both is not flagged.
- Test: `tests/test_release_2_8_2_locale_anchor.py`.

## 2.8.1 - 2026-11-23

- `growth ready --batch ...` reaches the batch: the front door took `ledger` for a page path and gated a page called /ledger. Verdicts stream as they land. `growth ready <page> --repo <worktree>` passes `--repo` on. (#96)
- Test: `tests/test_front_door.py::test_ready_batch_and_repo_reach_the_ready_tool`.

## 2.8.0 - 2026-11-23

Many pages at once. One site ran 12 pages through 4 review rounds in a day and accepted none: `ready` checked one page at a time (about 92 s each), any commit made every page not READY, and builders and the reviewer waited for each other. (#93, #94, #95)

Core (#93):
- `growth ready --batch FILE|ledger --jobs N [--stale-only]`: many pages side by side, each its own ready run (same verdict as a single run); verdicts print as they land; the full log goes to `journal/runs/ready-batch-<stamp>.log`. `--jobs` defaults to growth.json `ready_jobs`, else 3. `--repo` is passed on to every page. 12 pages: 3.2 min (was about 25).
- READY holds on the same commit, or on the same output: the ledger keeps the page's fingerprint of the built HTML and shared CSS/JS, so a commit that does not change a page keeps it READY. A build older than the last commit never vouches. `ready --list` says why a page is READY.
- Proofs must live in the project, the site repo or the kit: a proof that points outside (a scratch folder) is refused.
- ev.task-steps: the golden-rule and check-in-2 steps may come after READY.
- ev.brief: a steps-log rule row marked "(no page rule)" (a process rule) no longer makes every page brief stale.
- Book: "Many pages at once: the page flow" (04-lanes-and-releases); money-page playbook step 3a is a fact inventory and fold plan, reviewed before the build.
- Review fixes: a build only vouches when it is newer than the moment HEAD last moved (a fast-forward or checkout to an older commit no longer leaves an old build trusted); the commit and output are read before the gate, and a change while it runs is NOT READY; a page that fails is kept in `journal/ready-failed.json` so `--batch ledger` checks it again; duplicate batch lines run once; a preview-repo problem is reported once for the batch; a proof path that climbs out with `../` is refused, and a site path such as `/pricing/index.html` is not taken for a file; "(no page rule)" and "(no new rule)" count only in the What was done column.
- Tests: `tests/test_release_2_8_0_core.py`.

Checks (#94): the finding classes a reviewer kept finding by hand.
- New check words.fact-repeats (28): a fact in 3 or more folds, or a long sentence two folds share. growth.json `words.repeat_ok`, `repeat_terms`, `repeat_folds`, `repeat_sentence`; call-to-action reason lines are skipped.
- New check words.internal-labels (11): the team's own process words in the page text. growth.json `words.internal`, `internal_ok`.
- New check migrate.old-terms (36): short-list items must be on an archived old page of the site or in BRAND.md. Site-wide by default (an item found only on another old page is a WARN); `words.old_terms_scope: "page"` makes that a FAIL; `old_terms_ok`.
- New check layout.box-fill (158a): a card or panel whose content leaves its bottom half (55% of the height) or its right half (45%, boxes 320 px and wider) empty. growth.json `layout.box_*`.
- Tests: `tests/test_release_2_8_0_{fact_repeats,internal_labels,old_terms,box_fill}.py`.

Speed (#95):
- Faster browser checks, same catches. `ui.contrast-states` (36j) and `ui.phone` (70) took 67 s of one page's 92 s gate run (49.6 s and 17.5 s), and `ready` runs them on every page. (speed)
  - `contrast_check`: one browser for both widths (a fresh page per width); controls that look alike are measured once. The look-alike signature is the tag, class, style attribute, role / type / disabled / aria-current / -expanded / -pressed / -selected, first or last child, the text-bearing child, and for every ancestor its tag, class, style attribute and data-* attributes, plus which of the page's attribute selectors, ids and position or sibling selectors (`:nth-child`, `:has`, `+`, `~`) apply to it, plus the colours it reads at rest. The problem list still names every control. The scroll is the browser's own `scrollIntoViewIfNeeded` (same final position, 15 to 20 ms less per control).
  - Measurements are kept under `<project>/.cache/contrast/` (a `.gitignore` of `*` inside keeps it out of git; entries unused for 30 days are removed), keyed by sha256 of the signature, the width, a hash of every stylesheet (linked, inline, imported), the browser version and the tool's own code. Any CSS change gives new keys. `growth contrast_check --no-cache` and `growth gate page --no-cache` skip it; growth.json `"contrast_cache": false` switches it off; `--no-dedupe` measures every control (the old way). `--width` can be repeated.
  - A hover that did not take (the mouse missed the middle of a wrapped link, or a sticky bar covered the control) is retried at each line of the link, then with the control brought to the middle of the screen, then on the next look-alike control; the hover is let go before focus is read. A stored measurement is therefore never a miss, and focus never shows a leftover hover (before, the same control could read differently from one run to the next on a busy machine). A group whose hover or focus could not be read at all is measured again on every run, never kept.
  - `phone_check`: one browser for all four widths (a fresh context per width), measured side by side: about 4 s instead of 14, with the same answers on every page tried, failing and passing. Each page keeps all of its own settle waits. growth.json `"phone_parallel": false` or `phone_check --serial` measures them one after the other.
  - `growth gate page --profile`: after the normal output, each check's seconds (slowest 25) and the total, on stderr.
  - `contrast_check` review fixes: a stylesheet or script that cannot be read (cross-origin fetch fails) turns the cache off for that page (measured live, one line on stderr) instead of hashing fixed text.
  - `contrast_check` review fixes: the cache key now includes a hash of the page's JavaScript (inline text and external script sources), so a script that adds a class on hover or focus cannot leave stale passes.
  - `contrast_check` review fixes: more than 4000 selector probes no longer cuts the list silently; grouping of look-alike controls is turned off for that page with a one-line warning on stderr. The dead first `JS_COLLECT` was removed.
- Not changed, on purpose: `tags.not-local` waits 5.5 s by design (a tag manager may load 4 s late) and `repo.no-unused-code` is the site's own `astro check` or `tsc`; neither can be shortened without catching less.
- Tests: `tests/test_contrast_phone_checks.py`.

## 2.7.6 - 2026-11-23

- ready: `--repo <worktree>` passes the page's worktree to the gate (repo.branch and the evidence dates read the branch the page is built on).
- link_graph crawl --base: always reads the preview's own sitemap (not only on no-crawl sites), so an unreleased page is crawled and its link checks can run before release.
- Tests: `tests/test_ready_fail_closed.py::test_repo_flag_reaches_the_gate`, `tests/test_live_site_rule.py::test_a_preview_crawl_reads_the_previews_own_sitemap_on_a_crawl_ok_site_too`.

## 2.7.5 - 2026-11-23

- links.blue: the '+' marker CSS is found by its own class (`.link-plus`, `.lc-plus`), not a BEM modifier such as `.leadcard--plus`; CSS comments are removed before colours are read.
- repo.guard-tests: growth.json `guard_tests.all_pages` names one data-driven test that loops over every built page; it counts for every page when it tests the house features and FAQPage markup.
- Test: `tests/test_release_2_7_5_links_guard.py`.

## 2.7.4 - 2026-11-23

- links.no-utm skips `//`, `/* */`, `<!-- -->` and `#` comments, so a comment that mentions an old utm-tagged link no longer fails the page.
- Test: `tests/test_release_2_6_0_any_stack.py::test_a_utm_link_in_a_code_comment_is_not_a_utm_link`.

## 2.7.3 - 2026-11-23

- links.no-utm: only source that writes `?utm_` / `&utm_` into an address fails; code that reads the landing URL's utm tags for attribution passes.
- copy.shared: a `mailto:` or `tel:` link with no address or number (an "Email it" share action) needs no copy button.
- icons.check-circle: a tick inside a JavaScript regex literal (emoji recognisers) is not a bare tick.
- repo.retired-410: a retired group passes when its name and a 410 sit within 5 lines of each other (nginx rules name groups in one pattern).
- Tests in `tests/test_release_2_6_0_any_stack.py`.

## 2.7.2 - 2026-11-23

- hero.unique (157): an icon inside a button or call-to-action link (the booking button's arrow) is not the hero's picture or motion, so a hero without its own drawing is no longer counted as having one. (#92)

## 2.7.1 - 2026-11-23

- New check layout.line-length (45): characters per rendered line of long paragraphs in the reading flow (200+ characters, not in cards, asides, tables, figures or FAQ), measured at 1440. The median must sit in growth.json `layout.line_chars` (default 55 to 90: rule 45's 60 to 80 with an allowance for rounding). (#91)
- Test: `tests/test_release_2_4_0_layout.py`.

## 2.7.0 - 2026-11-23

- New check ev.fold-plan-own (36h): a fold plan is written for its own page. A field answer that stands word for word in the plans of 3 or more pages fails; the icons and check fields may repeat. One site had 86% of its plan answers copied from a template. (#90)
- New check ev.fold-plan-match (36h): the built page follows its plan fold by fold: the data-surface and data-job named in the plan, the headline's words in the built heading, a call to action present or absent as planned, controls and a picture when the plan describes them. (#90)
- Test: `tests/test_release_2_7_0_fold_plans.py`.

## 2.6.7 - 2026-11-22

- hero.split ignores script, style, template and aria-hidden elements when it looks for the hero's columns; an inline script or a hint beside the grid no longer hides a real words + tool split.
- Test: `tests/test_release_2_6_7_hero_split.py`.

## 2.6.6 - 2026-11-22

- layout.picture-text measures a `<figure>` as the picture as a whole (its box), not the largest small icon inside it; a document-style figure no longer fails on its 14px icon.
- layout.column-ratio and the other layout checks skip tables: a table row is not two page columns.
- Test: `tests/test_release_2_4_0_layout.py::test_a_figure_is_measured_as_a_whole_and_table_rows_are_not_columns`.

## 2.6.5 - 2026-11-22

- claims.box-numbers (10): text inside <time> (a byline or card date) is no box number. (#89)
- layout.column-ratio (158a): inline children (links in a wrapped paragraph) are never a two-column row. (#89)
- Tests: `tests/test_release_2_6_4_box_time.py`, `tests/test_release_2_4_0_layout.py`.

## 2.6.4 - 2026-11-22

- inventory: growth.json `pillars_are_money` (default true). False marks a silo's top page a money page only when it is listed in `money_core`, so a pillar that maps its cluster is judged as a hub (rule 26).
- Test: `tests/test_release_2_6_4_pillars.py`.

## 2.6.3 - 2026-11-22

- words.call-length reads each text element on its own, so a tool's "2 minutes" next to "Free 30-minute call" is no longer read as the call length (22 false FAILs on a real project).
- schema.house-types: the home page needs no BreadcrumbList, matching crumbs.visible.
- Test: `tests/test_release_2_6_3_call_home.py`.

## 2.6.2 - 2026-11-22

- layout.card-orphan (158a): only a grid of like children (most share one tag and first class) is a card grid; a hero laid out as a heading, a picture and an answer box is a layout. (#88)
- links.blue (36c): a link rule scoped to a dark surface may use a light --*link* token, because the light-mode link blue fails contrast on dark ink; never the brand or CTA colour. (#88)
- Tests: `tests/test_release_2_4_0_layout.py`, `tests/test_release_2_6_1_links_logo_home.py`.

## 2.6.1 - 2026-11-22

- links.blue (36c): growth.json `links.not_text` (regex alternatives) names a site's own menu, contents or badge classes that are not running text. Hover and focus colours are left out of the colour test (rule 36j). The dark link colour is required only when the site has a dark theme (prefers-color-scheme: dark, [data-theme=dark], .dark). (#87)
- repo.logo-untouched (42): only logo-named files (logo, lockup, wordmark, brand-mark) count. A brand folder also holds icons such as a tick. (#87)
- links.up-across (89): the home page sits above every silo; it passes when its content links down to each silo's top page. (#87)
- Test: `tests/test_release_2_6_1_links_logo_home.py`.

### 2.6.0

- The checks that read the site's code (needs="repo", about 45 of them, once written for Next.js) now run on any stack whenever a site checkout is given, and without one they print a blocked SKIP (never a pass). Next.js behaviour is unchanged.
- A non-Next page's source tree is its route file under src/pages (or the catch-all route), its content file and every import; the site's CSS is what the served page loads, else src/**/*.css and the <style> blocks.
- Shared components are found on any stack (new `ctx.component(name)`, `gatelib/components.py`): growth.json `components`, else the Next.js default path, else a file under src/ whose name matches in kebab or Pascal case. repo.shared-components checks that the page's tree holds the component file, copy.shared takes the one clipboard component plus its helper, links.cards / links.punct / links.card-glow use the site's own card class and marker and find the guard test by name, icons.check-circle accepts a Tick in any source extension (.astro included), repo.guard-tests and repo.scroll-test find tests anywhere (**/*.test.*, tests/**).
- links.blue accepts a "+" drawn as a `::after` on the link itself (no -plus class needed).
- Internal-link checks (links.inbound 88, links.plan 88a, links.up-across 89, links.anchor-unique 90, links.no-redirect 75) compute the same flags from inventory/link-graph.db on a stack with no app/ folder (`gatelib/graph_links.py`). A missing or stale graph is a blocked SKIP that names `growth link_graph crawl --base <preview>`; the check never writes into the project. link_map.py stays the Next.js path.
- repo.logo-untouched (42): a diff that changes only the text of an aria-label or title is allowed; any path, shape or image change still fails. The branch's file list now leaves out a file whose diff against the base is empty.
- repo.no-unused-code (124a) runs the site's own checker (`astro check` with @astrojs/check, else tsc with a tsconfig.json); when the stack has neither it is a blocked SKIP that names what is missing, not a FAIL telling the reader to install node_modules. repo.no-dead-files reads src/** on a non-Next stack.
- New growth.json keys: `components` (copy, link_cards, link_cards_css_class, link_cards_marker, sticky_cta, call_dialog, exit_offer, tick, tests), `commit_identity.email_sha256` (the identity by the sha256 of its address), `commit_style.since` (older commits are history), `link_graph.max_age_hours` (default 24).
- Test: `tests/test_release_2_6_0_any_stack.py`; `tests/test_demo.py` now expects the repo checks to run with --repo and to be blocked without it.

## 2.5.0 - 2026-11-22

- hero.unique (157) reads the served page on every stack and now covers posts too. It compares the first screen with its siblings on the same preview: the same depth and either the same cluster or the same kind of page across clusters (every .../experts). A shared hero design (the composition: the tag and class tree plus each drawing's shape list), the same picture, or the same animation fails. A hero with no picture, tool or motion of its own fails. It used to be Next.js only, and a static site shipped 128 pages on 14 hero designs. (#85)
- house.features (156, 161) warns about house features the stack cannot check yet, instead of counting them as passed in silence.
- Test: `tests/test_release_2_5_0_hero_unique.py`.

## 2.4.11 - 2026-11-22

- New check words.h1-clean (84): the visible H1 reads once. It fails when one element's text runs into the next with no space ("...and CostFeatures, Compliance, Cost") or a 3-4 word phrase is shown twice; aria-hidden decoration is left out. A live H1 kept by rule 74 (inventory h1) that repeats a phrase only warns. A hero template had appended its highlight label inside the H1 on 32 pages that passed every other check. (#84)
- Test: `tests/test_release_2_4_11_h1_clean.py`.

## 2.4.10 - 2026-11-22

- words.question-title (20): only a yes/no question H1 ("Is ...?", "Can ...?") must open with yes, no or "it depends". A what/how/why H1 ("What Is FHIR?") passes with a direct first line and fails on a preamble ("In this guide...", "Let's...", a question). (#80)
- Test: `tests/test_release_2_4_9_title_question.py`.

## 2.4.9 - 2026-11-22

- seo.title-query (81) vs rule 74: when the page still shows its live title (inventory/inventory.json) and the only problem is the missing query, the check warns with a proposal for the owner instead of failing. Rule 74 keeps a ranking title until the owner approves a change. (#79)
- words.question-title (20): the first line under a question H1 skips bylines, breadcrumbs, kickers and reading-time lines. (#79)
- Test: `tests/test_release_2_4_9_title_question.py`.

## 2.4.8 - 2026-11-22

- Evidence freshness: growth.json `evidence.fresh_on: "page_html"` keeps a page's shots, click test and share preview current while its own markup is unchanged, even when the shared CSS/JS bundles were rebuilt by another page's merge. The default `"built"` stays strict. Fingerprints now also store `page` (the markup with hashed asset names neutralised); old fingerprints fall back to `html`. The measured layout checks still run live on every gate. (#78)
- Test: `tests/test_release_2_4_8_fresh_on.py`.

## 2.4.7 - 2026-11-22

- Research records: a page with Search Console impressions but only anonymised queries passes the search section with a written `queries_none` reason (`growth research none <path> --key K queries "why"`), the way `paa_none` works. The record still needs the window. Before, such a page could never be READY without invented query rows.
- tests/test_harness.py: a kit path exported in the shell no longer makes the A12 test pass by accident (it failed the pre-commit run whenever GROWTH_KIT was set).
- Test: `tests/test_release_2_4_7_queries_none.py`.

## 2.4.6 - 2026-11-22

- ev.brief (0): only a steps-log row that sets or changes a rule makes a page's brief stale. A row whose "What was done" says "(no new rule)" (a question, a status request) does not; the check compares the newest rule row's ID with the IDs the brief holds. One owner question had dropped every READY page.
- Fold plans: a true short answer ("plain", "sage tint") counts; placeholders (tbd, todo, ?, -, same, see above, a bare n/a) do not. It was a 12-character floor.
- `growth fold_plan init --folds` wins over `--url`, so a new page's plan can be written before the page is built.
- `growth tasks <command> --help` prints help and never runs the command (`tasks add --help` created a task).
- Test: `tests/test_release_2_4_6_brief_plan_tasks.py`.

## 2.4.5 - 2026-11-22

- page.surfaces-paint (36f): the browser helper drops no pseudo argument, so a surface painted on `::before` or `::after` is seen (#72). It was a false FAIL on every geometry fold of a site that draws its patterns on `::before`.
- hub.cards (144): a drawn cover counts, whether an inline svg, a sprite `<use>`, a `<picture>` or an element marked `data-cover` (#73).
- Tests: `tests/test_surfaces_paint.py` (a `::before`-only surface), `tests/test_release_2_4_3_cards_folds.py`.

## 2.4.4 - 2026-11-21

- page.surfaces and page.surfaces-paint (36f) on posts: neighbouring folds whose job is `read` (the article body, one per heading) may share the plain surface, and 2 surface kinds are enough; the header and the closing call still differ from their neighbours. Money and service pages keep the full rhythm.
- layout.card-orphan (158a) skips a wrapping flex row whose children draw no box (a post's author / date / read-time line); display:grid is always measured.
- Tests: `tests/test_release_2_3_0_house_live.py::test_post_body_folds_may_share_plain`, `tests/test_release_2_4_0_layout.py::test_text_meta_row_is_not_a_card_grid`.

## 2.4.3 - 2026-11-20

- hub.cards (144) judges only the hub's post cards: cards marked `data-post-card`, else cards linking into the hub's own cluster path. Service cards to other hubs and ask, brief and form cards are no longer counted.
- layout.folds-distinct (30): the fold signature ignores markup that changes nothing for the reader. A single-child wrapper collapses into its child and div/span/aside/nav are one generic box, so extra wrapper tags cannot make look-alike folds pass. The signature now reads 5 levels.
- Test: `tests/test_release_2_4_3_cards_folds.py`.

## 2.4.2 - 2026-11-20

- layout.column-ratio and layout.card-orphan (158a) leave out a tool's or a menu's own layout: rows and grids inside growth.json `layout.exempt` (default: nav, form, fieldset, [data-tool], [role=tablist], [role=radiogroup], .toc, [data-layout-exempt]), and a two-column row whose side column is a table of contents or sticky.
- The conversion page (rule 38: its form is the first fold) skips layout.hero-height and cta.label-same; dialog.call matches the contact path with or without the slash.
- seo.title-query (81): a plan with `target_searches` and `use_target_searches: {"why": ...}` is judged on its own targets, for a page whose Search Console searches the duplication register gives to another page.
- Tests: `tests/test_release_2_4_2_contact_toc_title.py`, one more case in `tests/test_release_2_4_0_layout.py`.

## 2.4.1 - 2026-11-19

- footer.call-row (140): topic links match with or without the trailing slash, like core.service-links; a secondary-styled footer button counts, so the closing screen can keep one primary (158a).
- cta.label-same and cta.reason-line (32a) skip legal paths (growth.json layout.legal_paths), and page.surfaces (36f) asks a legal page for no act fold, no 3-fold minimum and no 3 surface kinds: legal pages stay plain with a quiet contact link (rule 49).
- Test: `tests/test_release_2_4_1_footer_legal.py`.

## 2.4.0 - 2026-11-19

- New measured design checks in `kit/tools/gatelib/c_layout.py` (rule 158a, with 30, 32b and 49). One headless-browser pass opens the page at 1440x900 and 390x844 (reduced motion, animations off) and every check reads the same boxes. A design audit of a real site found white space, unbalanced columns and crowded buttons on pages that had passed every other check.
- layout.fold-gap, layout.hero-height, layout.column-ratio, layout.picture-text, layout.card-orphan, cta.one-per-view, cta.spacing, cta.legal-quiet, engage.one-mechanic. Limits come from growth.json `layout` (section_step 80, hero_extra 66, hero_max_mobile 1100, column_ratio 1.30, nearly_empty 0.25, top_tolerance 8, picture_ratio 0.60, mechanics_max 2, legal_paths, mechanics). A page that cannot be measured is BLOCKED-SKIP, never a pass. They are not in the HOUSE lists.
- Test: `tests/test_release_2_4_0_layout.py`.

## 2.3.0 - 2026-11-19

- sticky.present (35), exit.present (35b) and page.surfaces (36f) now read the served page on every stack. They were in the Next.js adapter only, so on any other stack they printed SKIP and pages passed with no sticky bar, no exit offer and no fold surfaces (found on a real Astro site whose owner called the CTAs weak and the folds unbalanced). The code-level parts (the shared component in the page's source tree) still run on Next.js only. New `page_css(ctx)`: on other stacks it reads the page's inline styles and linked stylesheets from the same local server.
- house.features (156, 161): a house feature switched off in growth.json `features` now counts as missing unless growth.json `features_dropped` gives its fit reason. A reader-visible feature is never dropped silently. The project template and the demo carry `features_dropped`.
- Test: `tests/test_release_2_3_0_house_live.py`.

## 2.2.7 - 2026-11-19

- claims.head-figures and claims.box-numbers skip drawn examples too (an `<svg>`, `aria-hidden="true"` or `data-example`), the same rule ev.fact-sources has had since 2.2.6. The rule now lives once in `domx.is_example` / `domx.in_example` and `domx.text(..., skip_examples=True)`. Test: `tests/test_release_2_2_7_examples.py`.

## 2.2.6 - 2026-11-19

- ev.fact-sources: text inside a drawn example (an `<svg>`, an element with `aria-hidden="true"`, or one marked `data-example`) is not a claim, so made-up numbers in an example screen ("You owe $42.10") need no source. Test: `tests/test_release_2_2_6_examples.py`.

## 2.2.5 - 2026-11-19

- ev.fact-sources: a page's own computed reading time ("11 min read", "N min left", "Reading time: N minutes") and its table of contents are not stats. Test: `tests/test_release_2_2_5_read_time.py`.

## 2.2.4 - 2026-11-19

- `post.takeaways`: the box is the INNERMOST element that says "Key takeaways" and holds list items (or the one whose aria-label says it), not the page wrapper, so a guide with 130 list items elsewhere no longer counts them all.
- `post.ask-card`: only a class that is exactly `ask-card` or `next-step` (or ends `-ask-card` / `-next-step`) is an ask card; an `<a class="ask">` card-foot link no longer counts.
- `form.bot-guard`: a GET form whose action is an in-page `#anchor` or the conversion path only prefills the real lead form and is skipped; POST forms and every other form keep the rule.
- `claims.box-numbers`: a box number is looked for in the page text WITHOUT that one box (before, every copy of the box text was removed, so a number could never be found in the prose); a trailing full stop or comma ("2026.", "99.") is dropped from the number. `box_ignore` selectors like `aside.author` and `aside.howwe` are tested to apply.

## 2.2.3 - 2026-11-19

- Evidence freshness by what the page renders: evidence (a click-test or share-preview or speed journal entry, and screenshots) is stored with a fingerprint of the page as served (new `kit/tools/fingerprint.py`, `growth fingerprint show|record`; `growth journal add|run --url` for a preview address): the sha256 of its built HTML (build ids, build times, nonces, comments and timestamps stripped) plus the sha256 of the CSS and JS files it links, read from `build_dir` (or fetched from the preview URL); nothing is rebuilt. When the fingerprint still equals the page now, the evidence is fresh whatever commits touched `src/components` or `src/data`. Evidence with no fingerprint (old evidence) keeps the commit-based rule (a journal entry also still counts when it is filed after the last change). Shots take their fingerprint from `research/*-shots/fingerprint.json` (`growth fingerprint record <page> --key <key>`).

## 2.2.2 - 2026-11-19

- `words.no-customers`: new growth.json `words.implied_proof_allow` (`[{"pattern", "why"}]`): an entry with a why removes that implied-proof pattern ("trusted by", "case stud(y|ies)", ...) for a site whose owner approved it; `aggregateRating` in the same list lets structured data carry a rating; customer names in `words.hidden_customers` still FAIL, also after an allowed "trusted by"; an entry without a why FAILs. Default empty, nothing changes.
- `ev.fact-sources`: "case study" and "case studies" are a content type, never a study claim (real study sentences still count).
- `ev.fact-sources`: postal addresses and phone numbers hold no stats: text inside `<address>`, `tel:` link text, street numbers ("222 East Main St"), "Suite B-2", ZIP codes after a state code ("AZ 85201"), Canadian postal codes and phone numbers ("+1 (623) 555-0100", "623-555-0100", international) are skipped.
- `cta.reason-line` (rule 32a): on the conversion page (growth.json `conversion_path` or `cta.contact_path`) the main form with a submit button counts as the primary booking action; its reason line is looked for before its submit or after the form. Header buttons never counted. Other pages are unchanged.

## 2.2.1 - 2026-11-19

- READY asks a trailing-slash site for `/x/` (growth.json `trailing_slash`, else the slash the caller typed), not `/x`, so there is no 301 and the technical SEO checks no longer print "input missing"; the page key and ledger stay without the slash (`ready.fetch_path`).
- `ev.fact-sources`: "study", "survey", "report" and "according to" count only in a prose sentence of 8 or more words, never in a heading or a label; link-only blocks (menus, sitemap lists), nav and breadcrumbs are skipped.
- `words.no-customers`: link text and nav labels that name a site section ("Case Studies", "Client Reviews") are no customer claim (any short internal link in nav, header or footer; elsewhere a link whose words are its own address); on a sitemap page short section headings too. Customer names in prose still FAIL.
- Evidence freshness: a page's last change is the newest commit touching its own content file(s) (page_tracker.page_sources, page_tracker.content_globs or evidence.content_globs) or shared code (growth.json `evidence.shared_paths`, default src/components, src/layouts, src/styles, styles, src/lib, src/data, astro.config.*). Commits that only touch other pages' content do not count; a page whose files cannot be found falls back to the newest commit of the checkout.
- `thin_ok_paths`: `[{"glob", "why"}]`; a matching page gets a WARN, not a FAIL, on CNT-01 and JSR-02. An entry without a why is ignored; the default is empty.
- `ev.fact-sources` with the site's own claims: checked that `growth research fact --how raw --raw-file <mirror file> --source-url https://<own site>/<page>/ --vendor "<own name>"` is accepted and covers the stat (nothing refused the own host; a test now holds it).

## 2.2.0 - 2026-11-19

- New gate check `ev.fact-sources` (rule 5): every stat sentence of the page's main text (numbers with %, +, x, years, durations, money, counts next to a noun, named regulations such as 45 CFR, HIPAA §, HTI-1, and sentences with "according to", study, survey, report) must be the project's own claim (the number and unit written in a non-"never" line of BRAND.md, in growth.json `research.own_claims`, or in the record's `other_numbers`) or match a research-record fact row whose quote holds the number (1,000 and 1000 alike), read within 90 days (`research.fact_max_age_days`), by browser or raw text, on a source that is not banned. FAIL lists each unsourced stat with its sentence and why. Banned sources (one list in `kit/tools/fact_sources.py`, replace it with `research.banned_sources` or add to it with `research.banned_sources_extra`): ChatGPT, Perplexity, Gemini, Bard, Copilot, Claude chats and Google results or AI Overview pages. `growth research fact` refuses such a source address at write time ("ChatGPT is not a source: open the real page and quote it"). Tests: `tests/test_fact_sources.py`.

- `claims.head-figures` (friction 47): `number_values` reads K, M and B (and "million", "billion", "thousand") like `money_figures`, with or without `$` and a `+` after, so "$40K to $600K+" in the head matches "$40,000" or "600K" in the body. Test: `tests/test_release_2_2_fixes.py`.
- URL-05 (friction 48): the root canonical `/` matches a trailing-slash or a plain sitemap; inner pages are still compared.
- `seo.breadcrumbs` and SCH-07 skip on the home page: "home is the root: no breadcrumb trail" (a SKIP, also when the page has no JSON-LD). `seo.*` checks whose every line is a SKIP now SKIP instead of passing.
- LNK-02 "not migrated yet" mode: growth.json `"migration": {"on": true, "task": "T4"}` makes a 404 internal link a WARN (naming the task and the count) when its normalised path is in the live site's inventory (`inventory/inventory.json`, else `.csv`); a 404 to any other path still FAILs; off changes nothing. Template: `migration` and `_migration`.
- Delegated approvals for local work: growth.json `approvals.delegate_local` (with `delegated_to`, `owner_words`, `since`). When on, `growth approve <decision|review|exception|answer|baseline> <id> --delegated` needs no terminal and no code. The log line is signed and chained but says `"mode": "delegated"`, `"by": "lead agent (delegated by owner <since>)"` and the owner's words; `growth approve list` shows `[delegated]`. Browser, region, pending, key and any go-live or release act are refused as `--delegated` (the kit has no release approval kind). The gate and READY accept a delegated line only while `delegate_local` is on (state `delegation_off` otherwise). Generated permissions allow `growth approve * --delegated` only when on and still deny browser, region, pending and key. README "What the kit can and cannot guarantee" explains it.
- `words.never_claims_allow`: `[{"pattern", "paths", "why"}]`; a never-claim hit on a page whose path fits the glob and whose matched words (with a little text around them) match the pattern is a WARN naming the why, not a FAIL; anything else still FAILs.
- `core.service-links`: compares normalised paths (`paths.normalize`) on both sides, so a link `/lawn-care/` with a trailing slash counts as present.
- `words.no-customers`: a page whose path holds "case-stud" (or fits growth.json `words.no_customers_allow_paths`, a list of globs) may use "case study" in its own H1, nav and breadcrumb; the same words in the body, "trusted by", ratings and `words.hidden_customers` names still FAIL.
- Style checks skip a client's own words: `words.hype`, `words.banned` and `words.us-spelling` do not read text inside `<blockquote>` or `<q>` (with their `<p>` and `<cite>` children). `words.never-claim`, `words.no-customers`, `words.no-price` and the claims checks still read quotes.

## 2.1.1 - 2026-11-19

- Doctor A8 before go-live: a site rebuilt locally sets `page_tracker.changes_since` to a future day (the go-live date, or 9999-12-31 until it is known) so local commits are not read as live changes. A8 now passes with 0 changes tracked when pages are mapped to their files, and says "waiting for go-live: changes count from <day>". A past day needs changes again. Test: `tests/test_doctor_autostart.py::test_a8_before_go_live_needs_mapped_pages_not_changes`.
- Doctor A8: the project's own dashboard on `tracker_port` was reported as "in use by another program", because the check looked for "page change tracker" while the page says "Page Change Tracker". The match ignores case now.
- Known, not changed: `repo_meta.branch_ref` falls back to HEAD when `site_branch` does not exist yet, so `changes_since` is the way to hold off change tracking until go-live.

## 2.1.0 - 2026-11-19

- Page tracker: YAML dates in front matter no longer crash `growth page-tracker sync` ("Object of type date is not JSON serializable", found on an Astro site whose MDX has `date: 2026-08-13`). `repo_meta.split_md` turns every date and time, at any depth, into its ISO text (`repo_meta.plain`), and `diffs.flat` falls back to `default=str`. Test: `tests/test_research_measure.py::test_yaml_dates_in_front_matter_become_text_and_diff`.
- `kit/VERSION` now matches this changelog (it said 1.0.0 while the changelog was at 2.0.1).

- `growth approve pending`: everything that waits for the owner (unapproved design exceptions, a recorded research browser or Google region) on one screen with one typed code; each item is still its own signed log line. Items that cannot be approved (an evidence check, a bad date) are listed and skipped.

- Doctor A8: jobs the owner chose to schedule (growth.json `automation.jobs`, each with a `label` and a `why`, for example a daily unattended operator run) are shown but no longer block setup; any other auto-start job still does.

- Audit fixes joined up (the changes each fixer batch left for other files; tests in `tests/test_join_up.py`). READY takes a BLOCKED-SKIP only when `approvals.excuses_blocked_skip` says the owner approved an exception (never for `ev.*` or `proc.*`), checks that the files, commits and journal ids a manual proof names exist, and fails when a rule of the `checkpoints_extra` file was deleted from the checkpoints file; the research gate passes the project to `research.problems`; `growth workflow` cuts covered work at the commit stored with the last proof (`last_checked_commit`), not at a minute-based time (tasks from before it keep the old time cut-off); `growth journal answer` goes through `growth approve answer` (owner only), `journal run` records the sha256 of its raw answer and a `--capture-method`, and `journal add --kind decision` tells the owner to run `growth approve decision <id>`; the evidence gate reads journal times with `journal.parse_at` (no real zone: not counted); every JSON read-modify-write (tasks, research record and plan, harness settings merge, wizard state, preflight and READY ledgers, measure, registry sync, setup task, the page tracker's JSON files) goes through `atomic` (lock plus atomic replace); `page_snapshot`, `page_archive` and `vendor_page` obey `live_site_rule: no-crawl` (a vendor page is another host: only the site's own live host is refused); `owner_messages` uses `transcript.owner_text`, and a prompt from a scheduled run (listed in `docs/scheduled-prompts.txt`, named in `GROWTH_SCHEDULED_PROMPT_FILE`, or the one prompt of a run with `GROWTH_SCHEDULED=1`) is not an owner message; `growth new-project` writes a commented, git-ignored `.private-words` template; default model roles are builders sonnet, independent reviewer opus (flagged when a builder ran on the same model), log and count work haiku.
- New step "after the page is live, get it indexed": `growth index <url...> [--refresh] [--dry-run]`, `growth index status|report|setup` (`kit/tools/index_pages.py`). Providers in growth.json `indexing`: `freshlycited` (FreshlyCited's MCP/API, smart mode, `--refresh` with its cost printed first), `indexnow` (free, Bing and others) and `manual` (Search Console steps). Off until configured; spend printed before every paid call; daily cap `indexing.max_pages_per_day` (default 50); the key is read from the keys file and never printed; results in `<project>/indexing/state.json` and journal notes tagged `indexing`; `growth measure` prints "Google sees the page: yes/no since <date>" first. Release playbook step 9, book flow D and E, README section and an optional, skippable wizard step (`growth wizard indexing`). Tests use a local fake MCP server. The tool names and result fields of the provider are read defensively; check them against its tool list on the first real run.
- Kit friction 43 and 44: `contrast_check` judges a focus ring against the colour outside the element (the ring sits outside the button, not on its fill; a negative offset still uses the fill) and takes a link's text colour from the link's own words, not a child span; `phone_check` no longer counts a link inline in a sentence as a too-small tap target (WCAG 2.5.8), while a row of links with only separators between them still counts.

- Audit fixes, the trust model (19 Nov audit, V1, C3, C4, H1, H2, H9, L5). New `growth approve <exception|decision|browser|region|answer|review|baseline>`: an owner-only act typed in the owner's own terminal (a real terminal is required and the owner types back a 4-digit code); each approval is a line in `docs/approvals.jsonl` with the sha256 of the approved content, who, when, a hash chain and an HMAC signature (key made on first use in `~/.config/growth-ops-kit/approvals.key`). `growth tasks answer` goes through it; `growth approve list|verify` show and check the log. Design exceptions count only when the owner approved that exact entry, with `until` at most 30 days after the approval; `ev.*` and `proc.*` checks and "input missing / check crashed" lines are never excused, and `approvals.excuses_blocked_skip()` gives READY the same rule for a BLOCKED-SKIP. Browser and region confirmations: `growth wizard confirm` and an answers file only record what was seen; `growth approve browser|region` (or the owner's yes in `growth setup` at a terminal) confirms, and the research gate checks the approval; `--owner-confirmed` is no longer taken. Generated permissions: no venv-python, pytest or `git branch*` allow; deny push in its other forms, branch -f/-D/-m, update-ref, core.hooksPath, --no-verify, the owner-only commands, and Edit/Write of the settings, growth.json, setup files, the approvals log, tasks, journal, research records, git hooks, the kit folder and the signing key; repair removes the old unsafe entries and doctor A13 reports them, a removed deny entry and a bypassing core.hooksPath. `growth` runs tools by name only (a path ran a file outside the kit). Hook commands use the kit's absolute path, not the first `growth` on the PATH. Proof: one rule for task steps, checkpoints and the gate (a file, commit or journal id that exists, a command with its output line, or a web address; "x" or "yes" is refused); files are hashed and the commit is stored on the step (`tasks.checked_commit`); `tasks status done` refuses open steps unless `--force-reason` (logged, shown by the gate); `--type setup`. Evidence: screenshots must be real PNGs of the named width; `ev.review` needs a Builder line and the owner's sign-off of the file; `ev.decision` needs the owner's approval; AI runs need a saved answer and distinct questions; dossier questions need 20+ words; the fact check needs 5+ lines and a source address; answers typed into tasks.json fail `ev.task-steps`. Research record: no future dates, every row cites a source, raw vendor facts carry the saved page (with `growth vendor_page --record` saving it) and the quote must be in it, a frozen baseline is re-frozen only once per owner approval, and a task that names research meets the research-browser gate. README: "What the kit can and cannot guarantee".
- Golden-rule guard (kit friction 42, found on a real run): a link already blocked keeps blocking until a correction withdraws it, then stops blocking; a line that withdraws a link may name it; a new mention blocks again. READY holds for a page whose worktree release removed, when the commit it was checked at is in the site checkout's history.

- Audit M9 and LOW L4/L6 (docs): README "Three rules" is now "Three rules the kit works toward" and says what each rule really enforces (permissions deny push/merge/deploy patterns, the URL guard is a safety net, SKIP is not a pass), lists supported systems (macOS, Linux; no Windows) and every network call; the book flow starts with the six-command front door (`growth setup/page/check/ready/measure/status`) and A7/A7b use `--base <preview>`; the onboard skill matches the code (T1 setup task, `growth wizard --repair` for A10/A12, no-crawl note). New test: every `growth <command>` the onboard skill names exists.
- Audit M6: `paths.normalize()` is the one form of a page path (origin, query and fragment removed, percent-decoded, Unicode NFC, one leading slash, no trailing slash); `paths.key` uses it (`key("x")` is now `/x`) and `paths.snapshot_slug` is the one folder name per page (`/a/b-c` is `a__b-c`, `/a-b/c` is `a-b__c`), now used by `page_archive` (was `a-b-c`) and the journal notes. Archive folders written under the old name are not renamed; the gate readers `gatelib/core.py` and `gatelib/c_plan.py` must call `paths.snapshot_slug` too.
- Audit M1 and M5: new `kit/tools/atomic.py` (`locked`, `write_text`, `write_json`, `update_json`, `append_line`): a file lock plus a write to a uniquely named temp file and one `os.replace`. The journal takes one lock per command, so parallel `journal add` calls no longer repeat ids or lose lines (ids come from the highest id used, not the line count). Journal times are stored as ISO 8601 with the UTC offset (`2026-11-19 06:48-05:00`), so changing the project timezone never moves past entries; `journal.parse_at()` reads them strictly (a time with no zone, a made-up zone or text gives None), and an entry whose time cannot be read is ignored and named on stderr instead of counting as fresh. `kit/tools/gatelib/c_evidence.py` should call `journal.parse_at` instead of `at[:16]`.
- Audit H8: `inventory` and `link_graph` (crawl, update, and every request they make) refuse the live host when growth.json `live_site_rule` is `no-crawl`, with a plain "REFUSED ... use --base <preview>" message. With `--base` a crawl reads the sitemap from that origin instead of the live site. The shared check is `kit/tools/fetch_rule.py` (`assert_may_fetch(url)`); other fetchers (`page_snapshot`, `page_archive`, `vendor_page`) should call it too.
- Audit H7: `leak_check` also catches Stripe-style (`sk_live_`, `rk_`, `pk_`), Slack and Discord webhook, GitLab (`glpat-`), Hugging Face (`hf_`), npm, Google OAuth (`GOCSPX-`) and SendGrid keys, `scheme://user:pass@host` passwords, hyphenated `api-key: value` assignments, written-out emails (`name [at] host`, `name%40host`), unspaced 10-digit numbers next to a phone word and international numbers with a plus sign and groups. Files of any size are read in chunks (they were skipped past 2 MB); an unreadable file is a FAIL naming it; binary files are listed as a WARN; `.sqlite`/`.db` files fail by name. The `leak-check: allow` marker counts only under `tests/fixtures/`.
- Audit fixes, the workflow guard really holds (19 Nov audit, C2, H5, H6, M3, M7, M8, L2-L4). Workflow: a chat task covers no file changes, and the "Project setup" task covers only the setup files (growth.json, SETUP.md, BRAND.md, OWNER-RULES.md, CLAUDE.md, ...); page files need a page task. Work that was committed counts: commits made after the last page task's proof or finish are compared (project and site checkouts), so committing at the end of a reply no longer hides it. The Stop hook finds the project when Claude was started in a folder above it (GROWTH_PROJECT, the folder Claude is in or above it, exactly one project below it, or the one with changes) and otherwise blocks once with a plain "Claude was started outside the project" message; `growth workflow check` exits 2, not 0, with no project, and `growth workflow resolve [dir]` prints the one it found. url_guard catches 0.0.0.0, private-network addresses, `*.local`, any-case localhost, the preview_url host and an address with no `http://` (host:port), accepts `preview_ports` as a list, `{"from","to"}` or "a-b", drops the loose "owner said link" escape (the owner must ask for an unapproved link), and is never softened on the second stop. agent_models reads the lead's model from the transcript (growth.json `agent_models` may set roles, a lead fallback and exempt types), fails a helper whose role it cannot tell, and judges a reviewer against the models the builders really ran on. Owner messages in list form (text with a pasted image) now start a new reply window in both guards through one shared reader (`kit/tools/transcript.py`). The Stop hook never prints an empty block (it says why when no transcripts are found). `install_hooks` rejects no or unknown arguments (`remove foo` no longer removes the kit hooks), quotes every path it writes into a hook, and the kit pre-commit hook uses the kit's own Python when it has one.
- Audit M4: the hard-coded cut-off date in `ev.task-steps` is gone. A done step needs its proof in every project; a project that adopted proofs later sets `proof_required_since` in growth.json.
- Audit M2: `growth ready` runs the status check of every internal link (it passed `--no-link-status` before). The cap is `link_check_cap` in growth.json (default 200, was a fixed 80) and the OK line says how many of the unique internal targets were checked; a skipped status check that was asked for is a BLOCKED-SKIP.
- Audit H3: `growth ready --key` is bound to the path (`growth preflight` records the key in `journal/preflight.json`; READY refuses a different one). Research files belong to a key only when their name starts with `<key>-` and no longer pre-flighted key owns them (key `pricing` no longer picks up `enterprise-pricing-review-...` or `pricing-guide-review-...`). The default page key and the page-archive folder are now the path slug (`blog__my-post`, from `paths.snapshot_slug`), so `/a/b-c` and `/a-b/c` no longer collide; an archive made under the old folder name needs renaming.
- Audit H4: the gate tells two kinds of SKIP apart. `SKIP` means the rule does not apply (another stack, a feature that is off). `BLOCKED-SKIP` means it applies but could not run (no headless browser, no way to date the page, no research record yet); it is counted in the `Gate:` line and `growth ready` refuses the page while any is left.
- Audit C1: `growth ready` fails closed. A gate that exits non-zero without a FAIL line (refusal, crash, import error), prints no single `Gate:` summary line, ran 0 checks, or leaves out an expected check is NOT READY with a plain reason ("gate did not complete ...") and the page is dropped from `journal/ready.json`.
- A simpler front door (the owner asked "so why so complex?"): `growth` with no arguments, and `growth help`, print a short menu of the six commands a person needs; `growth help --all` lists every tool as before. `growth setup [folder] [--site URL]` asks a few plain questions one at a time (website, country, approver, live-site rule, one yes for the safety helpers), detects the rest, and guides the two manual steps ("Open Chrome and type /chrome ... Done? [y/N]", "What does Google's Results region say? ... Is that right for <country>? [y/N]"), recording each confirmation through the same wizard and research-gate functions; with no terminal it keeps the QUESTION / answer protocol and exit code 3. `growth page <url-or-path>` opens the page job (task with the playbook's steps), runs pre-flight and writes the brief; `growth check` runs the gate on the open job's page against the preview address; `growth ready` and `growth measure` take the page from the open job and put a plain summary (how many problems, the top three) before the exact lines; `growth status` shows what is open, a progress bar and the next step. Every old command and every check works unchanged (`growth ready <path> --type T --key K` and `growth measure run|schedule` pass straight through).
- Plain messages: the wizard's WAITING lines and the research-gate summary start with one plain sentence ("The research browser is not connected yet."), the exact command second. `growth doctor` at a terminal groups its steps into 4 stages (Your site, Access, Agent setup, Research browser) with a bar each and, for each open step, one plain sentence and the next action; `--verbose`, and any pipe (so agents and tests), list every step as before; `--summary` forces the grouped view.
- README "Start in 10 minutes" is rewritten around install, `growth setup`, `growth page`, `growth check`, `growth ready`, `growth measure`; the onboard skill starts with `growth setup`. New `tests/test_front_door.py` includes a stranger test that drives the interactive setup on a fixture site and counts the questions (8, from the website to the region confirmation).
- Setup wizard (epic #36): `growth wizard <folder> --site <url>` asks the target market first, then all access once (site repo, analytics keys file, live-site rule and preview address, release approver, one yes for the harness), detects the rest, installs the harness, and runs two guided steps (research browser, Google region). Non-interactive with `--answers answers.json`; with no answer it prints `QUESTION <step>` and stops with exit 3 so an agent can ask and record it with `growth wizard answer`. `setup.sh` offers to add the PATH line to your shell profile (asks first). (#36)
- Setup is a task: `growth new-project` and the wizard open task "Project setup" with one step per doctor step; `growth doctor` ticks a step with its own result line as proof when it turns OK or BUSY and un-ticks it when it is TODO or FAIL again, so the status bar shows setup progress from the first question. The template's OWNER-RULES.md starts with "Every job is a task". (#26)
- Agent permissions: the harness writes a `permissions` block (allow `growth *`, the kit's python, read-only git, pytest (the python and pytest allows were removed by the trust fixes above); deny `git push`, merges to main, rm -rf outside the project, the `deploy_commands` in growth.json, and a direct fetch of the live site when `live_site_rule` is `no-crawl`). Entries are added, never replaced; `growth new-project --no-permissions` leaves it out. (#32)
- Doctor A13 "Agent harness complete" lists each piece (Stop hook with status message, workflow guard, status line, permissions, skills, CLAUDE.md lines, git hooks) with OK/TODO/n/a and the fix; `growth wizard --repair` installs what is missing without touching your own settings. A12 stays "hook commands find the kit" and now also checks the `hook stage` command. (#33)
- Wizard memory: `setup-state.json` keeps every step's status (todo, asked, answered, tested, done, declined), the answer's source and date, and the test that proved it; a run resumes at the first open step; `growth wizard --check` re-runs every test and reports drift; `growth wizard status` lists it. (#34)
- Detection: `growth detect` (and the wizard) read the stack from the repo (Astro, Next.js, Hugo, Jekyll, Eleventy, ...), the build and preview commands, the sitemap shape (index or urlset, children, pages), trailing-slash form, language copies and hreflang, redirect files and content folders; each is written to growth.json `detected` with its source and date. (#35)
- Research browser hard gate: doctor A14 "Research browser connected, market region set" is a FAIL until the browser is confirmed and the region Google reports (read from its settings page, never assumed; "Current Region" fails) is the target country and confirmed by the owner; `growth preflight` and `growth tasks add --playbook <name>` (or `--research`) refuse a job with a research step meanwhile and print the fix (`/chrome`, the named browser, "By default: on"); `growth wizard research-check --connected "<names>" [--task T5 --step 3]` at the start of a research step blocks the step when the browser is gone. Market `google_params` now carry `pws=0`. Not done in code: connecting Chrome and changing Google's region (guided steps with a recorded confirmation). (#37)
- One yes for the whole harness: the wizard shows every piece once and asks one yes (git hooks separately, because they live in a git repo), instead of asking mid-job for each settings change; every hook has a status message so silence never looks like a stall. The harness also registers the `hook stage` PostToolUse hook. (#41)
- Doctor A15 "Work is tracked in a task": files changed in the project or site repo with no open task is TODO, with the command that opens one. (#24)
- Research is read, not filed (#53, epic): a structured research record per page, `research/<key>-record.json`, written with `growth research` (search window from the tracker with its definition and the page's own numbers kept apart from the site's, AI answers seen, People-also-ask questions chosen or declined with a reason, vendor facts with the vendor's quote, address, date, how it was read and which view). New gate checks read it: `ev.research-record` (complete, dated, no number read only from a summary), `ev.vendor-numbers` (every amount of money on the page is a row read within `research.fact_days`, default 30) and `ev.paa-answered` (every chosen question is answered on the page). `growth research plan` writes the plan's target searches from the record, `growth brief` puts the record in the helper's brief, `growth research baseline` freezes the numbers `growth measure` compares against. Not done: the check that the title, H1 and headings hold the record's top searches (`seo.title-query` already reads the plan's target searches). (#53)
- Measure stage (#50, #53): `growth measure run <path> --key K --release D` compares the N days after the release (day 7, 14, 28, 56) with the frozen baseline in the page's research record (same numbers at every window, per day so windows of different length compare), prints the page's own table apart from the whole site's, lists searches won, lost and moved, writes `research/<key>-measure.json` and, with `--task`, a task step; a window not over yet says "not yet" and unsettled Google days make a verdict "too early". `growth measure schedule` files the four re-checks on release + 7/14/28/56 and the new `ev.rechecks-release` fails when any is missing or on another date (the older `ev.rechecks`, which counted any four, stays). Tracker insights: the page's verdict uses its latest change (this release), not its biggest word change; "readers on changed pages" counts only the changed pages (it was the whole site); each winner/loser carries the day 7/14/28/56 windows. Page snapshot: stored query clicks come from the newest 28-day window, not summed across overlapping syncs (it inflated clicks from the second sync). (#50)
- Query-noise filter (#19): growth.json `query_noise` (`brand`, `spam`, `off_topic`, optional `on_topic`; whole words, any case; web addresses are spam by default) sorts the searches Google lists for a page into brand, spam, off topic and buyer searches (`market.classify`, `market.noise`). The page view's Target market table adds the measured and estimated impressions without that noise and the shares per class, each marked with its assumption (the share is measured on the listed searches; the long tail is assumed to split the same way). The noise list is part of the recorded definition, so changing it is flagged like any definition change.
- Spelling (rule 93) has word lists for en-US, en-CA and en-GB (`gatelib/spelling.py`). `growth.json` `spelling` may be one locale, a locale per path prefix (`{"/": "en-CA", "/en-us/": "en-US"}`, longest prefix wins) or `html_lang` (each page's own `<html lang>`); `spelling_allow` / `spelling_allow_file` hold a reviewed list of brand and trade words that are never flagged. Words real in another locale (check, meter, program) are not flagged. A locale with no list still SKIPs and says why. (#54)
- `growth vendor_page <url> --find "<plan>"`: reads a vendor page's raw text and embedded data with no summarising model, quotes the exact line with its address and time, lists the page's monthly/yearly, currency and cloud/self-hosted controls so every view is read, and with `--record` files the fact (refused when the value is not inside the quoted line). The book says a number that would change a page is confirmed on the page itself and every view is recorded. (#43)
- Design-agnostic gate, second part. `growth design learn --base <local preview> [--page /x/ ...] [--write]` finds each page concept by meaning first (landmarks, schema.org, `<time>`), proposes a selector from the page's own class names for a concept the meaning misses (it must match on at least half of the pages read) and prints what each matched for the owner to confirm; `--write` saves them to `design.json`, which the detectors read under growth.json `design` (hand entries win). `growth design calibrate --base <preview> --page ... [--type post]` runs the gate on known-good pages and lists every detector that FAILs there as SUSPECT (a detector miss, not a page fault) with the pages; it exits 1 while any is. Local previews only (the real site's address is refused). `post.read-next` now goes through design.py (an aside, nav or section labelled Read next, or `design.read_next`). Not done yet: see issue #58. (#58)
- Status line: shows "manual checks n/m" from the page's checkpoints file (the one the open task names, else the newest; hidden when it has no manual items), e.g. `T3 ▰▰▱▱▱▱▱▱▱▱ 9/44 · now: 10 Research · manual checks 3/12`. This is the status-line counter #62 left open. (#62)
- README: a table "What you get per stack" (live-page checks on every stack, code checks per adapter, an Astro site runs as `static`) and a roadmap line for an Astro adapter. (#11)
- README, "Start in 10 minutes": any folder works; keep the kit, the project folder and the site repository as three separate folders, and the project folder outside the site repository. (#14)
- `growth owner_messages` reads only the project folder's own agent transcripts by default; the folder above is read only when growth.json `transcripts_dir` says so (it may now be one folder or a list), so a general projects folder no longer floods the Stop hook with unrelated messages. (#21)
- SETUP.md and BRAND.md templates: each table cell holds a short `<fill in>`; the long hint for each row moved to an HTML comment under the table, so a cell is filled without matching the hint text (delete the comment when done). (#23)
- Rules are re-read at each stage: new hook `growth hook stage` (a PostToolUse hook on Bash): after a `growth tasks tick` or `step` whose step names a stage (research, edit, build, fold, test, gate, hand-over, ready, publish), it prints the page's open manual checkpoints so the agent re-reads them. `growth preflight --extra-rules <file>` (and `research/<key>-site-rules.md`, read automatically) merges a site's own rules into the checkpoints file; a run without the file keeps them and their proofs. Not done: a per-stage unchecked list from the gate (the gate is not touched here). (#25)
- The task workflow is enforced, not optional: new `growth workflow check` (run by the Stop hook) blocks the stop, every time and with the command that clears it, when files changed in the project or site checkout and no task is open, when an open task has no steps, or when a step is done with no proof; it never softens on the second stop. A chat that is not page work uses `growth tasks add "Chat: ..." "" --type chat`. `growth tasks step` now starts a step as todo; creating one as done needs `--output`, like `tick`. A stop the other checks let through on the second try is filed in the journal (tag stop-hook). Not yet: preflight/gate/ready refusing a page with no task, the doctor "work without a task" line, the journal page header. (#24)
- Held-field proposals are stored structured in the page plan (`research/plans/<key>.json`, key `held`: field, current, proposed, the facts quoted, date, status) with `growth held add|list|changed|rewrite|apply|drop`. `growth held changed <key> --old <fact>` marks every open proposal that quotes the fact stale; the new check `ev.held-proposals` (rule 109) FAILs while one is stale, and also when a quoted fact is no longer on the page, so a review fix that changes a number cannot leave an old description proposal waiting to ship. `growth ready` lists the held proposals with their status. (#61)
- The gate checks the argument, not only the structure. `ev.review` now needs the independent review file to answer every item of the kit's fixed checklist (`kit/checklists/review.md`: like-for-like comparisons, head numbers stated in the body with their source, no two answers contradicting, sources, fairness, first screen, held fields) with `Rn pass|fixed|n/a`, and a `Reviewer:` line that is not the `Builder:`; `growth review new <key>` writes the file from the checklist. New check `claims.head-figures` (rule 109) FAILs when a money figure in the first screen or a verdict block (`design.verdict`, `data-verdict`, a class `verdict`/`tldr`/`quick-answer`) is not stated in the body ($1,234.50 and $1234.5 count as one). The brief templates for lists, comparisons and guides carry the comparison rule. (#60)
- READY runs on a production build, not a dev server. New check `ev.prod-build` (rule 106) FAILs when the page holds dev-server markers (hot-reload clients, dev toolbar, source-location attributes of Vite, Astro, Next.js, webpack, Nuxt, SvelteKit, Hugo and others) and names the right command; new `growth serve <dist>` serves a built folder on 127.0.0.1 (clean URLs, 404.html); growth.json `preview_cmd` records the site's own production preview command (for a site that renders on a server). Documented in rule 106 and the release playbook. (#57)
- Journal findings start open and stay open until `growth journal close <id> --output "what was done and its proof"` (the output is required); before, a finding was closed the moment it was filed, so `ev.open-findings` could only fail on questions. `growth journal open` now lists open findings too. (#48)
- `ev.review` needs a research file named `<page>-audit-<date>` or `<page>-review-<date>`; the name is matched without the page key and the checkpoints file never counts, so a page key that contains "review" no longer passes with no review. (#49)
- `growth ready` and `growth preflight` stop when `growth.json` has a `site_repo` but no `preview_repo`: READY and the evidence dates would otherwise read the main site folder, not the worktree the page is built in, so commits there never made READY stale. Set `preview_repo` to the worktree (or to the `site_repo` folder if you build there); `preflight --repo` still overrides. (#51)
- Small crashes and gaps: `journal add/run --recheck` refuses a date that is not a real YYYY-MM-DD and `journal due` no longer crashes on a bad one already filed; `growth preflight` no longer crashes with no journal yet; the gate's default page key never contains a slash; `ev.archive-before` matches `new_pages` without the trailing slash; a fold plan with zero folds no longer passes; one naming rule for research files, in the gate and in the cluster-redesign playbook (`<page>-research-<date>.md` now satisfies `ev.research-check`, and the page key is ignored when matching the name). (#52)
- Checkpoints file read back: items that no gate check runs are manual (the project's own rules from `growth.json` `checkpoints_extra`, one bullet each, and any checkbox the builder adds). Each must be ticked with a proof (`- [x] rule 530: click test -- J0028, 53/53`); `growth ready` fails and lists the open ones, `growth checkpoints <file>` shows them, and `growth preflight` now merges into the file (ticks, proofs, hand-added items and project sections stay; new items are added; items that left the scope move to "Removed from scope") and prints "manual checks 12/18". Not done here: the status-line counter. (#62)
- Doctor A5: the 'Control check' row passes when "done" is anywhere in its status cell (the last cell), and it must name at least one commit id (7 to 40 hex characters; a template placeholder such as `<fill in: done or not>` no longer counts). A bare `| done |` with no proof is TODO. When `site_repo` is set, every id is checked with `git cat-file`. (#6)
- Doctor shows BUSY, not TODO/FAIL, for normal work in progress, and counts it as done (it never fails the run): A9 when the owner journal page is behind a log line written in the last 15 minutes (the Stop hook rebuilds it), A8 when the tracker database is locked by a sync. The last line says how many steps are BUSY. Older staleness still fails. (#17)
- The tracker port is checked: `growth new-project` writes the first free port from the default upward into `growth.json` `tracker_port` (an existing file is never changed), and doctor A8 says when another program already holds the configured port (a tracker dashboard answering there is fine) and tells you to set `tracker_port`. (#13)
- The onboard skill no longer says "doctor 8/8": it stops at doctor's own last line, and its step table now names every step doctor checks (A7b, A9, A10, A11 added). A test fails when doctor has a step the skill does not name, or when the skill hard-codes a step count. (#31)
- Page tracker: the target market is MEASURED, not only estimated. growth.json `target_markets` (country codes as the search tool lists them, e.g. `["usa"]`) adds a "Target market" table to the page view: all countries, the target market measured from the country rows (clicks, impressions and its OWN position, e.g. 3.2 overall but 5.2 in the main country), and an estimate marked as an upper bound with its assumption written out (unlisted countries split like the listed ones; one real estimate was about 2.5x too high). Each pull records the definition with its snapshot, and the table warns when the definition changed, so a before/after never compares two definitions. (`kit/tools/market.py`) (#19)
- Page tracker: a moved page's OLD addresses are added to its Search Console figures. Google keeps showing the old address for months after a move (one real page: 13,860 impressions on the new address, 280,563 on the old one, 295,811 in all), so counting only the current address undercounts it about 20x and makes a before/after verdict meaningless. Set growth.json `page_aliases` (`{"/topic/post": ["/blog/post/"]}`) and/or `redirects_file` (a redirect list with `old new [301]` lines; wildcards, other hosts and non-redirect codes are skipped, chains are followed). The page view shows a "Which address Google shows" table; `growth aliases` prints the resolved map. (#16)
- `growth link_graph report`, rule 90 (same anchor words, different pages): a page and its language or region copies (its `hreflang` alternates, or the prefixes in growth.json `link_graph.locale_prefixes`, e.g. `["/en-us"]`) count as ONE target; pager links (rel next/prev, page numbers, "older", `/page/N`) are left out; the real collisions are listed first (most distinct pages first), and the summary says how many were not counted and why. On a 328-page site this removes about 1,600 of 1,638 false collisions. (#9)
- `growth link_graph crawl --base <static server>` asks for each page the way the sitemap spells it: on a trailing-slash site it requests `/x/`, so a plain static server's 301s no longer make a 328-page site look broken (327 of 328 "not 200"). The graph key stays slash-free. A page that still answers one same-page 301 is followed one hop. growth.json `trailing_slash` overrides the detection. (#20)
- Repo checks are configurable (Next.js adapter): growth.json `branch_prefixes` (default `page/`, `article/`, `fix/`, `design/`; `review-` style entries allowed) is the source of truth for `repo.branch`, and `commit_identity.email` for `repo.commit-identity` and `proc.commit-identity`; the noreply rule applies only when `commit_identity.email` is empty (before, an empty value failed every commit). The checkpoint plan written by `growth preflight` now marks adapter checks `SKIP on this stack` on a non-Next.js stack, so nobody plans around a FAIL that cannot happen (#30, #42).
- Stack-neutral settings moved out of the `nextjs` block: `retired_paths`, `redirect_files`, `posts_dir`, `pages_dir` and `content_reader` now sit at the top level of `growth.json` (any stack can record its retired paths and redirect list). The old place is still read as a fallback for one release; the top level wins when both are set. One reader, `config.site_setting` (#22).
- Tests: `test_help_lists_every_tool_with_one_line` skips the shared helper modules named in `INTERNAL_MODULES` (tests/test_cli.py), so a new helper in `kit/tools/` no longer needs a fake `growth <name>` command and help line; a second test checks each entry is a real file and not also a command (#40).
- `growth new-project` writes the Stop hook and status line as `growth hook stop` / `growth statusline`, found through the `growth` command on the PATH at run time; the kit's folder on the machine that ran it is only the last fallback (`${GROWTH_KIT:-...}`), so a shared project folder or a moved kit still runs its hooks. Older absolute-path commands made by new-project are moved to the new form on the next `new-project --force`. New `growth hook stop`; new doctor step A12 checks the kit path in `.claude/settings.json` exists (#39).
- Commit messages are checked before they are written: `growth install_hooks kit` and `project` now also install a `commit-msg` hook (new `growth leak_check --message FILE`) that fails on a key or private word in the message, and the kit also gets a `pre-push` hook that runs `growth leak_check --history`. `setup.sh` installs the kit's hooks. The hooks find the git-ignored `.private-words` of the main checkout from a linked worktree (#38).
- `growth leak_check --history` now FAILS (it was a warning) when a private word is in the author or committer name or email of a commit no remote has yet; commits already on a remote stay a warning. `setup.sh` sets a repo-local GitHub no-reply commit identity for the kit checkout only (asks once, or reads `GROWTH_KIT_GIT_EMAIL`; the global git config is never touched). README Contributing documents the git-ignored `.private-words` file (#12).
- Progress you can watch, by default: `growth new-project` registers a Claude Code status line (`growth statusline`) that shows the open task, a progress bar and the current step at the bottom of the agent's window, e.g. `T3 ▰▰▱▱▱▱▱▱▱▱ 9/44 · now: step 10 ...`. Style in growth.json `statusline_style`: bars (default), squares, blocks, dots, checks, plain. The Stop hook gets a `statusMessage`. An existing status line is never replaced.

- One sitemap reader (`kit/tools/sitemaps.py`, also `growth sitemaps <url-or-file>`) for the inventory, the link graph,
  the page tracker and the technical SEO check. A sitemap index is followed to its pages; before, the inventory and the
  tracker took an index's child sitemap files as pages, and MAP-02 said a page in a child sitemap was "not in the
  sitemap". A saved index (`--offline`) reads its children from its own folder, so a local build's `dist/` works.
  `growth inventory --base <preview>` reads the preview's own sitemap and every child sitemap from the preview (never
  the production host named in `<loc>`), so a page that exists only on the branch is listed. The technical SEO check
  reads the sitemap robots.txt names (for example /sitemap_index.xml), else /sitemap.xml.
  `inventory.json` meta and `INVENTORY.md` now say which address the pages were read from (`base`) and which sitemap;
  "Search Console: not connected" is now "none yet ... run `growth page-tracker sync`" when the tracker has no rows;
  doctor's A7 fix line says `growth inventory --base <preview_url>` when a preview is set.
- Doctor A8: an auto-start job counts only when it is THIS project's: a launchd plist or crontab line that runs
  something inside the project folder or names it (`GROWTH_PROJECT=<folder>`). Before, any launchd job with the
  business name in it failed A8, so another tool for the same business (its own folder) blocked setup. The jobs found
  are named in the line, and they show even before the tracker exists. Known limits: a job that names the folder
  through ~ or a symlink is not matched, and Linux systemd user timers are not checked.
- Rule 32 (`cta.one-path`): `growth.json` `booking_allowed` lists the site's OWN booking links that it uses on purpose,
  each with a required reason (`{"match": ..., "why": ...}`). The gate prints them as a WARN that names the exception
  and its reason, never a silent OK; any other booking link still FAILs, and an entry with no reason FAILs.
- The booking paths (`conversion_path`, `cta.contact_path`) are compared without a trailing slash: a site whose
  addresses end in "/" (for example "/contact/") was told "no link to the booking path at all" on every page.

- Doctor A2: once `old_brand_words` was filled it could never pass, because the brand sheet's "never say" line and the
  steps log (which quotes the owner) counted as leftovers. Lines that ban the words, `growth.json` and the steps log no
  longer count; a real mention in any other project file still FAILs. New `build_dir` (the site's production build):
  A2 also searches its pages (html, txt, xml, md, json), so a leftover on the site itself fails too. The line says
  how many files were searched and how many mention the old brand, with the build's absolute path; with no build
  (unset, missing, or no page files) A2 is TODO, never OK.
- Sites whose addresses end in "/": the page tracker asked analytics for /x while Search Console keys the page as
  /x/, so every page's Google numbers came back 0 (and page_journeys' replies, keyed /x/, were never matched). The
  tracker learns the site's form from its sitemap (`trailing_slash` in sitemap-cache.json; `page_tracker.trailing_slash`
  overrides) and sends that form. The inventory matches sitemap paths, tracker numbers and growth.json lists
  (money_core, core_pages, new_pages) with or without the slash.

- `growth page_snapshot --base <url>` reads the page from a preview or a local build instead of the live site, and the
  snapshot records the address it read (`base`). The page is matched to its inventory row with or without a trailing
  slash, and its own address form is used for the page and for analytics (before: a trailing-slash site was "not a
  live page", and analytics answered 0).

- Gate evidence on trailing-slash sites (new `kit/tools/paths.py`, also `growth paths`): ev.inventory, ev.task-steps
  and seo.kept match a page with or without its slash (seo.kept used to call every such page "new" and pass); a task
  title may name the page by its full address; ev.snapshot looks in the folder page_snapshot writes
  (`inventory/pages/blog__post/`, it looked for `blog/post/`); a fresh task with no step done is no longer reported as
  "still todo while later steps are done".

- Measuring any site layout: `growth.json` `page_tracker.content_globs` maps content files to addresses with a template
  filled from each file's own fields (`{"glob": "src/content/blog/*.md", "address": "/{cluster}/{slug}/", "values":
  {...}}`; JSON pages too), so an Astro-style site gets change dates (before: 0 changes, so no before/after). Doctor A8
  fails when a site repo is set and no change is tracked. Task steps are ordered by their label ("Step 16a" after
  "Step 16"), not by list position. Journal entries and the title check's Search Console queries match a page with
  or without its trailing slash.

- Design-agnostic gate, first part (`kit/tools/gatelib/design.py`): one place finds each page part (site header and
  footer, main, cover image, byline, updated date, reading aid, FAQ, table source, calculator, read next, disclosure)
  from semantic signals first (landmarks, ARIA, schema.org, `<time datetime>`, rel=author, itemprop), then the
  project's `design` map of CSS selectors. Rewritten on it: faq.schema-equal and every FAQ check (only the FAQ's own
  questions, found through the FAQPage markup; never a contents list or a fold), post.cover, layout.shared-frame,
  cta.no-bare-book (the site's own label with its reason line passes), words.named-author, post.reading-aids ("N min
  left" anywhere; FAQ toggles need no copy button), geo.updated (the shown date that equals dateModified), geo.table-
  sources (its own box, the component's data-checked/data-source, or the section), claims.box-numbers (data-calculator
  and `box_ignore` skipped). New growth.json settings: `design`, `design_exceptions` (a WARN with its reason; FAILs
  again when its task is done or its date has passed), `disclosure_pattern`, `box_ignore`.

- tags.not-local judges what a local page really requests: it loads the page in the headless browser, waits 4 s, scrolls
  and clicks once, and fails only on requests to analytics or ad hosts. Without a browser it reads the markup, where a
  loader behind a `location.hostname` guard for the site's own host counts as off. embeds.lazy ignores iframes inside
  `<noscript>` (they never load while JavaScript is on).

## 2.0.1 - 2026-11-18

Fixes from the independent review of 2.0.0, before anything is published.

- Leak check: a listed private phrase now matches across spaces, hyphens, underscores and dots; `--history` also reads
  every commit's author and committer (a WARN: the public history is made fresh).
- Every trace of the first source site removed from code, registry texts, messages and examples. A registry rule's text
  is copied from the book's heading by `growth registry_sync`, and a test keeps them equal.
- Next.js adapter: works on any Next.js repo. Its layout assumptions are settings in `growth.json` `nextjs` (production
  branch and remote, content reader, retired paths, redirect files, Markdown folders, hub files); a check with no setting
  prints SKIP. Fixed the `links.blue` crash. New fixture repo and tests run the adapter on a plain Next.js tree.
- Rule 36b / 95: Organization, WebSite, BreadcrumbList and WebPage never count as a page's main type.
- A static site with no checkout can reach READY: evidence is dated from `site_dir` or the page's own capture.
- Owner-message check: no transcripts found is a WARN with a clear line, never OK.
- A project may have a remote (`proc.remote-private` warns); the book and the gate now agree.
- `setup.sh` links `growth` into `~/.local/bin`; `new-project` installs the `/onboard` skill and the Stop hook into the
  project's `.claude/`; `growth doctor` checks the hook and the preview address.
- Book: one name for folds and surfaces (`data-fold`, `geo-lines`); owner quotes made neutral; DESIGN.md ships; Search
  Console and GA4 come through an analytics connector (today: Skald), a direct connector is not yet built.

## 2.0.0 - 2026-11-18

The first open-source edition: a growth book and a kit that works for any website.

### Book (CC BY 4.0)
- New generic book in `book/`: the flow (stages A to H), the default working rules, the page rulebook (rule numbers
  and `[code: ...]` tags unchanged so the book keeps matching the rules registry), lanes and releases, 17 playbooks,
  16 helper brief templates, the lessons (merged and de-duplicated, with the short do's and don'ts), and the day-one
  project foundation checklist.
- Every business-specific fact moved out of the book. A rule that needs a fact now reads it from the project's
  `BRAND.md` or `growth.json` (the one CTA label, the words never to use, the author, the market). Examples use one
  made-up business, Brightline Lawn Care.
- Rules that read a site's code are marked "(Next.js adapter)" and run only for Next.js projects.
- Analytics and Search Console are optional connectors.
- Tool commands are now `growth <tool> <args>`.

### Templates
- `templates/project/`: `BRAND.md`, `OWNER-RULES.md`, `SETUP.md`, `CLAUDE.md` and `docs/steps-log.md` for a new
  project folder.

### Licences
- Book: CC BY 4.0 (`LICENSE-BOOK`). Code: MIT (`LICENSE`).
