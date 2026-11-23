---
title: Lanes and releases
version: 2.0.0
updated: 2026-11-18
license: CC BY 4.0
---

# Lanes and releases: how to improve many pages fast

**Version 2.0.0 (generic edition) · 18 Nov 2026.** The parallel "page lanes" method: a branch and a pull request in the
site repo, the owner's yes, a merge to the production branch, and the host's deploy. The hard lessons in it came from a
rebuild of about 30 releases a night at best. They are kept because they are about method, not about a site. Read it
with [playbooks/release.md](playbooks/release.md).

## Which workflow for which job

The table of jobs, playbooks and owner check-ins is in [01-flow.md](01-flow.md) stage C (one copy only).

## The idea in one paragraph

A **lane** is a production line for pages. It takes one page at a time through three steps: **audit** (read the page as
a visitor would, study its Google searches and competitors, list what is wrong), **write** (fix it), **test** (run
every check, look at it in a browser, fix what fails, mark it ready). Each lane works in its **own private copy of the
site** (a git worktree), so two lanes cannot break each other. Several lanes run side by side. **The lead** (one agent
session, the one the owner talks to) starts the lanes, reviews each ready page, pushes its branch, opens its pull
request, asks the owner, and after the owner's yes merges it. Merging to the production branch is the release: the
host deploys it. Every page goes live on its own as soon as it is ready and approved; nobody waits for a batch.

```
   lane 1:  audit -> write -> test -> "ready" -+
   lane 2:  audit -> write -> test -> "ready" -+-> lead: review -> push branch -> pull request
   lane 3:  audit -> write -> test -> "ready" -+        -> owner's yes -> merge -> host deploys -> live check
   (a post for a daily queue goes to the queue branch instead of a pull request: see release.md, route B)
```

## The numbers that limit it

- **At most 4 agents at once on the project (the default cap in `growth.json` `agent_cap`):** the lead plus up to 3
  lanes. An independent reviewer agent counts as one of the four, so with a reviewer running there are 2 lanes, not 3.
  Agents never start agents.
- **The limit is also the machine,** not only the number of lanes. A lane runs a dev server and sometimes a full
  build. Before starting heavy work check free memory and load; if free memory is under 20 percent or the load is
  high, wait. Build one lane at a time. Browsers are headless where possible, one per agent, closed when the check ends.
- **The owner's yes is the real speed limit.** Ask for several ready pages in one message, each named with its pull
  request and its addresses ("pages A, B, C are ready; may I merge all three?"). A yes that names the pages covers
  those pages only.

## The parts

| Part | What it is | Where it lives |
| --- | --- | --- |
| Lane | One agent, one page (or one small job), one worktree, one branch | `git worktree add ../wt-<lane>-<slug> -b <kind>/<slug> origin/main`, next to the clone |
| Lane brief | What the lane must audit, fix, check and never touch (template below) | written by the lead per page; see [prompts/lane-write.md](prompts/lane-write.md) |
| Audit | The nine-step audit | [playbooks/cro-audit.md](playbooks/cro-audit.md) |
| Playbook for the job | new post, update, fact, links, redirects, money page | [playbooks/](playbooks/README.md) |
| Checks | only the checks the change touches (`growth checks`, rule 105), the two studio reports, a look in a browser | [playbooks/change-a-page.md](playbooks/change-a-page.md) |
| Ready file | Each lane appends `<lane> ready <commit>` (or `blocked <reason>`) to one text file in the scratchpad | `lanes-ready.txt` |
| Watcher | The lead watches the ready file (for example `tail -f ... \| grep ready`) and reviews each page as its line appears; re-arm it when it expires | the agent tool's monitor |
| Release | Push branch, pull request, owner's yes, merge, host deploy, live check, clean up | [release.md](playbooks/release.md) route A |
| Queue | New posts the owner approved wait on a queue branch; one goes live a day | [release.md](playbooks/release.md) route B |

## One page, start to end

1. **The lead prepares the lane.** Picks the page, writes the brief, reserves a port for the lane's dev server (for
   example 3701, 3702, 3703; check what is listening on it first), makes the worktree from the **current** production
   branch, and gives the lane its dependencies: link the clone's `node_modules`
   (`ln -s <clone>/node_modules <worktree>/node_modules`), or run a clean install in the worktree if a build complains
   about the link. **Try this on the first lane alone before starting three.** Check `git config user.email` in the
   worktree (rule 118).
2. **Audit (read only).** The audit file goes in the project's `research/`.
3. **Write.** The lane fixes what the audit found, edits only its own page's files, runs the quick checks, and does
   not build. Changes other pages need go in its report as "sibling changes for the lead".
