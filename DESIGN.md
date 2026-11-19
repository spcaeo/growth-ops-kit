# Growth Ops Kit: design (v2, open source)

The goal: turn one team's working playbook into an open-source growth book and kit that is generic enough for any other
project. Decisions: everything ships, page tracker included; any website, Next.js first; MIT for code and CC BY 4.0 for the
book. Nothing goes public until the maintainer says yes.

## What it is

A growth system for any website, run with an AI coding agent (Claude Code first): a **book** (how to grow a site page
by page, the rules every page must pass, the playbooks for each job, the lessons that cost real time) and a **kit**
(the tools that make the rules run: a gate that checks every page, a page tracker with a dashboard, a task and
instruction log, guards that stop the agent from skipping steps).

Sources: the strictest working setup of the first project, the playbooks other projects wrote and the first version of
this kit for anything the newer one lacked. No client name, person, key, private number or private data comes across.

## Layout

```
growth-ops-kit/
  README.md                 what it is, start in 10 minutes
  LICENSE                   MIT (kit/, templates/, examples/, tests)
  LICENSE-BOOK              CC BY 4.0 (book/)
  DESIGN.md                 this file
  CHANGELOG.md              versions of the kit and the book
  setup.sh                  one command on a clean machine: checks tools, installs add-ons, runs the tests on the demo site
  book/                     the growth book (read in order; each rule has one home)
    README.md               the table of contents and how to read it
    01-flow.md              the order of work, stages A to H
    02-owner-rules.md       default working rules for the agent (a project may add its own)
    03-page-rulebook.md     every rule a page must pass, each tagged [code: check-id] or [judgment]
    04-lanes-and-releases.md
    playbooks/*.md          one per job: new money page, change a page, new post, release, lost pages, CRO audit ...
    prompts/*.md            brief templates for helper agents
    lessons.md              what went wrong and what it cost, from real projects (no client names)
    foundation.md           the day-one checklist for any new project
  kit/
    tools/                  gate, ready, preflight, doctor, tasks, journal, owner_messages, url_guard, agent_models,
                            inventory, link_graph, brief, fold_plan, page_archive, phone_check ... (Python 3.10+)
    tools/gatelib/          the page gate's checks, grouped by area
    tools/techseo/          technical SEO checks that read the live page (any site)
    adapters/nextjs/        checks that read a Next.js repo (code-level); skipped with a clear note on other stacks
    page-tracker/           the page tracker and dashboard (analytics, Search Console, Bing optional, each switched on by config)
    rules/registry.json     every check: id, rule, what it proves, which adapter it needs
    hooks/                  git pre-commit and the agent Stop hook
    skills/onboard/         the /onboard skill: asks the owner one question at a time and writes the project folder
  templates/project/        what a new project folder starts from (growth.json, BRAND.md, OWNER-RULES.md, SETUP.md,
                            CLAUDE.md, docs/steps-log.md, docs/tasks.json): made by `kit/tools/new_project.py`
  examples/demo-site/       a small made-up website (static HTML) and its project folder: the tests run the gate on it
  tests/                    small tests (no network) and the demo-site run
  .github/workflows/ci.yml  tests + leak check on every push
```

## Main decisions

1. **The kit is a library, the project is data.** The kit is one checkout shared by every project; each project has
   its own folder (made from `templates/project/`) holding `growth.json`, its brand facts, its owner's extra rules, its
   journal, research and logs. Tools find the project from `GROWTH_PROJECT` or by walking up from the current folder
   to the nearest `growth.json`. Nothing about one project is written inside the kit.
2. **Any site; adapters for code.** Checks that read the live page (title, links, schema, images, speed, words, CTA)
   work on every site. Checks that read the site's code live in `kit/adapters/<stack>/` and run only when
   `growth.json` says `"stack": "nextjs"`. Other stacks get a clear "SKIP: no adapter for <stack>" line, never a fake OK.
3. **Brand facts are the project's.** Anything a rule needs to know about one business (the one CTA label, the words
   it must never use, the author, the market) is read from the project's `BRAND.md` / `growth.json`, never written in
   the rulebook.
4. **Connectors are optional.** Search Console and GA4 are read through an analytics connector (today: Skald); each is
   switched on in `growth.json` with its keys in a file outside git (`keys_file`). Without one the tools still run and say
   what is missing. A direct Search Console connector and a Bing connector are **not yet** built.
5. **Rules run, not just read.** Every rule is tagged `[code: <check-id>]` or `[judgment]`; a test fails when a tagged
   check does not exist, when a check points at no rule, or when a book rule and the registry disagree.
6. **Nothing private leaks.** `kit/tools/leak_check.py` fails on key-shaped strings, `.env` files and every word in a
   git-ignored `.private-words` file (client names, people, domains). It runs at pre-commit and in CI. The whole
   history is scanned before any push.
7. **Fresh history.** The first private repo's history holds earlier project data (and its commits carry the author's own
   name). Before publishing, the old `main` is kept in a private archive repo; the public repo starts from a new first
   commit with a neutral git identity and UTC dates. Both steps wait for the maintainer's yes. Until then `leak_check
   --history` reports the old commits' leaks as FAIL and the author identity as WARN; on the fresh history it must say 0.

## The ten questions (project-foundation playbook, section 6)

1. **Shared code:** the kit is the one copy; projects read it from source (a checkout or `pip install -e`), never a
   pasted copy. A change reaches every project on its next pull.
2. **What stops a breaking change:** CI and the pre-commit hook run the tests, the demo-site gate and the leak check;
   `main` is protected on GitHub.
3. **What a test can reach:** only the demo site on 127.0.0.1 and fixtures. No keys exist in tests; connectors are
   off unless a key file is present, and CI has none. No test spends money.
4. **How a new project starts:** `python3 kit/tools/new_project.py <folder> --site <url>` (or `/onboard`) from the
   template; never by copying another project.
5. **Clean machine:** `./setup.sh` checks Python, Node and git, installs the add-ons, and ends with a green test run on
   the demo site.
6. **How "done" is proven:** the gate's report at the current commit, `ready.py` saying READY, and the owner's look at
   a preview; the release playbook records what ran and when.
7. **What is measured weekly:** each page's searches, clicks and calls before and after its release (page tracker).
   Pages that passed the gate first time and gate FAILs per page are **not yet** reported by any tool.
8. **Not yet checked:** adapters for stacks other than Next.js (WordPress first, when a project needs it); Windows;
   moving existing projects onto this kit (each its own step, with its owner).
9. **Off the laptop:** a private GitHub repository, private until the maintainer says public; the old history in a
   private archive.
10. **Ten times bigger:** checks are registered, not hard-wired, so new ones and new adapters add without touching the
    gate; the project folder keeps each site's data apart, so ten sites are ten folders.

## Build order

1. Book (builder A) and kit (builder B) in parallel, each owning its folders; rule ids stay as in the source so the
   book and the registry keep matching.
2. Demo site and tests green; setup on a clean user (empty HOME) green.
3. Independent review on a different model; the leak check over every file and the whole history.
4. Show the owner. Publishing (archive the old history, replace, make public) only with the owner's yes.
