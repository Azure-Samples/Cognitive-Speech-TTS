# Foundry GPT Live with the OpenAI Python SDK

An English-teacher voice sample that creates or reuses an agent in an existing
Foundry project, streams microphone audio through the OpenAI Live SDK, and displays
user/agent transcripts. The Agent area has separate **GPT Live** and **Delegation**
panes; delegation IDs, status, and guidance appear in the Delegation pane.

## Files

| File | Description |
| --- | --- |
| `foundry_gpt_live_openai_sdk.py` | Checks deployments, runs the voice conversation, and prints its ID and download command. |
| `audio_common.py` | Captures microphone audio and plays the agent's response. |
| `transcript_common.py` | Independently scrollable GPT Live, Delegation, and User terminal panes. |
| `../download_conversation_artifacts.py` | Existing separate downloader for conversation JSON, per-item audio, and merged audio. |
| `requirements.txt` | Required Python packages and versions. |
| `.env.example` | Configuration template. |
| `.env` | Your local project, agent, deployment, and subscription settings; git-ignored. |
| `.gitignore` | Excludes credentials, the virtual environment, and recordings. |

## How to run

Requires Python 3.11+, Azure CLI, a microphone/headset, and a Foundry project with the
Voice Agents / GPT Live preview, a GPT Live deployment, and a Responses deployment.
On Linux, install the PortAudio runtime (`libportaudio2` on Ubuntu/Debian).

Use the shared `VoiceAgent/.venv`. From the repository root, in PowerShell:

```powershell
Set-Location VoiceAgent
az login
if (-not (Test-Path -LiteralPath .venv\Scripts\python.exe)) { python -m venv .venv }
.\.venv\Scripts\python.exe -m pip install --index-url https://pypi.org/simple -r samples\requirements.txt -r samples\gpt_live\requirements.txt
if (-not (Test-Path -LiteralPath samples\gpt_live\.env)) { Copy-Item samples\gpt_live\.env.example samples\gpt_live\.env }
```

In `samples/gpt_live/.env`, set `FOUNDRY_PROJECT_ENDPOINT`. Authentication uses
your `az login` account through `AzureCliCredential`, with automatically refreshed
Entra tokens for REST and the Live WebSocket handshake. No API keys or manually
copied tokens are needed. If you have multiple signed-in subscriptions, set
`AZURE_SUBSCRIPTION_ID` to select the right account without changing the CLI default.

To use an existing GPT Live agent, set `AGENT_NAME=your-agent-name` in `.env`.
Its latest version and saved configuration are used without creating, updating,
or deleting the agent. The deployment variables below are ignored in this mode.

Leave `AGENT_NAME` blank to create a new English-teacher agent, and configure both
deployments:

```dotenv
GPT_LIVE_DEPLOYMENT=YOUR-GPT-LIVE-DEPLOYMENT
GPT_LIVE_DELEGATION_DEPLOYMENT=YOUR-DELEGATION-DEPLOYMENT
```

Both names are required for new agents. Existing agents' saved deployments are
checked instead. The sample does not create deployments. Never commit `.env`.

Run:

```powershell
.\.venv\Scripts\python.exe samples\gpt_live\foundry_gpt_live_openai_sdk.py
```

Wait for **Ready**, speak into your microphone, and press **Ctrl+C** to stop.
Text starts at the top of each pane and fills downward.
Scroll each pane with the mouse wheel, or use **Tab / Shift+Tab** to focus it and
**arrows / PgUp / PgDn / Home** to scroll. **End** resumes following new text.
Scrolling one pane does not move the others; full history remains after exit.
New agents are kept by default; add `--auto-delete` to delete only an agent created
by this run. Existing agents are never deleted, even with `--auto-delete`.

New agents are created with `store=True`. When `AGENT_NAME` is set, the existing
agent's storage policy is left as-is; no session override or agent update is sent.
After close, if a persisted conversation ID is returned,
the sample prints the Foundry conversation ID and a command for the existing
`samples/download_conversation_artifacts.py`; it does not download anything itself.
Run that command from `VoiceAgent`, with `AZURE_VOICE_AGENTS_ENDPOINT` set to the
same value as `FOUNDRY_PROJECT_ENDPOINT`. The separate downloader waits for
persistence and saves JSON and audio to `voice-agent-output/<conversation-id>/`.
Keep the agent (omit `--auto-delete`) if you want to download later.

On macOS/Linux, also run from `VoiceAgent`: use `python3` to create `.venv` if
needed, `.venv/bin/python` for install/run commands, and `/` path separators.
Keep `.env` beside the sample, not in the shared environment directory.
