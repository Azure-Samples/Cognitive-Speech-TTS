#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SAMPLES_ROOT="$(cd "${ROOT}/../samples" && pwd)"
HANDOFF_SAMPLE="${SAMPLES_ROOT}/example1_finance_with_handoff"
OTP_SAMPLE="${SAMPLES_ROOT}/example2_finance_with_OTP_and_Officer_Search"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_ROOT="${ROOT}/state/e2e/${RUN_ID}"
LOCAL_STATE_ROOT="${ROOT}/state/local"
PORT="${SHARED_MCP_E2E_PORT:-18003}"
CONTAINER_NAME="voice-agent-shared-mcp-local"
HANDOFF_CONNECTION="${HANDOFF_E2E_CONNECTION:-finance-handoff-local-e2e}"
OTP_CONNECTION="${OTP_E2E_CONNECTION:-finance-otp-officer-local-e2e}"
KEEP_RUNNING="${SHARED_MCP_E2E_KEEP_RUNNING:-1}"
GENERATED_CONFIG_DIR="${ROOT}/config/generated"
HANDOFF_CONFIG="${GENERATED_CONFIG_DIR}/example1.local.env"
OTP_CONFIG="${GENERATED_CONFIG_DIR}/example2.local.env"
TOKEN_FILE="${LOCAL_STATE_ROOT}/token"
TUNNEL_ID_FILE="${LOCAL_STATE_ROOT}/devtunnel-id"
TUNNEL_PID=""

die() {
  echo "ERROR: $*" >&2
  exit 1
}

cleanup() {
  if [[ -n "${TUNNEL_PID}" ]] && kill -0 "${TUNNEL_PID}" >/dev/null 2>&1; then
    kill "${TUNNEL_PID}"
    wait "${TUNNEL_PID}" 2>/dev/null || true
  fi
  docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

for command_name in az curl devtunnel docker openssl python3; do
  command -v "${command_name}" >/dev/null 2>&1 ||
    die "${command_name} is required"
done

mkdir -p "${RUN_ROOT}" "${LOCAL_STATE_ROOT}"
umask 077
if [[ ! -s "${TOKEN_FILE}" ]]; then
  openssl rand -hex 32 > "${TOKEN_FILE}"
fi
TOKEN="$(<"${TOKEN_FILE}")"

TUNNEL_ID="${SHARED_MCP_TUNNEL_ID:-}"
if [[ -z "${TUNNEL_ID}" && -s "${TUNNEL_ID_FILE}" ]]; then
  TUNNEL_ID="$(<"${TUNNEL_ID_FILE}")"
fi
if [[ -z "${TUNNEL_ID}" ]]; then
  USER_PART="$(
    printf '%s' "${USER:-local}" |
      tr '[:upper:]_' '[:lower:]-' |
      tr -cd 'a-z0-9-' |
      cut -c1-24
  )"
  TUNNEL_ID="voice-agent-mcp-${USER_PART:-local}-$(openssl rand -hex 2)"
fi
[[ "${TUNNEL_ID}" =~ ^[a-z0-9][a-z0-9-]{2,59}$ ]] ||
  die "SHARED_MCP_TUNNEL_ID must be a 3-60 character lowercase DNS label"
printf '%s\n' "${TUNNEL_ID}" > "${TUNNEL_ID_FILE}"

if ! devtunnel show "${TUNNEL_ID}" --json >/dev/null 2>&1; then
  devtunnel create "${TUNNEL_ID}" \
    --allow-anonymous \
    --expiration 30d \
    --description "Voice Agent shared local MCP" >/dev/null
fi
if ! devtunnel port show "${TUNNEL_ID}" -p "${PORT}" --json >/dev/null 2>&1; then
  devtunnel port create "${TUNNEL_ID}" \
    -p "${PORT}" \
    --protocol http >/dev/null
fi

PROJECT_ENDPOINT="${AZURE_AI_PROJECT_ENDPOINT:-}"
if [[ -z "${PROJECT_ENDPOINT}" ]]; then
  PROJECT_ENDPOINT="$(
  SAMPLE_DIR="${HANDOFF_SAMPLE}" python3 - <<'PY'
import os
from pathlib import Path

