# Voice Agent portal local change log

This is the downstream port log, not the full upstream repository history.
Keep the upstream pin and intentional differences in every port entry.

## 2026-09-16 — Require an Azure Foundry project

**Upstream pin unchanged:** `e713a37c4cdb3282157cbaf46b6d425bcd984c05`.
This is a local product-policy change, not a new upstream import.

- Removed the `--mode` option, the default offline fallback, and `offline.py`.
  Both CLI parsing and application construction now require a valid public-cloud
  Azure Foundry project endpoint. Missing configuration exits with setup guidance
  before opening a listener or requesting credentials.
- Removed backend switching/cookies and all offline-specific UI, media bypasses,
  mock chat, and template generation from the production application.
- Normal startup is `python demo_server.py` after configuring the project.
  `--port` remains optional (default `9527`, or `DEMO_PORT`).
- Agent auto-delete remains removed. Stopping the portal never deletes Azure
  agents; local protocol recording remains opt-in.
- Updated the parent VoiceAgent README, portal setup guide, environment example,
  porting policy, and browser bundles.
- Replaced offline-product tests with required-project/configuration/security
  checks and normal portal integration tests. Azure credential/transport
  substitutes exist only in `tests/serve_portal.py`, never as a production mode.
- Refreshed local hashes and validation results without changing upstream hashes.
  The initial import below is retained as historical context, not current setup
  guidance.

## 2026-09-16 — First standalone public-repository port

**Upstream:** `main` at `e713a37c4cdb3282157cbaf46b6d425bcd984c05`

**Previous upstream pin:** none (first import).

**Source:** `tests/voice-agent-tests/voice-agents-tests-dashboard/voice_demo`

**Destination:** `VoiceAgent/portal`

### Retained

- React studio, standalone WebRTC UI, YAML definition editor, agent catalog and
  version editing, managed/BYOM authoring, and guided-authoring review.
- Voice WebSocket/PCM, WebRTC and avatar signaling, transcripts, tool approvals,
  client functions, greetings, structured inputs, handoffs, and turn metrics.
- Service-shaped REST/conversation/audio proxies and persisted/session viewers.
- Upstream library and browser regression tests applicable to the standalone
  portal, and Microsoft/third-party copyright notices.

### Adapted for this repository

- Replaced internal `common.py` presets with explicit public-cloud Foundry
  endpoint configuration and lazy server-side `DefaultAzureCredential`.
  Environment names align with the adjacent VoiceAgent samples.
- Aligned manual voice/prompt creation with this repository's public REST/SDK
  contract: `POST /agents/{name}/versions`, with the name only in the URL, and
  flat `audio.output.voice` / `voice_type` fields (including session overrides).
  Normalize version-create responses for the catalog; continue reading older
  nested voice definitions. Do not reintroduce the upstream `POST /agents` path.
- Added a clearly labeled, bounded, in-memory offline text demo for credential-
  free local startup, agent CRUD/versioning, template authoring, WebSocket echo,
  and saved-text inspection. Offline mode never captures microphone/shared
  audio and does not claim to execute an AI model, tools, or media.
- Made new-agent Azure conversation storage opt-in; local session recording is
  separately opt-in. Removed shutdown deletion of created agents.
- Restricted local browser access with loopback/Host/Origin checks; forward
  only service headers and never follow credentialed HTTP/WebSocket redirects.
  Moved credential acquisition off the event loop, sanitized local proxy errors,
  and awaited bridge-task cancellation. Agent URL selection is retained but
  automatic URL-triggered sessions are removed; the operator must press Connect.
- Replaced deployment discovery with user-supplied BYOM names. MCP/IQ/Toolbox
  presets are empty unless configured by the user. Trace links use optional
  explicit project metadata and only the preview flight used by sibling samples.
- Removed the MCP probe UI's network action; the compatibility endpoint returns
  an explicit unsupported response without fetching URLs or connection secrets.
- Redacted common credential fields in optional local event logs. Added visible
  mode/navigation notices and fixed the session viewer's `#root` CSS collision.
- Sanitized upstream test fixture backend names. Rebuilt checked-in browser
  assets; pinned public frontend dependencies and raised esbuild from 0.24.2
  to 0.28.2 and Playwright from 1.54.2 to 1.63.0. React 18.3.1 and js-yaml
  5.2.3 are retained. Python dependencies now require modern aiohttp/WebSocket
  APIs and include python-dotenv.
- Added setup docs, source/local SHA-256 manifest tracking, a read-only upstream
  comparison tool, Python HTTP/WebSocket/security tests, and a browser test that
  runs against the actual local Python server. Browser suites have separate
  output directories. Portal text uses LF line endings so local checksums remain
  stable across Windows and POSIX checkouts.

### Intentionally omitted

- Internal backend/subscription/resource-group/account presets, local service
  route overrides, test subagent seeding, and APIM bypass authentication headers.
- Automatic ARM subscription/project/deployment discovery and server-side MCP
  connection-secret retrieval/probing.
- Telephony provisioning guides/screenshots, internal API/design guides and
  load-test reports. Exact omitted source files/reasons are in `UPSTREAM.json`.
- Parent test dashboard, matrix tests, template catalog, deployment scripts,
  and corporate-network infrastructure; these are not dependencies of the port.

### Validation boundary

Local setup, frontend builds, protocol/unit tests, browser regressions, and the
real offline browser workflow are validated without Azure or microphone access.
Live REST and bidirectional binary/text WebSocket proxy behavior is exercised
against an actual localhost upstream fixture with a fake token. This is **not**
proof of an Azure model response, real microphone speech, WebRTC media, avatar,
or service-side tool execution; those require the operator's enabled project.
