---
title: The work board
version: 3.0.0
updated: 2026-11-24
license: CC BY 4.0
---

# The work board: many hands, one database (kit 3.0)

**Version 3.0.0 · 24 Nov 2026.** How several agents work on one site at the same time without waiting for each other.
It does not change any rule of the page rulebook or the order of [01-flow.md](01-flow.md); it changes how the work is
handed out. Read it with [04-lanes-and-releases.md](04-lanes-and-releases.md).

From a real project (23 and 24 Nov 2026): the checks themselves took seconds (build 4 s, gate 5 to 30 s, READY 33 s), yet
12 pages took a whole day and none was accepted. The time went into waiting: builders for the reviewer, the reviewer for
builders, everyone for one preview and one batch branch, and lanes that stopped and stayed stopped. The owner: "we are
not able to do many things at a time ... something very central ... all goes to simple local db".

## The parts

| Part | What it is | Command |
| --- | --- | --- |
| The database | One SQLite file per project, `state/growth.db`: tasks, journal, verdicts, the board, resources, and an event for every change. The plain files (`docs/tasks.json`, `journal/entries.jsonl`, `journal/ready.json` ...) stay as mirrors, rewritten after each change; a mirror changed outside the kit (restored, copied from another machine) is read back in. A lost database is rebuilt from the mirrors. | `growth store info`, `growth store events` |
| Micro kits | The kit in eleven parts (core, site, research, plan, shared, build, check, evidence, review, owner, release), each with its tools, its job kinds and how its jobs run. | `growth kits`, `growth kits pipelines` |
| The board | Every page, its stage, who holds it, and its jobs. Adding a page creates the jobs of its type's pipeline, each with what it needs first. | `growth board`, `growth board add`, `growth board import` |
| Jobs | Pulled, not pushed: an agent asks for the next job it can do and gets it with a lease. Finishing needs a checkable proof and ticks the task step it belongs to. A lease that runs out puts the job back in the queue, so a stopped agent never blocks a page. | `growth work next / beat / done / fail` |
| Resources | The slow, shared doors, handed out one turn at a time: the Google pacer, the browser pool, the lane ports, the owner's preview, the shared-code lock. | `growth pace google`, `growth lock`, `growth board resources` |
| Lanes | One private copy of the site per builder (a worktree, its own port, its own preview server), outside the project folder. | `growth lane open / check / close` |
| The machine runner | Takes the machine jobs (build, link graph, gate, shots, click-tests, READY) and runs several side by side, under the browser pool and a load guard. | `growth run --jobs 3` |

## Sites with more than one locale

A project whose `growth.json` `market.locales` lists two or more locales ([06-international.md](06-international.md)) gets two
more kinds of job when a page goes on the board, after the page's usual line:

| Job | Who | What |
| --- | --- | --- |
| `localize` | a builder agent (way: page) | one for each locale that is not the primary; the job carries its locale and needs the page's primary copy READY; it writes that locale's copy in its own folder |
| `intl-check` | the machine (way: parallel) | one per page; needs every `localize` job of the page; runs the `intl.*` gate checks (rule 162) |

`growth work next --kinds localize` prints the job's locale and the folder to write to; `growth board show <path>` lists
each `localize` job with its locale. A project with one locale gets neither job. A project with its own way of making copies
drops them with `pipeline_overrides.drop`.

## How each kind of work runs

| Way | Meaning | Examples |
| --- | --- | --- |
| ahead | done for many pages before they are built, with a use-by date | snapshot, dossier, research record, fold plan |
| parallel | many at once, limited only by the machine | gate, shots, click-tests, READY |
| page | one page at a time inside one agent, each step on the last | the folds, the hero scene, drawings, animation, the 390 layout |
| single | one at a time for the whole site | shared components and styles, a release |
| paced | one turn at a time through a slow, shared door | Google searches, outside facts, AI answers |
| owner | waits for the owner (or the lead, where the owner delegated it) | check-ins, the go-live yes |

## The rules of the board

1. **Pull, never wait to be told.** A worker that finishes asks `growth work next`; there is no ready file to watch and
   no lead nudging lanes. `growth board` shows what waits for what.
2. **Research and planning run ahead of building.** Keep a shelf of pages whose plan is reviewed, so a builder never waits.
   Results with a use-by date (AI baseline, research check, review: 30 days; inventory: 7; link graph: 8; outside facts:
   90) get a refresh job before they expire (`growth board refresh`; every claim runs it too).
3. **Google through the pacer only.** Before every Google search: `growth pace google`. It gives one turn every 20 to 30
   seconds for all agents together; on a robot check, `growth pace google --robot` stops everyone for 10 minutes.
4. **Shared code has one writer.** Take `growth lock shared-code` before editing a shared component, style or data file,
   and give it back when committed. When it is given back, only the pages whose built output changed are checked again
   (READY holds while a page's built output is the same).
5. **Builders build in their own lane** and check on their own port (`growth lane check`). READY stays on the one preview
   address the owner sees; the runner's READY job holds the `owner-preview` lock while it runs.
6. **A job is done only with proof** a reader can check (a file, a commit, a journal id, a command with its output line).
   The task step it belongs to is ticked at that moment, so the task list shows real times.
7. **Measure from the events.** `growth board times` prints, per job kind, the median wait and the median work. The
   slowest wait is the first thing to fix.
8. **The limits still hold:** the project's agent cap, the machine (the runner's load guard), and the owner's yes.

## A day on the board

```
growth board import research/batches/next.txt      # pages and their pipelines go on the board
growth run --jobs 3 &                              # the machine runner: snapshots, gates, shots, READY
GROWTH_AGENT=research-1  growth work next --kit research    # pace google before each search
GROWTH_AGENT=planner-1   growth work next --kit plan
GROWTH_AGENT=builder-1   growth work next --kit build       # then: growth lane open <path> --agent builder-1
GROWTH_AGENT=reviewer-1  growth work next --kit review
growth board                                       # what is where; growth board times: where the waiting is
```

## Change log

| Date | Version | What changed |
| --- | --- | --- |
| 2026-11-24 | 3.0.0 | First version: the database, micro kits, the board, jobs, resources, lanes and the machine runner. Sites with more than one locale: the `localize` and `intl-check` jobs. |
