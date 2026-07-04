#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_SCOPE="${INSTALL_SCOPE:-system}"
BIN_DIR="${BIN_DIR:-}"
SUDO_CMD=""

usage() {
  cat <<'EOF'
Usage: ./scripts/install.sh [--system|--user] [--bin-dir DIR]

Options:
  --system       Install to a system-wide bin directory (default: /usr/local/bin).
  --user         Install to user-local bin directory (~/.local/bin).
  --bin-dir DIR  Override installation directory explicitly.
  -h, --help     Show this help.

Environment:
  INSTALL_SCOPE=system|user
  BIN_DIR=/custom/bin
EOF
}

detect_python_with_clingo() {
  if [[ -x "${ROOT_DIR}/.venv/bin/python" ]]; then
    if "${ROOT_DIR}/.venv/bin/python" - <<'PY' >/dev/null 2>&1
import clingo
PY
    then
      echo "${ROOT_DIR}/.venv/bin/python"
      return 0
    fi
  fi

  for candidate in python3.13 python3.12 python3.11 python3.10 python3.9 python3; do
    if ! command -v "${candidate}" >/dev/null 2>&1; then
      continue
    fi
    if "${candidate}" - <<'PY' >/dev/null 2>&1
import clingo
PY
    then
      command -v "${candidate}"
      return 0
    fi
  done

  return 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --system)
      INSTALL_SCOPE="system"
      shift
      ;;
    --user)
      INSTALL_SCOPE="user"
      shift
      ;;
    --bin-dir)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for --bin-dir." >&2
        exit 1
      fi
      BIN_DIR="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if ! PYTHON_BIN="$(detect_python_with_clingo)"; then
  echo "Python with clingo bindings not found." >&2
  echo "Run ./scripts/setup_venv.sh first, then retry installation." >&2
  exit 1
fi

if [[ -z "${BIN_DIR}" ]]; then
  if [[ "${INSTALL_SCOPE}" == "system" ]]; then
    BIN_DIR="/usr/local/bin"
  else
    BIN_DIR="$HOME/.local/bin"
  fi
fi

if [[ "${INSTALL_SCOPE}" == "system" && ! -w "${BIN_DIR}" ]]; then
  if command -v sudo >/dev/null 2>&1; then
    SUDO_CMD="sudo"
  else
    echo "No write permission for ${BIN_DIR} and sudo is unavailable." >&2
    echo "Use --user or set --bin-dir to a writable directory." >&2
    exit 1
  fi
fi

chmod +x "${ROOT_DIR}/klingo"
${SUDO_CMD} mkdir -p "$BIN_DIR"

tmp_launcher="$(mktemp)"
cat > "${tmp_launcher}" <<EOF
#!/usr/bin/env bash
exec "${PYTHON_BIN}" "${ROOT_DIR}/klingo" "\$@"
EOF
chmod +x "${tmp_launcher}"
${SUDO_CMD} install -m 755 "${tmp_launcher}" "${BIN_DIR}/klingo"
rm -f "${tmp_launcher}"

echo "Installed klingo to $BIN_DIR/klingo"
echo "Interpreter: $PYTHON_BIN"
echo "Scope: ${INSTALL_SCOPE}"

resolved_path="$(command -v klingo 2>/dev/null || true)"
if [[ -n "${resolved_path}" && "${resolved_path}" != "${BIN_DIR}/klingo" ]]; then
  echo "Warning: current PATH resolves klingo to ${resolved_path}, not ${BIN_DIR}/klingo" >&2
fi
