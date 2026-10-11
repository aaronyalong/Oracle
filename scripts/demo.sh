#!/usr/bin/env bash
# Walk through the whole pipeline, then answer questions until you press Enter on an empty line.
# Usage: scripts/demo.sh [vault]   (default: sample-vault)
set -euo pipefail

cd "$(dirname "$0")/.."
VAULT="${1:-sample-vault}"
PY=".venv/bin/python"
export PYTHONWARNINGS="ignore::DeprecationWarning"  # hide a warning from inside chromadb

if [[ ! -x "$PY" ]]; then
  echo "No virtual environment found. Run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

step() { printf '\n\033[1m== %s ==\033[0m\n' "$1"; }

step "1. Parse the vault"
"$PY" src/ingest.py --vault "$VAULT"

step "2. Chunk notes (first 2 shown)"
"$PY" src/chunking.py --vault "$VAULT" --show 2

step "3. Index (only changed notes are re-embedded)"
"$PY" src/index.py --vault "$VAULT"

if [[ "$VAULT" == "sample-vault" ]]; then
  step "4. Retrieval scores"
  "$PY" src/evaluate.py --vault "$VAULT" --k 1 3
fi

step "Ask questions (empty line to quit, start with ? to also show the context the model saw)"
while read -rp $'\n> ' question; do
  [[ -z "$question" ]] && break
  if [[ "$question" == \?* ]]; then
    "$PY" src/query.py "${question#\?}" --show-context
  else
    "$PY" src/query.py "$question"
  fi
done
