#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -d "$SCRIPT_DIR/.venv" ]; then
  python3 -m venv "$SCRIPT_DIR/.venv"
fi
"$SCRIPT_DIR/.venv/bin/pip" install --quiet -r "$SCRIPT_DIR/requirements.txt"
exec "$SCRIPT_DIR/.venv/bin/python3" "$SCRIPT_DIR/score_evals.py" "$@"
