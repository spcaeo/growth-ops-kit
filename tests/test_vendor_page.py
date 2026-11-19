"""growth vendor_page reads a vendor page's raw text and embedded data, never through a summariser (#43): the exact quoted
line, both billing views, the page's toggles, and a fact filed only when the value is inside the vendor's own words.
A saved page and an invented vendor; no network."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "kit" / "tools"
sys.path.insert(0, str(TOOLS))
import vendor_page  # noqa: E402

PAGE = """<html><head><script type="application/json" id="__NEXT_DATA__">{"plans":[{"name":"Pro","price":"$30 user / mo, billed annually"}]}</script></head>
<body><div class="banner">Our recommendation: at least 25 users for best results.</div>
<div role="tablist"><button role="tab" aria-selected="true">Yearly</button><button role="tab" aria-selected="false">Monthly</button></div>
<select><option>USD</option><option>CAD</option></select><label>Self-hosted</label>
<div class="plan"><h3>Basic</h3><p>$12 user / mo · billed monthly</p><p>Minimum 5 users</p></div></body></html>"""


def test_the_plan_line_is_quoted_from_the_text_and_the_embedded_data():
    rows = vendor_page.find(PAGE, "Basic")
    assert any("Minimum 5 users" in r["quote"] and r["from"] == "page text" for r in rows)
    pro = vendor_page.find(PAGE, "Pro")
    assert any(r["from"] == "embedded data" and "$30" in r["quote"] for r in pro)        # the price a summary missed
    assert vendor_page.view_hint("$12 user / mo · billed monthly") == "Monthly"
    assert vendor_page.view_hint("$10 user / mo, billed annually") == "Yearly"


def test_the_pages_toggles_are_listed_so_every_view_is_read():
    kinds = {(t["kind"], t["label"]) for t in vendor_page.toggles(PAGE)}
    assert ("billing", "Monthly") in kinds and ("billing", "Yearly") in kinds
    assert ("currency", "CAD") in kinds and ("deployment", "Self-hosted") in kinds


def run(project, *args):
    env = {**os.environ, "GROWTH_PROJECT": str(project), "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run([sys.executable, str(TOOLS / "vendor_page.py"), *args], capture_output=True, text=True, env=env, cwd=project)


def test_record_files_a_raw_fact_only_when_the_value_is_in_the_quoted_line(demo_project, tmp_path):
    saved = tmp_path / "pricing.html"
    saved.write_text(PAGE)
    (demo_project / "research").mkdir(exist_ok=True)
    init = subprocess.run([sys.executable, str(TOOLS / "research.py"), "init", "/pm", "--key", "pm"], capture_output=True, text=True,
                          env={**os.environ, "GROWTH_PROJECT": str(demo_project)}, cwd=demo_project)
    assert init.returncode == 0, init.stderr
    base = ["--file", str(saved), "--find", "Basic", "--record", "/pm", "--key", "pm", "--vendor", "Acme", "--fact", "Basic a user a month", "--view", "Monthly",
            "--source-url", "https://acme.example.com/pricing"]
    wrong = run(demo_project, *base, "--value", "$25")                              # the banner's number is not Basic's line
    assert wrong.returncode != 0 and "vendor's own words" in wrong.stderr
    assert run(demo_project, *base[:-2], "--value", "$12").returncode != 0           # a saved file needs its source address
    ok = run(demo_project, *base, "--value", "$12")
    assert ok.returncode == 0, ok.stderr
    row = json.loads((demo_project / "research" / "pm-record.json").read_text())["vendor_facts"][0]
    assert row["how_read"] == "raw" and row["view"] == "Monthly" and "billed monthly" in row["quote"] and row["source_url"].startswith("https://acme.example.com")
    assert "controls that can change the numbers" in ok.stdout
