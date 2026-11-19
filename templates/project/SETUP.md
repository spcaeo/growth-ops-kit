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
| 1 | The site | <fill in> | sitemap, robots |
| 2 | Clusters (page groups) | <fill in> | sitemap, repo |
| 3 | The code | <fill in> | repo |
| 4 | Publishing | <fill in> | repo, host |
| 5 | Lanes in the site repo | <fill in> | repo rules |
| 6 | The business | <fill in> | site |
| 7 | Analytics | <fill in> | live HTML, a test call |
| 8 | Agents and machine | <fill in> | owner |
| 9 | Retired pages and old hosts | <fill in> | repo, redirect config |

<!-- What goes in each <fill in> cell above (delete this comment when done):
  - The site: address, languages and regions, sitemap address and URL count with the date, robots.txt, llms.txt
  - Clusters (page groups): core pages; each cluster with its money page and where its posts live; the address scheme (rule 73)
  - The code: the repo, the stack, where content lives, the one module that reads it (rule 104), how to run tests and build
  - Publishing: the host, the production branch, what a push does, branches and prefixes, any date gate or queue (rule 117), the commit identity (rule 118)
  - Lanes in the site repo: who edits design, content and code; shared files that clash (04-lanes-and-releases)
  - The business: what is sold, to whom, the one conversion, pricing in words. Point at `BRAND.md` for the wording
  - Analytics: the connectors in use (analytics, Search Console, Bing), the keys file path (never its contents), what is not connected
  - Agents and machine: the computer, the agent cap, the time zone
  - Retired pages and old hosts: page groups that answer 410 on purpose (rule 76), old hosts and addresses (rule 78)
-->

## What was set up

| Piece | Where | Status |
| --- | --- | --- |
| Setup facts, brand sheet, owner rules | `SETUP.md`, `BRAND.md`, `OWNER-RULES.md` | <fill in> |
| Inventory | `inventory/` | <fill in> |
| Link graph | `inventory/link-graph.db` | <fill in> |
| Page tracker | the tracker folder | <fill in> |
| Analytics connector | <fill in> | <fill in> |
| Control check: edit the live site and roll back | <fill in: the two commits> | <fill in: done or not> |

<!-- What goes in each <fill in> cell above (delete this comment when done):
  - Page tracker: started by hand; no auto-start
-->

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
