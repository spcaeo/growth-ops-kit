"""Rule 93 per locale (#54): en-US, en-CA and en-GB word lists, a locale per path or per page (<html lang>), and a reviewed allowlist."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "kit" / "tools"))
from gatelib import CHECKS, spelling  # noqa: E402
from gatelib.core import Ctx, run_check  # noqa: E402

HTML = "<html lang='{lang}'><head><title>{t}</title><meta name='description' content='A good plan'></head><body><main><p>{t}</p><img src='x.png' alt='{a}'></main></body></html>"


def gate(cfg, path="/x", t="plain words", lang="en", alt="a photo", project=None):
    c = Ctx(project=project or Path("."), path=path, html=HTML.format(lang=lang, t=t, a=alt), cfg=cfg)
    run_check(c, CHECKS["words.us-spelling"])
    return c.lines[-1]


def test_canadian_words_pass_in_en_ca_and_fail_in_en_us():
    t = "Pick the colour and the centre of the favourite tire"
    assert gate({"spelling": "en-CA"}, t=t).level == "OK"
    ln = gate({"spelling": "en-US"}, t=t)
    assert ln.level == "FAIL" and "colour" in ln.what and "centre" in ln.what and "tire" not in ln.what


def test_en_ca_keeps_ize_and_flags_ise_and_british_only_words():
    assert gate({"spelling": "en-CA"}, t="We organize and optimize the program").level == "OK"
    ln = gate({"spelling": "en-CA"}, t="We organise it with a tyre and a programme")
    assert ln.level == "FAIL" and "organise" in ln.what and "tyre" in ln.what and "programme" in ln.what


def test_en_gb_flags_the_us_forms_but_not_words_that_are_real_in_gb():
    assert gate({"spelling": "en-GB"}, t="We organise the programme; check the program on the meter and license it").level == "OK"
    ln = gate({"spelling": "en-GB"}, t="The color of the center")
    assert ln.level == "FAIL" and "color" in ln.what and "center" in ln.what


def test_each_path_has_its_own_locale_longest_prefix_wins():
    cfg = {"spelling": {"/": "en-CA", "/en-us/": "en-US"}}
    t = "the colour of the centre"
    assert gate(cfg, path="/pricing/", t=t).level == "OK"
    assert gate(cfg, path="/en-us/pricing/", t=t).level == "FAIL"
    assert gate(cfg, path="/en-us/pricing/", t="the color of the center").level == "OK"
    assert gate(cfg, path="/en-usa/pricing/", t=t).level == "OK"           # "/en-us/" is a folder, not a prefix of the word


def test_the_pages_own_html_lang_can_decide():
    cfg = {"spelling": "html_lang"}
    assert gate(cfg, t="the colour", lang="en-CA").level == "OK"
    assert gate(cfg, t="the colour", lang="en-US").level == "FAIL"
    assert gate(cfg, t="the colour", lang="fr-CA").level == "SKIP"


def test_a_locale_with_no_list_skips_and_says_why():
    ln = gate({"spelling": "fr-CA"}, t="la couleur")
    assert ln.level == "SKIP" and "no word list" in ln.what


def test_the_allowlist_and_its_file_keep_brand_and_trade_words_unflagged(tmp_path):
    t = "Our Colourway line"
    assert gate({"spelling": "en-US"}, t="Our colour line").level == "FAIL"
    assert gate({"spelling": "en-US", "spelling_allow": ["colour"]}, t="Our colour line").level == "OK"
    (tmp_path / "allow.txt").write_text("# reviewed 2026-11-19\ncentre  # a trade term we read in place\n")
    cfg = {"spelling": "en-US", "spelling_allow_file": "allow.txt"}
    assert gate(cfg, t="the centre", project=tmp_path).level == "OK"
    assert gate(cfg, t="the colour", project=tmp_path).level == "FAIL"        # only the listed word is allowed
    assert t


def test_every_row_gives_each_locale_a_spelling_and_no_locale_flags_its_own_forms():
    for loc in spelling.LOCALES:
        bad = spelling.correct_for(loc)
        own = {row[spelling.LOCALES.index(loc)].lstrip("?") for row in spelling.ROWS}
        assert not (set(bad) & own), (loc, set(bad) & own)
