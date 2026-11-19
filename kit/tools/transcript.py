"""One reader for Claude Code session transcripts (library), shared by the Stop-hook guards (url_guard, agent_models).

An owner message is what the owner typed: a plain string, or a list of blocks holding text and/or images (a pasted
screenshot arrives as a list). Tool results, system notes, teammate messages and side-chain turns are not owner messages.
No project is needed to import this module.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

SKIP = ("Another Claude session sent a message", "<task-notification", "<teammate-message", "<system-reminder", "<command-name>",
        "<local-command", "Caveat:", "[Request interrupted", "This session is being continued")


def entries(path):
    for line in Path(path).read_text(errors="replace").splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if isinstance(e, dict):
            yield e


def owner_text(e):
    """The owner's words in a transcript entry, or None when the entry is not an owner message."""
    if e.get("type") != "user" or e.get("isMeta") or e.get("isSidechain"):
        return None
    msg = e.get("message")
    c = msg.get("content") if isinstance(msg, dict) else None
    if isinstance(c, str):
        blocks = [{"type": "text", "text": c}]
    elif isinstance(c, list):
        blocks = [b for b in c if isinstance(b, dict)]
    else:
        return None
    if any(b.get("type") == "tool_result" for b in blocks):
        return None
    texts, image = [], False
    for b in blocks:
        if b.get("type") == "text":
            t = re.sub(r"<system-reminder>.*?</system-reminder>", "", b.get("text") or "", flags=re.S).strip()
            if t and not t.startswith(SKIP):
                texts.append(t)
        elif b.get("type") in ("image", "document"):
            image = True
    if texts:
        return "\n".join(texts)
    return "[attachment]" if image else None


def lead_model(path):
    """The model the lead session actually ran on (the last main-thread assistant turn), lower case, or ''."""
    model = ""
    for e in entries(path):
        if e.get("type") == "assistant" and not e.get("isSidechain"):
            m = (e.get("message") or {}).get("model")
            if isinstance(m, str) and m and not m.startswith("<"):
                model = m.lower()
    return model


def assistant_blocks(e):
    if e.get("type") != "assistant":
        return []
    c = (e.get("message") or {}).get("content")
    return [b for b in c if isinstance(b, dict)] if isinstance(c, list) else []
