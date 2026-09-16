# Voice Agent portal

A standalone local port of the upstream **Voice Agent studio** and **WebRTC
demo**. Configure agents, edit their definitions as YAML, and connect to your
own Azure Foundry project. No checkout of the upstream repository, internal
dashboard, private package feed, or bundled Projects SDK wheel is needed.

The first port is pinned to upstream commit
`e713a37c4cdb3282157cbaf46b6d425bcd984c05` on `main`.
See [UPSTREAM.json](UPSTREAM.json), [CHANGELOG.md](CHANGELOG.md), and
[the update procedure](PORTING.md). Dated test results and their limitations are
in [VALIDATION.md](VALIDATION.md).

## Prerequisites

- **Python 3.10+**. Built browser assets are checked in, so Node.js is not
  required just to run the portal.
- **Your own Azure Foundry project**, with Voice Agents preview access and an
  identity authorized to use it. Follow the [VoiceAgent prerequisites](../README.md).
- Azure CLI sign-in (`az login`) or another `DefaultAzureCredential` identity.
- A microphone and headset for voice conversations.

**The portal always uses Azure Foundry.** There is no offline backend or runtime
mode selector. A missing or invalid project endpoint stops startup with setup
instructions; authentication/network errors never switch to mock responses.
Running the portal locally does not run the Azure voice service locally.

## Set up

From the repository root, in PowerShell:

