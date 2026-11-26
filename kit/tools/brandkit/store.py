"""brand.generated.json + brand.overrides.json -> brand.json, and the edits that go through it.

A value is a "leaf": {"value": ..., "source": "site" | "override" | "default", "evidence": "..."} plus any extra fields a kind of
value needs (a font leaf also holds its "stack" and "weights"). The merge keeps every leaf the site gave, lets the overrides
change any of them, and fills what neither said from defaults, saying which is which. Only `learn` writes the generated file,
only the owner (by hand or through `set` and `unset`) writes the overrides, and `learn` never touches the overrides.

  <project>/brand/brand.generated.json   what learn read from the site        (written by learn)
  <project>/brand/brand.overrides.json   the owner's changes                    (written by hand, set, unset, import)
  <project>/brand/brand.json             the merge: every value with where it came from (written by every command that changes either)
  <project>/brand/.build-stamp           sha256 of the brand.json the builds were made from
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path

from . import colors as C

SCHEMA = 1
ROLES = ["background", "surface", "text", "muted", "primary", "onPrimary", "accent", "border", "link", "success", "warning", "error"]
PROVENANCE = {"source", "evidence", "was", "var"}
FIELDS = {"value", "stack", "weights", "ref", "note", "line_height", "letter_spacing", "weight"}
SCALE_LEVELS = ["h1", "h2", "h3", "h4", "h5", "h6", "body", "small"]
STATE_DEFAULTS = {"success": "#15803D", "warning": "#B45309", "error": "#B91C1C"}


def leaf(value, source="site", evidence="", **extra) -> dict:
    d = {"value": value, "source": source}
    if evidence:
        d["evidence"] = evidence
    d.update({k: v for k, v in extra.items() if v not in (None, "", [])})
    return d


def is_leaf(x) -> bool:
    return isinstance(x, dict) and "value" in x


def dump(obj) -> str:
    """One spelling of a JSON file, so two builds of the same data are the same bytes."""
    return json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def brand_dir(project) -> Path:
    return Path(project) / "brand"


def read_json(path: Path, default=None):
    try:
        data = json.loads(Path(path).read_text())
        return data if isinstance(data, dict) else default
    except (OSError, ValueError):
        return default


def get(tree, path: str):
    node = tree
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def val(tree, path: str, default=None):
    """The value of the leaf at `path` (colors.primary), or `default`."""
    node = get(tree, path)
    return node["value"] if is_leaf(node) else default


def put(tree: dict, path: str, node) -> None:
    parts = path.split(".")
    cur = tree
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = node


# ---- merge ---------------------------------------------------------------------------------------------------------------
def _merge(gen, ovr, path=""):
    """Deep merge: dicts merge key by key; a leaf in the overrides changes the generated leaf (keeping what the override does not say)."""
    if is_leaf(ovr):
        base = gen if is_leaf(gen) else {}
        out = {k: v for k, v in base.items() if k not in PROVENANCE}
        out.update({k: v for k, v in ovr.items() if k not in PROVENANCE})
        out["source"] = "override"
        if is_leaf(gen) and gen.get("value") != out["value"]:
            out["was"] = gen["value"]
        return out
    if isinstance(ovr, dict) and (isinstance(gen, dict) or gen is None):
        out = dict(gen or {})
        for k, v in ovr.items():
            if k.startswith("_"):
                continue
            out[k] = _merge(out.get(k), v, f"{path}.{k}" if path else k)
        return out
    return copy.deepcopy(ovr) if gen is None else gen


def _drop_stale_states(tree: dict, ovr: dict) -> None:
    """The primary colour was changed by hand: the learned hover and focus looks of the primary button belonged to the old colour."""
    if is_leaf(get(ovr, "colors.primary")) or is_leaf(get(ovr, "colors.onPrimary")):
        prim = get(tree, "components.button.primary")
        if isinstance(prim, dict):
            for state in ("hover", "focus"):
                if state in prim and not get(ovr, f"components.button.primary.{state}"):
                    del prim[state]


def merge(generated: dict | None, overrides: dict | None) -> dict:
    """The brand: generated + overrides + defaults, as one tree of leaves."""
    gen = copy.deepcopy(generated or {})
    ovr = overrides or {}
    gen.pop("schema", None)
    tree = _merge(gen, {k: v for k, v in ovr.items() if not k.startswith("_")})
    _drop_stale_states(tree, ovr)
    _follow_refs(tree)
    fill_defaults(tree)
    _follow_refs(tree)
    tree["schema"] = SCHEMA
    return tree


def _walk(node, path=""):
    if is_leaf(node):
        yield path, node
    elif isinstance(node, dict):
        for k, v in node.items():
            yield from _walk(v, f"{path}.{k}" if path else k)


def _follow_refs(tree: dict) -> None:
    """A learned button colour that was the primary colour follows the primary colour (unless the owner set it itself)."""
    for _p, lf in list(_walk(tree)):
        ref = lf.get("ref")
        if ref and lf.get("source") != "override":
            target = val(tree, ref)
            if target is not None and target != lf["value"]:
                lf["value"] = target


# ---- defaults ------------------------------------------------------------------------------------------------------------
def _dflt(tree: dict, path: str, value, why: str, **extra) -> None:
    if get(tree, path) is None:
        put(tree, path, leaf(value, "default", why, **extra))


def fill_defaults(tree: dict) -> None:
    """Everything neither the site nor the owner said, so every kit is complete. Each is marked "default"."""
    def col(role, fallback):               # a colour typed wrongly by hand must not stop the merge: `check` reports it
        v = val(tree, f"colors.{role}")
        return v if C.valid_hex(v) else fallback
    _dflt(tree, "colors.background", "#FFFFFF", "white page")
    _dflt(tree, "colors.text", "#111827", "near-black text")
    bg, tx = col("background", "#FFFFFF"), col("text", "#111827")
    _dflt(tree, "colors.surface", C.mix(bg, tx, 0.04), "the page colour with 4% of the text colour")
    sf = col("surface", bg)
    share = next((s / 100 for s in range(40, -1, -5) if min(C.contrast(C.mix(tx, bg, s / 100), bg), C.contrast(C.mix(tx, bg, s / 100), sf)) >= 4.5), 0.0)
    _dflt(tree, "colors.muted", C.mix(tx, bg, share), f"the text colour {round(share * 100)}% toward the page colour (as soft as still passes AA on the page and on panels)")
    _dflt(tree, "colors.primary", "#2563EB", "no button or brand colour was found")
    pr = col("primary", "#2563EB")
    _dflt(tree, "colors.onPrimary", "#FFFFFF" if C.contrast("#FFFFFF", pr) >= C.contrast("#000000", pr) else "#000000", "the better of white and black on the primary")
    _dflt(tree, "colors.border", C.mix(bg, tx, 0.15), "the page colour with 15% of the text colour")
    _dflt(tree, "colors.link", pr, "links follow the primary colour")
    for k, v in STATE_DEFAULTS.items():
        _dflt(tree, f"colors.{k}", v, "a standard accessible " + k + " colour")
    body = val(tree, "typography.families.body")
    _dflt(tree, "typography.families.body", "system-ui", "the system font", stack="system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif", weights=[400, 700])
    body = val(tree, "typography.families.body")
    if get(tree, "typography.families.heading") is None:
        put(tree, "typography.families.heading", leaf(body, "default", "headings use the body font", stack=get(tree, "typography.families.body").get("stack", ""),
                                                      weights=get(tree, "typography.families.body").get("weights", [400, 700])))
    _fill_scale(tree)
    _dflt(tree, "spacing.unit", 8, "an 8px grid")
    _dflt(tree, "spacing.steps", [4, 8, 12, 16, 24, 32, 48, 64], "a common 4/8px scale")
    _dflt(tree, "radius.control", 8, "buttons and fields")
    _dflt(tree, "radius.card", 12, "cards and panels")
    _dflt(tree, "radius.pill", 999, "fully round")
    _dflt(tree, "logo.clearSpace", "0.5 x the logo height", "half the logo's height on every side")
    _dflt(tree, "logo.minHeight", 24, "the smallest height, in pixels, that stays readable on screen")
    _fill_button(tree)


def _fill_scale(tree: dict) -> None:
    """Headings the site did not show (many pages have no h5 or h6) sit between the nearest ones it did, so the scale never goes up as the level goes down."""
    body_px = _num(val(tree, "typography.scale.body")) or 16
    _dflt(tree, "typography.scale.body", f"{_fmt(body_px)}px", "16px body text", line_height=1.5, weight=400)
    h1 = _num(val(tree, "typography.scale.h1")) or round(body_px * 2.5)
    _dflt(tree, "typography.scale.h1", f"{_fmt(h1)}px", "2.5 x the body size", line_height=1.2, weight=700)
    sizes = {i: _num(val(tree, f"typography.scale.h{i}")) for i in range(1, 7)}
    sizes[7] = body_px                                      # the body is the bottom of the ladder
    for i in range(2, 7):
        if sizes[i]:
            continue
        lo = max(j for j in range(1, i) if sizes[j])
        hi = min(j for j in range(i + 1, 8) if sizes[j])
        size = max(body_px, min(sizes[lo], round(sizes[lo] * (sizes[hi] / sizes[lo]) ** ((i - lo) / (hi - lo)))))
        _dflt(tree, f"typography.scale.h{i}", f"{_fmt(size)}px", "between the nearest headings the site shows", line_height=1.3, weight=700)
        sizes[i] = size
    _dflt(tree, "typography.scale.small", f"{_fmt(round(body_px * 0.875))}px", "7/8 of the body size", line_height=1.4, weight=400)


def _fill_button(tree: dict) -> None:
    pr, on = val(tree, "colors.primary"), val(tree, "colors.onPrimary")
    pr = pr if C.valid_hex(pr) else "#2563EB"
    base = "components.button.primary"
    rad = val(tree, "radius.control")
    for k, v, why in [("rest.background", pr, "the primary colour"), ("rest.color", on, "text on the primary colour"),
                      ("rest.radius", rad, "the control radius"), ("rest.padding", "12px 24px", "a comfortable tap size"),
                      ("rest.font_size", val(tree, "typography.scale.body"), "the body size"), ("rest.font_weight", 600, "semi-bold"),
                      ("hover.background", C.scale(pr)[600], "the primary, one shade darker"), ("hover.color", on, "text on the primary colour"),
                      ("focus.outline_color", pr, "a ring in the primary colour"), ("focus.outline_width", 2, "2px ring"), ("focus.outline_offset", 2, "2px gap")]:
        _dflt(tree, f"{base}.{k}", v, why)
    if get(tree, f"{base}.focus.background") is None:
        _dflt(tree, f"{base}.focus.background", val(tree, f"{base}.rest.background"), "as at rest")
        _dflt(tree, f"{base}.focus.color", val(tree, f"{base}.rest.color"), "as at rest")


def _num(v):
    m = re.match(r"^\s*([\d.]+)\s*px\s*$", str(v)) if v is not None else None
    return float(m.group(1)) if m else None


def _fmt(n) -> str:
    return str(int(n)) if float(n) == int(n) else str(round(n, 2))


# ---- edits ---------------------------------------------------------------------------------------------------------------
def coerce(text: str):
    """A value typed on the command line: JSON when it parses (numbers, true, lists), else the text itself."""
    try:
        return json.loads(text)
    except ValueError:
        return text


def resolve_path(merged: dict, path: str) -> str:
    """colors.primary names a value: it means colors.primary.value. A path into a leaf's own fields (colors.primary.value) is kept."""
    parts = path.strip(".").split(".")
    if not parts or any(not p for p in parts):
        raise ValueError(f"not a path: {path!r}")
    node = get(merged, ".".join(parts))
    if is_leaf(node):
        return ".".join(parts + ["value"])
    if parts[-1] in FIELDS and is_leaf(get(merged, ".".join(parts[:-1]))):
        return ".".join(parts)
    if node is None and parts[0] == "colors" and len(parts) == 2:
        return ".".join(parts + ["value"])             # a new colour: colors.partner
    if node is None and len(parts) >= 2 and parts[-1] in FIELDS:
        return ".".join(parts)
    if node is None:
        raise ValueError(f"no value at {path}. Look at brand/brand.json for the names (for example colors.primary, typography.families.body, spacing.unit).")
    raise ValueError(f"{path} is a group of values, not one value. Name one inside it (for example {path}.<name>).")


