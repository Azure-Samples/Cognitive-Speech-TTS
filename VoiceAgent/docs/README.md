# Voice Agent Finance examples

## Conclusion

This directory is the ordered documentation entry point for the two
self-contained Finance Voice Agent examples:

1. [Set up the subscription and Foundry Project](./01_setup_subscription.md).
2. [Configure, start, deploy, or change the shared MCP](./02_mcp_settings.md).
3. [Start and run the samples and local UI](./03_run_samples.md).
4. [Debug a local UI session](./04_debug_session.md).

The scenario-specific source of truth remains with each example:

- [Example 1: Finance with Handoff](../samples/example1_finance_with_handoff/README.md)
- [Example 2: Finance with OTP and Officer Search](../samples/example2_finance_with_OTP_and_Officer_Search/README.md)
- [Local UI](../samples/local_UI/README.md)

This `README.md` owns only the architecture and navigation. The numbered
documents own procedures.

## Setup and troubleshooting map

| Need or failure | Source of truth |
| --- | --- |
| Select a subscription, find an existing Project endpoint, create a Project, or verify `gpt-realtime` mode and region support | [01: Subscription and Foundry Project](./01_setup_subscription.md) |
| Build through a Python package mirror, install or authenticate Dev Tunnel, create MCP connections, or diagnose missing `*.local.env` files | [02: MCP settings and E2E](./02_mcp_settings.md) |
| Install/check the two sample virtual environments, prepare the Local UI environment, or create `.env` files | [`setup-local-finance-examples.sh`](../scripts/setup-local-finance-examples.sh) and [03: Run samples and Local UI](./03_run_samples.md) |
| Start, restart, stop, or inspect the local MCP + Dev Tunnel + Local UI processes | [`manage-local-finance-mcp-and-ui.sh`](../scripts/manage-local-finance-mcp-and-ui.sh) and [03: Run samples and Local UI](./03_run_samples.md) |
| Diagnose a session that reached the Voice WebSocket | [04: Debug a local UI session](./04_debug_session.md) and [`skills/debug-local-session/`](../skills/debug-local-session/) |

The local MCP E2E path uses the identity from `az login` for Project discovery
and connection creation. It does not publish Agents and does not require
`azd auth login`. Each sample or the local UI publishes its selected Agent
after MCP readiness. Azure Developer CLI remains a prerequisite only for the
Azure Container Apps deployment path.

## Architecture

The browser and sample CLIs do not execute MCP tools themselves. They publish
or invoke a Voice Agent in Microsoft Foundry; Foundry calls the public MCP URL
using a credential stored in a Project connection.

```text
                              management and publication
  sample.py or local UI  ------------------------------------+
       |                                                      |
       | Voice WebSocket                                      v
       +------------------------------------------> Foundry Voice Agent
                                                          |
                                                          | server_url
                                                          | project_connection_id
                                                          v
                                                Foundry RemoteTool connection
                                                          |
                                                          | Authorization: Bearer ...
                                                          v
                            +---------------- public HTTPS MCP host ----------------+
                            |                                                       |
                 local: named Dev Tunnel                         Azure: Container App
                            |                                                       |
                            +------------------------+------------------------------+
                                                     |
                                                     v
                                      one shared MCP container/image
                                                     |
                         +---------------------------+---------------------------+
                         |                                                       |
             /mcp/finance-handoff                            /mcp/finance-otp-officer
                         |                                                       |
             Finance handoff business pack                      OTP/officer business pack
```

One Docker image contains both Finance MCP implementations. The routes remain
separate because they contain some same-named tools with different schemas.
This is not one image per tool or per route.

## Components and ownership

| Component | Owns | Does not own |
| --- | --- | --- |
| [`shared_mcp/`](../shared_mcp/) | Both Finance MCP implementations, fictional data, auth, Docker image, local hosting, Dev Tunnel, Azure Container Apps IaC, protocol probes, and Foundry connection configuration | Foundry Project creation, model deployment, Agent publication |
| [`example1_finance_with_handoff/`](../samples/example1_finance_with_handoff/) | Example 1 Agent definition, handoff graph, CLI publication/readback/runtime validation | MCP hosting |
| [`example2_finance_with_OTP_and_Officer_Search/`](../samples/example2_finance_with_OTP_and_Officer_Search/) | Example 2 Agent definition, flat tool workflow, CLI publication/readback/runtime validation | MCP hosting |
| [`local_UI/`](../samples/local_UI/) | Project and Agent selection, template publication, microphone/text sessions, handoff visualization, latency, MCP activity, and local session recording | MCP business execution |
| [`voice_agent_sdk_common.py`](../samples/voice_agent_sdk_common.py) | Shared config materialization, Agent publication/readback, and text Voice WebSocket runtime | Browser UI and MCP transport |

