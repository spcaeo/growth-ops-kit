"""kit 3.0 work board: the independent check's corrections (pipeline order, per-project overrides, shelf life, no assumed
ChatGPT, lock status) and the public contract the lanes and the machine runner call."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import board
import kits
import store
from board_helpers import ROOT, growth, make_project, proof_file


def fresh(tmp_path, **cfg):
    project = make_project(tmp_path, **cfg)
    return project, store.Store(project)


def needs_of(ptype):
    return {s["kind"]: s["needs"] for s in kits.pipeline(ptype)}


# -- 1. the order of the line ------------------------------------------------------------------------------------------
def test_the_brief_comes_before_preflight_and_every_review_before_ready():
    for t in ("money", "hub", "post", "core"):
        n = needs_of(t)
        assert "brief" in n["preflight"] and "brief" in n and n["brief"] == ["fold-plan"]
        assert {"shots", "click-test", "review"} <= set(n["ready"])
        assert n["owner-checkin-2"] == ["ready"]
        kinds = list(n)
        assert kinds.index("review") < kinds.index("ready") < kinds.index("owner-checkin-2") < kinds.index("release")
    m = needs_of("money")
    assert {"review", "cross-check", "cro-audit"} <= set(m["ready"])
    assert "owner-checkin-1" in m["build"] and m["owner-checkin-1"] == ["record"]       # asked early, needed by the build
    assert "owner-checkin-1" not in needs_of("hub") and "cro-audit" not in needs_of("hub")
    assert "cross-check" in needs_of("hub") and "cross-check" not in needs_of("post")


def test_the_golden_rule_in_the_line_the_owner_is_not_asked_before_ready(tmp_path):
    _, st = fresh(tmp_path)
    board.add_page("/p", "core", "p", st=st)
    for _ in range(60):
        j = board.claim("x", st=st)
        if j is None:
            break
        assert j["kind"] != "owner-checkin-2"
        board.done(j["id"], "x", "https://example.com/p/%d" % j["id"], st=st)
    kinds = [e["data"]["kind"] for e in reversed(st.events("job-claimed", limit=100))]
    assert kinds.index("review") < kinds.index("ready") and kinds[-1] == "ready"
    assert board.pages_view(st=st)[0]["stage"] == "owner"


# -- 2. per-project overrides ------------------------------------------------------------------------------------------
def test_a_project_can_drop_a_step_and_the_chain_stays_connected(tmp_path):
    _, st = fresh(tmp_path, pipeline_overrides={"drop": ["owner-checkin-1"]})
    r = board.add_page("/p", "money", "p", st=st)
    assert len(r["jobs"]) == 21
    jobs = {j["kind"]: j for j in board.jobs_view(page="/p", st=st)}
    assert "owner-checkin-1" not in jobs
    assert jobs["preflight"]["id"] in jobs["build"]["needs"]                      # (and the record the dropped step needed)
    assert jobs["record"]["id"] in jobs["build"]["needs"] and len(jobs["build"]["needs"]) == 2
    _, st2 = fresh(tmp_path / "b", pipeline_overrides={"drop": ["dossier", "ai-baseline", "figures"]})
    board.add_page("/q", "money", "q", st=st2)
    jobs = {j["kind"]: j for j in board.jobs_view(page="/q", st=st2)}
    assert jobs["record"]["needs"] == [jobs["snapshot"]["id"]]                   # a step that needed a dropped one needs what it needed


def test_a_project_can_change_who_runs_a_step_and_the_lead_is_asked_for_by_name(tmp_path):
    _, st = fresh(tmp_path, pipeline_overrides={"runner": {"owner-checkin-2": "agent:lead"}})
    board.add_page("/p", "core", "p", st=st)
    assert {j["kind"]: j["runner"] for j in board.jobs_view(st=st)}["owner-checkin-2"] == "agent:lead"
    for _ in range(60):                                                          # nothing a worker asks for ever gives it out
        j = board.claim("w", st=st) or board.claim("w", runner="agent", st=st)
        if j is None:
            break
        assert j["kind"] != "owner-checkin-2"
        board.done(j["id"], "w", "https://example.com/p/%d" % j["id"], st=st)
    assert board.claim("w", runner="owner", st=st) is None
    mine = board.claim("lead", runner="agent:lead", st=st)
    assert mine["kind"] == "owner-checkin-2"


def test_a_bad_override_is_refused_with_a_plain_message(tmp_path):
    for bad in ({"drop": ["owner-checkin-9"]}, {"runner": {"build": "robot"}}, {"way": {"build": "fast"}}):
        _, st = fresh(tmp_path / str(len(str(bad))), pipeline_overrides=bad)
        with pytest.raises(KeyError, match="pipeline_overrides"):
            board.add_page("/p", "core", "p", st=st)


# -- 3. shelf life -----------------------------------------------------------------------------------------------------
def _age(st, job_id, days):
    when = (datetime.now(timezone.utc) - timedelta(days=days)).replace(microsecond=0).isoformat()
    st.conn.execute("UPDATE jobs SET status='done', finished=?, proof='x' WHERE id=?", (when, job_id))


def test_use_by_days_follow_the_gates_freshness_rules():
    j = kits.jobs()
    assert {k: j[k].get("use_by_days") for k in ("ai-baseline", "record", "review", "inventory", "link-graph", "dossier")} == \
        {"ai-baseline": 30, "record": 30, "review": 30, "inventory": 7, "link-graph": 8, "dossier": 90}


def test_the_board_shows_how_long_a_result_still_counts_and_refresh_queues_a_new_one(tmp_path):
    project, st = fresh(tmp_path)
    board.add_page("/p", "money", "p", st=st)
    ids = {j["kind"]: j["id"] for j in board.jobs_view(page="/p", st=st)}
    _age(st, ids["snapshot"], 1)
    _age(st, ids["ai-baseline"], 20)
    page = board.pages_view(st=st)[0]
    assert page["shelf"].startswith("ai-baseline expires in 9 days") or page["shelf"].startswith("ai-baseline expires in 10 days")
    assert board.refresh_expiring(st=st) == []                                   # more than 3 days left: nothing yet
    _age(st, ids["ai-baseline"], 28)                                             # 2 days left
    assert "expires in 1 days" in board.pages_view(st=st)[0]["shelf"] or "expires in 2 days" in board.pages_view(st=st)[0]["shelf"]
    made = board.refresh_expiring(st=st)
    assert len(made) == 1 and board.refresh_expiring(st=st) == []                # one open refresh per page and kind
    new = board.jobs_view(kind="ai-baseline", st=st)[1]
    assert new["id"] == made[0] and new["status"] == "queued" and new["needs"] == [] and "refresh" in new["why"]
    assert board.pages_view(st=st)[0]["stage"] == "research"                     # the page's stage ignores the refresh job
    taken = [board.claim("r1", kit="research", runner="agent:research", st=st) for _ in range(3)]   # a researcher takes it like any job
    got = next(j for j in taken if j and j["id"] == made[0])
    board.done(got["id"], "r1", "https://example.com/new-baseline", st=st)
    assert board.refresh_expiring(st=st) == []
    assert board.pages_view(st=st)[0]["shelf"].startswith("ai-baseline expires in 29 days")


def test_claim_refreshes_by_itself_and_ready_waits_for_it(tmp_path):
    _, st = fresh(tmp_path)
    board.add_page("/p", "post", "p", st=st)
    ids = {j["kind"]: j["id"] for j in board.jobs_view(page="/p", st=st)}
    st.conn.execute("UPDATE jobs SET status='done', finished=?, proof='x' WHERE page='/p' AND id < ?", (store.now(), ids["ready"]))
    _age(st, ids["record"], 29)                                                  # the record is a day from its 30
    assert board.claim("m", runner="machine", st=st) is None                    # the claim sweeps first; READY waits for the renewal
    rec = board.jobs_view(kind="record", st=st)
    assert len(rec) == 2 and rec[1]["status"] == "queued" and rec[1]["page"] == "/p"
    got = board.claim("r", runner="agent:research", st=st)
    assert got["kind"] == "record" and got["id"] == rec[1]["id"]
    board.done(got["id"], "r", "https://example.com/record", st=st)
    assert board.claim("m", runner="machine", st=st)["kind"] == "ready"


def test_a_page_that_is_ready_has_no_shelf_life_and_the_refresh_command(tmp_path):
    project, st = fresh(tmp_path)
    board.add_page("/a", "core", "a", st=st)
    board.add_page("/b", "core", "b", st=st)
    a = {j["kind"]: j["id"] for j in board.jobs_view(page="/a", st=st)}
    b = {j["kind"]: j["id"] for j in board.jobs_view(page="/b", st=st)}
    _age(st, a["record"], 28)
    _age(st, b["record"], 28)
    _age(st, b["ready"], 0)                                                      # /b is READY: its results are not renewed
    shelves = {p["path"]: p["shelf"] for p in board.pages_view(st=st)}
    assert "record" in shelves["/a"] and shelves["/b"] == ""
    out = growth(project, "board", "refresh", check=True).stdout
    assert "1 refresh job(s) queued" in out
    assert "record expires in" in growth(project, "board", check=True).stdout


# -- 4. no assumed ChatGPT ---------------------------------------------------------------------------------------------
def test_the_kit_assumes_google_only_and_another_engine_comes_from_the_project(tmp_path):
    assert "chatgpt" not in (ROOT / "kit" / "kits.json").read_text().lower()
    assert kits.jobs()["ai-baseline"]["resource"] == "google" and "Google" in kits.jobs()["ai-baseline"]["what"]
    _, st = fresh(tmp_path, pacers={"answers-b": {"min_s": 5, "max_s": 6, "robot_pause_s": 60}},
                  pipeline_overrides={"resource": {"ai-baseline": "answers-b"}})
    from boardlib import resources
    assert resources.defs(st)["answers-b"]["kind"] == "pacer"
    board.add_page("/p", "money", "p", st=st)
    assert {j["kind"]: j["resource"] for j in board.jobs_view(st=st)}["ai-baseline"] == "answers-b"
    import pace
    assert pace.settings(st, "answers-b")["min_s"] == 5


# -- 5. the public contract of the lanes and the machine runner ---------------------------------------------------------
def test_acquire_release_held_by_hand(tmp_path):
    project, st = fresh(tmp_path, resources={"port": [28440, 28441], "browser": 2})
    a = board.acquire("port", "lane-1", project=project)
    assert set(a) >= {"resource", "slot", "holder", "until"} and a["slot"] == "28440" and a["holder"] == "lane-1"
    again = board.acquire("port", "lane-1", project=project)
    assert again["slot"] == "28440" and again["until"] >= a["until"]              # its own slot back, the lease renewed
    assert board.acquire("port", "lane-2", project=project)["slot"] == "28441"
    assert board.acquire("port", "lane-3", project=project) is None                # none free
    assert board.acquire("browser", "m", project=project)["slot"] == "1"
    assert board.acquire("shared-code", "builder", project=project)["slot"] == "lock"
    assert board.acquire("shared-code", "other", project=project) is None
    assert {(h["resource"], h["holder"]) for h in board.held(project=project)} == \
        {("port", "lane-1"), ("port", "lane-2"), ("browser", "m"), ("shared-code", "builder")}
    assert [h["holder"] for h in board.held("shared-code", project=project)] == ["builder"]
    assert board.release("port", "lane-1", project=project) is True and board.release("port", "lane-1", project=project) is False
    assert board.acquire("port", "lane-3", project=project)["slot"] == "28440"
    with pytest.raises(KeyError):
        board.acquire("google", "x", project=project)                              # a pacer is not held
    st.conn.execute("UPDATE leases SET until='2000-01-01T00:00:00+00:00' WHERE holder='builder'")
    assert board.acquire("shared-code", "other", project=project)["holder"] == "other"   # an expired lease is freed


def test_claim_gives_the_page_and_the_slot_and_the_job_calls_take_a_project(tmp_path):
    project, st = fresh(tmp_path)
    board.add_page("/pricing", "core", "pricing", cluster="money", st=st)
    j = board.claim("lead", runner="machine", project=project)
    assert (j["path"], j["key"], j["type"]) == ("/pricing", "pricing", "core")
    assert board.beat(j["id"], "lead", project=project) is True
    assert board.done(j["id"], "lead", "https://example.com/snap", project=project)["status"] == "done"
    for _ in range(40):
        b = board.claim("lane", project=project)
        if b["kind"] == "build":
            break
        board.done(b["id"], "lane", "https://example.com/%d" % b["id"], project=project)
    assert b["kind"] == "build" and b["port"] and b["resource_slot"] == str(b["port"])
    assert board.fail(b["id"], "lane", "the build broke", project=project)["status"] == "queued"


def test_lock_status(tmp_path):
    project, _ = fresh(tmp_path)
    assert "shared-code: free" in growth(project, "lock", "status", check=True).stdout
    growth(project, "lock", "shared-code", "--agent", "builder-2", check=True)
    out = growth(project, "lock", "status", check=True).stdout
    assert "shared-code: held by builder-2" in out and "owner-preview: free" in out


def test_claim_can_be_limited_to_some_job_kinds(tmp_path):
    project, st = fresh(tmp_path)
    board.add_page("/p", "core", "p", st=st)
    assert board.claim("m", kinds=["shots", "click-test"], st=st) is None          # not ready yet: nothing of those kinds
    snap = board.claim("m", kinds=["snapshot"], st=st)
    assert snap["kind"] == "snapshot"
    board.done(snap["id"], "m", "https://example.com/s", st=st)
    assert board.claim("m", kinds=["snapshot", "preflight"], st=st) is None        # record is ready, but it is not asked for
    assert board.claim("m", kinds=["record"], st=st)["kind"] == "record"
    r = growth(project, "work", "next", "--agent", "m", "--kinds", "shots,click-test")
    assert r.returncode == 3
