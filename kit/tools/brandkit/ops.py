"""build, check, export and import of a brand kit: the file work around brand.json. No browser, no network."""
from __future__ import annotations

import base64
import shutil
from pathlib import Path

from . import colors as C
from . import page_html, page_md, store, tokens

OUTPUTS = ["brand-guidelines.html", "BRAND-GUIDELINES.md", "exports/tokens.css", "exports/tokens.json", "exports/tailwind.brand.cjs", "exports/tokens.scss"]
MIME = {".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif", ".ico": "image/x-icon"}
MAX_ASSET = 300_000


def load_assets(d: Path) -> dict:
    """{"logo": data: address} when learn saved the logo file: the guidelines page then needs no other file."""
    out = {}
    for f in sorted((d / "assets").glob("logo.*")) if (d / "assets").is_dir() else []:
        mime = MIME.get(f.suffix.lower())
        if mime and f.stat().st_size <= MAX_ASSET:
            out["logo"] = f"data:{mime};base64," + base64.b64encode(f.read_bytes()).decode()
            break
    return out


def build(project) -> list[str]:
    """Merge, then write the guidelines page, the words, and the four token files. The same brand.json gives the same bytes."""
    d = store.brand_dir(project)
    tree = store.write_merged(project)
    stamp = store.sha(d / "brand.json")
    files = {
        "brand-guidelines.html": page_html.render(tree, load_assets(d), stamp),
        "BRAND-GUIDELINES.md": page_md.render(tree, stamp),
        "exports/tokens.css": tokens.tokens_css(tree),
        "exports/tokens.json": tokens.tokens_dtcg(tree),
        "exports/tailwind.brand.cjs": tokens.tailwind_preset(tree),
        "exports/tokens.scss": tokens.tokens_scss(tree),
    }
    (d / "exports").mkdir(parents=True, exist_ok=True)
    for rel, text in files.items():
        (d / rel).write_text(text)
    (d / ".build-stamp").write_text(stamp + "\n")
    return [f"brand/{rel}" for rel in files]


# ---- check ---------------------------------------------------------------------------------------------------------------
def validate(tree: dict) -> list[str]:
    """What is wrong with the brand itself (not its contrast): missing or malformed values, in plain words."""
    bad = []
    if tree.get("schema") != store.SCHEMA:
        bad.append(f"schema is {tree.get('schema')!r}, expected {store.SCHEMA}")
    for role in ("background", "text", "primary"):
        if not C.valid_hex(store.val(tree, f"colors.{role}")):
            bad.append(f"colors.{role} is not a #RRGGBB colour")
    for k, v in (tree.get("colors") or {}).items():
        if store.is_leaf(v) and k != "palette" and not C.valid_hex(v.get("value")):
            bad.append(f"colors.{k} is not a #RRGGBB colour ({v.get('value')!r})")
    if not store.val(tree, "typography.families.body"):
        bad.append("typography.families.body is empty")
    for lvl in store.SCALE_LEVELS:
        v = store.val(tree, f"typography.scale.{lvl}")
        if v is None or store._num(v) is None or store._num(v) <= 0:
            bad.append(f"typography.scale.{lvl} is not a size in px ({v!r})")
    steps = store.val(tree, "spacing.steps")
    if not isinstance(steps, list) or not all(isinstance(s, (int, float)) and s > 0 for s in steps):
        bad.append("spacing.steps is not a list of positive numbers")
    return bad


def check(project) -> dict:
    """{"problems": [...], "contrast": [failing rows], "stale": [...]}: everything `growth brand-kit check` reports."""
    d = store.brand_dir(project)
    out = {"problems": [], "contrast": [], "stale": []}
    f = d / "brand.json"
    if not f.is_file():
        out["problems"].append("brand/brand.json does not exist: run growth brand-kit learn (or import a kit), then build")
        return out
    gen, ovr, disk = store.load_all(project)
    if disk is None:
        out["problems"].append("brand/brand.json is not valid JSON")
        return out
    if (d / "brand.overrides.json").is_file() and store.read_json(d / "brand.overrides.json") is None:
        out["problems"].append("brand/brand.overrides.json is not valid JSON")
    if (d / "brand.generated.json").is_file() and gen is None:
        out["problems"].append("brand/brand.generated.json is not valid JSON")
    out["problems"] += validate(disk)
    out["contrast"] = tokens.failures(disk)
    if store.dump(store.merge(gen, ovr)) != f.read_text():
        out["stale"].append("brand.json is older than the generated or override file: run growth brand-kit build")
    stamp = d / ".build-stamp"
    missing = [o for o in OUTPUTS if not (d / o).is_file()]
    if missing:
        out["stale"].append("not built yet: " + ", ".join(missing))
    elif not stamp.is_file() or stamp.read_text().strip() != store.sha(f):
        out["stale"].append("the guidelines and token files were built from an older brand.json: run growth brand-kit build")
    return out


# ---- export and import ---------------------------------------------------------------------------------------------------
def export_kit(project, dest) -> list[str]:
    """Copy the built kit to `dest`: brand.json, the guidelines, the token files and the logo file. Builds first when needed."""
    build(project)
    d, dest = store.brand_dir(project), Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    out = []
    for rel in ["brand.json"] + OUTPUTS:
        (dest / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(d / rel, dest / rel)
        out.append(rel)
    if (d / "assets").is_dir():
        for f in sorted((d / "assets").iterdir()):
            if f.is_file():
                (dest / "assets").mkdir(exist_ok=True)
                shutil.copyfile(f, dest / "assets" / f.name)
                out.append(f"assets/{f.name}")
    return out


def _strip(node):
    """A brand tree as overrides: what the owner could have typed (values and their own fields), without provenance or defaults."""
    if store.is_leaf(node):
        if node.get("source") == "default":
            return None
        return {k: v for k, v in node.items() if k not in store.PROVENANCE}
    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            if k in ("schema", "meta") or k.startswith("_"):
                continue
            s = _strip(v)
            if s not in (None, {}):
                out[k] = s
        return out
    return None


def import_kit(project, src, force: bool = False) -> str:
    """Make `src` (a kit folder, or its brand.json) this project's overrides, so the project starts from it and can still be fine-tuned.
    Refuses to replace overrides that already hold changes unless `force`. Returns a one-line result."""
    src = Path(src)
    f = src / "brand.json" if src.is_dir() else src
    data = store.read_json(f)
    if data is None:
        raise ValueError(f"{f} is not a brand.json (missing or not valid JSON)")
    d = store.brand_dir(project)
    ov = d / "brand.overrides.json"
    existing = store.read_json(ov, {}) or {}
    if any(not k.startswith("_") for k in existing) and not force:
        raise ValueError(f"{ov} already holds your changes. Run again with --force to replace them (the old file is kept as brand.overrides.json.bak).")
    d.mkdir(parents=True, exist_ok=True)
    if ov.is_file():
        shutil.copyfile(ov, d / "brand.overrides.json.bak")
    ovr = {"_about": f"Imported from {f.name} of another project. Each value below changes the brand; edit freely, or remove one to go back to what `growth brand-kit learn` reads from this site."}
    ovr.update(_strip(data))
    ov.write_text(store.dump(ovr))
    for asset in sorted((src / "assets").glob("*")) if src.is_dir() and (src / "assets").is_dir() else []:
        (d / "assets").mkdir(exist_ok=True)
        shutil.copyfile(asset, d / "assets" / asset.name)
    store.write_merged(project)
    n = sum(1 for _ in store._walk(_strip(data)))
    return f"imported {n} values from {f} as this project's overrides"
