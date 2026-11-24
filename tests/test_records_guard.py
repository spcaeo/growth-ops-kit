"""kit 3.0 core: the one access layer. No kit module may open the task list, the journal or the verdict files itself: they
live in the project's database and every module reads and writes them through kit/tools/records.py (tasks_doc,
journal_lines, verdicts, ...). The plain files are only mirrors."""
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KIT = ROOT / "kit"

# A string in the code (not a docstring, not a sentence in a message) that names one of the mirrored files, with or without
# a folder in front of it: "tasks.json", "docs/tasks.json", f"{docs}/tasks.json", "/entries.jsonl" ...
MIRRORED = re.compile(r"\S*(tasks\.json|entries\.jsonl|ready\.json|ready-failed\.json|preflight\.json)")

# The only kit files allowed to name a mirrored file, and why.
ALLOWED = {
    "tools/records.py": "the access layer: it is the one place that knows where the mirrors are",
    "tools/harness.py": "the agent's protected-file list (permissions), a list of paths and nothing opened",
    "tools/workflow.py": "BOOKKEEPING: file names that do not count as page work, a list of paths and nothing opened",
}


def named_files(path: Path) -> list:
    """(line, text) for every string constant in the file's code that names a mirrored file."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                docstrings.add(id(first.value))
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
            if MIRRORED.fullmatch(node.value):
                out.append((node.lineno, node.value))
    return out


def kit_files():
    return sorted(p for p in KIT.rglob("*.py") if "__pycache__" not in p.parts)


def test_no_module_opens_a_mirrored_file_itself():
    offenders = []
    for p in kit_files():
        rel = p.relative_to(KIT).as_posix()
        if rel in ALLOWED:
            continue
        for line, text in named_files(p):
            offenders.append(f"{rel}:{line} names {text!r}")
    assert not offenders, ("these modules name a mirrored file: read and write it through records.py instead (tasks_doc, "
                           "tasks_update, journal_lines, journal_add, verdicts, verdicts_update):\n  " + "\n  ".join(offenders))


def test_the_allow_list_is_not_stale():
    for rel in ALLOWED:
        p = KIT / rel
        assert p.exists(), f"{rel} is on the allow-list but does not exist"
        assert named_files(p), f"{rel} is on the allow-list but no longer names a mirrored file: remove it from ALLOWED"


def test_the_guard_sees_a_direct_read():
    sample = ROOT / "tests" / "__guard_sample__.py"
    tree = ast.parse('import json\nx = json.loads((DOCS / "tasks.json").read_text())\ny = f"{docs}/tasks.json"\n"""docstring about tasks.json"""\n')
    found = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and MIRRORED.fullmatch(n.value)]
    assert sorted(found) == ["/tasks.json", "tasks.json"] and not sample.exists()


def test_only_the_access_layer_opens_the_database_tables_of_the_records():
    """The three record tables (tasks, journal, verdicts) are read and written by records.py alone."""
    pat = re.compile(r"\b(FROM|INTO|UPDATE|DELETE FROM)\s+(tasks|task_doc|journal|verdicts)\b", re.I)
    offenders = []
    for p in kit_files():
        rel = p.relative_to(KIT).as_posix()
        if rel == "tools/records.py":
            continue
        for n, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if pat.search(ln) and ("execute" in ln or "q(" in ln or "q1(" in ln):
                offenders.append(f"{rel}:{n}")
    assert not offenders, offenders
