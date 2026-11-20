"""Cases for the Stop-hook model guard (kit/tools/agent_models.py). 1 = the call must be flagged, 0 = it must pass."""
import pytest

from agent_models import problems

CASES = [
    ("pp-fixer", "Pricing page review fixes builder", "sonnet", 0),  # a fixer named after a review is a builder
    ("pp-builder", "Pricing page builder", "opus", 1),  # builders run on Sonnet
    ("pp-builder", "Pricing page builder", None, 1),  # no model inherits the lead's (Opus)
    ("pp-review-a", "Pricing page independent review, part 1", "opus", 0),
    ("pp-review-b", "Review of Opus-built pricing folds (part 2)", "sonnet", 0),
    ("pp-review-b", "Review of Opus-built pricing folds (part 2)", "opus", 1),
    ("r", "Independent review", "sonnet", 1),
    ("x", "Count log lines", None, 1),
    ("e", "Final evidence shots", "sonnet", 0),
    ("rs", "Researcher: AU region vendor pages, verify facts", "sonnet", 0),  # a researcher is known (friction 45)
    ("rs", "Researcher: AU region vendor pages", "opus", 1),
    ("ev", "page 4 evidence: account-to-account dossier", "sonnet", 0),   # friction 53: 'account' is not 'count'
    ("x", "Count log lines", "haiku", 0),
]


@pytest.mark.parametrize("name,desc,model,flagged", CASES)
def test_cases(name, desc, model, flagged):
    assert len(problems([{"name": name, "description": desc, "model": model}])) == flagged


def test_a_reviewer_is_compared_with_its_own_jobs_builder_only():
    # friction 48: an earlier job's opus builder flagged every later opus reviewer for the rest of the session
    from agent_models import builders_for
    built = [("t6-fix T6 builder", "opus"), ("t21-build T21 crawl_check builder", "sonnet"), ("p1 page 1 builder", "sonnet")]
    assert builders_for("T21 independent review", built) == {"sonnet"}
    assert problems([{"name": "r", "description": "T21 independent review", "model": "opus"}],
                    builders=lambda who: builders_for(who, built)) == []
    assert builders_for("T6 review", built) == {"opus"}                        # its own builder was opus: flagged
    assert problems([{"name": "r", "description": "T6 review", "model": "opus"}],
                    builders=lambda who: builders_for(who, built))
    assert builders_for("independent review", built) == {"sonnet"}            # no job named: the latest builder
    assert builders_for("independent review", []) is None


def test_a_helper_stopped_with_taskstop_is_not_judged(tmp_path):
    # friction 51: a wrong-model helper that the session stopped kept failing every stop
    import json as _j
    from agent_models import agent_calls
    def asst(blocks):
        return {"type": "assistant", "message": {"model": "claude-opus-5-5", "content": blocks}}
    def res(uid, aid):
        return {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": uid,
                "content": [{"type": "text", "text": f"Async agent launched successfully.\\nagentId: {aid} (internal ID)"}]}]}}
    rows = [{"type": "user", "message": {"content": "go"}},
            asst([{"type": "tool_use", "id": "u1", "name": "Agent", "input": {"description": "Curia check", "model": "opus"}}]),
            res("u1", "a111"),
            asst([{"type": "tool_use", "id": "u2", "name": "TaskStop", "input": {"task_id": "a111"}}]),
            asst([{"type": "tool_use", "id": "u3", "name": "Agent", "input": {"description": "page 1 researcher: Curia", "model": "sonnet"}}]),
            res("u3", "a222")]
    t = tmp_path / "t.jsonl"
    t.write_text("".join(_j.dumps(r) + "\n" for r in rows))
    calls = agent_calls(t)
    assert [c["description"] for c, _ in calls] == ["page 1 researcher: Curia"]
    assert problems(calls) == []


def test_a_review_wins_over_the_word_fix_but_a_builder_word_wins_over_review():
    assert problems([{"name": "r", "description": "T40 independent review: a2a truth fix", "model": "opus"}]) == []
    assert problems([{"name": "pp-fixer", "description": "Pricing page review fixes builder", "model": "sonnet"}]) == []
    assert problems([{"name": "f", "description": "T41 hero fix", "model": "sonnet"}]) == []
    from agent_models import BUILDER
    import re as _re
    assert not _re.search(BUILDER, "T40 independent review: a2a truth fix")
    assert _re.search(BUILDER, "T41 hero fix")


def test_only_recent_helpers_are_judged(tmp_path):
    import json as _j
    from agent_models import agent_calls
    def asst(ts, desc, model):
        return {"type": "assistant", "timestamp": ts, "message": {"model": "claude-opus-5-5", "content": [
            {"type": "tool_use", "id": desc, "name": "Agent", "input": {"description": desc, "model": model}}]}}
    rows = [{"type": "user", "message": {"content": "go"}},
            asst("2026-11-19T10:00:00Z", "T6 builder", "opus"),          # long ago: judged when it ran
            asst("2026-11-19T22:00:00Z", "T41 builder", "sonnet")]
    t = tmp_path / "t.jsonl"
    t.write_text("".join(_j.dumps(r) + "\n" for r in rows))
    assert [c["description"] for c, _ in agent_calls(t)] == ["T41 builder"]
    assert len(agent_calls(t, recent_only=False)) == 2


def test_a_helper_from_an_earlier_turn_is_not_judged_again(tmp_path):
    # issue #67: a finished wrong-model helper kept blocking every later stop
    import json as _j
    from agent_models import agent_calls
    def asst(desc, model):
        return {"type": "assistant", "timestamp": "2026-11-20T07:00:00Z", "message": {"model": "claude-opus-5-5", "content": [
            {"type": "tool_use", "id": desc, "name": "Agent", "input": {"description": desc, "model": model}}]}}
    rows = [{"type": "user", "message": {"content": "go"}},
            asst("T6 builder", "opus"),                                               # turn 1: wrong model
            {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "T6 builder", "content": "launched"}]}},
            {"type": "user", "message": {"content": "<cross-session-message>next job</cross-session-message>"}},   # turn 2
            asst("T7 builder", "sonnet")]
    t = tmp_path / "t.jsonl"
    t.write_text("".join(_j.dumps(r) + "\n" for r in rows))
    assert [c["description"] for c, _ in agent_calls(t)] == ["T7 builder"]
    assert problems(agent_calls(t)) == []
