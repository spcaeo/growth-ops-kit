"""Result collection and printing. Levels: OK, WARN, FAIL, INFO, SKIP."""
from __future__ import annotations

from dataclasses import dataclass, field

ORDER = ["FAIL", "WARN", "INFO", "SKIP", "OK"]


@dataclass
class Result:
    cid: str          # check id, same as in the SOP (for example TTL-02)
    level: str        # OK / WARN / FAIL / INFO / SKIP
    msg: str          # what was found, plain words
    fix: str = ""     # what to change (only for WARN / FAIL)


@dataclass
class Report:
    url: str = ""
    mode: str = "dev"
    results: list = field(default_factory=list)

    def add(self, cid, level, msg, fix=""):
        self.results.append(Result(cid, level, msg, fix))

    def ok(self, cid, msg, fix=""):
        self.add(cid, "OK", msg)

    def warn(self, cid, msg, fix=""):
        self.add(cid, "WARN", msg, fix)

    def fail(self, cid, msg, fix=""):
        self.add(cid, "FAIL", msg, fix)

    def info(self, cid, msg, fix=""):
        self.add(cid, "INFO", msg)

    def skip(self, cid, msg, fix=""):
        self.add(cid, "SKIP", msg)

    def count(self, level):
        return sum(1 for r in self.results if r.level == level)

    def exit_code(self):
        return 1 if self.count("FAIL") else 0

    def to_text(self, show_ok=True):
        out = [f"Technical SEO check: {self.url}  (mode: {self.mode})", ""]
        for r in self.results:
            if r.level == "OK" and not show_ok:
                continue
            out.append(f"{r.level:<4} {r.cid:<7} {r.msg}")
            if r.fix and r.level in ("WARN", "FAIL"):
                out.append(f"          fix: {r.fix}")
        out.append("")
        out.append(self.summary())
        return "\n".join(out)

    def summary(self):
        return (f"Summary: {self.count('OK')} OK, {self.count('WARN')} WARN, "
                f"{self.count('FAIL')} FAIL, {self.count('INFO')} INFO, {self.count('SKIP')} SKIP "
                f"({len(self.results)} lines)")

    def to_markdown(self):
        out = [f"Checker output for `{self.url}` (mode `{self.mode}`). {self.summary()}", ""]
        for lvl in ("FAIL", "WARN", "INFO", "SKIP", "OK"):
            rows = [r for r in self.results if r.level == lvl]
            if not rows:
                continue
            out += [f"### {lvl} ({len(rows)})", "", "| ID | What it found | Fix |", "| --- | --- | --- |"]
            for r in rows:
                esc = lambda s: s.replace("|", "\\|").replace("\n", " ")
                out.append(f"| {r.cid} | {esc(r.msg)} | {esc(r.fix)} |")
            out.append("")
        return "\n".join(out)
