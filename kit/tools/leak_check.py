#!/usr/bin/env python3
"""Fail when something private is about to be committed or published.

  growth leak_check                      # every file of the repo that is tracked or not ignored
  growth leak_check --staged             # only what is staged (the pre-commit hook)
  growth leak_check --message FILE       # one commit message (the commit-msg hook)
  growth leak_check --text FILE          # an issue or PR body before posting: every line, Markdown headings too
  growth leak_check --history            # every commit of the repo: added lines, file names, messages, author and committer (before any push)
  growth leak_check --root DIR           # another folder (default: the git repo or folder the command runs in)

What it looks for (exit 1 on any hit):
  - key-shaped strings: cloud and API keys, tokens, private keys, bearer headers, KEY=value secrets
  - .env files and private-key files by name (.env.example is fine)
  - email addresses that are not @example.* (and not the assistant's noreply address)
  - phone numbers (the reserved fictional 555-01xx numbers are fine)
  - every word in a git-ignored `.private-words` file at the root (one per line, case-insensitive, `#` comments): client
    names, people, domains. A space, hyphen, underscore or dot in a listed phrase matches any of them or none, so
    "red fox" also finds "red-fox", "red_fox" and "redfox". The file is read when it exists and never committed;
    CI has none and still runs the rest.
  - with --history, the author and committer name and email of every commit: a private word there is a WARN (the
    history is replaced by a fresh one at publish time), while the same word in a file or a message is a FAIL.
A line that holds the marker `leak-check: allow` is skipped, but only in files under tests/fixtures/ (anywhere else
the marker is ignored, so it cannot hide a real key). Files of any size are read in chunks, never skipped. Binary files
cannot be read: they are listed as a WARN; .sqlite and .db files fail by name.
A hit never prints the secret itself: a key shows its first four characters.
"""
from __future__ import annotations

import argparse
import io
import os
import re
import subprocess
import sys
from pathlib import Path

ALLOW = "leak-check: allow"
CHUNK = 1_000_000          # bytes read at a time; a bigger file is scanned chunk by chunk, never skipped
OVERLAP = 512              # bytes carried over when one line is longer than a chunk, so a key on the seam is still seen
ALLOW_DIR = "tests/fixtures/"
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".pytest_cache", ".venv", "venv"}
ENV_NAME = re.compile(r"(^|/)(\.env(\.[\w.-]+)?|id_rsa|id_ed25519|[\w.-]+\.(pem|p12|pfx|key|sqlite3?|db))$")
ENV_OK = re.compile(r"(^|/)\.env\.(example|sample|template)$")

KEYS = [
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("API key (sk-)", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}")),
    ("GitHub token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})")),
    ("Stripe-style key", re.compile(r"\b[spr]k_(?:live|test)_[0-9A-Za-z]{16,}")),
    ("Slack webhook", re.compile(r"hooks\.slack\.com/services/")),
    ("Discord webhook", re.compile(r"discord(?:app)?\.com/api/webhooks/")),
    ("GitLab token", re.compile(r"\bglpat-[A-Za-z0-9_-]{16,}")),
    ("Hugging Face token", re.compile(r"\bhf_[A-Za-z0-9]{30,}")),
    ("npm token", re.compile(r"\bnpm_[A-Za-z0-9]{30,}")),
    ("Google OAuth secret", re.compile(r"\bGOCSPX-[A-Za-z0-9_-]{16,}")),
    ("SendGrid key", re.compile(r"\bSG\.[\w-]{16,}\.[\w-]{16,}")),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("private key block", re.compile(r"-----BEGIN (?:[A-Z]+ )*PRIVATE KEY-----")),
    ("bearer token", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{24,}")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
]
SECRET_ASSIGN = re.compile(r"""(?ix)\b([A-Z0-9_-]*(?:TOKEN|SECRET|(?:API|ACCESS|AUTH|PRIVATE)[_-]?KEY|AUTH|CREDENTIAL|PASSWORD|PASSWD)[A-Z0-9_-]*)\s*[:=]\s*["']?([A-Za-z0-9/+_=.~-]{16,})""")
PLACEHOLDER = re.compile(r"(?i)^(x{4,}|\*{4,}|<.*>|\$\{?\w+|your[_-]|example|changeme|placeholder|dummy|fake|redacted|\.{3})|^[a-z_]+\(")
URL_CREDS = re.compile(r"\b[a-z][a-z0-9+.-]*://([^\s/:@]+):([^\s/@]{3,})@([\w.-]+)")
CRED_PLACEHOLDER = {"pass", "password", "secret", "user", "username", "xxxx", "changeme", "passwd"}
OBFUSCATED_EMAIL = re.compile(r"(?i)\b[A-Za-z0-9._+-]+\s*(?:\[at\]|\(at\)|%40)\s*([A-Za-z0-9-]+(?:(?:\.|\s*\[dot\]\s*|\s*\(dot\)\s*)[A-Za-z0-9-]+)*(?:\.|\s*\[dot\]\s*|\s*\(dot\)\s*)[A-Za-z]{2,})\b")
TEL_WORD = re.compile(r"(?i)\b(?:tel|telephone|phone|call|mobile|cell|whatsapp|fax|sms|text us|contact)\b")
BARE_PHONE = re.compile(r"(?<![\w.+-])(?:\+?1)?[2-9]\d{9}(?![\w-])")
INTL_PHONE = re.compile(r"(?<![\w.])\+\d{1,3}[ .-]?\d{4,5}[ .-]\d{4,6}(?![\w-])|(?<![\w.])\+\d{10,14}(?![\w-])")
EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,})\b")
EMAIL_OK_DOMAIN = re.compile(r"(?i)(^|\.)example(\.[a-z]+)?$|(^|\.)noreply(\.github\.com)?$|^anthropic\.com$|(^|\.)invalid$|(^|\.)localhost$|(^|\.)test$")
EMAIL_OK_FULL = {"noreply@anthropic.com"}
PHONE = re.compile(r"(?<![\w.])(?:\+?1[ .-])?\(?\b[2-9]\d{2}\)?[ .-]\d{3}[ .-]\d{4}\b(?![\w-])|(?<![\w.])\+\d{1,3}[ .-]\d{2,4}[ .-]\d{3,4}(?:[ .-]\d{2,4})?\b")
PHONE_OK = re.compile(r"555[ .-]?01\d\d")


