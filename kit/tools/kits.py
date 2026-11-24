#!/usr/bin/env python3
"""The micro-kit manifest (kit 3.0): which kit owns which tool and job kind, and each page type's pipeline.

  growth kits                 every micro kit: purpose, tools, job kinds
  growth kits <name>          one micro kit in full
  growth kits pipelines       the ordered job kinds of each page type and what each needs

The data is kit/kits.json (read by this module, by the work board and by the tests). A project may not change it; a new
step on a page's line is a change in that file.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

MANIFEST = Path(__file__).resolve().parents[1] / "kits.json"
_CACHE: dict = {}


def load() -> dict:
    """The manifest, read once per process (and again when the file changes)."""
    mtime = MANIFEST.stat().st_mtime
    if _CACHE.get("mtime") != mtime:
        _CACHE["data"] = json.loads(MANIFEST.read_text(encoding="utf-8"))
        _CACHE["mtime"] = mtime
        _CACHE.pop("jobs", None)
    return _CACHE["data"]


def kits() -> dict:
    return load()["kits"]


def stages() -> list:
    return list(load()["stages"])


def resources() -> dict:
    return load()["resources"]


def jobs() -> dict:
    """Every job kind: {kind: {kit, way, runner, resource, stage, what}} (one flat table over all micro kits)."""
    load()
    if "jobs" not in _CACHE:
        out = {}
        for kname, k in kits().items():
            for kind, j in k.get("jobs", {}).items():
                out[kind] = {**j, "kit": kname}
        _CACHE["jobs"] = out
    return _CACHE["jobs"]


def job(kind: str, overrides: dict | None = None) -> dict:
    """One job kind's definition; a project's pipeline_overrides may change who runs it (runner) or its resource."""
    j = jobs().get(kind)
    if j is None:
        raise KeyError(f"no job kind '{kind}' in kit/kits.json (known: {', '.join(sorted(jobs()))})")
    j = dict(j)
    for field in ("runner", "resource", "way"):
        v = ((overrides or {}).get(field) or {}).get(kind)
        if v:
            j[field] = v
    return j


def pipeline(page_type: str, overrides: dict | None = None) -> list:
    """The job kinds of a page type in order: [{"kind", "needs": [kinds]}]. `overrides` is growth.json's
    pipeline_overrides: {"drop": [kinds]} removes steps (a step that needed a dropped one needs what the dropped one needed)."""
    p = load()["pipelines"].get(page_type)
    if not isinstance(p, dict) or "jobs" not in p:
        types = sorted(k for k, v in load()["pipelines"].items() if isinstance(v, dict) and "jobs" in v)
        raise KeyError(f"no pipeline for page type '{page_type}' (known: {', '.join(types)})")
    drop = set((overrides or {}).get("drop") or [])
    if not drop:
        return p["jobs"]
    needs_of = {s["kind"]: list(s["needs"]) for s in p["jobs"]}

    def real(kinds):
        out = []
        for k in kinds:
            for r in (real(needs_of.get(k, [])) if k in drop else [k]):
                if r not in out:
                    out.append(r)
        return out
    return [{"kind": s["kind"], "needs": real(s["needs"])} for s in p["jobs"] if s["kind"] not in drop]


def check_overrides(overrides: dict | None) -> None:
    """Refuse an override that names a job kind or a resource the kit does not know, or a runner that is not one."""
    o = overrides or {}
    known = jobs()
    for k in list(o.get("drop") or []) + [k for f in ("runner", "resource", "way") for k in (o.get(f) or {})]:
        if k not in known:
            raise KeyError(f"growth.json pipeline_overrides names '{k}', which is not a job kind (known: {', '.join(sorted(known))})")
    for k, v in (o.get("runner") or {}).items():
        if v not in ("machine", "owner") and not (v.startswith("agent:") and len(v) > 6):
            raise KeyError(f"growth.json pipeline_overrides.runner.{k}: '{v}' is not machine, owner or agent:<role>")
    for k, v in (o.get("way") or {}).items():
        if v not in load()["ways"]:
            raise KeyError(f"growth.json pipeline_overrides.way.{k}: '{v}' is not one of {', '.join(load()['ways'])}")


def page_types() -> list:
    return sorted(k for k, v in load()["pipelines"].items() if isinstance(v, dict) and "jobs" in v)


def kit_of_tool(tool: str) -> str | None:
    for name, k in kits().items():
        if tool in k.get("tools", []):
            return name
    return None


def main(argv=None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    if a[:1] in (["-h"], ["--help"]):
        print(__doc__)
        return 0
    if a[:1] == ["pipelines"]:
        for t in page_types():
            print(f"{t}:")
            for step in pipeline(t):
                j = job(step["kind"])
                needs = ", ".join(step["needs"]) or "-"
                print(f"  {step['kind']:<15} {j['kit']:<9} {j['way']:<9} {j['runner']:<15} {j['resource']:<14} needs: {needs}")
        return 0
    names = a[:1] or list(kits())
    for n in names:
        k = kits().get(n)
        if k is None:
            print(f"growth kits: no micro kit '{n}'. Known: {', '.join(kits())}", file=sys.stderr)
            return 2
        print(f"{n}: {k['purpose']}")
        if a[:1]:
            print(f"  tools: {', '.join(k['tools'])}")
            if k.get("libraries"):
                print(f"  libraries: {', '.join(k['libraries'])}")
            for kind, j in k.get("jobs", {}).items():
                print(f"  job {kind}: {j['way']}, {j['runner']}, resource {j['resource']}, stage {j['stage'] or '-'}: {j['what']}")
        else:
            print(f"  {len(k['tools'])} tools; jobs: {', '.join(k.get('jobs', {})) or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
