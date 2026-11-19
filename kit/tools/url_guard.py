#!/usr/bin/env python3
"""Stop-hook guard for the golden rule: never share a page URL with the owner before it is 100% approved and checked.
Off unless growth.json has "preview_url" (the one preview address).

Reads the hook input (JSON on stdin, with transcript_path), takes Claude's last reply to the owner, and finds every
local page URL in it (127.0.0.1 or localhost on the preview port or any dev port in growth.json preview_ports, default 3700-3799). Each page must be READY in
journal/ready.json at the preview worktree's current commit (growth ready). Prints the offending URLs and exits 1
when any is not READY; exits 0 otherwise. tools/stop_hook.sh turns that into a blocked stop, so the reply must be
corrected (the URL withdrawn) before the turn can end.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import CFG  # noqa: E402
from ready import is_ready  # noqa: E402

PREVIEW_PORT = urlsplit(CFG.get("preview_url", "")).port
PORTS = CFG.get("preview_ports", [3700, 3799])
URL = re.compile(r"https?://(?:127\.0\.0\.1|localhost|\[::1\]):(\d{2,5})(/[^\s)>\]\"'`|*,]*)?")


def last_exchange(transcript):
    """The owner's last message and Claude's reply to it."""
    text, asked = "", ""
    for line in Path(transcript).read_text(errors="replace").splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("type") == "user" and isinstance(e.get("message", {}).get("content"), str):
            text, asked = "", e["message"]["content"]   # a new owner message starts a new reply
        if e.get("type") == "assistant":
            for b in e.get("message", {}).get("content", []) or []:
                if isinstance(b, dict) and b.get("type") == "text":
                    text += "\n" + b.get("text", "")
    return text, asked


# When the owner's own message asks for URLs, unready local links may be given, but only marked "not approved yet",
# so a link is never mistaken for a page that passed.
OWNER_ASKED = re.compile(r"\burls?\b|\blinks?\b", re.I)
MARK = "not approved yet"


def offenders(text):
    bad = []
    for m in URL.finditer(text):
        port = int(m.group(1))
        if port != PREVIEW_PORT and not PORTS[0] <= port <= PORTS[1]:
            continue
        path = urlsplit("http://x" + (m.group(2) or "/")).path.rstrip("/.") or "/"
        if not is_ready(path):
            bad.append(m.group(0))
    return sorted(set(bad))


def main():
    if not CFG.get("preview_url"):
        return 0                                  # the golden rule is off for projects that keep no preview address
    try:
        data = json.load(sys.stdin)
        text, asked = last_exchange(data["transcript_path"])
    except Exception:  # noqa: BLE001  no transcript: nothing to check
        return 0
    bad = offenders(text)
    if bad and OWNER_ASKED.search(asked) and MARK in text.lower():
        return 0
    if bad:
        print("GOLDEN RULE: page URL(s) shown to the owner that are not READY (growth ready, 0 FAIL at the current "
              "commit):\n  " + "\n  ".join(bad) + "\nWithdraw them in a short correction; share a URL only after "
              "`growth ready <path> --type ... --key ...` says READY.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
