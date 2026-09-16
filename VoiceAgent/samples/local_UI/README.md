# Voice Agent Local UI

This standalone UI lets a customer select a visible Microsoft Foundry Project,
choose one of its published Voice Agents, run a microphone or text session, inspect live
handoffs, read the transcript and browser-observed latency, and publish a new
Agent from a sample template.

Use the [architecture and documentation index](../../docs/README.md) for the
system overview. For the complete local MCP, Agent publication, and UI order,
use [03: Start and run the samples](../../docs/03_run_samples.md).

## What the UI includes

- **Live session**: published Agent picker, microphone controls, text fallback,
  live handoff graph, transcript, MCP activity, TTFT, TTFA, and token usage.
- **Templates**: a configuration-driven catalog. The checked-in config points
  to the sibling Finance Example and Finance with OTP and Officer Search
  samples; Finance Example demonstrates the multi-node handoff view.
- **Project selection**: the header provides a searchable Project text box
  backed by visible Foundry Project suggestions. Search matches Project names
  only; the account is shown only as supporting context. You may also paste a
  full endpoint. Switching Project reloads its published Voice Agents.
- **Server-side authentication**: Azure credentials and access tokens remain in
  Python. The browser connects only to the local server.

The Live and Templates surfaces directly reuse the proven React components,
styles, graph renderer, latency engine, and streaming update model from the
Voice Agent Test Dashboard. The local UI intentionally omits that dashboard's
test scheduler and left-side Create/Generate authoring form.

## Prerequisites

- Python 3.10 or later.
- Access to a Microsoft Foundry Project that contains Voice Agents.
- `az login` or another identity supported by `DefaultAzureCredential`.
- Browser microphone permission. Chrome or Edge is recommended.

These prerequisites are enough to open published Agents in **Live session**.
Using **Templates** and **Try it now** also requires the Docker, Azure CLI,
and Dev Tunnel setup in the
[03: Start and run the samples](../../docs/03_run_samples.md).

## Configure and run

```bash
cd Cognitive-Speech-TTS/VoiceAgent/samples/local_UI
cp .env.example .env
# Edit AZURE_AI_PROJECT_ENDPOINT in .env.

python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py --host 127.0.0.1 --port 8097
```

Open `http://localhost:8097`.

Set `AZURE_CREDENTIAL_MODE=cli` to use exactly the identity selected by
`az login`. The default uses `DefaultAzureCredential`.

The configured endpoint is the initial Project. Use the **Foundry project**
text box in the page header to search by Project name, select a suggestion, or
paste a full Project endpoint, then press Enter or **Switch**. Project
discovery uses Azure Resource Graph and requires Reader access; invoking an
Agent also requires the corresponding data-plane access.

Before using **Try it now**, run `../../shared_mcp/scripts/e2e-local.sh`. It
creates the fixed local MCP tunnel, stores authentication in the two Foundry
connections, and writes the non-secret configs consumed by this UI. No MCP
token is entered in the browser or this UI's `.env`.

## Configure templates

[`templates.config.json`](./templates.config.json) is the only template
allowlist. Each entry points to a sibling sample folder:

```json
{
  "version": 1,
  "templates": [
    {
      "id": "finance-example",
      "folder": "../example1_finance_with_handoff"
    },
    {
      "id": "finance-with-otp-and-officer-search",
      "folder": "../example2_finance_with_OTP_and_Officer_Search"
    }
  ]
}
```

`folder` is resolved relative to the config file and `agent_file` defaults to
`agent.json`. Agent source paths must remain under `VoiceAgent/samples/`.
Each default template uses `mcp.config_file` and `mcp.token_file` under
`VoiceAgent/shared_mcp/`; the server rejects MCP paths outside that directory,
including after symlink resolution. It does not read the sibling sample
`.env`, README, or validation output.

Optional presentation fields are `name`, `category`, `summary`, `accent_color`,
and `enabled`. Without them, the UI uses the Agent document's `name` and
`description` plus neutral defaults.

Set `LOCAL_UI_TEMPLATE_CONFIG` or pass `--template-config` to use a different
allowlist without changing code. The Templates **Reload** button re-reads both
the config and every enabled `agent.json`.

