# Changelog

The kit and the book share one version number. Dates are written year-month-day.

## Unreleased

- Research is read, not filed (#53, epic): a structured research record per page, `research/<key>-record.json`, written with `growth research` (search window from the tracker with its definition and the page's own numbers kept apart from the site's, AI answers seen, People-also-ask questions chosen or declined with a reason, vendor facts with the vendor's quote, address, date, how it was read and which view). New gate checks read it: `ev.research-record` (complete, dated, no number read only from a summary), `ev.vendor-numbers` (every amount of money on the page is a row read within `research.fact_days`, default 30) and `ev.paa-answered` (every chosen question is answered on the page). `growth research plan` writes the plan's target searches from the record, `growth brief` puts the record in the helper's brief, `growth research baseline` freezes the numbers `growth measure` compares against. Not done: the check that the title, H1 and headings hold the record's top searches (`seo.title-query` already reads the plan's target searches). (#53)
- Measure stage (#50, #53): `growth measure run <path> --key K --release D` compares the N days after the release (day 7, 14, 28, 56) with the frozen baseline in the page's research record (same numbers at every window, per day so windows of different length compare), prints the page's own table apart from the whole site's, lists searches won, lost and moved, writes `research/<key>-measure.json` and, with `--task`, a task step; a window not over yet says "not yet" and unsettled Google days make a verdict "too early". `growth measure schedule` files the four re-checks on release + 7/14/28/56 and the new `ev.rechecks-release` fails when any is missing or on another date (the older `ev.rechecks`, which counted any four, stays). Tracker insights: the page's verdict uses its latest change (this release), not its biggest word change; "readers on changed pages" counts only the changed pages (it was the whole site); each winner/loser carries the day 7/14/28/56 windows. Page snapshot: stored query clicks come from the newest 28-day window, not summed across overlapping syncs (it inflated clicks from the second sync). (#50)
- Query-noise filter (#19): growth.json `query_noise` (`brand`, `spam`, `off_topic`, optional `on_topic`; whole words, any case; web addresses are spam by default) sorts the searches Google lists for a page into brand, spam, off topic and buyer searches (`market.classify`, `market.noise`). The page view's Target market table adds the measured and estimated impressions without that noise and the shares per class, each marked with its assumption (the share is measured on the listed searches; the long tail is assumed to split the same way). The noise list is part of the recorded definition, so changing it is flagged like any definition change.
- Spelling (rule 93) has word lists for en-US, en-CA and en-GB (`gatelib/spelling.py`). `growth.json` `spelling` may be one locale, a locale per path prefix (`{"/": "en-CA", "/en-us/": "en-US"}`, longest prefix wins) or `html_lang` (each page's own `<html lang>`); `spelling_allow` / `spelling_allow_file` hold a reviewed list of brand and trade words that are never flagged. Words real in another locale (check, meter, program) are not flagged. A locale with no list still SKIPs and says why. (#54)
- `growth vendor_page <url> --find "<plan>"`: reads a vendor page's raw text and embedded data with no summarising model, quotes the exact line with its address and time, lists the page's monthly/yearly, currency and cloud/self-hosted controls so every view is read, and with `--record` files the fact (refused when the value is not inside the quoted line). The book says a number that would change a page is confirmed on the page itself and every view is recorded. (#43)
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
