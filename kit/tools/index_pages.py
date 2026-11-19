#!/usr/bin/env python3
"""After the page is live, get it indexed (release playbook step 9).

  growth index <url...> [--refresh] [--dry-run]   send pages to the indexing provider named in growth.json "indexing"
  growth index status                              ask the provider how each submitted job went; update what Google shows
  growth index report                              every page, what was sent, "Google sees the page: yes/no since <date>", credits
  growth index setup                               (freshlycited) add the sitemap and the IndexNow site, verify the IndexNow key

Providers, set in growth.json:

  "indexing": {"provider": "freshlycited" | "indexnow" | "manual" | "off",
               "keys_file": "~/.config/growth/site.env",      # outside git; else the project's keys_file is used
               "key_name": "FRESHLYCITED_API_KEY",            # the line in that file holding the key (never printed)
               "max_pages_per_day": 50,                        # a hard cap on pages sent in one day (default 50)
               "sitemap": "https://example.com/sitemap.xml",   # for `growth index setup`
               "indexnow_key": "...", "indexnow_key_location": "https://example.com/<key>.txt"}

  freshlycited  FreshlyCited (freshlycited.com), the built-in option: MCP/API at https://freshlycited.com/mcp. Smart mode checks
                Google first and sends only pages Google does not show; a credit is used only if Google indexes the page.
                --refresh re-sends updated pages: 1 credit each, spent even if nothing changes, no credit back (the cost is
                printed first).
  indexnow      free; Bing and the other IndexNow engines only (not Google). Needs the key file the site hosts.
  manual        prints the Search Console "Request indexing" steps for each URL.

Off until configured. The estimated spend is printed before every paid call. Results are kept in <project>/indexing/state.json
and as journal notes tagged `indexing`; `growth measure` shows "Google sees the page" before it judges traffic. Pages must be on
the site's own host. The key is read from the keys file and is never printed, logged or written anywhere.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit
import urllib.error
import urllib.request

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import atomic  # noqa: E402
import paths  # noqa: E402

DEFAULT_ENDPOINT = "https://freshlycited.com/mcp"
DEFAULT_KEY_NAME = "FRESHLYCITED_API_KEY"
INDEXNOW_ENDPOINT = "https://api.indexnow.org/indexnow"
DEFAULT_CAP = 50
PROVIDERS = ("freshlycited", "indexnow", "manual")
FINAL_JOB = {"completed", "complete", "done", "finished", "failed", "cancelled", "canceled", "error"}
# per-page words the provider may use: Google shows the page (already, or after the send), or not yet
SEEN = {"indexed", "already_indexed", "google_indexed", "in_google", "success", "succeeded", "skipped_indexed", "skipped"}
STEPS_MANUAL = ("Open Search Console for the site (the owner's own account), choose the property.",
                "Paste the full address into the search bar at the top ('Inspect any URL').",
                "Wait for the result, then press 'Request indexing' (it can take a minute). Leave the tab open until it says 'Indexing requested'.",
                "Search Console allows only a small number of these a day: do the money pages first.")


def fail(msg):
    raise SystemExit(f"index: {msg}")


# ---- the project's state -------------------------------------------------------------------------------------------

def state_path(project) -> Path:
    return Path(project) / "indexing" / "state.json"


def load_state(project) -> dict:
    return atomic.read_json(state_path(project), {"pages": {}, "days": {}}) or {"pages": {}, "days": {}}


def today() -> dt.date:
    return dt.date.today()


def sent_today(project) -> int:
    return int(load_state(project).get("days", {}).get(today().isoformat(), 0))


def _page(st, url):
    return st["pages"].setdefault(paths.key(url), {"url": url, "submissions": [], "google_sees": None, "google_sees_since": "",
                                                   "last_checked": ""})


def record_submission(project, urls, provider, mode, job_id="", note=""):
    day = today().isoformat()

    def change(st):
        st.setdefault("pages", {})
        st.setdefault("days", {})
        for u in urls:
            p = _page(st, u)
            p["url"] = u
            p["submissions"].append({"at": day, "provider": provider, "mode": mode, "job_id": job_id, "note": note})
        if provider != "manual":
            st["days"][day] = int(st["days"].get(day, 0)) + len(urls)
        return st
    atomic.update_json(state_path(project), change, {"pages": {}, "days": {}})


def mark_seen(project, url, seen: bool):
    day = today().isoformat()

    def change(st):
        p = _page(st, url)
        p["last_checked"] = day
        if seen and not p.get("google_sees"):
            p["google_sees"], p["google_sees_since"] = True, day
        elif not seen and p.get("google_sees") is None:
            p["google_sees"] = False
        return st
    atomic.update_json(state_path(project), change, {"pages": {}, "days": {}})


def google_sees(project, page) -> dict:
    """What `growth measure` shows before it judges traffic: {"sees": True|False|None, "since": str, "text": str}."""
    p = (load_state(project).get("pages") or {}).get(paths.key(page))
    if not p or not p.get("submissions"):
        return {"sees": None, "since": "", "text": "Google sees the page: unknown (growth index has not run for this page; traffic cannot be judged until it is in Google)"}
    if p.get("google_sees"):
        return {"sees": True, "since": p["google_sees_since"], "text": f"Google sees the page: yes since {p['google_sees_since']}"}
    first = p["submissions"][0]["at"]
    return {"sees": False, "since": "", "text": f"Google sees the page: no (sent {first}, not shown yet; do not judge its traffic yet, run growth index status)"}


def journal(project, url, title, text=""):
    r = subprocess.run([sys.executable, str(HERE / "journal.py"), "add", "--page", paths.key(url), "--kind", "note", "--tag", "indexing",
                        "--title", title[:90], "--text", text], capture_output=True, text=True, env={**os.environ, "GROWTH_PROJECT": str(project)})
    if r.returncode:
        print(f"note: the journal entry was not written ({(r.stderr or r.stdout).strip().splitlines()[-1:] or ['unknown']})", file=sys.stderr)


# ---- the FreshlyCited MCP client --------------------------------------------------------------------------------------

def check_endpoint(endpoint):
    u = urlsplit(endpoint)
    if u.scheme == "https" or (u.scheme == "http" and u.hostname in ("127.0.0.1", "localhost", "::1")):
        return
    fail("the endpoint must be https (http only for 127.0.0.1); the key is never sent in clear text")


def _decode(body: bytes, ctype: str, want_id):
    text = body.decode("utf-8", "replace")
    if "text/event-stream" in (ctype or ""):
        found = None
        for line in text.splitlines():
            if line.startswith("data:"):
                try:
                    msg = json.loads(line[5:].strip())
                except ValueError:
                    continue
                if isinstance(msg, dict) and ("result" in msg or "error" in msg) and (want_id is None or msg.get("id") == want_id):
                    return msg
                found = found or msg
        return found
    return json.loads(text) if text.strip() else None


class Mcp:
    """A small Streamable-HTTP MCP client: initialize, notifications/initialized, tools/call. Keeps Mcp-Session-Id."""

    def __init__(self, endpoint, key, timeout=60):
        check_endpoint(endpoint)
        self.endpoint, self._key, self.timeout, self.session, self._id = endpoint, key, timeout, "", 0

    def _redact(self, s):
        return str(s).replace(self._key, "***") if self._key else str(s)

    def _post(self, payload, want_id=None):
        h = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream", "Authorization": f"Bearer {self._key}",
             "MCP-Protocol-Version": "2025-03-26"}
        if self.session:
            h["Mcp-Session-Id"] = self.session
        req = urllib.request.Request(self.endpoint, data=json.dumps(payload).encode(), headers=h, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                self.session = r.headers.get("Mcp-Session-Id") or self.session
                return _decode(r.read(), r.headers.get("Content-Type", ""), want_id)
        except urllib.error.HTTPError as e:
            fail(f"the provider answered HTTP {e.code}" + (" (the key was refused: check the keys file)" if e.code in (401, 403) else ""))
        except (urllib.error.URLError, OSError) as e:
            fail(f"could not reach the provider: {self._redact(getattr(e, 'reason', e))}")

    def start(self):
        self._id += 1
        msg = self._post({"jsonrpc": "2.0", "id": self._id, "method": "initialize",
                          "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "growth-ops-kit", "version": "1"}}}, self._id)
        if not msg or "error" in msg:
            fail("the provider refused to start a session")
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return self

    def call(self, name, args=None):
        self._id += 1
        msg = self._post({"jsonrpc": "2.0", "id": self._id, "method": "tools/call", "params": {"name": name, "arguments": args or {}}}, self._id)
        if not msg:
            fail(f"{name}: empty answer")
        if "error" in msg:
            fail(f"{name}: {self._redact((msg['error'] or {}).get('message', 'error'))}")
        res = msg.get("result") or {}
        out = res.get("structuredContent")
        if out is None:
            txt = "\n".join(c.get("text", "") for c in res.get("content") or [] if isinstance(c, dict))
            try:
                out = json.loads(txt)
            except ValueError:
                out = {"text": txt}
        if res.get("isError"):
            fail(f"{name}: {self._redact((out or {}).get('text') or (out or {}).get('error') or 'the tool reported an error')}"[:300])
        return out


def read_key(project, cfg, name):
    from config import parse_keys, resolve_in
    ix = cfg.get("indexing") or {}
    kf = ix.get("keys_file") or cfg.get("keys_file")
    if not kf:
        return ""
    p = resolve_in(Path(project), kf)
    if not p.is_file():
        return ""
    return parse_keys(p.read_text()).get(name, "").strip().strip("'\"")


def connect(project, cfg):
    ix = cfg.get("indexing") or {}
    key = read_key(project, cfg, ix.get("key_name") or DEFAULT_KEY_NAME)
    if not key:
        fail(f"no key: put {ix.get('key_name') or DEFAULT_KEY_NAME}=<key> in the keys file named in growth.json (indexing.keys_file or keys_file), mode 600")
    return Mcp(ix.get("endpoint") or DEFAULT_ENDPOINT, key).start()


# ---- results of a job -------------------------------------------------------------------------------------------------

def find_job_id(out):
    if isinstance(out, dict):
        for k in ("job_id", "jobId", "id"):
            if out.get(k):
                return str(out[k])
        for v in out.values():
            if isinstance(v, dict):
                j = find_job_id(v)
                if j:
                    return j
    return ""


def job_urls(out):
    items = out if isinstance(out, list) else next((out[k] for k in ("urls", "items", "results", "pages") if isinstance(out, dict) and isinstance(out.get(k), list)), [])
    rows = []
    for it in items:
        if isinstance(it, str):
            rows.append((it, False, ""))
        elif isinstance(it, dict) and it.get("url"):
            status = str(it.get("status") or it.get("state") or "").lower()
            seen = it.get("indexed") in (True, 1) or it.get("google_indexed") in (True, 1) or status in SEEN   # the provider sends 1/0
            rows.append((it["url"], seen, status))
    return rows


# ---- commands -----------------------------------------------------------------------------------------------------------

def clean_urls(raw, cfg):
    site = urlsplit(cfg.get("site_url", ""))
    out = []
    for u in raw:
        p = urlsplit(u)
        if p.scheme not in ("http", "https") or not p.netloc:
            fail(f"{u}: give the full address, e.g. {site.scheme or 'https'}://{site.netloc or 'example.com'}/page")
        if site.netloc and p.netloc.lower() != site.netloc.lower():
            fail(f"{u}: not on the site's own host ({site.netloc}); only this site's pages are sent")
        u2 = p._replace(fragment="").geturl()
        if u2 not in out:
            out.append(u2)
    return out


def cmd_index(project, cfg, raw_urls, refresh=False, dry=False, say=print):
    ix = cfg.get("indexing") or {}
    prov = (ix.get("provider") or "off").lower()
    if prov not in PROVIDERS:
        say("indexing is off. To turn it on, set growth.json \"indexing\": {\"provider\": \"freshlycited\" | \"indexnow\" | \"manual\"} "
            "(growth wizard indexing walks through it). Free options: indexnow (Bing and others), manual (Search Console).")
        return 0
    urls = clean_urls(raw_urls, cfg)
    if not urls:
        fail("give at least one page address")
    cap = int(ix.get("max_pages_per_day") or DEFAULT_CAP)
    used = sent_today(project)
    if prov != "manual" and used + len(urls) > cap:
        fail(f"daily cap: {used} pages already sent today, {len(urls)} more would pass {cap} (growth.json indexing.max_pages_per_day). Send fewer, or tomorrow.")
    if prov == "manual":
        for u in urls:
            say(f"\nRequest indexing for {u}")
            for i, s in enumerate(STEPS_MANUAL, 1):
                say(f"  {i}. {s}")
        if not dry:
            record_submission(project, urls, "manual", "manual")
            for u in urls:
                journal(project, u, f"Indexing: manual steps printed for {u}")
        return 0
    if prov == "indexnow":
        say(f"IndexNow (free): {len(urls)} page(s) go to Bing and the other IndexNow engines. Google does not use IndexNow; for Google use freshlycited or manual.")
        if dry:
            return 0
        send_indexnow(project, cfg, urls)
        record_submission(project, urls, "indexnow", "indexnow")
        for u in urls:
            journal(project, u, f"Indexing: sent to IndexNow ({u})")
        say(f"sent {len(urls)} page(s) to IndexNow")
        return 0
    n = len(urls)
    if refresh:
        say(f"COST: --refresh sends {n} page(s) again: {n} credit(s) (1 per page), spent even if nothing changed, no credit back.")
    else:
        say(f"COST: smart mode checks {n} page(s) on Google first and sends only the ones Google does not show. A credit is used only if Google "
            f"indexes a page, so at most {n} credit(s), and none for pages already in Google.")
    if dry:
        say("dry run: nothing sent")
        return 0
    mcp = connect(project, cfg)
    try:
        bal = mcp.call("get_credits")
        say(f"credits before: {_credits(bal)}")
        left = _credits_int(bal)
        if refresh and left is not None and left < n:
            fail(f"--refresh needs {n} credit(s) and only {left} are left")
    except SystemExit as e:
        if refresh:
            raise
        say(f"note: could not read the credit balance ({e})")
    args = {"urls": urls, "smart": True, "name": f"growth {urlsplit(cfg.get('site_url', '')).netloc} {today().isoformat()}"}
    if refresh:
        args["force_refresh"] = True
    out = mcp.call("submit_index_job", args)
    job = find_job_id(out)
    record_submission(project, urls, "freshlycited", "refresh" if refresh else "smart", job)
    for u in urls:
        journal(project, u, f"Indexing: sent to FreshlyCited ({'refresh' if refresh else 'smart'}, job {job or 'n/a'})", f"{u}")
    say(f"sent {n} page(s) to FreshlyCited, job {job or '(no id returned)'}. Later: growth index status")
    return 0


def _credits(out):
    n = _credits_int(out)
    return str(n) if n is not None else "unknown"


def _credits_int(out):
    if isinstance(out, dict):
        for k in ("credits", "balance", "credits_remaining", "remaining"):
            if isinstance(out.get(k), (int, float)):
                return int(out[k])
        for v in out.values():
            if isinstance(v, dict):
                n = _credits_int(v)
                if n is not None:
                    return n
    return None


def send_indexnow(project, cfg, urls):
    ix = cfg.get("indexing") or {}
    key = ix.get("indexnow_key") or read_key(project, cfg, "INDEXNOW_KEY")
    if not key:
        fail("no IndexNow key: set indexing.indexnow_key (the key file the site hosts) or INDEXNOW_KEY in the keys file")
    host = urlsplit(cfg.get("site_url", "")).netloc
    loc = ix.get("indexnow_key_location") or f"https://{host}/{key}.txt"
    endpoint = ix.get("indexnow_endpoint") or INDEXNOW_ENDPOINT
    check_endpoint(endpoint)
    body = json.dumps({"host": host, "key": key, "keyLocation": loc, "urlList": urls}).encode()
    req = urllib.request.Request(endpoint, data=body, headers={"Content-Type": "application/json; charset=utf-8"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            if r.status not in (200, 202):
                fail(f"IndexNow answered {r.status}")
    except urllib.error.HTTPError as e:
        fail(f"IndexNow answered HTTP {e.code}" + (" (the key file is not found at the key location, or the key is wrong)" if e.code in (403, 422) else ""))
    except (urllib.error.URLError, OSError) as e:
        fail(f"could not reach IndexNow: {getattr(e, 'reason', e)}")


def cmd_status(project, cfg, say=print):
    st = load_state(project)
    jobs = {}
    for k, p in st.get("pages", {}).items():
        for s in p.get("submissions", []):
            if s.get("provider") == "freshlycited" and s.get("job_id"):
                jobs.setdefault(s["job_id"], []).append(p["url"])
    if not jobs:
        say("no FreshlyCited jobs to check (growth index <url> sends pages first)")
        return 0
    mcp = connect(project, cfg)
    for job, urls in jobs.items():
        info = mcp.call("get_job_status", {"job_id": job})
        state = str((info or {}).get("status") or (info or {}).get("state") or "unknown").lower()
        say(f"job {job}: {state}")
        rows = job_urls(mcp.call("list_job_urls", {"job_id": job}))
        for u, seen, word in rows:
            mark_seen(project, u, seen)
            if seen:
                journal(project, u, f"Indexing: Google sees {u}", f"job {job}: {word or 'indexed'}")
            say(f"  {'yes' if seen else 'no ':<3} {u}  ({word or 'not shown yet'})")
    return 0


def cmd_report(project, cfg, say=print):
    st = load_state(project)
    pages = st.get("pages", {})
    if not pages:
        say("nothing sent yet: growth index <url...>")
        return 0
    for k, p in sorted(pages.items()):
        g = google_sees(project, k)
        last = p["submissions"][-1] if p["submissions"] else {}
        say(f"{p['url']}\n  {g['text']}\n  last sent {last.get('at', '-')} via {last.get('provider', '-')} ({last.get('mode', '-')})"
            + (f", job {last['job_id']}" if last.get("job_id") else "") + f"; {len(p['submissions'])} send(s)")
    say(f"pages sent today: {sent_today(project)} of {int((cfg.get('indexing') or {}).get('max_pages_per_day') or DEFAULT_CAP)}")
    if ((cfg.get("indexing") or {}).get("provider") or "") == "freshlycited":
        try:
            say(f"FreshlyCited credits: {_credits(connect(project, cfg).call('get_credits'))}")
        except SystemExit as e:
            say(f"FreshlyCited credits: not read ({e})")
    return 0


def cmd_setup(project, cfg, say=print, verify=True):
    """FreshlyCited: add the sitemap and the IndexNow site, then verify the IndexNow key. Free calls."""
    ix = cfg.get("indexing") or {}
    site = cfg.get("site_url", "").rstrip("/")
    mcp = connect(project, cfg)
    sm = ix.get("sitemap") or f"{site}/sitemap.xml"
    say(f"sitemap: {_brief(mcp.call('add_sitemap', {'url': sm}))}")
    key = ix.get("indexnow_key") or read_key(project, cfg, "INDEXNOW_KEY")
    if key:
        args = {"url": site, "key": key}
        if ix.get("indexnow_key_location"):
            args["key_location"] = ix["indexnow_key_location"]
        say(f"IndexNow site: {_brief(mcp.call('add_indexnow_site', args))}")
        if verify:
            say(f"IndexNow verify: {_brief(mcp.call('verify_indexnow_site', {'url': site}))}")
    else:
        say("IndexNow: skipped (no indexnow_key)")
    return 0


def _brief(out):
    return (json.dumps(out) if not isinstance(out, dict) or "text" not in out else out["text"])[:160]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", nargs="+", help="page addresses, or: status | report | setup")
    ap.add_argument("--refresh", action="store_true", help="re-send updated pages (1 credit each, no credit back)")
    ap.add_argument("--dry-run", action="store_true", help="print what would be sent and the cost, send nothing")
    a = ap.parse_args(argv)
    import config
    project = config.require_project()
    cfg = config.load_cfg(project)
    first = a.what[0]
    if first in ("status", "report", "setup") and len(a.what) == 1:
        prov = ((cfg.get("indexing") or {}).get("provider") or "off").lower()
        if first == "report":
            return cmd_report(project, cfg)
        if prov != "freshlycited":
            print(f"growth index {first} needs indexing.provider \"freshlycited\" in growth.json (now: {prov})")
            return 0
        return cmd_status(project, cfg) if first == "status" else cmd_setup(project, cfg)
    return cmd_index(project, cfg, a.what, a.refresh, a.dry_run)


if __name__ == "__main__":
    sys.exit(main())
