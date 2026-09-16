#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MCP_ROOT="${ROOT}/shared_mcp"
UI_ROOT="${ROOT}/samples/local_UI"
STATE_ROOT="${ROOT}/.local-mcp-and-ui"
MCP_PID_FILE="${STATE_ROOT}/mcp.pid"
UI_PID_FILE="${STATE_ROOT}/local-ui.pid"
MCP_LOG="${STATE_ROOT}/mcp.log"
UI_LOG="${STATE_ROOT}/local-ui.log"
MCP_PORT="${SHARED_MCP_E2E_PORT:-18003}"
UI_HOST="${LOCAL_UI_HOST:-127.0.0.1}"
UI_PORT="${LOCAL_UI_PORT:-18098}"
PIP_INDEX_URL="${PIP_INDEX_URL:-https://pypi.org/simple}"
UI_PYTHON="${LOCAL_UI_PYTHON:-${UI_ROOT}/.venv/bin/python}"
ACTION="${1:-restart}"

usage() {
  cat <<'EOF'
Usage: ./scripts/manage-local-mcp-and-ui.sh [action]

Manage the complete local runtime for the configured Voice Agent examples: the
shared MCP container, named Dev Tunnel host, and Local UI.

Actions:
  start, restart  Replace stale repository-owned processes and start MCP + UI.
  status          Report MCP and Local UI readiness and the Local UI URL.
  stop            Stop repository-owned MCP, tunnel, UI, and local container.
  -h, --help      Show this help.
EOF
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

process_group() {
  ps -o pgid= -p "$1" 2>/dev/null | tr -d ' '
}

stop_group() {
  local group_id="$1"
  [[ "${group_id}" =~ ^[0-9]+$ ]] || return 0
  kill -TERM -- "-${group_id}" 2>/dev/null || true
  for _ in $(seq 1 40); do
    kill -0 -- "-${group_id}" 2>/dev/null || return 0
    sleep 0.25
  done
  kill -KILL -- "-${group_id}" 2>/dev/null || true
}

stop_pid_file() {
  local pid_file="$1"
  local pid=""
  local group_id=""
  if [[ -s "${pid_file}" ]]; then
    pid="$(<"${pid_file}")"
    if [[ "${pid}" =~ ^[0-9]+$ ]] && kill -0 "${pid}" 2>/dev/null; then
      group_id="$(process_group "${pid}")"
      stop_group "${group_id}"
    fi
  fi
  rm -f "${pid_file}"
}

stop_stale_repo_processes() {
  local proc=""
  local pid=""
  local cwd=""
  local command_line=""
  local group_id=""
  local groups=" "

  for proc in /proc/[0-9]*; do
    pid="${proc##*/}"
    cwd="$(readlink "${proc}/cwd" 2>/dev/null || true)"
    command_line="$(tr '\0' ' ' < "${proc}/cmdline" 2>/dev/null || true)"
    if {
      [[ "${cwd}" == "${UI_ROOT}" && "${command_line}" == *"app.py"* ]]
    } || {
      [[ "${cwd}" == "${MCP_ROOT}" && "${command_line}" == *"e2e-local.sh"* ]]
    }; then
      group_id="$(process_group "${pid}")"
      if [[ -n "${group_id}" && "${groups}" != *" ${group_id} "* ]]; then
        groups+="${group_id} "
      fi
    fi
  done

  for group_id in ${groups}; do
    stop_group "${group_id}"
  done
}

stop_stack() {
  mkdir -p "${STATE_ROOT}"
  stop_pid_file "${UI_PID_FILE}"
  stop_pid_file "${MCP_PID_FILE}"
  stop_stale_repo_processes
  docker rm -f voice-agent-shared-mcp-local >/dev/null 2>&1 || true
  echo "local_mcp_and_ui=stopped"
}

wait_for_http() {
  local name="$1"
  local url="$2"
  local pid="$3"
  local log_file="$4"
  for _ in $(seq 1 120); do
    kill -0 "${pid}" 2>/dev/null ||
      die "${name} exited before becoming ready; see ${log_file}"
    if curl -fsS "${url}" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  die "timed out waiting for ${name}; see ${log_file}"
}

wait_for_mcp_config() {
  local pid="$1"
  for _ in $(seq 1 120); do
    kill -0 "${pid}" 2>/dev/null ||
      die "MCP E2E exited before writing config; see ${MCP_LOG}"
    if [[ -s "${MCP_ROOT}/config/generated/example1.local.env" \
      && -s "${MCP_ROOT}/config/generated/example2.local.env" \
      && -s "${MCP_ROOT}/state/local/token" ]]; then
      return 0
    fi
    sleep 1
  done
  die "timed out waiting for MCP config; see ${MCP_LOG}"
}

verify_template_probes() {
  "${UI_PYTHON}" - "http://${UI_HOST}:${UI_PORT}" <<'PY'
import json
import sys
import urllib.request

base_url = sys.argv[1]
with urllib.request.urlopen(f"{base_url}/api/templates?reload=1", timeout=30) as response:
    catalog = json.load(response)
if len(catalog.get("templates") or []) != 2:
    raise SystemExit(f"template catalog is not ready: {catalog}")

for template_id in (
    "finance-example",
    "finance-with-otp-and-officer-search",
):
    with urllib.request.urlopen(
        f"{base_url}/api/templates/{template_id}/mcp/probe",
        timeout=60,
    ) as response:
        result = json.load(response)
    if not result.get("ok"):
        raise SystemExit(f"MCP probe failed for {template_id}: {result}")
    print(
        f"template={template_id} mcp=ready "
        f"http_status={result.get('http_status')} tools={len(result.get('tools') or [])}"
    )
PY
}

start_stack() {
  command -v docker >/dev/null 2>&1 || die "docker is required"
  command -v curl >/dev/null 2>&1 || die "curl is required"
  command -v setsid >/dev/null 2>&1 || die "setsid is required"
  [[ -x "${UI_PYTHON}" ]] ||
    die "Local UI environment is missing; create ${UI_ROOT}/.venv first"
  if ! command -v devtunnel >/dev/null 2>&1 && [[ -x "${HOME}/bin/devtunnel" ]]; then
    export PATH="${HOME}/bin:${PATH}"
  fi
  command -v devtunnel >/dev/null 2>&1 || die "devtunnel is required"

  mkdir -p "${STATE_ROOT}"
  rm -f \
    "${MCP_ROOT}/config/generated/example1.local.env" \
    "${MCP_ROOT}/config/generated/example2.local.env"

  setsid env \
    PATH="${PATH}" \
    PIP_INDEX_URL="${PIP_INDEX_URL}" \
    SHARED_MCP_E2E_PORT="${MCP_PORT}" \
    "${MCP_ROOT}/scripts/e2e-local.sh" \
    >"${MCP_LOG}" 2>&1 < /dev/null &
  local mcp_pid=$!
  printf '%s\n' "${mcp_pid}" > "${MCP_PID_FILE}"

  wait_for_http "MCP" "http://127.0.0.1:${MCP_PORT}/healthz" "${mcp_pid}" "${MCP_LOG}"
  wait_for_mcp_config "${mcp_pid}"

  setsid env \
    LOCAL_UI_HOST="${UI_HOST}" \
    LOCAL_UI_PORT="${UI_PORT}" \
    "${UI_PYTHON}" "${UI_ROOT}/app.py" \
    --host "${UI_HOST}" \
    --port "${UI_PORT}" \
    >"${UI_LOG}" 2>&1 < /dev/null &
  local ui_pid=$!
  printf '%s\n' "${ui_pid}" > "${UI_PID_FILE}"

  wait_for_http \
    "Local UI" \
    "http://${UI_HOST}:${UI_PORT}/healthz" \
    "${ui_pid}" \
    "${UI_LOG}"
  verify_template_probes

  echo "local_mcp_and_ui=ready"
  echo "local_ui_url=http://localhost:${UI_PORT}"
  echo "mcp_health=http://127.0.0.1:${MCP_PORT}/healthz"
  echo "mcp_log=${MCP_LOG}"
  echo "local_ui_log=${UI_LOG}"
}

status_stack() {
  local mcp_status="stopped"
  local ui_status="stopped"
  curl -fsS "http://127.0.0.1:${MCP_PORT}/healthz" >/dev/null 2>&1 &&
    mcp_status="ready"
  curl -fsS "http://${UI_HOST}:${UI_PORT}/healthz" >/dev/null 2>&1 &&
    ui_status="ready"
  echo "mcp=${mcp_status} local_ui=${ui_status} local_ui_url=http://localhost:${UI_PORT}"
}

case "${ACTION}" in
  restart|start)
    stop_stack
    start_stack
    ;;
  stop)
    stop_stack
    ;;
  status)
    status_stack
    ;;
  -h|--help)
    usage
    ;;
  *)
    usage >&2
    exit 1
    ;;
esac