def check_value(path: str, value):
    """Validate and normalise a value being set; raises ValueError with a plain reason."""
    if path.startswith("colors.") and path.endswith(".value"):
        if C.parse(value) is None:
            raise ValueError(f"{value!r} is not a colour. Use a hex such as #0B6E4F.")
        return C.to_hex(value)
    if path.startswith("typography.scale.") and path.endswith(".value"):
        if _num(value) is None:
            if isinstance(value, (int, float)):
                return f"{_fmt(value)}px"
            raise ValueError(f"{value!r} is not a size. Use pixels, for example 48px.")
    if path.endswith((".stack", ".weights")) and path.startswith("typography.") and value in ("", None):
        raise ValueError("a font needs a value")
    return value


def set_override(overrides: dict, merged: dict, path: str, value) -> str:
    full = resolve_path(merged, path)
    value = check_value(full, value)
    put(overrides, full, value)
    return full


def unset_override(overrides: dict, path: str) -> bool:
    """Remove an override: the exact path, a leaf (path.value), or a whole group. True when something was removed."""
    parts = path.strip(".").split(".")
    for cand in (parts, parts + ["value"]):
        stack, node = [], overrides
        for p in cand[:-1]:
            if not isinstance(node, dict) or p not in node:
                break
            stack.append((node, p))
            node = node[p]
        else:
            if isinstance(node, dict) and cand[-1] in node:
                del node[cand[-1]]
                for parent, key in reversed(stack):         # tidy: an emptied group goes too
                    if parent[key] == {} or (is_leaf(parent[key]) is False and not any(not k.startswith("_") for k in parent[key])):
                        del parent[key]
                    else:
                        break
                return True
    return False


