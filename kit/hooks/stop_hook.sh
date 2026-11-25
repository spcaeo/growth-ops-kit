#!/usr/bin/env bash
# Claude Code Stop hook (".md files are not followed fully; rules must run").
# Runs when Claude finishes a reply. If an owner message is not in the steps log, or a rule has no check, it blocks
# the stop (exit 2) and shows the failing lines so Claude fixes them first. On the second try in a row
# (stop_hook_active) it warns instead of blocking (and files a journal note, so the owner sees it). The task-workflow checks
# (growth workflow check: no page task while files changed or were committed, steps done with no proof) and the golden rule
# (growth url_guard: a page URL that is not READY) are never softened: they block every
# time and print the command that clears them. A chat that is not page work: growth tasks add "Chat: ..." "" --type chat
# Needs the project folder: GROWTH_PROJECT, or run from inside it (the nearest folder holding growth.json).
G="$(cd "$(dirname "$0")/../.." && pwd)/growth"
INPUT=$(cat)
ACTIVE=$(printf '%s' "$INPUT" | python3 -c 'import json,sys
try: print(str(json.load(sys.stdin).get("stop_hook_active", False)).lower())
except Exception: print("false")')
# Claude may be started in a folder above the project: find the project (GROWTH_PROJECT, the folder Claude is in, a folder
# above it, or exactly one project below it) and use it for every check; refuse loudly (block once) when there is none.
START=$(printf '%s' "$INPUT" | python3 -c 'import json,sys
try: print(json.load(sys.stdin).get("cwd", ""))
except Exception: print("")')
[ -z "$START" ] && START="${CLAUDE_PROJECT_DIR:-$PWD}"
if P=$("$G" workflow resolve "$START" 2>/dev/null); then
  export GROWTH_PROJECT="$P"
else
  MSG=$("$G" workflow resolve "$START" 2>&1 >/dev/null)
  [ -z "$MSG" ] && MSG="Claude was started outside a growth project and the rule guards could not find it. Restart Claude in the project folder, or set GROWTH_PROJECT=<project folder>."
  if [ "$ACTIVE" = "true" ]; then
    python3 -c 'import json,sys; print(json.dumps({"systemMessage": "Rule guards are OFF this turn: " + sys.argv[1]}))' "$MSG"
    exit 0
  fi
  printf 'Rule guards are not running: %s\n' "$MSG" >&2
  exit 2
fi
OUT=""     # soft rules: blocked once, then a warning
HARD=""    # never softened: the golden rule (a URL not READY)
"$G" owner_messages log-missing >/dev/null 2>&1      # quiet book-keeping: the row is written here, never asked for in chat
if ! R=$("$G" owner_messages check 2>&1); then
  L=$(printf '%s\n' "$R" | grep -E '^(MISSING|ANSWER)')
  if [ -n "$L" ]; then
    OUT+=$'Owner messages not in docs/steps-log.md (book/01-flow.md stage F):\n'"$L"$'\n'
  elif printf '%s' "$R" | grep -q 'NO TRANSCRIPTS'; then
    OUT+=$'Owner messages could not be checked: no session transcripts were found for this project (set growth.json transcripts_dir, or start Claude inside the project folder). First line: '"$(printf '%s\n' "$R" | head -1)"$'\n'
  else
    OUT+=$'Owner message check failed: '"$(printf '%s\n' "$R" | head -3)"$'\n'
  fi
fi
if ! R=$(printf '%s' "$INPUT" | "$G" url_guard 2>&1); then
  HARD+="${R:-GOLDEN RULE: the URL guard failed with no message; withdraw any local page link you showed the owner.}"$'\n'
fi
if ! R=$(printf '%s' "$INPUT" | "$G" agent_models 2>&1); then
  OUT+=$'Helpers on the wrong model (book/02-owner-rules.md Agents):\n'"${R:-the model guard failed with no message}"$'\n'
fi
WF=$("$G" workflow check 2>&1 >/dev/null)
[ -z "$OUT" ] && [ -z "$WF" ] && [ -z "$HARD" ] && exit 0
if [ -n "$WF" ] || [ -n "$HARD" ]; then
  printf '%s\n%s\n%s' "$WF" "$HARD" "$OUT" >&2
  exit 2
fi
if [ "$ACTIVE" = "true" ]; then     # soft rules are never shown in the owner's chat (owner, 24 Nov 2026: less noise); the journal keeps them
  "$G" journal add --kind note --title "Stop hook: warned through" --text "$OUT" --tag stop-hook >/dev/null 2>&1
  exit 0
fi
printf '%s' "$OUT" >&2
exit 2
