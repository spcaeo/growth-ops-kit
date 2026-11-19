# Changelog

The kit and the book share one version number. Dates are written year-month-day.

## Unreleased

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
