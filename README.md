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

**1. Install**

```
git clone <this repository> growth-ops-kit
cd growth-ops-kit
./setup.sh              # checks your tools, installs the add-ons, links `growth`, runs the tests on the demo site
```

`setup.sh` links the `growth` command into `~/.local/bin`. If it says that folder is not on your PATH, add the line it
prints to your shell profile (for example `export PATH="$HOME/.local/bin:$PATH"`) and open a new terminal; or run
`./growth ...` from the kit folder. It offers to add the PATH line for you (it asks first).

**2. Set up once**

```
growth setup --site https://your-site.example
```

It asks a few plain questions, one at a time: your website, the country you want to rank in, who approves a page, whether it
may read your live site page by page (the safe answer is no), and one yes for the agent's safety helpers. It works out the rest
itself (what your site is built with, its sitemap, redirects, where your pages live). Then it walks you through the two steps
no program can do for you: connect Chrome for research (`/chrome` in Claude Code), and check that Google's Results region
matches your country. It ends with one line: setup done, and the next command. If you stop halfway, run it again: it
picks up where it stopped.

**3. Work on a page**

```
growth page /pricing    # opens the job with the playbook's steps, checks you are ready, writes the brief for your agent
growth check            # is the page right? a plain summary first (how many problems, the top three), the details after
growth ready            # may you look at it? Only when every check passes on the one preview address
growth measure          # did it help? compares the days after release with the numbers before (day 7, 14, 28, 56)
```

`growth status` shows what is open, how far along it is and what comes next. `growth` alone prints the short menu.
Every safety check runs behind these commands; `growth help --all` lists every tool (there are over fifty) if you want one
directly, and `growth doctor --verbose` lists every setup step with its result.

Any folder works. Keep three separate folders: the kit (this repository), the project folder `growth setup` makes (it holds your
notes, research and the task list), and your site's own repository. Run `growth setup` from your site's folder and it finds the
code; do not put the project folder inside the site repository.

For an agent or a script (no terminal), `growth setup` keeps the older question-and-answer way: it prints
`QUESTION <step>: ...` and stops with exit code 3; record the answer with `growth wizard answer <step> <value>` and run it
again. `growth wizard`, `growth new-project`, `growth doctor` and every other tool work exactly as before. The wizard never calls
setup done until the research browser (Claude in Chrome) is connected and Google's results region is set to your target
country and confirmed by you; `growth wizard --check` re-tests everything and `--repair` installs what is missing.

`setup.sh` ends with a green test run on the demo site (Brightline Lawn Care, a made-up lawn-care company in
`examples/demo-site/`). `growth setup` makes a project folder from `templates/project/` with your site address
in `growth.json`, the `/onboard` skill, and the Stop hook that makes the agent follow the rules (`.claude/`).

Then, in your agent (Claude Code), open the project folder and type `/onboard`: it runs `growth setup`, then does the work steps
(it asks one question at a time, fills `growth.json`, `BRAND.md` and `SETUP.md`, and stops when `growth doctor` says every step
is OK). After that, pick a job from [book/playbooks/](book/playbooks/README.md).

## What you get per stack

Checks that read the live page (the gate's page, SEO, link and speed checks, the page tracker, the link graph, the owner
journal) work on every stack, from the web address alone. Checks that read a site's code need an adapter.

| Stack (`growth.json` `stack`) | Live-page checks | Code checks | Notes |
| --- | --- | --- | --- |
| `nextjs` | all | all (Next.js adapter) | the only adapter today |
| `static` (Astro, Hugo, Eleventy, plain HTML, anything else) | all | none: each prints "SKIP: no adapter for static", never a fake OK | set `"stack": "static"`; check the code rules by hand |

Roadmap: an Astro adapter (content collections in `src/content/`, build and redirect checks), then Hugo. Want another
stack? Open an issue and say which code checks you need first.

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

## Three rules the kit works toward

1. **No shortcuts.** Every step of the job's playbook, in order, with every owner check-in. The task list and the Stop hook
   check that steps are ticked and carry proof; they cannot judge whether the work behind a proof is good.
2. **Nothing goes live without the owner's yes.** The agent's permissions deny `git push`, merges to the main branch and the
   project's `deploy_commands`, and the rule is in every agent's instructions. The permissions are a list of command
   patterns: a determined agent can run other code, so the owner's review of what ships stays the real control.
3. **No page URL goes to the owner before the gate says READY.** The URL guard stops a reply that names a page the gate has
   not marked READY. It is a safety net for honest mistakes, not a lock.

A check that cannot run (no adapter, no browser, no key) prints SKIP with the reason instead of a fake OK. Read the SKIP
lines before you trust a READY: a skipped check has not looked at the page.

