#!/bin/bash
# Start the backend API using the project virtual environment.
# Run from the backend/ directory:  bash start.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SCRIPT_DIR/.venv"

if [ ! -d "$VENV" ]; then
  echo "Virtual environment not found. Run:"
  echo "  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

echo "Starting backend with venv: $VENV"
PYTHONPATH="$SCRIPT_DIR" "$VENV/bin/uvicorn" app.main:app --reload --host 0.0.0.0 --port 8000
