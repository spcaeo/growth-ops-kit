---
title: The growth flow
version: 2.0.0
updated: 2026-11-18
license: CC BY 4.0
---

# The growth flow

**Version 2.0.0 (generic edition) · 18 Nov 2026.** This is the one process, start to finish, for any website. Every
other file in the book is either a fact this flow reads (`growth.json`, `SETUP.md`, `BRAND.md` in the project folder), a
rule it obeys ([02-owner-rules.md](02-owner-rules.md), [03-page-rulebook.md](03-page-rulebook.md)), or the detail of
one step (a playbook, a brief, a tool). If two files disagree about the order of work, this file wins; fix the other one.

```
 A. ONBOARD (once per project)          B. CHOOSE          C. RUN THE JOB            D. RELEASE        E. MEASURE
 A1 understand  A5 prove control        inventory    →     playbook + owner      →   owner's yes   →   day 7/14/28/56
 A2 fill config A6 task tracker         money first        check-ins                 alone, checked    act on numbers
 A3 study repo  A7 inventory            snapshot                                                          │
 A4 analytics   A8 tracker + backfill       ▲                                                            │
        │ `growth doctor` all OK             └──────────── F. LEARN: log, rules, playbook, memory ◄────────┘
```

**The short front door.** Day to day a person types six commands: `growth setup` (once: asks a few plain questions and
installs everything), `growth page <url-or-path>` (opens the page job and writes the brief), `growth check` (runs the gate on
the open job's page against the preview), `growth ready` (the gate's verdict, with a plain summary first), `growth measure`
(the day 7/14/28/56 comparison) and `growth status` (what is open and the next step). Every other tool in this book still
works on its own; the flow below names them.

**Three rules hold in every stage** (full list: [02-owner-rules.md](02-owner-rules.md)):
1. **No shortcuts.** Every step of the job's playbook, in order, with every owner check-in. A skipped step is raised
   with the owner before, never after.
2. **Lean checks.** Run only the tests a change can affect (`growth checks`). Lean means no needless checks; it never
   means skipped steps.
3. **Nothing goes live without the owner's yes,** and nothing is pushed, merged or deployed by an agent or workflow.

**Words.** The "owner" is the person who decides for the business. A "money page" is a page meant to bring a buyer to
the one conversion. A "fold" is one section of a page. "Search Console" is Google's free report on how a site shows
in search. An "agent" is an AI helper that does one job.

---

## A. Onboard (once per project)

