---
name: onboard
description: Onboard a website onto this growth kit, or re-check an existing setup. Walks stage A of the flow (the setup steps `growth doctor` lists), using `growth doctor` to see what is done, asks the owner only what is still open, records every answer, and stops when doctor's last line says every step is done (the count is whatever doctor prints; it grows with the kit). Use on a new project, when the user asks to set up, check, connect or re-run onboarding, or at the start of a session when doctor is not green.
---

# Onboard (re-runnable)

Goal: `growth doctor` says **every step OK** (its last line, `N/N setup steps done.`, with N equal to the number of steps it lists; BUSY counts as done), and the project's `growth.json`, `SETUP.md` and `BRAND.md` are true. The skill never
starts from zero: it reads what is recorded, skips what is done, and asks only what is open. The steps and their
"done when" are in the book, [01-flow.md](../../../book/01-flow.md) stage A; the rules are [02-owner-rules.md](../../../book/02-owner-rules.md)
(the project may add its own `OWNER-RULES.md`). Work inside the project folder (the one holding `growth.json`), made with
`growth new-project <folder> --site <url>`.

## How to ask

- One question at a time (AskUserQuestion): 2–4 options, your recommendation first, simple English.
- Look for the answer yourself first (files, the site, the repo). Ask only what you cannot find, and say what you found.
- Record each answer the moment you get it (`growth.json`, `SETUP.md` row with date and source, or `BRAND.md`), and log
  the owner's words in `docs/steps-log.md`, so a stopped run resumes.
- Never ask for a secret in chat. Keys come only through the analytics tool's one-time code into
  the file named in `growth.json` `keys_file` (outside git, mode 600) and are never printed.

## Step 0. Run the setup

Run `growth setup` in the project folder (or `growth setup <folder> --site <url>` for a new one). With a person at a terminal it asks
plain questions; as an agent you have no terminal, so it runs the wizard's question-and-answer protocol described next (`growth wizard`
is the same thing, called directly). It does the setup in
order and remembers where it is in `setup-state.json` (each answer with its date, source and test), so a stopped run
resumes at the first open step. When it prints `QUESTION <step>: ...` and stops (exit code 3), ask the owner that one
question (see "How to ask"), record the answer with `growth wizard answer <step> '<json>'`, and run `growth setup` again. When it
prints `WAITING browser` or `WAITING region`, walk the owner through the guided step (A14 below). The wizard opens the
setup task ("Project setup": one step per doctor step) and doctor ticks it, so the status bar shows setup progress from
the first question. Setup is **not done** until the research browser is connected and the target country's Google region
is set and confirmed by the owner (A14); no research step may start before that.

## Step 1. Where are we

Run `growth doctor`. Read the project's `growth.json`, `SETUP.md`, `BRAND.md`, `docs/steps-log.md` and
`growth tasks list`, and the book's `01-flow.md`. Make the list of steps not yet OK.

## Step 2. Do each open step, in order (every step doctor lists, in the order it lists them; book/01-flow.md stage A)