## Artifact flow

There are three distinct stages. Keeping them separate prevents credentials or
environment-specific URLs from leaking into the committed Agent definitions.

### 1. Source

- Each example owns a portable `agent.json`.
- MCP `server_url` and `project_connection_id` are intentionally empty.
- [`shared_mcp/`](../shared_mcp/) contains both business implementations and
  fictional fixtures.

### 2. MCP hosting and connection configuration

Choose one:

- Local development: `VoiceAgent/shared_mcp/scripts/e2e-local.sh`
- Customer-owned Azure hosting: `VoiceAgent/shared_mcp/scripts/deploy.sh`

These workflows create route-specific generated config files containing only:

```dotenv
VOICE_AGENT_MCP_SERVER_URL=https://...
VOICE_AGENT_MCP_CONNECTION_ID=...
```

The bearer token remains in ignored local state or an Azure Container App
secret and in the Foundry Project connection. It is not written to
`agent.json` or returned to the browser.

### 3. Agent publication and session runtime

The CLI or local UI reads a generated config, injects the route URL and
connection name into every MCP declaration, publishes an immutable Agent
version, and verifies readback. During a session, Foundry uses the connection
credential to call the selected MCP route.

## Fastest complete local workflow

For the first run, complete these in order:

1. Select the exact subscription and discover or create the Project endpoint
  in [01: Subscription and Foundry Project](./01_setup_subscription.md).
2. Create both Finance virtual environments, the Local UI environment, and
  all three `.env` files in
  [03: Start and run the samples](./03_run_samples.md).
3. Install and authenticate Dev Tunnel as described in
  [02: MCP settings and E2E](./02_mcp_settings.md).
4. Start E2E and wait for its final success lines:

```bash
cd VoiceAgent
./scripts/manage-local-finance-mcp-and-ui.sh restart
```

The command safely stops stale MCP, Dev Tunnel, and Local UI processes owned
by this repository; starts a fresh MCP E2E and Local UI; then verifies both
template MCP probes. It prints the Local UI URL when the full stack is ready.

Use the same script for lifecycle operations:

```bash
./scripts/manage-local-finance-mcp-and-ui.sh status
./scripts/manage-local-finance-mcp-and-ui.sh stop
```

The local workflow is fully ready only when all three layers pass:

1. MCP: `e2e-local.sh` prints `e2e_local=passed` and
  `local_runtime=ready`, then remains running.
2. Sample CLI: each scenario's `sample.py publish` and `sample.py check`
  report matching requested/readback fingerprints.
3. Local UI: **Reload** clears any pre-E2E catalog cache, **Test MCP** reports
  HTTP 200 for the selected template, and **Try it now** publishes a `gft-`
  Agent version.

## Local and Azure deployment boundaries

`e2e-local.sh` is the MCP local closed loop: it packages and starts the MCP
container, hosts it through a named Dev Tunnel, verifies both route contracts,
creates connections, writes generated config, and remains running. Agent
publication belongs to each sample CLI or the local UI.

`deploy.sh` deploys the shared MCP image to Azure Container Apps and creates
the two Foundry connections and generated configs. It does not create the
Foundry Project, deploy the realtime model, or publish the two Agents. Publish
from the example CLI after deployment. The checked-in local UI template
catalog intentionally targets the local E2E token/config workflow; using a
different MCP deployment requires a custom template config with a server-side
token file so the UI can authenticate and upsert the selected Project
connection.

Both paths validate authenticated MCP `initialize`, `tools/list`, and the
required tool inventory before declaring the MCP ready.

## Sample-only limitations

- The loan-officer name matcher deliberately returns a random available
  fictional officer; it is not the production phonetic matcher.
- OTP values and committed records are fictional test data.
- MCP state uses a local Docker volume for the local workflow and ephemeral
  single-replica storage in the Azure sample deployment.
- Dev Tunnel is development ingress, not a production network design.
- Session recordings can contain transcript and tool data and have no
  automatic retention policy.

Use the numbered documents for procedures and troubleshooting rather than
extending this overview with component-specific detail.