# ---- files ---------------------------------------------------------------------------------------------------------------
def sha(path: Path) -> str:
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return ""


def load_all(project):
    d = brand_dir(project)
    return read_json(d / "brand.generated.json"), read_json(d / "brand.overrides.json", {}) or {}, read_json(d / "brand.json")


def write_merged(project) -> dict:
    """Merge the two files into brand.json (rewritten only when it changes) and return the tree."""
    d = brand_dir(project)
    gen, ovr, _ = load_all(project)
    tree = merge(gen, ovr)
    d.mkdir(parents=True, exist_ok=True)
    text = dump(tree)
    f = d / "brand.json"
    if not f.is_file() or f.read_text() != text:
        f.write_text(text)
    return tree


def current_tree(project) -> dict:
    gen, ovr, _ = load_all(project)
    return merge(gen, ovr)


def status(project) -> tuple[bool | None, str]:
    """(ok, note) for the doctor: None (open) when brand.json is missing or out of date, True when it and its builds are current."""
    d = brand_dir(project)
    f = d / "brand.json"
    if not f.is_file():
        return None, "no brand kit yet (brand/brand.json)"
    gen, ovr, on_disk = load_all(project)
    if on_disk is None:
        return None, "brand/brand.json is not readable"
    if dump(merge(gen, ovr)) != f.read_text():
        return None, "brand/brand.json is out of date with the generated and override files"
    stamp = d / ".build-stamp"
    if not stamp.is_file() or stamp.read_text().strip() != sha(f):
        return None, "the guidelines and token files are not built from this brand.json"
    return True, f"brand kit current: {len(ROLES)} colour roles, guidelines and tokens built"
