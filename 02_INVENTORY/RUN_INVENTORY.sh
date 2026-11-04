#!/usr/bin/env sh
set -eu
if [ "$#" -lt 1 ]; then
  echo 'Usage: RUN_INVENTORY.sh "/path/to/source"' >&2
  exit 2
fi
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR/.."
python -m engine.registry scan "$@"

