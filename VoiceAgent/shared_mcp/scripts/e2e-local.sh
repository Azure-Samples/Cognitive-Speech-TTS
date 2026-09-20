#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SAMPLES_ROOT="$(cd "${ROOT}/../samples" && pwd)"
HANDOFF_SAMPLE="${SAMPLES_ROOT}/example1_finance_with_handoff"
OTP_SAMPLE="${SAMPLES_ROOT}/example2_finance_with_OTP_and_Officer_Search"
ELEVATOR_SAMPLE="${SAMPLES_ROOT}/example3_elevator_service_with_safety_zendesk_and_handoff"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_ROOT="${ROOT}/state/e2e/${RUN_ID}"
LOCAL_STATE_ROOT="${ROOT}/state/local"
PORT="${SHARED_MCP_E2E_PORT:-18003}"
NATIVE_PYTHON="${SHARED_MCP_PYTHON:-${ROOT}/.venv/bin/python}"
NATIVE_PID=""
HANDOFF_CONNECTION="${HANDOFF_E2E_CONNECTION:-finance-handoff-local-e2e}"
OTP_CONNECTION="${OTP_E2E_CONNECTION:-finance-otp-officer-local-e2e}"
ELEVATOR_CONNECTION="${ELEVATOR_E2E_CONNECTION:-elevator-service-local-e2e}"
KEEP_RUNNING="${SHARED_MCP_E2E_KEEP_RUNNING:-1}"
GENERATED_CONFIG_DIR="${ROOT}/config/generated"
HANDOFF_CONFIG="${GENERATED_CONFIG_DIR}/example1.local.env"
OTP_CONFIG="${GENERATED_CONFIG_DIR}/example2.local.env"
ELEVATOR_CONFIG="${GENERATED_CONFIG_DIR}/example3.local.env"
TOKEN_FILE="${LOCAL_STATE_ROOT}/token"
TUNNEL_ID_FILE="${LOCAL_STATE_ROOT}/devtunnel-id"
TUNNEL_PID=""

die() {
  echo "ERROR: $*" >&2
  exit 1
}

devtunnel_cli() {
  (
    cd "${ROOT}"
    devtunnel "$@"
  )
}

