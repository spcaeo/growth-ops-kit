---
title: Default working rules
version: 2.0.0
updated: 2026-11-18
license: CC BY 4.0
---

# Default working rules

**Version 2.0.0 (generic edition) · 18 Nov 2026**

These are the standing rules for the AI agent that does the growth work, as given by owners of real sites. They are
**defaults**. A project adds its own rules, or changes a default, in the `OWNER-RULES.md` of its project folder (made
from `templates/project/OWNER-RULES.md`). Where the project's rules or the site repo's own rules are stricter, the
stricter rule wins. The order of work is in [01-flow.md](01-flow.md).

Every rule has one home. Other files link here instead of repeating a rule. Tags: `[code: ...]` means the kit's gate
checks it; `[judgment]` means a person or reviewer decides it.

## 1. How we work

> **GOLDEN RULE (from a real project, "this cannot be broken"): never share a page URL with the owner before it is
> 100% approved and checked.** READY = `growth ready` says 0 FAIL on the full gate at the current commit of the one
> preview (independent review, fact check, research cross-check, CRO audit, fresh shots and click-test, share
> preview, AI baseline and speed included). Until then the owner gets status in words, never a link. Enforced by the
> Stop hook (`url_guard`). **Exception:** when the owner asks for the links, the local preview links are given even if
> not READY, each marked "not approved yet".

| Rule | What it means |
| --- | --- |
| **No shortcuts** | Before any job, open its playbook and copy every step into the task; follow each in order with every owner check-in. An audit or a quick-wins pass is one step, never the job. A step that can't be done is raised with the owner **before** it is skipped. (On a first money page an audit was followed straight by a quick-wins build; the owner caught it.) [code: ev.task-steps, proc.tasks] |
| **Work like a freelancer** | Fast and lean: run only the tests a change can affect (`growth checks`, page rulebook rule 105), never the whole suite "to be safe". No ceremony, no needless helpers. Lean never means skipping a playbook step. [judgment] |
| **Workflows you can watch** | Multi-step jobs run as workflows where the agent tool supports them, so the owner sees each step tick off. Split long steps into smaller helpers that log a status line as each finishes, so the owner can see it is not stuck. A workflow starts only with the owner's yes. Independent parts run in parallel. [code: proc.workflows] |
| **One project at a time** | In one project, never mix in other projects' names, facts or questions. Check the steps log before asking; never re-ask a settled answer. [code: proc.doctor, words.banned] |
| **Records match the work** | A finished step is ticked in place with its proof (`growth tasks tick <task> <n> --output <proof>`), never added again; `growth tasks step` refuses a step that is already open, and the gate's `ev.task-steps` fails on a step left open while later steps are done. [code: ev.task-steps] |
| **Log every instruction** | Flow stage F, at once, before reporting: steps log, the rule's one home (as code when a program can check it), the cross-project lessons, memory. Proven by `growth owner_messages check` (exit 0). [code: proc.owner-messages, proc.steps-log] |
| **The owner reviews screens, not documents** | The owner never reviews .md files. Research, dossiers and concepts are inputs for builders. The owner sees the work as UI on a local link (laptop and phone) and answers short one-click questions in chat, each with a safe default so the build never waits. [judgment] |
| **Rules are code** | "Markdown files are guidelines; program runs are rules." Every rule a program can check is checked by `growth gate` (page rules) or `growth gate process` (how we work), listed in `rules/registry.json`; the kit's tests fail when a rule has no entry. A judgment rule names the code proxy that proves it was done. A page ships only with zero FAIL. No loose words: must, never, or a number; never "should", "try", "ideally" or "where possible". [code: proc.rules-code] |
| **No owner message goes unlogged** | `growth owner_messages check` reads every message the owner typed in this project's sessions and fails on any not in `docs/steps-log.md` (quoted, or mapped in `docs/owner-messages-map.json`). Run it before every report; it is part of `growth gate process`. [code: proc.owner-messages] |
| **Engine vs project data** | The kit holds no project facts: names, numbers, URLs and claims come from `growth.json`, `BRAND.md` and `SETUP.md` in the project folder. Project data (`growth.json`, `BRAND.md`, `SETUP.md`, `journal/`, `research/`, `inventory/`, `page-tracker/*.db`, `docs/`, keys) never goes into the kit or the book. [code: engine.facts] |
| **Keep a page journal** | Like a person's working notes: every finding, question, decision and check you run (the exact query, market, settings and full answer) goes into `journal/` with `growth journal`, tagged to the page(s) it concerns, time-stamped, with a re-check date (day 21, 28, 56). Before working on a page, read `growth journal show <page>`. `journal/` opens as an Obsidian vault. [code: ev.journal-page] |
| **Owner action items are their own list** | Anything only the owner can do (listings, accounts, indexing requests, spend, price decisions) is filed with `growth journal action` and lives in `journal/OWNER-ACTIONS.md`, never only in a chat report. Every report that names one gives its number. [code: proc.owner-actions] |
| **Primary market first** | The project's primary market is in `growth.json` `market`. Google checks add the market's `gl`, `hl` and `pws=0`; AI prompts state a place in that market. A first set of checks once ran from the wrong country and gave different answers. [code: ev.ai-baseline] |
| **Simple English, answer first** | Every report, question and brief leads with the answer in plain words; a technical term is explained the first time. Text the owner will paste goes in its own plain code block. [judgment: proxy proc.plain-report] [judgment] |
| **Decide page questions from evidence** | Titles, descriptions, wording, fold order, FAQs: the agent decides from Search Console, competitors and audits, and reports after. **Claims about the business, prices, offers and calls to action stay with the owner** (`BRAND.md`). [judgment] |
| **Agents** | At most 4 agents on the project at once (lead included), unless the project's `growth.json` `agent_cap` says otherwise. Model per job: lead and reviews the strongest model; builders a mid model; log reading and counting the smallest model; a reviewer always a different model from the builder. Each agent closes its browsers and servers, removes its worktrees and scratch files, and ends with "Cleaned: ...". Enforced: `agent_models` in the Stop hook blocks a reply that starts a helper on the wrong model. [judgment] |

