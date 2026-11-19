# Growth Ops Kit

A growth system for any website, run with an AI coding agent (Claude Code first). It has two parts:

- **The book** (`book/`): how to grow a site page by page. The order of work, the rules every page must pass, one
  playbook for each job, helper brief templates, and the lessons that cost real time. Licence: CC BY 4.0.
- **The kit** (`kit/`): the tools that make the rules run. A gate that checks every page, a page tracker with a
  dashboard, a task and instruction log, a link graph, a technical SEO checker, and guards that stop the agent from
  skipping steps. Licence: MIT.

Each rule in the book is tagged `[code: check-id]` (the kit's gate checks it) or `[judgment]` (a person or reviewer
decides it). A test fails when the book and the kit disagree.

It works on any site. Checks that read the live page need only a web address. Checks that read a site's code live in
adapters (Next.js first); on another stack they print "SKIP: no adapter" instead of a fake OK.

**Analytics and Search Console are optional.** The recommended connector is [Skald](https://skaldanalytics.com): AI traffic
analytics from your server log, plus Search Console. The kit reads Search Console, GA4 and AI-traffic numbers through it.
The kit works without it: without any connector, the gate, the page tracker and every other tool still run on the live page, the
code and the project folder, and say plainly which numbers are missing. A direct Search Console connector (no analytics
service in between) is **not yet** built.

## Start in 10 minutes

You need Python 3.10 or newer and git. Node 18 or newer is needed only for a Next.js site's own checks (the Next.js
adapter), not for the demo site or any other stack.

```
git clone <this repository> growth-ops-kit
cd growth-ops-kit
./setup.sh                                   # checks your tools, installs the add-ons, links `growth`, runs the tests on the demo site
growth new-project ~/Projects/my-site-growth --site https://example.com
```

`setup.sh` links the `growth` command into `~/.local/bin`. If it says that folder is not on your PATH, add the line it
prints to your shell profile (for example `export PATH="$HOME/.local/bin:$PATH"`) and open a new terminal; or run
`./growth ...` from the kit folder.

`setup.sh` ends with a green test run on the demo site (Brightline Lawn Care, a made-up lawn-care company in
`examples/demo-site/`). `growth new-project` makes a project folder from `templates/project/` with your site address
in `growth.json`, the `/onboard` skill, and the Stop hook that makes the agent follow the rules (`.claude/`).

Then, in your agent (Claude Code), open the project folder and run `/onboard`. It asks the owner one question at a
time, fills `growth.json`, `BRAND.md` and `SETUP.md`, and stops when `growth doctor` says every step is OK. After that, pick a job
from [book/playbooks/](book/playbooks/README.md).

## What is where

```
growth-ops-kit/
  README.md             this file
  LICENSE               MIT (kit/, tests/, examples/, setup.sh, growth, templates/project/*.json)
  LICENSE-BOOK          CC BY 4.0 (book/, templates/project/*.md)
  CHANGELOG.md          versions of the kit and the book
  DESIGN.md             the design of the kit and its main decisions
  setup.sh              one command on a clean machine
  book/                 the growth book
    README.md           contents, who it is for, how to read it
    01-flow.md          the order of work, stages A to H
    02-owner-rules.md   default working rules for the agent
    03-page-rulebook.md every rule a page must pass, tagged [code: ...] or [judgment]
    04-lanes-and-releases.md
    playbooks/          one file per job
    prompts/            brief templates for helper agents
    lessons.md          what went wrong, what it cost, the guard
    foundation.md       the day-one checklist for any new project
  kit/
    tools/              the gate, ready, preflight, doctor, tasks, journal, owner_messages, link_graph, ...
    adapters/nextjs/    checks that read a Next.js repo
    page-tracker/       the page tracker and dashboard
    rules/registry.json every check: id, rule, what it proves
    hooks/, skills/     git and agent hooks; the /onboard skill
  templates/project/    what a new project folder starts from
  examples/demo-site/   a small made-up website; the tests run the gate on it
  tests/                small tests with no network, and the demo-site run
```

The kit is shared by every project. Each project is its own folder (made from `templates/project/`) that holds its
`growth.json`, brand facts, owner rules, journal and research. Nothing about one project is ever written inside the
kit, so one checkout serves many sites.

## The flow in one line

**Onboard** (the setup steps of `growth doctor`, once) then **choose** (inventory, money pages first, snapshot) then **run the job** (its
playbook) then **release** (the owner's yes, one page at a time) then **measure** (day 7 to 56) then **learn** (every
instruction logged and written into its one home). Details: [book/01-flow.md](book/01-flow.md).

## Three rules that never bend

1. **No shortcuts.** Every step of the job's playbook, in order, with every owner check-in.
2. **Nothing goes live without the owner's yes.** Agents never push, merge or deploy.
3. **No page URL goes to the owner before the gate says READY.**

## Licences

- Code (`kit/`, `tests/`, `examples/`, `setup.sh`, `growth`, and the settings files `templates/project/growth.json` and
  `templates/project/docs/tasks.json`): MIT. See `LICENSE`.
- Book (`book/` and the Markdown files in `templates/project/`): CC BY 4.0. See `LICENSE-BOOK`. Credit "Growth Ops Kit" and
  link to the licence if you share or adapt it.

## Contributing

Add what you learn. A new rule goes in the page rulebook with its tag and its entry in `kit/rules/registry.json` in
the same change. A new lesson goes in `book/lessons.md` with its date and what it cost. Never put a client name, a
key or a private number in this repository: the leak check runs at pre-commit and in CI.