cleanup() {
  if [[ -n "${TUNNEL_PID}" ]] && kill -0 "${TUNNEL_PID}" >/dev/null 2>&1; then
    kill "${TUNNEL_PID}"
    wait "${TUNNEL_PID}" 2>/dev/null || true
  fi
  if [[ -n "${NATIVE_PID}" ]] && kill -0 "${NATIVE_PID}" >/dev/null 2>&1; then
    kill "${NATIVE_PID}"
    wait "${NATIVE_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

for command_name in az curl devtunnel openssl python3; do
  command -v "${command_name}" >/dev/null 2>&1 ||
    die "${command_name} is required"
done
[[ -x "${NATIVE_PYTHON}" ]] ||
  die "native MCP environment is missing; run ${ROOT}/../scripts/setup-local-examples.sh"

DEVTUNNEL_USER_JSON="$(devtunnel_cli user show --json 2>/dev/null || true)"
if ! DEVTUNNEL_USER_JSON="${DEVTUNNEL_USER_JSON}" python3 - <<'PY'
import json
import os

try:
    user = json.loads(os.environ["DEVTUNNEL_USER_JSON"])
except (json.JSONDecodeError, TypeError):
    raise SystemExit(1)
raise SystemExit(0 if user.get("status") == "Logged in" else 1)
PY
then
  die "Dev Tunnel is not authenticated for ${ROOT}. Run 'cd ${ROOT} && devtunnel user login --entra --use-device-code-auth' or use --github, then retry."
fi

mkdir -p "${RUN_ROOT}" "${LOCAL_STATE_ROOT}"
umask 077
if [[ ! -s "${TOKEN_FILE}" ]]; then
  openssl rand -hex 32 > "${TOKEN_FILE}"
fi
TOKEN="$(<"${TOKEN_FILE}")"

TUNNEL_ID="${SHARED_MCP_TUNNEL_ID:-}"
TUNNEL_ID_SOURCE="explicit"
if [[ -z "${TUNNEL_ID}" ]]; then
  [[ -s "${TUNNEL_ID_FILE}" ]] ||
    die "Dev Tunnel ID is not initialized. Run ${ROOT}/../scripts/setup-local-examples.sh once, then retry."
  TUNNEL_ID="$(<"${TUNNEL_ID_FILE}")"
  TUNNEL_ID_SOURCE="setup"
fi
[[ "${TUNNEL_ID}" =~ ^[a-z0-9][a-z0-9-]{2,59}$ ]] ||
  die "SHARED_MCP_TUNNEL_ID must be a 3-60 character lowercase DNS label"

if ! devtunnel_cli show "${TUNNEL_ID}" --json >/dev/null 2>&1; then
  CREATE_OUTPUT=""
  if ! CREATE_OUTPUT="$(
    devtunnel_cli create "${TUNNEL_ID}" \
      --allow-anonymous \
      --expiration 30d \
      --description "Voice Agent shared local MCP" 2>&1
  )"; then
    printf '%s\n' "${CREATE_OUTPUT}" >&2
    if grep -Eqi 'conflict with existing entity|already exists' <<<"${CREATE_OUTPUT}"; then
      if [[ "${TUNNEL_ID_SOURCE}" == "explicit" ]]; then
        die "SHARED_MCP_TUNNEL_ID=${TUNNEL_ID} conflicts with a tunnel unavailable to this identity. Sign in with its owner or choose a different explicit ID."
      fi
      die "The fixed Dev Tunnel ID ${TUNNEL_ID} conflicts with a tunnel unavailable to this identity. Sign in with its owner. To intentionally initialize a different ID for this machine, remove ${TUNNEL_ID_FILE} and rerun setup-local-examples.sh."
    fi
    die "could not inspect or create Dev Tunnel ${TUNNEL_ID}"
  fi
fi

if ! devtunnel_cli port show "${TUNNEL_ID}" -p "${PORT}" --json >/dev/null 2>&1; then
  devtunnel_cli port create "${TUNNEL_ID}" \
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

NATIVE_STATE_ROOT="${LOCAL_STATE_ROOT}/runtime"
mkdir -p \
  "${NATIVE_STATE_ROOT}/finance-handoff" \
  "${NATIVE_STATE_ROOT}/finance-otp-officer" \
  "${NATIVE_STATE_ROOT}/elevator-service" \
  "${NATIVE_STATE_ROOT}/auth"
PYTHONPATH="${ROOT}/app" \
  "${NATIVE_PYTHON}" -m unittest discover -s "${ROOT}/tests" -v
env \
  PYTHONPATH="${ROOT}/app" \
  SHARED_MCP_TOKEN="${TOKEN}" \
  SHARED_MCP_HOST="127.0.0.1" \
  SHARED_MCP_PORT="${PORT}" \
  FINANCE_MCP_DATA_DIR="${ROOT}/data/finance_handoff" \
  FINANCE_OFFICER_DATA_DIR="${ROOT}/data/finance_otp_officer" \
  FINANCE_OTP_MCP_DATA_DIR="${ROOT}/data/finance_otp_officer" \
  ELEVATOR_MCP_DATA_DIR="${ROOT}/data/elevator_service" \
  FINANCE_MCP_STATE_DIR="${NATIVE_STATE_ROOT}/finance-handoff" \
  FINANCE_OTP_MCP_STATE_DIR="${NATIVE_STATE_ROOT}/finance-otp-officer" \
  FINANCE_OTP_MCP_AUTH_DIR="${NATIVE_STATE_ROOT}/auth" \
  ELEVATOR_MCP_STATE_DIR="${NATIVE_STATE_ROOT}/elevator-service" \
  "${NATIVE_PYTHON}" -m shared_mcp.server \
  >"${RUN_ROOT}/native-mcp.log" 2>&1 &
