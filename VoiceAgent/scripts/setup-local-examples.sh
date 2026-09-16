#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SAMPLES_ROOT="${ROOT}/samples"
HANDOFF_ROOT="${SAMPLES_ROOT}/example1_finance_with_handoff"
OTP_ROOT="${SAMPLES_ROOT}/example2_finance_with_OTP_and_Officer_Search"
UI_ROOT="${SAMPLES_ROOT}/local_UI"
UI_WEB_ROOT="${UI_ROOT}/web"
PIP_INDEX_URL="${PIP_INDEX_URL:-https://pypi.org/simple}"
PROJECT_ENDPOINT="${AZURE_AI_PROJECT_ENDPOINT:-}"
CHECK_ONLY=0

usage() {
  cat <<'EOF'
Usage: ./scripts/setup-local-examples.sh [options]

Prepare the configured Voice Agent sample CLIs and Local UI on one development
machine: check required tools, install dependencies, build the browser bundle,
and create or update local .env files.

Options:
  --project-endpoint URL  Write the Foundry Project endpoint to new local .env files.
  --pip-index-url URL     Python package index for venv and Docker builds.
  --check                 Check prerequisites and local files without installing.
  -h, --help              Show this help.

Environment equivalents:
  AZURE_AI_PROJECT_ENDPOINT
  PIP_INDEX_URL
EOF
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-endpoint)
      [[ $# -ge 2 ]] || die "--project-endpoint requires a URL"
      PROJECT_ENDPOINT="$2"
      shift 2
      ;;
    --pip-index-url)
      [[ $# -ge 2 ]] || die "--pip-index-url requires a URL"
      PIP_INDEX_URL="$2"
      shift 2
      ;;
    --check)
      CHECK_ONLY=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown option: $1"
      ;;
  esac
done

[[ "${PIP_INDEX_URL}" == https://* ]] ||
  die "PIP_INDEX_URL must be an HTTPS URL"
if [[ -n "${PROJECT_ENDPOINT}" ]]; then
  [[ "${PROJECT_ENDPOINT}" =~ ^https://[^[:space:]]+\.services\.ai\.azure\.com/api/projects/[^/[:space:]]+$ ]] ||
    die "project endpoint must match https://<account>.services.ai.azure.com/api/projects/<project>"
fi

require_command() {
  local command_name="$1"
  local guidance="$2"
  command -v "${command_name}" >/dev/null 2>&1 ||
    die "${command_name} is required. ${guidance}"
}

check_base_tools() {
  require_command git "Install Git and rerun setup."
  require_command python3 "Install Python 3.10 or later and rerun setup."
  require_command curl "Install curl and rerun setup."
  require_command openssl "Install OpenSSL and rerun setup."
  require_command node "Install Node.js and rerun setup."
  require_command npm "Install npm and rerun setup."
  require_command docker "Install Docker Desktop or Docker Engine and rerun setup."
  require_command az "Install Azure CLI and rerun setup."

  python3 - <<'PY'
import sys

if sys.version_info < (3, 10):
    raise SystemExit("ERROR: Python 3.10 or later is required")
print(f"python={sys.version.split()[0]}")
PY
  echo "node=$(node --version)"
  echo "npm=$(npm --version)"
  echo "docker=$(docker --version)"
  echo "azure_cli=$(az version --query '"'"'azure-cli'"'"' --output tsv)"
}

ensure_devtunnel() {
  if ! command -v devtunnel >/dev/null 2>&1 && [[ -x "${HOME}/bin/devtunnel" ]]; then
    export PATH="${HOME}/bin:${PATH}"
  fi
  if command -v devtunnel >/dev/null 2>&1; then
    echo "devtunnel=$(devtunnel --version)"
    return 0
  fi
  [[ "${CHECK_ONLY}" == "0" ]] ||
    die "devtunnel is missing. Run setup without --check to install it."

  local installer
  installer="$(mktemp)"
  curl -L https://aka.ms/DevTunnelCliInstall -o "${installer}"
  bash "${installer}"
  rm -f "${installer}"

  if ! command -v devtunnel >/dev/null 2>&1 && [[ -x "${HOME}/bin/devtunnel" ]]; then
    export PATH="${HOME}/bin:${PATH}"
  fi
  command -v devtunnel >/dev/null 2>&1 ||
    die "Dev Tunnel installed but is not on PATH. Add the directory reported by the installer and rerun setup."
  echo "devtunnel=$(devtunnel --version)"
}

ensure_env_file() {
  local directory="$1"
  local env_file="${directory}/.env"
  local example_file="${directory}/.env.example"
  local ui_port="$2"
  local mcp_config="${3:-}"

  if [[ ! -f "${env_file}" ]]; then
    cp "${example_file}" "${env_file}"
    chmod 600 "${env_file}"
    echo "created=${env_file}"
  else
    echo "reused=${env_file}"
  fi

  ENV_FILE="${env_file}" \
  PROJECT_ENDPOINT="${PROJECT_ENDPOINT}" \
  UI_PORT="${ui_port}" \
  MCP_CONFIG="${mcp_config}" \
    python3 - <<'PY'
import os
from pathlib import Path

path = Path(os.environ["ENV_FILE"])
lines = path.read_text(encoding="utf-8").splitlines()
values = {}
remove = set()
if os.environ["PROJECT_ENDPOINT"]:
    values["AZURE_AI_PROJECT_ENDPOINT"] = os.environ["PROJECT_ENDPOINT"]
    values["AZURE_CREDENTIAL_MODE"] = "cli"
if os.environ["UI_PORT"]:
    values["LOCAL_UI_PORT"] = os.environ["UI_PORT"]
if os.environ["MCP_CONFIG"]:
    values["VOICE_AGENT_MCP_CONFIG"] = os.environ["MCP_CONFIG"]
    remove.update(
        {
            "VOICE_AGENT_MCP_SERVER_URL",
            "VOICE_AGENT_MCP_CONNECTION_ID",
            "VOICE_AGENT_MODEL_TYPE",
        }
    )

seen = set()
updated = []
for line in lines:
    key, separator, _ = line.partition("=")
    if separator and key in remove:
        continue
    if separator and key in values:
        updated.append(f"{key}={values[key]}")
        seen.add(key)
    else:
        updated.append(line)
for key, value in values.items():
    if key not in seen:
        updated.append(f"{key}={value}")
path.write_text("\n".join(updated) + "\n", encoding="utf-8")
PY
}

install_python_environment() {
  local directory="$1"
  local label="$2"
  local python="${directory}/.venv/bin/python"

  if [[ ! -x "${python}" ]]; then
    python3 -m venv "${directory}/.venv" ||
      die "could not create ${label} venv; install the Python venv package for this interpreter"
  fi
  "${python}" -m pip install \
    --index-url "${PIP_INDEX_URL}" \
    -r "${directory}/requirements.txt"
  echo "python_environment=${label} ready"
}

check_env_file() {
  local env_file="$1"
  if [[ ! -s "${env_file}" ]]; then
    echo "ACTION_REQUIRED: create ${env_file}" >&2
    return 1
  fi
  if ! ENV_FILE="${env_file}" python3 - <<'PY'
import os
from pathlib import Path

path = Path(os.environ["ENV_FILE"])
endpoint = ""
for raw_line in path.read_text(encoding="utf-8").splitlines():
    key, separator, value = raw_line.partition("=")
    if separator and key.strip() == "AZURE_AI_PROJECT_ENDPOINT":
        endpoint = value.strip()
        break
if not endpoint or "<account>" in endpoint or "<project>" in endpoint:
    raise SystemExit(1)
PY
  then
    echo "ACTION_REQUIRED: set AZURE_AI_PROJECT_ENDPOINT in ${env_file}" >&2
    return 1
  fi
  return 0
}

check_python_environment() {
  local python="$1"
  local label="$2"
  shift 2
  [[ -x "${python}" ]] || {
    echo "ACTION_REQUIRED: install the ${label} virtual environment" >&2
    return 1
  }
  "${python}" -c "$*" || {
    echo "ACTION_REQUIRED: reinstall the ${label} requirements" >&2
    return 1
  }
  echo "python_environment=${label} ready"
}

check_installed_environments() {
  local failed=0
  check_python_environment \
    "${HANDOFF_ROOT}/.venv/bin/python" \
    "finance-handoff" \
    "import azure.ai.projects, azure.identity, dotenv, websockets" || failed=1
  check_python_environment \
    "${OTP_ROOT}/.venv/bin/python" \
    "finance-otp-officer" \
    "import azure.ai.projects, azure.identity, dotenv, websockets" || failed=1
  check_python_environment \
    "${UI_ROOT}/.venv/bin/python" \
    "local-ui" \
    "import aiohttp, azure.ai.projects, azure.identity, dotenv, requests, websockets" || failed=1
  if [[ ! -d "${UI_WEB_ROOT}/node_modules" ]]; then
    echo "ACTION_REQUIRED: run npm ci in ${UI_WEB_ROOT}" >&2
    failed=1
  else
    echo "node_environment=local-ui ready"
  fi
  if [[ ! -s "${UI_ROOT}/static/dashboard-bundle.js" ]]; then
    echo "ACTION_REQUIRED: build the Local UI browser bundle" >&2
    failed=1
  else
    echo "browser_bundle=ready"
  fi
  return "${failed}"
}

check_authentication() {
  local failed=0
  if az account show --output none >/dev/null 2>&1; then
    echo "azure_cli_auth=ready"
  else
    echo "ACTION_REQUIRED: run az login and select the intended subscription" >&2
    failed=1
  fi
  if devtunnel user show >/dev/null 2>&1; then
    echo "devtunnel_auth=ready"
  else
    echo "ACTION_REQUIRED: run devtunnel user login" >&2
    echo "If Entra Conditional Access rejects it, run:" >&2
    echo "  devtunnel user login --github --use-device-code-auth" >&2
    failed=1
  fi
  return "${failed}"
}

check_base_tools
ensure_devtunnel

if [[ "${CHECK_ONLY}" == "0" ]]; then
  install_python_environment "${HANDOFF_ROOT}" "finance-handoff"
  install_python_environment "${OTP_ROOT}" "finance-otp-officer"
  install_python_environment "${UI_ROOT}" "local-ui"

  npm --prefix "${UI_WEB_ROOT}" ci
  npm --prefix "${UI_WEB_ROOT}" test
  npm --prefix "${UI_WEB_ROOT}" run build

  ensure_env_file \
    "${HANDOFF_ROOT}" \
    "" \
    "../../shared_mcp/config/generated/example1.local.env"
  ensure_env_file \
    "${OTP_ROOT}" \
    "" \
    "../../shared_mcp/config/generated/example2.local.env"
  ensure_env_file "${UI_ROOT}" "18098"
fi

missing_config=0
check_installed_environments || missing_config=1
check_env_file "${HANDOFF_ROOT}/.env" || missing_config=1
check_env_file "${OTP_ROOT}/.env" || missing_config=1
check_env_file "${UI_ROOT}/.env" || missing_config=1
check_authentication || missing_config=1

docker info >/dev/null ||
  die "Docker is installed but its daemon is unavailable"

if [[ "${missing_config}" == "0" ]]; then
  echo "local_setup=ready"
  echo "next=${ROOT}/scripts/manage-local-mcp-and-ui.sh restart"
else
  echo "local_setup=installed configuration=required"
  echo "rerun with: ./scripts/setup-local-examples.sh --project-endpoint https://<account>.services.ai.azure.com/api/projects/<project>"
  exit 1
fi
