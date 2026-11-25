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

# Default roles: builders and researchers sonnet; the independent reviewer opus (the strongest model, and different from the builders);
# log and count work haiku; screenshots and click-tests sonnet (they need sight). (growth.json "agent_models": {"roles": [{"match": "<regex on name + description>", "models": ["sonnet"]}, ...],
# "lead": "<model>" used only when the transcript names none, "exempt_types": ["Explore", ...]} replaces them).
# role pattern -> allowed models, first match wins
DEFAULT_ROLES = [
    # an explicit builder word wins ("review fixes builder" builds); then a researcher; then a REVIEW wins over the
    # word "fix" ("T40 independent review: a2a truth fix" reviews, friction 54); a plain fixer is a builder
    (r"(?i)\bbuild(er|ers|s|ing)?\b", {"sonnet"}),
    # a researcher reads sources and writes a research file (it may "verify facts"): mid model, before the reviewer pattern
    (r"(?i)\bresearch(er|ers|ing)?\b", {"sonnet"}),
    (r"(?i)review|audit|verif", {"opus"}),
    (r"(?i)\bfix(er|ers|es|ing)?\b", {"sonnet"}),
    # whole words only: "account" is not a count job, "catalog" not a log job (friction 53)
    (r"(?i)\b(logs?|counts?|counting|triage|summar\w*|tally)\b", {"haiku"}),
    (r"(?i)\b(evidence|shots?|screenshots?|click\w*)\b", {"sonnet"}),
]
BUILDER = r"(?i)\bbuild(er|ers|s|ing)?\b|^(?!.*(review|audit|verif)).*\bfix(er|ers|es|ing)?\b"   # who built (for the reviewer's comparison)
RECENT_MINUTES = 120    # only helpers launched in the last two hours are judged; earlier ones were judged when they ran (friction 54)
REVIEWER = r"(?i)review|audit|verif"   # the independent reviewer's pattern (matched by value, not by list position)
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


ROLE_PREFIX = re.compile(r"^\s*([A-Za-z][A-Za-z /&-]{1,30}):\s")


def role_words(c, roles=None):
    """The words a helper's role is read from. A description that opens with a role label ("review: ...",
    "builder: ...") is judged by that label alone, so a reviewer described as "review: the plan before build" is not
    taken for a builder by the word "build" later on (friction, 24 Nov 2026). Otherwise the name and the description."""
    desc = str(c.get("description", ""))
    m = ROLE_PREFIX.match(desc)
    if m and any(re.search(p, m.group(1)) for p, _ in (roles or DEFAULT_ROLES)):
        return m.group(1)
    return f"{c.get('name', '')} {desc}".strip()


def _is_tool_result(e):
    c = (e.get("message") or {}).get("content")
    return isinstance(c, list) and any(isinstance(b, dict) and b.get("type") == "tool_result" for b in c)


def agent_calls(transcript, all_turns=False, recent_only=True):
    """Agent tool calls made after the owner's last message (all of them with all_turns), each with the model of the
    session that made it: [(input, lead_model_at_that_time)]."""
    calls, lead = [], ""
    use_to_agent, stopped = {}, set()       # Agent tool_use id -> launched agent id; agent ids stopped with TaskStop
    for e in transcripts.entries(transcript):
        # a new turn starts at any user entry that is not a tool result (the owner, a peer's message, a task notice):
        # only helpers started in THIS turn are judged, so a finished helper never re-blocks later stops (issue #67)
        if not all_turns and e.get("type") == "user" and not e.get("isSidechain") and not _is_tool_result(e):
            calls = []
        if e.get("type") == "assistant" and not e.get("isSidechain"):
            m = (e.get("message") or {}).get("model")
            if isinstance(m, str) and m and not m.startswith("<"):
                lead = family(m)
        for b in transcripts.assistant_blocks(e):
            if b.get("type") == "tool_use" and b.get("name") in ("Agent", "Task"):
                calls.append((b.get("input") or {}, lead, b.get("id"), e.get("timestamp") or ""))
            elif b.get("type") == "tool_use" and b.get("name") == "TaskStop":
                stopped.add(str((b.get("input") or {}).get("task_id") or ""))
        content = (e.get("message") or {}).get("content") if e.get("type") == "user" else None
        for b in content if isinstance(content, list) else []:
            if isinstance(b, dict) and b.get("type") == "tool_result":
                m = re.search(r"agentId:\s*([\w-]+)", json.dumps(b.get("content")))
                if m:
                    use_to_agent[b.get("tool_use_id")] = m.group(1)
    # a helper the session stopped (TaskStop) is gone: it is not judged (friction 51)
    live = [(c, ld, ts) for c, ld, uid, ts in calls if use_to_agent.get(uid) not in stopped or not use_to_agent.get(uid)]
    if not all_turns and recent_only:
        import datetime as _dt
        def when(ts):
            try:
                return _dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                return None
        stamps = [w for w in (when(ts) for _, _, ts in live) if w]
        if stamps:
            cut = max(stamps) - _dt.timedelta(minutes=RECENT_MINUTES)
            live = [x for x in live if (when(x[2]) or cut) >= cut]
    return [(c, ld) for c, ld, _ in live]


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
        pat = next(((p, ok) for p, ok in roles if re.search(p, role_words(c, roles))), None)
        if pat is None:
            out.append(f"helper '{who}' has no role the kit knows, so its model cannot be judged. Name the role in its description "
                       "(builder, review, log/count, evidence) and start it again, or list the role in growth.json agent_models.")
            continue
        ok = set(pat[1])
        if pat[0] == REVIEWER:            # an independent reviewer differs from the model its builder ran on
            builders_of = builders(who) if callable(builders) else builders   # its own job's builders (friction 48)
            if builders_of is not None:
                if model in builders_of:      # the strongest model reviews, so a builder on it leaves no different model to review with
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


JOB = re.compile(r"\bT\d+\b|/[\w./-]{2,}|\bpage\s*\d+\b", re.I)


def builders_for(who, built):
    """The models the builders of THIS reviewer's job ran on (friction 48: every builder of the whole session was counted,
    so one old opus builder flagged every later opus reviewer). A job is named by a task id (T21), a path (/pricing/) or
    'page 1' in both descriptions; with no shared name, the most recent builder before the review stands for its job.
    `built`: [(name + description, model)] in transcript order. None when no builder is known."""
    jobs = {j.lower().rstrip("/") for j in JOB.findall(who)}
    mine = [m for w, m in built if jobs & {j.lower().rstrip("/") for j in JOB.findall(w)}]
    if mine:
        return set(mine) - {""}
    return ({built[-1][1]} - {""}) if built else None


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
    built = [(f"{c.get('name', '')} {c.get('description', '')}", family(c.get("model")) or lead)
             for c, lead in agent_calls(tp, all_turns=True) if re.search(BUILDER, role_words(c))]
    probs = problems(agent_calls(tp), lead=transcripts.lead_model(tp), builders=lambda who: builders_for(who, built))
    for p in probs:
        print(p)
    return 1 if probs else 0


if __name__ == "__main__":
    sys.exit(main())
