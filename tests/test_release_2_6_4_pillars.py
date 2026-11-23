"""2.6.4: growth.json pillars_are_money false marks a silo's top page money only when it is in money_core."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HTML = "<html><head><title>t</title></head><body><main><h1>x</h1></main></body></html>"


def rows(demo_project, monkeypatch, **extra):
    cfg = json.loads((demo_project / "growth.json").read_text())
    cfg.update({"silos": {"guides": "Guides", "services": "Services"}, "money_core": ["/services"]}, **extra)
    (demo_project / "growth.json").write_text(json.dumps(cfg))
    monkeypatch.setenv("GROWTH_PROJECT", str(demo_project))
    sys.path.insert(0, str(ROOT / "kit" / "tools"))
    for m in ("config", "inventory"):
        sys.modules.pop(m, None)
    import inventory
    sm = {"/guides/": None, "/services/": None}
    return {r["path"]: r for r in inventory.build(sm, {p: (200, HTML) for p in sm})}


def test_default_keeps_every_pillar_a_money_page(demo_project, monkeypatch):
    r = rows(demo_project, monkeypatch)
    assert r["/guides/"]["type"] == "pillar" and r["/guides/"]["money_page"] and r["/services/"]["money_page"]


def test_pillars_are_money_false_leaves_a_hub_pillar_out(demo_project, monkeypatch):
    r = rows(demo_project, monkeypatch, pillars_are_money=False)
    assert not r["/guides/"]["money_page"]          # maps its cluster: a hub
    assert r["/services/"]["money_page"]            # a pillar in money_core stays money
