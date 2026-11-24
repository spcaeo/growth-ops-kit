"""kit 3.0 international markets on the work board: a project with two or more locales gets one `localize` job per non-primary
locale (each carrying its locale, each needing the page's READY) and one `intl-check` that needs them all; a one-locale project
gets neither."""
import pytest

import board
import kits
import runner
import store
from board_helpers import growth, make_project
from boardlib import schema as board_schema

FOUR = ["en-US", "en-CA", "fr-CA", "es-US"]


def fresh(tmp_path, locales=None, **cfg):
    market = {"primary_country": "US", "language": "en-US", "google_params": "gl=us&hl=en&pws=0"}
    if locales:
        market["locales"] = locales
    project = make_project(tmp_path, market=market, **cfg)
    return project, store.Store(project)


def kinds(st, page):
    return [(j["kind"], j["locale"]) for j in board.jobs_view(page=page, st=st)]


def test_a_four_locale_project_gets_three_localize_jobs_and_one_check(tmp_path):
    _, st = fresh(tmp_path, FOUR)
    r = board.add_page("/pricing/", "money", "pricing", st=st)
    assert r["created"] and len(r["jobs"]) == 22 + 3 + 1
    got = kinds(st, "/pricing")
    assert [k for k in got if k[0] == "localize"] == [("localize", "en-CA"), ("localize", "fr-CA"), ("localize", "es-US")]
    assert got[-1] == ("intl-check", None) and got[21][0] == "measure"            # after the pipeline, which is unchanged
    again = board.add_page("/pricing", "money", "pricing", st=st)
    assert not again["created"] and again["jobs"] == r["jobs"]                  # a second add makes none


def test_a_one_locale_project_gets_none(tmp_path):
    for locales in (None, ["en-US"]):
        _, st = fresh(tmp_path / str(bool(locales)), locales)
        r = board.add_page("/pricing/", "money", "pricing", st=st)
        assert len(r["jobs"]) == 22
        assert not [k for k in kinds(st, "/pricing") if k[0] in ("localize", "intl-check")]


def test_two_locales_make_one_localize_job_and_every_page_type_gets_them(tmp_path):
    _, st = fresh(tmp_path, ["en-US", "fr-CA"])
    for path, typ in (("/a/", "money"), ("/b/", "hub"), ("/c/", "post"), ("/d/", "core")):
        board.add_page(path, typ, path.strip("/"), st=st)
        assert [k for k in kinds(st, path.rstrip("/")) if k[0] == "localize"] == [("localize", "fr-CA")]


def test_localize_waits_for_ready_and_the_check_waits_for_every_copy(tmp_path):
    _, st = fresh(tmp_path, FOUR)
    board.add_page("/pricing/", "money", "pricing", st=st)
    jobs = {(j["kind"], j["locale"]): j for j in board.jobs_view(page="/pricing", st=st)}
    ready = jobs[("ready", None)]["id"]
    loc_ids = sorted(jobs[("localize", t)]["id"] for t in ("en-CA", "fr-CA", "es-US"))
    assert all(jobs[("localize", t)]["needs"] == [ready] for t in ("en-CA", "fr-CA", "es-US"))
    assert jobs[("intl-check", None)]["needs"] == loc_ids
    assert (jobs[("localize", "fr-CA")]["runner"], jobs[("localize", "fr-CA")]["way"], jobs[("localize", "fr-CA")]["kit"]) == ("agent:build", "page", "build")
    assert (jobs[("intl-check", None)]["runner"], jobs[("intl-check", None)]["way"], jobs[("intl-check", None)]["kit"]) == ("machine", "parallel", "check")
    assert board.claim("b1", kinds=["localize"], st=st) is None                 # READY is not done yet
    with st.tx() as db:
        db.execute("UPDATE jobs SET status='done', finished=? WHERE page='/pricing' AND id <= ?", (store.now(), ready))
    got = board.claim("b1", kinds=["localize"], st=st)
    assert got["kind"] == "localize" and got["locale"] == "en-CA"                # the oldest first; its locale comes with it
    assert board.claim("m1", runner="machine", kinds=["intl-check"], st=st) is None
    for _ in range(2):
        assert board.claim("b2", kinds=["localize"], st=st)["locale"] in ("fr-CA", "es-US")
    assert board.claim("b3", kinds=["localize"], st=st) is None                 # three jobs, three locales, no more
    for jid in loc_ids:
        board.done(jid, None, "https://example.com/copy/%d" % jid, st=st)
    assert board.claim("m1", runner="machine", kinds=["intl-check"], st=st)["kind"] == "intl-check"


