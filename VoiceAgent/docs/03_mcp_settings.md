# 03 - MCP settings, deployment, and development

## Conclusion

The [`VoiceAgent/shared_mcp/`](../shared_mcp/) directory contains the
customer-owned MCP implementation used by both Finance Voice Agent samples.
Run one command to build it locally or one command to deploy it to Azure
Container Apps and create the two Foundry Project connections required by the
Agents.

Use the [architecture and documentation index](./README.md) for the system
overview. Use [02: Start and run the samples](./02_run_samples.md) when
running MCP, Agent publication, and UI in sequence.

The container exposes two separate Streamable HTTP routes because the samples
have overlapping tool names with different schemas:

| Sample | MCP route | Generated config |
| --- | --- | --- |
| `example1_finance_with_handoff` | `/mcp/finance-handoff` | `config/generated/example1.local.env` |
| `example2_finance_with_OTP_and_Officer_Search` | `/mcp/finance-otp-officer` | `config/generated/example2.local.env` |

Both routes require the same bearer token. `/healthz` is public and contains
only liveness status.

## Choose the command by goal

| Goal | Command | Port / reachability | What remains running |
| --- | --- | --- | --- |
| Build the image and run container tests | `./scripts/package.sh` | No listener | Nothing |
| Exercise MCP directly on one machine | `./scripts/run-local.sh` | `127.0.0.1:8000`; not reachable by Foundry | Docker Compose service |
| Run the complete local Foundry path | `./scripts/e2e-local.sh` | Local `18003` plus a public named Dev Tunnel | Container and tunnel host |
| Deploy customer-owned Azure hosting | `AZURE_AI_PROJECT_ENDPOINT=... ./scripts/deploy.sh` | Azure Container App HTTPS URL | Azure resources |

Use port `8000` only for direct local protocol development. Use the `18003`
E2E path when a published Foundry Agent must call the local MCP.

## Important sample limitation

The name search in
`app/shared_mcp/finance_otp_officer/directory.py` is intentionally a **fake
implementation**. Production name search uses a large phonetic index and
recognizer-aware matching that is too complex and heavy for this portable
sample. Here, every non-empty name query returns one random available officer
from the committed fictional fixture.

Do not use this fake matcher, the fictional OTP, or the filesystem state store
for real customer data.

## Package locally

Prerequisites:

- Docker with `docker compose`
- Bash and OpenSSL

Build the runtime image and run all MCP tests inside the image:

```bash
cd /path/to/Cognitive-Speech-TTS/VoiceAgent/shared_mcp
./scripts/package.sh
```

The resulting image is `voice-agent-shared-mcp:local`. Override it with
`SHARED_MCP_IMAGE`.

## Run locally

```bash
./scripts/run-local.sh
```

The command generates a private `.env.local` bearer token on first use and
starts the service at `http://127.0.0.1:8000`.

Useful endpoints:

```text
GET  http://127.0.0.1:8000/healthz
POST http://127.0.0.1:8000/mcp/finance-handoff
POST http://127.0.0.1:8000/mcp/finance-otp-officer
```

Foundry cannot call a laptop's `localhost`. Use the local E2E command below to
host this same local container through a persistent named Dev Tunnel. Its
public HTTPS URL remains stable across runs while the tunnel ID and port stay
the same.

## Deploy and configure both Agents

Prerequisites:

- Azure CLI authenticated with `az login`
- Azure Developer CLI authenticated with `azd auth login`
- Docker
- Permission to create a resource group, Container Registry, Log Analytics,
  Container Apps resources, and an `AcrPull` role assignment
- Permission to create connections in the target Foundry Project

Run:

```bash
export AZURE_AI_PROJECT_ENDPOINT="https://<account>.services.ai.azure.com/api/projects/<project>"
cd /path/to/Cognitive-Speech-TTS/VoiceAgent/shared_mcp
./scripts/deploy.sh
```

The first run creates a unique azd environment name and may ask for the Azure
subscription and location. Later runs reuse the selected environment. To make
it non-interactive, set `AZURE_SUBSCRIPTION_ID`, `AZURE_LOCATION`, and
optionally `AZURE_ENV_NAME` before running the command.

The deployment command:

1. creates or selects an azd environment;
2. generates a 256-bit bearer token if the environment does not already have
   one;
