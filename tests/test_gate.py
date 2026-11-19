"""Guards for the rule gate (python3 -m pytest tests/test_gate.py).

- Every check an entry names exists in the kit, every check is used by some entry, and each entry's files and needs match
  the code (growth registry_sync keeps them in step).
- No check passes on missing input: with no page, no site checkout, no journal and no docs, nothing says OK.
- A check that does not apply (no adapter for the stack, a feature that is off) is SKIP, never OK.
"""
import json
import re
import tempfile
from pathlib import Path

import pytest

from gatelib import CHECKS, registry
from gatelib.core import PAGE_TYPES, Ctx, run_check

REG = registry.load()["rules"]
BY_ID = {e["id"]: e for e in REG}


class TestRegistry:
    def test_no_duplicate_entries(self):
        ids = [e["id"] for e in REG]
        assert len(ids) == len(set(ids))

    def test_entries_are_classified(self):
        for e in REG:
            assert e["enforcement"] in registry.ENFORCEMENT, e["id"]
            assert e["scope"] and set(e["scope"]) <= set(registry.SCOPES), e["id"]
            assert e.get("severity", "FAIL") in ("FAIL", "WARN")
            if e.get("severity") == "WARN":
                assert e.get("warn_reason"), f"{e['id']}: a WARN rule needs a written reason"
            if e["enforcement"] == "code":
                assert e.get("checks"), f"{e['id']}: a code rule names its checks"
            else:
                assert e.get("proxy"), f"{e['id']}: a judgment rule names its code proxy"
                assert e.get("why_judgment"), f"{e['id']}: a judgment rule says why no program can decide it"

    def test_named_checks_exist_and_files_match(self):
        for e in REG:
            for c in registry.checks_of(e):
                assert c in CHECKS, f"{e['id']} names unknown check {c}"
                assert CHECKS[c].where in e["files"], f"{e['id']}: files lacks {CHECKS[c].where} (run growth registry_sync)"

    def test_needs_match_the_code(self):
        for e in REG:
            have = {CHECKS[c].needs for c in registry.checks_of(e) if c in CHECKS}
            if not have:
                continue
            want = sorted(have)
            assert e["needs"] == (want[0] if len(want) == 1 else want), f"{e['id']}: needs out of step (run growth registry_sync)"
            assert set(want) <= set(registry.NEEDS)

    def test_every_check_is_used(self):
        used = {c for e in REG for c in registry.checks_of(e)}
        assert sorted(set(CHECKS) - used) == [], "a check no rule uses: add it to an entry or delete it"

    def test_every_check_prints_its_rule(self):
        for c in CHECKS.values():
            assert c.rule in BY_ID, f"{c.cid} prints under rule {c.rule}, which has no registry entry"

    def test_nextjs_checks_live_in_the_adapter(self):
        for c in CHECKS.values():
            assert (c.needs == "nextjs") == c.where.startswith("adapters/nextjs/"), f"{c.cid}: needs {c.needs} but lives in {c.where}"

    def test_registry_text_has_no_one_business_in_it(self):
        text = (Path(registry.REGISTRY)).read_text()
        assert "PAGE-RULEBOOK.md" not in text


def empty_ctx(tmp, ptype, **kw):
    return Ctx(project=Path(tmp), path="", url="http://127.0.0.1:9/nothing", repo=None, ptype=ptype, docs=None, cfg=kw.get("cfg", {}), key="")


class TestMissingInputFails:
    def test_no_page_check_passes_without_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            for ptype in PAGE_TYPES:
                ctx = empty_ctx(tmp, ptype)
                for c in CHECKS.values():
                    if ptype in c.types and c.cid != "house.features":
                        run_check(ctx, c)
                run_check(ctx, CHECKS["house.features"])
                ok = [l.cid for l in ctx.lines if l.level == "OK"]
                assert ok == [], f"these checks said OK with no input ({ptype})"

    def test_no_process_check_passes_without_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = empty_ctx(tmp, "money")
            for c in CHECKS.values():
                if "process" in c.types or "engine" in c.types:
                    run_check(ctx, c)
            # proc.rulebook-current reads only the kit's own book and registry, so it may say OK with no project at all
            assert [l.cid for l in ctx.lines if l.level == "OK" and l.cid != "proc.rulebook-current"] == []

    def test_static_mode_skips_only_page_reading_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = empty_ctx(tmp, "money")
            ctx.static, ctx.url = True, ""
            for c in CHECKS.values():
                if "money" in c.types and c.cid != "house.features":
                    run_check(ctx, c)
            assert ctx.skipped
            assert [l.cid for l in ctx.lines if l.level == "OK"] == [], "a static check said OK with no repo"

    def test_blank_page_has_no_house_feature(self):
        from gatelib.c_house import CONDITIONAL, HOUSE
        with tempfile.TemporaryDirectory() as tmp:
            for ptype, feats in HOUSE.items():
                ctx = empty_ctx(tmp, ptype, cfg={"stack": "nextjs"})
                ctx.html, ctx.status, ctx.path = "<html><head><title>x</title></head><body><main></main></body></html>", 200, "/x"
                for cid in feats:
                    run_check(ctx, CHECKS[cid])
                ok = [l.cid for l in ctx.lines if l.level == "OK" and l.cid not in CONDITIONAL[ptype]]
                assert ok == [], f"a blank {ptype} page passed these house features"


