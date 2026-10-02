#!/usr/bin/env bash
# Create .venv from the pinned Python in .python-version and install exact deps.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if command -v uv >/dev/null 2>&1; then
  UV=(uv)
elif [[ -x "${HOME}/.local/bin/uv" ]]; then
  UV=("${HOME}/.local/bin/uv")
else
  echo "uv is required. Install it from https://docs.astral.sh/uv/ and re-run." >&2
  exit 1
fi

VER="$(tr -d '[:space:]' < .python-version)"
if [[ -z "$VER" ]]; then
  echo ".python-version is empty." >&2
  exit 1
fi

if [[ -x .venv/bin/python ]]; then
  ACTUAL="$(.venv/bin/python -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])')"
  if [[ "$ACTUAL" != "$VER" ]]; then
    echo "Recreating .venv (found Python ${ACTUAL}, need ${VER})."
    rm -rf .venv
  fi
fi

if [[ ! -x .venv/bin/python ]]; then
  "${UV[@]}" venv --managed-python --python "$VER" .venv
fi

"${UV[@]}" pip install --python .venv -r requirements.txt -r requirements-dev.txt
echo "Environment ready: $(.venv/bin/python -c 'import sys; print(sys.executable)')"
