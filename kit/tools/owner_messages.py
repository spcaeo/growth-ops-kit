#!/usr/bin/env python3
"""Every message the owner typed in this project's Claude sessions, and whether docs/steps-log.md logs it.

The rule: no single comment or piece of feedback may be missed. This reads the session
transcripts (~/.claude/projects/<project>/*.jsonl), keeps only what the owner typed (not tool results, system notes,
teammate messages or pasted blocks alone), and checks each against the steps log. A message counts as logged when
the log quotes it (at least 60% of its words, or its first 8 words in a row, in one log row) or when
docs/owner-messages-map.json names the log row that paraphrases it. Any other message fails the check (exit 1).

  growth owner_messages list          # every owner message, numbered, with time
  growth owner_messages check         # unlogged messages; exit 1 if any
  growth owner_messages check --since 2026-11-17

Exit codes of check: 0 all logged, 1 something is missing, 3 no transcripts were found (nothing was checked).

Short replies that only answer a question (yes, ok, an option label) are listed as "answers" and must appear in the
log row of the question they answer, or in tasks.json; they are reported separately.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import CFG, PROJECT, DOCS  # noqa: E402



def slug(path: Path) -> str:
    """How Claude Code names a folder's transcript directory: every / and _ becomes -, with a leading -."""
    return "-" + str(path).strip("/").replace("/", "-").replace("_", "-")


def transcript_dirs(project: Path = PROJECT, home: Path | None = None, cfg: dict | None = None):
    """The agent's transcript folders for this project: the project's own path (the session started inside it), the
    folder above it (the session started in a workspace that holds it), or growth.json "transcripts_dir"."""
    root = (home or Path.home()) / ".claude" / "projects"
    given = (cfg or {}).get("transcripts_dir")
    cands = [Path(given).expanduser()] if given else [root / slug(project), root / slug(project.parent)]
    return [c for c in cands if c.is_dir()]


LOG = DOCS / "steps-log.md"
MAP = DOCS / "owner-messages-map.json"
SKIP = ("Another Claude session sent a message", "<task-notification", "<teammate-message", "<system-reminder", "<command-name>", "<local-command",
        "Caveat:", "[Request interrupted", "This session is being continued")


def words(t):
    return re.findall(r"[a-z0-9$']+", t.lower())


def owner_messages(since=""):
    out = []
    for f in sorted(p for d in transcript_dirs(cfg=CFG) for p in d.glob("*.jsonl")):
        for line in f.read_text(errors="replace").splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("type") != "user" or e.get("isMeta") or e.get("isSidechain"):
                continue
            c = e.get("message", {}).get("content")
            parts = [c] if isinstance(c, str) else [p.get("text", "") for p in (c or []) if isinstance(p, dict) and p.get("type") == "text"]
            for t in parts:
                t = (t or "").strip()
                if not t or t.startswith(SKIP):
                    continue
                t = re.sub(r"<system-reminder>.*?</system-reminder>", "", t, flags=re.S).strip()
                t = re.sub(r"<pasted_content[^>]*>.*?</pasted_content[^>]*>", "[pasted]", t, flags=re.S).strip()
                if not t or t == "[pasted]":
                    continue
                ts = e.get("timestamp", "")
                if since and ts[:10] < since:
                    continue
                out.append({"at": ts[:16].replace("T", " "), "text": t, "session": f.stem[:8]})
    seen, uniq = set(), []
    for m in out:
        k = m["text"][:200]
        if k not in seen:
            seen.add(k)
            uniq.append(m)
    return uniq


def logged(msg, rows):
    w = words(msg)
    if not w:
        return True
    first = " ".join(w[:8])
    for r in rows:
        rw = words(r)
        rs = " ".join(rw)
        if len(w) >= 8 and first in rs:
            return True
        if len(w) >= 4 and sum(1 for x in set(w) if x in set(rw)) / len(set(w)) >= 0.6:
            return True
    return False


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["list", "check"])
    ap.add_argument("--since", default="")
    a = ap.parse_args()
    msgs = owner_messages(a.since)
    if a.cmd == "check" and not transcript_dirs(cfg=CFG):
        tried = [str(Path.home() / ".claude" / "projects" / slug(PROJECT)), str(Path.home() / ".claude" / "projects" / slug(PROJECT.parent))]
        print(f"NO TRANSCRIPTS no agent transcripts found at {' or '.join(tried)}; set growth.json transcripts_dir to the folder that holds them. "
              "Nothing was checked.")
        sys.exit(3)
    rows = [l for l in LOG.read_text().splitlines() if l.startswith("|")] if LOG.exists() else []
    if a.cmd == "list":
        for i, m in enumerate(msgs, 1):
            print(f"{i:3}  {m['at']}  {m['text'][:300].replace(chr(10), ' ')}")
        return
    mapped = json.loads(MAP.read_text()) if MAP.exists() else {}
    miss, answers = [], []
    for m in msgs:
        if m["at"] in mapped or logged(m["text"], rows):
            continue
        (answers if len(words(m["text"])) < 4 else miss).append(m)
    for m in miss:
        print(f"MISSING  {m['at']}  {m['text'][:300].replace(chr(10), ' ')}")
    for m in answers:
        print(f"ANSWER?  {m['at']}  {m['text'][:120].replace(chr(10), ' ')}")
    print(f"{len(msgs)} owner messages; {len(miss)} not in the steps log; {len(answers)} short answers to confirm.")
    try:  # keep the owner's journal page current with the steps log
        import owner_journal
        owner_journal.build()
    except Exception as e:  # noqa: BLE001
        print(f"owner journal page not rebuilt: {e}", file=sys.stderr)
    sys.exit(1 if (miss or answers) else 0)


if __name__ == "__main__":
    main()
