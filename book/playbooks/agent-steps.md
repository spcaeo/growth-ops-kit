---
title: Steps for an agent changing a page
version: 2.0.0
updated: 2026-11-18
license: CC BY 4.0
---

# Steps for an agent changing a page

**Version 2.0.0 (generic edition) · 18 Nov 2026**

You are an agent asked to change something on the site: a post, a page, a fact, a link, a redirect. Follow these steps
in order. Each step has a **stop point**. If it is not met, stop and report; do not work around it.

## The five stages (every job, small or large)

| # | Stage | What happens | Done when |
| --- | --- | --- | --- |
| 1 | **Audit** | Read the page as it is now (the file and the page in a browser). Find every fact on its source. Read the rules that apply (`BRAND.md`, the [page rulebook](../03-page-rulebook.md), the [lessons](../lessons.md)). For a page that should convert, run [cro-audit](cro-audit.md). | every fact you will write has a source URL or file, and the job is one line in the task list |
| 1b | **Pre-flight** (rule 0a) | `growth preflight <path> --type ... --key ...`: shared site problems fixed first, planning evidence in place, `research/<key>-checkpoints.md` written (every check by when it runs). | PRE-FLIGHT PASS |
| 2 | **Write** | Make the change on a branch, in its own worktree (a private copy of the repo). Edit the content or the code file. | the change is in a commit on the branch |
| 3 | **Test** | After **every** commit (never only at the end) the gate on the preview; then `growth ready` READY before the owner sees a URL; only the checks the change touches (`growth checks`, rule 105), then a local preview you look at (phone and desktop width). Someone who did not write it reviews it. | all pass, and a human or reviewer agent looked |
| 4 | **Release** | Pull request, **the owner's explicit yes**, merge, the host deploys, confirm live. A new post may instead go into the queue ([release](release.md)). | the live page shows the change |
| 5 | **Measure** | Look again at 7, 14 and 28 days: indexed? impressions and clicks? conversions? The page tracker records each change date from git and shows before and after once Search Console is switched on. Write down what moved. | the result is in the task step |

## What needs the owner

- Any claim about the business that is not already worded in `BRAND.md`: customers, results, numbers, integrations,
  security or compliance words, prices. `BRAND.md` also lists what no page may claim. A customer may be named only
  once it has a row in the permission log.
- A new kind of page, a new section, a design change, a change to the menu or the logo lockup.
- Removing a page, a redirect to the home page, a 410 (gone) answer, a changed slug.
- **Every merge to the production branch, and every push to it.** A yes given for one change does not cover the next.
- **Adding a post to a scheduled queue.** It goes live by itself later, so treat it like a merge.
- Hosting settings, DNS, workflow settings, analytics and Search Console settings, money.

## Roles

| Role | Who | Does | Never |
| --- | --- | --- | --- |
| **Owner** | the person who decides for the business | approves topics, claims, new page types, design, and every merge | is asked twice for the same OK |
| **Lead** | one agent session | plans, briefs, reviews, pushes branches, opens the PR, asks the owner, merges after the yes, confirms live | merges without the yes |
| **Writer (a lane)** | one agent per page | audits, writes, tests in its own worktree, commits on its own branch | pushes anything, touches the production branch, edits another lane's files |
| **Reviewer** | an agent that did not write the work (a different model) | checks facts on the source, the rules, the page in a browser | approves its own work |
| **Another coding agent** | may also work in the repo | works in the lane the repo's rules give it | is overwritten: before starting, look at `git branch -r` and open worktrees for work in progress on the same files |

At most the project's agent cap (default 4) work on the project at once. Every agent closes the browsers it opens and
ends itself when its job is handed over.

## 0. Before anything

1. Read, in this order: the project's `BRAND.md` (what may be claimed; note its version), the project's
   `OWNER-RULES.md`, the playbook for your job ([playbooks](README.md)), the per-page checklist at the top of the
   [page rulebook](../03-page-rulebook.md), and the [lessons](../lessons.md) for your kind of job.
