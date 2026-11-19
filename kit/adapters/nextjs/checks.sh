#!/usr/bin/env bash
# Run ONLY the checks a change touches (work like a freelancer: never run tests or builds the change cannot affect).
# Next.js adapter. Run inside the site's checkout or worktree:
#   bash <kit>/kit/adapters/nextjs/checks.sh            # changes vs the production branch (committed + uncommitted)
#   bash <kit>/kit/adapters/nextjs/checks.sh --dry-run  # only print the plan
#
# Settings (environment, all optional):
#   GROWTH_BRANCH          the production branch                                       (default: main, else master)
#   GROWTH_REMOTE          its remote; with no such remote the local branch is used     (default: origin)
#   GROWTH_CONTENT_TESTS   the site's content test files, run when content changes   (default: none)
#   GROWTH_BUILD_ENV       variables for the production build, e.g. "PREVIEW=0"       (default: none)
#
# What runs, by what changed:
#   copy only inside app/ or components/ (.tsx/.css) -> nothing local; the host's build is the gate
#   content/*, public/images/*                        -> the content tests (GROWTH_CONTENT_TESTS)
#   lib/*.ts, scripts/*, middleware.ts                -> vitest "related" tests for those files + build
#   app/**/page.tsx structure, sitemap, robots,       -> build (production view)
#   next.config.*, package*.json, tsconfig
set -euo pipefail
DRY=0; [ "${1:-}" = "--dry-run" ] && DRY=1
CONTENT_TESTS=${GROWTH_CONTENT_TESTS:-}
BUILD_ENV=${GROWTH_BUILD_ENV:-}
REMOTE=${GROWTH_REMOTE:-origin}
BASE=""
for b in ${GROWTH_BRANCH:-main master}; do
  git fetch -q "$REMOTE" "$b" 2>/dev/null || true
  for cand in "$REMOTE/$b" "$b"; do
    if git rev-parse --verify -q "$cand^{commit}" >/dev/null 2>&1; then BASE=$cand; break 2; fi
  done
done
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo "SKIP: not inside a git checkout; run this inside the site's checkout or worktree."; exit 0; }
if [ -z "$BASE" ]; then
  echo "No production branch found (tried ${GROWTH_BRANCH:-main and master}); checking uncommitted changes only. Set GROWTH_BRANCH (and GROWTH_REMOTE) to compare a branch."
  BASE=HEAD
fi
CHANGED=$( { git diff --name-only "$BASE"...HEAD; git diff --name-only HEAD; git ls-files --others --exclude-standard; } | sort -u | grep -v '^$' || true)
[ -z "$CHANGED" ] && { echo "No changes vs $BASE: nothing to check."; exit 0; }

TESTS=(); RELATED=(); BUILD=0; COPY_ONLY=1
while read -r f; do
  case "$f" in
    content/*|public/images/*)
      [ -n "$CONTENT_TESTS" ] && TESTS+=($CONTENT_TESTS); COPY_ONLY=0 ;;
    lib/*.test.ts|scripts/*.test.mjs) TESTS+=("$f"); COPY_ONLY=0 ;;
    lib/*|scripts/*|middleware.ts) RELATED+=("$f"); BUILD=1; COPY_ONLY=0 ;;
    app/sitemap.ts|app/robots.ts|app/rss.xml/*|next.config.*|package.json|package-lock.json|tsconfig.json|postcss.config.*)
      BUILD=1; COPY_ONLY=0 ;;
    app/*|components/*) : ;;  # copy or layout: judged below
    docs/*|*.md) : ;;          # notes only
    *) BUILD=1; COPY_ONLY=0 ;;
  esac
done <<< "$CHANGED"

# A .tsx change that adds/removes imports, exports or routes is code, not copy: build it.
if git diff "$BASE" -- 'app/*' 'components/*' | grep -qE '^[+-][[:space:]]*(import |export |generateStaticParams|async function)'; then BUILD=1; COPY_ONLY=0; fi
[ -n "$(echo "$CHANGED" | grep -E '^app/.*/(page|layout|route)\.tsx?$' | while read -r f; do git cat-file -e "$BASE:$f" 2>/dev/null || echo new; done)" ] && BUILD=1 && COPY_ONLY=0

mapfile_unique() { printf '%s\n' "$@" | sort -u | grep -v '^$' || true; }
TESTS_U=$(mapfile_unique "${TESTS[@]:-}"); RELATED_U=$(mapfile_unique "${RELATED[@]:-}")

echo "Changed: $(echo "$CHANGED" | wc -l | tr -d ' ') file(s)"
[ -n "$TESTS_U" ]   && echo "Tests:   $(echo $TESTS_U)"
[ -n "$RELATED_U" ] && echo "Related: vitest related $(echo $RELATED_U)"
[ "$BUILD" = 1 ]    && echo "Build:   ${BUILD_ENV:+$BUILD_ENV }npm run build"
[ "$COPY_ONLY" = 1 ] && [ -z "$TESTS_U$RELATED_U" ] && [ "$BUILD" = 0 ] && \
  echo "Copy/layout only: no local tests or build. the host builds it; check the page live (or locally if it changes layout)."
[ "$DRY" = 1 ] && exit 0

[ -n "$TESTS_U" ]   && npx vitest run $TESTS_U
[ -n "$RELATED_U" ] && npx vitest related --run $RELATED_U --passWithNoTests
[ "$BUILD" = 1 ]    && env $BUILD_ENV NEXT_TELEMETRY_DISABLED=1 npm run build
echo "Checks done."
