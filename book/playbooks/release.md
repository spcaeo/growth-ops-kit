---
title: Playbook - release, queue and undo
version: 2.0.0
updated: 2026-11-18
license: CC BY 4.0
---

# Playbook: release, queue and undo

**Version 2.0.0 (generic edition) · 18 Nov 2026**

**Lead only.** Writers never run these steps. Release has two routes. Both end at a change on the production branch,
which on many hosts is a live deploy within minutes, so both have a gate. The project's `SETUP.md` says which host,
which branch and whether route B exists.

| Route | For | The gate |
| --- | --- | --- |
| **A. Branch, pull request, merge** | everything: pages, code, redirects, fixes, posts | **the owner's explicit yes** to the merge, in the conversation |
| **B. The scheduled queue** (only if the project has one) | new posts the owner has approved, one a day | the owner's yes to **adding the post to the queue**; the bot's daily push was approved once when the workflow was merged |

**Never push to the production branch. Never merge a pull request without the yes. Never run a manual deploy** unless
the owner asks for it (rules 114, 115). A yes given for one change does not cover the next (rule 116).

Nothing enters either route unless the page passed pre-flight before its build (rule 0a, `journal/preflight.json`) and
`growth ready` says READY at the branch's last commit (the golden rule).

## Route A: branch, check, pull request, yes, merge

1. **Before the push.** The branch is based on the current production branch (`git fetch origin`, then
   `git merge-base --is-ancestor origin/main HEAD`; if not, rebase). `git config user.email` prints the project's
   commit identity (rule 118). `git status` is clean.
2. **Checks on the branch** (in a worktree that has its dependencies): `growth checks`, and
   `growth gate page <path> --url <local URL> --repo . --type <type>`. Fix on the branch until all pass. If one fails
   the same way on the production branch, say so and stop.
3. **Local preview.** The gate and READY run on the production build served locally (`growth serve <dist>`, or the site's own
   preview command in `growth.json` `preview_cmd`); `ev.prod-build` fails a page a dev server answered. The preview
   is looked at by someone who did not write the change, at the widths
   of rule 106 (360 to 1920). The review surface is a localhost address, not the code host or the hosting dashboard
   (rule 113). Close the browser and stop the server when done.
4. **Push the branch and open the pull request** (`git push -u origin <branch>`, `gh pr create`). This does not deploy
   production. (Many hosts build a private preview of any branch; do not share its key or link.) The description
   says: what changed, the live addresses it touches, the checks and their results, the sources, what could not be
   verified, **the undo** (the merge commit to revert, or the earlier deployment to promote; rule 127), and the line
   **"Merging this deploys to production."**
5. **Ask the owner.** One message: the PR link, the list of addresses, what to look at, and the question "May I
   merge?" In the same message ask: "If the live check fails, may I revert it at once?" so an undo does not wait.
6. **After the yes, merge** the way the repo's recent pull requests were merged (`git log --oneline -15 origin/main`;
   do not change repo settings). Do not merge while another release is mid-way.
7. **Wait for the host** (a few minutes). Poll the changed address, one request at a time, until it shows the change.
   Do not crawl.
8. **Live check, one request per changed page:** status 200; title, description, H1; canonical; structured data and
   FAQ (view source); the CTA opens the booking path; a new page is listed in the sitemap; the cluster page lists a
   new post; for a redirect, `curl -s -o /dev/null -w '%{http_code} %{redirect_url}\n' <old>` gives `301` and the new
   address (or `410`).
9. **Same day:** the owner asks Google to re-read each new or rebuilt money page (Search Console, request indexing).
   That is the owner's own account.
10. **Clean up:** remove the worktree (`git worktree remove`), delete the local branch, stop dev servers and browsers.
    Leave the remote branch. Mark the task step done and book the day-7 look (below). Take the "after" archive
    (`growth page_archive capture <path> --stage after`, rule 36i).

## Route B: the scheduled queue (optional)

Some sites run a daily job that takes the oldest commit from a queue branch, cherry-picks it onto the production
branch, runs the tests and a production build, and pushes only if both pass. When the queue is empty it does nothing.
If the project has one, `SETUP.md` names the branch and the workflow. To add a post:

1. The owner approved the post. The post passed everything in [new-post](new-post.md) on its own branch.
2. **One post per commit**, oldest first, and each commit holds everything the post needs so the tests pass after the
   cherry-pick: the content file, its artwork and cover entries, its pictures, and its entry in its cluster page list.
3. The post's `date` is the day it should go live, or earlier. A later date keeps it hidden even after the push (rule 117).
4. On the queue branch: only the checks the change touches (`growth checks`, rule 105), then push the queue branch.
   This deploys nothing, but it schedules a live post, so it needs the owner's yes first.
5. **Rebase when the production branch moves.** Every queued commit edits the same shared files, so any change to
   them on the production branch can make the next cherry-pick conflict. After a merge that touches them: rebase the
   queue, re-run the tests, and push with `--force-with-lease` (lead only; tell the owner).
6. **Dry run first** for any change to the queue: run the workflow with "dry run" ticked. A real manual run pushes to
   the production branch and needs the owner's yes.
7. **Daily look:** list the last runs of the workflow. Green means published or empty; red means nothing was published
   that day (read the log). Then do the live check (Route A step 8) for the post.

To stop the queue: the owner disables the workflow, or the queue branch is deleted. The job then does nothing.

## When it stops

| It says | Do |
| --- | --- |
| Tests fail: "Missing original artwork" | the post has no artwork entry or pictures; add them in that commit |
| "Cherry-pick conflicted" | rebase the queue (Route B step 5) |
| The host did not deploy the push | check the committer email (rule 118); check auto-deploy is on (owner) |
| Build fails on a date | fix the front matter: quoted `'YYYY-MM-DD'`, `updated` not before `date` |
| Pushed but the post is not visible | its `date` is in the future, or no build has run since its day (rule 117) |
| `Permission denied` or `protected branch` | the workflow's write permission or branch protection (owner, code host settings) |

## Undo

- **Fastest:** in the hosting dashboard, promote the previous production deployment (an instant rollback; the owner or
  whoever has access does it). The live site is back in a minute, but the production branch still holds the change, so
  follow with the revert.
- **In code:** branch `fix/revert-<topic>`, `git revert <commit>`, run the checks, and merge with the owner's yes
  (asked in advance, Route A step 5). For a queued post that is bad, also remove it from the queue branch.
- Write down what was undone and why, in the task step and in [../lessons.md](../lessons.md).

## Measure (every release)

| When | Look at | Where |
| --- | --- | --- |
| Day 1 to 3 | indexed? last crawl after the release? | Search Console (owner's account) |
| Day 7 | impressions, the new snippet shown | Search Console |
| Day 14 | clicks and position against the same number of days before | Search Console |
| Day 28 | the same, plus conversions from the page | Search Console, your analytics connector |
| Day 56 | conversions; the AI answers check again | analytics, the AI answers baseline |

The page tracker records the release date of each page from git and, once Search Console and an analytics connector are
switched on, draws before and after. Until then the numbers come from Search Console by hand. Write the numbers, with
their dates, in the task step. One change at a time, so a change can be tied to a number.
