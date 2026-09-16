# Foundry-required portal validation

Validated on **September 16, 2026** after removing the offline runtime, on Windows with Python **3.12.10**, Node.js
**22.14.0**, npm **10.9.2**, and headless Microsoft Edge (`msedge`).

Upstream `HEAD`, `origin/main`, and the remote `refs/heads/main` were verified at
`e713a37c4cdb3282157cbaf46b6d425bcd984c05`.

| Check | Result |
| --- | --- |
| Isolated portal `.venv` installation and `pip check` | Passed |
| Clean `npm ci` using the public-URL lockfile | Passed |
| `npm run build:all` | Studio and standalone WebRTC bundles built |
| `npm test` | **194 passed** |
| Portal `python -m unittest discover -s tests -v` | **25 passed** |
| `npm run test:ui` / Playwright studio suite | **35 passed** |
| `npm run test:local` / Foundry-only portal with test-only Azure boundaries | **5 passed** |
| Existing sibling VoiceAgent SDK sample tests | **19 passed**; existing files/dependencies left unchanged |
| Actual frontend create serializer -> bundled Projects SDK model -> serialized definition | Passed; version-create route and flat `voice` / `voice_type` retained |
| Python compilation | Passed |
| Missing endpoint / removed `--mode` / optional port | Startup requires a project; obsolete mode flags are rejected; default port remains `9527` |
| Public npm metadata for all 37 locked package records | URLs and integrity hashes verified; lockfile uses SHA-512 |
| Public npm advisory API, all locked frontend packages | No affected package names returned on the validation date |

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
service fixture. The former offline server was stopped; no replacement was
started because no actual Foundry endpoint is configured in this workspace.

These are dated validation results, not a guarantee of future dependency or
service compatibility. Follow [README.md](README.md) to rerun the checks and
[PORTING.md](PORTING.md) when changing the source pin or local port.
