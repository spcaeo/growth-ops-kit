#!/usr/bin/env python3
"""The owner's journal as one page to look at (from a real project: "where is the owner journal?"; the owner does not
read .md files). Builds journal/owner-journal.html from the three records and opens it in the browser:

  - Your instructions: every owner instruction and what was done (docs/steps-log.md)
  - Your to-dos: the owner's open action items (journal entries of kind "action")
  - Page journal: every finding, question, decision and check, per page (journal/entries.jsonl)

  growth owner_journal          # build and open
  growth owner_journal --no-open

Tabs and the search box live in the address (#tab=...&q=...), so a view can be copied and reopened. Plain local file,
no server, nothing sent anywhere.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import CFG, DOCS, PROJECT, TZ  # noqa: E402

OUT = PROJECT / "journal" / "owner-journal.html"


def steps():
    rows = []
    for line in (DOCS / "steps-log.md").read_text().splitlines():
        if not line.startswith("| I-"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split(" | ")]
        if len(cells) >= 4:
            rows.append({"id": cells[0], "date": cells[1], "said": cells[2], "done": cells[3],
                         "where": cells[4] if len(cells) > 4 else ""})
    return rows[::-1]  # newest first


def entries():
    """Journal entries with answers and status changes folded in (the file is append-only)."""
    out = {}
    f = PROJECT / "journal" / "entries.jsonl"
    for l in (f.read_text().splitlines() if f.is_file() else []):         # a new project has no journal yet
        if not l.strip():
            continue
        e = json.loads(l)
        if e.get("id") in out and e.get("kind") in (None, "answer", "status", "done"):
            out[e["id"]].update({k: v for k, v in e.items() if k not in ("id", "kind")})
        else:
            out.setdefault(e.get("id") or f"x{len(out)}", e)
    return sorted(out.values(), key=lambda e: e.get("at", ""), reverse=True)


def esc(s):
    s = html.escape(str(s or ""))
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    return re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)


def card(title, meta, body, extra="", tags=""):
    return (f'<article class="row" data-text="{html.escape((title + " " + body + " " + meta).lower())}">'
            f'<div class="meta">{meta}</div><h3>{title}</h3><p>{body}</p>{extra}{tags}</article>')


def build():
    st, ens = steps(), entries()
    actions = [e for e in ens if e.get("kind") in ("action", "owner-action") and e.get("status", "open") == "open"]
    tab1 = "".join(card(esc(r["said"]), f'{esc(r["id"])} · {esc(r["date"])}', esc(r["done"]),
                        f'<p class="where">Kept in: {esc(r["where"])}</p>' if r["where"] else "") for r in st)
    tab2 = "".join(card(esc(e.get("title")), f'{esc(e["id"])} · due {esc(e.get("due", "-"))}',
                        esc(e.get("why") or e.get("text")), f'<p class="where">Pages: {esc(", ".join(e.get("pages") or []))}</p>')
                   for e in actions) or "<p>Nothing waiting on you.</p>"
    tab3 = "".join(card(esc(e.get("title")),
                        f'{esc(e.get("id"))} · {esc(e.get("at"))} · <span class="kind k-{esc(e.get("kind"))}">{esc(e.get("kind"))}</span>'
                        + (f' · <span class="open">open</span>' if e.get("status") == "open" else ""),
                        esc(e.get("text") or ""), f'<p class="where">Pages: {esc(", ".join(e.get("pages") or []))}</p>'
                        + (f'<p class="answer">Answer: {esc(e.get("answer"))}</p>' if e.get("answer") else ""))
                   for e in ens if e.get("kind") not in ("action", "owner-action"))
    built = dt.datetime.now(TZ).strftime("%b %-d, %Y %-I:%M %p %Z")
    page = TEMPLATE.replace("{{name}}", CFG.get("name", "Project")).replace("{{built}}", built).replace("{{n1}}", str(len(st))).replace("{{n2}}", str(len(actions))) \
        .replace("{{n3}}", str(len(ens) - len(actions))).replace("{{tab1}}", tab1).replace("{{tab2}}", tab2).replace("{{tab3}}", tab3)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page)
    return OUT


TEMPLATE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{name}} owner journal</title><style>
:root{--bg:#f7f5f0;--card:#fff;--ink:#1d1d1b;--muted:#5f5d57;--line:#e3dfd6;--accent:#b4501c;--link:#1f4fd1}
@media (prefers-color-scheme:dark){:root{--bg:#161614;--card:#201f1c;--ink:#f1efe9;--muted:#b4b0a6;--line:#34322d;--accent:#f08a4b;--link:#8fb0ff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,system-ui,sans-serif}
header{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);padding:14px 16px;z-index:1}
.wrap{max-width:980px;margin:0 auto}h1{font-size:20px;margin:0 0 10px}.sub{color:var(--muted);font-size:13px}
nav{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0}nav button{font:inherit;border:1px solid var(--line);background:var(--card);color:var(--ink);
border-radius:999px;padding:6px 14px;cursor:pointer}nav button[aria-selected=true]{background:var(--ink);color:var(--bg);border-color:var(--ink)}
nav button:hover{border-color:var(--ink)}nav button:focus-visible,input:focus-visible{outline:3px solid var(--link);outline-offset:2px}
input{width:100%;font:inherit;padding:8px 12px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--ink)}
main{padding:16px}.row{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin:0 0 10px}
.row h3{font-size:15px;margin:2px 0 6px}.row p{margin:4px 0}.meta,.where{color:var(--muted);font-size:13px}code{font-size:13px}
.kind{font-weight:600}.open{color:var(--accent);font-weight:600}.answer{border-left:3px solid var(--accent);padding-left:8px}
[hidden]{display:none!important}</style></head><body>
<header><div class="wrap"><h1>{{name}} owner journal</h1><div class="sub">Built {{built}} · newest first</div>
<nav role="tablist"><button role="tab" data-tab="instructions">Your instructions ({{n1}})</button>
<button role="tab" data-tab="todos">Your to-dos ({{n2}})</button><button role="tab" data-tab="pages">Page journal ({{n3}})</button></nav>
<input type="search" id="q" placeholder="Search the journal" aria-label="Search the journal"></div></header>
<main class="wrap"><section data-panel="instructions">{{tab1}}</section><section data-panel="todos">{{tab2}}</section>
<section data-panel="pages">{{tab3}}</section></main>
<script>
const q=document.getElementById('q');
function state(){const h=new URLSearchParams(location.hash.slice(1));return{tab:h.get('tab')||'instructions',q:h.get('q')||''}}
function apply(){const s=state();q.value=s.q;document.querySelectorAll('[role=tab]').forEach(b=>b.setAttribute('aria-selected',b.dataset.tab===s.tab));
document.querySelectorAll('[data-panel]').forEach(p=>{p.hidden=p.dataset.panel!==s.tab;
p.querySelectorAll('.row').forEach(r=>r.hidden=!!s.q&&!r.dataset.text.includes(s.q.toLowerCase()))})}
function go(tab,qq){const h=new URLSearchParams();h.set('tab',tab);if(qq)h.set('q',qq);history.pushState(null,'','#'+h);apply()}
document.querySelectorAll('[role=tab]').forEach(b=>b.onclick=()=>go(b.dataset.tab,q.value));
q.oninput=()=>{const h=new URLSearchParams();h.set('tab',state().tab);if(q.value)h.set('q',q.value);history.replaceState(null,'','#'+h);apply()};
addEventListener('popstate',apply);apply();
</script></body></html>
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-open", action="store_true")
    a = ap.parse_args()
    out = build()
    print(f"built {out}")
    if not a.no_open:
        subprocess.run(["open", str(out)], check=False)


if __name__ == "__main__":
    main()
