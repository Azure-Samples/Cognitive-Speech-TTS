#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

die() {
  echo "ERROR: $*" >&2
  exit 1
}

for command_name in azd openssl curl python3; do
  command -v "${command_name}" >/dev/null 2>&1 ||
    die "${command_name} is required"
done

[[ -n "${AZURE_AI_PROJECT_ENDPOINT:-}" ]] ||
  die "set AZURE_AI_PROJECT_ENDPOINT before running this command"

cd "${ROOT}"
CURRENT_ENVIRONMENT="$(
  azd env get-value AZURE_ENV_NAME 2>/dev/null || true
)"
ENVIRONMENT_NAME="${
  AZURE_ENV_NAME:-${
    CURRENT_ENVIRONMENT:-voice-agent-shared-mcp-$(openssl rand -hex 2)
  }
}"
if ! azd env select "${ENVIRONMENT_NAME}" >/dev/null 2>&1; then
  azd env new "${ENVIRONMENT_NAME}" --no-prompt
fi

TOKEN="$(azd env get-value SHARED_MCP_TOKEN 2>/dev/null || true)"
if [[ -z "${TOKEN}" ]]; then
  TOKEN="$(openssl rand -hex 32)"
  azd env set SHARED_MCP_TOKEN "${TOKEN}"
fi

azd up

BASE_URL="$(azd env get-value SHARED_MCP_BASE_URL)"
for route in finance-handoff finance-otp-officer; do
  STATUS="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 \
    "${BASE_URL}/mcp/${route}" || true)"
  [[ "${STATUS}" == "401" ]] ||
    die "deployed MCP ${route} authentication check returned HTTP ${STATUS}, expected 401"
done

SHARED_MCP_TOKEN="${TOKEN}" PYTHONPATH="${ROOT}/app" \
  python3 -m shared_mcp.probe \
    --url "${BASE_URL}/mcp/finance-handoff" \
    --agent-json "${ROOT}/../samples/example1_finance_with_handoff/agent.json"
SHARED_MCP_TOKEN="${TOKEN}" PYTHONPATH="${ROOT}/app" \
  python3 -m shared_mcp.probe \
    --url "${BASE_URL}/mcp/finance-otp-officer" \
    --agent-json \
      "${ROOT}/../samples/example2_finance_with_OTP_and_Officer_Search/agent.json"

"${ROOT}/scripts/configure-agent.sh"

echo "deploy_complete base_url=${BASE_URL}"
