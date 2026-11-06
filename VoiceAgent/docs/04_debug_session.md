# 04 - Debug a portal session

## Conclusion

Start with the local session recording, not with a reproduction or a broad
cloud-log search. Every bridged session has enough identity and event evidence
to identify the first failed transition; only then query the Foundry trace or
the relevant tool backend.

This UI is local, and its Voice WebSocket connects to the official Foundry
Voice Agent endpoint.

Use the [architecture and documentation index](./README.md) for the component
map, the [portal guide](../portal/README.md) for startup, and
[02: MCP settings](./02_mcp_settings.md) when local evidence assigns the
failure to MCP hosting or a business tool.

## Canonical debugging Skill

The reusable debugging implementation is:

```text
VoiceAgent/skills/debug-local-session/
  SKILL.md
  scripts/analyze_session.py
```

Use [`skills/debug-local-session/`](../skills/debug-local-session/) for both
Agent instructions and the analyzer. Do not look under
Do not look for a component-local Skill under `portal/`; the Skill is shared at
the `VoiceAgent` level.

## Before a session recording exists

If **Try it now** is disabled or Agent publication fails before a Voice
WebSocket opens, there is no session to analyze yet:

1. Open **Templates** and run **Test MCP**. It must complete an authenticated
   handshake and verify every required tool.
2. Check `curl -sS http://127.0.0.1:18003/healthz`.
3. Confirm `VoiceAgent/shared_mcp/scripts/e2e-local.sh` is still running and
   the two `VoiceAgent/shared_mcp/config/generated/*.local.env` files exist.
4. Confirm the UI selected the intended Foundry Project and identity.
5. Use the UI server log for connection creation or Agent publication errors.

Continue with the recorded-session workflow below only after the Voice
WebSocket attempt creates a session directory.

## Recording implementation

[`demo_server.py`](../portal/demo_server.py) creates a `SessionRecorder` before
opening the upstream WebSocket, records both directions, and closes the
recorder from `finally`.
[`session_log.py`](../portal/session_log.py) writes:

```text
<data-dir>/
  server.log
  server.log.1
  sessions/<UTC>-<web-id>/
    meta.json
    timeline.log
    events.jsonl
```

The default `<data-dir>` is `~/.voice-agent-portal`. `VOICE_PORTAL_DATA_DIR` or
`demo_server.py --data-dir` overrides it. When another account or service starts the
UI, its home directory may differ from the current shell's home directory.
Check the running command or the startup line in `server.log` before declaring
a recording missing.

### What each file proves

| File | Use it for | Important limitation |
| --- | --- | --- |
| `meta.json` | IDs, Agent, backend, upstream, UTC window, final node, counters, bridge errors | `errors: []` does not exclude handoff or MCP failures |
| `timeline.log` | Compact ordering of session, handoff, tool, audio-summary, and close events | It omits detailed error objects and transcript text |
| `events.jsonl` | Exact event fields, error codes, edge/node IDs, item IDs, transcripts, and usage | Long fields are clipped; audio and token deltas are omitted |
| `server.log*` | Recorder startup, credential/bridge exceptions, HTTP access, process-level context | Concurrent sessions share these rotating files |

`up` means browser to service. `down` means service to browser.

Audio frames are counted and coalesced rather than storing base64 PCM.
Token-level `*.delta` events are omitted because the completed `.done` event
contains the assembled value. Their absence is not evidence of packet loss.

The recorder is intentionally best-effort: recording exceptions are swallowed
so observability cannot break the live call. A missing or partially corrupt
recording must therefore be checked against `server.log*`.

## Fast path

Run from `VoiceAgent`:

```bash
# List newest recordings.
python skills/debug-local-session/scripts/analyze_session.py --list

# Resolve any exact session identity.
python skills/debug-local-session/scripts/analyze_session.py sess_...
python skills/debug-local-session/scripts/analyze_session.py conv_...
python skills/debug-local-session/scripts/analyze_session.py web-...
python skills/debug-local-session/scripts/analyze_session.py 20260916T...

# Use the actual data directory when it was overridden.
python skills/debug-local-session/scripts/analyze_session.py \
  --data-dir /path/to/data \
  sess_...

# Produce a machine-readable report without printing transcript content.
python skills/debug-local-session/scripts/analyze_session.py --json sess_...
```

