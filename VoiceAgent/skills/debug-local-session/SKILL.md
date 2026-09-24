---
name: debug-local-session
description: >-
  Debug the customer Voice Agent sample stack across local setup, Foundry Project and
  model deployment, Agent publication/version, RemoteTool connection, shared
  MCP deployment/routes, portal bridge, and recorded sessions. Use for setup
  failures, wrong Project/model, publish errors, disabled Try it now, MCP auth
  or tool failures, handoff aborts, silence, unexpected close, missing
  recordings, or any run/session/Voice Live/Foundry ID. Correlate local stack
  logs, generated MCP config, Project connections, Agent definitions, session
  recordings, Foundry traces, and MCP business state to identify the first
  failing boundary.
---

# Debug the customer Voice Agent sample stack

Work from `VoiceAgent/`. Read [references/system-map.md](references/system-map.md)
before diagnosing Project, deployment, connection, MCP, or UI ownership.

The portal runs locally and connects to the official Foundry Voice Agent
endpoint.

## Workflow

1. Preserve identity before restarting anything.
   - Capture the exact Foundry Project endpoint, Agent name/version, model type
     and deployment name, local run/web ID, `sess_*`, `conv_*`, and UTC window.
   - Do not correlate sessions only by close timestamps or similar Agent names.

2. Check local process boundaries:

   ```bash
   ./scripts/manage-local-mcp-and-ui.sh status
   curl -fsS http://127.0.0.1:18003/healthz
   curl -fsS http://127.0.0.1:18098/healthz
   ```

  Read `.local-mcp-and-ui/mcp.log` and
  `.local-mcp-and-ui/portal.log` when a process is not ready. For requests
  that reached the native MCP runtime, read the `native-mcp.log` under the
  newest `shared_mcp/state/e2e/<UTC-run>/` directory; the manager log contains
  startup output but is not the authoritative HTTP access log.

3. If setup, publication, or **Try it now** fails before a recording exists:
   - Run `./scripts/setup-local-examples.sh --check`.
   - Confirm all three `.env` files select the intended Project.
   - Confirm `model_type` and `model` identify an available model deployment
     in the account that owns that Project; a deployment in a sibling account
     is not automatically visible.
   - Inspect `shared_mcp/config/generated/example*.local.env`; never print
     `shared_mcp/state/local/token`.
   - Call both portal template probe endpoints. An MCP is ready only after
     authenticated HTTP 200 `initialize` and `tools/list` with all expected
     Agent tools.
   - Verify the selected Project contains the referenced RemoteTool connection
     before changing prompts or business logic.

4. If a recording exists, determine the actual data directory.
   - Prefer `--data-dir` from the running `demo_server.py` command.
   - Otherwise use `VOICE_PORTAL_DATA_DIR`.
  - Otherwise use `<portal-process-HOME>/.voice-agent-portal`, where
    `<portal-process-HOME>` comes from `/proc/<portal-pid>/environ`; do not
    substitute the portal working directory.
   - Do not assume the current shell user started the UI.

   For the manager-owned portal, resolve only the allowed fields without
   printing its complete environment:

   ```bash
   portal_pid="$(<.local-mcp-and-ui/portal.pid)"
   tr '\0' '\n' < "/proc/${portal_pid}/environ" |
     sed -n '/^HOME=/p;/^VOICE_PORTAL_DATA_DIR=/p;/^VOICE_PORTAL_RECORD_SESSIONS=/p'
   ```

   If `VOICE_PORTAL_DATA_DIR` is unset, use the reported `HOME` plus
   `/.voice-agent-portal`.

5. Resolve the recording with the bundled analyzer:

   ```bash
   python skills/debug-local-session/scripts/analyze_session.py --list
   python skills/debug-local-session/scripts/analyze_session.py <session-id>
   ```

   Accept a run ID, `web-*`, `sess_*`, `conv_*`, or Agent name. Pass
   `--data-dir /path/to/data` for an override. If an Agent name matches
   multiple recordings, use an exact ID or add `--latest` only when the newest
   run is intentionally the target. Use `--json` for structured output.

6. Read evidence in this order:
   1. `meta.json` for identity, UTC window, upstream, final node, counters, and
      bridge errors.
   2. `timeline.log` for the compact event sequence.
   3. `events.jsonl` for exact error codes, handoff edge/node IDs, and item IDs.
   4. `server.log*` only for bridge/auth/process failures or a missing record.

7. Stop at the first missing or failed expected transition:

   | Evidence | Primary fault domain |
   |---|---|
   | Setup checker fails | Local dependencies, auth, environment, or missing `.env` |
   | MCP health/probe fails | Container, Dev Tunnel/Container App, bearer credential, route, or tool inventory |
   | Publish rejects `model_type` or `model` | Wrong Project, model mode, or deployment name |
   | Publish reports unresolved connection | Wrong Project or missing/stale RemoteTool connection |
   | No recording directory | Wrong data directory, recorder initialization, or process ownership |
   | No `session.created` | Credential, WebSocket, Foundry route, or session bootstrap |
   | Early `error` such as `tool_connection_unresolved` | Published definition, Project connection, or Vienna materialization |
   | `session.handoff.started` then `.aborted` | Target prepare/activation; use `frame.error.code`, edge, and target node |
  | Closed session with `HANDOFF_INCOMPLETE` | Target preparation never emitted a terminal event; correlate the started offset with Foundry trace and native MCP access log |
  | Handoff abort plus MCP `GET ... 400 Missing session ID` | Foundry used legacy HTTP+SSE against a Streamable-HTTP-only route |
  | Handoff prepare timeout plus MCP `GET 200`, but no message `POST` | Legacy SSE did not return a usable `endpoint` event or public message URL |
  | MCP `GET 200`, message `POST 202`, `ListToolsRequest`, then handoff completed | Target MCP transport and tool discovery succeeded |
   | MCP/function call `.failed` | Tool execution path; correlate tool/item ID with backend logs |
   | Tool `.completed` but no next response/handoff | Response continuation or scheduling |
   | `bridge` error in meta/server log | Portal proxy or network transport |
   | Normal close with no failure | No recorded infrastructure failure; business correctness remains unproven |

