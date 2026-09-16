# Voice Agent Local UI

This standalone UI lets a customer select a visible Microsoft Foundry Project,
choose one of its published Voice Agents, run a microphone or text session, inspect live
handoffs, read the transcript and browser-observed latency, and publish a new
Agent from a sample template.

## What the UI includes

- **Live session**: published Agent picker, microphone controls, text fallback,
  live handoff graph, transcript, MCP activity, TTFT, TTFA, and token usage.
- **Templates**: a configuration-driven catalog. The checked-in config points
  to the sibling Finance Example and Finance with OTP and Officer Search
  samples; Finance Example demonstrates the multi-node handoff view.
- **Project selection**: the header lists Foundry Projects visible to the
  current Azure identity. Switching Project reloads its published Voice Agents.
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
selector in the page header to switch to another Project visible to the same
identity. Project discovery uses Azure Resource Graph and requires Reader
access; invoking an Agent also requires the corresponding data-plane access.

For one-click **Try it now**, put the scoped trial MCP tokens in the local
`.env` variables shown in [`.env.example`](./.env.example). If a token is not
configured, the Templates page asks for it once in a password field.

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
`agent.json`. The server reads only that Agent JSON; it does not read the
sibling `.env`, README, validation output, or credentials. Resolved paths must
remain under `VoiceAgent/samples/`, including after symlink resolution.

Optional presentation fields are `name`, `category`, `summary`, `accent_color`,
and `enabled`. Without them, the UI uses the Agent document's `name` and
`description` plus neutral defaults.

Set `LOCAL_UI_TEMPLATE_CONFIG` or pass `--template-config` to use a different
allowlist without changing code. The Templates **Reload** button re-reads both
the config and every enabled `agent.json`.

Each MCP template also declares a trusted public `mcp.server_url` and a
`mcp.token_env`. On **Try it now**, the local server:

1. reads the token from its environment or the one-time password field;
2. creates a unique `RemoteTool` / `CustomKeys` connection in the selected
   Foundry account, storing `Authorization: Bearer ...` in the connection;
3. publishes an Agent version containing only `project_connection_id`;
4. opens the new Agent in Live session.

The token is never returned to the browser, written to the Agent definition,
placed in a URL, logged, or saved locally. The resulting Foundry connection is
persistent so the published Agent continues to work. Use a distinct,
pack-scoped, revocable trial token per customer; do not distribute a shared
production token. The signed-in identity needs permission to write account
connections as well as publish Agents.

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
examples contain MCP tools, so the page requires:

- the public MCP server HTTPS URL;
- the Project connection ID that holds its credential.

No MCP secret is accepted or stored by this UI.

## Tests

```bash
.venv/bin/python -m unittest discover -s tests -v
cd web
npm install
npm test
npm run build
```
