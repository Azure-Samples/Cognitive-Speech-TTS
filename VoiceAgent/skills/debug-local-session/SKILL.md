---
name: debug-local-session
description: >-
  Debug a Voice Agent session recorded by VoiceAgent/samples/local_UI. Use
  when given a local UI run ID, local-ui web ID, Voice Live sess_ ID, Foundry
  conv_ ID, Agent name, or a symptom such as startup errors, handoff aborted,
  MCP failure, silence, unexpected close, or missing session records. Locate
  meta.json, timeline.log, events.jsonl, and server.log; identify the first
  fault domain; and decide whether to inspect Foundry traces or a tool backend.
---

# Debug Local Session

Debug the recorded session before attempting to reproduce it. This UI runs
locally but connects to the official Foundry Voice Agent endpoint; do not treat
it as a local Voice Live/orchestrator session.

## Workflow

1. Determine the actual data directory.
   - Prefer `--data-dir` from the running `app.py` command.
   - Otherwise use `LOCAL_UI_DATA_DIR`.
   - Otherwise use `~/.voice-agent-local-ui`.
   - Do not assume the current shell user started the UI.

2. From `VoiceAgent`, resolve the recording with the bundled
   analyzer:

   ```bash
   python skills/debug-local-session/scripts/analyze_session.py --list
   python skills/debug-local-session/scripts/analyze_session.py <session-id>
   ```

   Accept a run ID, `local-ui-*`, `sess_*`, `conv_*`, or Agent name. Pass
   `--data-dir /path/to/data` for an override. If an Agent name matches
   multiple recordings, use an exact ID or add `--latest` only when the newest
   run is intentionally the target. Use `--json` for structured output.

3. Read evidence in this order:
   1. `meta.json` for identity, UTC window, upstream, final node, counters, and
      bridge errors.
   2. `timeline.log` for the compact event sequence.
   3. `events.jsonl` for exact error codes, handoff edge/node IDs, and item IDs.
   4. `server.log*` only for bridge/auth/process failures or a missing record.

4. Stop at the first missing or failed expected transition:

   | Evidence | Primary fault domain |
   |---|---|
   | No recording directory | Wrong data directory, recorder initialization, or process ownership |
   | No `session.created` | Credential, WebSocket, Foundry route, or session bootstrap |
   | Early `error` such as `tool_connection_unresolved` | Published definition, Project connection, or Vienna materialization |
   | `session.handoff.started` then `.aborted` | Target prepare/activation; use `frame.error.code`, edge, and target node |
   | MCP/function call `.failed` | Tool execution path; correlate tool/item ID with backend logs |
   | Tool `.completed` but no next response/handoff | Response continuation or scheduling |
   | `bridge` error in meta/server log | Local UI proxy or network transport |
   | Normal close with no failure | No recorded infrastructure failure; business correctness remains unproven |

5. Escalate only after fixing the local evidence.
   - Use `conv_*` with `samples/download_conversation_traces.py` when the recording
     proves the event reached the official service but does not expose the
     internal owner.
   - Query an MCP/business backend only after the event stream shows a tool
     attempt or target preparation involving it.
   - Preserve the failed recording, then run a control with the same
     Agent/version. Do not restart or redeploy before preserving evidence.

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
