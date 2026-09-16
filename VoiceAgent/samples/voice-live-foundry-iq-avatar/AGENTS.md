# Coding Agent Instructions — Voice Live Foundry IQ Avatar

This sample is a Microsoft Foundry hosted agent using the `invocations_ws` protocol. Keep it a minimal direct bridge between the browser, public Azure Voice Live, and a Foundry IQ knowledge-base MCP endpoint.

## Deployment mode

- **Direct code deployment:** `azure.yaml` declares the Python runtime and entry point. The Dockerfile is retained as an optional local container path.

## Key files

- `azure.yaml` — hosted-agent manifest and post-provision hooks
- `src/voice-live-foundry-iq-avatar/main.py` — WebSocket and Voice Live bridge
- `src/voice-live-foundry-iq-avatar/provision_kb.py` — knowledge-base provisioner
- `src/voice-live-foundry-iq-avatar/requirements.txt` — fully pinned runtime dependencies
- `src/voice-live-foundry-iq-avatar/requirements-dev.txt` — fully pinned local test dependencies
- `README.md` — supported setup, RBAC, run, deployment, and cleanup guidance

## Dependency workflow

Keep `requirements.txt` and `requirements-dev.txt` fully pinned, including transitive dependencies. Regenerate them from their `.in` files with `pip-tools` using the commands in their headers; do not hand-maintain independent dependency lists. Do not add private package feeds, credentials, or local-path dependencies.

## Scope

Do not add orchestration frameworks, consent-asset management, token watchers, browser automation, or an additional wire protocol. Keep changes inside this sample directory.
