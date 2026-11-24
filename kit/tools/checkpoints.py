#!/usr/bin/env python3
"""The page's checkpoints file (research/<key>-checkpoints.md): write it without losing what the builder ticked, and read
the manual half back.

  growth checkpoints <path-to-checkpoints-file>     # print the manual checks still open (exit 1 while any is)

Two kinds of item:
  generated   - [ ] `ev.review` (rule 109): ...      one gate check; its proof is the gate run, so a tick is optional
  manual      anything else that is a checkbox: the project's own rules (growth.json "checkpoints_extra" names a file
              with one rule per bullet) and any line the builder adds. No gate check runs them, so each one must be
              ticked with its proof after " -- ":   - [x] rule 530: click test -- J0028, 53/53 clicked
              The proof must name something checkable: a file that exists, a commit, a journal id, a command with its
              output line, or a web address ("x", "abc", "yes" are refused).
`growth ready` fails while a manual item is unticked or ticked with no proof. `growth preflight` merges into the file
instead of rewriting it: ticks, proofs, hand-added items and project sections stay, new generated items are added and a
generated item that left the scope moves to "Removed from scope" (kept for the record, never counted).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

GEN_HEADS = ("1. Before the build", "2. After EVERY fold", "3. Before READY", "4. After publishing")
MANUAL_HEAD = "5. Manual checks"
REMOVED_HEAD = "Removed from scope"
ITEM = re.compile(r"^- \[([ xX])\] (.*)$")
GEN_ITEM = re.compile(r"^`([\w.\-]+)`")
SEP = re.compile(r"\s(?:--|—)\s")
WEAK = {"", "proof", "todo", "tbd", "done", "ok", "..."}

# ---- what counts as proof (tasks, checkpoints, the gate: one rule) ------------------------------------------------------
# A proof names something a person can check: a file that exists, a commit that exists, a journal entry that exists, a
# command with its output line, or a web address. "x", "abc", "yes" and "done" are not proof (audit H1).
PROOF_MIN = 4
URL_RE = re.compile(r"https?://[^\s)>\]]+")
# "rules 18, 32a, 36b re-read": a list of three or more rule ids is the proof of a re-read-checkpoints step (issue #25)
RULES_RE = re.compile(r"(?i)\brules?\s+(\d+[a-z]?(?:\s*(?:,|and)\s*\d+[a-z]?){2,})")
JOURNAL_RE = re.compile(r"\bJ-?\d{1,6}\b")
COMMIT_RE = re.compile(r"(?<![\w/.-])[0-9a-f]{7,40}(?![\w/.-])")
FILE_RE = re.compile(r"(?<![\w:/])(?:~?/|\./)?(?:[\w.@+-]+/)*[\w@+-][\w.@+-]*\.[A-Za-z0-9]{1,8}(?![\w/])")
CMD_RE = re.compile(r"(?:`[^`]{3,}`|\b(?:growth|git|npm|npx|pnpm|yarn|pytest|python3?|node|curl|make|lighthouse|playwright)\s+\S[^\n]*?)"
                    r"\s*(?:->|=>|→|:|\bgave\b|\bprints?\b|\breturned\b)\s*\S")


def _git_has(repo, sha):
    import subprocess
    try:
        return subprocess.run(["git", "-C", str(repo), "cat-file", "-e", f"{sha}^{{commit}}"], capture_output=True, timeout=10).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _git_blob(repo, sha, path):
    """The bytes of `path` as committed in `sha` of `repo`, or None (no such file there, or not a path in that repo)."""
    import subprocess
    p = Path(path).expanduser()
    if p.is_absolute():
        try:
            p = p.resolve().relative_to(Path(repo).resolve())
        except ValueError:
            return None
    try:
        r = subprocess.run(["git", "-C", str(repo), "show", f"{sha}:{p.as_posix()}"], capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def _journal_ids(project):
    import json
    try:
        return {json.loads(l).get("id") for l in (Path(project) / "journal" / "entries.jsonl").read_text().splitlines() if l.strip()}
    except (OSError, ValueError):
        return set()


def proof_refs(text, project=None, repos=()):
    """What the proof names that exists: {"file": [(path, sha256)], "commit": [...], "journal": [...], "url": [...],
    "command": [...]}. Without a project, a file, commit or journal id counts by its shape alone."""
    import hashlib
    text = str(text or "")
    out = {"url": URL_RE.findall(text), "command": [m.group(0) for m in CMD_RE.finditer(text)], "file": [], "commit": [], "journal": [],
           "rules": [re.sub(r"\s+", " ", m.group(1)) for m in RULES_RE.finditer(text)]}
    bare = URL_RE.sub(" ", text)
    roots = [Path(r) for r in ((project,) if project else ()) + tuple(repos or ()) if r]
    jids = _journal_ids(project) if project else None
    for j in JOURNAL_RE.findall(bare):
        if jids is None or j in jids:
            out["journal"].append(j)
    for sha in COMMIT_RE.findall(bare):
        if roots and any(_git_has(r, sha) for r in roots):
            out["commit"].append(sha)
        elif not roots and re.search(r"\d", sha) and re.search(r"[a-f]", sha):   # by shape: digits and letters
            out["commit"].append(sha)
    # a proof that names a commit is about the files AS IN THAT COMMIT: work is done in a worktree on a branch, and the
    # main checkout still holds the old file (issue #66). Hash from the commit where the file exists there.
    in_commit = [(r, sha) for sha in out["commit"] for r in roots if _git_has(r, sha)]
    for f in FILE_RE.findall(bare):
        if re.fullmatch(r"\d+(\.\d+)+", f):          # 1.5, 53.0: a number, not a file
            continue
        if not roots:
            out["file"].append((f, ""))
            continue
        blob = next((b for b in (_git_blob(r, sha, f) for r, sha in in_commit) if b is not None), None)
        if blob is not None:
            out["file"].append((f, hashlib.sha256(blob).hexdigest()))
            continue
        for r in roots:
            cand = Path(f).expanduser()
            cand = cand if cand.is_absolute() else r / cand
            if cand.is_file():
                out["file"].append((f, hashlib.sha256(cand.read_bytes()).hexdigest()))
                break
    return out


KIT_ROOT = Path(__file__).resolve().parents[2]


def outside_files(text, project=None, repos=()):
    """Absolute file paths the proof names that sit outside the project, the site repos and the kit (a scratchpad, /tmp,
    a home folder). Such a file is not proof: scratch folders are cleaned, and the proof then points at nothing (2.8.0;
    from a real project: a clean-up of the scratchpad broke the ticks of a dozen finished pages)."""
    if not project:
        return []
    roots = [Path(r).expanduser().resolve() for r in ((project,) + tuple(repos or ())) if r] + [KIT_ROOT]
    bare = URL_RE.sub(" ", str(text or ""))
    out = []
    disk = ("/Users/", "/home/", "/private/", "/tmp/", "/var/", "/Volumes/", "/opt/", "/root/")
    for f in FILE_RE.findall(bare):
        cand = Path(f).expanduser()
        if not cand.is_absolute():
            if ".." not in cand.parts:
                continue
            cand = Path(project).expanduser() / cand   # ../scratch/notes.md climbs out of the project
        elif not cand.exists() and not str(cand).startswith(disk) and not f.startswith("~"):
            continue   # "/pricing/index.html in dist" is a site path, not a file on this machine
        try:
            rc = cand.resolve()
        except OSError:
            rc = cand
        if not any(rc == r or r in rc.parents for r in roots):
            out.append(f)
    return out


def proof_problem(text, project=None, repos=()):
    """None when `text` is meaningful proof; else what is wrong, in plain words."""
    t = str(text or "").strip()
    if t.lower() in WEAK or len(t) < PROOF_MIN:
        return (f"'{t}' is not proof: name what you checked (a file, a commit, a journal id, a command with its output "
                "line, or a web address)")
    away = outside_files(t, project, repos)
    if away:
        return (f"'{away[0][:70]}' is outside the project: proof must live in the project (research/, journal/), the site "
                "repo or the kit; copy the file into research/ and name that copy, or name the commit or journal id instead")
    refs = proof_refs(t, project, repos)
    if any(refs.values()):
        return None
    hint = " (it names a file, commit or journal id that does not exist)" if project and (
        FILE_RE.search(t) or COMMIT_RE.search(t) or JOURNAL_RE.search(t)) else ""
    return (f"'{t[:60]}' names nothing checkable{hint}: give a file that exists, a commit id, a journal id, a command with "
            "its output line (growth gate page /x -> 0 FAIL), a web address, or the rule ids you re-read (rules 18, 32a, 36b)")


def split_proof(text):
    """(rule text, proof) of an item: the proof follows the first ' -- '."""
    m = SEP.search(text)
    return (text[:m.start()].strip(), text[m.end():].strip()) if m else (text.strip(), "")


def sections(text):
    """[(heading or None, [lines])]: the lines before the first '## ' have heading None."""
    out = [(None, [])]
    for ln in text.splitlines():
        if ln.startswith("## "):
            out.append((ln[3:].strip(), []))
        else:
            out[-1][1].append(ln)
    return out


def kind_of(heading):
    h = re.sub(r"\s*\(\d+\)\s*$", "", heading or "")
    if h.startswith(GEN_HEADS):
        return "generated"
    if h.startswith(MANUAL_HEAD):
        return "manual"
    if h.startswith(REMOVED_HEAD):
        return "removed"
    return "other"


def extra_items(path):
    """The project's own rules: one per bullet of the checkpoints_extra file (a checkbox or its proof is ignored)."""
    out = []
    for ln in Path(path).read_text().splitlines():
        m = re.match(r"^\s*[-*]\s+(?:\[[ xX]\]\s+)?(.+)$", ln)
        if m and split_proof(m.group(1))[0]:
            out.append(split_proof(m.group(1))[0])
    return out


