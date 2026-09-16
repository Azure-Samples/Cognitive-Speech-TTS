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

After the one-time prerequisites in
[03: Start and run the samples](./03_run_samples.md):

```bash
cd VoiceAgent/shared_mcp
./scripts/e2e-local.sh
```

Leave that command running. In another terminal:

```bash
cd VoiceAgent/samples/local_UI
cp .env.example .env
# Set AZURE_AI_PROJECT_ENDPOINT and, if needed, AZURE_CREDENTIAL_MODE=cli.
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py --host 127.0.0.1 --port 8097
```

Open `http://localhost:8097`, or forward remote port `8097` from the same VS
Code Remote-SSH window. In **Templates**, choose either Finance example and
select **Try it now**.

## Local and Azure deployment boundaries

`e2e-local.sh` is the full local closed loop: it packages and starts the MCP
container, hosts it through a named Dev Tunnel, creates connections, publishes
both Agents, and runs smoke tests.

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
