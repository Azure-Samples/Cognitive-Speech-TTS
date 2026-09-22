#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEVTUNNEL="${ROOT}/.local-mcp-and-ui/tools/devtunnel/bin/devtunnel"

case "${1:-}" in
  "")
    ;;
  -h|--help)
    echo "Usage: ./scripts/login-devtunnel.sh"
    echo "Authenticates the local MCP Dev Tunnel with GitHub device code."
    exit 0
    ;;
  *)
    echo "ERROR: this workflow accepts no provider argument; it uses GitHub" >&2
    exit 1
    ;;
esac

if [[ ! -x "${DEVTUNNEL}" ]]; then
  echo "ERROR: repository-local Dev Tunnel CLI is missing." >&2
  echo "Run ./scripts/setup-local-examples.sh before logging in." >&2
  exit 1
fi

cd "${ROOT}/shared_mcp"
exec "${DEVTUNNEL}" user login --github --use-device-code-auth