def merge(old, gen, extra, header, today):
    """The new file text. gen: [(heading, [(cid, line_without_tick)])]; extra: rule texts; old: the previous file text."""
    secs = sections(old) if old else [(None, [])]
    old_gen, old_manual, removed, keep_other, added = {}, {}, [], [], {}
    for head, lines in secs[1:]:
        k = kind_of(head)
        for ln in lines:
            m = ITEM.match(ln)
            if k in ("generated", "manual") and m:
                g = GEN_ITEM.match(m.group(2))
                if g and k == "generated":
                    old_gen[g.group(1)] = (m.group(1), split_proof(m.group(2))[1])
                else:
                    (old_manual if k == "manual" else added.setdefault(head, {}))[split_proof(m.group(2))[0]] = ln
            elif k == "removed" and ln.startswith("- "):
                removed.append(ln)
        if k == "other":
            keep_other.append((head, lines))
    out = [header, ""]
    live = set()
    for head, items in gen:
        out += [f"## {head} ({len(items)})", ""]
        for cid, line in items:
            live.add(cid)
            tick, proof = old_gen.get(cid, (" ", ""))
            out.append(f"- [{tick}] {line}" + (f" -- {proof}" if proof else ""))
        base = re.sub(r"\s*\(\d+\)\s*$", "", head)
        for text, ln in next((v for k, v in added.items() if re.sub(r"\s*\(\d+\)\s*$", "", k) == base), {}).items():
            out.append(ln)                       # a manual line the builder added inside a generated section
        out.append("")
    for cid, (tick, proof) in sorted(old_gen.items()):
        if cid not in live:
            removed.append(f"- `{cid}` left the scope on {today}" + (f" (it was ticked: {proof})" if tick != " " and proof else ""))
    manual = dict(old_manual)
    for t in extra:
        manual.setdefault(t, f"- [ ] {t}")
    if manual:
        out += [f"## {MANUAL_HEAD} ({len(manual)}): tick each with its proof after ' -- ', e.g. '- [x] rule 530: click test -- J0028, 53/53'", ""]
        out += list(manual.values()) + [""]
    for head, lines in keep_other:
        out += [f"## {head}"] + lines
        if lines and lines[-1].strip():
            out.append("")
    if removed:
        out += [f"## {REMOVED_HEAD}", ""] + list(dict.fromkeys(removed)) + [""]
    return "\n".join(out).rstrip("\n") + "\n"


