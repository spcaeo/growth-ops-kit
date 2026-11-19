---
title: Setup record
version: 0.1.0
updated: <fill in: date>
---

# Setup record

Started <fill in: date>. This folder is the growth system for **<fill in: business name>** (<fill in: site address>),
made from the Growth Ops Kit. The values the tools read are in `growth.json`; the setup state is `growth doctor`
(the steps `growth doctor` lists, flow stage A).

## Answers

Fill one row per question during onboarding. Each answer says how we know.

| # | Question | Answer | How we know |
| --- | --- | --- | --- |
| 1 | The site | <fill in: address, languages and regions, sitemap address and URL count with the date, robots.txt, llms.txt> | sitemap, robots |
| 2 | Clusters (page groups) | <fill in: core pages; each cluster with its money page and where its posts live; the address scheme (rule 73)> | sitemap, repo |
| 3 | The code | <fill in: the repo, the stack, where content lives, the one module that reads it (rule 104), how to run tests and build> | repo |
| 4 | Publishing | <fill in: the host, the production branch, what a push does, branches and prefixes, any date gate or queue (rule 117), the commit identity (rule 118)> | repo, host |
| 5 | Lanes in the site repo | <fill in: who edits design, content and code; shared files that clash (04-lanes-and-releases)> | repo rules |
| 6 | The business | <fill in: what is sold, to whom, the one conversion, pricing in words. Point at `BRAND.md` for the wording> | site |
| 7 | Analytics | <fill in: the connectors in use (analytics, Search Console, Bing), the keys file path (never its contents), what is not connected> | live HTML, a test call |
| 8 | Agents and machine | <fill in: the computer, the agent cap, the time zone> | owner |
| 9 | Retired pages and old hosts | <fill in: page groups that answer 410 on purpose (rule 76), old hosts and addresses (rule 78)> | repo, redirect config |

## What was set up

| Piece | Where | Status |
| --- | --- | --- |
| Setup facts, brand sheet, owner rules | `SETUP.md`, `BRAND.md`, `OWNER-RULES.md` | <fill in> |
| Inventory | `inventory/` | <fill in> |
| Link graph | `inventory/link-graph.db` | <fill in> |
| Page tracker | the tracker folder | <fill in: started by hand; no auto-start> |
| Analytics connector | <fill in> | <fill in> |
| Control check: edit the live site and roll back | <fill in: the two commits> | <fill in: done or not> |

## What is still waiting on the owner

The live list is `growth tasks list` (open questions). <fill in the ones that matter on the first day>

## Speed baseline (rule 154)

Fill after the first production build, with Lighthouse on a production build and analytics blocked. Scores are out of
100 (performance / accessibility / best practices / SEO).

| Page | Mobile scores | Mobile LCP | Mobile CLS | Desktop scores | Desktop LCP | Desktop CLS |
| --- | --- | --- | --- | --- | --- | --- |
| / (home) | | | | | | |
| a money page | | | | | | |
| the blog list | | | | | | |
| a post | | | | | | |
| contact | | | | | | |
