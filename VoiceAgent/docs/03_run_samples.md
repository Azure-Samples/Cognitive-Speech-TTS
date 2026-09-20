# 03 - Start and run the Finance samples

## Conclusion

This is the executable local setup and validation sequence. Start with the
[architecture and documentation index](./README.md) when choosing a
component or looking for a specific guide.

After completing the one-time prerequisites, run
`VoiceAgent/shared_mcp/scripts/e2e-local.sh` before publishing or opening either Finance
example in the portal. The command starts the MCP implementation as a native Python process,
exposes it to Microsoft Foundry through a persistent named Dev Tunnel, creates
the required Foundry connections, generates the shared local config, and
verifies both public MCP route contracts. Each sample CLI or the portal then
publishes the selected Agent independently.

The complete local path is:

```text
local Python process
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
       +--> portal Templates / Try it now
```

Do not put `localhost` in a published Voice Agent. MCP calls are made from
Foundry, not from the local browser or Python client, so the Agent requires a
public HTTPS URL even when the MCP implementation runs on a developer machine.

For component-specific detail, use:

- [MCP implementation, local hosting, and Azure deployment](./02_mcp_settings.md)
- [Portal startup and configuration](../portal/README.md)
- [Example 1: Finance with Handoff](../samples/example1_finance_with_handoff/README.md)
- [Example 2: Finance with OTP and Officer Search](../samples/example2_finance_with_OTP_and_Officer_Search/README.md)
- [Recorded session debugging](./04_debug_session.md)

## Components

| Component | Responsibility |
| --- | --- |
| [`shared_mcp/`](../shared_mcp/) | Customer-owned MCP code, native local runtime, optional container packaging, Dev Tunnel, connections, and E2E |
| [`example1_finance_with_handoff/`](../samples/example1_finance_with_handoff/) | Handoff Agent definition and CLI publication/runtime entry point |
| [`example2_finance_with_OTP_and_Officer_Search/`](../samples/example2_finance_with_OTP_and_Officer_Search/) | Flat OTP/officer Agent definition and CLI publication/runtime entry point |
| [`portal/`](../portal/) | Browser template catalog, Try it now publication, authoring, and live Voice Agent session |
| [`voice_agent_sdk_common.py`](../samples/voice_agent_sdk_common.py) | Shared config materialization, publication, readback, and Voice WebSocket runtime |

The MCP host exposes separate routes because the two business packs have some
same-named tools with different schemas:

| Example | MCP route | Foundry connection |
| --- | --- | --- |
| Example 1 | `/mcp/finance-handoff` | `finance-handoff-local-e2e` |
| Example 2 | `/mcp/finance-otp-officer` | `finance-otp-officer-local-e2e` |

## Prerequisites

- Python 3.10 or later.
- Azure CLI authenticated with `az login`.
- Dev Tunnel CLI authenticated with a Microsoft or GitHub identity.
- Access to a Microsoft Foundry Project with a compatible versioned managed
  realtime model.
- Permission to create Project connections and publish Voice Agents.

Azure Developer CLI is not required for this local workflow. It is required
only by the Azure Container Apps deployment path in guide 02.

This guide assumes the repository is already cloned. Set one reusable path to
its `VoiceAgent/samples` directory:

```bash
export VOICE_AGENT_ROOT=/path/to/Cognitive-Speech-TTS/VoiceAgent
export SAMPLES_ROOT="$VOICE_AGENT_ROOT/samples"
test -d "$VOICE_AGENT_ROOT/shared_mcp"
```

Verify that the Azure identity and Dev Tunnel identity are
ready before continuing:

```bash
az account show --output none

cd "$VOICE_AGENT_ROOT/shared_mcp"
devtunnel user show --json
```

The local workflow does not require or invoke Docker. Install Docker only when
deliberately running the separate `shared_mcp/scripts/package.sh` image
packaging command. Azure Container Apps deployment uses a remote build.

