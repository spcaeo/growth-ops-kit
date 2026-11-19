#!/usr/bin/env bash
# Start the page tracker by hand (nothing starts with the computer).
#   bash start.sh              # pull today's data, then open the dashboard (Ctrl+C stops it)
#   bash start.sh --no-sync    # dashboard only
# Run it inside the project folder (or set GROWTH_PROJECT). Paths are relative to this file.
set -euo pipefail
cd "$(dirname "$0")"
if [ "${1:-}" != "--no-sync" ]; then
  echo "Pulling today's data (sitemap, git history, and the connectors switched on in growth.json)..."
  python3 tracker.py sync && python3 tracker.py report
fi
PORT=$(python3 -c 'import config; print(config.PORT)')
echo "Dashboard: http://127.0.0.1:$PORT/dashboard.html  (Ctrl+C to stop)"
exec python3 serve.py
