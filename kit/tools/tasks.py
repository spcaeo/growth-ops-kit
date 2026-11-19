#!/usr/bin/env python3
"""Task tracker for the growth project.

Data: docs/tasks.json (one file, easy to read, copy and reuse for another project).

  growth tasks list                       # all tasks with status
  growth tasks show T5                    # one task with every step
  growth tasks add "Title" "Owner's words" [--playbook new-post] [--research]   # new task, prints its id; a job with a
                                          # research step is refused until the research browser and Google region are confirmed
  growth tasks add "Title" "Owner's words" [--type chat]   # new task, prints its id (--type chat: a chat that is not page work, needs no steps)
  growth tasks add "Title" "Owner's words" [--type setup]   # the project's setup task
  growth tasks step T5 "What to do" [--status todo|doing|done|blocked] [--output proof]   # default todo; done needs --output
  growth tasks tick T5 3 [--status done] --output "proof"   # update step 3 in place (never re-add it)
  growth tasks status T5 done|doing|blocked|waiting-owner|todo   # done only when every step is done, or with
                                          # --force-reason "why" (logged on the task and shown by the gate)

A proof names something checkable: a file that exists, a commit id, a journal id, a command with its output line
("growth gate page /x -> 0 FAIL"), or a web address. "x", "abc" or "yes" is refused. Files named are stored with their
sha256, and the project's commit at the time is stored on the step (last_checked_commit).
  growth tasks ask "Question for the owner" [--task T5]
  growth tasks answer Q1 "Owner's answer"     # the owner only, in their own terminal (same as growth approve answer)
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import CFG, DOCS, PROJECT, TZ as _TZ  # noqa: E402
import research_gate  # noqa: E402
import checkpoints  # noqa: E402  (the one proof rule)

DATA = DOCS / "tasks.json"  # the project's task list (growth.json: project_docs)
TZ = _TZ  # growth.json timezone
STATUSES = {"todo", "doing", "done", "blocked", "waiting-owner"}


def now() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%d %H:%M %Z")


def load() -> dict:
    return json.loads(DATA.read_text())


def save(db: dict) -> None:
    db["updated"] = now()
    tmp = DATA.with_suffix(".tmp")
    tmp.write_text(json.dumps(db, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(DATA)


def find(db: dict, tid: str) -> dict:
    for t in db["tasks"]:
        if t["id"].lower() == tid.lower():
            return t
    sys.exit(f"No task {tid}")


def head_commit(project=None) -> str | None:
    """The project's current commit (None outside a git repo)."""
    import subprocess
    r = subprocess.run(["git", "-C", str(project or PROJECT), "rev-parse", "HEAD"], capture_output=True, text=True)
    return r.stdout.strip() or None if r.returncode == 0 else None


def checked_commit(step: dict) -> str | None:
    """The commit the project was at when this step's proof was recorded (for workflow.py: work after it is not covered)."""
    return step.get("last_checked_commit")


def _repos() -> list:
    try:
        from config import SITE_REPO
        return [SITE_REPO] if Path(SITE_REPO).is_dir() else []
    except Exception:  # noqa: BLE001
        return []


def check_proof(output: str) -> dict:
    """The proof's checkable references, or exit with what is wrong (audit H1)."""
    why = checkpoints.proof_problem(output, PROJECT, _repos())
    if why:
        sys.exit("refused: " + why)
    refs = checkpoints.proof_refs(output, PROJECT, _repos())
    return {"files": [{"path": f, "sha256": h} for f, h in refs["file"]], "commits": refs["commit"], "journal": refs["journal"],
            "urls": refs["url"]}


def set_proof(st: dict, output: str) -> None:
    st["output"] = output
    st["proof_refs"] = check_proof(output)
    st["last_checked_commit"] = head_commit()


def opt(args: list, name: str, default=None):
    if name in args:
        i = args.index(name)
        val = args[i + 1]
        del args[i : i + 2]
        return val
    return default


