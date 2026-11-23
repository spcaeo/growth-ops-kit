"""Find the site's shared components on any stack (2.6.0).

The Next.js checks once looked for fixed paths (components/copy-button.tsx, components/link-cards.tsx ...). An Astro,
Vite or SvelteKit site names and places them differently, so growth.json may say where each one is:

  "components": {"copy": "src/components/frame/CopyOpen.astro", "link_cards": "...", "link_cards_css_class": "lc",
                 "sticky_cta": "...", "call_dialog": "...", "exit_offer": "...", "tick": "...", "tests": ["tests/*.mjs"]}

Every key is optional. Order of discovery for a component: the path in growth.json; else on Next.js the default path;
else the first source file under src/ (or components/, lib/, app/) whose file name is the component's name in kebab or
Pascal case (a few aliases: CopyButton / CopyOpen, LinkCards / LinkCard)."""
from __future__ import annotations

import re
from pathlib import Path

NEXT_DEFAULT = {"copy": "components/copy-button.tsx", "link_cards": "components/link-cards.tsx",
                "sticky_cta": "components/sticky-cta.tsx", "call_dialog": "components/call-dialog.tsx",
                "exit_offer": "components/exit-offer.tsx", "tick": "components/tick.tsx"}
# file stems with the dashes, underscores and case removed ("CopyOpen", "copy-open" and "copy_open" are one stem)
STEMS = {"copy": ("copybutton", "copyopen"), "link_cards": ("linkcards", "linkcard"), "sticky_cta": ("stickycta",),
         "call_dialog": ("calldialog",), "exit_offer": ("exitoffer",), "tick": ("tick",)}
SOURCE_EXT = (".astro", ".tsx", ".jsx", ".vue", ".svelte", ".ts", ".js", ".mjs")
COMPONENT_EXT = (".astro", ".tsx", ".jsx", ".vue", ".svelte")          # a markup file beats a .ts helper of the same name
SEARCH_DIRS = ("src", "components", "lib", "app")
TEST_GLOBS = ("**/*.test.*", "**/*.spec.*", "tests/**/*.ts", "tests/**/*.tsx", "tests/**/*.mjs", "tests/**/*.js",
              "test/**/*.ts", "test/**/*.mjs", "test/**/*.js", "e2e/**/*.ts")
SKIP_PARTS = ("node_modules", ".next", "dist", ".astro", "build", ".git")


def flat(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def is_test(p: Path) -> bool:
    return bool(re.search(r"\.(test|spec)\.", p.name))


def configured(ctx) -> dict:
    return ctx.cfg.get("components") or {}


def find_component(ctx, name: str) -> Path | None:
    """The file of the shared component `name` (copy, link_cards, sticky_cta, call_dialog, exit_offer, tick), or None."""
    repo = ctx.need_repo()
    key = ("comp", name)
    if key in ctx.cache:
        return ctx.cache[key]
    found = None
    given = configured(ctx).get(name)
    if given:
        p = Path(given).expanduser()
        found = p if p.is_absolute() else repo / p
    elif ctx.stack() == "nextjs":
        found = repo / NEXT_DEFAULT[name]
    else:
        stems = STEMS[name]
        hits = []
        for d in SEARCH_DIRS:
            for p in (repo / d).rglob("*") if (repo / d).is_dir() else []:
                if p.is_file() and p.suffix in SOURCE_EXT and not is_test(p) and not any(x in p.parts for x in SKIP_PARTS) \
                        and flat(p.stem) in stems:
                    hits.append(p)
        # a markup file beats a .ts helper; then the order of the aliases; then the shortest path
        hits.sort(key=lambda p: (p.suffix not in COMPONENT_EXT, stems.index(flat(p.stem)), len(p.parts), str(p)))
        found = hits[0] if hits else None
    ctx.cache[key] = found
    return found


def css_prefix(ctx) -> str:
    """The class prefix of the link-preview card ("lc" for .lc .lc__title ...): growth.json components.link_cards_css_class,
    else the first class the link-card component writes (its BEM block), else "lcx" (the Next.js component's)."""
    given = configured(ctx).get("link_cards_css_class")
    if given:
        return given.strip(".")
    if ctx.stack() == "nextjs":
        return "lcx"
    f = find_component(ctx, "link_cards")
    if f and f.is_file():
        m = re.search(r"""class(?:Name)?(?::list)?=\{?\[?\s*['"]([a-z][a-z0-9-]*)(?:__[a-z0-9-]+)?[ '"]""", f.read_text(errors="replace"))
        if m:
            return m.group(1)
    return "lcx"


def test_files(ctx, extra=()) -> list[Path]:
    """Every test file of the site: growth.json components.tests globs, else the usual places (**/*.test.*, tests/**)."""
    repo = ctx.need_repo()
    globs = tuple(configured(ctx).get("tests") or TEST_GLOBS) + tuple(extra)
    out = set()
    for g in globs:
        out.update(p for p in repo.glob(g) if p.is_file() and not any(x in p.parts for x in SKIP_PARTS))
    return sorted(out)


def in_tree(ctx, f: Path | None) -> bool:
    """True when the page's source tree (its route file and everything it imports) holds the file."""
    return bool(f) and f.resolve() in {p.resolve() for p in ctx.tree_sources()}
