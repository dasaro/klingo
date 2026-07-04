#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"

if [[ -n "${PYTHON_BIN:-}" ]]; then
  if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
    echo "PYTHON_BIN='${PYTHON_BIN}' was provided but is not executable." >&2
    exit 1
  fi
else
  for candidate in python3.13 python3.12 python3.11 python3.10 python3.9 python3; do
    if command -v "${candidate}" >/dev/null 2>&1; then
      PYTHON_BIN="${candidate}"
      break
    fi
  done
fi

if [[ -z "${PYTHON_BIN:-}" ]]; then
  echo "No Python 3 interpreter found." >&2
  exit 1
fi

echo "Using Python interpreter: ${PYTHON_BIN}"
# Recreate in place to avoid stale environments tied to a different interpreter.
"${PYTHON_BIN}" -m venv --clear "${VENV_DIR}"
"${VENV_DIR}/bin/python" -m pip install --upgrade pip
"${VENV_DIR}/bin/python" -m pip install -r "${ROOT_DIR}/requirements.txt"

echo "Virtual environment ready at ${VENV_DIR}"
echo "Activate with: source .venv/bin/activate"
