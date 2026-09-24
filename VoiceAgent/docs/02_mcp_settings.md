# 02 - MCP settings, deployment, and development

## Conclusion

The [`VoiceAgent/shared_mcp/`](../shared_mcp/) directory contains the
customer-owned MCP implementation used by all three Portal examples. Run one
command to build it locally or one command to deploy it to Azure Container Apps
and create the three Foundry Project connections required by the Agents.

Use the [architecture and documentation index](./README.md) for the system
overview. After the MCP is ready, continue with
[03: Start and run the samples](./03_run_samples.md).

The server exposes two separate Streamable HTTP routes because the samples
have overlapping tool names with different schemas:

| Sample | MCP route | Generated config |
| --- | --- | --- |
| `example1_finance_with_handoff` | `/mcp/finance-handoff` | `config/generated/example1.local.env` |
| `example2_finance_with_OTP_and_Officer_Search` | `/mcp/finance-otp-officer` | `config/generated/example2.local.env` |
| `example3_elevator_service_with_safety_zendesk_and_handoff` | `/mcp/elevator-service` | `config/generated/example3.local.env` |

Both routes require the same bearer token. `/healthz` is public and contains
only liveness status.

## Choose the command by goal

| Goal | Command | Port / reachability | What remains running |
| --- | --- | --- | --- |
| Run the complete local Foundry path | `./scripts/e2e-local.sh` | Local `18003` plus a public named Dev Tunnel | Native Python server and tunnel host |
| Optionally build the image and run container tests | `./scripts/package.sh` | No listener | Nothing |
| Deploy customer-owned Azure hosting | `AZURE_AI_PROJECT_ENDPOINT=... ./scripts/deploy.sh` | Azure Container App HTTPS URL | Azure resources |

## Important sample limitation

The name search in
`app/shared_mcp/finance_otp_officer/directory.py` is intentionally a **fake
implementation**. Production name search uses a large phonetic index and
recognizer-aware matching that is too complex and heavy for this portable
sample. Here, every non-empty name query returns one random available officer
from the committed fictional fixture.

Do not use this fake matcher, the fictional OTP, or the filesystem state store
for real customer data.

## Optional Docker packaging

Prerequisites:

- Docker Engine or Docker Desktop, accessible to the current user
- Docker Buildx with support for additional build contexts
- Bash

Verify both the daemon and builder before packaging:

```bash
docker info
docker buildx version
docker buildx build --help | grep -q -- '--build-context'
```

If `docker buildx version` fails, install the Buildx CLI plugin for the current
Docker distribution. If the final check fails, upgrade Buildx. Only
`package.sh` enforces these checks. Local setup, E2E, and lifecycle commands do
not inspect, require, or invoke Docker.

Build the runtime image and run all MCP tests inside the image:

```bash
cd /path/to/Cognitive-Speech-TTS/VoiceAgent/shared_mcp
./scripts/package.sh
```

The resulting image is `voice-agent-shared-mcp:local`. Override it with
`SHARED_MCP_IMAGE`.

### Use another Python package index

The Docker build uses `https://pypi.org/simple` by default. If the Docker
network or corporate proxy cannot complete TLS requests to
`files.pythonhosted.org`, use a package index that also hosts the package files:

```bash
PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
   ./scripts/package.sh
```

`PIP_INDEX_URL` is passed into both the test and runtime Docker targets. A
mirror must be approved by the customer's security policy; the example above
is not a Microsoft-operated service.

## Run the complete local MCP E2E

This is the supported local workflow for publishing the Finance templates or
selecting **Try it now** in the portal. It always uses native Python; building
the optional image alone does not create a public MCP address, Project
connections, or generated template config.

Prerequisites:

- Azure CLI authenticated with `az login`
- Python 3.10 or later
- OpenSSL and `curl`
- Dev Tunnel CLI authenticated with GitHub for this local workflow
- Permission to create connections in the target Foundry Project

The local workflow uses Azure CLI for Project discovery and connection
creation. It does not require Azure Developer CLI or `azd auth login`.

### Install Dev Tunnel CLI on Linux or WSL

The recommended full setup installs a repository-local CLI automatically when
`devtunnel` is not already available:

```bash
cd /path/to/Cognitive-Speech-TTS/VoiceAgent
./scripts/setup-local-examples.sh \
   --project-endpoint "https://<account>.services.ai.azure.com/api/projects/<project>"
```