For the two default templates, **Try it now** reads the fixed named-tunnel URL
and connection name from `mcp.config_file`. The local server reads the ignored
token file and creates or updates that connection in the **currently selected
Foundry Project/account** before publishing. This prevents an Agent published
after a Project switch from referencing a connection that exists only under a
different Foundry account.

No token is accepted from the browser. Selecting a template automatically runs
**Test MCP**. The local server reads the ignored token file, performs an
authenticated MCP handshake and `tools/list`, and verifies that the route
contains every tool allowed by the template. HTTP 401 or 403 is reported as an
authentication failure rather than readiness. Try it now and Publish remain
disabled while the MCP is unavailable or incomplete. The failure panel
displays the local E2E command and links to the setup guide.

Start `VoiceAgent/shared_mcp/scripts/e2e-local.sh`, leave it running, select **Reload**,
and use **Test MCP** to retry.

For the default local workflow, the server:

1. reads the ignored local token file on the server;
2. creates or updates the fixed `RemoteTool` / `CustomKeys` connection in the selected
   Foundry account, storing `Authorization: Bearer ...` in the connection;
3. publishes an Agent version containing only `project_connection_id`;
4. opens the new Agent in Live session.

The token is never returned to the browser, written to the Agent definition,
placed in a URL, or logged. The signed-in identity needs permission to write
connections as well as publish Agents in the selected Foundry account.

## Remote-SSH and port forwarding

The default port is `8097`, separate from the legacy dashboard ports `8095`
and `8096`.

1. On the remote Linux host, verify the service:

   ```bash
   curl -sS http://127.0.0.1:8097/healthz
   ```

2. In the same VS Code Remote-SSH window, open **PORTS** and forward remote
   port `8097`.
3. Open the exact **Forwarded Address** shown by VS Code. If local port `8097`
   is occupied, VS Code may choose a different local port.
4. Verify from the local browser, not only from the Remote-SSH terminal.

Microphone capture requires a secure browser context. `http://localhost` is
treated as secure; a raw remote-host HTTP address usually is not.

## Local session logs

Every Voice WebSocket session is recorded under:

```text
~/.voice-agent-local-ui/
  server.log
  sessions/<UTC>-<local-session-id>/
    meta.json
    timeline.log
    events.jsonl
```

Use a Code Agent or local file tools to search by run ID, local web ID, Voice
Live `sess_*`, Foundry `conv_*`, or Agent name. Start with `meta.json`, then
read `timeline.log`, and inspect `events.jsonl` only when the timeline does not
explain the failure.

Use [04: Debug a local UI session](../../docs/04_debug_session.md) and the
canonical shared
[`VoiceAgent/skills/debug-local-session`](../../skills/debug-local-session/)
Skill for Project/model, Agent version, connection, MCP, UI bridge, and session
failures. From `VoiceAgent`, start with:

```bash
python skills/debug-local-session/scripts/analyze_session.py --list
python skills/debug-local-session/scripts/analyze_session.py <session-id>
```

Audio payloads are counted and coalesced rather than written as base64. Token
level `*.delta` frames are omitted because their completed `.done` event
contains the assembled text. Session, handoff, completed transcript, tool,
usage, and error frames remain in `events.jsonl`; `timeline.log` promotes the
events most useful for debugging.

Set `LOCAL_UI_DATA_DIR` or pass `--data-dir` to use another fixed location.
`server.log` rotates at 5 MiB with three backups. Session directories currently
have no automatic retention policy and may contain customer transcript/tool
data, so protect and clean the directory according to the customer's data
handling requirements.

## Template publication

Publishing creates and enables a new immutable Agent version. Both Finance
examples contain MCP tools, so the page reads:

- the public MCP server HTTPS URL;
- the Project connection ID that holds its credential.

No MCP secret is accepted from or stored in the browser. The local server uses
the ignored token file to upsert the fixed connection in the currently
selected Foundry account before publishing.

Every Agent created from Templates uses the required `gft-` prefix, short for
`generated_from_template`. A requested name such as `my-finance-agent` is
published as `gft-my-finance-agent`; an existing `gft-` prefix is not repeated.
Foundry Agent names do not allow underscores, so the intended `gft_` spelling
must use the platform-compatible `gft-` form.

## Tests

```bash
.venv/bin/python -m unittest discover -s tests -v
cd web
npm install
npm test
npm run build
```