4. **Test.** The lane merges the current production branch in, runs only the checks the change touches
   (`growth checks`), looks at the page (only if layout changed) at the widths of page rulebook rule 106 (360 to
   1920), fixes what fails, commits, and appends `<lane> ready <commit>`.
5. **Review.** The lead reads the diff and the page, and checks `git log origin/main..<branch>` shows the commit the
   lane named. An independent reviewer (a different model from the writer) reads money pages and anything with a
   claim about the business.
6. **Release.** The lead pushes the branch, opens the pull request, asks the owner, merges after the yes, and does the
   live check ([release.md](playbooks/release.md)). A failure stops that page, not the others.
7. **Clean up.** The lead removes the finished worktree and local branch, stops the lane's dev server, and removes
   scratch files. The lane's last line is "Cleaned: ...".
8. **Measure.** Day 7, 14, 28, 56 from the release date (release.md "Measure"; the page tracker holds the change dates).
9. **After a cluster:** one clean-up job for the sibling changes (links back, stale facts elsewhere), and **the
   cluster's main page** updated: a cluster is not done until its main page is.

## Shared files: the clashes

Many sites keep a few shared files that every new post edits: an artwork map, a cover list, a hub's "last modified"
date, a list of related posts. Two lanes adding a post at the end of the same list will clash when the second one
merges. The rules:

- **Release one lane at a time, then rebase the next on the new production branch** (`git rebase origin/main`) and
  keep both entries. Never resolve by "take mine".
- **Do not use a "union" merge setting on these code files:** it can silently produce a duplicate key or break the
  syntax. Resolve by hand and let the tests prove it.
- A lane that is not writing a post does not touch these files.
- A queue branch has the same problem every day; see release.md route B.

The project lists its own shared files in `SETUP.md`.

## Many pages at once: the page flow (2.8.0)

From a real project (23 Nov 2026): 12 pages went through four review rounds in one day and none was accepted. Each round
fixed 30 to 50 findings and the next round found as many new ones; ready ran one page at a time (25 minutes for 12);
builders waited for the reviewer and the reviewer waited for builders; one commit anywhere made every page not READY. The
owner: "the process is fully broken, the speed is super slow, the process runs in sequence vs in parallel". The fixes:

- **Pages flow one by one, never in rounds.** Queues, not batches: planned -> plan reviewed -> built -> reviewed (0
  BLOCKING) -> READY -> accepted. Each page moves on its own and counts the moment it is accepted. No page waits for
  another page's review, and the next pages start while earlier ones are reviewed.
- **The reviewer is always on.** It takes pages from the "built" queue while the builder builds the next ones (the
  builder stays 2 to 3 pages ahead). A page sent back goes to the front of the builder's queue.
- **Review the plan before the build** (about 5 minutes): the fact inventory and the fold plan. Borrowed drawings,
  proof from another field, two folds doing one job and a fact said three times are cheapest to fix on paper.
- **Fact inventory first.** Before writing a fold, list every fact the page states, its source, and the folds it sits
  in. Each fact is said once in full, with at most one short echo in the hero or a call to action
  (words.fact-repeats checks it).
- **BLOCKING or NIT, nothing in between.** BLOCKING: an unsourced or wrong claim, internal wording a buyer can read, a
  part broken or cut at any width, an empty half or an orphan, a fact said three or more times, two folds with one job or
  one shape, a drawing that tells another page's story. Everything else is a NIT on a list; a NIT never blocks a page.
  A page is accepted at 0 BLOCKING. A second look checks the closures plus a fresh look for BLOCKING only.
- **Two strikes, then a machine.** A finding class seen on two pages becomes a check (a site test, or a kit check) the
  same day, and every page in the queue and every accepted page is checked against it. A reviewer is for judgement,
  not for counting repeats.
- **Fix once, carry everywhere.** A fix found on one page is applied to every page with the same problem, by the lane
  that owns the shared code, before the builders' next pages.
- **Ready runs side by side, after every merge:** `growth ready --batch ledger --stale-only --jobs 3`. READY holds while
  a page's built output is byte for byte the same, so a fix to one page re-checks that page only; a shared CSS change
  re-checks the pages whose output it changed. 12 pages: 3 minutes, not 25.
- **Evidence lives in the project.** Shots, click-tests and every proof a task tick names sit in research/ or journal/,
  never in a scratchpad or /tmp (a clean-up once broke the ticks of a dozen finished pages; 2.8.0 refuses such proofs).