The executable is stored under the ignored `.local-mcp-and-ui/tools/` state,
and both setup and lifecycle scripts discover it automatically. Do not add that
directory to the interactive shell `PATH`. The manual system/user-local install
below is optional and remains useful when `devtunnel` is needed outside this
repository.

```bash
curl -sL https://aka.ms/DevTunnelCliInstall | bash

# The installer commonly uses ~/bin on Linux and WSL.
export PATH="$HOME/bin:$PATH"
devtunnel --version
```

Persist the `PATH` update in the user's shell profile when the executable is
installed under `~/bin`. Confirm the actual installer output before choosing a
directory.

### Authenticate Dev Tunnel

Use GitHub device-code authentication for this local MCP workflow. Azure
resource operations still use the separate identity selected by `az login`;
the GitHub identity authenticates only the Dev Tunnel host.

Run login and verification from the same `shared_mcp` directory used by E2E.
On the onboarding Linux host, Dev Tunnel resolved different saved identities
from different working directories. The setup and E2E scripts therefore also
run all Dev Tunnel identity and tunnel commands from this directory.

When setup installed the repository-local CLI, use the repository wrapper. It
selects the correct executable and working directory in a fresh shell:

```bash
cd /path/to/Cognitive-Speech-TTS/VoiceAgent
./scripts/login-devtunnel.sh
./scripts/setup-local-examples.sh --check
```

The wrapper is the supported login entry point. It selects the repository-local
executable and the `shared_mcp` working directory, including on a remote or
headless host.

The verification output must contain `"status": "Logged in"`. Do not use the
command's exit code as the authentication gate: current Dev Tunnel CLI builds
also exit zero with `{"status":"Not logged in"}`. The repository setup and
E2E scripts parse this JSON status before reporting readiness.

A customer policy can prohibit GitHub or Dev Tunnel entirely; in that case use
the Azure Container Apps deployment path instead of changing identity providers.

The script creates the tunnel with anonymous network reachability so Foundry
can call it. The MCP routes are not anonymous: they still require the bearer
token stored in the Project connection.

### Run E2E

Complete normal setup once from the `VoiceAgent` directory. Setup generates a
random tunnel ID for this machine and records it in ignored local state;
`--check` verifies but does not create that ID:

```bash
./scripts/setup-local-examples.sh \
   --project-endpoint "${AZURE_AI_PROJECT_ENDPOINT}"
```

Then run:

```bash
az account show --output table
./scripts/setup-local-examples.sh --check
./scripts/manage-local-mcp-and-ui.sh restart
```

The script requires authenticated `az` and `devtunnel` CLIs. By default it:

- runs the MCP tests from `shared_mcp/.venv`;
- starts `python -m shared_mcp.server` on port `18003`;
- creates or reuses a named Dev Tunnel and local bearer token;
- verifies public health and unauthenticated HTTP 401 behavior;
- creates or updates three `RemoteTool` Project connections through Azure CLI;
- writes `config/generated/example1.local.env` and `example2.local.env`;
- verifies authenticated `initialize` and `tools/list` against both public MCP
   routes and checks each route against its sample `agent.json` tool contract;
- remains running so the sample CLIs or portal can publish and invoke Agents.

Project connection creation uses the active Azure CLI subscription. If the
Project is not found, select its exact subscription and retry:

```bash
az account set --subscription "<exact-subscription-name-or-id>"
```

