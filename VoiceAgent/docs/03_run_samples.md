# 03 - Start and run the Finance samples

## Conclusion

This is the executable local setup and validation sequence. Start with the
[architecture and documentation index](./README.md) when choosing a
component or looking for a specific guide.

After completing the one-time prerequisites, run
`VoiceAgent/shared_mcp/scripts/e2e-local.sh` before publishing or opening either Finance
example in the local UI. The command starts the MCP implementation in Docker,
exposes it to Microsoft Foundry through a persistent named Dev Tunnel, creates
the required Foundry connections, generates the shared local config, publishes
both examples, and runs their Voice WebSocket smoke tests.

The complete local path is:

```text
local Docker container
  http://127.0.0.1:18003
       |
       v
persistent named Dev Tunnel
  https://<stable-tunnel>-18003.<region>.devtunnels.ms
       |
       v
two Foundry RemoteTool connections
       |
       v
generated example1.local.env / example2.local.env
       |
       +--> sample.py publish / check / run
       |
       +--> local UI Templates / Try it now
```

Do not put `localhost` in a published Voice Agent. MCP calls are made from
Foundry, not from the local browser or Python client, so the Agent requires a
public HTTPS URL even when the MCP implementation runs on a developer machine.

For component-specific detail, use:

- [MCP implementation, local hosting, and Azure deployment](./02_mcp_settings.md)
- [Local UI startup and configuration](../samples/local_UI/README.md)
- [Example 1: Finance with Handoff](../samples/example1_finance_with_handoff/README.md)
- [Example 2: Finance with OTP and Officer Search](../samples/example2_finance_with_OTP_and_Officer_Search/README.md)
- [Recorded session debugging](./04_debug_session.md)

## Components

| Component | Responsibility |
| --- | --- |
| [`shared_mcp/`](../shared_mcp/) | Customer-owned MCP code, Docker packaging, fixed local runtime, Dev Tunnel, connections, and E2E |
| [`example1_finance_with_handoff/`](../samples/example1_finance_with_handoff/) | Handoff Agent definition and CLI publication/runtime entry point |
| [`example2_finance_with_OTP_and_Officer_Search/`](../samples/example2_finance_with_OTP_and_Officer_Search/) | Flat OTP/officer Agent definition and CLI publication/runtime entry point |
| [`local_UI/`](../samples/local_UI/) | Browser template catalog, Try it now publication, and live Voice Agent session |
| [`voice_agent_sdk_common.py`](../samples/voice_agent_sdk_common.py) | Shared config materialization, publication, readback, and Voice WebSocket runtime |

The MCP host exposes separate routes because the two business packs have some
same-named tools with different schemas:

| Example | MCP route | Foundry connection |
| --- | --- | --- |
| Example 1 | `/mcp/finance-handoff` | `finance-handoff-local-e2e` |
| Example 2 | `/mcp/finance-otp-officer` | `finance-otp-officer-local-e2e` |

## Prerequisites

- Python 3.10 or later.
- Docker.
- Azure CLI authenticated with `az login`.
- Azure Developer CLI (`azd`) authenticated with `azd auth login`.
- Dev Tunnel CLI authenticated with `devtunnel user login`.
- Access to a Microsoft Foundry Project with a compatible `gpt-realtime`
  model.
- Permission to create Project connections and publish Voice Agents.

This guide assumes the repository is already cloned. Set one reusable path to
its `VoiceAgent/samples` directory:

```bash
export VOICE_AGENT_ROOT=/path/to/Cognitive-Speech-TTS/VoiceAgent
export SAMPLES_ROOT="$VOICE_AGENT_ROOT/samples"
test -d "$VOICE_AGENT_ROOT/shared_mcp"
```

Verify that the Docker daemon, Azure identity, and Dev Tunnel identity are
ready before continuing:

```bash
docker info >/dev/null
az account show --output none
azd auth login --check-status
devtunnel user show
```

If `docker info` fails, start Docker Desktop or the Docker daemon for the
current operating system before retrying.

Install each example's Python dependencies before the first run:

```bash
cd "$SAMPLES_ROOT/example1_finance_with_handoff"
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt

cd "$SAMPLES_ROOT/example2_finance_with_OTP_and_Officer_Search"
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

`e2e-local.sh` prefers each sample's `.venv/bin/python`. It falls back to
`python3` only when the required SDK packages are already installed there.
`HANDOFF_SAMPLE_PYTHON` and `OTP_SAMPLE_PYTHON` may explicitly select other
interpreters.

Configure both sample `.env` files. They should use the same Foundry Project:

```bash
cd "$SAMPLES_ROOT"
cp example1_finance_with_handoff/.env.example \
  example1_finance_with_handoff/.env
