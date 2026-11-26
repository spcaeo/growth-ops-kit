"""Does BRAND.md name what the brand scan found? (`growth doctor` A2.) Pure functions, no network."""
from __future__ import annotations

import json
import re
from pathlib import Path


def _plain(url: str) -> str:
    """A web address as it is compared: no scheme, no www., no query, no trailing slash, lower case."""
    u = re.sub(r"^https?://(?:www\.)?", "", (url or "").strip().lower())
    return u.split("?", 1)[0].split("#", 1)[0].rstrip("/")


def missing_from_brand(scan: dict, brand_text: str) -> tuple[list[str], int]:
    """(what BRAND.md leaves out, how many facts were checked). Checked: every email on the company's domain and every booking
    link the scan found. A fact counts as named when BRAND.md holds it anywhere, so a line "legacy address, not used" is enough."""
    text = (brand_text or "").lower()
    plain_text = re.sub(r"https?://(?:www\.)?", "", text)
    f = scan.get("findings") or {}
    want = [e["email"] for e in f.get("emails") or [] if e.get("group") == "company" and e.get("email")]
    want += [b["url"] for b in f.get("booking_links") or [] if b.get("url")]
    missing = []
    for w in want:
        needle = w.lower() if "@" in w else _plain(w)
        if needle and needle not in (text if "@" in w else plain_text):
            missing.append(w)
    return missing, len(want)


def load_scan(path: Path) -> dict | None:
    """The scan file, or None when it is missing or not readable (a broken file never stops the doctor)."""
    try:
        data = json.loads(Path(path).read_text())
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def check(scan_file: Path, brand_file: Path) -> tuple[bool | None, str]:
    """(ok, note) for doctor: ok None when there is no scan (nothing to check), True when BRAND.md names it all, False when not."""
    if not Path(scan_file).is_file():
        return None, ""
    scan = load_scan(scan_file)
    if scan is None:
        return None, "; brand scan file docs/brand-scan.json is not readable (run growth brand-scan again), not checked"
    when = scan.get("read_on") or "undated"
    try:
        brand = Path(brand_file).read_text(errors="replace")
    except OSError:
        brand = ""
    missing, n = missing_from_brand(scan, brand)
    if not missing:
        return True, f"; brand scan {when}: BRAND.md names the {n} company emails and booking links it found" if n else f"; brand scan {when}: nothing to name"
    shown = ", ".join(missing[:4]) + (f" and {len(missing) - 4} more" if len(missing) > 4 else "")
    return False, f"; brand scan {when}: BRAND.md does not name {len(missing)} of {n} facts found on the site ({shown})"