3. runs `azd up`;
4. confirms that unauthenticated MCP access returns HTTP 401 on both routes;
5. uses the bearer token to run MCP `initialize` and `tools/list` on both
   routes and verifies every tool allowed by the corresponding `agent.json`;
6. creates or updates two Foundry remote-tool connections;
7. writes two non-secret Agent config files under `config/generated/`.

The token remains in the local azd environment, the Container App secret, and
the Foundry Project connections. It is not written to either Agent config.

## Run the complete local MCP E2E

The repeatable E2E packages the image, starts the fixed
`voice-agent-shared-mcp-local` container on port `18003`, publishes it through
a persistent named Dev Tunnel protected by the MCP bearer token, creates
stable Foundry connections, publishes both `*-local-e2e` Agents, and runs both
Voice WebSocket smoke tests:

```bash
./scripts/e2e-local.sh
```

The script requires both sample `.env` files and their Python dependencies,
plus authenticated `azd` and `devtunnel` CLIs. It verifies:

- public health and unauthenticated HTTP 401 behavior;
- example1 handoff and MCP-call evidence;
- example2 MCP tool discovery and OTP-call evidence;
- published definition/readback fingerprints.

The first run creates and records the tunnel ID in
`state/local/devtunnel-id`; later runs reuse that tunnel, its fixed URL, the
token in `state/local/token`, and the two connection names. Evidence is written
under `state/e2e/<UTC-run-id>/`.

The container and tunnel remain active after the tests so both published
Agents stay runnable. Press `Ctrl+C` to stop hosting them. The named tunnel
itself is retained, so the next run restores the same address. For CI, set
`SHARED_MCP_E2E_KEEP_RUNNING=0`; the script then exits immediately and cleans
up its local container and tunnel host process. The isolated Foundry Agents,
connections, and named tunnel are retained, but the MCP endpoint is naturally
unavailable while no local host process is running.

The fixed local container mounts the named Docker volume
`voice-agent-shared-mcp-state` at `/app/state`. Active call IDs and OTP session
state therefore survive a container restart. Removing that volume invalidates
in-progress calls; start a new Voice Agent session afterward.

The script also writes the current non-secret route and connection mappings:

```text
config/generated/example1.local.env
config/generated/example2.local.env
```

It uses those files itself when publishing. While the E2E script is still
running, you can publish or invoke either sample from another terminal:

```bash
cd ../samples/example1_finance_with_handoff
VOICE_AGENT_NAME=finance-example-local-e2e \
VOICE_AGENT_MCP_CONFIG=../../shared_mcp/config/generated/example1.local.env \
  python sample.py publish
```

```bash
cd ../samples/example2_finance_with_OTP_and_Officer_Search
VOICE_AGENT_NAME=finance-otp-officer-local-e2e \
VOICE_AGENT_MCP_CONFIG=../../shared_mcp/config/generated/example2.local.env \
  python sample.py publish
```

The config files contain only the MCP URL and Foundry connection name. The
bearer token stays in the Foundry connection and local E2E state.

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
3. add data and state environment variables to the Docker and Container Apps
   configuration when required;
4. add the new Agent definition and generated-config mapping;
5. extend `configure-agent.sh`, `e2e-local.sh`, and `deploy.sh`;
6. add authenticated `initialize`/`tools/list` contract validation for the
   route before declaring it ready.

Do not merge tool inventories merely because they share one image. Keep
separate routes whenever same-named tools have different schemas or state.

### Validate a change

```bash
# Python contracts.
cd VoiceAgent
PYTHONPATH=shared_mcp/app \
  python -m unittest discover -s shared_mcp/tests -v

# Docker test target and runtime image.
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

To recreate only the Foundry connections and generated config without
redeploying:

```bash
AZURE_AI_PROJECT_ENDPOINT="https://.../api/projects/..." \
  ./scripts/configure-agent.sh
```

## Architecture and persistence

The service preserves the existing Finance business state machines and tool
schemas. One container hosts both packs but isolates their MCP inventories by
route, preventing same-named tools from overwriting one another.

Azure deployment intentionally fixes `minReplicas` and `maxReplicas` at one.
The sample stores call and OTP state on that replica's filesystem, which is
enough for short demonstrations but is not durable across a revision or
restart. A production implementation must use a customer-owned durable store,
replace the fake name matcher, rotate credentials, and define its own network
and retention policies.
