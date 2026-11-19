#!/usr/bin/env python3
"""Stop-hook guard for the golden rule: never share a page URL with the owner before it is 100% approved and checked.
Off unless growth.json has "preview_url" (the one preview address).

Reads the hook input (JSON on stdin, with transcript_path), takes Claude's last reply to the owner, and finds every
local page URL in it (this machine or the private network: 127.0.0.1, 0.0.0.0, localhost in any case, 192.168.x.x, 10.x.x.x, *.local, with or without http://,
on the preview port or a port in growth.json preview_ports, default 3700-3799; any address on the preview_url host). Each page must be READY in
journal/ready.json at the preview worktree's current commit (growth ready). Prints the offending URLs and exits 1
when any is not READY; exits 0 otherwise. tools/stop_hook.sh turns that into a blocked stop, so the reply must be
corrected (the URL withdrawn) before the turn can end.
"""
from __future__ import annotations

import ipaddress
import json
import re
import socket
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import transcript as transcripts  # noqa: E402
from config import CFG  # noqa: E402
from ready import is_ready  # noqa: E402

def preview_host() -> str:
    return (urlsplit(CFG.get("preview_url", "")).hostname or "").lower()


def preview_port():
    return urlsplit(CFG.get("preview_url", "")).port


def port_ok(port: int, spec=None) -> bool:
    """Is `port` one of the preview ports? growth.json preview_ports: a list of ports, {"from": a, "to": b}, or "a-b".
    A list of exactly two numbers stays a range (the older form); use {"from", "to"} for a range and a list of 3+ for exact ports."""
    spec = CFG.get("preview_ports", [3700, 3799]) if spec is None else spec
    try:
        if isinstance(spec, dict):
            return int(spec["from"]) <= port <= int(spec["to"])
        if isinstance(spec, str):
            lo, _, hi = spec.partition("-")
            return int(lo) <= port <= int(hi or lo)
        ports = [int(x) for x in spec]
    except (KeyError, ValueError, TypeError):
        return True                                  # a setting this guard cannot read must not switch it off
    if len(ports) == 2 and ports[0] <= ports[1]:
        return ports[0] <= port <= ports[1]
    return port in ports


def _generic(host: str) -> bool:
    """A loopback or private-network address or name (not a named preview host)."""
    try:
        ip = ipaddress.ip_address(host.strip("[]"))
        return ip.is_private or ip.is_loopback or ip.is_unspecified or ip.is_link_local
    except ValueError:
        return host in ("localhost", "ip6-localhost") or host.endswith((".localhost", ".local"))


def is_local_host(host: str) -> bool:
    """True for this machine and the private network: localhost in any case, 0.0.0.0, 127/8, ::1, RFC1918, link-local,
    *.local, this machine's hostname, and the preview_url host whatever it is."""
    host = host.strip("[]").lower().rstrip(".")
    if not host:
        return False
    if host == preview_host() or (host in ("localhost", "ip6-localhost") or host.endswith((".localhost", ".local"))):
        return True
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_private or ip.is_loopback or ip.is_unspecified or ip.is_link_local
    except ValueError:
        pass
    try:
        return host in (socket.gethostname().lower(), socket.gethostname().lower().split(".")[0])
    except OSError:
        return False


HOST = r"(?:\[[0-9a-fA-F:.]+\]|[A-Za-z0-9](?:[A-Za-z0-9.\-]*[A-Za-z0-9])?)"
# an address with a scheme (any port or none), or a bare host:port; the path stops at the usual closers
URL = re.compile(r"(?<![\w@./:-])(?:(?P<scheme>https?)://)?(?P<host>" + HOST + r")(?::(?P<port>\d{2,5}))?(?P<path>/[^\s)>\]\"'`|*,]*)?",
                 re.I)


def last_exchange(transcript):
    """Claude's reply text since the owner's last message, and that message."""
    text, asked = "", ""
    for e in transcripts.entries(transcript):
        t = transcripts.owner_text(e)
        if t is not None:
            text, asked = "", t                      # a new owner message starts a new reply
        for b in transcripts.assistant_blocks(e):
            if b.get("type") == "text":
                text += "\n" + (b.get("text") or "")
    return text, asked


# When the owner's own message explicitly asks for a link that is not approved, unready local links may be given, but only
# marked "not approved yet", so a link is never mistaken for a page that passed. Saying "links" or "backlinks" is not asking.
OWNER_ASKED = re.compile(r"\b(unapproved|not[- ]approved|not[- ]ready|unready|draft|work[- ]in[- ]progress)\b[^.\n]{0,40}\b(urls?|links?)\b"
                         r"|\b(urls?|links?)\b[^.\n]{0,40}\b(unapproved|not[- ]approved|not[- ]ready|unready|even if (it'?s|it is) not)\b"
                         r"|\bbefore (it'?s|it is) (approved|ready)\b", re.I)
MARK = "not approved yet"


def offenders(text):
    bad = []
    pport, phost = preview_port(), preview_host()
    for m in URL.finditer(text):
        host, port, scheme = m.group("host"), m.group("port"), m.group("scheme")
        if not scheme and not port and host.lower() != phost:
            continue                                  # a bare word or domain with no scheme and no port is not a local address
        if not is_local_host(host):
            continue
        named_preview = host.lower() == phost and not _generic(phost)    # a real preview name: every port on it is a preview
        if not named_preview and (port is None or not (int(port) == pport or port_ok(int(port)))):
            continue                                  # some other local service, not a preview port
        path = urlsplit("http://x" + (m.group("path") or "/")).path.rstrip("/.") or "/"
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
