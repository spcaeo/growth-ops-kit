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