8. Escalate only after fixing the local evidence.
   - Use `conv_*` with `samples/download_conversation_traces.py` when the recording
     proves the event reached the official service but does not expose the
     internal owner.
   - Query an MCP/business backend only after the event stream shows a tool
     attempt or target preparation involving it.
   - Preserve the failed recording, then run a control with the same
     Agent/version. Do not restart or redeploy before preserving evidence.

## Handoff transport triage

For `handoff_target_activation_failed` or `handoff_target_prepare_timeout`, do
not stop after confirming health or the Portal template probe. The probe uses
Streamable HTTP, while Foundry RemoteTool can use legacy HTTP+SSE against the
same route.

1. Get the failed handoff timestamp and target node from `events.jsonl`.
2. Find the active native MCP artifact from the manager log or the newest
   `shared_mcp/state/e2e/<UTC-run>/native-mcp.log`.
3. Match Foundry requests by timestamp and public client address. A successful
   legacy sequence is:

   ```text
   GET  /mcp/<route>                                  200
   POST /mcp/<route>/messages/?session_id=<id>        202
   Processing request of type ListToolsRequest
   Processing request of type CallToolRequest         # only when a tool runs
   ```

4. Interpret the first deviation:
   - `GET 400 Missing session ID`: the route handled legacy SSE as stateful
     Streamable HTTP.
   - `GET 200` followed by a 30-second handoff timeout and no message `POST`:
     the SSE stream did not expose a usable `endpoint` event.
   - message `POST 401` or `404`: Project connection credential or SSE session
     mismatch.
   - `ListToolsRequest` without the required tool: wrong route or inventory.
   - `CallToolRequest` with a business error: transport succeeded; debug the
     tool implementation and state.

Never print `shared_mcp/state/local/token`. Use the Portal probe for the
Streamable HTTP control and the native access log for the Foundry transport.

## Evidence quality rules

- Prove the baseline before assigning a feature failure. If Project access,
  model publication, or plain session establishment also fails, classify the
  MCP/handoff case as blocked or inconclusive rather than blaming the feature.
- "No MCP log" proves only that the request did not reach MCP. Before assigning
  the fault upstream, prove that the same endpoint was healthy at that time
  through health/probe evidence or successful calls immediately before/after.
- A browser can prove what it did not receive, not which server component owes
  the next event. For a stuck post-tool turn, use the Foundry trace to check
  whether `execute_tool` has a result and whether a second `chat` follows it.
- Foundry trace ingestion can be delayed. Requery before finalizing a
  conclusion from an apparently truncated timeline.
- Use `PASS`, `FAIL`, `BLOCKED_EXTERNAL`, or `INCONCLUSIVE` explicitly. Do not
  report a product failure when the closest control fails the same way.

## Required relationship checks

Always confirm these joins instead of validating each component in isolation:

1. UI-selected Project = Project where the Agent version is published.
2. Agent `model_type: managed` + its exact versioned `model` identifier = a
  model enabled for that Project and region.
3. Agent `project_connection_id` = a RemoteTool connection in the same Project.
4. Connection target = the route in the generated example config.
5. Connection bearer credential = `SHARED_MCP_TOKEN` used by the active MCP
   deployment.
6. Route tool inventory includes every `allowed_tools` entry in the exact
   published Agent definition.
7. Session MCP item/call ID = the backend log/business-state operation being
   investigated.

## Project and deployment controls

- Treat each `sample.py publish` or UI **Try it now** as a new immutable Agent
  version; verify the exact version rather than the Agent name alone.
- The checked-in Finance definitions default to service-managed
  `gpt-realtime-2.1`. If unsupported, verify `gpt-realtime-1.5`, then another
  exact managed identifier enabled for the selected Project.
  Account deployment inventory is not the readiness gate for this mode.
- The local MCP path is native Python `:18003` -> named Dev Tunnel -> Foundry
  RemoteTool connection. The Azure path is Container App -> RemoteTool
  connection. Do not mix generated `.local.env` and `.shared.env`.
- The UI is a local credentialed proxy and recorder. Foundry, not the browser,
  invokes MCP tools.

## Recording semantics

- `up` is browser to service; `down` is service to browser.
- Audio payloads and token-level deltas are intentionally omitted. A missing
  audio delta is not packet loss.
- Long fields are clipped in `events.jsonl`; use backend/cloud evidence for
  complete tool payloads when needed.
- Empty `meta.errors` does not mean healthy. Handoff aborts live in
  `events.jsonl`, and MCP failures are represented in `meta.tool_calls`.
- The recorder is best-effort and must never break a call. Missing/corrupt
  artifacts require checking `server.log*` and the active data directory.
- Recordings can contain customer transcript and tool data. Do not copy them
  into source control or broad reports.

## Result format

Return a conclusion-first report:

1. **Conclusion**: first failed transition and owning fault domain.
2. **Session identity**: run ID, Agent, `web-*`, `sess_*`, `conv_*`, UTC
   window, upstream, and final active node.
3. **Evidence**: event type, offset, direction, edge/tool, error code, and
   artifact path/line.
4. **Control**: independent check separating persistent dependency failure
   from a session-specific failure.
5. **Next action**: one concrete owner/evidence source; state any missing
   evidence that prevents exact attribution.