def private_words(path: Path | None) -> list[str]:
    if not path or not path.is_file():
        return []
    return [l.strip().lower() for l in path.read_text(errors="replace").splitlines() if l.strip() and not l.lstrip().startswith("#")]


_RX_CACHE: dict[str, re.Pattern] = {}


def word_rx(word: str) -> re.Pattern:
    """A listed word as a pattern: its parts may be split by spaces, hyphens, underscores or dots, or by nothing."""
    rx = _RX_CACHE.get(word)
    if rx is None:
        parts = [p for p in re.split(r"[\s\-_.]+", word.lower()) if p]
        rx = re.compile(r"[\s\-_.]*".join(re.escape(p) for p in parts) if parts else r"(?!)", re.I)
        _RX_CACHE[word] = rx
    return rx


def mask(s: str) -> str:
    return s[:4] + "…" if len(s) > 4 else "…"


def allow_marker_ok(path: str) -> bool:
    """The allow marker counts only for files under tests/fixtures/."""
    return ("/" + path.replace("\\", "/")).find("/" + ALLOW_DIR) == 0 or ("/" + ALLOW_DIR) in "/" + path.replace("\\", "/")


def scan_text(text: str, words: list[str], allow: bool = False, first_line: int = 1):
    """[(line number, kind, shown)] for the text. Lines holding the allow marker are skipped only when `allow` is true
    (the caller passes it for files under tests/fixtures/)."""
    hits = []
    for n, line in enumerate(text.splitlines(), first_line):
        if allow and ALLOW in line:
            continue
        for kind, rx in KEYS:
            m = rx.search(line)
            if m:
                hits.append((n, kind, mask(m.group(0))))
        for m in SECRET_ASSIGN.finditer(line):
            val = m.group(2)
            if not PLACEHOLDER.search(val) and re.search(r"\d", val) and re.search(r"[A-Za-z]", val):
                hits.append((n, f"secret value for {m.group(1)}", mask(val)))
        for m in URL_CREDS.finditer(line):
            user, pw, host = m.groups()
            if PLACEHOLDER.search(pw) or pw.lower() in CRED_PLACEHOLDER or EMAIL_OK_DOMAIN.search(host):
                continue
            hits.append((n, "password inside a web address", mask(pw)))
        for m in OBFUSCATED_EMAIL.finditer(line):
            dom = re.sub(r"(?i)\s*[\[(]dot[\])]\s*", ".", m.group(1))
            if not EMAIL_OK_DOMAIN.search(dom):
                hits.append((n, "email address (written out)", mask(m.group(0))))
        for m in EMAIL.finditer(line):
            if m.group(0).lower() in EMAIL_OK_FULL or EMAIL_OK_DOMAIN.search(m.group(1)):
                continue
            hits.append((n, "email address", mask(m.group(0))))
        for m in PHONE.finditer(line):
            if PHONE_OK.search(m.group(0)):
                continue
            hits.append((n, "phone number", mask(re.sub(r"\D", "", m.group(0)))))
        for m in INTL_PHONE.finditer(line):
            if not PHONE_OK.search(m.group(0)) and not any(h[0] == n and h[1] == "phone number" for h in hits):
                hits.append((n, "phone number", mask(re.sub(r"\D", "", m.group(0)))))
        if TEL_WORD.search(line):
            for m in BARE_PHONE.finditer(line):
                if not PHONE_OK.search(m.group(0)) and not any(h[0] == n and h[1] == "phone number" for h in hits):
                    hits.append((n, "phone number", mask(m.group(0))))
        for w in words:
            if word_rx(w).search(line):
                hits.append((n, "private word", w))
    return hits


