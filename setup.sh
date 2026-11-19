#!/usr/bin/env bash
# One command on a clean machine: checks the tools the kit needs, installs its Python add-ons into a private virtual
# environment (outside the repo), runs the tests on the demo site, and ends "SETUP DONE" or lists what failed.
#
#   bash setup.sh              # check, install, test
#   bash setup.sh --browsers   # also download the headless browser (Chromium) for the contrast and phone checks
#   bash setup.sh --help
#
# Needs: Python 3.10 or newer and git. Node is needed only for the Next.js adapter (a site whose growth.json says
# "stack": "nextjs"); every other stack works without it. Nothing is installed outside the virtual environment, except one
# link: ~/.local/bin/growth points at this checkout ($GROWTH_BIN changes the folder), and no
# key, account or network call (beyond downloading the pinned add-ons from PyPI) is used. The virtual environment lives in
# $GROWTH_VENV (default ~/.growth-ops-kit/venv); the `growth` command finds and uses it by itself.
set -u
cd "$(dirname "$0")" || exit 1
ROOT=$(pwd)
BROWSERS=0
for a in "$@"; do
  case "$a" in
    --browsers) BROWSERS=1 ;;
    -h|--help) sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $a (try --help)"; exit 2 ;;
  esac
done

if [ -t 1 ]; then G=$'\033[32m'; R=$'\033[31m'; Y=$'\033[33m'; N=$'\033[0m'; else G=""; R=""; Y=""; N=""; fi
FAILS=()
ok()   { echo "${G}OK${N}    $1"; }
warn() { echo "${Y}NOTE${N}  $1"; }
bad()  { echo "${R}FAIL${N}  $1"; FAILS+=("$1"); }

# 1. Python 3.10+
PY=""
for c in python3 python3.13 python3.12 python3.11 python3.10; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then PY=$(command -v "$c"); break; fi
done
if [ -n "$PY" ]; then ok "Python $("$PY" -c 'import sys; print(".".join(map(str, sys.version_info[:3])))') ($PY)"; else bad "Python 3.10 or newer not found (install it from python.org or your package manager)"; fi

# 2. git
if command -v git >/dev/null 2>&1; then ok "git $(git --version | awk '{print $3}')"; else bad "git not found (install it: https://git-scm.com)"; fi

# 3. Node: only the Next.js adapter needs it
if command -v node >/dev/null 2>&1; then ok "Node $(node --version) (needed only for a Next.js site's own checks)"; else warn "Node not found: needed only for the Next.js adapter, not for the demo site or any other stack"; fi

# 4. Virtual environment and the pinned add-ons
VENV="${GROWTH_VENV:-$HOME/.growth-ops-kit/venv}"
if [ -n "$PY" ]; then
  if [ ! -x "$VENV/bin/python" ]; then
    mkdir -p "$(dirname "$VENV")" && "$PY" -m venv "$VENV" >/dev/null 2>&1 || bad "could not create the virtual environment at $VENV"
  fi
  if [ -x "$VENV/bin/python" ]; then
    if "$VENV/bin/python" -m pip install --quiet --disable-pip-version-check -r requirements.txt; then
      ok "add-ons installed in $VENV ($(grep -vcE '^#|^$' requirements.txt) packages, exact versions)"
    else
      bad "could not install requirements.txt (check the network and try again)"
    fi
  fi
fi

# 5. Browser (optional)
if [ "$BROWSERS" = 1 ] && [ -x "$VENV/bin/python" ]; then
  if "$VENV/bin/python" -m playwright install chromium >/dev/null 2>&1; then ok "headless Chromium downloaded"; else bad "could not download Chromium (python -m playwright install chromium)"; fi
elif [ "$BROWSERS" = 0 ]; then
  warn "headless browser not installed: the contrast and phone checks print SKIP. Run: bash setup.sh --browsers"
fi

# 6. The `growth` command on the PATH (a link in ~/.local/bin; nothing else outside the repo and the virtual environment)
BIN="${GROWTH_BIN:-$HOME/.local/bin}"
if mkdir -p "$BIN" 2>/dev/null && ln -sf "$ROOT/growth" "$BIN/growth" 2>/dev/null; then
  ok "growth command linked: $BIN/growth"
  case ":$PATH:" in
    *":$BIN:"*) ;;
    *) warn "$BIN is not on your PATH. Add this line to your shell profile (~/.zshrc or ~/.bashrc): export PATH=\"$BIN:\$PATH\"" ;;
  esac
else
  warn "could not link growth into $BIN. Use the full path $ROOT/growth, or: export PATH=\"$ROOT:\$PATH\""
fi

# 7. Tests (the demo site included), then the leak check
if [ -x "$VENV/bin/python" ]; then
  [ "$BROWSERS" = 1 ] || export GROWTH_SKIP_BROWSER=1
  OUT=$(PYTHONDONTWRITEBYTECODE=1 "$VENV/bin/python" -m pytest -p no:cacheprovider tests -q 2>&1); CODE=$?
  if [ $CODE -eq 0 ]; then ok "tests: $(printf '%s\n' "$OUT" | tail -1)"; else printf '%s\n' "$OUT" | tail -25; bad "tests failed (output above)"; fi
  if "$VENV/bin/python" kit/tools/leak_check.py --root "$ROOT" >/dev/null 2>&1; then ok "leak check: no key, personal address or private word in the files"; else bad "leak check found something (run: ./growth leak_check)"; fi
fi

echo
if [ ${#FAILS[@]} -eq 0 ]; then
  echo "${G}SETUP DONE${N}"
  echo "Next: growth help    |    growth new-project ~/my-site --site https://example.com    |    read book/README.md"
  echo "(If \`growth\` is not found, open a new terminal after adding the PATH line above, or use ./growth from this folder.)"
  exit 0
fi
echo "${R}SETUP FAILED${N}: ${#FAILS[@]} problem(s):"
for f in "${FAILS[@]}"; do echo "  - $f"; done
exit 1
