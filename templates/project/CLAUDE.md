# Growth Ops for {{name}}: instructions for the agent

This project folder holds the facts and the data of one website's growth work. The method is in the Growth Ops Kit
(the book and the tools). The kit is at `{{kit_root}}`. Set its location once: `export GROWTH_KIT={{kit_root}}` and put
`$GROWTH_KIT` on your PATH so `growth` works from this folder (`growth` is the kit's one command; `setup.sh` also links it
into `~/.local/bin`).

Read, before any work, in this order:
1. The book's `01-flow.md` (the order of work) and `02-owner-rules.md` (the default working rules), in the kit's
   `book/` folder.
2. This folder's own files: `OWNER-RULES.md` (the owner's extra rules), `BRAND.md` (what may be claimed), `SETUP.md`
   (the project's facts), `growth.json` (the config every tool reads).
3. `docs/steps-log.md` (every owner instruction, dated) and `growth tasks list` (where the work is).

Each rule has one home: link to it, never copy it here.

Before you act:
- `growth doctor` must say every step OK before any page work.
- Open the job's playbook (the book's `playbooks/`) and copy every step into the task (`growth tasks step`). No
  shortcuts.
- Before any page code: `growth preflight <path> --type ... --key ...` must say PASS (rule 0a); the gate runs after
  every commit; no URL to the owner before `growth ready` says READY.
- The site repo (`growth.json` `site_repo`) follows its own agent rules. A push to its production branch may be a live
  deploy: never push or merge without the owner's explicit yes in this conversation.
- The keys file named in `growth.json` `keys_file`: never print, copy or commit it.
- Every owner instruction: flow stage F (log it in `docs/steps-log.md` first, put the rule in its one home).
- Write to the owner in simple English, answer first.
