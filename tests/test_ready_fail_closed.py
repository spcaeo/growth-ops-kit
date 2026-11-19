"""READY means every check ran and passed: it fails closed when the gate does not run to the end (audit C1)."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent.parent / "kit" / "tools"


def gate_out(ptype="post", extra=(), summary=True, drop=(), blocked=0):
    from ready import expected_checks
    ids = sorted(expected_checks(ptype) - set(drop))
    lines = [f"OK   1    [{i}] fine" for i in ids] + list(extra)
    if summary:
        lines += ["", f"Gate: 0 FAIL, 0 WARN, {len(ids)} OK, 0 SKIP, {blocked} BLOCKED-SKIP ({len(ids)} checks; SKIP = does not apply). PASS."]
    return "\n".join(lines)


@pytest.fixture
def rdy(demo_project, monkeypatch):
    monkeypatch.setenv("GROWTH_PROJECT", str(demo_project))
    sys.path.insert(0, str(TOOLS))
    import ready
    (demo_project / "journal").mkdir(exist_ok=True)
    monkeypatch.setattr(ready, "PROJECT", demo_project)
    monkeypatch.setattr(ready, "LEDGER", demo_project / "journal" / "ready.json")
    monkeypatch.setattr(ready, "CFG", {"preview_url": "http://127.0.0.1:9"})
    monkeypatch.setattr(ready, "preview_repo", lambda: None)

    def go(code, out="", err="", monkey=monkeypatch):
        monkey.setattr(ready, "run_gate", lambda cmd: subprocess.CompletedProcess(cmd, code, out, err))
        monkey.setattr(sys, "argv", ["ready", "/x", "--type", "post", "--key", "x"])
        try:
            ready.main()
            return 0
        except SystemExit as e:
            return e.code
    go.ledger = lambda: json.loads(ready.LEDGER.read_text()) if ready.LEDGER.exists() else {}
    return go


def test_a_refusing_gate_is_not_ready(rdy, capsys):
    assert rdy(2, "", "Refusing to run the gate against the live site: pass a local URL.") == 1
    out = capsys.readouterr().out
    assert out.startswith("NOT READY") and "gate did not complete (exit code 2)" in out
    assert "/x" not in rdy.ledger()


def test_a_crashing_gate_is_not_ready(rdy, capsys):
    assert rdy(1, "", "Traceback (most recent call last):\nImportError: no module named x") == 1
    assert "gate did not complete" in capsys.readouterr().out and rdy.ledger() == {}


def test_a_gate_with_no_summary_line_is_not_ready(rdy, capsys):
    assert rdy(0, gate_out(summary=False)) == 1
    assert "'Gate:' summary line" in capsys.readouterr().out


def test_a_gate_that_ran_zero_checks_is_not_ready(rdy, capsys):
    assert rdy(0, "Gate: 0 FAIL, 0 WARN, 0 OK, 0 SKIP, 0 BLOCKED-SKIP (0 checks). PASS.") == 1
    assert "0 checks" in capsys.readouterr().out


def test_a_gate_that_leaves_out_a_check_is_not_ready(rdy, capsys):
    assert rdy(0, gate_out(drop=["ev.preflight"])) == 1
    assert "ev.preflight" in capsys.readouterr().out


def test_a_complete_clean_gate_is_ready(rdy, capsys):
    assert rdy(0, gate_out()) == 0
    assert capsys.readouterr().out.startswith("READY /x")
    assert "/x" in rdy.ledger()


def test_a_check_that_applies_but_could_not_run_blocks_ready(rdy, capsys):
    assert rdy(0, gate_out(drop=["ui.phone"], blocked=1, extra=["BLOCKED-SKIP ui.phone: no headless browser installed"])) == 1
    out = capsys.readouterr().out
    assert "could not run (ui.phone)" in out and rdy.ledger() == {}


def test_a_plain_skip_for_another_stack_does_not_block_ready(rdy, capsys):
    assert rdy(0, gate_out(drop=["ui.phone"], extra=["SKIP ui.phone: no adapter for static (this check reads nextjs code)"])) == 0


def test_the_gate_prints_blocked_skips_apart_from_plain_skips(capsys):
    import gate
    from gatelib.core import Check, Ctx, Skip, run_check
    ctx = Ctx(project=Path("."))

    def boom(c):
        raise Skip("no headless browser installed", blocked=True)

    def na(c):
        raise Skip("feature off")
    run_check(ctx, Check("t.blocked", "1", ("post",), "w", boom, "x.py"))
    run_check(ctx, Check("t.na", "1", ("post",), "w", na, "x.py"))
    gate.print_lines(ctx, "t")
    out = capsys.readouterr().out
    assert "BLOCKED-SKIP t.blocked: no headless" in out and "\nSKIP t.na: feature off" in out
    assert "0 FAIL, 0 WARN, 0 OK, 1 SKIP, 1 BLOCKED-SKIP" in out


# ---- audit H3: the key is bound to the path, research files match exactly ----

def test_two_different_paths_never_share_a_default_key():
    import gate
    import page_archive
    assert gate.default_key("/blog/pricing-guide") != gate.default_key("/blog/pricing-tips")
    assert gate.default_key("/a/b-c") != gate.default_key("/a-b/c")
    assert page_archive.slug_of("/a/b-c") != page_archive.slug_of("/a-b/c")


def research_ctx(tmp_path, key, names):
    from gatelib.core import Ctx
    (tmp_path / "research").mkdir()
    for n in names:
        (tmp_path / "research" / n).write_text("x\n")
    return Ctx(project=tmp_path, key=key)


def test_research_files_match_the_key_exactly_not_by_substring(tmp_path):
    ctx = research_ctx(tmp_path, "pricing", ["enterprise-pricing-review-2026-11-19.md", "pricing-guide-review-2026-11-19.md",
                                            "pricing-review-2026-11-19.md", "pricing-opus-review-2026-11-19.md"])
    (tmp_path / "journal").mkdir()
    (tmp_path / "journal" / "preflight.json").write_text(json.dumps({"/pricing": {"key": "pricing"}, "/pricing-guide": {"key": "pricing-guide"}}))
    got = [f.name for f in ctx.research(r"-(audit|review)-.*\d{4}-\d\d-\d\d")]
    assert got == ["pricing-opus-review-2026-11-19.md", "pricing-review-2026-11-19.md"]


def test_ready_refuses_a_different_key_than_the_one_the_page_was_preflighted_with(rdy, demo_project, capsys):
    (demo_project / "journal" / "preflight.json").write_text(json.dumps({"/x": {"ok": True, "key": "other-page"}}))
    assert rdy(0, gate_out()) == 1
    out = capsys.readouterr().out
    assert "pre-flighted with key 'other-page', not 'x'" in out and rdy.ledger() == {}


def test_ready_accepts_the_preflight_key(rdy, demo_project, capsys):
    (demo_project / "journal" / "preflight.json").write_text(json.dumps({"/x": {"ok": True, "key": "x"}}))
    assert rdy(0, gate_out()) == 0


def test_a_preflight_record_with_no_key_is_refused(rdy, demo_project, capsys):
    (demo_project / "journal" / "preflight.json").write_text(json.dumps({"/x": {"ok": True}}))
    assert rdy(0, gate_out()) == 1
    assert "did not record a page key" in capsys.readouterr().out


# ---- audit M2: READY looks at the status of every internal link ----

def test_ready_runs_the_gate_with_link_status_on(rdy, monkeypatch):
    import ready
    seen = []
    monkeypatch.setattr(ready, "run_gate", lambda cmd: seen.append(cmd) or subprocess.CompletedProcess(cmd, 0, gate_out(), ""))
    monkeypatch.setattr(sys, "argv", ["ready", "/x", "--type", "post", "--key", "x"])
    ready.main()
    assert seen and "--no-link-status" not in seen[0]


def seo_all(cache, **cfg):
    from gatelib.core import CHECKS, Ctx, run_check
    from techseo.report import Result
    ctx = Ctx(project=Path("."), cfg=cfg, ptype="post")
    ctx.cache.update(cache)
    ctx.cache["tseo"] = cache["tseo"]
    run_check(ctx, CHECKS["seo.all"])
    return ctx.lines[0]


def test_a_skipped_link_status_blocks_when_it_was_asked_for():
    from techseo.report import Result
    line = seo_all({"tseo": [Result("LNK-02", "SKIP", "live site: links are not fetched")]})
    assert line.level == "SKIP" and line.blocked
    line = seo_all({"tseo": [Result("LNK-02", "SKIP", "switched off")], "no_link_status": True})
    assert line.level == "OK" and not line.blocked


def test_the_link_status_count_is_part_of_the_ok_line():
    from techseo.report import Result
    line = seo_all({"tseo": [Result("LNK-02", "OK", "all 3 unique internal targets answer 200 (3 of 3 unique internal targets checked)")]})
    assert line.level == "OK" and "3 of 3 unique internal targets checked" in line.what


def test_ready_asks_a_trailing_slash_site_for_the_slash_form(rdy, monkeypatch):
    import ready
    seen = []
    monkeypatch.setattr(ready, "run_gate", lambda cmd: seen.append(cmd) or subprocess.CompletedProcess(cmd, 0, gate_out(), ""))
    for cfg, typed, want in (({"trailing_slash": True}, "/x", "/x/"), ({}, "/x/", "/x/"), ({}, "/x", "/x"),
                             ({"trailing_slash": False}, "/x/", "/x"), ({"trailing_slash": True}, "/feed.xml", "/feed.xml")):
        monkeypatch.setattr(ready, "CFG", {"preview_url": "http://127.0.0.1:9", **cfg})
        monkeypatch.setattr(sys, "argv", ["ready", typed, "--type", "post", "--key", "x"])
        seen.clear()
        ready.main()
        cmd = seen[0]
        assert cmd[cmd.index("--url") + 1] == "http://127.0.0.1:9" + want, (cfg, typed)
        assert cmd[cmd.index("page") + 1] == typed.rstrip("/")          # the page key stays without the slash
