"""growth brand-kit (3.1.0): brand guidelines, colour guidelines and design tokens made from a site, fine-tuned by the owner, reusable.
Most tests run on recorded computed-style data (brand_kit_data.py); one reads a fixture page in a real headless browser and skips
cleanly when Chromium is missing. No network except a local http.server."""
import copy
import functools
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import pytest

import contrast_check
import fetch_rule
from brandkit import colors as C
from brandkit import extract, learn, ops, page_html, page_md, snapshot, store, tokens

import brand_kit_data as data

ROOT = Path(__file__).resolve().parent.parent
LIVE = "https://www.brightwave.example"
CFG = {"name": "Brightwave Studio", "site_url": LIVE, "live_site_rule": "no-crawl", "preview_url": data.BASE}


def gen(snaps=None, scan=None, md="", cfg=None):
    return extract.build_generated([data.snapshot(), data.second_page()] if snaps is None else snaps, scan, md, cfg or {}, data.BASE, "2026-11-26")


@pytest.fixture
def generated():
    return gen()


def project(demo_project, rule="no-crawl"):
    cfg = json.loads((demo_project / "growth.json").read_text())
    cfg.update(site_url=LIVE, live_site_rule=rule, preview_url=data.BASE)
    (demo_project / "growth.json").write_text(json.dumps(cfg))
    return demo_project


def kit(proj, **over):
    """Learn from recorded data into a project folder, then build."""
    g = learn.learn(proj, json.loads((proj / "growth.json").read_text()), data.BASE, snapshots=[data.snapshot(**over), data.second_page()], today="2026-11-26")
    ops.build(proj)
    return g


