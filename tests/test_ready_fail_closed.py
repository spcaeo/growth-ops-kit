"""READY means every check ran and passed: it fails closed when the gate does not run to the end (audit C1)."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent.parent / "kit" / "tools"


def gate_out(ptype="post", extra=(), summary=True, drop=()):
    from ready import expected_checks
    ids = sorted(expected_checks(ptype) - set(drop))
    lines = [f"OK   1    [{i}] fine" for i in ids] + list(extra)
    if summary:
        lines += ["", f"Gate: 0 FAIL, 0 WARN, {len(ids)} OK, 0 SKIP ({len(ids)} checks; SKIP = does not apply). PASS."]
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
    assert rdy(0, "Gate: 0 FAIL, 0 WARN, 0 OK, 0 SKIP (0 checks). PASS.") == 1
    assert "0 checks" in capsys.readouterr().out


def test_a_gate_that_leaves_out_a_check_is_not_ready(rdy, capsys):
    assert rdy(0, gate_out(drop=["ev.preflight"])) == 1
    assert "ev.preflight" in capsys.readouterr().out


def test_a_complete_clean_gate_is_ready(rdy, capsys):
    assert rdy(0, gate_out()) == 0
    assert capsys.readouterr().out.startswith("READY /x")
    assert "/x" in rdy.ledger()
