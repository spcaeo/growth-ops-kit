#!/usr/bin/env bash
# Claude Code Stop hook (".md files are not followed fully; rules must run").
# Runs when Claude finishes a reply. If an owner message is not in the steps log, or a rule has no check, it blocks
# the stop (exit 2) and shows the failing lines so Claude fixes them first. On the second try in a row
# (stop_hook_active) it warns instead of blocking (and files a journal note, so the owner sees it). The task-workflow checks
# (growth workflow check: no open task while files changed, steps done with no proof) are never softened: they block every
# time and print the command that clears them. A chat that is not page work: growth tasks add "Chat: ..." "" --type chat
# Needs the project folder: GROWTH_PROJECT, or run from inside it (the nearest folder holding growth.json).
G="$(cd "$(dirname "$0")/../.." && pwd)/growth"
INPUT=$(cat)
ACTIVE=$(printf '%s' "$INPUT" | python3 -c 'import json,sys
try: print(str(json.load(sys.stdin).get("stop_hook_active", False)).lower())
except Exception: print("false")')
OUT=""
if ! R=$("$G" owner_messages check 2>&1); then
  OUT+=$'Owner messages not in docs/steps-log.md (book/01-flow.md stage F):\n'"$(printf '%s\n' "$R" | grep -E '^(MISSING|ANSWER)')"$'\n'
fi
if ! R=$(printf '%s' "$INPUT" | "$G" url_guard 2>&1); then
  OUT+="$R"$'\n'
fi
if ! R=$(printf '%s' "$INPUT" | "$G" agent_models 2>&1); then
  OUT+=$'Helpers on the wrong model (book/02-owner-rules.md Agents):\n'"$R"$'\n'
fi
WF=$("$G" workflow check 2>&1 >/dev/null)
[ -z "$OUT" ] && [ -z "$WF" ] && exit 0
if [ -n "$WF" ]; then
  printf '%s\n%s' "$WF" "$OUT" >&2
  exit 2
fi
if [ "$ACTIVE" = "true" ]; then
  "$G" journal add --kind note --title "Stop hook: warned through" --text "$OUT" --tag stop-hook >/dev/null 2>&1
  python3 -c 'import json,sys; print(json.dumps({"systemMessage": "Rule checks still failing:\n" + sys.argv[1]}))' "$OUT"
  exit 0
fi
printf '%s' "$OUT" >&2
exit 2
