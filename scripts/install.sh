#!/usr/bin/env bash
set -euo pipefail

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required." >&2
  exit 1
fi

if ! python3 - <<'PY' >/dev/null 2>&1
import clingo
PY
then
  echo "Python-enabled clingo is required. Install clingo with Python bindings." >&2
  exit 1
fi

chmod +x ./klingo
chmod +x ./scripts/pretty_sudoku_from_klingo.py

BIN_DIR="${BIN_DIR:-$HOME/.local/bin}"
mkdir -p "$BIN_DIR"

ln -sf "$(pwd)/klingo" "$BIN_DIR/klingo"
ln -sf "$(pwd)/scripts/pretty_sudoku_from_klingo.py" "$BIN_DIR/klingo-sudoku"

echo "Installed klingo to $BIN_DIR/klingo"
echo "Installed klingo-sudoku to $BIN_DIR/klingo-sudoku"
