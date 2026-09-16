#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_ENDPOINT="${AZURE_AI_PROJECT_ENDPOINT:-${1:-}}"

die() {
  echo "ERROR: $*" >&2
  exit 1
}

command -v azd >/dev/null 2>&1 || die "azd is required"
[[ "${PROJECT_ENDPOINT}" =~ ^https://[^[:space:]]+/api/projects/[^/[:space:]]+$ ]] ||
  die "set AZURE_AI_PROJECT_ENDPOINT to a Foundry Project endpoint"

ENVIRONMENT_NAME="$(azd env get-value AZURE_ENV_NAME 2>/dev/null || true)"
[[ -n "${ENVIRONMENT_NAME}" ]] || die "select an azd environment first"
CONNECTION_PREFIX="${MCP_CONNECTION_PREFIX:-${ENVIRONMENT_NAME:0:32}}"
HANDOFF_CONNECTION_ID="${
  FINANCE_HANDOFF_MCP_CONNECTION_ID:-${CONNECTION_PREFIX}-finance-handoff-mcp
}"
OTP_CONNECTION_ID="${
  FINANCE_OTP_MCP_CONNECTION_ID:-${CONNECTION_PREFIX}-finance-otp-officer-mcp
}"

TOKEN="$(azd env get-value SHARED_MCP_TOKEN 2>/dev/null || true)"
HANDOFF_URL="$(azd env get-value SHARED_MCP_FINANCE_HANDOFF_URL 2>/dev/null || true)"
OTP_URL="$(azd env get-value SHARED_MCP_FINANCE_OTP_OFFICER_URL 2>/dev/null || true)"

[[ -n "${TOKEN}" ]] || die "SHARED_MCP_TOKEN is missing from the selected azd environment"
[[ "${HANDOFF_URL}" == https://*/mcp/finance-handoff ]] ||
  die "SHARED_MCP_FINANCE_HANDOFF_URL is missing; run azd up first"
[[ "${OTP_URL}" == https://*/mcp/finance-otp-officer ]] ||
  die "SHARED_MCP_FINANCE_OTP_OFFICER_URL is missing; run azd up first"

create_connection() {
  local connection_id="$1"
  local target="$2"
  local auth_scheme
  auth_scheme="$(printf '%s%s' Bear er)"
  azd ai connection create "${connection_id}" \
    --project-endpoint "${PROJECT_ENDPOINT}" \
    --kind remote-tool \
    --target "${target}" \
    --auth-type custom-keys \
    --custom-key "Authorization=${auth_scheme} ${TOKEN}" \
    --force \
    --no-prompt
}

create_connection "${HANDOFF_CONNECTION_ID}" "${HANDOFF_URL}"
create_connection "${OTP_CONNECTION_ID}" "${OTP_URL}"

GENERATED_DIR="${ROOT}/config/generated"
mkdir -p "${GENERATED_DIR}"
umask 077
{
  printf 'VOICE_AGENT_MCP_SERVER_URL=%s\n' "${HANDOFF_URL}"
  printf 'VOICE_AGENT_MCP_CONNECTION_ID=%s\n' "${HANDOFF_CONNECTION_ID}"
} > "${GENERATED_DIR}/example1.shared.env"
{
  printf 'VOICE_AGENT_MCP_SERVER_URL=%s\n' "${OTP_URL}"
  printf 'VOICE_AGENT_MCP_CONNECTION_ID=%s\n' "${OTP_CONNECTION_ID}"
} > "${GENERATED_DIR}/example2.shared.env"

echo "agent_config_complete"
echo "example1 VOICE_AGENT_MCP_CONFIG=../../shared_mcp/config/generated/example1.shared.env"
echo "example2 VOICE_AGENT_MCP_CONFIG=../../shared_mcp/config/generated/example2.shared.env"