- **Someone wakes the lanes.** A lane that ends its turn while waiting stops for good: one night, work stopped at 1:48
  and started again at 13:00. The lead runs an hourly check that nudges any idle lane with open work.
- **Owner rules about how the team works** are logged with "(no page rule)" in docs/steps-log.md, so they do not make
  every page brief stale at once.
- **Measure before you guess.** `growth gate page ... --profile` prints each check's seconds; the slowest checks are the
  first to fix.

## Speed: what helped and what did not

- **No double checks.** The lane runs the suite once. The lead does not run it again unless the production branch
  moved and the branch was rebased. Writers do not build.
- **Release each page alone** when it is ready and approved. Batches waited on the slowest page. The same holds
  before release: pages flow one by one through review and ready (see "Many pages at once" above).
- **On one laptop, 2 to 3 lanes plus a release is the most that helps.** More lanes made every page slower. A second
  machine with its own lanes is the real way to go faster.
- **Automate every clash you see twice** (a checklist or a small script), but only for text that is safe to merge by
  machine.
- **A lane's state is its branch.** If a lane stops, restart it from its branch and its brief, not from memory.

## Mistakes we made (so you do not)

| Mistake | Guard now |
| --- | --- |
| Two lanes edited each other's pages | Briefs: only your own page's files; sibling changes go to the lead |
| A guard test checked that its page was last in a shared list; the next merge broke it | Guard tests check membership, never position |
| Hand-made merges of shared lists | One lane released at a time, the next rebased, the tests prove the result |
| A lane marked "ready" before its commit existed | The lead checks `git log origin/main..<branch>` before reviewing |
| Duplicate list pages kept stopping releases; lanes reworded text one at a time to get under a threshold | Fix the cause once (for example by marking the list noindex) instead of nudging text |
| A hub passed every check and shipped, and the owner called it poor (no pictures, nothing to do on it) | Checks are not design. Every hub shows each guide's cover, has a real element, and the owner sees it on a local address before it ships |
| Removing pictures to make a page shorter | Cut repeated text, never pictures |
| Finished worktree folders and old dev servers left behind (on one rebuild: 145 folders, 78 GB) | The lead removes the worktree and branch once the page is live; stop servers by their own port |
| A small-things pass skipped before bigger work | Site health first (404s, errors, broken images, small issues), then service pages and money pages |
| A cluster's posts were all rebuilt but its main page was forgotten | A cluster is done only when its main page is |
| Pushing to the wrong place | Writers never push. The lead never pushes to the production branch; only a merge after the owner's yes lands there |
| Two agents on one design file (the repo once split design to one tool and content to another) | Before starting, `git branch -r` and `git worktree list`; if someone has the file, wait or ask |

## Rules every agent brief carries

Local only: never push, merge, open a pull request, or run a deploy command; only the lead does, and only the owner's
yes merges. No secrets (never print keys or tokens). No sub-agents. Only your own page's files. Guard tests check
membership, not position. Never invent a number, customer, result or price. Never read a page behind a bot check by any
route. Keep the repo's committer email. Close every browser you open and stop every server you start. Report in simple
English, end with "Cleaned: ...", then end yourself. At most the project's agent cap at once.

## A lane brief (template)

```
Lane <n>: <page address>
Job: <audit | write | test> for <post | page | money page>, playbook <name>
Worktree: ../wt-<lane>-<slug> on branch <kind>/<slug>, from origin/main at <short hash>. Dev server port <port>.
You may edit: <exact files>. You may not edit anything else.
Read first: the book's playbook for this job, the audit file <path>, BRAND.md, the page rulebook.
Facts you may state about the business: only what BRAND.md words: <list or "none new">.
Done when: only the checks the change touches (growth checks, rule 105) pass; you looked at the page at the
rulebook's widths (rule 106); the commit is made.
Report: branch, commit, addresses touched, sources, checks and results, what you could not verify,
sibling changes for the lead, "Cleaned: ...". Then append "<lane> ready <commit>" to lanes-ready.txt and end.
```

For Brightline Lawn Care a lane might be: "Lane 1: /lawn-aeration, job write, playbook change-a-page; you may edit
`content/pages/lawn-aeration.md` and nothing else."

## Change log

| Date | Version | What changed |
| --- | --- | --- |
| 2026-11-18 | 2.0.0 | Generic edition: no project paths or hosts; the host, the production branch and the shared files come from the project's `SETUP.md`. |
| 2026-11-17 | 1.0.0 | First version (worktrees, pull request and deploy flow, shared-file clashes). |