Run `/onboard` (the skill in the kit's `skills/onboard/`) or `growth new-project <folder> --site <url>`. It walks these
steps, asks the owner only what is open, and records every answer. `growth doctor` shows which steps are done; **no
page work starts before every step is OK.**

| # | Step | How | Done when (`growth doctor` checks it) |
| --- | --- | --- | --- |
| A1 | Understand the business and the site | **First ask the owner the primary market** (country, language) and record it in `growth.json` `market`: every search, AI-answer check, keyword volume and competitor look uses it. Then read the home, about and pricing pages, sitemap, robots.txt, llms.txt. What is sold, to whom, the one conversion, the stack. | `docs/01-project-understanding.md` |
| A2 | Fill the project's config | Fill `growth.json` (site, repo, keys file, time zone, page groups, money pages, old-brand words), `SETUP.md`, `BRAND.md` and `OWNER-RULES.md`. Remove every example fact left from the template. | no template words left |
| A3 | Study the site repo end to end | Clone it; read its README, agent rules and ops guide; map each page type to its file; trace publishing (branch, checks, approval, live); run its tests and build. | `docs/02-<site>.md` |
| A4 | Connect analytics and Search Console | Use your analytics connector (recommended: [Skald](https://skaldanalytics.com), AI traffic analytics from your server log, plus Search Console; a direct Search Console connector is not yet built). Every connector is optional and the rest of the kit works without one. Keys go in a file outside git (`keys_file` in `growth.json`, mode 600), never printed. | analytics answers (or "not connected" is recorded); keys file mode 600 |
| A5 | Prove control of the live site | A tiny visible edit the owner checks live, then a rollback. | `SETUP.md` row "Control check": "done" in the status cell and the commit ids of the release and the rollback |
| A6 | Task tracker | `growth tasks` keeps `docs/tasks.json`: tasks, steps, outputs, and the owner's open questions. | the file reads |
| A7 | Full site inventory | `growth inventory --base <preview address>` (after a production build of the site, served locally; a project with `live_site_rule: no-crawl` refuses the live host): every URL with page group, pillar, cluster, type, buyer stage, words, links, Google numbers; a money-pages table. | live pages = sitemap count, built in the last 7 days |
| A7b | Site link graph | `growth link_graph crawl --base <preview address>` then `growth link_graph report --out research/link-graph-<date>.md`: every internal link of every page read from the rendered HTML (target, anchor, zone, nearest heading), inbound and outbound, orphans, weak pages, redirects, broken links, anchor problems, cluster health. File the fix list in the journal per source page (`growth journal add --page <src> --tag internal-link`). Playbook: [link-graph](playbooks/link-graph.md). | the link-graph database built in the last 7 days; report saved; fixes filed |
| A8 | Page tracker running, history backfilled | Find Search Console's first stored day and put it in `growth.json`; run the tracker's `search-history` backfill; then start the tracker each working day. **Nothing starts with the computer** (the project may move between computers). | history from the first day to the last 3 days; no auto-start job |
| A9 | Owner journal page current | `growth owner_journal --no-open` rebuilds `journal/owner-journal.html` from the steps log and the journal, so the owner can read what was asked and done. | the page is newer than the steps log and the journal |
| A10 | Agent guards installed | `growth new-project` writes `.claude/settings.json` with the Stop hook (`kit/hooks/stop_hook.sh`), which blocks an unlogged owner message, a preview address shown before READY, and a helper agent on the wrong model. | `.claude/settings.json` holds the Stop hook |
| A11 | Preview address set | Set `preview_url` in `growth.json` to the one address every review happens on. Without it the golden rule (no address to the owner before READY) is off. | `preview_url` is set |
| A12 | Hook commands find the kit | The Stop hook and status line in `.claude/settings.json` run through the `growth` command on the PATH (`bash setup.sh` links it), with the kit's folder only as the fallback. If the kit moved or the project came from a teammate, fix the link or set `GROWTH_KIT`. | every hook command resolves |
| A13 | Agent harness complete | The Stop hook (with a status message), the `hook stage` workflow guard, the status line, the permissions block, the skills, the project `CLAUDE.md` "before you act" lines and (if the owner said yes) the git hooks are all installed. `growth wizard --repair` installs what is missing and never overwrites the owner's own settings. | every piece OK or n/a |
| A14 | Research browser connected, market region set | The research browser (Claude in Chrome) is connected, and Google's Results region, read from its settings page, is the target country, confirmed by the owner. A FAIL, not a TODO: no job with a research step starts before it is OK. `growth wizard` walks through it. | `setup-state.json` holds the browser and the confirmed region |
| A15 | Work is tracked in a task | No file in the project or the site repo has changed without an open task. | no unticked work |

## B. Choose the work

1. **Inventory current:** re-run `growth inventory` if it is older than a week or the site changed.
2. **Money pages first.** Take the next page from the inventory's "Money pages" table (most Google demand with the
   weakest position and clicks), unless the owner names one. Posts are worked when they feed a money page.
3. **Open the task:** `growth tasks add "<job>: <page>" "<owner's words>"`, then copy **every step of the job's
   playbook** into it with `growth tasks step` (a step starts as todo; a done step needs `--output`) so each step is visible and ticked off. The Stop hook enforces this: it blocks while files changed and no task is open, or a done step has no proof. A chat that is not page work: `growth tasks add "Chat: <topic>" "" --type chat`.
4. **Snapshot the page:** `growth page_snapshot <path> --task T# --action "<job> start"`: its title, headings, FAQs,
   links and schema, all its Search Console data (every query with clicks, impressions, click rate, position; daily;
   countries) and its analytics (crawlers, AI visits, journeys). The touch is logged against the inventory.

## C. Run the job

Each job has a **playbook** (the steps, in [playbooks/](playbooks/README.md)). For the bigger jobs an agent tool that
supports scripted workflows can run those steps with a progress view the owner can watch; where it cannot, one agent
follows the playbook step by step and ticks each step in the task. A workflow is started only with the owner's yes,
because it starts several agents.

| Job | Playbook | Owner check-ins |
| --- | --- | --- |
| **Money page** (a service page, pricing, home) | [money-page](playbooks/money-page.md): research three ways side by side, dossier, fact check, concept; then prototype, check, research check, CRO audit, fix, independent review | 1: a few one-click questions in chat (claims, offers), never a document. 2: the prototype on a local URL, the owner's first look. 3: the yes to release. |
| Guide, "best software" list, comparison, hub, any page redesign | [cluster-redesign](playbooks/cluster-redesign.md) (snapshot, research, build, check, independent review; up to 3 pages side by side) | each page on a local URL; the yes |
| New post / post update | [new-post](playbooks/new-post.md) / [update-post](playbooks/update-post.md) | the topic first (new post); the yes |
| Fix a page from an audit | [cro-audit](playbooks/cro-audit.md), [change-a-page](playbooks/change-a-page.md) | the yes |
| A whole cluster | [cluster-redesign](playbooks/cluster-redesign.md) for its posts, then its main page through the money-page playbook | as above; a cluster is done only when its main page is |
| A fact, a lost page, a quick-exit page, an image | [fix-a-fact](playbooks/fix-a-fact.md), [lost-pages](playbooks/lost-pages.md), [leaving-pages](playbooks/leaving-pages.md), [images](playbooks/images.md) | per playbook |

What every build carries:
- **The owner reviews screens, not documents.** Research files are for the builders; the owner sees the page on a
  local link and answers short questions in chat.
- **Prototypes are real redesigns** in the real site on a local URL (never a separate mock-up): a new layout built
  from the research, the page's own interactive element, purposeful animation that honors reduced motion.
- Claims only from `BRAND.md` or the live site. A new claim waits for the owner.
- Each page in its own worktree and branch; only the checks it touches plus the technical SEO check
  (`growth tech_seo_check`, no FAIL); an independent reviewer on a different model.
- Agents close their browsers and servers, remove their scratch files and end with "Cleaned: ...".

## D. Release (the lead only, after the owner's yes)

Follow [playbooks/release.md](playbooks/release.md): each page alone, branch, pull request, the owner's yes, merge,
the host deploys, check the live title, structured data, canonical and the main call-to-action button. The owner
asks Google to re-read the page ("Request indexing") the same day. Then take the "after" snapshot
(`growth page_snapshot ... --action "released"`).

## E. Measure and act

`growth journal due --days 7` lists the re-checks coming up; each is re-run with the same query and market as the
stored baseline and logged as a new run against the page (`growth journal`, 02-owner-rules "Keep a page journal").
The research record's baseline (`growth research baseline`) is the number every re-check is compared with.

At day 28 and 56 also re-run the page's AI answers check (money-page playbook question 35): the same ChatGPT and
Google prompts, recorded next to the baseline, to see whether the page is now named or cited.

On release day file the four re-checks on their dates: `growth measure schedule <path> --release <date>` (day 7, 14, 28
and 56 after that release; `ev.rechecks-release` fails when any is missing or sits on another date). Each re-check runs
`growth measure run <path> --key <key> --release <date>`: the page's clicks, impressions and position per day, the N
days after the release against the SAME frozen baseline numbers from its research record, with searches won and lost.
A window that is not over says "not yet"; unsettled Google days make a verdict "too early". The whole site's numbers
print in their own table and are never read as the page's.

The page tracker keeps the release date. Look at day 1 to 3 (re-crawled?), day 7 (first look), day 14 (click rate and
position), day 28 (rankings, clicks, engagement, conversions) and day 56 (conversions). What each result means and
what to change next is the table in the money-page playbook, Part 4. One change at a time, each dated, so every number
can be traced to its cause. Report to the owner at day 14, 28 and 56.

## F. Learn (every time the owner says something)

The moment the owner gives an instruction or a correction, before reporting:
1. Log it in `docs/steps-log.md` (the owner's words and what it means), and the work in `docs/tasks.json`.
2. Put the rule in its **one** home (no copies): how we work, in the project's `OWNER-RULES.md`; how a page is built,
   in the page rulebook; the order of work, in this flow; the steps of one job, in its playbook; a project fact, in
   `growth.json` or `SETUP.md`; what may be said, in `BRAND.md`. Other files link to it.
   **If a program can check the rule, the rule is code** (02-owner-rules "Rules are code"): add its check to the gate
   and its entry to `rules/registry.json` in the same commit. A rule that lives only in a .md file is a guideline, not
   a rule.
3. Add the reusable form to your cross-project lessons file (see [lessons.md](lessons.md) for the shape).
4. The owner's journal page (`journal/owner-journal.html`: instructions, to-dos, page journal) is kept current: it
   rebuilds on every `growth journal` write and every `growth owner_messages check`, and `growth doctor` fails when
   it is older than the steps log or the journal (from a real project: "keeping the journals updated is your job").
5. Update the agent's memory only with what the files above can't hold (the project's current state, the why behind a
   correction).

## G. Helpers (agents) follow everything, checked not trusted

From a real project: "are your agents following the guide, SOP, background data, all of it 100%, not a single item
missed?"
1. Every helper's brief is generated: `growth brief <path> --type ... --task ... --out research/briefs/<key>.md`
   (all rules in scope, every playbook step, every owner instruction word for word, the agent rules, the finish
   list). The lead adds only the job; the helper reads the brief in full first.
2. Each new owner instruction: regenerate the brief and send the new rows to every live helper it touches.
3. A helper's report is checked, not trusted: the lead re-runs the gate and reads the task steps before telling the
   owner anything, and an independent reviewer (a different model) reads every page before release (rule 109).

## H. The golden rule: no URL before READY

From a real project: "never share a URL with me before it is 100% approved and checked; this cannot be broken."
1. A page goes to the owner only when `growth ready <path> --type ... --key ...` says READY: the full gate, 0 FAIL, on
   the one preview address at the current commit (`journal/ready.json`). No "known" FAILs are excused.
2. Any commit after READY makes it STALE: run `growth ready` again before the link is shared again.
3. The agent's Stop hook (`stop_hook.sh`, which runs `url_guard`) blocks a reply that shows a local page URL that is
   not READY; the reply is corrected before the turn ends.

## Pre-flight

No page is built until `growth preflight` says PASS: planning complete, shared site problems fixed first, every
checkpoint written down by when it runs; then the gate runs after every fold commit (page rulebook rule 0a,
money-page playbook step 3b).

## Where things live

In the project folder (made by `growth new-project`):

| Folder or file | What it is |
| --- | --- |
| `growth.json` | The project config every tool reads |
| `SETUP.md`, `BRAND.md` | The project's facts; what may and may not be claimed |
| `OWNER-RULES.md` | The owner's extra rules on top of [02-owner-rules.md](02-owner-rules.md) |
| `docs/` | Steps log, task list, study notes |
| `journal/` | The page journal, the owner's actions, the owner journal page |
| `research/` | Audits, dossiers, concepts, screenshots, plans, briefs |
| `inventory/`, `archive/` | The inventory and page snapshots; the before and after copies of pages |

In the kit (one checkout shared by every project): the book (this folder), `kit/tools/` (the `growth` commands),
`kit/page-tracker/`, `kit/rules/registry.json`, `kit/hooks/` and `kit/skills/`.

## Change log

| Date | Version | What changed |
| --- | --- | --- |
| 2026-11-18 | 2.0.0 | Generic edition: project facts removed; tools are `growth <tool>`; the connectors are optional. |
| 2026-11-17 | 1.0.0 | First version: one flow for onboarding, choosing, running, releasing, measuring and learning. |
