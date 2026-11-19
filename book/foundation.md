---
title: Project foundation
version: 2.0.0
updated: 2026-11-18
license: CC BY 4.0
---

# Project foundation: build the foundation first

**Version 2.0.0 (generic edition) · 18 Nov 2026.** A living document. It started on 15 Nov 2026 from what a large
multi-module app and a sister project learned the hard way. Owner's words: "we have to keep our knowledge and
learnings somewhere documented so in future in new project we do not make those mistakes."

**Who reads this:** the agent at the start of any NEW project, before the first feature is built, and any developer
who joins. For a website growth project, the kit's `growth new-project` already does the setup half of this list;
the rest is for the code you build around it.

**The one-line lesson:** we optimised for the speed of building with many agents in parallel, and nobody stopped to
design the whole system. The apps were built first and the foundation by accident. Fixing it later cost a full stop of
all feature work. **Design the foundation first, then build on it.**

---

## 1. The day-one checklist (before the first feature)

Do these first. Each one is cheap on day one and very expensive in week six.

### Code
- [ ] **One repository** for the whole product. Not one per module.
- [ ] **Shared code is a library read from source**, never a packed file with a version that modules "take".
- [ ] **One version of every package**, one lock file. A check fails when a second version appears.
- [ ] **One folder per module**: its screens, its service, its docs and its tests together.
- [ ] **A new module is made by a template** (a generator), never by copying an existing module.
- [ ] **A rule the build enforces:** a module uses another module only through its published parts.
- [ ] **An owner for every folder.**
- [ ] **The code has a home off the laptop from the first commit** (a private remote), pushed automatically.

### Checking
- [ ] **A gate before every merge**, started by the tool, not by a person: build, rule checks, tests.
- [ ] **The main line is protected.** Nobody, the lead included, can put a change on it without the gate.
- [ ] **Tests in three sizes** from the start: most are small (no network, no database), some medium (one service and
      its own database), few large (a real browser). Each size has a time budget.
- [ ] **Every test brings its own servers and data.** No shared test stack to queue for.
- [ ] **An independent reviewer reads every change** before it merges, on a different model from the author.
- [ ] **Look before release:** a person or tester sees the change on a preview before it is tagged.
- [ ] **A release is one command** that cannot skip a step.
- [ ] **A rehearsal is shaped like the real thing** (16 Nov 2026): before a gate, a deploy tool or any guard goes live,
      run it once in the same places as the real one (the same folders, the same user, a path with a space if the real
      one has one), not in a scratch folder beside it. A sandbox answers differently by folder.