def scan_name(path: str, words: list[str]):
    hits = []
    if ENV_NAME.search(path) and not ENV_OK.search(path):
        hits.append((0, "secret or environment file by name", path.rsplit("/", 1)[-1]))
    hits += [(0, "private word in the file name", w) for w in words if word_rx(w).search(path)]
    return hits


def is_text(b: bytes) -> bool:
    return b"\0" not in b[:4096]


def git(root: Path, *args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True)


def in_git(root: Path) -> bool:
    return git(root, "rev-parse", "--is-inside-work-tree").returncode == 0


def work_files(root: Path) -> list[str]:
    if in_git(root):
        out = git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard").stdout.decode("utf-8", "replace")
        return sorted({f for f in out.split("\0") if f and (root / f).is_file()})
    found = []
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in SKIP_DIRS]
        found += [str(Path(dp, f).relative_to(root)) for f in fn]
    return sorted(found)


def chunks(fh):
    """(first line number, text) pieces of an open binary file, each cut at a line end where possible. A line longer
    than CHUNK is cut anyway, and the last OVERLAP bytes are repeated in the next piece so nothing on the seam is missed."""
    line_no, carry = 1, b""
    while True:
        block = fh.read(CHUNK)
        data = carry + block
        if not block:
            if data:
                yield line_no, data.decode("utf-8", "replace")
            return
        cut = data.rfind(b"\n")
        if cut < 0:
            yield line_no, data.decode("utf-8", "replace")
            carry = data[-OVERLAP:]
            continue
        piece = data[:cut + 1]
        yield line_no, piece.decode("utf-8", "replace")
        line_no += piece.count(b"\n")
        carry = data[cut + 1:]


def scan_files(root: Path, files: list[str], words: list[str], staged=False, warns=None):
    """Hits for the files. A file that cannot be read in full is a hit (never skipped quietly); a binary file is
    appended to `warns` (when given) because its content cannot be checked."""
    report = []
    for f in files:
        for n, kind, shown in scan_name(f, words):
            report.append((f, n, kind, shown))
        allow = allow_marker_ok(f)
        try:
            if staged:
                fh = io.BytesIO(git(root, "show", f":{f}").stdout)
            else:
                fh = open(root / f, "rb")
            with fh:
                head = fh.read(4096)
                if not head:
                    continue
                if not is_text(head):
                    if warns is not None:
                        warns.append((f, 0, "binary file not checked", f))
                    continue
                fh.seek(0)
                seen = set()
                for first, text in chunks(fh):
                    for n, kind, shown in scan_text(text, words, allow=allow, first_line=first):
                        if (n, kind, shown) not in seen:
                            seen.add((n, kind, shown))
                            report.append((f, n, kind, shown))
        except OSError as e:
            report.append((f, 0, "file could not be read, so it was not checked", str(e)[:60]))
    return report


def scan_history(root: Path, words: list[str]):
    """(hits, warnings). Hits: every added line of every commit, every file name that ever existed and every commit
    message. A private word in the author or committer name or email is a hit when the commit is not on any remote yet
    (one push would publish it for good), else a warning (history is replaced at publish)."""
    report, warns = [], []
    # commits no remote has yet: a private word in their identity is a FAIL (one push would publish it for good)
    unpushed = {h[:8] for h in git(root, "rev-list", "--all", "--not", "--remotes").stdout.decode("utf-8", "replace").split()}
    log = git(root, "log", "--all", "--no-color", "-p", "-U0", "--no-ext-diff",
              "--format=@@commit %H%n@@who %an%x09%ae%x09%cn%x09%ce%n%B%n@@endmsg").stdout.decode("utf-8", "replace")
    commit, msg, cur, in_msg, ln = "", [], "", False, 0
    seen = set()
    for line in log.split("\n"):
        if line.startswith("@@commit "):
            commit, in_msg, msg = line.split()[1][:8], True, []
            continue
        if in_msg:
            if line.startswith("@@who ") and not msg:
                name, email, cname, cemail = (line[6:].split("\t") + ["", "", "", ""])[:4]
                for role, nm, em in (("author", name, email), ("committer", cname, cemail)):
                    for w in words:
                        for field, val in (("name", nm), ("email", em)):
                            if not word_rx(w).search(val):
                                continue
                            if commit in unpushed:
                                report.append((f"commit {commit}", 0, f"private word in the {role} {field} (not pushed yet)", w))
                            else:
                                warns.append((f"commit {commit}", 0, f"private word in the {role} {field}", w))
            elif line == "@@endmsg":
                in_msg = False
                for _n, kind, shown in scan_text("\n".join(msg), words):
                    if kind != "email address":
                        report.append((f"commit {commit}", 0, kind + " in the commit message", shown))
            else:
                msg.append(line)
            continue
        if line.startswith("diff --git"):
            cur = line.split(" b/", 1)[-1]
            if (commit, cur) not in seen:
                seen.add((commit, cur))
                for n, kind, shown in scan_name(cur, words):
                    report.append((f"commit {commit}: {cur}", n, kind, shown))
            continue
        m = re.match(r"@@ -\S+ \+(\d+)", line)
        if m:
            ln = int(m.group(1)) - 1
            continue
        if line.startswith("+") and not line.startswith("+++"):
            ln += 1
            for _n, kind, shown in scan_text(line[1:], words, allow=allow_marker_ok(cur)):
                report.append((f"commit {commit}: {cur}", ln, kind, shown))
    # one line per kind of identity warning, not one per commit
    uniq, counts = [], {}
    for f, n, kind, shown in warns:
        k = (kind, shown)
        if k not in counts:
            counts[k] = [f, 0]
            uniq.append(k)
        counts[k][1] += 1
    warns = [(counts[k][0], 0, k[0], f"{k[1]} (in {counts[k][1]} commit(s), first {counts[k][0]})") for k in uniq]
    return report, warns


