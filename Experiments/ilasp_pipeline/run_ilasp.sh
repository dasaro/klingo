#!/usr/bin/env bash
set -euo pipefail

BIAS="$1"
EXAMPLES="$2"
OUT="$3"

ILASP --version=4 "$BIAS" "$EXAMPLES" > "$OUT"

printf "wrote learned rules to %s\n" "$OUT"
