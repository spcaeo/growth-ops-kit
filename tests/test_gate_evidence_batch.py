"""Gate and evidence fixes: findings stay open until closed (#48), the review check cannot pass on the checkpoints file
(#49), preview_repo is required when the site has a checkout (#51), small crashes (#52), manual checkpoints (#62)."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "kit" / "tools"


def tool(project, script, *args):
    env = {**os.environ, "GROWTH_PROJECT": str(project), "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run([sys.executable, str(TOOLS / script), *args], capture_output=True, text=True, env=env, cwd=project)


def entries(project):
    return [json.loads(l) for l in (project / "journal" / "entries.jsonl").read_text().splitlines() if l.strip()]


# ---- #48

def test_a_new_finding_starts_open_and_close_needs_output(demo_project):
    r = tool(demo_project, "journal.py", "add", "--page", "/x", "--kind", "finding", "--title", "t")
    assert r.returncode == 0, r.stderr
    fid = r.stdout.split()[0]
    assert [e for e in entries(demo_project) if e["id"] == fid][0]["status"] == "open"
    assert tool(demo_project, "journal.py", "close", fid).returncode != 0            # --output is required
    assert tool(demo_project, "journal.py", "close", fid, "--output", "  ").returncode != 0
    assert "No open" not in tool(demo_project, "journal.py", "open").stdout
    assert tool(demo_project, "journal.py", "close", fid, "--output", "commit abc1234").returncode == 0
    assert entries(demo_project)[-1]["status"] == "done"
    assert "No open" in tool(demo_project, "journal.py", "open").stdout


def test_decisions_and_notes_are_still_filed_done(demo_project):
    r = tool(demo_project, "journal.py", "add", "--page", "/x", "--kind", "decision", "--title", "t")
    assert [e for e in entries(demo_project) if e["id"] == r.stdout.split()[0]][0]["status"] == "done"


def test_stale_open_finding_fails_ev_open_findings():
    import datetime as dt
    from gatelib import CHECKS
    from gatelib.core import Ctx, run_check
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp)
        (p / "journal").mkdir()
        old = (dt.datetime.now() - dt.timedelta(days=10)).strftime("%Y-%m-%d %H:%M UTC")
        (p / "journal/entries.jsonl").write_text(json.dumps({"id": "J0001", "at": old, "pages": ["/x"], "kind": "finding", "status": "open", "tags": []}) + "\n")
        c = Ctx(project=p, path="/x", cfg={})
        run_check(c, CHECKS["ev.open-findings"])
        assert c.lines[0].level == "FAIL"


# ---- #49

def review_ctx(tmp, key, names):
    from gatelib.core import Ctx
    (tmp / "research").mkdir(exist_ok=True)
    for n in names:
        (tmp / "research" / n).write_text("x\n")
    return Ctx(project=tmp, path="/" + key, key=key, cfg={})


def run_review(ctx):
    from gatelib import CHECKS
    from gatelib.core import run_check
    run_check(ctx, CHECKS["ev.review"])
    return ctx.lines[0].level


def test_a_key_containing_review_does_not_pass_on_the_checkpoints_file(tmp_path):
    ctx = review_ctx(tmp_path, "asana-review", ["asana-review-checkpoints.md"])
    assert run_review(ctx) == "FAIL"


def test_a_key_containing_review_does_not_pass_on_another_research_file(tmp_path):
    ctx = review_ctx(tmp_path, "asana-review", ["asana-review-research-check-2026-11-18.md", "asana-review-dossier.md"])
    assert run_review(ctx) == "FAIL"


def test_a_dated_audit_or_review_file_passes(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    assert run_review(review_ctx(tmp_path / "a", "asana-review", ["asana-review-audit-2026-11-18.md"])) == "OK"
    assert run_review(review_ctx(tmp_path / "b", "lawn", ["lawn-opus-review-2026-11-18.md"])) == "OK"


def test_an_undated_review_name_fails(tmp_path):
    assert run_review(review_ctx(tmp_path, "lawn", ["lawn-review.md"])) == "FAIL"


# ---- #51

def set_cfg(project, **kw):
    f = project / "growth.json"
    d = json.loads(f.read_text())
    d.update(kw)
    f.write_text(json.dumps(d))


def test_ready_and_preflight_refuse_a_site_checkout_without_preview_repo(demo_project):
    set_cfg(demo_project, site_repo="../site-main", preview_repo="", preview_url="http://127.0.0.1:9")
    for script, args in (("ready.py", ["/x", "--type", "post", "--key", "x"]), ("preflight.py", ["/x", "--type", "post", "--key", "x"])):
        r = tool(demo_project, script, *args)
        assert r.returncode != 0 and "preview_repo" in r.stderr, (script, r.stderr)


def test_the_preview_repo_problem_clears_when_it_is_set_or_there_is_no_checkout(demo_project, monkeypatch):
    monkeypatch.setenv("GROWTH_PROJECT", str(demo_project))
    sys.path.insert(0, str(TOOLS))
    import ready
    for cfg, bad in (({"site_repo": "../s", "preview_repo": ""}, True), ({"site_repo": "../s", "preview_repo": "../wt"}, False),
                     ({"site_repo": "", "preview_repo": ""}, False)):
        monkeypatch.setattr(ready, "CFG", cfg, raising=False)
        assert bool(ready.preview_repo_problem()) is bad, cfg
# ---- #52

def test_a_bad_recheck_date_is_refused_and_due_never_crashes(demo_project):
    r = tool(demo_project, "journal.py", "add", "--page", "/x", "--kind", "finding", "--title", "t", "--recheck", "2026-13-45")
    assert r.returncode != 0 and "YYYY-MM-DD" in r.stderr
    (demo_project / "journal").mkdir(exist_ok=True)
    with (demo_project / "journal" / "entries.jsonl").open("a") as f:
        f.write(json.dumps({"id": "J0099", "at": "x", "pages": ["/x"], "kind": "finding", "status": "open", "title": "bad", "recheck_on": "soon"}) + "\n")
    r = tool(demo_project, "journal.py", "due")
    assert r.returncode == 0 and "BAD DATE" in r.stderr


def test_a_default_key_has_no_slash():
    import gate
    assert "/" not in gate.default_key("/topic/some-page")
    assert gate.default_key("/topic/some-page") == "topic-some"
    assert gate.default_key("/") == "home"


def test_a_plan_with_zero_folds_does_not_pass():
    from gatelib.c_plan import problems
    plan = {"goal": "A goal that is long enough", "folds": [], "shared": {}}
    assert any("no folds" in p for p in problems(plan, []))


def test_the_books_research_file_name_satisfies_the_fact_check(tmp_path):
    from gatelib import CHECKS
    from gatelib.core import run_check
    ctx = review_ctx(tmp_path, "lawn", ["lawn-research-2026-11-18.md"])
    run_check(ctx, CHECKS["ev.research-check"])
    assert ctx.lines[0].level == "OK", ctx.lines[0].text()
    (tmp_path / "x").mkdir()
    ctx = review_ctx(tmp_path / "x", "my-research", ["my-research-checkpoints.md"])    # a key that contains the word is not evidence
    run_check(ctx, CHECKS["ev.research-check"])
    assert ctx.lines[0].level == "FAIL"


def test_a_new_page_in_new_pages_is_matched_without_the_trailing_slash(tmp_path):
    from gatelib import CHECKS
    from gatelib.core import Ctx, run_check
    ctx = Ctx(project=tmp_path, path="/blog/new", cfg={"new_pages": ["/blog/new/"]})
    run_check(ctx, CHECKS["ev.archive-before"])
    assert ctx.lines[0].level == "OK"


def test_preflight_plan_files_survives_a_project_with_no_journal(demo_project):
    (demo_project / "journal" / "entries.jsonl").unlink(missing_ok=True)
    set_cfg(demo_project, stack="nextjs", preview_url="http://127.0.0.1:9")
    code = ("import sys; sys.path.insert(0, %r); import preflight; print(preflight.plan_files('/x', 'x', 'money'))" % str(TOOLS))
    env = {**os.environ, "GROWTH_PROJECT": str(demo_project)}
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, cwd=demo_project)
    assert r.returncode == 0, r.stderr
    assert "links.plan" in r.stdout          # reported as a missing plan, not a crash


# ---- #62

GEN = [("1. Before the build (x)", [("ev.a", "`ev.a` (rule 1): a"), ("ev.b", "`ev.b` (rule 2): b")]),
       ("3. Before READY (y)", [("ev.c", "`ev.c` (rule 3): c")])]


def merged(old="", gen=GEN, extra=()):
    import checkpoints
    return checkpoints.merge(old, gen, list(extra), "# Checkpoints: /x", "2026-11-19")


def test_manual_items_need_a_tick_and_a_proof():
    import checkpoints
    text = merged(extra=["rule 530: click test", "rule 31: one verdict"])
    total, done, probs = checkpoints.manual_status(text)
    assert (total, done, len(probs)) == (2, 0, 2)          # generated items are not counted
    text = text.replace("- [ ] rule 530: click test", "- [x] rule 530: click test")
    assert "ticked with no proof" in checkpoints.manual_status(text)[2][0]
    text = text.replace("- [x] rule 530: click test", "- [x] rule 530: click test -- J0028, 53/53")
    assert checkpoints.manual_status(text)[:2] == (2, 1)
    assert checkpoints.manual_status(text.replace("-- J0028, 53/53", "-- todo"))[1] == 0


def test_preflight_merges_keeps_ticks_proofs_and_project_sections():
    first = merged(extra=["rule 530: click test"])
    edited = (first.replace("- [ ] rule 530: click test", "- [x] rule 530: click test -- J0028, 53/53")
              .replace("- [ ] `ev.a`", "- [x] `ev.a`") + "\n## 6. Site rules\n\n- [ ] logo per tool\n- [x] FAQ equals schema -- compared\n")
    gen2 = [("1. Before the build (x)", [("ev.a", "`ev.a` (rule 1): a changed words"), ("ev.d", "`ev.d` (rule 4): new")]),
            ("3. Before READY (y)", [])]
    out = merged(edited, gen2, extra=["rule 530: click test", "rule 99: new rule"])
    assert "- [x] rule 530: click test -- J0028, 53/53" in out          # tick and proof kept
    assert "- [x] `ev.a` (rule 1): a changed words" in out              # generated tick kept, text refreshed
    assert "- [ ] `ev.d`" in out and "- [ ] rule 99: new rule" in out   # new items added
    assert "## 6. Site rules" in out and "- [ ] logo per tool" in out   # project section kept
    assert "`ev.b` left the scope" in out and "`ev.c` left the scope" in out   # removed ones marked, not deleted
    import checkpoints
    assert checkpoints.manual_status(out)[2][0].startswith("unticked")  # the open ones still count, removed ones do not
    assert merged(out, gen2, extra=["rule 530: click test", "rule 99: new rule"]) == out    # a second run changes nothing


def test_ready_lists_open_manual_items_and_passes_when_all_are_proven(demo_project, monkeypatch):
    monkeypatch.setenv("GROWTH_PROJECT", str(demo_project))
    sys.path.insert(0, str(TOOLS))
    import ready
    monkeypatch.setattr(ready, "PROJECT", demo_project)
    (demo_project / "research").mkdir(exist_ok=True)
    plan = demo_project / "research" / "x-checkpoints.md"
    plan.write_text(merged(extra=["rule 530: click test"]))
    assert len(ready.manual_problems("/x", "x")) == 1
    plan.write_text(plan.read_text().replace("- [ ] rule 530: click test", "- [x] rule 530: click test -- J0028, 53/53"))
    assert ready.manual_problems("/x", "x") == []
    plan.unlink()
    assert ready.manual_problems("/x", "x") == []          # no file: ev.preflight is the check that wants it


def test_checkpoints_cli_exits_1_while_a_manual_item_is_open(tmp_path):
    f = tmp_path / "c.md"
    f.write_text(merged(extra=["rule 530: click test"]))
    r = subprocess.run([sys.executable, str(TOOLS / "checkpoints.py"), str(f)], capture_output=True, text=True)
    assert r.returncode == 1 and "manual checks 0/1" in r.stdout
