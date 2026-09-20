# Example 3: Elevator Service with Safety, Zendesk, and Handoff

## Conclusion

This sample publishes a fictional inbound elevator-service Voice Agent through
the preview `azure-ai-projects` unified Agents API. It demonstrates:

- a 9-node, 17-edge handoff graph;
- a deterministic five-question safety check;
- persistent mock Zendesk create and exact-ID status-query contracts;
- caller-visible ticket review and explicit confirmation before creation;
- caller-safe ticket responses;
- browser human-follow-up fallback;
- runtime-owned telephony transfer when the hosting platform injects
  `transfer_call`.

The committed `agent.json` is portable. It contains no MCP URL, Project
connection ID, bearer token, subscription ID, tenant ID, or real customer data.
The Portal Template uses this repository's `shared_mcp` runtime. The Portal
creates or updates the required RemoteTool connection in the customer's
selected Foundry Project; it does not rely on a pre-existing connection.

## When to use this example

Use this example to study an inbound field-service workflow where safety,
external writes, status reads, and human escalation require different tool
scopes.

Use Example 1 for a larger outbound Finance handoff graph. Use Example 2 for a
flat MCP-only Finance Agent.

## Workflow

```text
open_call
  -> intent_router
     -> report_issue
        -> next_request
        -> human_handoff
     -> query_issue
        -> next_request
        -> human_handoff
     -> human_handoff
  -> finalize / human_finalize
  -> end
```

The report path does not create a Zendesk ticket immediately after collecting
an address. It first asks:

```text
Please confirm: I will create a Zendesk ticket for [issue summary]
at [address], postal code [postal code]. Is that correct?
```

Only an explicit approval permits `mock_zendesk_create_ticket` with
`caller_confirmed=true`.

The query path requires only the exact Zendesk ticket ID. It deliberately does
not ask for a ZIP code that the backend does not use for authorization.

## MCP contract

The Agent declares these seven business tools:

```text
start_service_call
record_issue
assess_safety
mock_zendesk_create_ticket
mock_zendesk_get_ticket_status
request_human_handoff
end_service_call
```

The selected MCP server may expose the additional diagnostic tool
`get_call_state`, but it is not available to the Agent graph.

The Portal allowlist uses `connection_mode: managed` and reads
`shared_mcp/config/generated/example3.local.env`. Run the local shared MCP E2E
first so the Dev Tunnel URL, bearer token, and customer-Project connection are
ready.

## Configure the CLI sample

```bash
cd /path/to/Cognitive-Speech-TTS/VoiceAgent/samples/example3_elevator_service_with_safety_zendesk_and_handoff
cp .env.example .env
```

Set the Project endpoint, then select the generated managed MCP config:

```dotenv
AZURE_AI_PROJECT_ENDPOINT=https://<account>.services.ai.azure.com/api/projects/<project>
VOICE_AGENT_MCP_CONFIG=../../shared_mcp/config/generated/example3.local.env
```

Use `AZURE_CREDENTIAL_MODE=default` for `DefaultAzureCredential`, or `cli` when
the sample must use the identity selected by `az login`.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Publish and verify

```bash
python sample.py publish
python sample.py check
```

The publisher materializes the environment-specific Agent name, model, MCP
server URL, and Project connection ID without modifying `agent.json`.

## Run

Check session readiness:

```bash
python sample.py connect
```

Exercise an exact-ID status query:

```bash
python sample.py run \
  --message "Check Zendesk ticket 15." \
  --expect-handoff \
  --expect-mcp \
  --evidence-file validation/elevator-service-status-smoke.json
```

Ticket `15` is committed fictional mock data.

## Portal

The Portal Template is named:

```text
Example 3: Elevator Service with Safety, Zendesk, and Handoff
```

Reload Templates after changing the allowlist or `agent.json`. The Portal
publishes a `local-only-elevator-service-example` Agent in the selected Project.

`/mcp/elevator-service` always uses persistent fictional ticket data. The
`mock_zendesk_*` names make that boundary visible in the Agent definition and
MCP inventory. To replace the mock with a customer-owned Zendesk adapter, keep
the same backend contract and follow
[the Zendesk integration guide](../../docs/integration_zendesk.md).

## Telephony boundary

The portable definition does not statically declare `transfer_call`. Real
telephone transfer is a hosting-platform capability:

```text
telephony binding
  -> configured transfer target
  -> runtime injects transfer_call
  -> model requests logical target
  -> provider executes transfer
```

This keeps the Portal/browser human-follow-up path from emitting an unhandled
telephone function call. A deployed runtime must preserve ingress-owned
call-control tools in the active graph node.

## Limitations

- The sample does not provision a Foundry Project, model deployment, Zendesk
  tenant, Logic App, or telephone number. The Portal does create or update the
  MCP connection after the customer selects a Project.
- Exact-ID ticket query is test-only until trusted caller and ticket-ownership
  authorization are added.
- The filesystem state model is not production multi-region storage.
- `request_human_handoff` records follow-up; it is not a PSTN transfer.
- Telephony transfer requires a real phone session and a compatible hosting
  runtime.
- Re-running publish creates another immutable Agent version.
- Cleanup is intentionally manual to avoid deleting an unrelated Agent.
