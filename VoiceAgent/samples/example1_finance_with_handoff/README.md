# Finance Example Voice Agent - vNext SDK sample

Start with the [architecture and documentation index](../../docs/README.md).
For the complete local MCP serving, publication, and UI workflow, use
[02: Start and run the samples](../../docs/02_run_samples.md).

## Conclusion

This sample publishes a generic Finance English Realtime profile through
the preview `azure-ai-projects` unified Agents API and runs a text-only Voice
WebSocket smoke test. The profile uses managed `gpt-realtime` with a 13-node,
24-edge `handoff` graph. Because `handoff` is not in the pinned typed
`VoiceAgentDefinition`, publication uses the SDK's raw-body `create_version`
overload and verifies that the graph survives readback.

The realtime client uses `azure-identity` plus `websockets`. The pinned SDK has
no public high-level Voice Agent realtime connector.

The committed `agent.json` is a self-contained, customer-neutral wire
definition with the matching Finance MCP tool contracts. The customer-owned
implementation is included in `../../shared_mcp`; the internal authoring compiler
and an internally hosted MCP service are not required at runtime.

## When to use this example

Use this example to validate a multi-stage Agent: it has 13 nodes, 24 handoff
edges, stage-specific instructions, and restricted MCP tool access per node.
The local UI displays both the authored graph and live handoff transitions.

Use [Example 2](../example2_finance_with_OTP_and_Officer_Search/README.md)
instead when the goal is a smaller flat MCP-only Agent without handoff
topology. Both examples use the same Docker image, but this example targets
`/mcp/finance-handoff`.

## Prerequisites

- Python 3.10 or later and Git.
- Access to a Microsoft Foundry Project with a compatible realtime model.
- Permission to deploy the included shared MCP container and create a Project
  connection.
- A local Azure identity with permission to manage and invoke Agents.

If you have only a new Azure subscription, complete
[Set up a Microsoft Foundry subscription](../../docs/01_setup_subscription.md)
before configuring this sample.

After that shared step, this README is the source of truth for this scenario's
MCP connection, `.env`, SDK publication, readback, and runtime validation.

## Deploy the included MCP service

From `../../shared_mcp`, run:

```bash
export AZURE_AI_PROJECT_ENDPOINT="https://<account>.services.ai.azure.com/api/projects/<project>"
./scripts/deploy.sh
```

This deploys the customer-owned container and creates the route-specific
Foundry connection. The bearer token is stored in the Container App and the
Project connection, never in `agent.json` or this sample directory. See
`../../docs/03_mcp_settings.md` for local packaging and deployment details.

## Configure

```bash
cd /path/to/Cognitive-Speech-TTS/VoiceAgent/samples/example1_finance_with_handoff
cp .env.example .env
```

Set the Project endpoint, isolated Agent name, model, and
`VOICE_AGENT_MCP_CONFIG` in `.env`. The local E2E command writes the default
config at:

```dotenv
VOICE_AGENT_MCP_CONFIG=../../shared_mcp/config/generated/example1.local.env
```

Use the Project endpoint created by the subscription setup guide. The selected
MCP config must have been generated for that same Project.

`AZURE_CREDENTIAL_MODE=default` uses `DefaultAzureCredential`. Set it to `cli`
only when local validation must use the identity selected by `az login`.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

The dependency is pinned to the exact vNext SDK source commit used to author
this sample. It is not evidence that the same Voice Agent surface is available
from a released PyPI wheel.

## Publish and verify

```bash
python sample.py publish
python sample.py check
```

The `publish` command:

1. loads `agent.json`;
2. injects environment-specific model and MCP references;
3. calls `AIProjectClient.agents.create_version(...)` with a raw body;
4. enables the Agent;
5. reads back the exact immutable version;
6. verifies `kind`, model, MCP connection IDs, and the handoff graph.

## Run

Validate session readiness and the opening response:

```bash
python sample.py connect
```

Handoff is model-decided and is not guaranteed during the opening response.
Send a non-greeting turn to require both handoff and MCP-call evidence:

```bash
python sample.py run \
  --message "Hello, who is calling?" \
  --expect-handoff \
  --expect-mcp \
  --evidence-file validation/finance-example-smoke.json
```

The client prints turn indexes, not message contents. It does not capture a
microphone or play audio; it validates the published Voice Agent, handoff, MCP,
and model response path over the production Voice WebSocket protocol.

`sample.py` is the single Python entry point for publication, readback, session
connection, and text turns. `agent.json` remains separate because the local
template dashboard also consumes that definition directly.

## Boundaries

- The sample does not create the Foundry Project or deploy the model.
- Project connection provisioning is a management-plane prerequisite.
- The Finance MCP backend is included under `../../shared_mcp`; deployment remains
  a separate customer-owned step.
- The included filesystem state store is for a single-replica sample, not
  production durability.
- The committed definition intentionally pins managed `gpt-realtime`, even if
  another Finance publication profile uses a cascaded model.
- Re-running publish creates another immutable Agent version.
- Cleanup is intentionally manual to avoid deleting an unrelated Agent.
