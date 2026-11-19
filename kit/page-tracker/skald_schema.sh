#!/usr/bin/env bash
# Print the full description and input schema of Skald tools (read-only; the token is never printed).
set -euo pipefail
KEYS="${SKALD_KEYS:?set SKALD_KEYS to the keys file named in growth.json keys_file (outside git)}"
eval "$(grep -E '^(SKALD_MCP_URL|SKALD_MCP_TOKEN)=' "$KEYS" | sed 's/^/export /')"
curl -s -m 60 -H "Authorization: Bearer $SKALD_MCP_TOKEN" -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' "$SKALD_MCP_URL" -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' |
python3 -c '
import sys, json
want=set(sys.argv[1:])
for t in json.load(sys.stdin)["result"]["tools"]:
    if not want or t["name"] in want:
        print("=== "+t["name"]); print(t.get("description","")); print(json.dumps(t.get("inputSchema",{}).get("properties",{}),indent=1)[:1500])
' "$@"
