---
name: debug-local-session
description: >-
  Debug the customer Voice Agent sample stack across local setup, Foundry Project and
  model deployment, Agent publication/version, RemoteTool connection, shared
  MCP deployment/routes, Local UI bridge, and recorded sessions. Use for setup
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

The Local UI runs locally and connects to the official Foundry Voice Agent
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
   `.local-mcp-and-ui/local-ui.log` when a process is not ready.

3. If setup, publication, or **Try it now** fails before a recording exists:
   - Run `./scripts/setup-local-examples.sh --check`.
   - Confirm all three `.env` files select the intended Project.
   - Confirm `model_type` and `model` identify an available model deployment.
   - Inspect `shared_mcp/config/generated/example*.local.env`; never print
     `shared_mcp/state/local/token`.
   - Call both Local UI template probe endpoints. An MCP is ready only after
     authenticated HTTP 200 `initialize` and `tools/list` with all expected
     Agent tools.
   - Verify the selected Project contains the referenced RemoteTool connection
     before changing prompts or business logic.

4. If a recording exists, determine the actual data directory.
   - Prefer `--data-dir` from the running `app.py` command.
   - Otherwise use `LOCAL_UI_DATA_DIR`.
   - Otherwise use `~/.voice-agent-local-ui`.
   - Do not assume the current shell user started the UI.

5. Resolve the recording with the bundled analyzer:

   ```bash
   python skills/debug-local-session/scripts/analyze_session.py --list
   python skills/debug-local-session/scripts/analyze_session.py <session-id>
   ```

   Accept a run ID, `local-ui-*`, `sess_*`, `conv_*`, or Agent name. Pass
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
   | MCP/function call `.failed` | Tool execution path; correlate tool/item ID with backend logs |
   | Tool `.completed` but no next response/handoff | Response continuation or scheduling |
   | `bridge` error in meta/server log | Local UI proxy or network transport |
   | Normal close with no failure | No recorded infrastructure failure; business correctness remains unproven |

8. Escalate only after fixing the local evidence.
   - Use `conv_*` with `samples/download_conversation_traces.py` when the recording
     proves the event reached the official service but does not expose the
     internal owner.
   - Query an MCP/business backend only after the event stream shows a tool
     attempt or target preparation involving it.
   - Preserve the failed recording, then run a control with the same
     Agent/version. Do not restart or redeploy before preserving evidence.

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
2. Agent `model_type` + `model` = an eligible managed model or exact
   self-deployed deployment in that Project/account.
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
- The checked-in Finance definitions use `model_type: self_deployed`; `model`
  is the exact deployment name, not the underlying model family.
- The local MCP path is Docker `:18003` -> named Dev Tunnel -> Foundry
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
2. **Session identity**: run ID, Agent, `local-ui-*`, `sess_*`, `conv_*`, UTC
   window, upstream, and final active node.
3. **Evidence**: event type, offset, direction, edge/tool, error code, and
   artifact path/line.
4. **Control**: independent check separating persistent dependency failure
   from a session-specific failure.
5. **Next action**: one concrete owner/evidence source; state any missing
   evidence that prevents exact attribution.
