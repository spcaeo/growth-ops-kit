"""Daily AI summary of the insights (runs after `tracker.py report`, which writes insights-digest.json).

OFF by default (growth.json: ai_summary.on). Modes: "mock" writes a fixed plain note with no model call; "claude" runs
the smallest model (config ai_summary.model, claude-haiku-5-5). Nothing is paid for until the owner switches it on.
When on in "claude" mode it runs Claude Code headless with no tools at all (`--tools ""`, no MCP servers, no saved session): it only reads the
digest given on stdin and writes plain text. The result goes to insights.md and insights.json (with its date), which
the dashboard's Insights view shows as the "Why it moved" and "What to do next" lines marked AI. Every number in the summary is checked
against the digest; numbers not found there are listed as unverified.
  python3 ai_summary.py
"""
import json, os, re, shutil, subprocess, datetime as dt
import config

import config
HERE = config.HERE      # the project's page-tracker data folder
PROMPT = """You write two short notes for the owner of {site}, shown on the dashboard under the headline and the cards.
The headline already says whether we are winning or losing, and the cards already show the numbers. Your job is only
WHY the numbers moved and WHAT TO DO NEXT. The JSON on stdin is the only source. Rules:
- Do not repeat the cards' numbers or list figures. Name causes and actions in words. Use a number only when the point
  needs it (a date, or one figure that explains a cause), at most one per bullet, and only numbers that appear in the JSON.
- Causes to weigh, in this order: our own changes (our_change_days), Google's own updates (google_updates; a core update
  that is still rolling out moves rankings for every site), the long-term trend and the time of year (last_weeks, trend),
  provisional Google days (the newest 2 to 3 days are not final), pages Google has not indexed yet.
- cross_check compares Google clicks with Skald's search-engine visits and all readers over the same whole days. Mention
  it only when a scope is marked unusual, and give the likely reason from its note (Bing and others, time zones,
  provisional days, blocked tracking). time_on_page says whether people stay longer after our changes; mention it only
  when both sides have a median.
- conversions: leads (forms) for the whole site a day before vs after, and visits proven to have sent a form on the
  changed pages. Follow its verdict; if Skald could not tie leads to pages, say that leads cannot be credited to our
  changes yet.
- competing_pages: searches where two of our pages compete. low_click_rate: pages clicked far less than their positions
  usually get here. Name at most the top one or two of each in "What to do next" (which page should own a search; which
  title and description to rewrite).
- Follow the verdicts in the JSON: if a verdict is "too early", say it is too early; never call a too-early move a win or a loss.
- Simple English, short sentences, no jargon.
- Exactly these two sections as markdown headings, 2 to 4 bullets each, one sentence per bullet:
## Why
## What to do next
- "What to do next" gives concrete, low-risk actions (for example: wait until a date, request indexing for named pages,
  look at a named page or search).
- No preamble, no closing line. At most 140 words."""