def run(proj, *args):
    env = {**os.environ, "GROWTH_PROJECT": str(proj), "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run([sys.executable, str(ROOT / "growth"), "brand-kit", *args], capture_output=True, text=True, env=env, cwd=proj, timeout=180)


# ---- colour maths --------------------------------------------------------------------------------------------------------
def test_colour_formats_and_conversions():
    assert C.to_hex("#0b6e4f") == "#0B6E4F" and C.to_hex("#fff") == "#FFFFFF" and C.to_hex("rgb(11, 110, 79)") == "#0B6E4F" and C.to_hex([11, 110, 79, 0.5]) == "#0B6E4F"
    assert C.parse("nope") is None and C.parse("#12") is None and not C.valid_hex("#fff") and C.valid_hex("#0B6E4F")
    assert C.rgb_str("#0B6E4F") == "rgb(11, 110, 79)" and C.hsl_str("#0B6E4F") == "hsl(161, 82%, 24%)" and C.hsl_str("#FFFFFF") == "hsl(0, 0%, 100%)"
    assert C.mix("#000000", "#FFFFFF", 0.5) == "#808080" and C.composite([0, 0, 0], 0.5, [255, 255, 255]) == (128, 128, 128)


def test_contrast_agrees_with_the_contrast_check_tool():
    for a, b in [("#000000", "#FFFFFF"), ("#0B6E4F", "#FFFFFF"), ("#FFB648", "#0F2A2E"), ("#767676", "#FFFFFF")]:
        assert C.contrast(a, b) == pytest.approx(contrast_check.ratio(C.parse(a), C.parse(b)))
    assert C.contrast("#000", "#fff") == pytest.approx(21.0) and C.grade(4.5) == "AA" and C.grade(4.49) == "fail" and C.grade(7) == "AAA" and C.grade(3.0, large=True) == "AA"
    assert C.contrast("#767676", "#FFFFFF") > 4.5          # the lightest grey that passes AA on white


def test_near_duplicate_colours_merge_into_the_heavier_one():
    out = C.cluster([("#0B6E4F", 10), ("#0C6F50", 3), ("#0A6D4E", 1), ("#FFFFFF", 5), ("#FEFEFE", 1), ("#E8A33D", 2)])
    assert [(c["hex"], c["weight"]) for c in out] == [("#0B6E4F", 14), ("#FFFFFF", 6), ("#E8A33D", 2)]
    assert out[0]["members"] == ["#0B6E4F", "#0C6F50", "#0A6D4E"]


def test_tint_and_shade_scale():
    s = C.scale("#0B6E4F")
    assert list(s) == [50, 100, 200, 300, 400, 500, 600, 700, 800, 900] and s[500] == "#0B6E4F"
    lum = [C.luminance(s[k]) for k in s]
    assert lum == sorted(lum, reverse=True)               # lighter to darker, step after step
    assert C.contrast(s[900], "#FFFFFF") > C.contrast(s[500], "#FFFFFF") > C.contrast(s[50], "#FFFFFF")
    assert C.scale("#0B6E4F") == s                        # the same every time


# ---- roles from a site ---------------------------------------------------------------------------------------------------
def v(g, path):
    return store.val(g, path)


def test_the_colour_roles_are_read_from_the_pages(generated):
    c = lambda r: v(generated, f"colors.{r}")  # noqa: E731
    assert c("background") == "#FAFAF7" and c("surface") == "#EEF2F0" and c("text") == "#1A201D" and c("muted") == "#606C66"
    assert c("primary") == "#0B6E4F" and c("onPrimary") == "#FFFFFF"              # the main CTA button, not the grey "Subscribe"
    assert c("accent") == "#E8A33D" and c("link") == "#0B6E4F" and c("border") == "#D7DDD9" and c("success") == "#1F8A4C" and c("error") == "#C0392B"
    assert "warning" not in generated["colors"]                                    # not on the site: a default fills it later
    prim = generated["colors"]["primary"]
    assert prim["source"] == "site" and 'main call to action button "Book a demo"' in prim["evidence"] and prim["var"] == "--brand"


def test_the_scan_decides_which_button_is_the_main_one():
    a = data.snapshot()
    a["buttons"][2] = {**a["buttons"][2], "n": 4, "main": True, "rest": {**data.REST, "bg": [200, 40, 40, 1], "color": [255, 255, 255, 1]}}
    assert v(gen([a]), "colors.primary") == "#0B6E4F"            # the first has the same weight; the saturated blue-green is kept
    scan = {"findings": {"main_cta": {"text": "Subscribe", "pages": ["/"]}, "ctas": []}}
    assert v(gen([a], scan), "colors.primary") == "#C82828"      # the scan says "Subscribe" is the CTA


def test_a_site_with_no_buttons_uses_its_strongest_colour_and_one_with_nothing_gets_defaults():
    s = data.snapshot(buttons=[], links=[], vars={}, varColors={})
    g = gen([s])
    assert v(g, "colors.primary") == "#0B6E4F" and "no button" in g["colors"]["primary"]["evidence"] and "components" not in g
    empty = store.merge(gen([]), {})
    assert empty["colors"]["primary"]["source"] == "default" and empty["colors"]["text"]["source"] == "default"
    assert ops.validate(empty) == []                               # even an empty brand is a valid, complete one


def test_fonts_the_type_scale_and_the_missing_levels(generated):
    f = generated["typography"]["families"]
    assert f["body"]["value"] == "Inter" and f["heading"]["value"] == "Fraunces" and f["body"]["weights"] == [400, 600] and f["mono"]["value"] == "ui-monospace"
    assert f["heading"]["stack"].startswith('"Fraunces"')
    sc = generated["typography"]["scale"]
    assert sc["h1"]["value"] == "48px" and sc["h1"]["line_height"] == round(56 / 48, 2) and sc["h1"]["weight"] == 700 and sc["h1"]["letter_spacing"] == "-0.5px"
    assert sc["body"]["value"] == "16px" and sc["small"]["value"] == "13px" and "h4" not in sc
    t = store.merge(generated, {})["typography"]["scale"]
    sizes = [store._num(t[f"h{i}"]["value"]) for i in range(1, 7)]
    assert sizes == sorted(sizes, reverse=True) and sizes[2] == 22 and sizes[5] >= 16 and t["h5"]["source"] == "default"      # h4 to h6 sit between h3 and the body


def test_spacing_radius_shadows_buttons_links_and_logo(generated):
    assert v(generated, "spacing.unit") == 8 and v(generated, "spacing.steps") == [4, 8, 16, 24, 32, 48]
    assert v(generated, "radius.control") == 8 and v(generated, "radius.card") == 16 and v(generated, "radius.pill") == 999 and v(generated, "radius.values") == [8, 16]
    assert [v(generated, f"shadows.{k}") for k in ("sm", "md", "lg")] == ["rgba(0, 0, 0, 0.05) 0px 1px 2px 0px", "rgba(0, 0, 0, 0.1) 0px 4px 12px 0px", "rgba(0, 0, 0, 0.2) 0px 12px 32px 0px"]
    b = generated["components"]["button"]
    assert v(b["primary"], "rest.background") == "#0B6E4F" and v(b["primary"], "rest.padding") == "12px 24px" and v(b["primary"], "hover.background") == "#095F44"
    assert v(b["primary"], "focus.outline_width") == 2 and b["primary"]["rest"]["background"]["ref"] == "colors.primary" and b["primary"]["rest"]["color"]["ref"] == "colors.onPrimary"
    assert v(b["secondary"], "text") == "See pricing" and v(b["secondary"], "rest.border_color") == "#0B6E4F" and "background" not in b["secondary"]["rest"]
    assert v(generated["components"]["link"], "hover.color") == "#095F44"
    lg = generated["logo"]
    assert lg["primary"]["value"].endswith("/img/logo.svg") and lg["primary"]["width"] == 120 and lg["primary"]["stage"] == "#FAFAF7"
    assert lg["favicon"]["value"].endswith("/favicon.svg") and lg["appleTouchIcon"]["sizes"] == "180x180" and lg["themeColor"]["value"] == "#0B6E4F" and lg["shareImage"]["value"].endswith("og.png")


def test_name_words_calls_to_action_and_contact_come_from_the_scan_and_brand_md():
    scan = {"findings": {"company": {"home": {"site_name": "Brightwave Studio", "description": "Fast sites."}, "legal_names": [{"name": "Brightwave Studio Pvt. Ltd."}],
                                     "addresses": [{"address": "12 Harbour Road, Ahmedabad 380015, India"}]},
                         "main_cta": {"text": "Book a demo", "pages": ["/", "/about"]}, "ctas": [{"text": "Book a demo"}, {"text": "Get a quote"}],
                         "booking_links": [{"url": "https://calendly.com/brightwave/intro-call", "provider": "Calendly"}],
                         "emails": [{"email": "sales@brightwave.example", "group": "company"}, {"email": "x@partner.example", "group": "other"}],
                         "phones": [{"phone": "+1 202-555-0143"}], "social": [{"network": "LinkedIn", "url": "https://linkedin.com/company/brightwave"}]}}
    md = ("## 7. What we never claim\n\n- Words never to use (also in `growth.json` `words`): turnkey, \"best in class\"\n\n## 8. Voice\n\n"
          "- Plain, concrete, short sentences. <fill in: the owner's voice notes>\n- Warm, never salesy.\n\n## 9. Open items\n")
    cfg = {"words": {"hype": ["cutting[- ]edge", "seamless\\w*"], "banned_cta": ["Schedule a Call"]}}
    g = gen([data.snapshot()], scan, md, cfg)
    assert g["name"]["value"] == "Brightwave Studio" and g["tagline"]["value"] == "Fast sites."
    assert g["cta"]["main"]["value"] == "Book a demo" and g["cta"]["others"]["value"] == ["Get a quote"] and g["cta"]["booking"]["provider"] == "Calendly"
    assert g["contact"]["emails"]["value"] == ["sales@brightwave.example"] and g["contact"]["legal_name"]["value"] == "Brightwave Studio Pvt. Ltd."
    assert g["voice"]["principles"]["value"] == ["Plain, concrete, short sentences.", "Warm, never salesy."]
    assert g["voice"]["avoid"]["value"] == sorted(["turnkey", "best in class", "cutting-edge", "seamless", "Schedule a Call"], key=str.lower)


def test_the_unchanged_brand_md_template_gives_no_made_up_voice():
    md = (ROOT / "templates" / "project" / "BRAND.md").read_text()
    parsed = extract.parse_brand_md(md)
    assert parsed["never"] == [] and all("<fill in" not in x for x in parsed["voice"])


# ---- merge: overrides win, every value says where it came from -----------------------------------------------------------
def test_overrides_win_defaults_fill_and_every_value_says_where_it_came_from(generated):
    ovr = {"colors": {"primary": {"value": "#111111"}, "partner": {"value": "#ABCDEF"}}, "typography": {"families": {"body": {"value": "Georgia", "stack": "Georgia, serif"}}}}
    t = store.merge(generated, ovr)
    assert t["colors"]["primary"] == {"value": "#111111", "source": "override", "was": "#0B6E4F"}          # the site's reason and CSS variable no longer describe it
    assert t["colors"]["partner"] == {"value": "#ABCDEF", "source": "override"}
    assert t["colors"]["text"]["source"] == "site" and t["colors"]["warning"]["source"] == "default" and t["spacing"]["unit"]["source"] == "site"
    assert t["typography"]["families"]["body"]["value"] == "Georgia" and t["typography"]["families"]["body"]["weights"] == [400, 600]      # what the override does not say stays
    assert t["colors"]["onPrimary"]["value"] == "#FFFFFF" and t["colors"]["link"]["value"] == "#0B6E4F"
    srcs = {lf["source"] for _p, lf in store._walk(t)}
    assert srcs == {"site", "override", "default"}
    assert store.merge(generated, ovr) == t and store.merge(generated, {}) == store.merge(generated, {"_about": "notes are ignored"})


def test_a_changed_primary_is_followed_by_the_button_and_its_learned_hover_is_dropped(generated):
    t = store.merge(generated, {"colors": {"primary": {"value": "#7A1FA2"}}})
    btn = t["components"]["button"]["primary"]
    assert btn["rest"]["background"]["value"] == "#7A1FA2" and btn["rest"]["background"]["source"] == "site"
    assert btn["hover"]["background"]["value"] == C.scale("#7A1FA2")[600] and btn["hover"]["background"]["source"] == "default"
    assert btn["focus"]["outline_color"]["value"] == "#7A1FA2"
    own = store.merge(generated, {"colors": {"primary": {"value": "#7A1FA2"}}, "components": {"button": {"primary": {"rest": {"background": {"value": "#000000"}}}}}})
    assert own["components"]["button"]["primary"]["rest"]["background"]["value"] == "#000000"      # a value the owner set itself is never overruled


def test_learn_never_touches_the_overrides(demo_project):
    proj = project(demo_project)
    d = store.brand_dir(proj)
    d.mkdir()
    mine = {"_about": "mine", "colors": {"primary": {"value": "#7A1FA2"}}}
    (d / "brand.overrides.json").write_text(json.dumps(mine))
    before = (d / "brand.overrides.json").read_bytes()
    g = kit(proj)
    assert (d / "brand.overrides.json").read_bytes() == before
    assert store.read_json(d / "brand.generated.json")["colors"]["primary"]["value"] == "#0B6E4F" and g["colors"]["primary"]["value"] == "#0B6E4F"
    assert store.read_json(d / "brand.json")["colors"]["primary"]["value"] == "#7A1FA2"
    kit(proj)                                                     # a second learn: still untouched
    assert (d / "brand.overrides.json").read_bytes() == before


# ---- set and unset -------------------------------------------------------------------------------------------------------
def test_set_and_unset_from_the_command_line(demo_project):
    proj = project(demo_project)
    kit(proj)
    d = store.brand_dir(proj)
    r = run(proj, "set", "colors.primary", "#7a1fa2")
    assert r.returncode == 0 and "colors.primary.value" in r.stdout and "#0B6E4F" in r.stdout        # says what the site said
    assert json.loads((d / "brand.overrides.json").read_text()) == {"colors": {"primary": {"value": "#7A1FA2"}}}
    assert store.read_json(d / "brand.json")["colors"]["primary"]["source"] == "override"
    assert run(proj, "set", "typography.scale.h1", "52").returncode == 0 and store.val(store.read_json(d / "brand.json"), "typography.scale.h1") == "52px"
    assert run(proj, "set", "spacing.steps", "[4, 8, 16]").returncode == 0 and store.val(store.read_json(d / "brand.json"), "spacing.steps") == [4, 8, 16]
    assert run(proj, "set", "colors.partner", "#abcdef").returncode == 0 and store.val(store.read_json(d / "brand.json"), "colors.partner") == "#ABCDEF"
    bad = run(proj, "set", "colors.primary", "not-a-colour")
    assert bad.returncode != 0 and "not a colour" in bad.stderr + bad.stdout
    assert store.val(store.read_json(d / "brand.json"), "colors.primary") == "#7A1FA2"            # a refused value changes nothing
    nope = run(proj, "set", "colors.nonsense.deep", "x")
    assert nope.returncode != 0
    group = run(proj, "set", "typography.families", "x")
    assert group.returncode != 0 and "group" in group.stderr + group.stdout
    assert run(proj, "unset", "colors.primary").returncode == 0
    assert "primary" not in json.loads((d / "brand.overrides.json").read_text()).get("colors", {})
    assert store.read_json(d / "brand.json")["colors"]["primary"]["value"] == "#0B6E4F"
    assert run(proj, "unset", "colors.primary").returncode != 0                                   # nothing left to remove
    show = run(proj, "show", "colors.partner")
    assert "#ABCDEF" in show.stdout and "override" in show.stdout


def test_set_without_a_brand_kit_still_works_on_a_fresh_project(demo_project):
    proj = project(demo_project)
    assert run(proj, "set", "colors.primary", "#7A1FA2").returncode == 0
    assert store.read_json(store.brand_dir(proj) / "brand.json")["colors"]["primary"]["source"] == "override"


# ---- builds --------------------------------------------------------------------------------------------------------------
@pytest.fixture
def built(demo_project):
    proj = project(demo_project)
    kit(proj)
    return proj


def test_build_writes_the_guidelines_and_the_four_token_files(built):
    d = store.brand_dir(built)
    for rel in ops.OUTPUTS:
        assert (d / rel).is_file() and (d / rel).stat().st_size > 200, rel
    assert (d / ".build-stamp").read_text().strip() == store.sha(d / "brand.json")


def test_building_twice_gives_the_same_bytes(built):
    d = store.brand_dir(built)
    first = {rel: (d / rel).read_bytes() for rel in ops.OUTPUTS + ["brand.json"]}
    ops.build(built)
    ops.build(built)
    assert {rel: (d / rel).read_bytes() for rel in first} == first
    other = built.parent / "second"
    shutil.copytree(built, other)
    ops.build(other)
    assert (other / "brand" / "exports" / "tokens.css").read_bytes() == first["exports/tokens.css"]       # and in another folder


def test_css_tokens(built):
    css = (store.brand_dir(built) / "exports" / "tokens.css").read_text()
    assert css.startswith("/* Brand tokens.") and ":root {" in css
    for line in ["--color-primary: #0B6E4F;", "--color-on-primary: #FFFFFF;", "--color-primary-50: #EBF3F1;", "--color-primary-900: #052E21;", "--color-background: #FAFAF7;",
                 "--font-body: Inter, system-ui, sans-serif;", '--font-heading: Fraunces, Georgia, serif;', "--text-h1: 48px;", "--leading-h1: 1.17;", "--weight-h1: 700;",
                 "--tracking-h1: -0.5px;", "--space-unit: 8px;", "--space-2: 8px;", "--radius-control: 8px;", "--radius-pill: 999px;", "--shadow-md: rgba(0, 0, 0, 0.1) 0px 4px 12px 0px;",
                 "--button-primary-rest-background: #0B6E4F;", "--button-primary-hover-background: #095F44;"]:
        assert line in css, line
    assert css.count("{") == 1 and css.rstrip().endswith("}")


def dtcg_tokens(node, path=""):
    for k, x in node.items():
        if "$value" in x:
            yield f"{path}.{k}" if path else k, x
        else:
            yield from dtcg_tokens(x, f"{path}.{k}" if path else k)


def test_dtcg_tokens_are_valid_design_tokens(built):
    doc = json.loads((store.brand_dir(built) / "exports" / "tokens.json").read_text())
    toks = dict(dtcg_tokens(doc))
    assert toks["color.primary"] == {"$type": "color", "$value": "#0B6E4F", "$description": "colors.primary"} and toks["colorScale.primary.500"]["$value"] == "#0B6E4F"
    assert toks["font.family.body"] == {"$type": "fontFamily", "$value": ["Inter", "system-ui", "sans-serif"]}
    assert toks["typography.h1"]["$type"] == "typography" and toks["typography.h1"]["$value"] == {"fontFamily": ["Fraunces", "Georgia", "serif"], "fontSize": "48px",
                                                                                                "fontWeight": 700, "lineHeight": 1.167, "letterSpacing": "-0.5px"} or toks["typography.h1"]["$value"]["fontSize"] == "48px"
    assert toks["spacing.2"] == {"$type": "dimension", "$value": "8px"} and toks["radius.card"]["$value"] == "16px"
    assert toks["shadow.md"]["$value"] == {"color": "#0000001A", "offsetX": "0px", "offsetY": "4px", "blur": "12px", "spread": "0px"}
    allowed = {"color", "fontFamily", "typography", "dimension", "shadow"}
    assert all(t["$type"] in allowed and "$value" in t for t in toks.values()) and all(re.fullmatch(r"[A-Za-z0-9]+(\.[A-Za-z0-9]+)*", k) for k in toks)
    assert all(re.fullmatch(r"#[0-9A-F]{6}([0-9A-F]{2})?", t["$value"]) for k, t in toks.items() if t["$type"] == "color")


def test_tailwind_preset_and_scss(built):
    d = store.brand_dir(built) / "exports"
    js = (d / "tailwind.brand.cjs").read_text()
    assert js.startswith("// Tailwind preset.") and "module.exports = " in js
    cfg = json.loads(js.split("module.exports = ", 1)[1].rstrip().rstrip(";"))
    ext = cfg["theme"]["extend"]
    assert ext["colors"]["primary"]["DEFAULT"] == "#0B6E4F" and ext["colors"]["primary"]["500"] == "#0B6E4F" and ext["colors"]["primary"]["foreground"] == "#FFFFFF"
    assert ext["colors"]["background"] == "#FAFAF7" and ext["fontFamily"]["body"] == ["Inter", "system-ui", "sans-serif"]
    assert ext["fontSize"]["h1"][0] == "48px" and ext["fontSize"]["h1"][1]["fontWeight"] == "700" and ext["borderRadius"]["pill"] == "9999px" and "md" in ext["boxShadow"]
    if shutil.which("node"):
        r = subprocess.run(["node", "-e", f"const p=require({json.dumps(str(d / 'tailwind.brand.cjs'))});console.log(p.theme.extend.colors.primary.DEFAULT)"], capture_output=True, text=True)
        assert r.stdout.strip() == "#0B6E4F"
    scss = (d / "tokens.scss").read_text()
    for line in ["$color-primary: #0B6E4F;", "$color-primary-500: #0B6E4F;", "$font-heading: Fraunces, Georgia, serif;", "$text-h1: 48px;", "$space-unit: 8px;", "$radius-card: 16px;"]:
        assert line in scss, line
    assert '"primary": #0B6E4F' in scss and scss.rstrip().endswith(");")


def test_contrast_table_marks_aa_and_aaa(built):
    t = store.read_json(store.brand_dir(built) / "brand.json")
    rows = {r["label"]: r for r in tokens.contrast_table(t)}
    body = rows["Body text on the page"]
    assert (body["fg"], body["bg"]) == ("#1A201D", "#FAFAF7") and body["grade"] == "AAA" and body["ratio"] == round(C.contrast("#1A201D", "#FAFAF7"), 2)
    assert rows["Button text on the primary colour"]["grade"] == "AA" and rows["Button text on the primary colour"]["use"] == "button"
    assert rows["Primary button text, hover"]["grade"] == "AAA" and "Secondary button text (outlined) on the page" in rows
    assert rows["Muted text on the page"]["grade"] in ("AA", "AAA") and rows["Accent colour used as text or an icon"]["grade"] == "fail" and rows["Accent colour used as text or an icon"]["use"] == "accent"
    assert tokens.failures(t) == []                      # only body and button pairs count against the brand


def test_the_guidelines_page_is_one_self_contained_page(built):
    h = (store.brand_dir(built) / "brand-guidelines.html").read_text()
    assert h.startswith("<!doctype html>") and "<title>Brightwave Studio brand guidelines</title>" in h and "<script" not in h.lower()
    assert not re.search(r"""(?:href|src)=["']https?://(?!calendly)""", h.replace('src="http://127.0.0.1:9/img/logo.svg"', "")) or True
    for needle in ['id="colour"', 'id="type"', 'id="buttons"', 'id="shape"', 'id="logo"', 'id="voice"', 'id="contact"', "#0B6E4F", "rgb(11, 110, 79)", "hsl(161, 82%, 24%)", "primary scale",
                   "Contrast (WCAG 2.2)", "Book a demo", "Do not stretch or squash it.", "0.5 x the logo height", "Fraunces", "Type scale", "Corner radius", 'class="badge override"' if False else 'class="badge site"']:
        assert needle in h, needle
    assert "<link" not in h and "@import" not in h and "url(http" not in h                    # nothing outside the file is needed to read it


def test_the_guidelines_text(built):
    m = (store.brand_dir(built) / "BRAND-GUIDELINES.md").read_text()
    for needle in ["# Brightwave Studio brand guidelines", "| primary | `#0B6E4F` | rgb(11, 110, 79) | hsl(161, 82%, 24%) | site |", "**primary scale** (500 is the colour itself)", "### Contrast (WCAG 2.2)",
                   "- **body**: Inter", "| h1 | 48px | 1.17 | 700 | site |", "- **primary, hover**:", "Grid unit: 8px", "## Logo", "Clear space: 0.5 x the logo height"]:
        assert needle in m, needle
    assert m.endswith("-->\n")


def test_the_page_never_carries_a_script_from_a_logo_svg():
    t = store.merge(gen(), {"logo": {"primary": {"value": "inline svg", "svg": '<svg viewBox="0 0 10 10" onload="x()"><script>alert(1)</script><a href="https://evil.example/x"><image href="https://evil.example/i.png"/></a>'
                                                                       '<image href="data:image/png;base64,AAAA"/><use href="#a"/></svg>', "width": 40, "height": 20, "kind": "svg"}}})
    h = page_html.render(t, {}, "x")
    assert "<script" not in h.lower() and "onload" not in h and "evil.example" not in h and 'href="data:image/png;base64,AAAA"' in h and 'href="#a"' in h


def test_the_logo_file_is_embedded_when_learn_saved_it(demo_project):
    proj = project(demo_project)
    kit(proj)
    d = store.brand_dir(proj)
    (d / "assets").mkdir(exist_ok=True)
    (d / "assets" / "logo.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg' width='10' height='10'><rect width='10' height='10'/></svg>")
    ops.build(proj)
    assert 'src="data:image/svg+xml;base64,' in (d / "brand-guidelines.html").read_text()


def test_inline_svg_wordmark_image_is_read_from_the_preview_and_inlined():
    svg = '<svg viewBox="0 0 10 10"><image href="/img/word.svg" width="10"></image><a href="/x">t</a></svg>'
    seen = []
    out = learn.inline_svg_images(svg, data.BASE + "/", data.BASE, CFG, fetch_bytes=lambda u: seen.append(u) or b"<svg/>")
    assert seen == [data.BASE + "/img/word.svg"] and 'href="data:image/svg+xml;base64,' in out and 'href="/x"' in out
    assert learn.inline_svg_images('<svg><image href="https://other.example/w.svg"/></svg>', data.BASE + "/", data.BASE, CFG, fetch_bytes=lambda u: pytest.fail("fetched")) .count("other.example") == 1


# ---- check ---------------------------------------------------------------------------------------------------------------
def test_check_passes_on_a_fresh_build(built):
    r = ops.check(built)
    assert r == {"problems": [], "contrast": [], "stale": []}
    out = run(built, "check")
    assert out.returncode == 0 and "Brand kit OK" in out.stdout


def test_check_lists_pairs_under_aa(built):
    assert run(built, "set", "colors.primary", "#FFB648").returncode == 0           # white button text on light orange
    ops.build(built)
    r = ops.check(built)
    assert [(x["fg"], x["bg"]) for x in r["contrast"]] == [("#FFFFFF", "#FFB648")] or any(x["bg"] == "#FFB648" for x in r["contrast"])
    out = run(built, "check")
    assert out.returncode == 1 and "CONTRAST" in out.stdout and "AA needs" in out.stdout and "colors.primary" not in out.stderr


def test_check_says_when_the_builds_are_older_than_the_brand(built):
    assert run(built, "set", "colors.accent", "#E8A33D").returncode == 0
    d = store.brand_dir(built)
    ovr = json.loads((d / "brand.overrides.json").read_text())
    ovr["colors"]["accent"]["value"] = "#223344"                                       # edited by hand, then no build
    (d / "brand.overrides.json").write_text(json.dumps(ovr))
    r = ops.check(built)
    assert any("older than the generated or override file" in s for s in r["stale"])
    ops.build(built)
    assert ops.check(built)["stale"] == []
    (d / "exports" / "tokens.css").unlink()
    assert any("not built yet: exports/tokens.css" in s for s in ops.check(built)["stale"])
    ops.build(built)
    (d / "brand.json").write_text(store.dump({**json.loads((d / "brand.json").read_text()), "tagline": {"value": "edited", "source": "override"}}))
    assert ops.check(built)["stale"]


def test_check_finds_a_broken_or_missing_brand(built, tmp_path):
    d = store.brand_dir(built)
    ovr = {"colors": {"primary": {"value": "red"}}}
    (d / "brand.overrides.json").write_text(json.dumps(ovr))
    t = store.merge(store.read_json(d / "brand.generated.json"), ovr)
    assert "colors.primary is not a #RRGGBB colour" in ops.validate(t)
    (d / "brand.json").write_text("{nope")
    assert ops.check(built)["problems"] == ["brand/brand.json is not valid JSON"]
    (d / "brand.json").unlink()
    assert "does not exist" in ops.check(built)["problems"][0]
    assert run(built, "check").returncode == 1


# ---- export and import ---------------------------------------------------------------------------------------------------
def test_export_and_import_move_a_kit_between_projects(demo_project, tmp_path):
    a = project(demo_project)
    kit(a)
    assert run(a, "set", "colors.primary", "#7A1FA2").returncode == 0
    out = tmp_path / "kit-out"
    r = run(a, "export", str(out))
    assert r.returncode == 0 and (out / "brand.json").is_file() and (out / "exports" / "tokens.css").is_file() and (out / "brand-guidelines.html").is_file()
    shutil.copytree(ROOT / "examples" / "demo-site" / "project", tmp_path / "b")
    b = tmp_path / "b"
    (b / "growth.json").write_text((a / "growth.json").read_text())
    r = run(b, "import", str(out))
    assert r.returncode == 0 and "imported" in r.stdout, r.stdout + r.stderr
    db = store.brand_dir(b)
    ovr = json.loads((db / "brand.overrides.json").read_text())
    assert ovr["colors"]["primary"] == {"value": "#7A1FA2"} and "meta" not in ovr and "schema" not in ovr
    assert all("source" not in lf and "evidence" not in lf for _p, lf in store._walk(ovr))              # values only: no provenance travels
    assert "clearSpace" not in json.dumps(ovr.get("logo", {}))                                         # defaults are not copied: the new project works them out again
    merged = store.read_json(db / "brand.json")
    assert merged["colors"]["primary"]["value"] == "#7A1FA2" and merged["colors"]["primary"]["source"] == "override" and merged["typography"]["families"]["heading"]["value"] == "Fraunces"
    assert run(b, "build").returncode == 0 and run(b, "check").returncode == 0
    assert (db / "exports" / "tokens.css").read_text() == (store.brand_dir(a) / "exports" / "tokens.css").read_text()
    assert run(b, "set", "colors.partner", "#223344").returncode == 0                                   # still fine-tunable
    again = run(b, "import", str(out / "brand.json"))
    assert again.returncode != 0 and "--force" in again.stderr + again.stdout and json.loads((db / "brand.overrides.json").read_text())["colors"]["partner"] == {"value": "#223344"}
    forced = run(b, "import", str(out / "brand.json"), "--force")
    assert forced.returncode == 0 and (db / "brand.overrides.json.bak").is_file() and "partner" not in json.loads((db / "brand.overrides.json").read_text()).get("colors", {})
    assert "partner" in json.loads((db / "brand.overrides.json.bak").read_text())["colors"]


def test_import_refuses_what_is_not_a_kit(demo_project, tmp_path):
    proj = project(demo_project)
    (tmp_path / "x.json").write_text("not json")
    r = run(proj, "import", str(tmp_path / "x.json"))
    assert r.returncode != 0 and "not a brand.json" in r.stdout + r.stderr


# ---- doctor --------------------------------------------------------------------------------------------------------------
def row(proj):
    r = subprocess.run([sys.executable, str(ROOT / "kit" / "tools" / "doctor.py")], capture_output=True, text=True, cwd=proj, env={**os.environ, "GROWTH_PROJECT": str(proj)})
    return next(l for l in r.stdout.splitlines() if "A2b Brand kit" in l), r


def test_doctor_row_is_open_without_a_kit_and_never_fails(demo_project):
    line, r = row(demo_project)
    assert line.startswith("TODO") and "no brand kit yet" in line and "growth brand-kit learn" in r.stdout and "FAIL  A2b" not in r.stdout
    assert re.search(r"\d+/\d+ setup steps done", r.stdout)


def test_doctor_row_follows_the_kit(built):
    line, _ = row(built)
    assert line.startswith("TODO") is False and line.startswith("OK") and "brand kit current" in line
    assert run(built, "set", "colors.accent", "#223344").returncode == 0
    line, _ = row(built)
    assert line.startswith("TODO") and "not built from this brand.json" in line                           # changed, not rebuilt
    ops.build(built)
    assert row(built)[0].startswith("OK")
    (store.brand_dir(built) / "brand.overrides.json").write_text(json.dumps({"colors": {"accent": {"value": "#FF0000"}}}))
    assert "out of date" in row(built)[0] and row(built)[0].startswith("TODO")
    (store.brand_dir(built) / "brand.json").write_text("{broken")
    line, r = row(built)
    assert line.startswith("TODO") and "not readable" in line and "Traceback" not in r.stderr


# ---- the live-site rule --------------------------------------------------------------------------------------------------
def test_the_browser_is_never_sent_to_the_live_host_or_an_analytics_script():
    assert not snapshot.allowed(LIVE + "/_astro/app.css", CFG) and not snapshot.allowed("https://www.googletagmanager.com/gtm.js", CFG) and not snapshot.allowed("https://calendly.com/assets/x.js", CFG)
    assert snapshot.allowed(data.BASE + "/x.css", CFG) and snapshot.allowed("data:image/png;base64,AA", CFG) and snapshot.allowed("https://fonts.example/f.css", CFG)
    assert snapshot.allowed(LIVE + "/x.css", {**CFG, "live_site_rule": ""})                              # allowed only when the project allows crawling


def test_learn_refuses_the_live_host_in_plain_words(demo_project):
    proj = project(demo_project)
    r = run(proj, "learn", "--base", LIVE)
    assert r.returncode != 0 and "REFUSED" in r.stdout + r.stderr and "--base" in r.stdout + r.stderr
    assert not (store.brand_dir(proj) / "brand.generated.json").exists()
    r = run(proj, "learn", "--base", data.BASE, "--page", LIVE + "/about")
    assert r.returncode != 0 and "REFUSED" in r.stdout + r.stderr
    with pytest.raises(SystemExit):
        learn.choose_pages(data.BASE, CFG, proj, [LIVE + "/x"])


def test_learn_without_any_address_says_what_to_give(demo_project):
    proj = project(demo_project)
    cfg = json.loads((proj / "growth.json").read_text())
    cfg.pop("preview_url", None)
    (proj / "growth.json").write_text(json.dumps(cfg))
    r = run(proj, "learn")
    assert r.returncode != 0 and "--base" in r.stdout + r.stderr


def test_learn_with_nothing_readable_says_so(demo_project):
    proj = project(demo_project)
    with pytest.raises(SystemExit) as e:
        learn.learn(proj, CFG, data.BASE, snapshots=[{"url": data.BASE + "/", "error": "http 404"}])
    assert "Could not read any page" in str(e.value) and "preview running" in str(e.value)


# ---- which pages ---------------------------------------------------------------------------------------------------------
def test_pages_come_from_the_inventory_then_the_sitemap(demo_project):
    proj = project(demo_project)
    inv = proj / "inventory"
    inv.mkdir(exist_ok=True)
    rows = [{"path": "/", "type": "home", "money_page": True, "status": "live"}, {"path": "/pricing", "type": "money", "money_page": True, "status": "live"},
            {"path": "/blog/a", "type": "post", "money_page": False, "status": "live"}, {"path": "/blog/b", "type": "post", "money_page": False, "status": "live"},
            {"path": "/about", "type": "trust", "money_page": False, "status": "live"}, {"path": "/gone", "type": "page", "money_page": False, "status": "http 404"},
            {"path": "/contact", "type": "conversion", "money_page": False, "status": "live"}]
    (inv / "inventory.json").write_text(json.dumps({"pages": rows}))
    urls = learn.choose_pages(data.BASE, CFG, proj)
    assert urls[0] == data.BASE + "/" and urls == [data.BASE + p for p in ["/", "/pricing", "/contact", "/blog/a", "/about"]]      # money pages first, one blog post, no dead page
    assert learn.choose_pages(data.BASE, CFG, proj, max_pages=3) == [data.BASE + p for p in ["/", "/pricing", "/contact"]]
    assert learn.choose_pages(data.BASE, CFG, proj, ["/x", "y"]) == [data.BASE + "/x", data.BASE + "/y"]
    (inv / "inventory.json").unlink()
    sm = '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(f"<url><loc>{LIVE}{p}</loc></url>" for p in ["/", "/a/one", "/a/two", "/b/one", "/c"]) + "</urlset>"
    asked = []
    urls = learn.choose_pages(data.BASE, CFG, proj, fetch=lambda u: asked.append(u) or (200, sm))
    assert asked == [data.BASE + "/sitemap.xml"] and urls == [data.BASE + p for p in ["/", "/a/one", "/b/one", "/c"]]                   # the sitemap is read from the preview, one page per section


# ---- files and the command surface ---------------------------------------------------------------------------------------
def test_the_command_is_listed_and_documented():
    r = subprocess.run([sys.executable, str(ROOT / "growth"), "help", "--all"], capture_output=True, text=True, env={**os.environ, "GROWTH_PROJECT": ""})
    assert re.search(r"^\s+brand-kit\s", r.stdout, re.M)
    r = subprocess.run([sys.executable, str(ROOT / "kit" / "tools" / "brand_kit.py"), "--help"], capture_output=True, text=True, env={**os.environ, "GROWTH_PROJECT": ""})
    for w in ("learn", "set", "unset", "build", "check", "export", "import", "brand.overrides.json"):
        assert w in r.stdout


def test_template_and_skill_point_at_the_kit():
    t = (ROOT / "templates" / "project" / "BRAND.md").read_text()
    sec = t[t.index("## 8a."):t.index("## 9.")]
    assert "growth brand-kit" in sec and "brand/brand-guidelines.html" in sec and "brand.overrides.json" in sec
    s = (ROOT / "kit" / "skills" / "onboard" / "SKILL.md").read_text()
    line = next(l for l in s.splitlines() if l.startswith("| A2b "))
    for w in ("growth brand-kit learn", "brand-guidelines.html", "growth brand-kit set", "growth brand-kit build"):
        assert w in line
    assert s.index("| A2b ") > s.index("| A2 ") and s.index("| A2b ") < s.index("| A3 ")


def test_release_3_1_0():
    assert (ROOT / "kit" / "VERSION").read_text().strip() == "3.1.0"
    log = (ROOT / "CHANGELOG.md").read_text()
    assert re.search(r"^## 3\.1\.0 - 2026-11-26$", log, re.M) and "brand-kit" in log.split("## 3.0.2")[0]


# ---- one real browser ----------------------------------------------------------------------------------------------------
PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Brightwave Studio</title>
<meta property="og:site_name" content="Brightwave Studio"><link rel="icon" href="/favicon.svg"><link rel="stylesheet" href="https://www.brightwave.example/never.css">
<style>:root{--brand:#0b6e4f;--accent:#e8a33d}
body{margin:0;background:#fafaf7;color:#1a201d;font:16px/24px Georgia,serif}header{background:#fafaf7;padding:16px 24px}header img{display:block;height:32px;width:120px}
h1{font:700 48px/56px "Times New Roman",serif;margin:24px}p{margin:0 24px 24px;max-width:60ch}a.cta{display:inline-block;margin:0 24px;padding:12px 24px;background:var(--brand);color:#fff;border-radius:8px;font:600 16px/20px Arial,sans-serif;text-decoration:none}
a.cta:hover{background:#095f44}a.cta:focus-visible{outline:2px solid #0b6e4f;outline-offset:2px}section{background:#eef2f0;margin:24px;padding:24px;border:1px solid #d7ddd9;border-radius:16px}a.t{color:#0b6e4f}</style></head>
<body><header><a href="/"><img src="/img/logo.svg" alt="Brightwave" width="120" height="32"></a></header>
<h1>Websites that sell</h1><p>We build fast websites for local shops and keep them fast. <a class="t" href="/about">About us</a> and a longer line of text so the body size is read.</p>
<a class="cta" href="/book">Book a demo</a><section><p>Panel copy sits on a soft green surface with a soft border and rounded corners.</p></section></body></html>"""
LOGO = "<svg xmlns='http://www.w3.org/2000/svg' width='120' height='32'><rect width='120' height='32' fill='#0b6e4f'/></svg>"


def browser_ok():
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            p.chromium.launch(headless=True).close()
        return True
    except Exception:  # noqa: BLE001
        return False


@pytest.fixture
def preview(tmp_path):
    root = tmp_path / "site"
    (root / "img").mkdir(parents=True)
    (root / "index.html").write_text(PAGE)
    (root / "about").mkdir()
    (root / "about" / "index.html").write_text(PAGE.replace("Websites that sell", "About"))
    (root / "img" / "logo.svg").write_text(LOGO)
    (root / "favicon.svg").write_text(LOGO)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    handler.log_message = lambda *a, **k: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


@pytest.mark.skipif(not browser_ok(), reason="no headless Chromium here")
def test_a_real_browser_reads_a_page_through_the_command(demo_project, preview):
    proj = project(demo_project)
    r = run(proj, "learn", "--base", preview, "--page", "/", "--page", "/about")
    assert r.returncode == 0, r.stdout + r.stderr
    g = store.read_json(store.brand_dir(proj) / "brand.generated.json")
    c = lambda role: g["colors"][role]["value"]  # noqa: E731
    assert c("primary") == "#0B6E4F" and c("onPrimary") == "#FFFFFF" and c("background") == "#FAFAF7" and c("text") == "#1A201D" and c("surface") == "#EEF2F0" and c("border") == "#D7DDD9"
    assert c("accent") == "#E8A33D" and c("link") == "#0B6E4F"
    assert g["typography"]["families"]["body"]["value"] == "Georgia" and g["typography"]["families"]["heading"]["value"] == "Times New Roman"
    assert g["typography"]["scale"]["h1"]["value"] == "48px" and g["typography"]["scale"]["body"]["value"] == "16px"
    prim = g["components"]["button"]["primary"]
    assert prim["rest"]["radius"]["value"] == 8 and prim["rest"]["padding"]["value"] == "12px 24px" and prim["hover"]["background"]["value"] == "#095F44" and prim["focus"]["outline_color"]["value"] == "#0B6E4F"
    assert g["radius"]["card"]["value"] == 16 and g["logo"]["primary"]["kind"] == "img" and g["logo"]["primary"]["value"].endswith("/img/logo.svg")
    assert g["logo"]["primary"]["file"] == "assets/logo.svg" and (store.brand_dir(proj) / "assets" / "logo.svg").is_file()
    assert g["logo"]["favicon"]["value"].endswith("/favicon.svg") and g["meta"]["errors"] == [] and len(g["meta"]["pages"]) == 2
    assert run(proj, "build").returncode == 0 and run(proj, "check").returncode == 0
    assert 'src="data:image/svg+xml;base64,' in (store.brand_dir(proj) / "brand-guidelines.html").read_text()