Use the discovery procedure in
[01: Existing Project fast path](./01_setup_subscription.md#existing-project-fast-path)
when the endpoint or subscription is unknown.

Setup creates `state/local/devtunnel-id` once with a random 16-hex suffix. The
file is ignored by Git and all later E2E and management runs on this checkout
reuse that ID, its fixed URL, the token in `state/local/token`, and the two
connection names. E2E never silently replaces the recorded ID.

If the fixed ID is no longer visible to the authenticated identity but its
name conflicts during creation, first sign in with the identity that owns it.
To intentionally reset this machine's tunnel identity, remove only
`state/local/devtunnel-id` and rerun normal setup; review and update any system
that retained the old tunnel URL. An explicitly supplied
`SHARED_MCP_TUNNEL_ID` is also never replaced automatically.

Run evidence is written under `state/e2e/<UTC-run-id>/`.

The native server and tunnel remain active after the tests so downstream Agents
can call both MCP routes. Press `Ctrl+C` to stop hosting them. The named tunnel
itself is retained, so the next run restores the same address. For CI, set
`SHARED_MCP_E2E_KEEP_RUNNING=0`; the script then exits immediately and cleans
up its local Python server and tunnel host process. The isolated Foundry Agents,
connections, and named tunnel are retained, but the MCP endpoint is naturally
unavailable while no local host process is running.

The native runtime stores active call IDs and OTP state under
`state/local/runtime/`. State survives a native process restart. Removing that
directory invalidates in-progress calls; start a new Voice Agent session
afterward.

The script also writes the current non-secret route and connection mappings:

```text
config/generated/example1.local.env
config/generated/example2.local.env
```

The sample CLIs and portal read those files when publishing. While the E2E
script is still running, publish or invoke either sample from another terminal:

```bash
cd ../samples/example1_finance_with_handoff
VOICE_AGENT_MCP_CONFIG=../../shared_mcp/config/generated/example1.local.env \
  python sample.py publish --variant all
```

```bash
cd ../samples/example2_finance_with_OTP_and_Officer_Search
VOICE_AGENT_NAME=finance-otp-officer-local-e2e \
VOICE_AGENT_MCP_CONFIG=../../shared_mcp/config/generated/example2.local.env \
  python sample.py publish
```

The config files contain only the MCP URL and Foundry connection name. The
bearer token stays in the Foundry connection and local E2E state.

Do not treat the existence of those files as E2E success. Wait for all of these
lines and leave the command running:

```text
e2e_local=passed artifacts=...
fixed_tunnel_id=...
example1_config=...
example2_config=...
local_runtime=ready base_url=https://...
mcp_runtime=native
Press Ctrl+C to stop the local MCP runtime and dev tunnel.
```

### Local E2E failures seen during setup

| Error | Meaning | Resolution |
| --- | --- | --- |
| `devtunnel is required` | Repository-local CLI is missing | Run normal `setup-local-examples.sh` without `--check` |
| Dev Tunnel is not logged in | GitHub device-code login has not completed | Run `./scripts/login-devtunnel.sh`, complete the GitHub browser prompt, then run setup `--check` |
| The fixed Dev Tunnel ID conflicts with an unavailable tunnel | The ID belongs to another identity or stale external state | Sign in with its owner; to intentionally reset the machine ID, remove `state/local/devtunnel-id`, rerun normal setup, and update consumers of the old URL |
| `configure AZURE_AI_PROJECT_ENDPOINT` | Example 1 `.env` is missing or still contains the placeholder | Discover the endpoint with Azure CLI and copy it into both sample `.env` files |
| Project not found in active Azure CLI subscription | Endpoint and active subscription do not match | Run `az account set` with the exact subscription name or ID |
| UI says `The local MCP config is not ready` | E2E has not reached connection/config generation, or a prior failed run left an offline config | Run E2E to the final success lines, keep it running, then select **Reload** in Templates |

## Deploy to Azure Container Apps

Use this path when Dev Tunnel is prohibited or the MCP needs customer-owned
Azure hosting.

Prerequisites:

- Azure CLI authenticated with `az login`
- Azure Developer CLI authenticated with `azd auth login`
- Permission to create a resource group, Container Registry, Log Analytics,
  Container Apps resources, and an `AcrPull` role assignment
- Permission to create connections in the target Foundry Project

```bash
export AZURE_AI_PROJECT_ENDPOINT="https://<account>.services.ai.azure.com/api/projects/<project>"
cd /path/to/Cognitive-Speech-TTS/VoiceAgent/shared_mcp
./scripts/deploy.sh
```

The first run creates a unique azd environment and may ask for subscription
and location. Set `AZURE_SUBSCRIPTION_ID`, `AZURE_LOCATION`, and optionally
`AZURE_ENV_NAME` for a non-interactive run. Unlike local E2E, this path needs
`azd` because `azd up` provisions the Azure infrastructure, performs the
configured remote container build, and stores its outputs. Local Docker is not
required. If Conditional Access rejects `azd auth login`, use an authentication
method approved by the customer's administrator; GitHub Dev Tunnel login does
not authenticate Azure Developer CLI.

The deployment command:

1. creates or selects an azd environment;
2. generates a 256-bit bearer token if needed;
3. runs `azd up`;
4. verifies HTTP 401 and authenticated MCP protocol/tool inventory;
5. creates or updates two Foundry remote-tool connections through Azure CLI;
6. writes `example1.shared.env` and `example2.shared.env`.

The token remains in the local azd environment, Container App secret, and
Foundry Project connections. It is not written to either Agent config.

## Change or extend the MCP

Do not edit `config/generated/` or `state/`; they are runtime artifacts.
Change the source package, its Agent contract, and its tests together.

### Change existing business behavior

| Concern | Example 1 | Example 2 |
| --- | --- | --- |
| Tool registration and wire schema | `app/shared_mcp/finance_handoff/server.py` | `app/shared_mcp/finance_otp_officer/server.py` |
| Business state transitions | `app/shared_mcp/finance_handoff/service.py` | `app/shared_mcp/finance_otp_officer/service.py` |
| Domain and persistence | `domain.py`, `store.py` | `domain.py`, `store.py`, `auth.py` |
| Fixture loading | `data.py`, `data/finance_handoff/` | `data.py`, `data/finance_otp_officer/` |
| Agent tool contract | `../samples/example1_finance_with_handoff/agent.json` | `../samples/example2_finance_with_OTP_and_Officer_Search/agent.json` |

When changing a tool:

1. Preserve the existing name and schema unless the corresponding
   `agent.json` is changed in the same update.
2. Implement the business behavior in the service/domain layer; keep the
   FastMCP function focused on validation and transport mapping.
3. Update fictional fixtures only when the new behavior requires them.
4. Update the Agent's `allowed_tools` and instructions when the Agent must call
   a new or renamed tool.
5. Add or update tests under `tests/`. The inventory test reads both real
   `agent.json` files, so an Agent cannot reference a missing route tool.

### Add another isolated MCP route

Create a package under `app/shared_mcp/`, then:

1. expose a `register(mcp)` function like the existing `pack.py` files;
2. add a route and registration call in `app/shared_mcp/server.py`;
3. add data and state environment variables to the native and Container Apps
   configuration when required;
4. add the new Agent definition and generated-config mapping;
5. extend `configure-agent.sh`, `e2e-local.sh`, and `deploy.sh`;
6. add authenticated `initialize`/`tools/list` contract validation for the
   route before declaring it ready.

Do not merge tool inventories merely because they share one image. Keep
separate routes whenever same-named tools have different schemas or state.

### Validate a change

```bash
# Native Python contracts.
cd VoiceAgent
PYTHONPATH=shared_mcp/app shared_mcp/.venv/bin/python \
  -m unittest discover -s shared_mcp/tests -v

# Optional isolated container-image test and packaging command.
cd shared_mcp
./scripts/package.sh

# Full local Foundry closure.
./scripts/e2e-local.sh
```

For a running local service, the UI's **Test MCP** performs an authenticated
handshake and verifies the template's required tool inventory.

## Select shared MCP from an Agent

For the local named-tunnel runtime, each sample's `.env` needs only one MCP
selector:

```dotenv
# example1
VOICE_AGENT_MCP_CONFIG=../../shared_mcp/config/generated/example1.local.env
```

```dotenv
# example2
VOICE_AGENT_MCP_CONFIG=../../shared_mcp/config/generated/example2.local.env
```

`VOICE_AGENT_MCP_CONFIG` overrides MCP URL and connection values from the
sample `.env`. Process-level `VOICE_AGENT_MCP_SERVER_URL` and
`VOICE_AGENT_MCP_CONNECTION_ID` still have highest precedence for CI or
one-off tests.

The Azure Container Apps deployment writes `example1.shared.env` and
`example2.shared.env` instead. Select those files only when switching from the
local named tunnel to the deployed service.

After an Azure deployment, recreate only the Foundry connections and generated
shared config from the currently selected azd environment:

```bash
AZURE_AI_PROJECT_ENDPOINT="https://.../api/projects/..." \
  ./scripts/configure-agent.sh
```

For local Dev Tunnel config, rerun `e2e-local.sh`; the standalone command does
not create or host a local tunnel.

## Architecture and persistence

The service preserves the existing Finance business state machines and tool
schemas. One server hosts both packs but isolates their MCP inventories by
route, preventing same-named tools from overwriting one another.

Azure deployment intentionally fixes `minReplicas` and `maxReplicas` at one.
The sample stores call, OTP, and fictional elevator-ticket state on that
replica's filesystem, which is enough for short demonstrations but is not
durable across a revision or restart. A production implementation must use a
customer-owned durable store, replace the fake integrations, rotate
credentials, and define its own network and retention policies.

## Debug this layer

Use the shared [`debug-local-session` Skill](../skills/debug-local-session/)
when a Project connection, authenticated probe, tool inventory, tool call, or
post-tool response fails:

```bash
cd VoiceAgent
./scripts/manage-local-mcp-and-ui.sh status
python skills/debug-local-session/scripts/analyze_session.py <session-id>
```

The Skill verifies the join among the selected Project, published Agent
version, `project_connection_id`, generated route config, active MCP deployment,
and business tool call ID.