| Step | What you do | Ask the owner only |
| --- | --- | --- |
| A1 Understand | Ask first: the primary market (country and language), saved to `growth.json` `market`. Then plain requests (no browser on the live site: it counts as a visit; when growth.json says `live_site_rule: no-crawl`, the kit's own crawlers refuse the live host and need `--base <preview address>`): home, about, pricing, sitemap, robots.txt, llms.txt. Write `docs/01-project-understanding.md`. | the short name; anything the site does not say |
| A2 Adapt the project | Fill `growth.json` (site, sitemap, `stack`, repo, committer email, keys file, time zone, silos, money pages, core pages, old brand words, `cta`, `words`, `features`). Write `SETUP.md` and `BRAND.md` (claims with their source), and `OWNER-RULES.md` if the owner has rules of their own. Remove every old-brand fact until doctor A2 is OK. | which repo publishes the site, or none (then the live-page checks still run) |
| A3 Study the site repo | Clone; read README, agent rules, ops guide; map page types to files; trace publishing (branch → checks → approval → live; queues, cron jobs and whether they really work); run its tests and build in a worktree. Write `docs/02-<site>.md`. On a Next.js site, map its tests to `kit/adapters/nextjs/checks.sh`. | who says yes before a merge |
| A4 Analytics + Search Console | Read the analytics tool's setup page; take the keys with the owner's one-time code (curl only, umask 077); add the MCP server in this project's folder; test a read-only call. Record the first numbers as the baseline. Optional: switch the connectors on in `growth.json` `connectors` only when their keys exist. | the one-time code (pasted by the owner) |
| A5 Prove control | A tiny visible edit on a branch, checks it touches, the owner's yes, live check; rollback on the owner's word. Fill the SETUP row "Control check": the commit ids of the release and the rollback, and "done" in the status cell. | the yes to publish, then to roll back |
| A6 Task tracker | `docs/tasks.json` via `growth tasks` (`growth new-project` opens task T1 "Project setup" with one step per doctor step; add your own tasks next to it). | nothing |
| A7 Inventory | Production build of the site, serve it, then `growth inventory --base <preview address>` (never the live site on a no-crawl project). Live pages must equal the sitemap count. | nothing |
| A7b Link graph | `growth link_graph crawl --base <preview address>` (weekly, or after each release); file the fix list in the journal. | nothing |
| A8 Tracker + backfill | Find Search Console's first stored day (3-month windows), put it in `growth.json` `search_console_history_start`, run `growth page-tracker search-history`, then `growth page-tracker sync` and `serve` once. Never install a start-up or scheduled job. | nothing |
| A9 Owner journal | `growth owner_journal --no-open` rebuilds `journal/owner-journal.html`. BUSY right after a log line is normal: the Stop hook rebuilds it. | nothing |
| A10 Agent guards | `growth wizard --repair` adds the missing `.claude` files (the Stop hook); never overwrites. | nothing |
| A11 Preview address | Set `preview_url` in `growth.json` to the one address every review happens on. | the preview address, if you cannot find it |
| A12 Hook commands find the kit | `growth wizard --repair` rewrites old absolute-path hook commands to `growth hook stop` / `growth statusline`. | nothing |
| A13 Agent harness complete | `growth wizard --repair` installs what is missing (Stop hook with its status message, status bar, permissions block, skills, CLAUDE.md lines, git hooks the owner said yes to); never overwrites the owner's own settings. | nothing, unless git hooks were never answered |
| A14 Research browser connected, market region set | The wizard's two guided steps. Browser: the owner types `/chrome` in Claude Code, picks the browser, checks "By default: on"; the owner then runs, in their own terminal, `growth approve browser --name "<name>"` (you cannot: it needs the owner's terminal and is denied to you). Region: open Google's Search settings in that browser, read the Results region it reports (never trust a note that it is set; "Current Region" is a failure), tell the owner what it says, and the owner runs `growth approve region --seen "<what Google says>"` in their own terminal. Re-check at the start of each research step with `growth wizard research-check --connected "<names from list_connected_browsers>"`. | the browser to use; yes that the region is right |
| A15 Work is tracked in a task | Open a task for the work (`growth tasks add ...`, steps copied from the playbook, each ticked with proof). A chat that is not page work: `growth tasks add "Chat: <topic>" "" --type chat`. | nothing |

## Step 3. Drift check (on a re-run)

When everything was already OK, check the record is still true: sitemap count and silos, the repo's last commit and
stack versions, publishing files (CI workflows and the host's config files), the site's call-to-action and price wording
against `BRAND.md`, tracking ids. Update any row that changed, with the date.

## Step 4. Report

Doctor's table, then in simple English: what changed, what waits on the owner (numbered), and the next job from book/01-flow.md
stage B (the top money page in the inventory). Log the run in `docs/steps-log.md`.

## Never

Push or merge to the site's `main` or deploy; change how the site stores or publishes content; browse the live site in a
browser; print, copy or commit a key; install start-up or scheduled jobs; leave worktrees, servers or browsers behind
(end with "Cleaned: ...").
