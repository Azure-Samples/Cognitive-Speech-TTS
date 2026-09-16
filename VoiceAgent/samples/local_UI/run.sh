#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

exec python app.py --host "${LOCAL_UI_HOST:-127.0.0.1}" --port "${LOCAL_UI_PORT:-8097}"
