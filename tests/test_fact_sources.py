"""ev.fact-sources: every stat on a page is the project's own claim or a fresh fact row read on a real page (never a chat or a
Google results page); `growth research fact` refuses a banned source. Invented vendors and example.com only; no network."""
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import fact_sources  # noqa: E402
import research  # noqa: E402
from test_research_record import ctx_for, d, fact, rec, run  # noqa: E402

PAGE = "<html><body><nav><a href='/'>Home 24 hours</a></nav><main><h1>Boards</h1>{}</main><footer><p>&copy; 2026 Acme. All rights reserved.</p></footer></body></html>"
STAT = "Acme cuts review time by 45% for most teams."


def page(*paras):
    return PAGE.format("".join(f"<p>{p}</p>" for p in paras))


def row(**kw):
    return fact(fact="review time", value="45%", shown_as="45%", quote="Teams cut review time by 45 percent.", **kw)


def go(tmp_path, html, facts, **kw):
    return run("ev.fact-sources", ctx_for(tmp_path, rec(vendor_facts=facts), html=html, **kw))


def test_a_sourced_stat_passes(tmp_path):
    assert go(tmp_path, page(STAT), [row()]).level == "OK"


def test_an_unsourced_stat_fails_and_names_the_sentence(tmp_path):
    ln = go(tmp_path, page(STAT), [fact()])
    assert ln.level == "FAIL" and "'45%'" in ln.what and "Acme cuts review time by 45%" in ln.what and "no fact row" in ln.what


def test_chat_and_results_pages_are_never_a_source(tmp_path):
    for url in ("https://chatgpt.com/share/abc", "https://www.perplexity.ai/search/x", "https://gemini.google.com/app/1",
                "https://www.google.com/search?q=hipaa&udm=50", "https://claude.ai/chat/1"):
        ln = go(tmp_path, page(STAT), [row(source_url=url)])
        assert ln.level == "FAIL" and "is not a source" in ln.what, url
    assert go(tmp_path, page(STAT), [row(source_url="https://www.hhs.example.gov/hipaa")]).level == "OK"


def test_a_stale_row_fails(tmp_path):
    ln = go(tmp_path, page(STAT), [row(read_on=d(91))])
    assert ln.level == "FAIL" and "91 days ago" in ln.what
    assert go(tmp_path, page(STAT), [row(read_on=d(89))]).level == "OK"
    assert go(tmp_path, page(STAT), [row(read_on=d(91))], cfg={"research": {"fact_max_age_days": 120}}).level == "OK"


def test_a_summary_row_fails_and_comma_numbers_match(tmp_path):
    assert go(tmp_path, page(STAT), [row(how_read="summary")]).level == "FAIL"
    p = page("Over 1,000 clinics use it daily.")
    assert go(tmp_path, p, [fact(quote="more than 1000 clinics", value="1000")]).level == "OK"


def test_a_brand_claim_passes_but_a_never_line_does_not(tmp_path):
    (tmp_path / "BRAND.md").write_text("# Brand\n- Every call is a 30-minute call.\n- Never claim 99% uptime.\n")
    p = page("Book a 30 minute call.", "We promise 99% uptime.")
    ln = go(tmp_path, p, [])
    assert ln.level == "FAIL" and "'99%'" in ln.what and "30 minute" not in ln.what


def test_chrome_byline_and_copyright_are_ignored_and_regulations_need_a_row(tmp_path):
    p = PAGE.format("<p class='byline'>Updated 3 days ago by Sam</p><p>Plain words only.</p><p>The rule is 45 CFR 164.</p>")
    ln = go(tmp_path, p, [])
    assert ln.level == "FAIL" and "45 CFR" in ln.what and "24 hours" not in ln.what and "2026" not in ln.what
    assert go(tmp_path, p, [fact(quote="Under 45 CFR Part 164 a covered entity", value="45 CFR 164")]).level == "OK"


def test_a_page_with_no_stats_passes_without_a_record(tmp_path):
    assert run("ev.fact-sources", ctx_for(tmp_path, None, html=page("Plain words only."))).level == "OK"


def test_the_banned_list_can_be_replaced_or_extended():
    assert fact_sources.banned_entry("https://chatgpt.com/c/1") and fact_sources.banned_entry("https://example.com/") is None
    assert fact_sources.banned_entry("https://example.com/x", {"research": {"banned_sources_extra": ["example.com/x"]}})
    assert fact_sources.banned_entry("https://chatgpt.com/c/1", {"research": {"banned_sources": ["other.example"]}}) is None
    assert research.settings({}) and fact_sources.banned_entry("https://www.google.com/search?q=a")
    assert fact_sources.banned_entry("https://www.google.com/maps") is None


def cli(p, *args):
    return subprocess.run([sys.executable, str(Path(research.__file__)), *args], capture_output=True, text=True,
                          env={**os.environ, "GROWTH_PROJECT": str(p), "HOME": str(p.parent / "home")}, cwd=p)


def test_growth_research_fact_refuses_a_banned_source(tmp_path):
    p = tmp_path / "p"
    (p / "docs").mkdir(parents=True)
    (p / "growth.json").write_text(json.dumps({"name": "T", "site_url": "https://t.example"}))
    assert cli(p, "init", "/pm", "--key", "pm").returncode == 0
    args = ("fact", "/pm", "--key", "pm", "--vendor", "Acme", "--fact", "f", "--value", "45%", "--view", "page", "--how", "browser", "--quote", "45 percent")
    r = cli(p, *args, "--source-url", "https://chatgpt.com/share/1")
    assert r.returncode != 0 and "ChatGPT is not a source: open the real page and quote it" in r.stderr
    r = cli(p, *args, "--source-url", "https://www.google.com/search?q=acme")
    assert r.returncode != 0 and "not a source" in r.stderr
    assert json.loads((p / "research" / "pm-record.json").read_text())["vendor_facts"] == []
    assert cli(p, *args, "--source-url", "https://acme.example.com/p").returncode == 0