cp example2_finance_with_OTP_and_Officer_Search/.env.example \
  example2_finance_with_OTP_and_Officer_Search/.env
```

Set a valid `AZURE_AI_PROJECT_ENDPOINT` in both files. Use
`AZURE_CREDENTIAL_MODE=cli` when the intended publishing identity is the one
selected by `az login`.

Choose the model mode that exists in that Project:

```dotenv
# Service-managed Voice Agent model.
VOICE_AGENT_MODEL_TYPE=managed
VOICE_AGENT_MODEL=gpt-realtime
```

```dotenv
# Customer-created Foundry model deployment.
VOICE_AGENT_MODEL_TYPE=self-deployed
VOICE_AGENT_MODEL=<exact-deployment-name>
```

`model_type` and the deployment name are separate. Do not change `agent.json`
for one machine: set both values in each sample `.env`. If publication rejects
`model_type=managed` but the Project has a compatible deployment, list the
account deployments and use the exact deployment name:

```bash
az cognitiveservices account deployment list \
  --resource-group "$RESOURCE_GROUP" \
  --name "$FOUNDRY_RESOURCE" \
  --query "[].{name:name,state:properties.provisioningState,model:properties.model.name}" \
  --output table
```

The checked-in `.env.example` files already select the canonical local MCP
configs:

```dotenv
# Example 1
VOICE_AGENT_MCP_CONFIG=../../shared_mcp/config/generated/example1.local.env
```

```dotenv
# Example 2
VOICE_AGENT_MCP_CONFIG=../../shared_mcp/config/generated/example2.local.env
```

These generated files do not exist until the local MCP E2E starts.

## Start the complete local MCP path

Run:

```bash
cd "$VOICE_AGENT_ROOT/shared_mcp"
./scripts/e2e-local.sh
```

The command performs all of the following:

1. Builds `voice-agent-shared-mcp:local`.
2. Runs the MCP tests inside the Docker build.
3. Starts `voice-agent-shared-mcp-local` on local port `18003`.
   The named `voice-agent-shared-mcp-state` Docker volume preserves active
   business call state across container restarts.
4. Creates or reuses the named Dev Tunnel recorded in
   `state/local/devtunnel-id`.
5. Creates or reuses the bearer token recorded in `state/local/token`.
6. Verifies public health and that unauthenticated MCP requests return HTTP
   401.
7. Creates or updates the two fixed Foundry connections.
8. Writes the two non-secret `config/generated/*.local.env` files.
9. Publishes `finance-example-local-e2e` and
   `finance-otp-officer-local-e2e`.
10. Runs both Agents and requires MCP evidence.
11. Keeps the container and Dev Tunnel host running.

The named tunnel, local port, token, connection names, and generated config are
reused on later runs. This gives the local MCP a stable Foundry-facing URL
instead of a new temporary URL on every invocation.

Leave this command running while using either Agent or the local UI. Pressing
`Ctrl+C` stops the local container and tunnel host process. The named tunnel,
generated config, Foundry connections, and published Agent versions remain,
but MCP calls cannot succeed until the local host starts again.

Wait for all of these final lines before opening another terminal:

```text
e2e_local=passed artifacts=...
fixed_tunnel_id=...
example1_config=...
example2_config=...
local_runtime=ready base_url=https://...
Press Ctrl+C to stop the local MCP container and dev tunnel.
```

For CI, run the same E2E without keeping the runtime alive:

```bash
SHARED_MCP_E2E_KEEP_RUNNING=0 ./scripts/e2e-local.sh
```

## Authentication model

The Dev Tunnel permits anonymous network access so Foundry can reach it, but
the MCP routes are not anonymous. Every Streamable HTTP MCP request requires a
bearer token.

The local workflow makes this transparent:

1. `e2e-local.sh` generates the token once and keeps it under ignored local
   state.
2. The token is stored in the two Foundry connections.
3. Generated example configs contain only the MCP URL and connection name.
4. `agent.json`, the browser, and the local UI never receive the token.

An unauthenticated HTTP 401 is expected and proves that the public endpoint is
gated. Do not disable the bearer gate merely because the implementation runs
locally; the Dev Tunnel URL is still public.

## How a Voice Agent uses the MCP

The committed `agent.json` files intentionally leave `server_url` and
`project_connection_id` empty. They are portable source definitions, not
developer-specific deployed definitions.

At publication time:

1. `VOICE_AGENT_MCP_CONFIG` selects one generated config.
2. `voice_agent_sdk_common.py` reads its route URL and connection name.
3. Every MCP tool in the Agent definition receives the same route-specific
   values.
4. No authorization header or token is written into the Agent definition.
5. The SDK publishes and enables an immutable Voice Agent version.
6. Readback verifies the model, graph shape, and connection reference.

At runtime:

1. The client opens the published Agent's Voice WebSocket.
2. Foundry reads the MCP tool's public `server_url`.
3. Foundry obtains the authorization value from `project_connection_id`.
4. Foundry calls the local MCP through the Dev Tunnel.
5. The MCP executes the business state machine and returns the tool result.
6. The Voice Agent continues the conversation or handoff using that result.

## Publish and run from the CLI

`e2e-local.sh` already publishes and runs both examples. To repeat an operation
from another terminal while E2E remains running:

### Example 1: Finance with handoff

```bash
cd "$SAMPLES_ROOT/example1_finance_with_handoff"

VOICE_AGENT_NAME=finance-example-local-e2e \
  .venv/bin/python sample.py publish

VOICE_AGENT_NAME=finance-example-local-e2e \
  .venv/bin/python sample.py check

VOICE_AGENT_NAME=finance-example-local-e2e \
  .venv/bin/python sample.py run \
    --message "Hello, who is calling?" \
    --expect-handoff \
    --expect-mcp
```

### Example 2: OTP and officer search

```bash
cd "$SAMPLES_ROOT/example2_finance_with_OTP_and_Officer_Search"

VOICE_AGENT_NAME=finance-otp-officer-local-e2e \
  .venv/bin/python sample.py publish

VOICE_AGENT_NAME=finance-otp-officer-local-e2e \
  .venv/bin/python sample.py check

VOICE_AGENT_NAME=finance-otp-officer-local-e2e \
  .venv/bin/python sample.py run \
    --message "Hello, I need to reach my loan officer." \
    --message "12345007" \
    --expect-mcp
```

If a sample `.env` does not contain the canonical
`VOICE_AGENT_MCP_CONFIG`, set it on the command line explicitly:

```bash
VOICE_AGENT_MCP_CONFIG=../../shared_mcp/config/generated/example1.local.env \
  .venv/bin/python sample.py publish
```

## Load and publish the examples from the local UI

Run the MCP E2E first and leave it running. Then open another terminal:

```bash
cd "$SAMPLES_ROOT/local_UI"
cp .env.example .env
# Set AZURE_AI_PROJECT_ENDPOINT and, when needed,
# AZURE_CREDENTIAL_MODE=cli in .env.

python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py --host 127.0.0.1 --port 8097
```

If the UI runs on the same computer as the browser, open
`http://localhost:8097` directly.

If it runs in a VS Code Remote-SSH host:

1. Verify `curl -sS http://127.0.0.1:8097/healthz` in the remote terminal.
2. Open the VS Code **PORTS** view in that same Remote-SSH window.
3. Forward remote port `8097`.
4. Open the exact **Forwarded Address** shown by VS Code; the local port may
   differ if `8097` is already occupied.

Use `localhost` or the forwarded HTTPS address so browser microphone access
has a secure context.

The default [`local_UI/templates.config.json`](../samples/local_UI/templates.config.json)
maps each template to:

- its sibling `agent.json`;
- the same generated `*.local.env` used by the CLI.

On **Try it now**, the UI:

1. Loads the MCP route and fixed connection name from the generated config.
2. Reads the ignored local token file on the server, never in the browser.
3. Runs an authenticated MCP `initialize` and `tools/list`, then verifies every
   tool allowed by the template. HTTP 401/403 fails this readiness check.
4. Creates or updates the fixed connection in the currently selected Foundry
   Project/account.
5. Materializes and publishes a new independent Agent.
6. Opens that Agent in the Live session page.

Every Agent created from Templates is named with the `gft-` prefix
(`generated_from_template`). If no name is supplied, the result follows
`gft-<template-id>-<unique-suffix>`. Foundry Agent names do not allow
underscores, so `gft-` is the platform-compatible form of the intended `gft_`
prefix.

If the UI started before `e2e-local.sh`, open Templates and select **Reload**
after the E2E config has been generated. If the config is still unavailable,
publication remains disabled with an instruction to start the local MCP E2E.

The Project selected in the UI must be the same Project for which
`e2e-local.sh` created the two connections. To use another Project, update
`AZURE_AI_PROJECT_ENDPOINT` in both example `.env` files, rerun E2E so the
connections are created there, select that Project in the UI, and reload the
templates.

The UI initially uses `AZURE_AI_PROJECT_ENDPOINT` from `local_UI/.env`. To
change it, type a Project name in the **Foundry project** text box, choose a
suggestion, and press Enter or **Switch**. Search matches only the Project name;
the account is displayed only to distinguish suggestions. You may also paste
the full endpoint. Choose the Project whose name matches the endpoint configured
in both examples.

## Verify the closed loop

### MCP runtime

```bash
cd "$VOICE_AGENT_ROOT"
curl -sS http://127.0.0.1:18003/healthz
docker inspect \
  -f '{{.State.Status}}/{{.State.Health.Status}}' \
  voice-agent-shared-mcp-local
```

Expected:

```text
{"status":"ok"}
running/healthy
```

Inspect the persistent tunnel:

```bash
tunnel_id=$(<shared_mcp/state/local/devtunnel-id)
devtunnel show "$tunnel_id"
devtunnel port show "$tunnel_id" -p 18003
```

### Generated config

```bash
test -s shared_mcp/config/generated/example1.local.env
test -s shared_mcp/config/generated/example2.local.env
```

The files must contain an HTTPS MCP URL and a connection name, but no bearer
token.

The script creates `state/local/token` with owner-only permissions under a
directory ignored by Git. Do not use real customer data with this public
development tunnel.

### Agent publication

`.venv/bin/python sample.py check` should report:

- the expected Agent name and active version;
- the intended Foundry connection;
- matching requested/readback fingerprints for the current generated config.

### Local UI

The Templates page should:

- show both Finance examples;
- show a successful MCP reachability check;
- not display an MCP token field;
- expose **Test MCP** for a manual retry;
- allow **Try it now**;
- open the newly published Agent in Live session.

## Troubleshooting

| Symptom | Cause | Resolution |
| --- | --- | --- |
| Published Agent cannot list MCP tools | Local container or tunnel host stopped | Restart `shared_mcp/scripts/e2e-local.sh` and leave it running |
| Tool returns `unknown_call` after a runtime replacement | The call started before state persistence was enabled, or the Docker state volume was removed | End that Voice Agent session and reconnect; keep the named state volume for later restarts |
| HTTP 401 from a direct MCP request | Request omitted the bearer token | Expected for unauthenticated probes; Foundry supplies it from the connection |
| Generated config is missing | Local E2E has not completed connection setup | Run `e2e-local.sh`; in an already open UI, select Templates **Reload** |
| UI disables Try it now | `mcp.config_file` is not ready | Confirm both `config/generated/*.local.env` files exist |
| UI publish says connection not found | UI selected a different Foundry Project | Select the same Project configured in the examples and rerun/reload |
| UI publish reports Agent write permission denied | UI used the wrong Azure identity | Set `AZURE_CREDENTIAL_MODE=cli`, run `az login` with the intended identity, and restart UI |
| Port 18003 is already allocated | An older E2E/container is still running | Stop the older owning script/container, then start the canonical E2E |
| Agent check fingerprints differ | Active Agent was published with another tunnel/config | Republish using the current canonical `*.local.env` |
| New immutable versions appear | Foundry Agent versions are append-only | Expected after each successful publish |

## Rotate or revoke local access

Stop the running E2E with `Ctrl+C` before rotating its credential. From
`VoiceAgent/shared_mcp/`, remove only the local token and rerun E2E:

```bash
rm -f state/local/token
./scripts/e2e-local.sh
```

The script creates a new token and replaces the credential in both fixed
Foundry connections. Previously copied token values no longer authenticate.

To revoke the endpoint completely, stop the local host and delete or disable
the two `*-local-e2e` connections in the Foundry Project. The guide does not
delete connections or immutable Agent versions automatically.

## Local versus Azure-hosted MCP

This guide describes local debugging:

- Docker executes MCP locally.
- A persistent named Dev Tunnel provides Foundry reachability.
- Samples select `example1.local.env` and `example2.local.env`.

For a customer-owned Azure Container Apps deployment, use
`VoiceAgent/shared_mcp/scripts/deploy.sh`. That path writes
`example1.shared.env` and `example2.shared.env`; select those configs instead
of the local files.

## Sample limitations

- Loan-officer name search is deliberately a fake implementation that returns
  a random available fictional officer.
- State is stored locally and is not production durable.
- The local E2E uses one MCP container replica.
- Dev Tunnel is a development bridge, not a production ingress.

See [02: MCP settings](./02_mcp_settings.md) for packaging, infrastructure,
security, modification, and persistence details.
