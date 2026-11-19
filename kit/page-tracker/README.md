# Page tracker

It answers one question: **did our page changes help?**

It lists every page of the site in `growth.json`, groups the pages into clusters, finds the date each page changed (from the
site's git history), and shows a dashboard. When Search Console and analytics are switched on, the dashboard also shows what
Google and readers did before and after each change.

The tracker is part of the kit; the site it tracks is a project folder. Code and dashboard files live here (`kit/page-tracker/`).
Everything it writes (`tracker.db`, `data.json`, `insights*.json`, `diffs/`, logs, the sitemap copy) goes to
`<project>/page-tracker/` and stays out of git. Nothing is ever written inside the kit.

## What works with every outside source off

- Page list: read from the live sitemap (`growth.json` `sitemap_url`). If it cannot be read, the last copy is used, and if
  there is none, the site repo's own content.
- Clusters (page groups): the core pages, one cluster per silo in `growth.json` `silos`, and "Other pages".
- Change dates: each git commit that changed a page's file is one change (needs `site_repo` and, for a Markdown site,
  `page_tracker.content_dirs` / `page_tracker.page_sources`).
- Google's own Search Status Dashboard feed (dates of core and spam updates): free, no key.
- The dashboard, drawing cleanly while there are no reader or Google numbers. Verdicts say "too early".

## Connectors (all optional)

The recommended connector is [Skald](https://skaldanalytics.com): AI traffic analytics from your server log, plus Search
Console. Search Console, GA4 and AI-traffic data come through it. **Every connector is optional and the rest of the kit works
without one.** A direct Search Console connector (no analytics service in between) is **not yet** built.

Each is switched on in `growth.json` under `connectors`, and its keys are read from the file named in `keys_file`, which lives
outside git. A missing key gives one plain note on stderr and the run goes on with the sources that need none.

| Connector | Switch | What it needs in the keys file |
| --- | --- | --- |
| Skald analytics (readers, leads, AI crawlers, bounce) | `connectors.skald.on` | `SKALD_MCP_URL`, `SKALD_MCP_TOKEN` |
| Google Search Console, read through Skald | `connectors.search_console.on` | the same Skald keys |
| Google Analytics 4, read through Skald | `connectors.ga4.on` | the same Skald keys |
| Bing | `connectors.bing.on` | not yet: the setting is reserved and the dashboard has no Bing screen |
| AI daily summary | `page_tracker.ai_summary.on` | off until you say; `mock` mode makes no model call; `claude` mode uses the smallest model |

## Run it

From the project folder (or with `GROWTH_PROJECT` set):

```
growth page-tracker sync       # page list, clusters, change dates from git, then every source that is on
growth page-tracker report     # writes data.json (the dashboard's data) and report.html into the project
growth page-tracker ai-summary # the AI note: off by default, so it only writes a "this is off" line
growth page-tracker serve      # the dashboard on http://127.0.0.1:<tracker_port>/dashboard.html (this computer only)
```

Needs Python 3.10 or newer and `pyyaml` (installed by `setup.sh`). `bash start.sh` runs sync, report and serve in one go.

## Settings

Values come from the project's `growth.json` (`site_url`, `sitemap_url`, `site_repo`, `timezone`, `silos`, `core_pages`,
`connectors`, `keys_file`, `tracker_port`), then the optional `page_tracker` block of `growth.json`, then an optional
`<project>/page-tracker/config.json` of the same shape. The `page_tracker` block can hold: `clusters` (`exact` lists whole
paths, `prefix` takes a path and everything under it, the longest prefix wins), `content_dirs`, `page_sources`,
`path_variants`, `changes_since`, `site_branch`, `ai_summary`, `version`.

The footer shows the release line: `v<version> · build <n> · <time>`. The version is the kit's (`kit/VERSION`) unless
`page_tracker.version` is set; the build number goes up by one on every `report`.

## The dashboard in the address bar

Every screen has its own address you can copy, and Back and Forward work. The query parameters are `view`, `cluster`, `page`,
`tab`, `sort`, `dir`, `country` and `q`; an invalid value is dropped. (See `dashboard.js`, `readURL` and `urlFor`.)
