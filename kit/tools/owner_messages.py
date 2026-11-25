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

A prompt from a scheduled, unattended run is not an owner message: list its prompt file in docs/scheduled-prompts.txt
(or set GROWTH_SCHEDULED_PROMPT_FILE), or run with GROWTH_SCHEDULED=1 (then the one prompt of the newest session is left out).

Short replies that only answer a question (yes, ok, an option label) are listed as "answers" and must appear in the
log row of the question they answer, or in tasks.json; they are reported separately.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import transcript  # noqa: E402  (one reader for owner messages, shared with the Stop-hook guards)
from config import CFG, PROJECT, DOCS  # noqa: E402



def slug(path: Path) -> str:
    """How Claude Code names a folder's transcript directory: every / and _ becomes -, with a leading -."""
    return "-" + str(path).strip("/").replace("/", "-").replace("_", "-")


def transcript_dirs(project: Path = PROJECT, home: Path | None = None, cfg: dict | None = None):
    """The agent's transcript folders for this project: only the project's own path (the session started inside it), or
    growth.json "transcripts_dir" (a string, or a list of folders, for a session started in a workspace above the project).
    The folder above is never read by default: it holds the owner's unrelated sessions and floods the check with false alarms (#21)."""
    root = (home or Path.home()) / ".claude" / "projects"
    given = (cfg or {}).get("transcripts_dir")
    given = [given] if isinstance(given, str) else (given or [])
    cands = [Path(g).expanduser() for g in given] if given else [root / slug(project)]
    ws = (cfg or {}).get("workspace")
    if ws and not given:      # the folder Claude Code is opened in (growth.json "workspace", set by setup): named on purpose, so read it
        cands.append(root / slug(Path(ws).expanduser()))
    return [c for c in cands if c.is_dir()]


LOG = DOCS / "steps-log.md"
MAP = DOCS / "owner-messages-map.json"

def words(t):
    return re.findall(r"[a-z0-9$']+", t.lower())


def scheduled_prompts(docs=None):
    """The prompts of scheduled, unattended runs: a run records its prompt file path (one per line) in
    docs/scheduled-prompts.txt, or names it in $GROWTH_SCHEDULED_PROMPT_FILE. Such a prompt is a timer's text, not a message
    the owner typed, so it is never an owner message and never needs a line in docs/steps-log.md."""
    out = []
    listed = Path(docs or DOCS) / "scheduled-prompts.txt"
    names = (listed.read_text().splitlines() if listed.is_file() else []) + [os.environ.get("GROWTH_SCHEDULED_PROMPT_FILE", "")]
    for n in names:
        n = n.strip()
        if n and not n.startswith("#"):
            try:
                t = Path(n).expanduser().read_text(errors="replace").strip()
            except OSError:
                continue
            if t:
                out.append(" ".join(t.split()))
    return out


def is_scheduled(text, prompts):
    flat = " ".join(text.split())
    return any(flat == p or flat.startswith(p[:200]) or p.startswith(flat[:200]) and len(flat) >= 40 for p in prompts)


SECRET = re.compile(r"(?=\S*[A-Za-z])(?=\S*\d)(?=\S*[^\w\s/.:-])\S{10,}")     # letters + digits + symbols, 10+ long


def hide_secrets(text: str) -> str:
    """A password or key someone typed into the chat is never printed back (24 Nov 2026: the Stop hook echoed one)."""
    return SECRET.sub("[hidden]", text)


def project_start(project: Path = PROJECT, cfg: dict | None = None) -> str:
    """UTC "YYYY-MM-DDTHH:MM" from which owner messages count: growth.json "owner_messages_since", else 30 minutes before
    the setup started (the message that asked for the setup comes just before it). Chat from before the project existed,
    in a workspace that held an earlier setup, is not this project's to log. "" when unknown."""
    from datetime import datetime, timedelta, timezone
    given = (cfg or {}).get("owner_messages_since") or ""
    try:
        if not given:
            started = json.loads((Path(project) / "setup-state.json").read_text()).get("started") or ""
            if not started:
                return ""
            given = (datetime.fromisoformat(started) - timedelta(minutes=30)).isoformat()
        d = datetime.fromisoformat(given)
        d = d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)
        return d.strftime("%Y-%m-%dT%H:%M")
    except (OSError, ValueError):
        return ""


