---
title: Agent brief templates
version: 2.0.0
updated: 2026-11-18
license: CC BY 4.0
---

# Agent brief templates

**Version 2.0.0 (generic edition) · 18 Nov 2026**

A **brief** is the written job description an agent reads before it starts. Each file here is a template: fill the
`__PLACEHOLDERS__` and send it as the agent's task (or point the agent at the file and give it the values). In a real
project the lead does not fill them by hand: `growth brief <path> --type ... --task ... --out research/briefs/<key>.md`
generates the brief with every rule in scope, every playbook step, every owner instruction, the agent rules and the
finish list (flow stage G). These templates are the base the generator and a human lead both start from.

The examples use Brightline Lawn Care (https://brightline.example), a lawn-care service company whose one CTA is
"Get a quote".

## The shared blocks

Every brief ends with the two blocks below. Paste the one that fits.

### Block 1: BUILDER RULES (any brief that writes files)

```
- LOCAL ONLY. Never push, never merge, never touch the production branch: on many hosts a push there is an instant
  live deploy. Never run a deploy command. The lead asks the owner before anything goes up.
- Work only in your own worktree and branch. Never edit the main checkout or another worktree. Touch only the files
  this brief names; another agent may be working in the same repo.
- Commit by path, never `git add -A`. Keep the repo's own git identity (__COMMIT_IDENTITY__); never change git config.
  End each commit message with the attribution line your own instructions give.
- The URL scheme is frozen. Never rename a slug or change a route path (rule 73).
- Claims: only what the live site says today, or what __PROJECT__/SETUP.md and __PROJECT__/BRAND.md record. Never
  invent a customer, case study, number, award, review, certification or price. Anything not sourced goes under
  "Needs the owner" in your report. Use the project's one CTA label, "__CTA__", and the words BRAND.md allows.
- A web page behind a bot check is never read by ANY route. Read vendor and competitor pages one request at a time.
- Do not browse the live site (it counts as a visit in analytics): read the repo and your local server.
- No secrets in files, logs, chat or reports. No sub-agents. Every file under 1,000 lines.
- Memory: before a build or a browser run, check free memory and load. If free memory is under 20% or the load is
  high, wait. One headless browser at a time. Text snapshots beat screenshots when the question is about text,
  order or links.
- Dev server: start it on your own port (__PORT__); stop it by its port, never by pattern (never `pkill -f`).
- Cleanup: at the end close every browser you opened, stop your own dev server, delete your screenshots, test
  results and scratch files (keep only what this brief says to keep), leave the worktree clean, and end your report
  with one line: "Cleaned: ...".
```

### Block 2: READ-ONLY RULES (any brief that only reads and reports)

```
- You write ONLY the one output file this brief names. You change no other file, make no commit, and push nothing.
- Read the site from the repo (or your page's worktree) and from a local dev server on __PORT__ (stopped by its port).
  Do not browse the live site.
- Claims about the business come only from the site, __PROJECT__/SETUP.md and __PROJECT__/BRAND.md. Never invent a
  customer, number, award, review or price. What you cannot source goes under "Needs the owner" or "Could not verify".
- A web page behind a bot check is never read by ANY route; write "not readable". Read competitor and vendor pages one
  request at a time, and give each fact a source URL and the date read.
- Search-result data: check __PROJECT__/research/serp/ first and reuse what is there (never pay twice for the same
  data). Fetch new results only with the search-data tool the lead names; if none is named, say so and work without it.
- Analytics and Search Console come through your connector if its tools are loaded (keys live in the file named in
  growth.json `keys_file`: never print, copy or commit them). If the page tracker exists, read it too. If neither gives
  data, write "no search data yet". Never guess traffic.
- No secrets. No sub-agents. One headless browser at a time, closed when you finish.
- Cleanup: stop your dev server, close every browser, delete scratch files, then end your report with one line:
  "Cleaned: ...".
```

## The briefs

| File | Job | Read-only? | Placeholders |
| --- | --- | --- | --- |
| [brief-cro-auditor.md](brief-cro-auditor.md) | Nine-step CRO audit of ONE page (CRO = making more of the right visitors take the next step). Writes `research/<w>-cro-audit-<date>.md`. | yes | `__FILE__` `__URL__` `__W__` `__PORT__` `__DATE__` |
| [lane-write.md](lane-write.md) | **The writer-lane brief.** Fixes one page from its audit, quick checks only, commits on `page/<slug>`. A tester takes over after. | no | `__FILE__` `__URL__` `__SLUG__` `__W__` `__PORT__` `__AUDIT__` `__RULE__` `__DO__` |
| [brief-cro-fix.md](brief-cro-fix.md) | The same fix pass as a stand-alone job (when you do not run lanes). | no | `__FILE__` `__URL__` `__SLUG__` `__W__` `__PORT__` `__AUDIT__` `__DO__` |
| [brief-fix.md](brief-fix.md) | Fix a small set of pages after an audit (MUST and SHOULD items, cuts, links, facts). | no | `__PAGES__` `__SLUG__` `__W__` `__PORT__` `__AUDIT__` `__DATE__` |
| [research.md](research.md) | Deep content research for one page that will be rebuilt: searchers, gaps, fact base, claim check, interactive ideas, outline. | yes | `__FILE__` `__URL__` `__SLUG__` `__PORT__` `__DATE__` `__KW__` `__SERP__` `__RELATED__` `__QUESTIONS__` |
| [brief-redesign.md](brief-redesign.md) | Build ONE page with its own UI, signature element and journey, on a local URL for the owner. | no | `__FILE__` `__URL__` `__SLUG__` `__W__` `__PORT__` `__DATE__` `__BRIEF__` `__TITLE__` `__EXTRA__` |
| [brief-guide.md](brief-guide.md) | Rebuild one long guide post. | no | `__FILE__` `__URL__` `__SLUG__` `__W__` `__PORT__` `__DATE__` `__KW__` `__SERP__` `__TITLE__` `__STEP0__` |
| [brief-alt.md](brief-alt.md) | Rebuild one "best list" or "alternatives" post, fair to every vendor. | no | same as the guide brief |
| [brief-vs.md](brief-vs.md) | Rebuild one "X vs us" comparison (or a method vs us), fair and sourced. | no | `__COMPETITOR__` plus the same as the guide brief |
| [brief-hub.md](brief-hub.md) | Rebuild one cluster hub as a reader's map. | no | `__CLUSTER__` `__SLUG__` `__W__` `__PORT__` `__DATE__` |
| [brief-hub-upgrade.md](brief-hub-upgrade.md) | Bring a hub up to an approved hub standard: interactive top, a picture on every card. | no | `__CLUSTER__` `__SLUG__` `__W__` `__PORT__` `__MODELS__` |
| [brief-money-page-dossier.md](brief-money-page-dossier.md) | Research dossier for one money page: buyers, competitors read one by one, content map, claims we can make, hook and journey ideas. Builds nothing. | yes | `__PAGE__` `__PORT__` `__DATE__` |
| [brief-money-impl.md](brief-money-impl.md) | Build one money page as a prototype from its dossier, local URL, waits for the owner. | no | `__PAGE__` `__SLUG__` `__W__` `__PORT__` `__DATE__` `__HISTORY__` `__APPROVED__` |
| [brief-sibling-fixes.md](brief-sibling-fixes.md) | Clean-up lane: collect the "sibling changes for the lead" that page lanes left, check, and apply. | no | `__JOURNALS__` `__PORT__` `__DATE__` |
| [verify.md](verify.md) | **The one generic verify brief.** An independent checker finds what is wrong on a rewritten page (facts, fairness, links, pictures, site rules). Report only. | yes | `__FILE__` `__SLUG__` `__W__` `__PORT__` `__DATE__` |

Placeholders not explained by their name: `__PROJECT__` the project folder; `__SITE_NAME__` the business's site name; `__WT_ROOT__` the folder that holds the worktrees; `__CTA__` the one CTA label from
`BRAND.md`; `__COMMIT_IDENTITY__` from `growth.json`; `__DO__` the lead's decisions for the page in plain words;
`__STEP0__` an extra instruction for the fact-check step (or blank); `__SERP__` the search results for the keyword, a
file path under `research/serp/` (reuse before you fetch: never pay twice for the same data); `__RULE__` a rulebook
number reserved for the page so two lanes never take the same one (only used if the page must add a rule);
`__HISTORY__` and `__APPROVED__` what earlier versions the owner rejected and which approved pages are the bar.

## The layout the briefs assume

| Thing | Where |
| --- | --- |
| Site repo (main checkout, never edited by agents) | `growth.json` `site_repo` |
| One worktree per page | next to the clone, `wt-<w>`, branch `page/<slug>` (other prefixes the site allows: `article/`, `fix/`, `design/`) |
| Research output (audits, facts, dossiers, verify reports, screenshots) | the project's `research/` (git tracks it; `research/raw/` is git-ignored scratch and holds `lanes-ready.txt`) |
| Checks every tester runs | only what the change touches: `growth checks` (rule 105); a browser look only when layout changed |
| Companion files the briefs point to | `SETUP.md`, `BRAND.md`, `OWNER-RULES.md` in the project; the page rulebook and the playbooks in the book |

## Models

Lead and design: the lead's own model. Builders and testers: a mid model, medium effort. Independent reviewers
(`verify.md`): a different, stronger model. Reading logs and counting: the smallest model. Never more than the
project's agent cap in total (default 4): lanes run at most 3, which leaves one for the lead.
