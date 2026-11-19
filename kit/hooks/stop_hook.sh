#!/usr/bin/env bash
# Claude Code Stop hook (".md files are not followed fully; rules must run").
# Runs when Claude finishes a reply. If an owner message is not in the steps log, or a rule has no check, it blocks
# the stop (exit 2) and shows the failing lines so Claude fixes them first. On the second try in a row
# (stop_hook_active) it warns instead of blocking, so a check that cannot pass never traps the session.
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
[ -z "$OUT" ] && exit 0
if [ "$ACTIVE" = "true" ]; then
  python3 -c 'import json,sys; print(json.dumps({"systemMessage": "Rule checks still failing:\n" + sys.argv[1]}))' "$OUT"
  exit 0
fi
printf '%s' "$OUT" >&2
exit 2