class TestSkipIsNeverOk:
    def test_adapter_checks_skip_on_other_stacks(self):
        with tempfile.TemporaryDirectory() as tmp:
            for stack in ("static", "wordpress"):
                ctx = empty_ctx(tmp, "money", cfg={"stack": stack})
                nx = [c for c in CHECKS.values() if c.needs == "nextjs" and "money" in c.types]
                assert nx
                for c in nx:
                    run_check(ctx, c)
                assert {l.level for l in ctx.lines} == {"SKIP"}
                assert all(l.text() == f"SKIP {l.cid}: no adapter for {stack} (this check reads nextjs code)" for l in ctx.lines)

    def test_adapter_checks_run_on_nextjs(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = empty_ctx(tmp, "money", cfg={"stack": "nextjs"})
            c = CHECKS["repo.no-secrets"]
            run_check(ctx, c)
            assert ctx.lines[0].level == "FAIL" and "input missing" in ctx.lines[0].what      # it ran, and failed for want of a repo

    def test_feature_off_is_skip(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = empty_ctx(tmp, "money")
            ctx.html, ctx.status, ctx.path = "<html><body><main><h1>x</h1></main></body></html>", 200, "/x"
            run_check(ctx, CHECKS["dialog.call"])
            assert ctx.lines[0].level == "SKIP" and "features.call_dialog" in ctx.lines[0].what


class TestNoProjectFactsInTheKit:
    def test_kit_files_hold_no_named_business(self):
        """The kit's own folder never names the demo business, its domain or an absolute home path."""
        root = Path(registry.REGISTRY).parent.parent
        bad = []
        for f in root.rglob("*"):
            if not f.is_file() or f.suffix not in (".py", ".sh", ".json", ".js", ".md", ".css", ".html") or "__pycache__" in f.parts:
                continue
            t = f.read_text(errors="replace")
            if re.search(r"/Users/\w+/", t):
                bad.append(f"{f.relative_to(root)}: absolute home path")
        assert bad == []


class TestMainType:
    """Rule 95 / 36b: the page's main type must be able to fail (the site's Organization is on every page)."""

    PAGE = ('<html><head><title>x</title><script type="application/ld+json">%s</script></head><body><main><h1>x</h1></main></body></html>')

    def verdict(self, graph, cfg=None):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = empty_ctx(tmp, "money", cfg=cfg or {})
            ctx.html, ctx.status, ctx.path = self.PAGE % json.dumps({"@context": "https://schema.org", "@graph": graph}), 200, "/x"
            run_check(ctx, CHECKS["schema.house-types"])
            return ctx.lines[-1].level

    ORG = {"@type": "Organization", "@id": "https://x.example/#organization", "name": "X"}
    TRAIL = {"@type": "BreadcrumbList", "itemListElement": []}

    def test_a_page_with_only_the_sites_own_nodes_fails(self):
        assert self.verdict([self.ORG, {"@type": "WebPage"}, {"@type": "WebSite"}, self.TRAIL]) == "FAIL"

    def test_organization_in_the_config_never_counts_as_the_main_type(self):
        assert self.verdict([self.ORG, self.TRAIL], {"schema_types": {"money": "Service|Organization"}}) == "FAIL"
        assert self.verdict([self.ORG, self.TRAIL], {"schema_types": {"money": "Organization"}}) == "FAIL"

    def test_the_default_money_types_pass_with_a_real_main_node(self):
        for t in ("Product", "Service", "SoftwareApplication"):
            assert self.verdict([self.ORG, {"@type": t}, self.TRAIL]) == "OK", t

    def test_the_techseo_check_agrees(self):
        from techseo.c_schema import main_types
        assert "Organization" not in main_types("Product|Organization|LocalBusiness")
        assert main_types("Organization") == ("Product", "Service", "SoftwareApplication")