### Safety
- [ ] **Three separate copies: Live, Dev, Test.** Real data and real keys exist only in Live.
- [ ] **Tests and developers never hold a real key.** The key is absent, not merely unused.
- [ ] **A test project is marked as a test project** by the system, and only a test project may get a made-up answer.
- [ ] **Every database has a nightly backup, and a restore has been tried.**
- [ ] **Secrets never enter git.** Scan the whole history before any push. Ignore tool folders (for example the
      agent's transcript folder) from the first commit, so a session log can never be committed.
- [ ] **Tool versions are pinned exactly.** Never install "latest".

### People
- [ ] **One command sets up the project on a clean machine**, with made-up data, ending in a green test run.
- [ ] **A short developer guide** a person can follow without asking anyone.
- [ ] **Rules live in tools.** When something goes wrong, fix the tool so it cannot happen again. Do not write a note
      for an agent to remember.

### Measuring
- [ ] **Measure "right the first time", not speed.** Count the changes that needed no fix-up, not the releases made or
      tickets closed.
- [ ] **Say "not yet checked" out loud** for: size (does it hold with real numbers of rows and people), the split into
      services, the path to production, readiness for real client data.

---

## 2. What went wrong, and what to do instead

Every line below happened. The numbers are from 15 to 18 Nov 2026, on a large multi-module app (unless the line
says otherwise).

| What we did | What it cost | Do this instead | Make a tool enforce it |
| --- | --- | --- | --- |
| Shipped the shared kit as a versioned packed file that each module copied in | Modules sat on three kit versions; a kit fix was still broken in two modules at the end of the day; a fix needed a "take", a test run and a release in each of 13 apps | Shared code read from source in one repository | A check that fails if a packed copy of shared code exists |
| One repo per module (15) | One feature was half released; 16 package files; 6 GB of installs for what 538 MB serves | One repository | Start that way |
| The lead was the check before a release | Two releases shipped with failing tests in one day | A gate that runs by itself | A protected main line |
| Tests shared one running stack | Runs queued 15 minutes; the machine's load hit 69; tests failed only because it was busy | Each test brings its own servers | No shared stack exists |
| Real data, real keys and tests in one stack | Tests spent real money (about 1,900 paid page reads and 350 paid searches); made-up answers were saved for non-test projects; a full copy of real data sat in a forgotten database | Three copies: Live, Dev, Test | Keys are absent outside Live |
| Each new module started as a copy of the first | One file identical in all 11 services, others already drifting; a copied backup script pointed at another module's folder and would have left that module with no backup | A generator, and shared packages | A check that fails on a new copy of a shared piece |
| Work waited on branches | 86 unmerged branches; one finished piece of work was lost because its slot was taken | Small changes merged daily behind a switch | A tool that lists any branch older than the limit |
| A project could not move to another computer (a large app) | Hooks, worktree links and package shortcuts named the laptop's own folders; keys and rules lived outside the project; copying 444 MB of packages over Wi-Fi took over an hour and dropped once | Paths relative to the project (`$CLAUDE_PROJECT_DIR` in hooks, relative symlinks), and from day one a setup script that rebuilds packages, keys, notes and working copies and ends with checks; move the source, never the packages | Run the setup on a fresh user (empty HOME) before calling a move done |
| Page branches stacked on each other (a large app) | One shared bug fix had to be rebased through six pages; every page above it lost its checks and was re-checked (about 2 hours) | Each page on its own branch from the production branch; shared fixes on their own branch first | `proc.one-page-branch` fails when a page branch carries another page's files |
| A tester looked after the tag | Faults were found in released code; three of four releases in a day fixed the one before | Look before release | "In review" means before the tag |
| Each time something went wrong, a note was written | Over 80 trap notes for agents to remember | Fix the tool | Count the notes; the number must fall |
| Speed was reported: "8 releases, 19 tickets closed" | Fast-and-wrong looked the same as fast-and-right | Report first-time-right | The weekly number |
| Everything ran on one laptop, nothing was pushed | All code, history and data existed once; four databases had no backup | A remote and backups from day one | A check that every repo has a remote and every database a backup job |
| A session log was committed by accident | 46 MB with a database password in the history of two repos; history had to be rewritten | Ignore tool folders from the first commit; scan before every push | The gate refuses such a file |
| Built for agents on one machine | Setup lived in one person's notes; no way for a developer to start | One-command setup and a guide | Run the setup on a clean machine in the gate |
| Rehearsed the merge gate in a scratch folder, not where the real one lives (16 Nov 2026) | The gate went live and its first real change was red; every change would have been. Two faults were invisible in the rehearsal: the real merger and runner sat inside the home folder, which the gate's sandbox hides (a program could not ask about its own log file, and npm could not start any program). A third was a false green: the real folder has a space in its name, a script compared text with its own address (where a space is `%20`), did nothing and ended with 0, so every tools change passed with no test run. 157 passing tests and 14 green rehearsal changes had said it was ready. About three hours with nothing able to join | Rehearse in the place and shape of the real thing; keep a job's work folder outside any area the sandbox hides; look at how long each step took (a test step that ends in 5 seconds ran nothing) | One test in the gate's own test set runs a made-up merger and runner inside the home folder, in a path with a space; a scan fails on a script that finds itself by the text of its address |
| Tests asked the machine how busy it was (16 Nov 2026) | At load 40 to 53 three tests failed or hung for 30 minutes; a full test run was lost twice | A test hands in its own clock, pause and "is the machine busy" answer | A test proves that a made-up world gives the same answer at load 500 |
| A new gate check was switched on while the main line already failed it (17 Nov 2026) | A new "one word, one state" step came in 40 minutes after a change that broke that rule; the first change to meet it took the blame, sat red 3.5 hours unseen, and every change behind it would have failed | A change that adds a check runs it against the main line first, and fixes or lists what the main line fails in the same change; the lead watches for approved-or-red changes with nothing waiting to land |

---

## 3. What worked, and is worth keeping

- **A trial before a big change.** Four small trials on throwaway copies answered "will it work for us" in one
  afternoon, before any real code was touched. One trial found that all 13 apps built on the newest shared kit with not
  one line of module code changed.
- **An independent reviewer told to break the work.** It found 9 holes in a safety design, 4 holes in a safety build
  whose tests were all green, and showed that the author's plan for one core part was wrong. A builder's report reads
  the same whether the work was run or not.
- **Design before code**, for anything that touches more than one module, money, rights or shared data.
- **Honest words:** "written, never run"; "not yet checked"; "reported, not verified".
- **APIs built to one published style**, and every module showing its release line.
- **One tracker for everything** (tickets in plain words: what, why, what we saw, done when).
- **Measured facts with dates** in every ticket, so nobody argues from memory.

---

## 4. Working with many agents: what we learned

- **An agent reads messages only between its steps.** A "stop" or "hold" sent mid-run arrives late. To stop a run and
  keep it stopped: stop the agent first, then its processes, then restart it with one job.
- **Check every handoff against the disk** before believing it: the commits, the clean folder, the ports, the
  processes. Agents over-claim without meaning to.
- **Ask what was run and seen**, not what was written. Make every report say it per claim.
- **One owner per repository or folder.** Two agents built the same list once.
- **A reviewer on a different model from the builder.** The independence is the point.
- **Give each agent one clear job, the rules that cannot bend, and where to report.** A brief is the only context it
  has.
- **Do not start every agent's test run at once** after a release. Hand out jobs one at a time while a release run is
  on the machine.
- **Never stop processes by name pattern.** It once stopped another project's tests.
- **Keep the machine in view:** load, memory, and what is listening on which port.

---

## 5. Choosing tools: what we found (check again, these change)

- **Nx** (free, MIT) is the closest thing to Google's own build tool for Angular. It ran our existing builds unchanged;
  a repeat build went from 20 seconds to under 1. It has no official Go support; a small plugin of our own (131
  lines) was better than the community ones.
- **Bazel** is what Google uses. Best for Go, but its Angular support for outside projects is poor.
- **A build cache can lie.** It reused an old result when a file it did not know about had changed (a settings file
  git ignores; a test's set-up). Name every input. Release checks always run fresh.
- **A tool can be attacked.** A bad version of a popular build tool was published in Aug 2025. Pin exact versions and
  upgrade only to versions at least two weeks old.
- **Free private repos on some code hosts have no protected main line.** Plan for the paid plan or a gate of your own.
- **A code map for agents (tried 15 Nov 2026, version 0.9.100): not adopted.** On our own code it was right for file
  imports inside one module, for SQL tables and their links (61 of 61), and for callers of a plain function. It was
  wrong, with no warning, on the questions that matter: who calls a method (it said "none" where there were 22), which
  screens use a shared part (2 found of 106), and links between services (268 false ones from name clashes). After a
  rename the old map still answered with confidence. Lesson: try any "knowledge of the code" tool on questions whose
  answer you can check yourself, before an agent is allowed to trust it. A wrong map is worse than no map. Plain
  search stayed cheaper and complete.
- **A developer-portal website** was looked at and not adopted: it is an application to host and keep running, sized
  for hundreds of teams. Owners, docs and the module list live in the repository instead. Look again past about 30
  services or several teams.

---

## 6. Questions to answer in the design doc of any new project

1. Where does shared code live, and how does a change to it reach every user of it?
2. What stops a change that breaks another module from merging?
3. What can a test reach? Can it touch real data or spend money? What makes that impossible?
4. How does a new module start, so it carries no copied code?
5. How does a new developer start, on a clean machine, in one command?
6. How is "done" proven: what was run, by whom, before or after the release?
7. What is measured each week, and is it quality or only speed?
8. What is not yet checked, and when will it be?
9. Where does the code live besides the laptop, and has a restore been tried?
10. How would this hold with ten times the modules, the data and the people?

For a growth project the kit answers most of these itself: see the ten answers in the kit's `DESIGN.md`.

---

## 7. Pre-flight before every page or feature

Checking only at the end cost hours of repairs on four pages at once. In every project, a pre-flight tool runs before
the first line of a page or feature. It fixes shared problems first (oversized files, raw design values, banned
libraries), requires the planning artefacts and "before" measurements, and writes the checklist sorted by when each
check runs. The gate then runs after every commit. Every playbook for building something starts with this step
(page rulebook rule 0a, `growth preflight`).

## 8. To be completed when a project's foundation move is finished

- The real numbers before and after: time from a shared-code fix to every screen; releases that skipped a check;
  first-time-right rate; build and test times; branches older than the limit.
- What the move actually cost, step by step, and what surprised us.
- Which items in section 1 turned out to matter most, and any that did not.
- The final shape of the gate, the release set, and the three copies.

When a project learns something a new project should know, add it here (one place, no copies), with the date and what
it cost.