2. Read the site's own rules: its `AGENTS.md` or `CLAUDE.md`, and its handoff notes if you touch content or release.
3. Know your limits. You may write only the files your brief names. You **never** push, merge, open a pull request,
   run a deploy command, change hosting or code-host settings, or touch DNS. You never print a secret. You never start
   other agents. You close every browser you open.

**Stop point:** your brief names the job, the page or pages, the files you may write, and who approves. If any is
missing, ask the lead.

4. **Pre-flight is done before you start** (rule 0a): the lead gives you the generated brief AND
   `research/<key>-checkpoints.md`. Tick each checkpoint with its evidence. Run the gate after every commit and fix
   its FAILs before the next one; never save them for the end. Generated items are proven by the gate run. The manual
   items (section 5: the project's own rules from growth.json `checkpoints_extra`, plus any you add) have no gate
   check: tick each with one line of proof, `- [x] <rule> -- <what you saw>`. `growth ready` fails while one is open
   (`growth checkpoints <file>` lists them), and re-running `growth preflight` keeps your ticks and items.

## 1. Work in your own worktree

The local clone is the lead's. Never edit files in it directly.

```
git -C <clone> fetch origin
git -C <clone> worktree add ../wt-<job>-<slug> -b <kind>/<slug> origin/main
```

`<kind>` is one of the repo's own prefixes, for example `article` (a post), `page` (a page), `fix` (a fact, links,
redirects), `design` (layout or pictures). The worktree sits next to the clone. Check `git config user.email` inside
it: it must print the project's commit identity (rule 118); if it prints anything else, stop. A fresh worktree has no
dependencies installed; the lead links or installs them ([04-lanes-and-releases.md](../04-lanes-and-releases.md)).

**Stop point:** `git branch -r` and `git worktree list` show no one else working on the same file.

## 2. Gather the evidence

- The page as it is: its file, and the page in a browser from the dev server.
- Every fact you will write: its official source, opened today. Write the URL down (rule 5).
- The rules that apply (search the rulebook for the page type and the words you will change).
- For a link job: `growth link_map check <path> --repo <worktree>` (exit 1 on any flag) and `inbound <path>`.

**Stop point:** every fact has a source. A fact about the business itself must be worded in `BRAND.md`; anything else
goes to the owner, through the lead. Never invent a number, a customer, a result or a price, and read the "never
claim" list before you write.

## 3. Make the change with the right tool

| Change | Where |
| --- | --- |
| A new post | the content folder, plus its cover entries ([new-post](new-post.md)) |
| Text in an existing post or page | edit the content file; keep `updated` true ([update-post](update-post.md)) |
| Text on a service page, pricing or home | the page's code or data file ([money-page](money-page.md)) |
| A redirect or a 410 | the redirect config ([lost-pages](lost-pages.md)) |
| A cover | the artwork and cover files ([images](images.md)) |

Change only what the brief names. Keep the front matter valid: dates in quotes as `'YYYY-MM-DD'`, `updated` never
before `date`. A build may fail on a bad date by design.

**Stop point:** `git diff` shows exactly the change you meant and nothing else.

## 4. Test

From the worktree root:

```
growth checks                 # only the checks this change touches (rule 105)
<dev server command>          # then look at the page at 360, 390, 820, 1280 and 1920 wide (rule 106); close the browser after
growth link_map check <path> --repo <your worktree>
```

**Stop point:** every check passes, or you can name the one that fails and show it fails the same way on the
production branch (then it is not yours, and you say so).

## 5. Commit and hand over

Commit by path, never `git add -A` (rule 123). One plain sentence as the message, then the attribution line you were
given. **Do not push.** Hand over to the lead, in simple English:

- the branch and the commit;
- the live address or addresses the change touches;
- your sources (URL and date read);
- the checks you ran and their result;
- what you could not verify;
- anything in the rulebook or the playbooks that looked wrong;
- changes other pages need ("sibling changes"): links back to your page, stale facts elsewhere. List them; do not
  make them;
- one line "Cleaned: ..." (dev servers and browsers you stopped, scratch files removed).

Then end. You are done, with nothing left.

## What the lead does next (not you)

The lead reviews the branch, pushes it, opens the pull request, asks the owner, and after the owner's explicit yes
merges and confirms the page live ([release](release.md)).
