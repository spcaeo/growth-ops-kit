---
title: The Growth Ops book
version: 2.0.0
updated: 2026-11-18
license: CC BY 4.0
---

# The Growth Ops book

**Version 2.0.0 · 18 Nov 2026 · licence CC BY 4.0**

How to grow a website page by page, with an AI coding agent: the order of work, the rules every page must pass, one
playbook for each job, and the lessons that cost real time. It works for any website and any business. Nothing in it
belongs to one company: facts about a business come from its project folder (`BRAND.md` and `growth.json`).

The examples use one made-up business, **Brightline Lawn Care** (https://brightline.example), a lawn-care service
company whose one call to action is "Get a quote".

## Who it is for

- **An owner or marketer** who wants a site to earn more from search and from AI answers, and wants to know what the
  agent is doing and why.
- **A developer or an agent** who changes pages and needs the rules, the order of work and the checks in one place.
- **A team that runs several sites.** Each site is one project folder; the book is shared.

## How the book and the kit fit

The book is the **method**. The kit is the **machine** that makes the strict parts run. Every rule in the page
rulebook ends with a tag:

| Tag | Meaning |
| --- | --- |
| `[code: check-id]` | The kit's gate decides it. `growth gate page <path> ...` runs the check named by `check-id` and fails the page on a FAIL. |
| `[judgment: proxy check-id]` | A person or a reviewer decides it. The gate only checks that the evidence exists (fresh screenshots, a journal entry, a research file). |

A test in the kit fails when a tagged check does not exist, when a check points at no rule, or when a rule here and the
rules registry (`kit/rules/registry.json`) disagree. So **rule numbers and check ids never change**: a rule that is no
longer needed is rewritten, or marked "reserved", never renumbered.

Tool commands in the book are written `growth <tool> <args>`. For example `growth gate page /x --url ...`,
`growth ready`, `growth tasks tick`. Paths of project data (`growth.json`, `BRAND.md`, `docs/steps-log.md`,
`docs/tasks.json`, `journal/`, `research/`) are relative to the project folder.

Stack: rules that read the site's code say "(Next.js adapter)" and run only when `growth.json` has `"stack":
"nextjs"`. Every other rule reads the live page and applies to any site. Analytics and Search Console are optional
connectors (recommended: [Skald](https://skaldanalytics.com), AI traffic analytics from your server log, plus Search Console; a direct Search Console connector is not yet built); the tools run without them and say what is missing.

## How to read it

1. **New to the kit?** Read [01-flow.md](01-flow.md) first. It is one page of process: onboard, choose, run the job,
   release, measure, learn.
2. **Setting up a project?** Follow stage A of the flow. Fill `BRAND.md` and `growth.json` with the owner. Then read
   [foundation.md](foundation.md) if you are also building code.
3. **Doing a job?** Open the job's playbook in [playbooks/](playbooks/README.md), copy its steps into a task, and
   follow them in order.
4. **Building or changing a page?** Keep [03-page-rulebook.md](03-page-rulebook.md) open: the checklist at its top
   and the numbered rules.
5. **Briefing a helper agent?** Use the templates in [prompts/](prompts/README.md), or `growth brief`.
6. **Something went wrong?** Add it to [lessons.md](lessons.md) with its date and what it cost.

## Contents

| File | What it is |
| --- | --- |
| [01-flow.md](01-flow.md) | The order of work, stages A to H: onboard, choose, run, release, measure, learn, helpers, the golden rule |
| [02-owner-rules.md](02-owner-rules.md) | The default working rules for the agent. A project adds its own in its `OWNER-RULES.md` |
| [03-page-rulebook.md](03-page-rulebook.md) | Every rule a page must pass, with the per-page checklist and the house features of each page type |
| [04-lanes-and-releases.md](04-lanes-and-releases.md) | Several pages in parallel, each in its own copy of the site, each released alone |
| [05-board.md](05-board.md) | Kit 3.0: the one database, micro kits, the work board, jobs, resources (Google pacer, shared-code lock), lanes and the machine runner |
| [06-international.md](06-international.md) | Kit 3.0: a site in several languages and countries: locales in `growth.json`, rule 162 (lang, hreflang, canonical, no redirect by language, sitemap alternates), localize jobs on the board, research per market |
| [playbooks/](playbooks/README.md) | One file per job: money page, cluster, new post, update, fact fix, page change, links, link graph, lost pages, leaving pages, images, site map, release, technical SEO, CRO audit |
| [prompts/](prompts/README.md) | Brief templates for helper agents: auditor, writer, fixer, researcher, builder, hub, comparison, verifier |
| [lessons.md](lessons.md) | What went wrong, what it cost and the guard; the short do's and don'ts |
| [foundation.md](foundation.md) | The day-one checklist for any new project |

## Words used in the book

| Word | Plain meaning |
| --- | --- |
| Owner | The person who decides for the business. |
| Money page | A page meant to bring a buyer to the one conversion (a service page, pricing, the home page). |
| Hub, cluster | A cluster is one topic's pages. The hub is its main page. |
| Fold | One section of a page, about one screen tall. |
| Gate | The kit's check that runs every rule a program can decide, and fails the page on any FAIL. |
| Lane | One agent working one page in its own copy of the site. |
| Canonical | The one address you tell search engines is the real one for a page. |
| Search Console | Google's free report on how a site shows in search. |

## Licence

The book (this folder) is licensed CC BY 4.0: you may share and adapt it, with credit. See [../LICENSE-BOOK](../LICENSE-BOOK).
The kit's code is MIT. See [../LICENSE](../LICENSE).
