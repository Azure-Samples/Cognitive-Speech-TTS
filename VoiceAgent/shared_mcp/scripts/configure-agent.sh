#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_ENDPOINT="${AZURE_AI_PROJECT_ENDPOINT:-${1:-}}"
CONFIG_VARIANT="${MCP_CONFIG_VARIANT:-shared}"

die() {
  echo "ERROR: $*" >&2
  exit 1
}

command -v az >/dev/null 2>&1 || die "Azure CLI is required"
[[ "${PROJECT_ENDPOINT}" =~ ^https://[^[:space:]]+/api/projects/[^/[:space:]]+$ ]] ||
  die "set AZURE_AI_PROJECT_ENDPOINT to a Foundry Project endpoint"
[[ "${CONFIG_VARIANT}" =~ ^[a-z0-9-]+$ ]] ||
  die "MCP_CONFIG_VARIANT must contain only lowercase letters, numbers, and hyphens"

TOKEN="${SHARED_MCP_TOKEN:-}"
HANDOFF_URL="${SHARED_MCP_FINANCE_HANDOFF_URL:-}"
OTP_URL="${SHARED_MCP_FINANCE_OTP_OFFICER_URL:-}"
ELEVATOR_URL="${SHARED_MCP_ELEVATOR_SERVICE_URL:-}"
ENVIRONMENT_NAME=""
if [[ -z "${TOKEN}" || -z "${HANDOFF_URL}" || -z "${OTP_URL}" || -z "${ELEVATOR_URL}" ]]; then
  command -v azd >/dev/null 2>&1 ||
    die "azd is required when deployed MCP values are not provided"
  ENVIRONMENT_NAME="$(azd env get-value AZURE_ENV_NAME 2>/dev/null || true)"
  [[ -n "${ENVIRONMENT_NAME}" ]] || die "select an azd environment first"
  TOKEN="${TOKEN:-$(azd env get-value SHARED_MCP_TOKEN 2>/dev/null || true)}"
  HANDOFF_URL="${HANDOFF_URL:-$(azd env get-value SHARED_MCP_FINANCE_HANDOFF_URL 2>/dev/null || true)}"
  OTP_URL="${OTP_URL:-$(azd env get-value SHARED_MCP_FINANCE_OTP_OFFICER_URL 2>/dev/null || true)}"
  ELEVATOR_URL="${ELEVATOR_URL:-$(azd env get-value SHARED_MCP_ELEVATOR_SERVICE_URL 2>/dev/null || true)}"
fi

CONNECTION_PREFIX="${MCP_CONNECTION_PREFIX:-${ENVIRONMENT_NAME:-voice-agent}}"
HANDOFF_CONNECTION_ID="${FINANCE_HANDOFF_MCP_CONNECTION_ID:-${CONNECTION_PREFIX}-finance-handoff-mcp}"
OTP_CONNECTION_ID="${FINANCE_OTP_MCP_CONNECTION_ID:-${CONNECTION_PREFIX}-finance-otp-officer-mcp}"
ELEVATOR_CONNECTION_ID="${ELEVATOR_MCP_CONNECTION_ID:-${CONNECTION_PREFIX}-elevator-service-mcp}"

[[ -n "${TOKEN}" ]] || die "SHARED_MCP_TOKEN is missing from the selected azd environment"
[[ "${HANDOFF_URL}" == https://*/mcp/finance-handoff ]] ||
  die "SHARED_MCP_FINANCE_HANDOFF_URL is missing; run azd up first"
[[ "${OTP_URL}" == https://*/mcp/finance-otp-officer ]] ||
  die "SHARED_MCP_FINANCE_OTP_OFFICER_URL is missing; run azd up first"
[[ "${ELEVATOR_URL}" == https://*/mcp/elevator-service ]] ||
  die "SHARED_MCP_ELEVATOR_SERVICE_URL is missing; run azd up first"
[[ "${HANDOFF_CONNECTION_ID}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] ||
  die "FINANCE_HANDOFF_MCP_CONNECTION_ID is invalid"
[[ "${OTP_CONNECTION_ID}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] ||
  die "FINANCE_OTP_MCP_CONNECTION_ID is invalid"
[[ "${ELEVATOR_CONNECTION_ID}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] ||
  die "ELEVATOR_MCP_CONNECTION_ID is invalid"

PROJECT_HOST="${PROJECT_ENDPOINT#https://}"
PROJECT_HOST="${PROJECT_HOST%%/*}"
ACCOUNT_NAME="${PROJECT_HOST%%.*}"
PROJECT_NAME="${PROJECT_ENDPOINT##*/}"
[[ "${ACCOUNT_NAME}" =~ ^[a-z0-9][a-z0-9-]*$ ]] ||
  die "could not parse the Foundry account name from AZURE_AI_PROJECT_ENDPOINT"
[[ "${PROJECT_NAME}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] ||
  die "could not parse the Foundry Project name from AZURE_AI_PROJECT_ENDPOINT"

PROJECT_RESOURCE_ID="$(
  az resource list \
    --resource-type Microsoft.CognitiveServices/accounts/projects \
    --query "[?name=='${ACCOUNT_NAME}/${PROJECT_NAME}'].id | [0]" \
    --output tsv
)"
[[ -n "${PROJECT_RESOURCE_ID}" ]] ||
  die "the Foundry Project was not found in the active Azure CLI subscription"
ACCOUNT_RESOURCE_ID="${PROJECT_RESOURCE_ID%/projects/*}"

create_connection() {
  local connection_id="$1"
  local target="$2"
  local request_body
  request_body="$(mktemp)"
  chmod 600 "${request_body}"
  printf '%s' "{\"properties\":{\"category\":\"RemoteTool\",\"target\":\"${target}\",\"authType\":\"CustomKeys\",\"isDefault\":false,\"isSharedToAll\":false,\"credentials\":{\"keys\":{\"Authorization\":\"Bearer ${TOKEN}\"}},\"metadata\":{\"displayName\":\"${connection_id}\",\"source\":\"voice-agent-shared-mcp\"}}}" > "${request_body}"
  if ! az rest \
    --method put \
    --url "https://management.azure.com${ACCOUNT_RESOURCE_ID}/connections/${connection_id}?api-version=2025-04-01-preview" \
    --headers Content-Type=application/json \
    --body "@${request_body}" \
    --output none; then
    rm -f "${request_body}"
    die "failed to create Foundry connection ${connection_id}"
  fi
  rm -f "${request_body}"
}

create_connection "${HANDOFF_CONNECTION_ID}" "${HANDOFF_URL}"
create_connection "${OTP_CONNECTION_ID}" "${OTP_URL}"
create_connection "${ELEVATOR_CONNECTION_ID}" "${ELEVATOR_URL}"

GENERATED_DIR="${ROOT}/config/generated"
mkdir -p "${GENERATED_DIR}"
umask 077
{
  printf 'VOICE_AGENT_MCP_SERVER_URL=%s\n' "${HANDOFF_URL}"
  printf 'VOICE_AGENT_MCP_CONNECTION_ID=%s\n' "${HANDOFF_CONNECTION_ID}"
} > "${GENERATED_DIR}/example1.${CONFIG_VARIANT}.env"
{
  printf 'VOICE_AGENT_MCP_SERVER_URL=%s\n' "${OTP_URL}"
  printf 'VOICE_AGENT_MCP_CONNECTION_ID=%s\n' "${OTP_CONNECTION_ID}"
} > "${GENERATED_DIR}/example2.${CONFIG_VARIANT}.env"
{
  printf 'VOICE_AGENT_MCP_SERVER_URL=%s\n' "${ELEVATOR_URL}"
  printf 'VOICE_AGENT_MCP_CONNECTION_ID=%s\n' "${ELEVATOR_CONNECTION_ID}"
} > "${GENERATED_DIR}/example3.${CONFIG_VARIANT}.env"

echo "agent_config_complete"
echo "example1 VOICE_AGENT_MCP_CONFIG=../../shared_mcp/config/generated/example1.${CONFIG_VARIANT}.env"
echo "example2 VOICE_AGENT_MCP_CONFIG=../../shared_mcp/config/generated/example2.${CONFIG_VARIANT}.env"
echo "example3 VOICE_AGENT_MCP_CONFIG=../../shared_mcp/config/generated/example3.${CONFIG_VARIANT}.env"
