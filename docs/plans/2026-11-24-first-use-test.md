# Kit 3.0 first-use test on a real site (24 Nov 2026)

Owner: "think this way some one is using this kit for frist time just downloaded from github.. lets preented that".
The kit is cloned fresh, installed with `setup.sh`, set up with `growth setup`, then used for the home page. Each row is
something a newcomer meets, with what was done about it.

| # | Step | What the newcomer met | Fix | Status |
| --- | --- | --- | --- | --- |
| 1 | Install | `setup.sh` puts its add-ons in `~/.growth-ops-kit/venv` and links `growth` in `~/.local/bin`, outside the kit folder, without saying so up front | README now says how to keep everything inside the kit (`GROWTH_VENV=$PWD/.venv GROWTH_BIN=$PWD/.bin`) | fixed in the kit |
| 2 | Install | With the add-ons kept inside the kit, `setup.sh` ended "SETUP FAILED": the leak check read the packages in `.venv` (271 false hits), because the kit's `.gitignore` did not list `.venv/` or `.bin/` | `.venv/` and `.bin/` added to the kit's `.gitignore` | fixed in the kit |
| 3 | Install | Kit 3.0's own commit check failed once: tests that use the demo project in place leave `state/growth.db`, and the leak check flagged it as a secret by name in the commit's snapshot | The leak check skips a folder whose own `.gitignore` is `*` (the database folder), with a test | fixed in the kit |
| 4 | Set up | `growth setup` made the project folder by itself (beside the kit) without asking where | Kept: the name and place are right for this project | noted |
| 5 | Set up | The setup asks for one country and language; nothing in the kit handles several languages and markets (hreflang, x-default, per-market research), which a site with several markets needs from day 1 | Kit 3.0: `market.locales`, an international page check, a translation job per language on the board, research per market (builder at work) | in progress |
| 6 | Set up | The kit has no Astro adapter: on an Astro site its code checks print SKIP (its live-page checks all work). the real site is Astro + Markstage | To build after the home page: an Astro adapter (content collections, build and redirect checks) | to do |
| 7 | Set up | `growth doctor` says OK for A3 (site studied) when no site repo is named, and OK for A4 (analytics connected) when no connector is switched on: a newcomer reads 5/16 done when 2 of the 5 were never done | Doctor should say SKIP or TODO for a step that was never configured, never OK | to fix |
| 8 | Before pictures | The live-site rule has two settings (no-crawl, crawl-ok). With no-crawl, `growth page_archive --stage before` is refused, yet the rulebook (rule 36i) wants a "before" picture of every page: a newcomer must choose between the safe rule and the before archive | Add a gentle exception (for example `live_site_allow: ["page_archive"]`, one page at a time through a pacer, trackers blocked) | to fix; this time the rule was lifted for the 12 pictures only and restored |
| 9 | Set up | The owner's own commands (`growth approve browser`) are given as long lines with `cd ... && VAR=... VAR=... path/growth approve browser`; pasted into a terminal, the line wrapped and broke ("zsh: command not found: approve") | Give the owner a short script per approval ; the kit should write one into every new project | to fix |
| 10 | Before pictures | `growth page_archive` does not close pop-ups: on 7 of 12 pages of a real site a "free assessment" pop-up covers the first screen | Close or hide pop-ups and chat widgets before the capture (one list of common selectors, plus a growth.json list) | to fix |

Status at the end of the day: 1-3 fixed; 5 built (international support); 9 removed at the root by chat mode (the owner
never runs a command: "get rid off all such permissions steps from kit"); 4 noted; 6, 7, 8 and 10 open for the next
release.