def staged_files(root: Path) -> list[str]:
    out = git(root, "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z").stdout.decode("utf-8", "replace")
    return [f for f in out.split("\0") if f]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default="", help="folder to check (default: the git repo the command runs in, else this folder)")
    ap.add_argument("--staged", action="store_true", help="only the files staged for commit")
    ap.add_argument("--history", action="store_true", help="every commit, not just the files now")
    ap.add_argument("--message", default="", help="a commit message file (the commit-msg hook): keys and private words in it fail")
    ap.add_argument("--text", default="", help="any text file (an issue or PR body, Markdown): every line is scanned, headings too")
    ap.add_argument("--private-words", default="", help="the private words file (default: <root>/.private-words)")
    a = ap.parse_args(argv)
    root = Path(a.root or ".").resolve()
    top = git(root, "rev-parse", "--show-toplevel").stdout.decode().strip()
    if not a.root and top:
        root = Path(top)
    warns = []
    words = private_words(Path(a.private_words) if a.private_words else root / ".private-words")
    if a.message or a.text:
        f = Path(a.message or a.text)
        if not f.is_file():
            print(f"leak_check: {'--message' if a.message else '--text'} needs a readable FILE path, not the text itself "
                  f"(got {str(f)[:60]!r}); write the text to a file first", file=sys.stderr)
            return 2
        lines = f.read_text(errors="replace").splitlines()
        # a git commit message drops its '#' comment lines; any other text (Markdown headings!) is scanned in full (issue #65)
        is_commit = bool(a.message)          # --message is a git commit message: its '#' lines are git comments
        text = "\n".join(l for l in lines if not (is_commit and l.startswith("#")))
        label, what = ("commit message", "the commit message") if a.message else (f.name, f.name)
        bad = [(n, kind, shown) for n, kind, shown in scan_text(text, words) if kind != "email address"]
        for n, kind, shown in bad:
            print(f"FAIL {label}:{n} {kind}: {shown}")
        print(f"leak_check: {len(bad)} hit(s) in {what} ({len(words)} private word(s) checked).")
        return 1 if bad else 0
    if a.history:
        if not in_git(root):
            print("leak_check --history needs a git repository", file=sys.stderr)
            return 2
        report, warns = scan_history(root, words)
        what = "every commit"
    elif a.staged:
        report = scan_files(root, staged_files(root), words, staged=True, warns=warns)
        what = "the staged files"
    else:
        report = scan_files(root, [f for f in work_files(root) if f != ".private-words"], words, warns=warns)
        what = "the files"
    for f, n, kind, shown in report:
        print(f"FAIL {f}{':' + str(n) if n else ''} {kind}: {shown}")
    for f, n, kind, shown in warns:
        if kind == "binary file not checked":
            print(f"WARN {kind}: {shown}. Its content cannot be read as text; make sure it holds nothing private.")
            continue
        print(f"WARN {kind}: {shown}. History is replaced by a fresh one at publish time; set a neutral git identity for the new history.")
    note = f"{len(words)} private word(s) checked" if words else "no .private-words file: key, email and phone checks only"
    extra = f", {len(warns)} warning(s)" if warns else ""
    print(f"leak_check: {len(report)} hit(s) in {what}{extra} ({note}).")
    return 1 if report else 0


if __name__ == "__main__":
    sys.exit(main())
