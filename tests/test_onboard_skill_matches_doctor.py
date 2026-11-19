"""The onboard skill must name every step doctor checks and never hard-code how many there are."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = (ROOT / "kit" / "skills" / "onboard" / "SKILL.md").read_text()
DOCTOR = (ROOT / "kit" / "tools" / "doctor.py").read_text()


def doctor_steps():
    return re.findall(r'^\s*row\("(A\d+b?) ', DOCTOR, re.M)


def test_the_skill_table_has_a_row_for_every_doctor_step():
    steps = doctor_steps()
    assert len(steps) >= 12
    table = set(re.findall(r"^\| (A\d+b?) ", SKILL, re.M))
    assert not set(steps) - table, f"doctor steps missing from the onboard skill: {sorted(set(steps) - table)}"


def test_the_skill_does_not_hard_code_a_step_count():
    assert not re.search(r"\b\d{1,2}/\d{1,2}\b", SKILL), "write 'every step OK' (doctor's last line), not a number"


def test_every_growth_command_the_skill_names_exists():
    """Each `growth <tool>` in the onboard skill is a real command."""
    import sys
    sys.path.insert(0, str(ROOT))
    ns = {}
    exec(compile((ROOT / "growth").read_text(), "growth", "exec"), {"__name__": "x", "__file__": str(ROOT / "growth")}, ns)
    known = set(ns["TOOLS"]) | {"help", "setup", "page", "check", "ready", "measure", "status", "doctor", "wizard", "new-project"}
    named = set(re.findall(r"`growth ([a-z][a-z_-]+)", SKILL))
    assert not {n for n in named if n not in known and n.replace("-", "_") not in known}, named - known