path = Path(os.environ["SAMPLE_DIR"]) / ".env"
if path.is_file():
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if separator and key.strip() == "AZURE_AI_PROJECT_ENDPOINT":
            print(value.strip().strip("\"'"))
            break
PY
  )"
fi
[[ "${PROJECT_ENDPOINT}" =~ ^https://[^[:space:]]+/api/projects/[^/[:space:]]+$ ]] ||
  die "set AZURE_AI_PROJECT_ENDPOINT or configure it in the example1 .env file"

"${ROOT}/scripts/package.sh"

docker run --rm -d \
  --name "${CONTAINER_NAME}" \
  -p "${PORT}:8000" \
  -v voice-agent-shared-mcp-state:/app/state \
  -e SHARED_MCP_TOKEN="${TOKEN}" \
  voice-agent-shared-mcp:local >/dev/null

for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${PORT}/healthz" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
curl -fsS "http://127.0.0.1:${PORT}/healthz" >/dev/null

devtunnel host \
  "${TUNNEL_ID}" \
  --allow-anonymous \
  >"${RUN_ROOT}/devtunnel.log" 2>&1 &
TUNNEL_PID=$!

BASE_URL=""
for _ in $(seq 1 60); do
  BASE_URL="$(
    grep -Eo "https://[a-z0-9-]+-${PORT}\\.[a-z0-9.-]+\\.devtunnels\\.ms" \
      "${RUN_ROOT}/devtunnel.log" |
      head -n 1 || true
  )"
  if [[ -n "${BASE_URL}" ]]; then
    break
  fi
  if ! kill -0 "${TUNNEL_PID}" >/dev/null 2>&1; then
    die "dev tunnel exited before publishing a URL; see ${RUN_ROOT}/devtunnel.log"
  fi
  sleep 1
done
[[ -n "${BASE_URL}" ]] || die "timed out waiting for the dev tunnel URL"
printf '%s\n' "${BASE_URL}" > "${RUN_ROOT}/base-url"

for _ in $(seq 1 30); do
  if curl -fsS "${BASE_URL}/healthz" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
curl -fsS "${BASE_URL}/healthz" >/dev/null
STATUS="$(
  curl -sS -o /dev/null -w '%{http_code}' \
    "${BASE_URL}/mcp/finance-handoff"
)"
[[ "${STATUS}" == "401" ]] ||
  die "public MCP route returned HTTP ${STATUS}, expected 401"

SHARED_MCP_TOKEN="${TOKEN}" PYTHONPATH="${ROOT}/app" \
  python3 -m shared_mcp.probe \
    --url "${BASE_URL}/mcp/finance-handoff" \
    --agent-json "${HANDOFF_SAMPLE}/agent.json"
SHARED_MCP_TOKEN="${TOKEN}" PYTHONPATH="${ROOT}/app" \
  python3 -m shared_mcp.probe \
    --url "${BASE_URL}/mcp/finance-otp-officer" \
    --agent-json "${OTP_SAMPLE}/agent.json"

AZURE_AI_PROJECT_ENDPOINT="${PROJECT_ENDPOINT}" \
SHARED_MCP_TOKEN="${TOKEN}" \
SHARED_MCP_FINANCE_HANDOFF_URL="${BASE_URL}/mcp/finance-handoff" \
SHARED_MCP_FINANCE_OTP_OFFICER_URL="${BASE_URL}/mcp/finance-otp-officer" \
FINANCE_HANDOFF_MCP_CONNECTION_ID="${HANDOFF_CONNECTION}" \
FINANCE_OTP_MCP_CONNECTION_ID="${OTP_CONNECTION}" \
MCP_CONFIG_VARIANT=local \
  "${ROOT}/scripts/configure-agent.sh"

echo "e2e_local=passed artifacts=${RUN_ROOT}"
echo "fixed_tunnel_id=${TUNNEL_ID}"
echo "example1_config=${HANDOFF_CONFIG}"
echo "example2_config=${OTP_CONFIG}"
if [[ "${KEEP_RUNNING}" == "1" ]]; then
  echo "local_runtime=ready base_url=${BASE_URL}"
  echo "Press Ctrl+C to stop the local MCP container and dev tunnel."
  wait "${TUNNEL_PID}"
fi