```powershell
cd VoiceAgent\portal
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

macOS / Linux:

```bash
cd VoiceAgent/portal
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
[ -f .env ] || cp .env.example .env
```

Edit the portal's `.env` and set your project endpoint:

```dotenv
AZURE_VOICE_AGENTS_ENDPOINT=https://<account>.services.ai.azure.com/api/projects/<project>
AZURE_VOICE_AGENTS_MODEL=gpt-realtime
AZURE_VOICE_AGENTS_VOICE=en-US-AvaNeural
```

The backend uses `DefaultAzureCredential` and keeps its Azure access token out
of browser configuration. Only public-cloud HTTPS Foundry project endpoints
are accepted. It reads **only this directory's `.env`**, not `../samples/.env`;
process environment variables take precedence.

## Run locally

PowerShell, from this directory:

```powershell
az login
.\.venv\Scripts\python.exe demo_server.py
```

macOS / Linux:

```bash
az login
.venv/bin/python demo_server.py
```

Alternatively, supply the project on the command line instead of in `.env`:

```powershell
.\.venv\Scripts\python.exe demo_server.py --project-endpoint "https://<account>.services.ai.azure.com/api/projects/<project>"
```

Open **http://127.0.0.1:9527**, select or create an agent, click **Connect & start
session**, and grant microphone permission. Press **Ctrl+C** to stop.

`--port` is optional: it defaults to `9527`, or `DEMO_PORT` if configured. Use
`--port 9530` when needed; do not stop an unrelated service to free a port.

## Using the portal

- Choose an existing agent or create one. The browser sends service-shaped
  REST requests through the local authenticated backend.
  Creation uses `POST /agents/<name>/versions` and flat `voice` / `voice_type`
  audio fields, matching this repository's current REST/Projects SDK samples.
- Agent links select an agent but never start a session automatically.
  Press **Connect & start session** explicitly; legacy `autostart=1` is ignored.
- Use a headset and grant microphone permission for real audio. WebSocket PCM,
  WebRTC, and avatar signaling retain their upstream implementations.
- Creation and version edits change your Azure project and may incur charges.
  **Stopping the portal never deletes agents.** Manage unwanted agents in your
  Azure project separately.
- Managed models, guided authoring, hosted-agent wrappers, greetings, handoffs,
  tools, avatars, and WebRTC depend on the capabilities enabled in your project.
  The selectable examples are not a guarantee of model or feature availability.
- **Save conversations** defaults off for newly configured agents. Enable it
  deliberately to use **View persisted** and audio downloads. Existing agents
  retain their stored policy; session settings can override it.

The standalone WebRTC page is **http://127.0.0.1:9527/webrtc** and uses the same
configured Foundry project.

### Optional configuration

All values must refer to **your** resources; there are no internal presets.

| Environment variable | Purpose |
| --- | --- |
| `VOICE_PORTAL_REALTIME_DEPLOYMENTS` | Comma-separated BYOM realtime deployment names. |
| `VOICE_PORTAL_CASCADED_DEPLOYMENTS` | Comma-separated BYOM text-model deployment names. |
| `AZURE_VOICE_AGENTS_MCP_CONNECTION_ID` | Pre-fill your MCP project connection. |
| `AZURE_VOICE_AGENTS_MCP_SERVER_LABEL` | Label for that connection; default `mcp`. |
| `AZURE_VOICE_AGENTS_FOUNDRY_IQ_URL` | Your knowledge-base MCP URL. |
| `AZURE_VOICE_AGENTS_FOUNDRY_IQ_CONNECTION_ID` | Your knowledge-base connection. |
| `AZURE_VOICE_AGENTS_TOOLBOX_NAME` / `AZURE_VOICE_AGENTS_TOOLBOX_VERSION` | Your versioned Toolbox. |
| `AZURE_SUBSCRIPTION_ID` / `AZURE_RESOURCE_GROUP` | Optional project metadata enabling **View trace**. |
| `DEMO_PORT` | Local listener port; default `9527`. |

BYOM deployment lists are configuration, **not** automatic ARM discovery. The
portal does not enumerate your subscriptions or retrieve connection secrets.
Prefer project connections over entering MCP authorization tokens in the UI:
manually entered tokens are part of the draft/definition and must not be shared
in YAML, screenshots, or logs.

### Local event recording

`--record-sessions` opts in to recording voice protocol events under
`session-logs/`. Audio payloads are elided and common credential fields are
redacted, but **transcripts, prompts, and tool data may still be sensitive**.
Recording is separate from the agent's Azure `store` policy and remains off by
default. Do not commit or share these logs. The **Local session logs** link
opens the included viewer.

## Develop and validate

Frontend development requires **Node.js 22+**. From this directory:

```powershell
cd web
npm ci
npm run build:all
npm test
npx playwright install chromium
npm run test:ui
npm run test:local
cd ..
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
python tools\upstream_status.py --check
```

`npm run test:ui` runs the ported browser regressions with mocked Azure
boundaries. `npm run test:local` starts the **real Foundry-only Python portal**
on loopback port `8097`, using `tests/serve_portal.py` to substitute only the
Azure credential and upstream transport with test fixtures. It drives creation,
YAML edits, WebSocket responses, persisted-data retrieval, and microphone startup
through a synthetic browser device. The application has no test/offline runtime
mode. These tests do not prove a real Azure conversation.

The static UI fixture uses `8098`. Both test servers are stopped by Playwright;
neither test helper is used by `demo_server.py`.

For the browser tests you can use an installed Edge browser instead:
`$env:PLAYWRIGHT_CHANNEL='msedge'` (POSIX: `export PLAYWRIGHT_CHANNEL=msedge`).
`VOICE_PORTAL_PYTHON` can point to a Python environment other than `.venv`.
Run the two browser commands sequentially because their build steps write the
same checked-in bundles.

Use `npm run watch` / `npm run watch:webrtc` while editing. Rebuild **both**
bundles before committing, update the local change log, then record the new
local hashes as described in [PORTING.md](PORTING.md).

## Safety and troubleshooting

- This is a **single-user local sample**, not an authenticated hosted portal.
  It binds only to loopback and rejects cross-origin browser requests and
  unexpected Host headers. Do not expose it through a tunnel, proxy, or public
  listener without a separate authentication/security design.
- `401` / `403`: check Azure sign-in, project permissions, and preview access.
- `404` / unsupported feature: verify the project endpoint and available
  service capabilities; remove unsupported options from the definition.
- Missing browser assets: run `npm ci` and `npm run build:all` in `web/`.
- Microphone unavailable: use localhost and a supported browser, check
  permissions/hardware and your Foundry project access.
- No saved conversation: enable the desired agent/session storage policy,
  finish the session, and allow time for Azure persistence.

Upstream Microsoft copyright notices and bundled third-party license comments
are retained. See the repository [license](../../LICENSE.md). The private
upstream did not supply a standalone demo license; maintainers must confirm
redistribution approval before public publication. No upstream screenshots,
internal test reports, credentials, or deployment scripts are included.