def manual_status(text, project=None, repos=()):
    """(total, done, problems): every manual checkbox item must be ticked with a proof that names something checkable
    (proof_problem). With a project, files, commits and journal ids must also exist."""
    total = done = 0
    probs = []
    for head, lines in sections(text)[1:]:
        k = kind_of(head)
        if k == "removed":
            continue
        head_name = re.sub(r'\s*\(\d+\)\s*$', '', head or '')[:40]
        stage = f" [stage: {head_name}]"     # which stage the item belongs to (issue #25)
        for ln in lines:
            m = ITEM.match(ln)
            if not m or (k == "generated" and GEN_ITEM.match(m.group(2))):
                continue
            total += 1
            rule, proof = split_proof(m.group(2))
            if m.group(1) == " ":
                probs.append(f"unticked: {rule[:140]}{stage}")
            elif proof.lower() in WEAK or len(proof) < 3:
                probs.append(f"ticked with no proof (add ' -- <what you saw>'): {rule[:120]}{stage}")
            elif proof_problem(proof, project, repos):
                probs.append(f"ticked with a proof that names nothing checkable ({proof_problem(proof, project, repos)[:120]}): {rule[:100]}{stage}")
            else:
                done += 1
    return total, done, probs


def missing_extra(text, extra):
    """Rules of the project's checkpoints_extra file that are not in the checkpoints file at all (deleting a manual item
    must not make it pass). READY calls this with checkpoints.extra_items(<the file growth.json names>)."""
    have = {split_proof(ITEM.match(ln).group(2))[0] for ln in text.splitlines() if ITEM.match(ln)}
    return [f"missing from the checkpoints file: {r[:140]}" for r in extra if r not in have]


def project_of(path):
    """The project folder above a checkpoints file (the nearest folder holding growth.json), or None."""
    for d in Path(path).resolve().parents:
        if (d / "growth.json").is_file():
            return d
    return None


def main():
    if len(sys.argv) != 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    total, done, probs = manual_status(Path(sys.argv[1]).read_text(), project_of(sys.argv[1]))
    print(f"manual checks {done}/{total}")
    for p in probs:
        print("  " + p)
    return 1 if probs else 0


if __name__ == "__main__":
    sys.exit(main())