NATIVE_PID=$!

for _ in $(seq 1 30); do
  if ! kill -0 "${NATIVE_PID}" >/dev/null 2>&1; then
    die "native MCP exited before becoming ready; see ${RUN_ROOT}/native-mcp.log"
  fi
  if curl -fsS "http://127.0.0.1:${PORT}/healthz" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
curl -fsS "http://127.0.0.1:${PORT}/healthz" >/dev/null
if ! kill -0 "${NATIVE_PID}" >/dev/null 2>&1; then
  die "native MCP exited during startup; see ${RUN_ROOT}/native-mcp.log"
fi

(
  cd "${ROOT}"
  exec devtunnel host \
    "${TUNNEL_ID}" \
    --allow-anonymous
) >"${RUN_ROOT}/devtunnel.log" 2>&1 &
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
for route in finance-handoff finance-otp-officer elevator-service; do
  STATUS="$(
    curl -sS -o /dev/null -w '%{http_code}' \
      "${BASE_URL}/mcp/${route}"
  )"
  [[ "${STATUS}" == "401" ]] ||
    die "public MCP route ${route} returned HTTP ${STATUS}, expected 401"
done

SHARED_MCP_TOKEN="${TOKEN}" PYTHONPATH="${ROOT}/app" \
  "${NATIVE_PYTHON}" -m shared_mcp.probe \
    --url "${BASE_URL}/mcp/finance-handoff" \
    --agent-json "${HANDOFF_SAMPLE}/agent.json"
SHARED_MCP_TOKEN="${TOKEN}" PYTHONPATH="${ROOT}/app" \
  "${NATIVE_PYTHON}" -m shared_mcp.probe \
    --url "${BASE_URL}/mcp/finance-otp-officer" \
    --agent-json "${OTP_SAMPLE}/agent.json"
SHARED_MCP_TOKEN="${TOKEN}" PYTHONPATH="${ROOT}/app" \
  "${NATIVE_PYTHON}" -m shared_mcp.probe \
    --url "${BASE_URL}/mcp/elevator-service" \
    --agent-json "${ELEVATOR_SAMPLE}/agent.json"

AZURE_AI_PROJECT_ENDPOINT="${PROJECT_ENDPOINT}" \
SHARED_MCP_TOKEN="${TOKEN}" \
SHARED_MCP_FINANCE_HANDOFF_URL="${BASE_URL}/mcp/finance-handoff" \
SHARED_MCP_FINANCE_OTP_OFFICER_URL="${BASE_URL}/mcp/finance-otp-officer" \
SHARED_MCP_ELEVATOR_SERVICE_URL="${BASE_URL}/mcp/elevator-service" \
FINANCE_HANDOFF_MCP_CONNECTION_ID="${HANDOFF_CONNECTION}" \
FINANCE_OTP_MCP_CONNECTION_ID="${OTP_CONNECTION}" \
ELEVATOR_MCP_CONNECTION_ID="${ELEVATOR_CONNECTION}" \
MCP_CONFIG_VARIANT=local \
  "${ROOT}/scripts/configure-agent.sh"

echo "e2e_local=passed artifacts=${RUN_ROOT}"
echo "mcp_runtime=native"
echo "fixed_tunnel_id=${TUNNEL_ID}"
echo "example1_config=${HANDOFF_CONFIG}"
echo "example2_config=${OTP_CONFIG}"
echo "example3_config=${ELEVATOR_CONFIG}"
if [[ "${KEEP_RUNNING}" == "1" ]]; then
  echo "local_runtime=ready base_url=${BASE_URL}"
  echo "Press Ctrl+C to stop the local MCP runtime and dev tunnel."
  wait -n "${TUNNEL_PID}" "${NATIVE_PID}"
fi
