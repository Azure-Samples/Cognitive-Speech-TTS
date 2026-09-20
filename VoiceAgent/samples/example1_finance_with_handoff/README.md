# Finance Example Voice Agent - Projects SDK sample

Start with the [architecture and documentation index](../../docs/README.md).
For the complete local MCP serving, publication, and UI workflow, use
[03: Start and run the samples](../../docs/03_run_samples.md).

## Conclusion

This sample publishes two runtime variants of one shared Finance workflow
through the `azure-ai-projects` unified Agents API:

| Variant | Model pipeline | Transcription | Voice |
| --- | --- | --- | --- |
| `realtime` | `gpt-realtime-2.1` | `whisper-1` | `en-IN-Diya:DragonHDLatestNeural` |
| `cascade-luna` | `gpt-5.6-luna` | `azure-speech` | `en-IN-Diya:DragonHDLatestNeural` |

The Portal shows these as two separate cards. Publish either Agent individually with
`--variant realtime` or `--variant cascade-luna`, or publish both with `--variant all`.

Both variants compile from `agent.base.json`, share the same 13-node, 24-edge
handoff graph, prompts, edge latency-cover messages, and MCP tool scopes, and
publish under distinct Agent names. Because `handoff` is not in the SDK 2.7.0 typed
`VoiceAgentDefinition`, publication uses the SDK's raw-body
`create_version` overload and verifies that the graph survives readback.

The realtime client uses `azure-identity` plus `websockets` directly rather than
the SDK's high-level Voice Agent connector.

`agent.base.json` is the customer-neutral source of truth.
`profiles/realtime.json` and `profiles/cascade-luna.json` contain only runtime
overrides. `build_variants.py` generates the two portable wire definitions;
`agent.json` remains a compatibility alias for Realtime. The customer-owned
MCP implementation is included in `../../shared_mcp`.

## When to use this example

Use this example to validate a multi-stage Agent: it has 13 nodes, 24 handoff
edges, stage-specific instructions, and restricted MCP tool access per node.
The portal displays both the authored graph and live handoff transitions.

Use [Example 2](../example2_finance_with_OTP_and_Officer_Search/README.md)
instead when the goal is a smaller flat MCP-only Agent without handoff
topology. Both examples use the same shared MCP service, but this example targets
`/mcp/finance-handoff`.

## Prerequisites

- Python 3.10 or later and Git.
- Access to a Microsoft Foundry Project with a compatible realtime model.
- Permission to create a Project connection and either host the included MCP
  locally through Dev Tunnel or deploy it to Azure Container Apps.
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
`../../docs/02_mcp_settings.md` for local packaging and deployment details.

## Configure

```bash
cd /path/to/Cognitive-Speech-TTS/VoiceAgent/samples/example1_finance_with_handoff
cp .env.example .env
```

Set the Project endpoint and `VOICE_AGENT_MCP_CONFIG` in `.env`. Agent names,
models, transcription, and voices come from the selected variant. The local
E2E command writes the default MCP config at:

```dotenv
VOICE_AGENT_MCP_CONFIG=../../shared_mcp/config/generated/example1.local.env
```

Use the Project endpoint created by the subscription setup guide. The selected
MCP config must have been generated for that same Project.

Both portable definitions use `model_type: managed`. A process-level
`VOICE_AGENT_MODEL` may intentionally override the selected CLI variant, but
the sample `.env` does not override either profile. Portal Template publication
locks each card to its authored runtime so both variants remain distinct.

`AZURE_CREDENTIAL_MODE=default` uses `DefaultAzureCredential`. Set it to `cli`
only when local validation must use the identity selected by `az login`.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

The dependency requires `azure-ai-projects>=2.7.0`
from PyPI. No Azure SDK source checkout is required.

## Publish and verify

```bash
python build_variants.py --check
python sample.py publish --variant realtime
python sample.py publish --variant cascade-luna
python sample.py check --variant all
```

Publish both variants in one command when desired:

```bash
python sample.py publish --variant all
```

Each `publish` command:

1. loads the selected generated Agent document;
2. injects environment-specific model and MCP references;
3. calls `AIProjectClient.agents.create_version(...)` with a raw body;
4. enables the Agent;
5. reads back the exact immutable version;
6. verifies `kind`, model, MCP connection IDs, and the handoff graph.

## Run

Validate session readiness and the opening response:

```bash
python sample.py connect --variant realtime
python sample.py connect --variant cascade-luna
```

Handoff is model-decided and is not guaranteed during the opening response.
Send a non-greeting turn to require both handoff and MCP-call evidence:

```bash
python sample.py run --variant realtime \
  --message "Hello, who is calling?" \
  --expect-handoff \
  --expect-mcp \
  --evidence-file validation/finance-example-smoke.json
```

The client prints turn indexes, not message contents. It does not capture a
microphone or play audio; it validates the published Voice Agent, handoff, MCP,
and model response path over the production Voice WebSocket protocol.

`sample.py` is the single Python entry point for publication, readback, session
connection, and text turns. The Portal reads `agent.realtime.json` and
`agent.cascade-luna.json` as two separate Template cards.

## Update the shared workflow

Edit only `agent.base.json` for workflow, prompt, edge, or tool-scope changes.
Edit only the matching file under `profiles/` for model/audio changes, then run:

```bash
python build_variants.py
python build_variants.py --check
```

Commit the base, profiles, and regenerated Agent documents together. The check
fails when either generated variant or the compatibility `agent.json` is stale.
The builder also rejects handoff tools outside the Foundry publication types
`function`, `mcp`, `system`, and `toolbox`. In particular, the shared base uses
`{"type": "system", "name": "end_conversation"}`; the
`type: end_conversation` shape is only for direct local Voice Live injection
and must not be published through the Projects API.

## Debug

Use the shared [`debug-local-session` Skill](../../skills/debug-local-session/)
for Project/model publication, handoff, MCP, portal, or recorded-session
failures:

```bash
cd VoiceAgent
python skills/debug-local-session/scripts/analyze_session.py --list
python skills/debug-local-session/scripts/analyze_session.py <session-id>
```

The Skill knows this example targets `/mcp/finance-handoff` and requires
handoff, MCP, and post-tool response evidence.

## Boundaries

- The sample does not create the Foundry Project or deploy the model.
- Project connection provisioning is a management-plane prerequisite.
- The Finance MCP backend is included under `../../shared_mcp`; deployment remains
  a separate customer-owned step.
- The included filesystem state store is for a single-replica sample, not
  production durability.
- The Realtime and Cascade Luna definitions pin their own managed model IDs.
- Re-running publish creates another immutable Agent version.
- Cleanup is intentionally manual to avoid deleting an unrelated Agent.
