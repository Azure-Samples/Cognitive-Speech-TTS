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
- This repository includes the `azure-ai-projects` wheel built from the
  [Azure SDK for Python vnext branch](https://github.com/Azure/azure-sdk-for-python/tree/feature/azure-ai-projects/vnext/sdk/ai/azure-ai-projects).
  See [the SDK build record](dist/README.md) for its source commit and checksum.
- A microphone, speakers or headset, and PortAudio for the audio samples.

## Set up

Run from this directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r samples\requirements.txt
Copy-Item samples\.env.example samples\.env
```

The single `pip install` command installs every sample dependency, including
the bundled private-preview wheel under `dist/`. No Azure SDK source checkout
is required.

These samples require the bundled SDK, not a PyPI build with the same version
number. If reusing an environment that already has `azure-ai-projects` 2.6.1,
replace it explicitly:

```powershell
python -m pip install --force-reinstall --no-deps .\dist\azure_ai_projects-2.6.1-py3-none-any.whl
```

Set the project endpoint in `samples/.env`:

```dotenv
AZURE_VOICE_AGENTS_ENDPOINT=https://<account>.services.ai.azure.com/api/projects/<project>
AZURE_VOICE_AGENTS_MODEL=gpt-realtime
```

## Samples

| File | Lifecycle |
| --- | --- |
| `samples/simple_rest_lifecycle.py` | Create a simple agent with REST, or retrieve an existing agent. |
| `samples/basic_voice_agent.py` | Create and version a basic agent, or connect to an existing agent, then converse through the microphone. |
| `samples/voice_agent_with_mcp.py` | Create an MCP agent, converse through the microphone, and display tool arguments/output. |
| `samples/voice_agent_with_foundry_iq.py` | Create a Foundry IQ agent, converse through the microphone, and display tool arguments/output. |
| `samples/voice_agent_with_local_function.py` | Execute `add_numbers` in the client, return its output, and hear the response. |
| `samples/voice_agent_with_toolbox.py` | Create a Toolbox agent, converse through the microphone, and display tool arguments/output. |
| `samples/download_conversation_artifacts.py` | Download conversation JSON, per-turn WAV files, and the merged stereo WAV. |
| `samples/download_conversation_traces.py` | Download correlated Application Insights rows by conversation id. |

Reusable AI coding skills are under `skills/`:

- `voice-agent-private-preview` creates and tests private-preview voice agents.
- `provision-foundry-iq` creates a Foundry IQ knowledge base from local files
  and returns its MCP URL and Foundry project connection ID.
- `provision-foundry-toolbox` creates an Azure AI Search index from local files
  and returns the new Foundry Toolbox name and immutable version.

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

The REST sample puts the agent name in the URL and sends the description and
definition to the same version-creation endpoint used by the SDK:

```text
POST <project-endpoint>/agents/<agent-name>/versions?api-version=v1
Authorization: Bearer <Microsoft Entra token>
Foundry-Features: VoiceAgents=V1Preview
Content-Type: application/json
```

```powershell
python samples\simple_rest_lifecycle.py
```

### Basic agent: create, version, and microphone chat

The basic sample uses `VoiceAgentDefinition` and the audio/tool models from
`azure.ai.projects.models`. It creates an agent version through
`AIProjectClient` with preview features enabled:

```python
from azure.ai.projects.aio import AIProjectClient

async with AIProjectClient(
    endpoint=endpoint,
    credential=credential,
    allow_preview=True,
) as client:
    version = await client.agents.create_version(
        agent_name=agent_name,
        definition=definition,
    )
```

To update the definition, call `client.agents.create_version` again with the
same agent name. The returned version identifier is `version.version`.
Retrieve an existing agent with `client.agents.get(agent_name=agent_name)`.
The SDK supplies the management preview header; the Voice Live WebSocket
connection still supplies `Foundry-Features: VoiceAgents=V1Preview` explicitly.

Audio output uses a voice-name string and a separate `voice_type`, for example
`VoiceAgentAudioOutputConfig(voice="en-US-AvaNeural",
voice_type=VoiceType.AZURE_STANDARD)`.

Microphone samples use `RealtimeServerEventType` from `azure.ai.projects.models`
for event dispatch, including `SESSION_CREATED` and `RESPONSE_OUTPUT_AUDIO_DELTA`.
They follow the new Voice Agent protocol, without legacy audio-event aliases.

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

Microphone samples capture the top-level `conversation_id` from the
`session.created` event and print it when the session ends. They do not
automatically read persisted data. Copy the printed agent name and conversation
id and run:

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
    ├── 002_agent_<item-id>.wav
    └── ...
```

- `conversation.json` contains the conversation envelope, responses, ordered
  items, and audio metadata.
- `turns/` contains every persisted user and assistant audio segment.
- `merged.wav` is the final stereo recording: caller on the left channel and
  agent on the right.

Set `AZURE_VOICE_AGENTS_OUTPUT_DIR` in `.env` to change the output directory.
For bring-your-own storage, the JSON manifest records the returned blob URIs
(`blob_uri`) instead of downloading WAV data through the service.

The downloader uses `client.beta.voice_agents.conversations` for conversation
metadata, item/response listing, and audio downloads. These beta operations
automatically send the voice-agent preview header.

Conversation and audio download requires the agent to have been created with
`store=true`. All agents created by these samples enable it.

## Validate without Azure access

With the sample dependencies installed, run from this directory:

```powershell
python -m compileall -q samples skills
python -m unittest discover -s tests -v
```

The tests exercise the bundled SDK's request serialization, preview headers,
agent versioning, and conversation/audio downloads with a mocked transport.
They do not create Azure resources or open the microphone.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| `401` or `403` | Sign in again and confirm project access. |
| `404` during create or connect | Confirm preview enablement and region support. |
| Model not found | Set a voice-capable managed model or Foundry deployment. |
| MCP or Foundry IQ call fails | Verify the connection target, credential, and service reachability. |
| Microphone sample cannot start | Install PortAudio and `pyaudio`, then confirm microphone permission. |
| Trace query returns `403` | Grant the signed-in identity permission to query the Application Insights resource or its linked Log Analytics workspace. |

Never place access tokens, API keys, or connection secrets in source files.
Use Foundry project connections or environment-based credentials.
