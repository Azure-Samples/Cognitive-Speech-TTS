#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_NAME="${SHARED_MCP_IMAGE:-voice-agent-shared-mcp:local}"
PIP_INDEX_URL="${PIP_INDEX_URL:-https://pypi.org/simple}"

command -v docker >/dev/null 2>&1 || {
  echo "ERROR: docker is required" >&2
  exit 1
}
if ! BUILDX_VERSION="$(docker buildx version 2>&1)"; then
  printf '%s\n' "${BUILDX_VERSION}" >&2
  echo "ERROR: Docker Buildx is required. Install the Buildx CLI plugin and retry." >&2
  exit 1
fi
docker buildx build --help 2>&1 | grep -q -- '--build-context' || {
  echo "ERROR: Docker Buildx does not support --build-context. Upgrade Buildx and retry." >&2
  exit 1
}

docker buildx build --load \
  --build-arg PIP_INDEX_URL="${PIP_INDEX_URL}" \
  --build-context \
    handoff_agent="${ROOT}/../samples/example1_finance_with_handoff" \
  --build-context \
    otp_agent="${ROOT}/../samples/example2_finance_with_OTP_and_Officer_Search" \
  --build-context \
    elevator_agent="${ROOT}/../samples/example3_elevator_service_with_safety_zendesk_and_handoff" \
  --target test \
  -t voice-agent-shared-mcp:test \
  "${ROOT}"
docker buildx build --load \
  --build-arg PIP_INDEX_URL="${PIP_INDEX_URL}" \
  --target runtime \
  -t "${IMAGE_NAME}" \
  "${ROOT}"

echo "package_complete image=${IMAGE_NAME}"
