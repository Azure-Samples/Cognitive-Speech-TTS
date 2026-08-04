# Voice agents private preview

Voice agents now are available in `swedencentral` and `francecentral` regions.

## Prerequisites

- Python 3.10 or later.
- An Azure AI Foundry project endpoint:
  `https://<account>.services.ai.azure.com/api/projects/<project>`.
- Provide the Azure subscription ID that contains the Foundry project to the
  Voice Agent team, and wait for confirmation that the subscription has been
  allowlisted for the private preview.
- Azure CLI sign-in (`az login`) or another `DefaultAzureCredential` identity.
- Install the [private-preview](https://github.com/Azure/azure-sdk-for-python/tree/xitzhang/prompt-voice-agent-private-preview/sdk/voiceagents/azure-ai-voiceagents) `azure-ai-voiceagents` package from the
  Azure SDK for Python preview branch.
- A microphone, speakers or headset, and PortAudio for the audio samples.

## Set up

Run from this directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r samples\requirements.txt
Copy-Item samples\.env.example samples\.env
```

Set the project endpoint in `samples/.env`:

```dotenv
AZURE_VOICE_AGENTS_ENDPOINT=https://<account>.services.ai.azure.com/api/projects/<project>
AZURE_VOICE_AGENTS_MODEL=gpt-realtime
```

## Samples

| File | Lifecycle |
|---|---|
| `samples/simple_rest_lifecycle.py` | Create a simple agent with REST, or retrieve an existing agent. |
| `samples/basic_voice_agent.py` | Create and patch a basic agent, or connect to an existing agent, then converse through the microphone. |
| `samples/voice_agent_with_mcp.py` | Create an MCP agent, converse through the microphone, and display tool arguments/output. |
| `samples/voice_agent_with_foundry_iq.py` | Create a Foundry IQ agent, converse through the microphone, and display tool arguments/output. |
| `samples/voice_agent_with_local_function.py` | Execute `add_numbers` in the client, return its output, and hear the response. |
| `samples/voice_agent_with_toolbox.py` | Create a Toolbox agent, converse through the microphone, and display tool arguments/output. |
| `samples/download_conversation_artifacts.py` | Download conversation JSON, per-turn WAV files, and the merged stereo WAV. |
| `samples/download_conversation_traces.py` | Download correlated Application Insights rows by conversation id. |

The reusable AI coding skill is under
`skills/voice-agent-private-preview`.


## Run the agent samples

Run a sample without an agent-name argument to create a new agent. Pass an
existing agent name to skip creation and use its stored model, audio,
instructions, and tools:

```powershell
python samples\<sample-name>.py
python samples\<sample-name>.py <agent-name>
```

You can alternatively set `AZURE_VOICE_AGENTS_AGENT_NAME` in `.env`.

### Simple REST creation

The REST sample sends the agent name, description, and definition to:

```text
POST <project-endpoint>/voice_agents?api-version=v1
Authorization: Bearer <Microsoft Entra token>
Foundry-Features: VoiceAgents=V1Preview
Content-Type: application/json
```

```powershell
python samples\simple_rest_lifecycle.py
```

### Basic agent: create, patch, and microphone chat

The basic sample creates an agent through the Python SDK:

```python
client.voice_agents.create_voice_agent(
    name=agent_name,
    definition=definition,
    foundry_features=AgentDefinitionOptInKeys.VOICE_AGENTS_V1_PREVIEW,
)
```

Updating its definition creates a new immutable version.

```powershell
python samples\basic_voice_agent.py
```

### MCP with live microphone audio

The MCP tool references a Foundry project connection that stores the target and
authentication configuration:

```json
{
  "type": "mcp",
  "server_label": "my-mcp-server",
  "project_connection_id": "<project-connection-id>",
  "require_approval": "never"
}
```

Do not put MCP credentials in the agent definition.

Create a Foundry project connection for the MCP server, then set:

```dotenv
AZURE_VOICE_AGENTS_MCP_CONNECTION_ID=<project-connection-id>
AZURE_VOICE_AGENTS_MCP_SERVER_LABEL=my-mcp-server
```

Run:

```powershell
python samples\voice_agent_with_mcp.py
```

Speak a request that the MCP tools can answer. Press Ctrl-C to finish. The
sample prints the persisted conversation id.

### Foundry IQ with live microphone audio

A Foundry IQ knowledge base is represented as an MCP tool with its
knowledge-base URL and project connection:

```json
{
  "type": "mcp",
  "server_label": "foundry-iq",
  "server_url": "https://<search-service>.search.windows.net/knowledgebases/<knowledge-base>/mcp?api-version=<version>",
  "project_connection_id": "<project-connection-id>",
  "require_approval": "never"
}
```

Create a Foundry IQ knowledge base and a project connection that can access it:

```dotenv
AZURE_VOICE_AGENTS_FOUNDRY_IQ_URL=https://<search-service>.search.windows.net/knowledgebases/<knowledge-base>/mcp?api-version=<version>
AZURE_VOICE_AGENTS_FOUNDRY_IQ_CONNECTION_ID=<project-connection-id>
```

Run:

```powershell
python samples\voice_agent_with_foundry_iq.py
```

Ask a question covered by the knowledge base. Use a headset to reduce echo;
talk over the agent to test barge-in and press Ctrl-C to finish.

### Client-executed local function

A `function` tool is executed by the connected client. The client receives the
function name and JSON arguments, runs local application code, sends a
`function_call_output` conversation item, and requests the model's follow-up
response.

```powershell
python samples\voice_agent_with_local_function.py
```

Say: **“Add 5 and 7. You must use the add_numbers function.”** The sample
prints the arguments, executes Python locally, prints `{"sum": 12.0}`, returns
the result to the session, and plays the spoken answer.

### Foundry Toolbox

A `toolbox` tool references a versioned Foundry Toolbox:

```json
{
  "type": "toolbox",
  "toolbox_name": "voice-agent-toolbox-azure-search",
  "toolbox_version": "1"
}
```

Toolbox calls are surfaced through MCP events, allowing clients to display the
tool name, arguments, and structured output.

The local `.env` uses the existing
`voice-agent-toolbox-azure-search` toolbox, version `1`.

```powershell
python samples\voice_agent_with_toolbox.py
```


## Tracing and evaluation in Azure AI Foundry

When the conversation ends, click the URL printed in the terminal log to view
the trace in the Azure AI Foundry portal and run evaluations.

## Download conversation and audio

Microphone samples do not automatically read persisted data. After a session,
copy the printed agent name and conversation id and run:

```powershell
python samples\download_conversation_artifacts.py <agent-name> <conversation-id>
```

The downloader waits for persistence to complete and writes:

```text
voice-agent-output/<conversation-id>/
├── conversation.json
├── merged.wav
└── turns/
    ├── 001_user_<item-id>.wav
    ├── 002_assistant_<item-id>.wav
    └── ...
```

- `conversation.json` contains the conversation envelope, responses, ordered
  items, and audio metadata.
- `turns/` contains every persisted user and assistant audio segment.
- `merged.wav` is the final stereo recording: caller on the left channel and
  agent on the right.

Set `AZURE_VOICE_AGENTS_OUTPUT_DIR` in `.env` to change the output directory.
For bring-your-own storage, the JSON manifest records the returned blob paths
instead of downloading WAV data through the service.

Conversation and audio download requires the agent to have been created with
`store=true`. All agents created by these samples enable it.


## Troubleshooting

| Symptom | Action |
|---|---|
| `401` or `403` | Sign in again and confirm project access. |
| `404` during create or connect | Confirm preview enablement and region support. |
| Model not found | Set a voice-capable managed model or Foundry deployment. |
| MCP or Foundry IQ call fails | Verify the connection target, credential, and service reachability. |
| Microphone sample cannot start | Install PortAudio and `pyaudio`, then confirm microphone permission. |
| Trace query returns `403` | Grant the signed-in identity permission to query the Application Insights resource or its linked Log Analytics workspace. |

Never place access tokens, API keys, or connection secrets in source files.
Use Foundry project connections or environment-based credentials.