- **Plan and set every checkpoint before building** (from a real project: "when you start a new page the planning and
  preparation should be done in depth and all checkpoints clear set as part of that playbook and workflow"). Every
  page job starts with `growth preflight` (page rulebook 0a); the gate runs after every commit, not only at the end.

## 2. Choosing and measuring pages

| Rule | What it means |
| --- | --- |
| **Setup before page work** | No page work until `growth doctor` says every setup step is OK: inventory built, Search Console history backfilled (when connected), tracker running (flow stage A). [code: proc.doctor] |
| **Inventory first** | Work is chosen from the full inventory (`growth inventory`), never from a guess. [code: ev.inventory] |
| **Money pages first, always** | The project's money pages (`money_core` and the inventory's `money_page` flag): its main service pages, the home page, pricing, the booking page. Posts when they feed a money page. [judgment] |
| **Snapshot every page we touch** | Before and after: `growth page_snapshot`. "Search Console data" means every query with its impressions, clicks, click rate and position, plus daily figures and countries; and the analytics with it. Each touch is logged against the inventory. [code: ev.snapshot] |
| **Measure every release** | Day 7, 14, 28, 56 after the release date (flow stage E, `growth measure schedule` and `growth measure run`); one change at a time, each dated. [code: ev.rechecks, ev.rechecks-release] |

## 3. Building pages

