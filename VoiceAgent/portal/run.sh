#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

exec .venv/bin/python demo_server.py \
  --bind "${VOICE_PORTAL_HOST:-127.0.0.1}" \
  --port "${DEMO_PORT:-9527}"
