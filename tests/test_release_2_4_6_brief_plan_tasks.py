"""2.4.6: an owner question ("(no new rule)") does not make briefs stale; short true fold-plan answers count;
fold_plan --folds wins over an unbuilt --url; `tasks <cmd> --help` never runs the command."""
import subprocess
import sys
from pathlib import Path

from gatelib import CHECKS
from gatelib.c_plan import answered
from gatelib.core import Ctx, run_check

ROOT = Path(__file__).resolve().parent.parent
HEAD = "| ID | Date | What the owner said | What was done | Where |\n"


def brief_line(tmp_path, rows, brief_ids):
    (tmp_path / "docs").mkdir(exist_ok=True)
    (tmp_path / "docs" / "steps-log.md").write_text(HEAD + "".join(rows))
    (tmp_path / "research" / "briefs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "research" / "briefs" / "pg.md").write_text("".join(f"| I-{i} | ... |\n" for i in brief_ids))
    c = Ctx(project=tmp_path, path="/pg/", key="pg", ptype="core", cfg={}, html="", url="", status=200, docs=tmp_path / "docs")
    run_check(c, CHECKS["ev.brief"])
    return c.lines[-1]


def test_a_question_does_not_make_the_brief_stale(tmp_path):
    rows = ['| I-1 | 2026-11-22 | "use X" | Set rule X. | BRAND |\n',
            '| I-2 | 2026-11-22 | "what changes ?" | A question to the lead (no new rule). | lead |\n']
    assert brief_line(tmp_path, rows, [1]).level == "OK"


def test_a_new_rule_makes_the_brief_stale(tmp_path):
    rows = ['| I-1 | 2026-11-22 | "use X" | Set rule X. | BRAND |\n', '| I-2 | 2026-11-22 | "use Y" | Set rule Y. | BRAND |\n']
    ln = brief_line(tmp_path, rows, [1])
    assert ln.level == "FAIL" and "I-2" in ln.what


def test_short_true_answers_count():
    assert answered("plain") and answered("sage tint") and answered("n/a: no tool here")
    assert not any(answered(x) for x in ("", "tbd", "?", "-", "same", "n/a", "see above"))


def test_tasks_help_runs_nothing(tmp_path):
    (tmp_path / "growth.json").write_text("{}")
    (tmp_path / "docs").mkdir()
    r = subprocess.run([sys.executable, str(ROOT / "kit" / "tools" / "tasks.py"), "add", "--help"], capture_output=True, text=True,
                       env={"GROWTH_PROJECT": str(tmp_path), "PATH": "/usr/bin:/bin"})
    assert r.returncode == 0 and not (tmp_path / "docs" / "tasks.json").exists()
