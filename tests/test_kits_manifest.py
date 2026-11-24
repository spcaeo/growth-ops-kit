"""kit 3.0: the micro-kit manifest (kit/kits.json) names every tool of the dispatcher once and every job kind once."""
import ast
import json
from pathlib import Path

import pytest

import kits

ROOT = Path(__file__).resolve().parent.parent
# tools that are not in the dispatcher's TOOLS dict yet: the work board's commands and the lane and runner of a later piece
NEW_TOOLS = {"store", "board", "work", "pace", "lock", "unlock", "kits", "lane", "runner"}
WAYS = {"ahead", "parallel", "page", "single", "paced", "owner"}


def dispatcher_tools():
    tree = ast.parse((ROOT / "growth").read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "TOOLS" for t in node.targets):
            return {k.value for k in node.value.keys}
    raise AssertionError("no TOOLS dict in growth")


def test_every_dispatcher_tool_is_in_exactly_one_micro_kit():
    owner = {}
    for name, k in kits.kits().items():
        for t in k["tools"]:
            assert t not in owner, f"tool {t} is in both {owner[t]} and {name}"
            owner[t] = name
    missing = dispatcher_tools() - set(owner)
    assert not missing, f"tools in no micro kit: {sorted(missing)}"
    extra = set(owner) - dispatcher_tools() - NEW_TOOLS
    assert not extra, f"manifest tools the dispatcher does not know: {sorted(extra)}"


def test_new_tools_sit_where_the_design_puts_them():
    where = {t: n for n, k in kits.kits().items() for t in k["tools"]}
    for t in ("store", "board", "work", "pace", "lock", "unlock"):
        assert where[t] == "core"
    assert where["lane"] == "build" and where["runner"] == "evidence"


def test_every_job_kind_is_in_exactly_one_kit_and_is_well_formed():
    seen = {}
    res = kits.resources()
    for name, k in kits.kits().items():
        assert k["purpose"].strip()
        for kind, j in k["jobs"].items():
            assert kind not in seen, f"job kind {kind} is in both {seen[kind]} and {name}"
            seen[kind] = name
            assert j["way"] in WAYS and j["way"] in kits.load()["ways"]
            assert j["resource"] in res, f"{kind}: unknown resource {j['resource']}"
            assert j["runner"] in ("machine", "owner") or j["runner"].split(":")[0] == "agent" and j["runner"].split(":")[1] in ("research", "plan", "build", "review")
            assert j["stage"] == "" or j["stage"] in kits.stages()
            assert j["what"].strip()
    assert set(seen) == set(kits.jobs())


def test_the_library_files_exist():
    for name, k in kits.kits().items():
        for lib in k.get("libraries", []):
            assert (ROOT / "kit" / "tools" / f"{lib}.py").is_file() or (ROOT / "kit" / "tools" / lib).is_dir(), lib


@pytest.mark.parametrize("ptype", ["money", "hub", "post", "core"])
def test_pipelines_are_ordered_and_use_known_kinds(ptype):
    line = kits.pipeline(ptype)
    seen = []
    for step in line:
        assert step["kind"] in kits.jobs() and step["kind"] not in seen
        assert all(n in seen for n in step["needs"]), f"{step['kind']} needs a kind that comes later"
        seen.append(step["kind"])
    assert [s["kind"] for s in line][-3:] == ["owner-checkin-2", "release", "measure"]
    stages = [kits.jobs()[s["kind"]]["stage"] for s in line]
    order = [kits.stages().index(s) for s in stages]
    assert order == sorted(order), "a page's stages never go backwards along its line"
    assert load_why(ptype)


def load_why(ptype):
    return kits.load()["pipelines"][ptype].get("_why", "").strip()


def test_money_carries_the_dossier_and_ai_baseline_and_posts_a_lighter_set():
    kinds = {t: [s["kind"] for s in kits.pipeline(t)] for t in ("money", "hub", "post", "core")}
    assert {"dossier", "figures", "ai-baseline"} <= set(kinds["money"])
    assert "ai-baseline" not in kinds["hub"] and "dossier" in kinds["hub"]
    assert "dossier" not in kinds["post"] and "ai-baseline" not in kinds["post"]
    for k in kinds.values():
        assert k[0] == "snapshot" and "record" in k and "build" in k and k[-1] == "measure"


def test_the_activity_map_resources():
    j = kits.jobs()
    assert (j["figures"]["resource"], j["ai-baseline"]["resource"]) == ("google", "google")
    assert j["build"]["resource"] == "port" and j["build"]["runner"] == "agent:build"
    assert (j["shots"]["resource"], j["click-test"]["resource"]) == ("browser", "browser")
    assert j["ready"]["resource"] == "owner-preview" and j["ready"]["runner"] == "machine"
    assert j["plan-review"]["runner"] == "agent:review" and j["preflight"]["runner"] == "machine"
    assert j["owner-checkin-2"]["runner"] == "owner" and j["release"]["way"] == "single"


def test_the_manifest_is_plain_json_and_the_kits_command_prints_it(capsys):
    json.loads((ROOT / "kit" / "kits.json").read_text())
    assert kits.main([]) == 0
    assert "core:" in capsys.readouterr().out
    assert kits.main(["pipelines"]) == 0
    assert "money:" in capsys.readouterr().out
    assert kits.main(["nope"]) == 2
