---
name: onboard
description: Onboard a website onto this growth kit, or re-check an existing setup. Walks stage A of the flow (the setup steps `growth doctor` lists), using `growth doctor` to see what is done, asks the owner only what is still open, records every answer, and stops when doctor says 8/8. Use on a new project, when the user asks to set up, check, connect or re-run onboarding, or at the start of a session when doctor is not green.
---

# Onboard (re-runnable)

Goal: `growth doctor` says **every step OK**, and the project's `growth.json`, `SETUP.md` and `BRAND.md` are true. The skill never
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

## Step 1. Where are we

Run `growth doctor`. Read the project's `growth.json`, `SETUP.md`, `BRAND.md`, `docs/steps-log.md` and
`growth tasks list`, and the book's `01-flow.md`. Make the list of steps not yet OK.

## Step 2. Do each open step, in order (book/01-flow.md A1 to A8)

| Step | What you do | Ask the owner only |
| --- | --- | --- |
| A1 Understand | Ask first: the primary market (country and language), saved to `growth.json` `market`. Then plain requests (no browser on the live site: it counts as a visit): home, about, pricing, sitemap, robots.txt, llms.txt. Write `docs/01-project-understanding.md`. | the short name; anything the site does not say |
| A2 Adapt the project | Fill `growth.json` (site, sitemap, `stack`, repo, committer email, keys file, time zone, silos, money pages, core pages, old brand words, `cta`, `words`, `features`). Write `SETUP.md` and `BRAND.md` (claims with their source), and `OWNER-RULES.md` if the owner has rules of their own. Remove every old-brand fact until doctor A2 is OK. | which repo publishes the site, or none (then the live-page checks still run) |
| A3 Study the site repo | Clone; read README, agent rules, ops guide; map page types to files; trace publishing (branch → checks → approval → live; queues, cron jobs and whether they really work); run its tests and build in a worktree. Write `docs/02-<site>.md`. On a Next.js site, map its tests to `kit/adapters/nextjs/checks.sh`. | who says yes before a merge |
| A4 Analytics + Search Console | Read the analytics tool's setup page; take the keys with the owner's one-time code (curl only, umask 077); add the MCP server in this project's folder; test a read-only call. Record the first numbers as the baseline. Optional: switch the connectors on in `growth.json` `connectors` only when their keys exist. | the one-time code (pasted by the owner) |
| A5 Prove control | A tiny visible edit on a branch, checks it touches, the owner's yes, live check; rollback on the owner's word. Mark the SETUP row "Control check: done". | the yes to publish, then to roll back |
| A6 Task tracker | `docs/tasks.json` via `growth tasks` (the template starts it empty). | nothing |
| A7 Inventory | Production build of the site, then `growth inventory`. Live pages must equal the sitemap count. | nothing |
| A8 Tracker + backfill | Find Search Console's first stored day (3-month windows), put it in `growth.json` `search_console_history_start`, run `growth page-tracker search-history`, then `growth page-tracker sync` and `serve` once. Never install a start-up or scheduled job. | nothing |

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
