#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT}/.env.local"

command -v docker >/dev/null 2>&1 || {
  echo "ERROR: docker is required" >&2
  exit 1
}
command -v openssl >/dev/null 2>&1 || {
  echo "ERROR: openssl is required to generate a local bearer token" >&2
  exit 1
}

if [[ ! -s "${ENV_FILE}" ]]; then
  umask 077
  printf 'SHARED_MCP_TOKEN=%s\n' "$(openssl rand -hex 32)" > "${ENV_FILE}"
  printf 'FINANCE_OTP_DEMO_ACCESS_CODE=12345007\n' >> "${ENV_FILE}"
  echo "created ${ENV_FILE}"
fi

cd "${ROOT}"
exec docker compose --env-file "${ENV_FILE}" up --build