| Rule | What it means |
| --- | --- |
| **Money pages are unique** | Each researched on its own (the questioning dossier, 10 to 20 competitors), with its own hook, journey and interactive element; no copy shared with guides or other service pages. [code: ev.dossier, hero.unique, state.url] |
| **Prototypes are real redesigns, in the real site** | Built inside the real site repo on a branch, shown on a local URL (never stand-alone HTML): a new layout from the research, the page's own interactive element, purposeful animation that honors reduced motion. The owner sees it on laptop and phone width. [code: repo.branch, page.renders, motion.reveal] |
| **Each cluster gets its own design** | A cluster's pages get UI built for that topic after research, not a copied template. [judgment] |
| **Deep, not long** | Built around how much the buyer already understands; one fact in one place; detail behind folds. [judgment] |
| **Visuals** | Hubs and lists show a cover on every card; any tool named in a list or comparison shows its logo. [code: hub.cards, post.logos] |
| **Claims** | Only what `BRAND.md` words or the live site already says or shows, in any page, picture or post (from a real project: everything on the site is true). **Search the site repo before asking; never ask the owner what the site already answers.** Only claims found nowhere on the site wait for the owner. [judgment] |
| **Navigation lands at the top; every state has a URL; copy buttons** | JSON-LD never a page's first node (Next.js adapter), `scroll-padding-top`, a regression test; for any tool or dashboard built, every state in the URL; copy buttons on values in tools **and on the public site** (page rulebook rule 131: emails, phones, URLs in source lists; never form fields or secrets). [code: seo.jsonld-first, css.scroll-padding, state.url, copy.shared] |

## 4. Releasing and the machine

| Rule | What it means |
| --- | --- |
| **The owner's yes before anything goes live** | A push to the production branch is often a live deploy. The agent never pushes to it or merges without the owner's explicit yes **in that conversation**; a yes that names pages covers those pages only. Agents and workflows never push or merge. [code: proc.no-push-main, repo.branch] |
| **Release one page at a time** | Each page alone when it is ready and approved, then the live check ([release](playbooks/release.md)). The owner requests indexing the same day. [code: proc.one-page-branch] |
| **The site stays as it is** | The kit adds no CMS, no editor and no content database. Content stays where the site keeps it; follow the site repo's own agent rules and lanes. [code: site.no-cms, repo.content-reader] |
| **Nothing starts with the computer** | No launchd, cron or systemd jobs by default: projects move between computers. Tools start by hand. A project may allow one in its own `OWNER-RULES.md`. [code: proc.doctor] |
| **Secrets** | Keys only in a file outside git (`~/.config/<tool>/<site>.env`, mode 600); never printed, copied, committed or written in docs or logs. [code: repo.no-secrets] |
| **Keep the remote private** | A project's growth folder may have a remote repository (the [foundation checklist](foundation.md) asks for a private one, so the work lives off the laptop). It stays private until the owner says public; never make it public on your own, and do not ask. The gate only warns when a remote exists, so the owner can confirm it is private. [code: proc.remote-private] |

## 4b. Extra defaults (no registry entry)

These come from owners of larger setups. They are judgment rules with no check in the gate.

- **Housekeeping**. Every agent cleans up at the end of each piece of work: stops the dev servers and browsers it started (its own pids only, never by pattern), removes its finished worktrees (branch kept), deletes its test results, screenshots and scratch files, and writes one "Cleaned: ..." line in its handoff.
- **Never pay twice for the same data**. Before any paid call (a search API, a page reader, a transcript, an AI model reading a fixed input), check your own history first. Data that never changes is kept for good; data that changes is kept for a set time that suits it (write the reason next to the number); "nothing there yet" is re-checked after a while. Match on the real identity of the thing, and record every reuse at zero cost with where it came from.
- **Memory on the machine**. Before heavy work check free memory and load; if free memory is under 20 percent or the load is high, wait instead of starting a browser run. One headless browser per agent, closed when the work ends. Prefer text snapshots over screenshots when the question is about text, order or links.

## 5. How a project adds its own rules

1. The owner says it. The agent logs it in `docs/steps-log.md` first (flow stage F).
2. The rule goes in the project's `OWNER-RULES.md` as one row: the rule, the date, what it means, and why.
3. If a program can check it, the check goes in the gate and the rule gets an entry in `rules/registry.json`.
4. A rule that is useful to every project is proposed back to this book as a change.

## Change log

| Date | Version | What changed |
| --- | --- | --- |
| 2026-11-18 | 2.0.0 | Generic edition: the default rules for any project, a project adds its own in its own `OWNER-RULES.md`. |
| 2026-11-17 | 2.1.0 | The owner reviews screens, not documents. |
| 2026-11-17 | 2.0.0 | One home for every rule: duplicates merged, grouped by topic. |
