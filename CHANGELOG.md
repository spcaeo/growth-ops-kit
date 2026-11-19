# Changelog

The kit and the book share one version number. Dates are written year-month-day.

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
