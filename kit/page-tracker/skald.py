"""Read-only Skald MCP client for the page tracker. Off unless growth.json connectors.skald.on is true.
The token is read from the keys file named in growth.json `keys_file` (outside git) and never printed or logged.
The file holds two lines: SKALD_MCP_URL=... and SKALD_MCP_TOKEN=... A missing key gives one plain note, never a crash."""
import json, os, sys, urllib.request
import config

KEYS = str(config.KEYS_FILE) if config.KEYS_FILE else ""
_noted = []


class SourceOff(RuntimeError):
    """Skald is switched off in growth.json (or its keys file is missing)."""


def enabled():
    if not config.source_on("skald"):
        return False
    if not (KEYS and os.path.exists(KEYS)):
        if not _noted:
            _noted.append(1)
            print("note: connector 'skald' is on in growth.json but the keys file was not found: " + (KEYS or "growth.json keys_file is not set") + "; "
                  "skipping Skald, Search Console and GA4 for this run.", file=sys.stderr)
        return False
    return True

def _env():
    env = {}
    for line in open(KEYS):
        if "=" in line and not line.startswith("#"):
            k, v = line.strip().split("=", 1)
            env[k] = v.strip().strip('"').strip("'")
    return env["SKALD_MCP_URL"], env["SKALD_MCP_TOKEN"]

READ_ONLY = {"search_performance", "page_journeys", "list_sites", "overview", "breakdown", "top_pages", "ai_activity", "leads", "funnel", "compare",
             "page_story", "live_today", "data_quality", "site_health", "conversions", "what_changed", "todos",
             "lost_pages", "page_changes", "ai_readiness", "changed_pages", "your_tools", "find_person"}

def call(tool, **args):
    if not enabled():
        if not config.source_on("skald"):
            raise SourceOff("Skald is off: growth.json connectors.skald.on is not true")
        raise SourceOff(f"Skald keys file not found: {KEYS or '(growth.json keys_file is not set)'}")
    if tool not in READ_ONLY:
        raise SystemExit(f"{tool} is not a read-only tool; the tracker never writes to Skald")
    url, token = _env()
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": tool, "arguments": args}}).encode()
    req = urllib.request.Request(url, data=body, headers={"Authorization": "Bearer " + token, "Content-Type": "application/json",
                                                          "Accept": "application/json, text/event-stream"})
    raw = urllib.request.urlopen(req, timeout=90).read().decode()
    if raw.lstrip().startswith("event:") or "\ndata:" in raw:
        raw = "\n".join(l[5:] for l in raw.splitlines() if l.startswith("data:"))
    d = json.loads(raw)
    if "error" in d:
        raise RuntimeError(json.dumps(d["error"]))
    return d["result"]

if __name__ == "__main__":
    tool = sys.argv[1]; args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    r = call(tool, **args)
    print(json.dumps(r, indent=1)[:int(os.environ.get("MAX", "6000"))])
