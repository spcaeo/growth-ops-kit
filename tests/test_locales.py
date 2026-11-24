"""kit 3.0 international markets: the locales helper (kit/tools/locales.py), the wizard's two market answers, doctor's market row,
and the research tools' --locale option. A project with no market.locales is one locale built from the old market fields."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import locales as L  # noqa: E402
import pace  # noqa: E402
import store  # noqa: E402
import wizard  # noqa: E402
import wizard_state as ws  # noqa: E402
from board_helpers import growth as growth_cmd, make_project  # noqa: E402

FOUR = [{"locale": "en-US", "country": "US", "language": "en", "prefix": "/", "primary": True, "google_params": "gl=us&hl=en&pws=0"},
        {"locale": "en-CA", "country": "CA", "language": "en", "prefix": "/en-ca/", "google_params": "gl=ca&hl=en&pws=0"},
        {"locale": "fr-CA", "country": "CA", "language": "fr", "prefix": "/fr-ca/", "google_params": "gl=ca&hl=fr&pws=0"},
        {"locale": "es-US", "country": "US", "language": "es", "prefix": "/es-us/", "google_params": "gl=us&hl=es&pws=0"}]


# -- the helper -------------------------------------------------------------------------------------------------------
def test_an_old_single_market_config_is_one_locale():
    old = {"primary_country": "US", "google_params": "gl=us&hl=en", "secondary_countries": [], "language": "en-US"}
    locs = L.from_market(old)
    assert len(locs) == 1 and locs[0] == {"locale": "en-US", "country": "US", "language": "en", "prefix": "/", "primary": True,
                                          "google_params": "gl=us&hl=en"}        # its own google_params are kept exactly as written
    assert not L.is_multi({"market": old}) and L.problems({"market": old}) == []
    assert L.from_market({"primary_country": "CA", "language": "fr-CA"})[0]["google_params"] == "gl=ca&hl=fr&pws=0"     # derived when missing
    assert L.from_market({}) == [] and L.from_cfg({}) == []                                                             # nothing set yet


def test_four_locales_in_full_form_and_in_short_form_are_the_same_list():
    full = L.from_market({"locales": FOUR})
    short = L.from_market({"locales": ["en-US", "en-CA", "fr-CA", "es-US"]})
    assert full == short and [e["locale"] for e in full] == ["en-US", "en-CA", "fr-CA", "es-US"]
    assert [e["prefix"] for e in short] == ["/", "/en-ca/", "/fr-ca/", "/es-us/"]
    assert [e["google_params"] for e in short] == ["gl=us&hl=en&pws=0", "gl=ca&hl=en&pws=0", "gl=ca&hl=fr&pws=0", "gl=us&hl=es&pws=0"]
    assert L.primary(short)["locale"] == "en-US" and L.is_multi({"market": {"locales": FOUR}})
    assert L.market_fields(short) == {"primary_country": "US", "language": "en-US", "google_params": "gl=us&hl=en&pws=0", "secondary_countries": ["CA"]}


def test_a_missing_google_param_is_derived_and_tags_are_put_in_their_usual_case():
    locs = L.normalize([{"locale": "en-us", "primary": True}, {"locale": "FR-ca"}])
    assert [e["locale"] for e in locs] == ["en-US", "fr-CA"] and locs[1]["google_params"] == "gl=ca&hl=fr&pws=0"


@pytest.mark.parametrize("raw,words", [
    (["en_US"], "not a language tag"),
    (["english"], "not a language tag"),
])
def test_a_tag_that_is_not_bcp47_is_refused_in_plain_words(raw, words):
    with pytest.raises(L.LocaleError, match=words):
        L.normalize(raw)


def test_validation_finds_each_mistake_with_its_fix():
    def bad(raw):
        return " | ".join(L.validate(L.normalize(raw)))
    assert "exactly one locale must be the primary" in bad([{"locale": "en-US", "primary": True}, {"locale": "fr-CA", "primary": True, "prefix": "/fr/"}])
    assert "exactly one locale must be the primary" in bad([{"locale": "en-US", "primary": False}, {"locale": "fr-CA", "primary": False}])
    assert 'prefix must be "/"' in bad([{"locale": "en-US", "primary": True, "prefix": "/en/"}, {"locale": "fr-CA"}])
    assert "share the folder /x/" in bad([{"locale": "en-US", "primary": True}, {"locale": "fr-CA", "prefix": "/x/"}, {"locale": "es-US", "prefix": "/x"}])
    assert "listed twice" in bad(["en-US", "en-US"])
    assert "must not nest" in bad(["en-US", {"locale": "fr-CA", "prefix": "/fr/"}, {"locale": "fr-FR", "prefix": "/fr/fr/"}])
    assert "must carry gl=ca" in bad(["en-US", {"locale": "en-CA", "google_params": "gl=us&hl=en&pws=0"}])
    assert "must carry pws=0" in bad(["en-US", {"locale": "en-CA", "google_params": "gl=ca&hl=en"}])
    assert "has no country" in bad(["en-US", "fr"])
    assert "is not the primary but its prefix is" in bad(["en-US", {"locale": "fr-CA", "prefix": "/"}])
    assert L.validate(L.normalize(FOUR)) == []


def test_a_bad_list_in_growth_json_is_one_plain_error_and_never_a_crash():
    cfg = {"market": {"primary_country": "US", "locales": ["en-US", {"locale": "fr-CA", "prefix": "/"}]}}
    with pytest.raises(L.LocaleError, match="market.locales in growth.json is not right"):
        L.from_cfg(cfg)
    assert "market.locales in growth.json is not right" in L.problems(cfg)[0] and not L.is_multi(cfg)
    clash = {"market": {"primary_country": "CA", "locales": FOUR}}
    assert "must agree" in L.problems(clash)[0]                                  # the old field and the primary locale disagree


def test_a_path_knows_its_locale_and_its_copies():
    locs = L.from_market({"locales": FOUR})
    assert L.locale_of_path(locs, "/pricing/")[0]["locale"] == "en-US"
    loc, base = L.locale_of_path(locs, "/fr-ca/pricing/")
    assert (loc["locale"], base) == ("fr-CA", "/pricing/")
    assert L.locale_of_path(locs, "/fr-ca")[1] == "/" and L.locale_of_path(locs, "/fr-capital/x/")[0]["locale"] == "en-US"
    assert L.path_in(L.find(locs, "es-US"), "/pricing/") == "/es-us/pricing/" and L.path_in(L.find(locs, "en-US"), "/pricing") == "/pricing"
    assert L.path_in(L.find(locs, "fr-CA"), "/") == "/fr-ca/"
    assert L.find(locs, "fr_ca")["locale"] == "fr-CA" and L.find(locs)["locale"] == "en-US"
    with pytest.raises(L.LocaleError, match="known: en-US, en-CA, fr-CA, es-US"):
        L.find(locs, "de-DE")


# -- the wizard -------------------------------------------------------------------------------------------------------
def project_with_cfg(tmp_path, market=None):
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "growth.json").write_text(json.dumps({"name": "X", "site_url": "https://x.example", **({"market": market} if market else {})}))
    return proj


def market_step(proj, answer):
    return wizard.step_market(wizard.Session(proj, {"market": answer}))


def test_the_old_market_answer_still_writes_the_old_fields_and_no_locales(tmp_path):
    proj = project_with_cfg(tmp_path)
    msg = market_step(proj, {"country": "US", "language": "en"})
    m = json.loads((proj / "growth.json").read_text())["market"]
    assert m["google_params"] == "gl=us&hl=en&pws=0" and m["primary_country"] == "US" and "locales" not in m
    assert "United States, en" in msg and ws.get(proj, "market")["answer"] == {"country": "US", "language": "en"}


def test_the_locales_answer_records_both_forms(tmp_path):
    proj = project_with_cfg(tmp_path)
    msg = market_step(proj, {"locales": [{"locale": "en-US", "primary": True}, "en-CA", "fr-CA", "es-US"]})
    m = json.loads((proj / "growth.json").read_text())["market"]
    assert m["primary_country"] == "US" and m["google_params"] == "gl=us&hl=en&pws=0" and m["language"] == "en-US" and m["secondary_countries"] == ["CA"]
    assert [e["locale"] for e in m["locales"]] == ["en-US", "en-CA", "fr-CA", "es-US"] and m["locales"][2]["google_params"] == "gl=ca&hl=fr&pws=0"
    assert "4 locales" in msg and "fr-CA at /fr-ca/" in msg
    assert [e["locale"] for e in ws.get(proj, "market")["answer"]["locales"]] == ["en-US", "en-CA", "fr-CA", "es-US"]
    assert L.is_multi(json.loads((proj / "growth.json").read_text()))


def test_a_list_answer_is_the_same_as_the_locales_object_and_a_bad_one_stops_with_the_fix(tmp_path):
    proj = project_with_cfg(tmp_path)
    market_step(proj, ["en-US", "fr-CA"])
    assert [e["locale"] for e in json.loads((proj / "growth.json").read_text())["market"]["locales"]] == ["en-US", "fr-CA"]
    with pytest.raises(SystemExit, match="exactly one locale must be the primary"):
        market_step(proj, {"locales": [{"locale": "en-US", "primary": True}, {"locale": "fr-CA", "primary": True}]})
    assert [e["locale"] for e in json.loads((proj / "growth.json").read_text())["market"]["locales"]] == ["en-US", "fr-CA"]    # unchanged


def test_answering_market_again_changes_it_at_once_in_both_directions(tmp_path):
    proj = project_with_cfg(tmp_path)
    market_step(proj, {"country": "US", "language": "en"})
    r = growth_cmd(proj, "wizard", "answer", "market", json.dumps({"locales": ["en-US", "en-CA", "fr-CA"]}))
    assert r.returncode == 0 and "market changed" in r.stdout, r.stdout + r.stderr
    assert len(json.loads((proj / "growth.json").read_text())["market"]["locales"]) == 3
    r = growth_cmd(proj, "wizard", "answer", "market", '{"country": "CA", "language": "fr"}')
    assert r.returncode == 0 and "market changed" in r.stdout
    m = json.loads((proj / "growth.json").read_text())["market"]
    assert "locales" not in m and m["google_params"] == "gl=ca&hl=fr&pws=0" and m["language"] == "fr-CA"       # one locale again


# -- doctor -----------------------------------------------------------------------------------------------------------
def doctor_line(project):
    r = growth_cmd(project, "doctor", "--verbose")
    return next(l for l in r.stdout.splitlines() if "A14" in l), r.stdout


def test_doctor_lists_every_locale_and_names_a_bad_list(tmp_path):
    line, _ = doctor_line(make_project(tmp_path / "one"))
    assert "locales" not in line and "not required" in line
    line, _ = doctor_line(make_project(tmp_path / "four", market={"primary_country": "US", "locales": FOUR}))
    assert "4 locales" in line and "fr-CA at /fr-ca/" in line and "es-US at /es-us/" in line and "en-CA at /en-ca/" in line
    line, _ = doctor_line(make_project(tmp_path / "bad", market={"primary_country": "US", "locales": ["en-US", {"locale": "fr-CA", "prefix": "/"}]}))
    assert line.startswith("FAIL") and "market.locales in growth.json is not right" in line


# -- the research tools: --locale -------------------------------------------------------------------------------------
def test_research_ai_and_paa_record_the_locale_and_print_its_google_parameters(tmp_path):
    project = make_project(tmp_path, market={"primary_country": "US", "locales": FOUR})
    growth_cmd(project, "research", "init", "/pm", "--key", "pm", check=True)
    r = growth_cmd(project, "research", "ai", "/pm", "--key", "pm", "--engine", "chatbot", "--query", "meilleurs outils", "--summary", "Acme nommé",
                   "--source", "https://chat.example.com/share/abc", "--locale", "fr_CA")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "locale fr-CA: Google parameters gl=ca&hl=fr&pws=0" in r.stdout and "growth pace google" in r.stdout
    rec = json.loads((project / "research" / "pm-record.json").read_text())
    assert rec["ai_answers"][0]["locale"] == "fr-CA" and rec["ai_answers"][0]["market"] == "CA"          # the market follows the locale
    r = growth_cmd(project, "research", "paa", "/pm", "Est-ce gratuit ?", "--key", "pm", "--source", "https://search.example.com/?q=acme")
    assert r.returncode == 0
    assert json.loads((project / "research" / "pm-record.json").read_text())["paa"][0]["locale"] == "en-US"   # the default is the primary
    r = growth_cmd(project, "research", "ai", "/pm", "--key", "pm", "--engine", "chatbot", "--query", "q", "--summary", "s",
                   "--source", "https://chat.example.com/share/abc", "--locale", "de-DE")
    assert r.returncode != 0 and "no locale de-DE" in (r.stdout + r.stderr)


def test_a_one_locale_project_files_exactly_the_old_rows(tmp_path):
    project = make_project(tmp_path)
    growth_cmd(project, "research", "init", "/pm", "--key", "pm", check=True)
    r = growth_cmd(project, "research", "ai", "/pm", "--key", "pm", "--engine", "chatbot", "--market", "US", "--query", "q", "--summary", "s",
                   "--source", "https://chat.example.com/share/abc")
    assert r.returncode == 0 and "locale " not in r.stdout
    row = json.loads((project / "research" / "pm-record.json").read_text())["ai_answers"][0]
    assert "locale" not in row and row["market"] == "US"


def test_journal_run_takes_a_locale_and_the_market_follows_it(tmp_path):
    project = make_project(tmp_path, market={"primary_country": "US", "locales": FOUR})
    r = growth_cmd(project, "journal", "run", "--page", "/pm", "--engine", "chatbot", "--query", "q", "--response", "an answer", "--locale", "fr-CA")
    assert r.returncode == 0, r.stdout + r.stderr
    runs = list((project / "journal").rglob("*chatbot*.json"))
    assert runs and json.loads(runs[0].read_text())["market"] == "CA" and json.loads(runs[0].read_text())["locale"] == "fr-CA"
    entries = [json.loads(l) for l in (project / "journal" / "entries.jsonl").read_text().splitlines() if l.strip()]
    assert entries[-1]["locale"] == "fr-CA" and entries[-1]["market"] == "CA"


def test_every_locale_shares_the_one_google_door(tmp_path):
    project = make_project(tmp_path, market={"primary_country": "US", "locales": FOUR}, pacers={"google": {"min_s": 1, "max_s": 1, "robot_pause_s": 5}})
    st = store.Store(project)
    t1 = pace.turn("google", "a", st=st, locale="fr-CA")
    t2 = pace.turn("google", "b", st=st, locale="en-US")                        # a second locale waits for the same timer
    assert t2["at"] - t1["at"] >= 1.0
    ev = st.events("pace-turn", limit=10)
    assert sorted(e["data"].get("locale") for e in ev) == ["en-US", "fr-CA"] and len(ev) == 2
    r = growth_cmd(project, "pace", "google", "--locale", "es-US", "--max-wait", "0")
    assert r.returncode in (0, 3)
    r = growth_cmd(project, "pace", "google", "--locale", "de-DE", "--max-wait", "0")
    assert r.returncode == 2 and "no locale de-DE" in r.stderr