def owner_messages(since=""):
    out = []
    start = project_start(PROJECT, CFG)
    prompts = scheduled_prompts()
    unattended = os.environ.get("GROWTH_SCHEDULED") == "1"      # an unattended run's one user turn is its own prompt
    files = sorted(p for d in transcript_dirs(cfg=CFG) for p in d.glob("*.jsonl"))
    newest = max(files, key=lambda p: p.stat().st_mtime) if files else None
    for f in files:
        skip_first = unattended and f == newest
        for e in transcript.entries(f):
            t = transcript.owner_text(e)
            if t is None or t == "[attachment]":
                continue
            if skip_first:
                skip_first = False
                continue
            t = re.sub(r"<pasted_content[^>]*>.*?</pasted_content[^>]*>", "[pasted]", t, flags=re.S).strip()
            if not t or t == "[pasted]" or is_scheduled(t, prompts):
                continue
            ts = e.get("timestamp", "")
            if since and ts[:10] < since:
                continue
            if start and ts[:16] < start:
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
    w = words(hide_secrets(msg))          # a row never holds the hidden part, so compare without it
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


def log_missing(msgs) -> int:
    """Append one steps-log row per owner message not logged yet: their words (passwords hidden), and a "to fill" note the
    agent completes with what was done. Owner, 24 Nov 2026: book-keeping happens quietly, not as chat noise. Returns the count."""
    if not msgs or not LOG.exists():
        return 0
    lines = LOG.read_text().split("\n")
    ids = [int(m.group(1)) for l in lines for m in [re.match(r"\| I-(\d+) \|", l)] if m]
    at = max((i for i, l in enumerate(lines) if l.startswith("| I-") or l.startswith("| --- |")), default=None)
    if at is None:
        return 0
    n = max(ids, default=0)
    new = []
    kept = []
    for m in msgs:
        if new and logged(m["text"], new):     # the same message seen twice (two copies in the transcripts) gets one row
            continue
        kept.append(m)
        n += 1
        words_ = hide_secrets(" ".join(m["text"].split()))[:400].replace("|", "/")
        new.append(f'| I-{n} | {m["at"][:10]} | "{words_}" | (to fill: what was done) | (to fill) |')
    lines[at + 1:at + 1] = new
    LOG.write_text("\n".join(lines))
    short = {m["at"]: f"I-{n - len(new) + i + 1}" for i, m in enumerate(kept) if len(words(m["text"])) < 4}
    if short:                  # a short answer ("yes", "done") never matches a row by its words: map it to its row once
        mapped = json.loads(MAP.read_text()) if MAP.exists() else {}
        mapped.update(short)
        MAP.write_text(json.dumps(mapped, indent=2) + "\n")
    return len(new)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["list", "check", "log-missing"])
    ap.add_argument("--since", default="")
    a = ap.parse_args()
    msgs = owner_messages(a.since)
    if a.cmd == "check" and not transcript_dirs(cfg=CFG):
        tried = str(Path.home() / ".claude" / "projects" / slug(PROJECT))
        print(f"NO TRANSCRIPTS no agent transcripts found at {tried}; start the agent from the project folder, or set growth.json transcripts_dir to the folder that holds them. "
              "Nothing was checked.")
        sys.exit(3)
    rows = [l for l in LOG.read_text().splitlines() if l.startswith("|")] if LOG.exists() else []
    if a.cmd == "list":
        for i, m in enumerate(msgs, 1):
            print(f"{i:3}  {m['at']}  {hide_secrets(m['text'][:300]).replace(chr(10), ' ')}")
        return
    mapped = json.loads(MAP.read_text()) if MAP.exists() else {}
    if a.cmd == "log-missing":
        print(log_missing([m for m in msgs if m["at"] not in mapped and not logged(m["text"], rows)]))
        return
    miss, answers = [], []
    for m in msgs:
        if m["at"] in mapped or logged(m["text"], rows):
            continue
        (answers if len(words(m["text"])) < 4 else miss).append(m)
    for m in miss:
        print(f"MISSING  {m['at']}  {hide_secrets(m['text'][:300]).replace(chr(10), ' ')}")
    for m in answers:
        print(f"ANSWER?  {m['at']}  {hide_secrets(m['text'][:120]).replace(chr(10), ' ')}")
    print(f"{len(msgs)} owner messages; {len(miss)} not in the steps log; {len(answers)} short answers to confirm.")
    try:  # keep the owner's journal page current with the steps log
        import owner_journal
        owner_journal.build()
    except Exception as e:  # noqa: BLE001
        print(f"owner journal page not rebuilt: {e}", file=sys.stderr)
    sys.exit(1 if (miss or answers) else 0)


if __name__ == "__main__":
    main()
