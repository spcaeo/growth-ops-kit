# Changelog

The kit and the book share one version number. Dates are written year-month-day.

## Unreleased

- Doctor A5: the 'Control check' row passes when "done" is anywhere in its status cell (the last cell), and it must name at least one commit id (7 to 40 hex characters; a template placeholder such as `<fill in: done or not>` no longer counts). A bare `| done |` with no proof is TODO. When `site_repo` is set, every id is checked with `git cat-file`. (#6)
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
