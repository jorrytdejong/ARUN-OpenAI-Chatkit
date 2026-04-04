#!/usr/bin/env bash

# Simple helper to start the ChatKit backend (similar to cat-lounge UX).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# If the project folder was moved/copied, .venv may still point at an old absolute path.
if [ -d ".venv" ] && ! .venv/bin/python3 -V >/dev/null 2>&1; then
  echo "Removing stale .venv (Python path no longer valid for this location) ..."
  rm -rf .venv
fi

# Prefer uv when available: `python -m venv` can fail with ensurepip on some macOS
# setups (e.g. python shim in ~/.local/bin). uv venv uses a full CPython install.
if command -v uv >/dev/null 2>&1; then
  if [ ! -d ".venv" ]; then
    echo "Creating virtual env with uv in $PROJECT_ROOT/.venv ..."
    uv venv
  fi
  echo "Installing backend deps (editable) ..."
  uv pip install -e . >/dev/null
else
  if [ ! -d ".venv" ]; then
    echo "Creating virtual env in $PROJECT_ROOT/.venv ..."
    python3 -m venv .venv
  fi
  # shellcheck source=/dev/null
  source .venv/bin/activate
  echo "Installing backend deps (editable) ..."
  pip install -e . >/dev/null
fi

# Load env vars from the repo's .env.local (if present) so OPENAI_API_KEY
# does not need to be exported manually.
ENV_FILE="$PROJECT_ROOT/../.env.local"
if [ -z "${OPENAI_API_KEY:-}" ] && [ -f "$ENV_FILE" ]; then
  echo "Sourcing OPENAI_API_KEY from $ENV_FILE"
  # shellcheck disable=SC1090
  set -a
  . "$ENV_FILE"
  set +a
fi

if [ -z "${OPENAI_API_KEY:-}" ]; then
  echo "Set OPENAI_API_KEY in your environment or in .env.local before running this script."
  exit 1
fi

echo "Starting ChatKit backend on http://127.0.0.1:8000 ..."
if command -v uv >/dev/null 2>&1; then
  exec uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
else
  # shellcheck source=/dev/null
  source .venv/bin/activate
  exec uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
fi
