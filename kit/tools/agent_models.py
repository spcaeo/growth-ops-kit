#!/usr/bin/env python3
"""Stop-hook guard: every helper runs on the model its role calls for (book/02-owner-rules.md "Agents").
It exists because a lead once started a page builder on the lead's own model instead of Sonnet, which also breaks the
rule that the independent reviewer is a different model from the builder.

Reads the hook input (JSON on stdin, with transcript_path), finds every Agent call since the owner's last message,
and checks its role (from its name and description) against the roles (growth.json agent_models, else the defaults). A call
with no model inherits the lead's model, read from the transcript. A call with no known role fails: name the role.
Prints each wrong call and exits 1; exits 0 otherwise. tools/stop_hook.sh turns that into a blocked stop.

  growth agent_models < hook_input.json
  growth agent_models --transcript <path.jsonl>
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import transcript as transcripts  # noqa: E402

# Default roles: builders sonnet; the independent reviewer opus (the strongest model, and different from the builders);
# log and count work haiku; screenshots and click-tests sonnet (they need sight). (growth.json "agent_models": {"roles": [{"match": "<regex on name + description>", "models": ["sonnet"]}, ...],
# "lead": "<model>" used only when the transcript names none, "exempt_types": ["Explore", ...]} replaces them).
# role pattern -> allowed models, first match wins
DEFAULT_ROLES = [
    # a helper that fixes or builds is a builder even when its name says what it fixes ("review fixes builder")
    (r"(?i)\bbuild(er|s|ing)?\b|\bfix(er|es|ing)?\b", {"sonnet"}),
    (r"(?i)review|audit|verif", {"opus"}),
    (r"(?i)log|count|triage|summar|tally", {"haiku"}),
    (r"(?i)evidence|shots|screenshot|click", {"sonnet"}),
]
BUILDER = DEFAULT_ROLES[0][0]
DECLARED = re.compile(r"(?i)(review|audit|verif).*of opus-built|of opus-built.*(review|audit|verif)")
EXEMPT_TYPES = {"fork", "explore", "plan", "claude-code-guide", "statusline-setup"}   # read-only or inherit by design
FAMILIES = ("opus", "sonnet", "haiku", "fable")


def family(model) -> str:
    """'claude-opus-5-5' -> 'opus'; an unknown name is kept as given, lower case; None/'' -> ''."""
    m = (model or "").lower()
    return next((f for f in FAMILIES if f in m), m)


def settings():
    """(roles, lead_fallback, exempt types) from growth.json "agent_models", else the defaults. Needs no project to run."""
    try:
        from config import CFG
        cfg = (CFG.get("agent_models") or {}) if isinstance(CFG, dict) else {}
    except (SystemExit, ImportError):
        cfg = {}
    roles = [(r["match"], {family(x) for x in r.get("models", [])}) for r in cfg.get("roles") or []
             if isinstance(r, dict) and r.get("match")] or DEFAULT_ROLES
    exempt = EXEMPT_TYPES | {str(x).lower() for x in cfg.get("exempt_types") or []}
    return roles, family(cfg.get("lead")), exempt


def agent_calls(transcript, all_turns=False):
    """Agent tool calls made after the owner's last message (all of them with all_turns), each with the model of the
    session that made it: [(input, lead_model_at_that_time)]."""
    calls, lead = [], ""
    for e in transcripts.entries(transcript):
        if transcripts.owner_text(e) is not None and not all_turns:
            calls = []
        if e.get("type") == "assistant" and not e.get("isSidechain"):
            m = (e.get("message") or {}).get("model")
            if isinstance(m, str) and m and not m.startswith("<"):
                lead = family(m)
        for b in transcripts.assistant_blocks(e):
            if b.get("type") == "tool_use" and b.get("name") in ("Agent", "Task"):
                calls.append((b.get("input") or {}, lead))
    return calls


def problems(calls, lead=None, roles=None, builders=None, exempt=None):
    """Wrong-model helpers. `calls`: Agent inputs, or (input, lead model) pairs from agent_calls. `lead`: the model a call
    with no model inherits, read from the transcript (else growth.json, else unknown, and an unknown inherited model is
    a problem: name the model). `builders`: the models builders really ran on in this session; a reviewer must differ from
    them. None (not known) falls back to the description's own words 'of opus-built', which is only a self-declaration."""
    cfg_roles, cfg_lead, cfg_exempt = settings()
    roles, exempt = roles or cfg_roles, exempt or cfg_exempt
    out = []
    for c in calls:
        c, seen_lead = c if isinstance(c, tuple) else (c, "")
        if (c.get("subagent_type") or "").lower() in exempt:
            continue
        who = f"{c.get('name', '')} {c.get('description', '')}".strip()
        model = family(c.get("model")) or family(seen_lead or lead) or cfg_lead
        pat = next(((p, ok) for p, ok in roles if re.search(p, who)), None)
        if pat is None:
            out.append(f"helper '{who}' has no role the kit knows, so its model cannot be judged. Name the role in its description "
                       "(builder, review, log/count, evidence) and start it again, or list the role in growth.json agent_models.")
            continue
        ok = set(pat[1])
        if pat[0] == DEFAULT_ROLES[1][0]:            # an independent reviewer differs from the model its builder ran on
            if builders is not None:
                if model in builders:      # the strongest model reviews, so a builder on it leaves no different model to review with
                    out.append(f"helper '{who}' reviews on {model}, the same model a builder ran on. Builders run on sonnet "
                               "(restart them there), so the independent reviewer can be opus, a different model.")
                    continue
            elif DECLARED.search(who):               # builders not known: the description's own word, a self-declaration
                ok = {"sonnet"}
        if not model:
            out.append(f"helper '{who}' has no model set and the session's own model is not known; start it with model="
                       f"{sorted(ok)[0]} named explicitly.")
        elif model not in ok:
            out.append(f"helper '{who}' runs on {model}; its role needs {' or '.join(sorted(ok))} "
                       f"(book/02-owner-rules.md 'Agents'). Stop it and start it again with model={sorted(ok)[0]}.")
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
    builders = {family(c.get("model")) or lead for c, lead in agent_calls(tp, all_turns=True)
                if re.search(BUILDER, f"{c.get('name', '')} {c.get('description', '')}")} - {""}
    probs = problems(agent_calls(tp), lead=transcripts.lead_model(tp), builders=builders)
    for p in probs:
        print(p)
    return 1 if probs else 0


if __name__ == "__main__":
    sys.exit(main())