def numbers(text):
    return [n.replace(",", "") for n in re.findall(r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?", text)]


def check(summary, digest_text):
    """Numbers in the summary that do not appear in the digest (as written, rounded, or as a percent of a fraction)."""
    have = set()
    for n in numbers(digest_text):
        try:
            f = float(n)
        except ValueError:
            continue
        for v in (f, f * 100, abs(f), abs(f) * 100):
            have.update({str(round(v)), str(round(v, 1)), str(round(v, 2)), f"{v:g}"})
    bad = []
    for n in numbers(summary):
        try:
            f = float(n)
        except ValueError:
            continue
        if n in have or f"{f:g}" in have or str(round(f)) in have and float(n).is_integer() is False:
            continue
        if 1 <= f <= 31 or 2000 <= f <= 2100:  # day numbers and years from the dates in the digest
            continue
        bad.append(n)
    return sorted(set(bad))


def main():
    digest_path = os.path.join(HERE, "insights-digest.json")
    out = dict(date=dt.date.today().isoformat(), built=dt.datetime.now().astimezone().isoformat(timespec="minutes"))
    claude = shutil.which("claude")
    if not config.AI.get("on"):
        out["error"] = "The AI summary is off until the owner switches it on (growth.json: ai_summary.on)."
    elif config.AI.get("mode", "mock") == "mock":
        out["text"] = ("## Why\n- (mock note, no model was called) The numbers on the cards are the facts; this text only shows where the AI notes will appear.\n"
                       "## What to do next\n- (mock note) Connect Search Console so there is something to explain.")
        out["mock"] = True
    elif not claude:
        out["error"] = "Claude Code (claude) is not available here, so no AI summary today."
    else:
        digest = open(digest_path, encoding="utf-8").read()
        try:
            r = subprocess.run([claude, "-p", PROMPT.replace("{site}", config.SITE_HOST), "--model", config.AI.get("model", "claude-haiku-5-5"), "--tools", "", "--strict-mcp-config", "--no-session-persistence",
                                "--output-format", "text"], input=digest, capture_output=True, text=True, timeout=300, cwd=HERE)
            text = r.stdout.strip()
            if r.returncode or not text:
                out["error"] = f"claude exited {r.returncode}: {(r.stderr or text)[:300]}"
            else:
                out["text"] = text
                out["unverified_numbers"] = check(text, digest)
        except subprocess.TimeoutExpired:
            out["error"] = "claude took longer than 5 minutes; no AI summary today."
    config.save_json(os.path.join(HERE, "insights.json"), out, indent=1)
    md = f"# AI summary, {out['date']}\n\nAI summary, check the numbers on the dashboard.\n\n" + (out.get("text") or out.get("error", ""))
    if out.get("unverified_numbers"):
        md += "\n\nNumbers not found in the data: " + ", ".join(out["unverified_numbers"])
    open(os.path.join(HERE, "insights.md"), "w", encoding="utf-8").write(md + "\n")
    print("ai summary:", "ok" if out.get("text") else out.get("error"), "| unverified:", out.get("unverified_numbers"))


CLUSTER_PROMPT = """You write ONE line (at most 40 words) for the owner of {site} about one cluster of pages on the site,
shown under that cluster's key findings. The findings already state the numbers. Say only why it moved and the single
most useful next step. Use only what is in the JSON on stdin; use at most one number, and only one that appears in it.
If the verdict is too early, say so; never call a too-early move a win or a loss. Simple English. No heading, no bullet,
no preamble."""


def clusters_main():
    """One 'why and what next' line per sitemap cluster (cluster-digests.json, written by tracker.py report), same
    no-tools mode and number check as the summary; written to cluster-notes.json."""
    path = os.path.join(HERE, "cluster-digests.json")
    out = dict(date=dt.date.today().isoformat(), notes={})
    claude = shutil.which("claude")
    if not config.AI.get("on"):
        out["error"] = "The AI summary is off until the owner switches it on (growth.json: ai_summary.on)."
    elif config.AI.get("mode", "mock") == "mock":
        out["error"] = "mock mode: no cluster notes written, no model called"
    elif not os.path.exists(path) or not claude:
        out["error"] = "no cluster digests yet" if claude else "Claude Code (claude) is not available here."
    else:
        for cid, dg in json.load(open(path, encoding="utf-8")).items():
            text = json.dumps(dg, indent=1)
            try:
                r = subprocess.run([claude, "-p", CLUSTER_PROMPT.replace("{site}", config.SITE_HOST), "--model", config.AI.get("model", "claude-haiku-5-5"), "--tools", "", "--strict-mcp-config", "--no-session-persistence",
                                    "--output-format", "text"], input=text, capture_output=True, text=True, timeout=180, cwd=HERE)
                line = r.stdout.strip().splitlines()[0].strip() if r.stdout.strip() else ""
                out["notes"][cid] = dict(text=line, unverified_numbers=check(line, text)) if line and not r.returncode else dict(error=f"claude exited {r.returncode}")
            except subprocess.TimeoutExpired:
                out["notes"][cid] = dict(error="took longer than 3 minutes")
    config.save_json(os.path.join(HERE, "cluster-notes.json"), out, indent=1)
    print("cluster notes:", len(out["notes"]), out.get("error") or "")


if __name__ == "__main__":
    main()
    clusters_main()