Supported systems: macOS and Linux (the hooks are shell scripts; Windows is not supported, use WSL).

Network calls: setup downloads the pinned add-ons from PyPI. After that the kit reads only the addresses you point it at (your
preview, and your live site unless `live_site_rule` is `no-crawl`), the connectors you switch on, the indexing service you pick in `indexing` (only when you run `growth index`), and, while
`connectors.google_updates.on` is true (the template default), Google's public status page on each tracker sync. Set it to
false to stop that call.

## Get the page indexed after it is live

A page earns nothing until Google has it. After the live check, `growth index <full addresses>` sends the page to the indexing
service you picked in `growth.json` `indexing` (off until you set it; `growth wizard indexing` asks, and you can skip it).
The built-in option is [FreshlyCited](https://freshlycited.com): its smart mode asks Google first and sends only the pages
Google does not show, and a credit is used only when Google indexes the page. `--refresh` re-sends updated pages (1 credit
each, no credit back). The kit prints the estimated spend before every paid call and stops at a daily cap
(`indexing.max_pages_per_day`, default 50). Free fallbacks: `indexnow` (Bing and other IndexNow engines, not Google) and
`manual` (prints the Search Console "Request indexing" steps). `growth index status` and `growth index report` show what
was sent, and `growth measure` shows "Google sees the page: yes/no since <date>" before it judges traffic. The API key stays
in your keys file and is never printed. FreshlyCited is a separate paid service; the kit works fully without it.

## What the kit can and cannot guarantee

The kit runs on your machine, next to your agent. An agent that has a shell on the same machine can, in the end, do
anything you can: open a fake terminal, read your home folder, edit any file. No local tool can stop that completely.
So the kit aims for two things.

**It does not hand the agent the keys.** The permissions it writes into `.claude/settings.json` allow the `growth`
command and read-only git. They do not allow running any Python or test file, pushing, merging to main, moving or
deleting a branch, changing git hooks, or editing `growth.json`, the settings, the task list, the journal, the research
records or the approvals log. Some rules match the start of a command only, so treat them as a speed bump, not a wall.
`growth doctor` (step A13) says when one was removed or a hook is bypassed.

**Your "yes" is yours, and a fake one shows.** Owner acts (a design exception, a decision, an answer to a question, the
research browser and Google region, signing off a review, taking a baseline again) go through `growth approve`. It runs
only in your own terminal and only when you type back the code it shows. Each yes is a line in `docs/approvals.jsonl`
with a fingerprint (sha256) of exactly what you approved, chained to the line before and signed with a key kept in your
home folder (`~/.config/growth-ops-kit/approvals.key`). The gate fails when an approval is missing, when the approved
thing changed afterwards, or when the log was edited by hand. A design exception can never excuse evidence checks or a
page that did not load.

**What it checks, it reads.** A task step needs a proof that names something real (a file, a commit, a journal entry, a
command with its output, or a web address). Screenshots must be real images of the right width. AI answers need their
saved text. Research rows need a source and a date that is not in the future.

**What it cannot promise.** That an approval was typed by you and not by an agent driving a fake terminal on your
machine; that a screenshot shows the page it is named after; that a review was read. For that, keep the signing key
private, look at `growth approve list` now and then, and run the gate again somewhere the agent cannot reach (a CI job).

## Licences

- Code (`kit/`, `tests/`, `examples/`, `setup.sh`, `growth`, and the settings files `templates/project/growth.json` and
  `templates/project/docs/tasks.json`): MIT. See `LICENSE`.
- Book (`book/` and the Markdown files in `templates/project/`): CC BY 4.0. See `LICENSE-BOOK`. Credit "Growth Ops Kit" and
  link to the licence if you share or adapt it.

## Contributing

Add what you learn. A new rule goes in the page rulebook with its tag and its entry in `kit/rules/registry.json` in
the same change. A new lesson goes in `book/lessons.md` with its date and what it cost. Never put a client name, a
key or a private number in this repository: the leak check runs at pre-commit and in CI.

Commit under a neutral identity, not a personal one: `bash setup.sh` sets a repo-local GitHub no-reply identity for
this checkout (it asks once, or reads `GROWTH_KIT_GIT_EMAIL`; your global git config is never changed). Keep the words
that must never appear (client and project names) one per line in a git-ignored `.private-words` file at the checkout
root: the leak check reads it, and `growth leak_check --history` fails on a private word in an unpushed commit's
message, files or author identity. A second worktree does not have that file; pass it with
`--private-words <path-to-the-main-checkout>/.private-words`.