def main(argv: list) -> None:
    if not argv or argv[0] in {"-h", "--help"}:
        print(__doc__)
        return
    cmd, args = argv[0], argv[1:]
    db = load()
    if cmd == "list":
        for t in db["tasks"]:
            print(f'{t["id"]:<4} {t["status"]:<14} {t["title"]}')
        open_q = [q for q in db["questions"] if not q.get("answer")]
        if open_q:
            print("\nOpen questions for the owner:")
            for q in open_q:
                print(f'  {q["id"]}: {q["question"]}')
    elif cmd == "show":
        t = find(db, args[0])
        print(f'{t["id"]} [{t["status"]}] {t["title"]}\n  Owner: {t["owner_words"]}')
        for s in t["steps"]:
            out = f' -> {s["output"]}' if s.get("output") else ""
            print(f'  {s["n"]:>2}. [{s["status"]}] {s["at"]}  {s["what"]}{out}')
    elif cmd == "add":
        playbook, research = opt(args, "--playbook"), "--research" in args
        if research:
            args.remove("--research")
        if playbook:
            known = research_gate.playbook_has_research(playbook)
            if known is None:
                sys.exit(f"no playbook '{playbook}' in the kit's book/playbooks/")
            research = research or known
        # a job whose title or owner's words name research is a research job even without --playbook/--research (audit H9)
        research = research or bool(research_gate.RESEARCH_WORDS.search(" ".join(args[:2])))
        blocked = research_gate.problem(PROJECT, CFG) if research else None
        if blocked:
            sys.exit("this job has a research step and may not start yet: " + blocked)
        kind = opt(args, "--type", "page")
        if kind not in {"page", "chat", "setup"}:
            sys.exit(f"--type is page, chat or setup, not {kind}")
        tid = f'T{max((int(t["id"][1:]) for t in db["tasks"]), default=0) + 1}'
        task = {"id": tid, "title": args[0], "owner_words": args[1] if len(args) > 1 else "",
                "status": "doing", "started": now(), "finished": None, "steps": []}
        if kind != "page":
            task["type"] = kind
        db["tasks"].append(task)
        save(db)
        print(tid)
    elif cmd == "step":
        status = opt(args, "--status", "todo")   # a new step is todo: it is done only once it has proof (#24)
        output = opt(args, "--output")
        t = find(db, args[0])
        assert status in STATUSES, status
        if status == "done" and not (output or "").strip():
            sys.exit("a step created as done needs --output with its proof (file, commit or command and result); "
                     "otherwise add it as todo (the default) and tick it later")
        # A step already in the list is ticked with `tick`, never added again: re-adding left the first copy open
        # (once, 30 steps showed "todo" on five finished pages).
        key = re.match(r"\s*((?:Playbook |Pipeline |Part )?step\s*[\d.]+[a-z]?|Part [\d.]+[a-z]?|Pipeline \d+|\d+\.)", args[1], re.I)
        if key:
            same = [x for x in t["steps"] if x["status"] != "done" and x["what"].lower().startswith(key.group(1).lower())]
            if same:
                sys.exit(f"step '{key.group(1)}' is already step {same[0]['n']} ({same[0]['status']}): "
                         f"growth tasks tick {t['id']} {same[0]['n']} --output ...")
        st = {"n": len(t["steps"]) + 1, "what": args[1], "status": status, "at": now(), "output": output}
        if (output or "").strip() and status == "done":
            set_proof(st, output)
        t["steps"].append(st)
        save(db)
    elif cmd == "tick":
        t = find(db, args[0])
        n = int(args[1])
        status = opt(args, "--status", "done")
        assert status in STATUSES, status
        st = next(x for x in t["steps"] if x["n"] == n)
        out = opt(args, "--output")
        if out and status == "done":
            set_proof(st, out)
        elif out:
            st["output"] = out                     # a note on a step that is not done (blocked: why) is not a proof
        elif status == "done" and st.get("output"):
            set_proof(st, st["output"])            # an old proof is held to the same rule when the step is ticked done
        if status == "done" and not st.get("output"):
            sys.exit("a done step needs --output with its proof (file, commit or journal id)")
        st["status"], st["at"] = status, now()
        save(db)
    elif cmd == "status":
        force = opt(args, "--force-reason")
        t = find(db, args[0])
        assert args[1] in STATUSES, args[1]
        open_steps = [x for x in t["steps"] if x.get("status") != "done"]
        if args[1] == "done" and open_steps:
            if len((force or "").strip()) < 10:
                sys.exit(f"{t['id']} has {len(open_steps)} step(s) not done (first: {open_steps[0]['n']}. {open_steps[0]['what'][:60]}); "
                         f"tick them with their proof, or close it anyway with --force-reason \"why\" (logged, and the gate shows it)")
            t.setdefault("forced", []).append({"at": now(), "reason": force.strip(), "open_steps": [x["n"] for x in open_steps]})
            print(f"{t['id']} closed with {len(open_steps)} open step(s); reason logged on the task")
        t["status"] = args[1]
        t["finished"] = now() if args[1] == "done" else None
        save(db)
    elif cmd == "ask":
        task = opt(args, "--task")
        qid = f'Q{len(db["questions"]) + 1}'
        db["questions"].append({"id": qid, "question": args[0], "task": task, "asked": now(), "answer": None})
        save(db)
        print(qid)
    elif cmd == "answer":
        # the owner's answer is the owner's act: typed in their own terminal and logged (growth approve answer)
        import approvals
        approvals.main(["answer", *args])
    else:
        sys.exit(f"Unknown command {cmd}. Try --help.")


if __name__ == "__main__":
    main(sys.argv[1:])