def test_a_project_can_drop_the_steps(tmp_path):
    _, st = fresh(tmp_path / "a", FOUR, pipeline_overrides={"drop": ["localize"]})
    board.add_page("/p/", "money", "p", st=st)
    got = kinds(st, "/p")
    assert not [k for k in got if k[0] == "localize"] and ("intl-check", None) in got
    jobs = {j["kind"]: j for j in board.jobs_view(page="/p", st=st)}
    assert jobs["intl-check"]["needs"] == [jobs["ready"]["id"]]
    _, st = fresh(tmp_path / "b", FOUR, pipeline_overrides={"drop": ["localize", "intl-check"]})
    board.add_page("/p/", "money", "p", st=st)
    assert len(board.jobs_view(page="/p", st=st)) == 22


def test_a_bad_locale_list_refuses_the_page_with_the_fix(tmp_path):
    _, st = fresh(tmp_path, ["en-US", {"locale": "fr-CA", "prefix": "/"}])
    with pytest.raises(board.BoardError, match="market.locales in growth.json is not right"):
        board.add_page("/pricing/", "money", "pricing", st=st)
    assert board.pages_view(st=st) == []


def test_the_command_line_shows_the_locale_and_where_its_copy_goes(tmp_path):
    project, st = fresh(tmp_path, FOUR)
    assert growth(project, "board", "add", "/pricing/", "--type", "money", "--key", "pricing").returncode == 0
    out = growth(project, "board", "show", "/pricing").stdout
    assert "localize fr-CA" in out and "localize en-CA" in out and "localize es-US" in out and "intl-check" in out
    with store.Store(project).tx() as db:
        db.execute("UPDATE jobs SET status='done', finished=? WHERE page='/pricing' AND kind NOT IN ('localize', 'intl-check')", (store.now(),))
    r = growth(project, "work", "next", "--kit", "build", "--kinds", "localize", agent="b1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "localize en-CA for /pricing" in r.stdout and "locale: en-CA" in r.stdout and "write the copy at /en-ca/pricing" in r.stdout


def test_an_older_database_gets_the_locale_column(tmp_path):
    project = make_project(tmp_path)
    st = store.Store(project)
    st.ensure(board_schema.NAME, 1, board_schema.DDL.replace(", locale TEXT", ""))        # the database as kit 3.0 first made it
    assert "locale" not in {r[1] for r in st.conn.execute("PRAGMA table_info(jobs)")}
    st.conn.execute("INSERT INTO jobs(kind, kit, way, runner, created) VALUES('inventory','site','ahead','machine','2026-11-24')")
    st.conn.commit()
    st._board_ready = False
    board_schema.ready(st)
    assert "locale" in {r[1] for r in st.conn.execute("PRAGMA table_info(jobs)")}
    assert [j["locale"] for j in board.jobs_view(st=st)] == [None]                      # the old job is kept


def test_the_manifest_knows_both_kinds_and_the_runner_has_a_command_for_the_check():
    j = kits.jobs()
    assert j["localize"]["kit"] == "build" and j["intl-check"]["kit"] == "check"
    assert all(kind not in [s["kind"] for s in kits.pipeline(t)] for t in kits.page_types() for kind in ("localize", "intl-check"))
    cmd = runner.command_for("intl-check", {})
    assert "gate page {path} --url {url}" in cmd and "--only intl.lang,intl.copies" in cmd
    from gatelib import CHECKS
    assert set(runner.INTL_CHECKS) == {c for c in CHECKS if c.startswith("intl.")}