An Agent name can match many recordings. Prefer an exact run, web, session, or
conversation ID. Use `--latest` only when the newest matching Agent run is
known to be the target.

## Evidence-first workflow

### 1. Fix the identity and time window

Preserve these values from `meta.json`:

- `run_id` and `web_id` for local files and `server.log`;
- `session_id` (`sess_*`) for Voice Live correlation;
- `conversation_id` (`conv_*`) for Foundry persistence and tracing;
- exact Agent name, backend Project, upstream URL, UTC start/end, and final
  `active_node_id`.

Do not correlate different sessions only because their timestamps are close.

### 2. Find the first failed transition

Read `timeline.log` top to bottom. Then inspect only relevant raw events:

```bash
rg -n \
  '"type": "(error|session\.handoff\.(started|completed|aborted)|response\..*\.failed)"' \
  '<session-dir>/events.jsonl'
```

Use this ownership table:

| First missing or failed evidence | Primary fault domain | Next evidence |
| --- | --- | --- |
| No session directory | Wrong data dir, recorder initialization, or process owner | Running command and `server.log*` |
| No `session.created` | Credential, WebSocket, route, or Foundry bootstrap | Bridge error and server traceback |
| Early `error` with `tool_connection_unresolved` | Published tool connection or Vienna materialization | Error code/label and Project connection |
| `handoff.started` then `handoff.aborted` | Target prepare or activation | `frame.error.code`, edge, target node, cloud trace |
| Tool `.in_progress` then `.failed` | MCP/function/tool execution | Tool/item ID and backend log |
| Tool `.completed` but no next response/handoff | Continuation or response scheduling | Subsequent events and service trace |
| Bridge error at close | Local proxy/network path | `meta.errors` and `server.log*` |
| Normal bridge close only | No recorded infrastructure failure | Validate expected business outcome/transcript |

The first error is not always terminal. For example, a connection-resolution
error can drop tools while the session and handoffs continue. Report the
session as degraded instead of claiming that it never connected.

### 3. Read the exact error object

Do not stop at UI text such as `handoff aborted: error`. The raw event includes
the edge and server error:

```json
{
  "type": "session.handoff.aborted",
  "edge_id": "entrypoint_to_open_call",
  "from_node_id": "$entrypoint",
  "to_node_id": "open_call",
  "reason": "error",
  "error": {
    "code": "handoff_target_activation_failed",
    "message": "The target node could not be activated."
  }
}
```

Likewise, `response.mcp_call.failed` may contain only an `item_id`. Correlate
that ID with the earlier `response.output_item.added`; the analyzer does this
automatically. The tool name is also retained in `meta.tool_calls`.

### 4. Escalate to the correct external evidence

Because the upstream is official Foundry, use `conversation_id` when service
internals are required:

```bash
cd VoiceAgent
python samples/download_conversation_traces.py conv_...
```

This requires `AZURE_VOICE_AGENTS_APP_INSIGHTS_RESOURCE_ID` and Log Analytics
query permission. Preserve the local artifacts even when trace ingestion is
delayed.

For MCP or business tools, query the backend only after local events prove a
call or target preparation reached that path. Check endpoint availability,
authentication, tool inventory, request arrival, and the exact item/tool ID.
No backend log means the request did not reach that backend; it does not prove
the backend returned an error.

### 5. Run a control after preserving evidence

Use the same Agent/version and dependency path:

- a new session succeeds: prioritize session-specific or transient failure;
- the same edge/tool fails again: prioritize definition, connection, backend,
  or service rollout;
- a direct MCP probe fails: fix the endpoint/auth/tool inventory before
  changing the prompt or handoff graph.

Do not restart or redeploy before copying the failed run ID and critical event
fields.

## Reporting template

Write the result conclusion-first:

```text
Conclusion:
  <first failed transition and owning fault domain>

Session:
  run/web/sess/conv IDs, Agent, Project, UTC window, upstream, final node

Evidence:
  +<seconds> <direction> <event> <edge/tool> <error code>
  artifact path and line

Control:
  independent health/reproduction result

Next action:
  one owner and one evidence source; explicitly state any missing evidence
```

## Data handling

Recordings can contain customer transcript and tool data. Keep permissions
restricted, do not commit recordings, and do not paste complete
`events.jsonl` or transcripts into broad reports when an event code and ID are
sufficient. The implementation has no automatic retention policy.
