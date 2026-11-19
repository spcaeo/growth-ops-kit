#!/usr/bin/env python3
"""Stop-hook guard: every helper runs on the model its role calls for (book/02-owner-rules.md "Agents").
It exists because a lead once started a page builder on the lead's own model instead of Sonnet, which also breaks the
rule that the independent reviewer is a different model from the builder.

Reads the hook input (JSON on stdin, with transcript_path), finds every Agent call since the owner's last message,
and checks its role (from its name and description) against ROLES. A call with no model inherits the lead's model.
Prints each wrong call and exits 1; exits 0 otherwise. tools/stop_hook.sh turns that into a blocked stop.

  growth agent_models < hook_input.json
  growth agent_models --transcript <path.jsonl>
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

LEAD = "opus"  # a call with no model inherits the lead's model
# role pattern (matched on name + description) -> allowed models, first match wins
ROLES = [
    # a reviewer must differ from the builder: work built on Opus is reviewed on Sonnet ("of Opus-built" in the
    # description; this happened once when seven page folds were built on Opus by mistake)
    (re.compile(r"(?i)(review|audit|verif).*of opus-built|of opus-built.*(review|audit|verif)"), {"sonnet"}),
    # a helper that fixes or builds is a builder even when its name says what it fixes ("review fixes builder")
    (re.compile(r"(?i)\bbuild(er|s|ing)?\b|\bfix(er|es|ing)?\b"), {"sonnet"}),
    (re.compile(r"(?i)review|audit|verif"), {"opus"}),
    (re.compile(r"(?i)log|count|triage|summar|tally"), {"haiku"}),
    (re.compile(r"(?i)evidence|shots|screenshot|click"), {"sonnet"}),
]


def agent_calls(transcript):
    """Agent tool calls made after the owner's last typed message."""
    calls = []
    for line in Path(transcript).read_text(errors="replace").splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("type") == "user" and isinstance(e.get("message", {}).get("content"), str):
            calls = []
        if e.get("type") == "assistant":
            for b in e.get("message", {}).get("content", []) or []:
                if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "Agent":
                    calls.append(b.get("input", {}))
    return calls


def problems(calls):
    out = []
    for c in calls:
        if c.get("subagent_type") == "fork":
            continue
        who = f"{c.get('name', '')} {c.get('description', '')}"
        model = c.get("model") or LEAD
        for pat, ok in ROLES:
            if pat.search(who):
                if model not in ok:
                    out.append(f"helper '{who.strip()}' runs on {model}; its role needs {' or '.join(sorted(ok))} "
                               f"(book/02-owner-rules.md 'Agents'). Stop it and start it again with model={sorted(ok)[0]}.")
                break
    return out


def main():
    if "--transcript" in sys.argv:
        tp = sys.argv[sys.argv.index("--transcript") + 1]
    else:
        try:
            tp = json.load(sys.stdin).get("transcript_path", "")
        except ValueError:
            return 0
    if not tp or not Path(tp).exists():
        return 0
    probs = problems(agent_calls(tp))
    for p in probs:
        print(p)
    return 1 if probs else 0


if __name__ == "__main__":
    sys.exit(main())
