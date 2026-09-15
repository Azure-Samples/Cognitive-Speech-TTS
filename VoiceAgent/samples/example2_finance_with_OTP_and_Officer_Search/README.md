# Finance with OTP and Officer Search - vNext SDK sample

## Conclusion

This sample publishes a customer-neutral, flat, MCP-only Finance Voice Agent
through the preview `azure-ai-projects` unified Agents API and runs a text-only
Voice WebSocket smoke test. It uses managed `gpt-realtime`, American English,
and business tools for OTP, loan-offer discussion, explicit interest,
loan-officer selection, callback, and call disposition.

Because the definition has no handoff graph, publication constructs
`VoiceAgentDefinition(mapping)` before calling
`AIProjectClient.agents.create_version(...)`.

The committed `agent.json` is a self-contained wire definition with matching
MCP tool contracts. The internal authoring compiler is not required at
runtime.

The currently deployed compatibility route is `/mcp/umw-v3`; it contains the
pricing, OTP, interest, and officer-search tools required by this generic
sample. A neutral route alias should replace it before external distribution.

## Prerequisites

- Python 3.10 or later and Git.
- Access to a Microsoft Foundry Project with a compatible realtime model.
- A Project connection for the Finance OTP and officer-search MCP server.
- A local Azure identity with permission to manage and invoke Agents.

If you have only a new Azure subscription, complete
[Set up a Microsoft Foundry subscription](../../setup_subscription.md)
before configuring this sample.

After that shared step, this README is the source of truth for this scenario's
MCP connection, `.env`, SDK publication, readback, and runtime validation.

Do not put the MCP credential in this directory. Store it in the Foundry
Project connection.

## Create the Project connection

Obtain the Finance OTP/officer-search MCP HTTPS endpoint and a scoped,
revocable bearer token from the service owner through an approved secure
channel.

In the newly created Foundry Project:

1. Open **Operate** > **Admin** and select the Project.
2. Add a remote-tool/MCP connection.
3. Set the target to the OTP/officer-search MCP HTTPS endpoint.
4. Select custom-key authentication.
5. Add key `Authorization` with value `****** scoped-token>`.
6. Save the connection and record its Project connection name.

The connection must belong to the same Project identified by
`AZURE_AI_PROJECT_ENDPOINT`. Confirm that the endpoint returns HTTP 401 without
the bearer token before storing the credential.

The local template dashboard can also create a unique Project connection when
you select this template and choose **Try it now**. It accepts the scoped token
once in a password field and does not write it into `agent.json`.

## Configure

```bash
cd /path/to/Cognitive-Speech-TTS/VoiceAgent/samples/example2_finance_with_OTP_and_Officer_Search
cp .env.example .env
```

Set the Project endpoint, isolated Agent name, MCP server URL, Project
connection name, and model in `.env`.

Use the Project endpoint created by the subscription setup guide and the
connection name created above. Do not copy either value from another
subscription.

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

The `publish` command loads `agent.json`, injects environment-specific model
and MCP references, publishes and enables an immutable version, and verifies
its kind, model, and MCP connection IDs on readback.

## Run

Validate session readiness and the opening response:

```bash
python sample.py connect
```

Run the caller request and provide the synthetic test access code configured
by the target MCP environment:

```bash
python sample.py run \
  --message "Hello, I need to reach my loan officer." \
  --message "12345007" \
  --expect-mcp \
  --evidence-file validation/finance-otp-officer-search-smoke.json
```

`12345007` is a reserved fictional test code. Never replace it in
documentation with a real customer credential.

The client prints turn indexes, not message contents. It does not capture a
microphone or play audio; it validates the published Voice Agent, MCP, and
model response path over the production Voice WebSocket protocol.

`sample.py` is the single Python entry point for publication, readback, session
connection, and text turns. `agent.json` remains separate because the local
template dashboard also consumes that definition directly.

## Boundaries

- The sample does not create the Foundry Project or deploy the model.
- Project connection provisioning is a management-plane prerequisite.
- The Finance OTP and officer-search MCP backend is remote and is not included.
- Re-running publish creates another immutable Agent version.
- Cleanup is intentionally manual to avoid deleting an unrelated Agent.
