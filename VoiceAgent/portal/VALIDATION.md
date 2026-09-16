# Public-release fixes validation

Validated on **September 16, 2026** after the public-release review fixes, on Windows with Python **3.12.10**, Node.js
**22.14.0**, npm **10.9.2**, and headless Microsoft Edge (`msedge`).

The source pin remains `e713a37c4cdb3282157cbaf46b6d425bcd984c05`.
Pinned source hashes and current local hashes were verified; these local-only
changes do not update the source revision.

| Check | Result |
| --- | --- |
| Portal Python environment and `pip check` | Passed |
| Clean `npm ci` using the public-URL lockfile | Passed |
| `npm run build:all` | Studio and standalone WebRTC bundles built |
| `npm test` | **194 passed** |
| Portal `python -m unittest discover -s tests -v` | **36 passed** |
| Playwright studio and privacy suites | **43 passed** (35 existing, 8 new) |
| `npm run test:local` / Foundry-only portal with test-only Azure boundaries | **5 passed** |
| Existing sibling VoiceAgent SDK sample tests | **19 passed**; existing files/dependencies left unchanged |
| Comment-only cleanup in 14 runtime files | Identical compiled output before/after, including voice transport, serializers, tools, and handoffs |
| Bundled third-party notices | Exact installed license texts and lockfile versions verified; served without Azure credential acquisition |
| JSON-encoded tool log data | Nested/double-encoded secrets redacted; malformed/oversized/deep data omitted; plain text and forwarded frames retained |
| Generated-session storage | Explicit off/on choice reaches the WebSocket; draft contract and stored versions remain unchanged |
| Persisted HTML and WebRTC viewers | Captured IDs open directly; missing IDs require explicit selection; historical viewing and recording controls retained |
| Python compilation | Passed |
| Missing endpoint / removed `--mode` / optional port | Startup requires a project; obsolete mode flags are rejected; default port remains `9527` |
| Public npm metadata for all 37 locked package records | URLs and integrity hashes verified; lockfile uses SHA-512 |
| Public npm advisory API, all locked frontend packages | No affected package names returned on the validation date |

**278 portal tests passed**, plus the 19 unchanged sibling SDK tests. Frontend
dependency versions are unchanged from the first port; public-registry metadata
and advisory results above are the dated first-port checks.

Portal Python packages installed for this validation:

- `azure-identity==1.25.3`
- `requests==2.34.2`
- `aiohttp==3.14.3`
- `websockets==15.0.1`
- `python-dotenv==1.2.3`

## What was exercised

The local browser suite runs the production Foundry-only portal with an
explicitly configured project endpoint. `tests/serve_portal.py` substitutes only
the Azure credential and upstream HTTP/WebSocket transports, not the portal
routes. It creates an agent, saves a YAML edit as version 2, connects through the
real proxy, opens the persisted-data viewer, and exercises microphone startup
using Playwright's synthetic device. It also checks guided-authoring response
handling, normal WebRTC agent selection, disabled recording, cross-origin
rejection, and non-automatic agent links.

Eight additional browser regressions cover the generated-storage choice
(default off, explicit opt-in, draft preservation, refresh/reselection and
editable overrides) and both historical viewers. They prove no transcript is
read before a missing conversation ID is explicitly selected, while captured
IDs, known-ID entry after list failure, audio controls, and New session still
work. These new WebRTC review tests also replace the peer connection with a
test-only boundary, so they do not claim to validate actual WebRTC media.

The live proxy tests run actual local HTTP and WebSocket servers with fake
credentials. They verify public request paths/bodies, auth and preview headers,
binary/audio forwarding, structured inputs, redirect rejection, sanitized
authentication errors, and the agent-completion close reason needed to drain
queued audio. Configuration tests verify that no server is started without a
Foundry project and that `--mode` cannot be accepted as an abbreviation of
`--model`. Shutdown tests prove no agent DELETE is sent after creation.

## Not verified

No real Azure model response, physical microphone conversation, WebRTC media, avatar,
telephony, hosted-agent execution, or service-side tool execution was attempted.
Those require the operator's own preview-enabled Azure project and permissions.
No Azure resources were created, modified, or deleted during these checks.
There is no user-facing offline/test mode and no production import of the test
service fixture. Only test helpers were started and they were stopped afterward.
No operational portal was started against a real project during this validation.

Source-owner redistribution approval is a separate release decision, not a test
result. Removing private metadata from current files does not remove it from
already published Git history.

These are dated validation results, not a guarantee of future dependency or
service compatibility. Follow [README.md](README.md) to rerun the checks and
[PORTING.md](PORTING.md) when changing the source pin or local port.
