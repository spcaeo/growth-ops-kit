#!/usr/bin/env python3
"""The setup wizard: one guided setup that does every step in order, asks for all access once, installs the agent harness,
remembers where it is, and will not call setup done until the research browser is connected and Google is set to the
target country.

  growth wizard <folder> --site https://example.com [--name N] [--answers answers.json] [--yes]
  growth wizard                         # inside a project: resume at the first open step
  growth wizard --check                 # run every test again and report what changed (drift)
  growth wizard --repair                # install whatever the harness is missing (never overwrites your own settings)
  growth wizard status                  # each step, its status, answer source and date
  growth wizard answer <step> <value>   # record one answer (value is JSON or plain text); used by the /onboard skill
  growth wizard confirm browser --name "Browser 1"
  growth wizard confirm region --seen "United States" --owner-confirmed
  growth wizard research-check [--connected "Browser 1"] [--task T5 --step 3]   # start of every research step

What it will never do: push, merge, deploy, change DNS, read the live site page by page, print a key. Questions come from an
answers file (--answers), a person at the terminal, or (with neither) are printed as "QUESTION <step>: ..." and the run stops
with exit code 3, so an agent can ask the owner and record the answer with `growth wizard answer`. Things the code cannot do
itself (connect Chrome, set Google's region) are guided steps the run waits on until the confirmation is recorded.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import detect  # noqa: E402
import harness  # noqa: E402
import research_gate as gate  # noqa: E402
import setup_task  # noqa: E402
import wizard_state as ws  # noqa: E402

KIT_DIR = Path(__file__).resolve().parent.parent
WAIT = 3
ORDER = ["market", "site_repo", "analytics", "live_rule", "approver", "harness", "detect", "browser", "region"]
QUESTIONS = {
    "market": 'Which country and language is the target market? answer: {"country": "US", "language": "en"} (asked first; every search, AI answer and keyword uses it)',
    "site_repo": 'Where is the site repo (path, or a git address to clone), or none? answer: {"path": "~/code/site"} or {"path": "", "clone": "<git address>"} or "none"',
    "analytics": 'Analytics / Search Console: the keys file path (outside git, mode 600; the one-time code goes in it, never in chat), or "later". answer: {"keys_file": "~/.config/growth/site.env"} or "later"',
    "live_rule": 'The live-site rule and the preview address. answer: {"rule": "no-crawl", "preview_url": "http://127.0.0.1:4321"} (no-crawl = never read the live site page by page)',
    "approver": 'Who approves a release (a merge or a deploy)? answer: "Name, role"',
    "harness": 'Install the agent harness (Stop hook, status bar, permissions, skills, CLAUDE.md lines) and git hooks? answer: {"permissions": true, "git_hooks": true}',
    "detect": 'Confirm what was detected (stack, sitemap, trailing slash, languages, redirects, content folders)? answer: {"confirm": true}',
    "browser": 'Connect the research browser: in Claude Code type /chrome, choose the browser, check "By default: on". Then: growth wizard confirm browser --name "<its name>"',
    "region": 'Set Google to the target country in that browser (Search settings > Other settings > Language & region > Results region), read the region Google reports, then: growth wizard confirm region --seen "<what Google says>" --owner-confirmed',
}


class Waiting(Exception):
    pass


def say(msg: str = "") -> None:
    print(msg, flush=True)


def cfg_of(project: Path) -> dict:
    return json.loads((project / "growth.json").read_text())


def save_cfg(project: Path, cfg: dict) -> None:
    (project / "growth.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")


def parse_value(text: str):
    try:
        return json.loads(text)
    except ValueError:
        return text


class Session:
    def __init__(self, project: Path, answers: dict | None = None, interactive: bool = False, yes: bool = False):
        self.project, self.answers, self.interactive, self.yes = project, answers or {}, interactive, yes

    def answer(self, step: str, prompt_default=None):
        """(value, source) from the answers file, a person at the terminal, or --yes; raises Waiting with the question."""
        if step in self.answers:
            return self.answers[step], "answers-file"
        if self.interactive:
            say(f"\n{step.upper()}: {QUESTIONS[step]}")
            raw = input("> ").strip()
            if raw:
                return parse_value(raw), "owner"
        if self.yes and prompt_default is not None:
            return prompt_default, "flag --yes"
        ws.record(self.project, step, "asked")
        say(f"QUESTION {step}: {QUESTIONS[step]}")
        raise Waiting(step)


# ---- the steps -------------------------------------------------------------------------------------------------------

def step_market(s: Session) -> str:
    v, src = s.answer("market")
    if isinstance(v, str):
        v = {"country": v}
    code = str(v.get("country") or v.get("primary_country") or "").upper()
    if not code or len(code) != 2:
        raise SystemExit('market: give the two-letter country code, e.g. {"country": "US", "language": "en"}')
    lang = (v.get("language") or gate.COUNTRIES.get(code, ("", "en"))[1]).lower()
    cfg = cfg_of(s.project)
    m = cfg.setdefault("market", {})
    m.update({"primary_country": code, "country_name": v.get("country_name") or gate.COUNTRIES.get(code, (code, ""))[0],
              "language": f"{lang}-{code}", "google_params": gate.google_params(code, lang)})
    save_cfg(s.project, cfg)
    test = {"command": "growth.json market.google_params", "result": m["google_params"]}
    ws.record(s.project, "market", "done", answer={"country": code, "language": lang}, source=src, test=test)
    return f"{m['country_name']}, {lang}; Google parameters {m['google_params']}"


def step_site_repo(s: Session) -> str:
    v, src = s.answer("site_repo")
    if v in ("none", "", None):
        ws.record(s.project, "site_repo", "declined", answer="none", source=src)
        return "no site repo: live-page checks only"
    if isinstance(v, str):
        v = {"path": v}
    path = Path(v.get("path") or "").expanduser()
    if v.get("clone") and not path.exists():
        r = subprocess.run(["git", "clone", "-q", str(v["clone"]), str(path)], capture_output=True, text=True)
        if r.returncode:
            raise SystemExit(f"site_repo: git clone failed: {r.stderr.strip().splitlines()[-1] if r.stderr.strip() else r.returncode}")
    ok = path.is_dir() and harness.git_repo_of(path)
    cfg = cfg_of(s.project)
    cfg["site_repo"] = str(path)
    if v.get("clone"):
        cfg["site_repo_remote"] = v["clone"]
    save_cfg(s.project, cfg)
    ws.record(s.project, "site_repo", "done" if ok else "answered", answer={"path": str(path)}, source=src,
              test={"command": f"git -C {path} rev-parse", "result": "a git checkout" if ok else "NOT a git checkout"})
    return f"{path} ({'a git checkout' if ok else 'not a git checkout: check the path'})"


def step_analytics(s: Session) -> str:
    v, src = s.answer("analytics", "later")
    if v in ("later", "none", "", None) or (isinstance(v, dict) and not v.get("keys_file")):
        ws.record(s.project, "analytics", "declined", answer="later", source=src)
        return "analytics declined for now (doctor A4 stays optional until a connector is switched on)"
    path = Path(v["keys_file"] if isinstance(v, dict) else v).expanduser()
    cfg = cfg_of(s.project)
    cfg["keys_file"] = str(path)
    save_cfg(s.project, cfg)
    if path.is_file():
        mode = oct(path.stat().st_mode & 0o777)
        n = sum(1 for l in path.read_text().splitlines() if "=" in l and not l.lstrip().startswith("#"))
        result = f"keys file mode {mode[2:]}, {n} entries (values never read out)"
        ws.record(s.project, "analytics", "done" if mode == "0o600" and n else "tested", answer={"keys_file": str(path)}, source=src,
                  test={"command": f"stat {path}", "result": result})
        return result + ("" if mode == "0o600" else "; run chmod 600 on it")
    ws.record(s.project, "analytics", "answered", answer={"keys_file": str(path)}, source=src,
              test={"command": f"stat {path}", "result": "file not there yet: put the one-time-code keys there"})
    return "keys file named, not there yet"


def step_live_rule(s: Session) -> str:
    v, src = s.answer("live_rule", {"rule": "no-crawl", "preview_url": ""})
    if isinstance(v, str):
        v = {"rule": v}
    cfg = cfg_of(s.project)
    cfg["live_site_rule"] = "no-crawl" if str(v.get("rule", "no-crawl")).startswith("no") else "crawl-ok"
    if v.get("preview_url"):
        cfg["preview_url"] = v["preview_url"].rstrip("/")
    save_cfg(s.project, cfg)
    ws.record(s.project, "live_rule", "done", answer={"rule": cfg["live_site_rule"], "preview_url": cfg.get("preview_url", "")}, source=src)
    return f"live site: {cfg['live_site_rule']}; previews on {cfg.get('preview_url') or '(not set yet)'}"


def step_approver(s: Session) -> str:
    v, src = s.answer("approver", "the owner")
    cfg = cfg_of(s.project)
    cfg["release_approver"] = str(v)
    save_cfg(s.project, cfg)
    ws.record(s.project, "approver", "done", answer=str(v), source=src)
    return f"releases are approved by: {v}"


def show_harness() -> None:
    say("The harness, installed once with one yes:")
    for line in ("Stop hook with a status message (every owner message logged, every rule checked)",
                 "status line: the open task as a bar (▰▱) at the bottom of the window",
                 "permissions: allow growth, read-only git, the kit's python; deny git push, merge to main, deploys, rm -rf outside the project",
                 "skills: /onboard", "CLAUDE.md: the workflow is the rule, re-read checkpoints, show progress",
                 "git pre-commit hooks (asked separately: they live in a git repo)"):
        say(f"  - {line}")


def install_harness(project: Path, wanted: dict) -> list[str]:
    cfg = cfg_of(project)
    made = harness.install(project, cfg.get("name", ""), cfg.get("site_url", ""), permissions=wanted.get("permissions", True), cfg=cfg)
    out = [f"wrote {p.relative_to(project)}" for p in made]
    if wanted.get("git_hooks"):
        out += harness.install_git_hooks(project, cfg)
    return out or ["nothing to add: the harness was already complete"]


def step_harness(s: Session) -> str:
    show_harness()
    v, src = s.answer("harness", {"permissions": True, "git_hooks": False})
    if isinstance(v, bool):
        v = {"permissions": v, "git_hooks": v}
    wanted = {"permissions": bool(v.get("permissions", True)), "git_hooks": bool(v.get("git_hooks", False))}
    lines = install_harness(s.project, wanted)
    bad = [f"{p}: {w}" for p, st, w, _ in harness.check(s.project, cfg_of(s.project)) if st == "todo"]
    ws.record(s.project, "harness", "done" if not bad else "tested", answer=wanted, source=src,
              test={"command": "harness.check (doctor A13)", "result": "every piece present" if not bad else "; ".join(bad)})
    return "; ".join(lines)


def step_detect(s: Session) -> str:
    cfg = cfg_of(s.project)
    repo = (s.project / cfg["site_repo"]).expanduser() if cfg.get("site_repo") else None
    found = detect.detect_all(repo, s.answers.get("sitemap") or cfg.get("sitemap_url", ""))
    if "sitemap_error" in found:
        say(f"  sitemap not read: {found['sitemap_error']}")
    say("Detected:\n" + json.dumps(found, indent=2))
    v, src = s.answer("detect", {"confirm": True})
    if isinstance(v, bool):
        v = {"confirm": v}
    if not v.get("confirm", True):
        ws.record(s.project, "detect", "declined", answer=found, source=src)
        return "detected values shown, not written (declined)"
    write_detected(s.project, found)
    ws.record(s.project, "detect", "done", answer=found, source="detected",
              test={"command": "growth detect", "result": summary(found)})
    return summary(found)


def summary(found: dict) -> str:
    bits = []
    if found.get("stack"):
        bits.append(f"stack {found['stack'].get('framework')} ({found['stack'].get('stack')})")
    sm = found.get("sitemap")
    if sm:
        bits.append(f"sitemap {sm['shape']} ({sm['pages']} pages, {sm['children']} children), {sm['trailing_slash']}, languages {sm['languages'] or 'none'}")
    if found.get("redirects"):
        bits.append("redirects in " + ", ".join(found["redirects"]))
    return "; ".join(bits) or "nothing detected"


def write_detected(project: Path, found: dict) -> None:
    """Every detected value goes to growth.json with source "detected" and the date; the live keys are set only when empty."""
    cfg = cfg_of(project)
    det = cfg.setdefault("detected", {})
    day = ws.now()[:10]

    def put(key, value, live_key=None):
        if value in (None, "", [], {}):
            return
        det[key] = {"value": value, "source": "detected", "date": day}
        if live_key and cfg.get(live_key) in (None, "", [], {}):
            cfg[live_key] = value
    st = found.get("stack") or {}
    put("framework", st.get("framework"))
    put("stack", st.get("stack"), None)
    if st.get("stack") and cfg.get("stack") in (None, "", "static"):
        cfg["stack"] = st["stack"]
    put("build_cmd", st.get("build_cmd"), "build_cmd")
    put("preview_cmd", st.get("preview_cmd"), "preview_cmd")
    put("build_dir", st.get("build_dir"), "build_dir")
    put("redirect_files", found.get("redirects"), "redirect_files")
    put("content_dirs", found.get("content_dirs"))
    sm = found.get("sitemap") or {}
    for k in ("shape", "children", "pages", "trailing_slash", "languages", "hreflang"):
        if sm:
            put(f"sitemap_{k}", sm.get(k) if sm.get(k) is not False else None)
    if sm.get("hreflang") is False:
        det["sitemap_hreflang"] = {"value": False, "source": "detected", "date": day}
    save_cfg(project, cfg)


def step_browser(s: Session) -> str:
    cur = ws.get(s.project, "browser")
    if cur.get("status") == "done":
        return f"research browser {cur['answer'].get('name')} confirmed {cur.get('date', '')[:10]}"
    if "browser" in s.answers:
        confirm_browser(s.project, (s.answers["browser"] or {}).get("name", "") if isinstance(s.answers["browser"], dict) else str(s.answers["browser"]), "answers-file")
        return "research browser confirmed"
    ws.record(s.project, "browser", "asked")
    say(f"WAITING browser: {QUESTIONS['browser']}")
    raise Waiting("browser")


def confirm_browser(project: Path, name: str, source: str = "agent") -> None:
    if not name.strip():
        raise SystemExit('confirm browser needs the browser\'s name: --name "Browser 1" (what list_connected_browsers shows)')
    ws.record(project, "browser", "done", answer={"name": name.strip()}, source=source,
              test={"command": "list_connected_browsers", "result": f"{name.strip()} connected"})


def confirm_region(project: Path, seen: str, owner_confirmed: bool, source: str = "agent") -> tuple[bool, str]:
    cfg = cfg_of(project)
    market = cfg.get("market") or {}
    want = gate.country_name(market)
    ok = gate.region_matches(seen, market)
    test = {"command": "read Results region on Google's Search settings page", "result": f"Google reports: {seen or '(nothing)'}"}
    if not ok:
        ws.record(project, "region", "asked", answer={"seen": seen, "owner_confirmed": False}, source=source, test=test)
        return False, (f"Google's region reads \"{seen}\", not {want}. Fix: " + gate.REGION_FIX.format(country=want)
                       + f"; read it again, then: growth wizard confirm region --seen \"{want}\" --owner-confirmed")
    if not owner_confirmed:
        ws.record(project, "region", "tested", answer={"seen": seen, "owner_confirmed": False}, source=source, test=test)
        return False, f"Google reports {seen}: matches {want}. Not done until the owner confirms it: add --owner-confirmed after they say yes."
    ws.record(project, "region", "done", answer={"seen": seen, "owner_confirmed": True}, source=source, test=test)
    return True, f"Google region {seen} confirmed for {want}"


def step_region(s: Session) -> str:
    cur = ws.get(s.project, "region")
    if cur.get("status") == "done":
        return f"Google region {cur['answer'].get('seen')} confirmed {cur.get('date', '')[:10]}"
    if "region" in s.answers and isinstance(s.answers["region"], dict):
        ok, msg = confirm_region(s.project, s.answers["region"].get("seen", ""), bool(s.answers["region"].get("owner_confirmed")), "answers-file")
        if ok:
            return msg
        say(msg)
        raise Waiting("region")
    ws.record(s.project, "region", "asked")
    say(f"WAITING region: {QUESTIONS['region']}")
    raise Waiting("region")


HANDLERS = {"market": step_market, "site_repo": step_site_repo, "analytics": step_analytics, "live_rule": step_live_rule,
            "approver": step_approver, "harness": step_harness, "detect": step_detect, "browser": step_browser, "region": step_region}


# ---- SETUP.md, doctor, the run ---------------------------------------------------------------------------------------

def write_setup_md(project: Path) -> None:
    """The wizard's record inside SETUP.md (between markers; the rest of the file is the owner's)."""
    cfg, st = cfg_of(project), ws.load(project)["steps"]
    m = cfg.get("market") or {}
    b, r = st.get("browser") or {}, st.get("region") or {}
    rows = [f"**Target market:** {gate.country_name(m) or 'not set'}, {m.get('language', '')}; Google parameters `{m.get('google_params', '')}`"]
    if b.get("status") == "done":
        rows.append(f"**Research browser:** {b['answer'].get('name')} (Claude in Chrome, \"By default: on\"), confirmed {b['date'][:10]}")
    else:
        rows.append("**Research browser:** NOT connected: no job with a research step may start")
    if r.get("status") == "done":
        rows.append(f"**Google region:** {r['answer'].get('seen')} read from Google's settings, confirmed by the owner {r['date'][:10]}")
    else:
        rows.append("**Google region:** NOT verified: no job with a research step may start")
    for k, label in (("live_site_rule", "Live-site rule"), ("preview_url", "Preview address"), ("release_approver", "Releases approved by")):
        if cfg.get(k):
            rows.append(f"**{label}:** {cfg[k]}")
    block = "<!-- wizard:start -->\n" + "\n".join(f"- {x}" for x in rows) + "\n<!-- wizard:end -->\n"
    f = project / "SETUP.md"
    text = f.read_text() if f.exists() else "# Setup record\n"
    if "<!-- wizard:start -->" in text:
        a, b2 = text.index("<!-- wizard:start -->"), text.index("<!-- wizard:end -->") + len("<!-- wizard:end -->\n")
        text = text[:a] + block + text[b2:]
    else:
        lines = text.split("\n")
        i = next((n for n, l in enumerate(lines) if l.startswith("# ")), -1) + 1
        text = "\n".join(lines[:i]) + "\n\n" + block + "\n" + "\n".join(lines[i:]).lstrip("\n")
    f.write_text(text)


def run_doctor(project: Path) -> tuple[str, int]:
    r = subprocess.run([sys.executable, str(KIT_DIR / "tools" / "doctor.py")], capture_output=True, text=True, cwd=project,
                       env={**os.environ, "GROWTH_PROJECT": str(project)})
    return r.stdout, r.returncode


def finish(project: Path) -> int:
    write_setup_md(project)
    out, _ = run_doctor(project)
    cfg = cfg_of(project)
    say("\n" + out)
    stuck = gate.problems(project, cfg)
    open_steps = [l for l in out.splitlines() if l[:4] in ("TODO", "FAIL")]
    if stuck:
        say("SETUP NOT DONE: the research browser and the Google region are not confirmed yet:")
        for p in stuck:
            say(f"  - {p}")
        return WAIT
    if open_steps:
        say(f"WIZARD DONE. {len(open_steps)} doctor step(s) still open: they are work for the agent (type /onboard in Claude Code), "
            "not questions for the wizard. Setup is done when doctor says every step OK.")
        return 0
    say("SETUP DONE: doctor says every step OK. Suggested first job: the top money page in the inventory (book/01-flow.md stage B).")
    return 0


def run(project: Path, session: Session) -> int:
    say(f"Setup wizard for {cfg_of(project).get('name')} ({cfg_of(project).get('site_url')})")
    say("What to expect: market, site repo, analytics access, live-site rule, approver, the harness (one yes), detection, then two guided steps "
        "(research browser, Google region). It never pushes, merges, deploys, changes DNS, reads the live site page by page or prints a key.\n")
    for step in ORDER:
        cur = ws.get(project, step)
        if cur.get("status") in ws.CLOSED:
            say(f"[{cur['status']:>8}] {step}: {cur.get('date', '')[:10]} ({cur.get('source', '')})")
            continue
        try:
            msg = HANDLERS[step](session)
        except Waiting as w:
            say(f"\nStopped at step '{w}'. Answer it, then run `growth wizard` again: it resumes here.")
            write_setup_md(project)
            run_doctor(project)
            return WAIT
        say(f"[    done] {step}: {msg}")
        write_setup_md(project)
        run_doctor(project)
    return finish(project)


# ---- other commands ----------------------------------------------------------------------------------------------------

def cmd_status(project: Path) -> int:
    st = ws.load(project)["steps"]
    for step in ORDER:
        e = st.get(step) or {"status": "todo"}
        say(f"{e['status']:<9} {step:<10} {e.get('date', '')[:16]:<17} {e.get('source', ''):<14} {(e.get('test') or {}).get('result', '')}")
    return 0


def cmd_check(project: Path) -> int:
    """Run every test again; report what changed since it was recorded."""
    cfg, st, bad = cfg_of(project), ws.load(project)["steps"], 0
    for step in ORDER:
        e = st.get(step)
        if not e or e["status"] == "todo":
            say(f"TODO     {step}: never answered")
            bad += 1
            continue
        if e["status"] == "declined":
            say(f"declined {step}: {e.get('date', '')[:10]}")
            continue
        result = None
        if step == "site_repo":
            p = Path(cfg.get("site_repo") or "")
            result = ("OK", "a git checkout") if p.is_dir() and harness.git_repo_of(p) else ("CHANGED", f"{p} is not a git checkout any more")
        elif step == "analytics":
            p = Path(cfg.get("keys_file") or "").expanduser()
            result = ("OK", f"keys file mode {oct(p.stat().st_mode & 0o777)[2:]}") if p.is_file() and p.stat().st_mode & 0o777 == 0o600 else ("CHANGED", "keys file missing or not mode 600")
        elif step == "harness":
            todo = [f"{p}: {w}" for p, s2, w, _ in harness.check(project, cfg) if s2 == "todo"]
            result = ("OK", "every piece present") if not todo else ("CHANGED", "; ".join(todo) + " (growth wizard --repair)")
        elif step == "detect":
            repo = (project / cfg["site_repo"]).expanduser() if cfg.get("site_repo") else None
            now = detect.detect_all(repo, cfg.get("sitemap_url", "") if (cfg.get("detected") or {}).get("sitemap_shape") else "")
            old = e.get("answer") or {}
            same = (now.get("stack") == old.get("stack")) and (now.get("sitemap") == old.get("sitemap") if now.get("sitemap") else True)
            result = ("OK", summary(now)) if same else ("CHANGED", "was: " + summary(old) + " | now: " + summary(now))
        elif step in ("browser", "region"):
            probs = gate.problems(project, cfg)
            age = (ws.datetime.now().astimezone() - ws.datetime.fromisoformat(e["date"])).days if e.get("date") else 0
            result = ("OK" if not probs else "CHANGED", f"recorded {age} day(s) ago; the code cannot see Chrome: run growth wizard research-check at the start of research"
                      + ("" if not probs else "; " + "; ".join(probs)))
        elif step == "market":
            m = cfg.get("market") or {}
            ok = f"gl={str(m.get('primary_country', '')).lower()}" in m.get("google_params", "") and "pws=0" in m.get("google_params", "")
            result = ("OK", m.get("google_params", "")) if ok else ("CHANGED", f"google_params \"{m.get('google_params')}\" no longer fits the market")
        else:
            result = ("OK", "recorded")
        if result[0] != "OK":
            bad += 1
        say(f"{result[0]:<8} {step}: {result[1]}")
        e["last_check"] = {"date": ws.now(), "result": f"{result[0]}: {result[1]}"[:300]}
        state = ws.load(project)
        state["steps"][step] = {**state["steps"].get(step, {}), "last_check": e["last_check"]}
        ws.save(project, state)
    return 1 if bad else 0


def cmd_repair(project: Path) -> int:
    cfg = cfg_of(project)
    asked = ws.get(project, "harness").get("answer") or {}
    wanted = {"permissions": asked.get("permissions", True) if isinstance(asked, dict) else True,
              "git_hooks": bool(asked.get("git_hooks")) if isinstance(asked, dict) else False}
    for line in install_harness(project, wanted):
        say(line)
    setup_task.ensure(project, cfg)
    todo = [(p, w) for p, s, w, _ in harness.check(project, cfg_of(project)) if s == "todo"]
    for p, w in todo:
        say(f"still missing: {p}: {w}")
    run_doctor(project)
    return 1 if todo else 0


def cmd_research_check(project: Path, connected: str | None, task: str, step: int | None) -> int:
    """At the start of every research step. `connected` is what list_connected_browsers showed (names, comma separated; empty = none)."""
    cfg = cfg_of(project)
    rec = ws.get(project, "browser")
    name = (rec.get("answer") or {}).get("name", "") if isinstance(rec.get("answer"), dict) else ""
    problems = gate.problems(project, cfg)
    if connected is not None and not problems:
        names = [n.strip() for n in connected.split(",") if n.strip()]
        if name not in names:
            ws.record(project, "browser", "asked", test={"command": "list_connected_browsers", "result": ", ".join(names) or "[]"})
            problems = ["the research browser is gone (connected: " + (", ".join(names) or "none") + "): " + gate.fix_browser(name)]
    if not problems:
        say("research browser OK: connected and Google region confirmed for the target market")
        return 0
    for p in problems:
        say("BLOCKED: " + p)
    if task and step:
        subprocess.run([sys.executable, str(KIT_DIR / "tools" / "tasks.py"), "tick", task, str(step), "--status", "blocked",
                        "--output", ("blocked: " + problems[0])[:300]], cwd=project, env={**os.environ, "GROWTH_PROJECT": str(project)})
    return 1


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    sub = argv.pop(0) if argv and argv[0] in ("status", "answer", "confirm", "research-check") else None
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", nargs="*", help="folder (wizard), or: step value (answer), or: browser|region (confirm)")
    ap.add_argument("--site", default="")
    ap.add_argument("--name", default="")
    ap.add_argument("--stack", choices=["static", "nextjs"], default="static")
    ap.add_argument("--answers", default="")
    ap.add_argument("--sitemap", default="")
    ap.add_argument("--yes", action="store_true", help="take the recommended answer for a yes/no question")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--repair", action="store_true")
    ap.add_argument("--seen", default="")
    ap.add_argument("--owner-confirmed", action="store_true")
    ap.add_argument("--connected", default=None)
    ap.add_argument("--task", default="")
    ap.add_argument("--step", type=int, default=None)
    ap.add_argument("--project", default="")
    a = ap.parse_args(argv)
    from config import find_project
    folder = None
    if sub is None and a.what:
        folder = Path(a.what[0]).expanduser().resolve()
    project = folder if folder and (folder / "growth.json").is_file() else (Path(a.project).expanduser().resolve() if a.project else (find_project(folder or Path.cwd())))
    if sub is None and folder and project is None:
        if not a.site:
            sys.exit("a new folder needs --site https://example.com")
        import new_project
        project, _ = new_project.make(folder, a.site, a.name, a.stack, with_harness=False)
        say(f"Project folder made: {project}")
    if project is None:
        sys.exit("No project here: growth wizard <folder> --site https://example.com (or run it inside a project folder)")
    if sub == "status":
        return cmd_status(project)
    if sub == "answer":
        if len(a.what) < 2 or a.what[0] not in ORDER:
            sys.exit(f"growth wizard answer <{'|'.join(ORDER)}> <value>")
        path = project / "setup-answers.json"
        data = json.loads(path.read_text()) if path.is_file() else {}
        data[a.what[0]] = parse_value(" ".join(a.what[1:]))
        path.write_text(json.dumps(data, indent=2) + "\n")
        say(f"recorded the answer for {a.what[0]} (setup-answers.json); run growth wizard to use it")
        return 0
    if sub == "confirm":
        if a.what[:1] == ["browser"]:
            confirm_browser(project, a.name)
            say(f"research browser {a.name} confirmed")
        elif a.what[:1] == ["region"]:
            ok, msg = confirm_region(project, a.seen, a.owner_confirmed)
            say(msg)
            if not ok:
                return 1
        else:
            sys.exit("confirm browser --name \"...\"  |  confirm region --seen \"...\" --owner-confirmed")
        write_setup_md(project)
        run_doctor(project)
        return 0
    if sub == "research-check":
        return cmd_research_check(project, a.connected, a.task, a.step)
    if a.check:
        return cmd_check(project)
    if a.repair:
        return cmd_repair(project)
    answers = {}
    for f in (project / "setup-answers.json", Path(a.answers) if a.answers else None):
        if f and f.is_file():
            answers.update(json.loads(f.read_text()))
    if a.sitemap:
        answers["sitemap"] = a.sitemap
    interactive = sys.stdin.isatty() and sys.stdout.isatty() and not a.answers
    return run(project, Session(project, answers, interactive, a.yes))


if __name__ == "__main__":
    sys.exit(main())