If `devtunnel` is missing or authentication fails, follow the install and
device-code steps in
[02: MCP settings and E2E](./02_mcp_settings.md#install-dev-tunnel-cli-on-linux-or-wsl).

## Create the two sample and portal Python environments

The two Finance scenarios and portal have separate requirements and separate
virtual environments. Setup also creates `shared_mcp/.venv` for the native MCP
runtime. Create the environment for each component that you plan to run.

The recommended setup entry point is:

```bash
cd "$VOICE_AGENT_ROOT"
./scripts/setup-local-examples.sh \
  --project-endpoint "$AZURE_AI_PROJECT_ENDPOINT"
```

`setup-local-examples.sh` checks required command-line tools, installs
Dev Tunnel when missing, creates or reuses the three Python environments,
installs the portal Node dependencies, runs/builds the browser code, and
creates the three local `.env` files. On the first normal setup it also
generates `shared_mcp/state/local/devtunnel-id`; later setup, E2E, and manager
runs reuse that fixed local ID. The file is ignored by Git. Use `--check` to
inspect readiness without installing, generating the ID, or changing
environments.

When reusing an older sample `.env`, setup migrates MCP selection to the
canonical `VOICE_AGENT_MCP_CONFIG` file and removes legacy direct MCP URL and
connection overrides. This prevents an old connection from another Project
from overriding the connection created by the current E2E.

Set a package index once when the default PyPI file host is unavailable:

```bash
export PIP_INDEX_URL="${PIP_INDEX_URL:-https://pypi.org/simple}"
```

For example, a customer-approved mirror can be selected before running the
commands:

```bash
export PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
```

Install each example's Python dependencies before the first run:

```bash
cd "$SAMPLES_ROOT/example1_finance_with_handoff"
python3 -m venv .venv
.venv/bin/python -m pip install \
  --index-url "${PIP_INDEX_URL}" \
  -r requirements.txt

cd "$SAMPLES_ROOT/example2_finance_with_OTP_and_Officer_Search"
python3 -m venv .venv
.venv/bin/python -m pip install \
  --index-url "${PIP_INDEX_URL}" \
  -r requirements.txt

cd "$VOICE_AGENT_ROOT/portal"
python3 -m venv .venv
.venv/bin/python -m pip install \
  --index-url "${PIP_INDEX_URL}" \
  -r requirements.txt

cd web
npm ci
npm test
npm run build:all
```

## Configure the two sample and portal environment files

Configure both sample `.env` files. They must use the same Foundry Project:

```bash
cd "$SAMPLES_ROOT"
cp example1_finance_with_handoff/.env.example \
  example1_finance_with_handoff/.env
cp example2_finance_with_OTP_and_Officer_Search/.env.example \
  example2_finance_with_OTP_and_Officer_Search/.env

cp ../portal/.env.example ../portal/.env
```

Set the same valid Project endpoint in all three files. Portal uses
`AZURE_VOICE_AGENTS_ENDPOINT`; the samples use `AZURE_AI_PROJECT_ENDPOINT`.
Use `AZURE_CREDENTIAL_MODE=cli` in all three when the intended identity is the one
selected by `az login`. To find an existing endpoint rather than guessing it,
use [01: Existing Project fast path](./01_setup_subscription.md#existing-project-fast-path).

The endpoint must be a full Project endpoint, not an Azure portal URL or
account endpoint:

```dotenv
AZURE_AI_PROJECT_ENDPOINT=https://<account>.services.ai.azure.com/api/projects/<project>
AZURE_CREDENTIAL_MODE=cli
```

The samples use the standard service-managed Voice Agent model:

```dotenv
VOICE_AGENT_MODEL=gpt-realtime-2.1
```

`model_type: managed` remains in each committed `agent.json`. Start with the
default `gpt-realtime-2.1`. If that exact model is unsupported, set
`VOICE_AGENT_MODEL=gpt-realtime-1.5` in both Finance sample `.env` files and
the portal `.env`, then retry publication. If the Project exposes another
managed variant, use its exact identifier instead. This workflow does not
require a customer-created model deployment.

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

The recommended entry point starts both MCP and portal, replacing stale
processes from earlier runs:

```bash
cd "$VOICE_AGENT_ROOT"
PIP_INDEX_URL="${PIP_INDEX_URL}" \
  ./scripts/manage-local-mcp-and-ui.sh restart
```

`manage-local-mcp-and-ui.sh` owns the local runtime lifecycle. It
stops stale repository-owned MCP, Dev Tunnel, and portal processes; starts
the MCP E2E and portal; waits for both health endpoints; reloads the template
catalog; and requires successful MCP probes for both templates before reporting
`local_mcp_and_portal=ready`.

Runtime PID and log files are stored under ignored
`.local-mcp-and-ui/` state. Use:

```bash
./scripts/manage-local-mcp-and-ui.sh status
./scripts/manage-local-mcp-and-ui.sh stop
```

To run only MCP without the portal, use the lower-level command below.

Run:

```bash
cd "$VOICE_AGENT_ROOT/shared_mcp"
PIP_INDEX_URL="${PIP_INDEX_URL}" ./scripts/e2e-local.sh
```

The command performs all of the following:

1. Runs the MCP tests using `shared_mcp/.venv`.
2. Starts `python -m shared_mcp.server` on local port `18003`.
3. Persists active business state under `shared_mcp/state/local/runtime/`.
4. Creates or reuses the setup-initialized named Dev Tunnel recorded in
   `state/local/devtunnel-id`.
5. Creates or reuses the bearer token recorded in `state/local/token`.
6. Verifies public health and that unauthenticated MCP requests return HTTP
   401.
7. Creates or updates the two fixed Foundry connections.
8. Writes the two non-secret `config/generated/*.local.env` files.
9. Runs authenticated `initialize` and `tools/list` against both public routes
   and verifies the tool inventory against both `agent.json` contracts.
10. Keeps the native MCP process and Dev Tunnel host running for sample or UI
    publication.

The named tunnel, local port, token, connection names, and generated config are
reused on later runs. This gives the local MCP a stable Foundry-facing URL
instead of a new temporary URL on every invocation.

Leave this command running while using either Agent or the portal. Pressing
`Ctrl+C` stops the local Python server and tunnel host process. The named tunnel,
generated config, Foundry connections, and published Agent versions remain,
but MCP calls cannot succeed until the local host starts again.

Wait for all of these final lines before opening another terminal:

```text
e2e_local=passed artifacts=...
fixed_tunnel_id=...
example1_config=...
example2_config=...
local_runtime=ready base_url=https://...
mcp_runtime=native
Press Ctrl+C to stop the local MCP runtime and dev tunnel.
```

For CI, run the same E2E without keeping the runtime alive:

```bash
SHARED_MCP_E2E_KEEP_RUNNING=0 ./scripts/e2e-local.sh
```

Do not start the UI from Templates before E2E reaches the final success lines.
The optional `package.sh` only creates a Docker image. It does not generate the
Project connections, `state/local/token`, or `config/generated/*.local.env`.
The sample CLIs and portal publish Agents only after this MCP process is
ready; their model or Agent validation failures do not stop MCP hosting.

## Authentication model

The Dev Tunnel permits anonymous network access so Foundry can reach it, but
the MCP routes are not anonymous. Every Streamable HTTP MCP request requires a
bearer token.

The local workflow makes this transparent:

1. `e2e-local.sh` generates the token once and keeps it under ignored local
   state.
2. The token is stored in the two Foundry connections.
3. Generated example configs contain only the MCP URL and connection name.
4. `agent.json`, the browser, and the portal never receive the token.

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

Publish or run either example from another terminal while E2E remains running:

### Example 1: Finance with handoff

```bash
cd "$SAMPLES_ROOT/example1_finance_with_handoff"

.venv/bin/python sample.py publish --variant all

.venv/bin/python sample.py check --variant all

.venv/bin/python sample.py run --variant realtime \
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

## Load and publish the examples from the portal

Run the MCP E2E first and leave it running. Then open another terminal:

```bash
cd "$VOICE_AGENT_ROOT/portal"
.venv/bin/python demo_server.py --credential-mode cli --bind 127.0.0.1 --port 9527
```

Choose another free port with `--port`, for example `--port 9530`. The browser
URL and forwarded port must use the same value.

If the UI runs on the same computer as the browser, open
`http://localhost:9527` directly.

If it runs in a VS Code Remote-SSH host:

1. Verify `curl -sS http://127.0.0.1:9527/healthz` in the remote terminal.
2. Open the VS Code **PORTS** view in that same Remote-SSH window.
3. Forward remote port `9527`.
4. Open the exact **Forwarded Address** shown by VS Code; the local port may
   differ if `9527` is already occupied.

Use `localhost` or the forwarded HTTPS address so browser microphone access
has a secure context.

The default [`portal/templates.config.json`](../portal/templates.config.json)
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

Every Agent created from Templates is named with the `local-only-` prefix. If
no name is supplied, the result follows
`local-only-<template-id>-<unique-suffix>`. This deliberately warns that the
Agent's MCP connection targets this machine's Dev Tunnel and will be
unavailable when its native MCP runtime and tunnel are not running.

If the UI started before `e2e-local.sh`, open Templates and select **Reload**
after the E2E config has been generated. If the config is still unavailable,
publication remains disabled with an instruction to start the local MCP E2E.

The Project selected in the UI must be the same Project for which
`e2e-local.sh` created the two connections. To use another Project, update
`AZURE_AI_PROJECT_ENDPOINT` in both example `.env` files, rerun E2E so the
connections are created there, select that Project in the UI, and reload the
templates.

The portal initially uses `AZURE_VOICE_AGENTS_ENDPOINT` from `portal/.env`. To
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
```

Expected:

```text
{"status":"ok"}
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
test -s shared_mcp/state/local/token
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

### Portal

The Templates page should:

- show both Finance examples;
- show a successful MCP reachability check;
- not display an MCP token field;
- expose **Test MCP** for a manual retry;
- allow **Try it now**;
- open the newly published Agent in Live session.

The portal caches the template catalog. If E2E started after the portal,
select **Reload** before **Test MCP** or **Try it now**. Readiness is complete
only when both template probes report HTTP 200 and list the expected tools.

## Troubleshooting

For cross-layer diagnosis, use the shared
[`debug-local-session` Skill](../skills/debug-local-session/):

```bash
cd VoiceAgent
./scripts/manage-local-mcp-and-ui.sh status
python skills/debug-local-session/scripts/analyze_session.py --list
python skills/debug-local-session/scripts/analyze_session.py <session-id>
```

It covers setup, Project/model deployment, Agent publication/version,
RemoteTool connection, MCP route/auth/tools, portal bridge, and session
recordings.

| Symptom | Cause | Resolution |
| --- | --- | --- |
| `files.pythonhosted.org` TLS or connection failure during setup | The host cannot reach the configured Python package index | Set `PIP_INDEX_URL` to a customer-approved mirror and rerun setup |
| `devtunnel is required` | Dev Tunnel CLI is missing or not on `PATH` | Install it and add its reported directory, commonly `~/bin`, to `PATH` |
| Dev Tunnel sign-in says the account does not meet access criteria | Entra Conditional Access rejected the flow | Use GitHub device-code login as documented in guide 02, or use Azure hosting if policy prohibits Dev Tunnel |
| A sample command cannot import its requirements | That scenario's `.venv` was not created | Install that scenario's requirements; the UI `.venv` is not a substitute |
| E2E cannot find the Project | The active Azure CLI subscription is wrong or the endpoint was guessed | Select the exact subscription and discover the Project through Azure CLI as documented in guide 01 |
| `Model '<name>' is not supported in managed mode in this region` | The exact managed model identifier is unavailable in the selected Project, or the Project is not eligible | Try the documented versioned fallback (`gpt-realtime-2.1`, then `gpt-realtime-1.5`), use another exact identifier confirmed for that Project, or move to an eligible Project; do not switch to self-deployed mode merely to bypass the error |
| Published Agent cannot list MCP tools | Local Python server or tunnel host stopped | Restart `shared_mcp/scripts/e2e-local.sh` and leave it running |
| Tool returns `unknown_call` after a runtime replacement | The call started before state persistence was enabled, or `state/local/runtime` was removed | End that Voice Agent session and reconnect; retain the native state directory |
| HTTP 401 from a direct MCP request | Request omitted the bearer token | Expected for unauthenticated probes; Foundry supplies it from the connection |
| Generated config is missing | Local E2E has not completed connection setup | Run `e2e-local.sh` to its final success lines; in an already open UI, select Templates **Reload** |
| UI Build says `The local MCP config is not ready` | One of the generated config files or `state/local/token` is missing, or the portal cached its catalog before E2E completed | Keep a successful E2E process running, verify all three files, then select Templates **Reload** |
| UI publish says connection not found | UI selected a different Foundry Project | Select the same Project configured in the examples and rerun/reload |
| UI publish reports Agent write permission denied | UI used the wrong Azure identity | Set `AZURE_CREDENTIAL_MODE=cli`, run `az login` with the intended identity, and restart UI |
| Port 18003 is already allocated | An older E2E/native process is still running | Stop the older owning script, then start the canonical E2E |
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

- Native Python executes MCP locally.
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
- The local E2E uses one native MCP process.
- Dev Tunnel is a development bridge, not a production ingress.

See [02: MCP settings](./02_mcp_settings.md) for packaging, infrastructure,
security, modification, and persistence details.
