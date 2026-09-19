# Voice Agent samples

> [!IMPORTANT]
> Every future example intended for the portal Templates page must follow
> [Add an example to Portal Templates](./PORTAL_TEMPLATE_EXAMPLES.md). New
> sample directories are not discovered automatically; they require the
> documented portable `agent.json`, explicit allowlist entry, security rules,
> tests, and source-sync update when applicable.

## Conclusion

This directory owns the runnable Python, .NET, Finance, Knowledge IQ, and avatar
samples. Use the common setup below for the top-level Python
scripts. The Finance directories and C# application have separate dependencies
and their own documentation.

For the general browser UI, use the
[`portal/`](../portal/README.md) instead. For the complete Finance sample,
shared MCP, and portal workflow, start with the
[Finance documentation index](../docs/README.md).

## Choose a sample

| Sample | Lifecycle |
| --- | --- |
| [Knowledge, Andrew Dragon HD, and Harry Business](create-agent-with-iq-avatar-voice/README.md) | Portal creation is recommended; optional Python validation/create/readback is included. Supports optional custom photo avatar and Personal Voice workflows. |
| [`simple_rest_lifecycle.py`](simple_rest_lifecycle.py) | Create a simple Agent with REST, or retrieve an existing Agent. |
| [`basic_voice_agent.py`](basic_voice_agent.py) | Create and version a basic Agent, or connect to an existing Agent, then converse through the microphone. |
| [`voice_agent_with_mcp.py`](voice_agent_with_mcp.py) | Create an MCP Agent, converse through the microphone, and display tool arguments and output. |
| [`voice_agent_with_foundry_iq.py`](voice_agent_with_foundry_iq.py) | Create a Foundry IQ Agent, converse through the microphone, and display tool activity. |
| [`voice_agent_with_local_function.py`](voice_agent_with_local_function.py) | Execute `add_numbers` in the client, return its output, and hear the response. |
| [`voice_agent_with_toolbox.py`](voice_agent_with_toolbox.py) | Create a Toolbox Agent, converse through the microphone, and display tool activity. |
| [Basic prompt subagent](subagent/voice-subagent-prompt-basic/README.md) | Create a poetry prompt subagent and a voice agent that delegates poem writing to it. |
| [Hosted GitHub Copilot subagent](subagent/voice-subagent-hosted-agent/README.md) | Create a voice agent that delegates research, learning, and coding tasks to an existing hosted GitHub Copilot agent. |
| [Finance with Handoff](example1_finance_with_handoff/README.md) | Publish a Finance Realtime handoff graph and run a text Voice WebSocket smoke test. |
| [Finance with OTP and Officer Search](example2_finance_with_OTP_and_Officer_Search/README.md) | Publish a flat Finance Agent for OTP verification and loan-officer search, then run a text smoke test. |
| [C# voice agent sample](CSharp/README.md) | Create and manage a temporary Agent or use an existing Agent, stream audio over WebSocket, and read persisted conversations and recordings. |
| [`download_conversation_artifacts.py`](download_conversation_artifacts.py) | Download conversation JSON, per-turn WAV files, and the merged stereo WAV. |
| [`download_conversation_traces.py`](download_conversation_traces.py) | Download correlated Application Insights rows by conversation ID. |

The two Finance directory samples use their own `requirements.txt` files.
All Python samples require `azure-ai-projects>=2.7.0` from PyPI.

## Common Python sample prerequisites

- Python 3.10 or later.
- An Azure AI Foundry Project endpoint:
  `https://<account>.services.ai.azure.com/api/projects/<project>`.
- Azure CLI sign-in (`az login`) or another `DefaultAzureCredential` identity.
- A microphone, speakers or headset, and PortAudio for the audio samples.
- Azure AI Projects SDK 2.7.0 or later, installed by the requirements below.

## Common Python sample setup

Run these commands from the parent `VoiceAgent` directory.

PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r samples\requirements.txt
Copy-Item samples\.env.example samples\.env
```

Linux, macOS, or WSL2:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r samples/requirements.txt
cp samples/.env.example samples/.env
```

The single `pip install` command installs every common Python sample
dependency, including Projects SDK 2.7.0 or later with its `[voice]`
dependencies. No Azure SDK source checkout or Voice Live SDK is required.

For an existing preview or source installation, rerun the requirements install
command above to replace it with the released SDK.

Set the Project endpoint in `samples/.env`:

```dotenv
AZURE_VOICE_AGENTS_ENDPOINT=https://<account>.services.ai.azure.com/api/projects/<project>
AZURE_VOICE_AGENTS_MODEL=gpt-realtime
```

## Run the agent samples

Run a sample without an Agent-name argument to create a new Agent. Pass an
existing Agent name to skip creation and use its stored model, audio,
instructions, and tools:

```text
python samples/<sample-name>.py
python samples/<sample-name>.py <agent-name>
```

On Linux, macOS, or WSL2, use `.venv/bin/python` if the virtual environment is
not activated. You can alternatively set `AZURE_VOICE_AGENTS_AGENT_NAME` in
`samples/.env`.

### Simple REST creation

The REST sample puts the Agent name in the URL and sends the description and
definition to the same version-creation endpoint used by the SDK:

```text
POST <project-endpoint>/agents/<agent-name>/versions?api-version=v1
Authorization: <Entra token>
Foundry-Features: VoiceAgents=V1Preview
Content-Type: application/json
```

Run:

```text
python samples/simple_rest_lifecycle.py
```

### Basic Agent: create, version, and microphone chat

The basic sample uses `VoiceAgentDefinition` and the audio/tool models from
`azure.ai.projects.models`. It creates an Agent version through
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
same Agent name. The returned version identifier is `version.version`.
Retrieve an existing Agent with `client.agents.get(agent_name=agent_name)`.
The same Projects client opens the Voice Agent realtime session:

```python
async with client.beta.voice_agents.realtime.connect(agent_name=agent_name) as connection:
    await connection.input_audio_buffer.append(audio=pcm_bytes)
    async for event in connection:
        # Handle transcripts, audio, and tool events.
        ...
```

The SDK owns authentication, the Agent WebSocket URL, and the
`Foundry-Features: VoiceAgents=V1Preview` header. No private URL overrides or
Voice Live SDK imports are needed. The Agent's stored definition controls the
session; the samples do not send a replacement `session.update`.

See the upstream [Voice Agent SDK samples](https://github.com/Azure/azure-sdk-for-python/tree/azure-ai-projects_2.7.0/sdk/ai/azure-ai-projects/samples/agents/voice)
for additional realtime usage.

Audio output uses a voice-name string and a separate `voice_type`, for example
`VoiceAgentAudioOutputConfig(voice="en-US-AvaNeural",
voice_type=VoiceType.AZURE_STANDARD)`.

Microphone samples use `RealtimeServerEventType` from
`azure.ai.projects.models` for event dispatch, including `SESSION_CREATED` and
`RESPONSE_OUTPUT_AUDIO_DELTA`. They follow the new Voice Agent protocol,
without legacy audio-event aliases.

```text
python samples/basic_voice_agent.py
```

### MCP with live microphone audio

The MCP tool references a Foundry Project connection that stores the target and
authentication configuration:

```json
{
  "type": "mcp",
  "server_label": "my-mcp-server",
  "project_connection_id": "<project-connection-id>",
  "require_approval": "never"
}
```

Do not put MCP credentials in the Agent definition. Create a Foundry Project
connection for the MCP server, then set:

```dotenv
AZURE_VOICE_AGENTS_MCP_CONNECTION_ID=<project-connection-id>
AZURE_VOICE_AGENTS_MCP_SERVER_LABEL=my-mcp-server
```

Run:

```text
python samples/voice_agent_with_mcp.py
```

Speak a request that the MCP tools can answer. Press Ctrl+C to finish. The
sample prints the persisted conversation ID.

### Foundry IQ with live microphone audio

A Foundry IQ knowledge base is represented as an MCP tool with its
knowledge-base URL and Project connection:

```json
{
  "type": "mcp",
  "server_label": "foundry-iq",
  "server_url": "https://<search-service>.search.windows.net/knowledgebases/<knowledge-base>/mcp?api-version=<version>",
  "project_connection_id": "<project-connection-id>",
  "require_approval": "never"
}
```

Set:

```dotenv
AZURE_VOICE_AGENTS_FOUNDRY_IQ_URL=https://<search-service>.search.windows.net/knowledgebases/<knowledge-base>/mcp?api-version=<version>
AZURE_VOICE_AGENTS_FOUNDRY_IQ_CONNECTION_ID=<project-connection-id>
```

Run:

```text
python samples/voice_agent_with_foundry_iq.py
```

Ask a question covered by the knowledge base. Use a headset to reduce echo;
talk over the Agent to test barge-in and press Ctrl+C to finish.

### Client-executed local function

A `function` tool is executed by the connected client. After the function-call
response's `response.done` event, the sample sends a typed
`RealtimeConversationItemFunctionCallOutput` and requests the model's follow-up
response. Waiting avoids a concurrent-response error.

```text
python samples/voice_agent_with_local_function.py
```

Say: **"Add 5 and 7. You must use the add_numbers function."** The sample
executes Python locally, prints `{"sum": 12.0}`, returns the result to the
session, and plays the spoken answer.

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
tool name, arguments, and structured output. Configure the Toolbox name and
version in `samples/.env`, then run:

```text
python samples/voice_agent_with_toolbox.py
```

## Tracing and evaluation

When a conversation ends, use the URL printed in the terminal log to view the
trace in the Azure AI Foundry portal and run evaluations.

## Download conversation and audio

Microphone samples capture the top-level `conversation_id` from the
`session.created` event and print it when the session ends. Copy the printed
Agent name and conversation ID and run:

```text
python samples/download_conversation_artifacts.py <agent-name> <conversation-id>
```

The downloader waits for persistence to complete and writes:

```text
voice-agent-output/<conversation-id>/
|-- conversation.json
|-- merged.wav
`-- turns/
    |-- 001_user_<item-id>.wav
    |-- 002_agent_<item-id>.wav
    `-- ...
```

- `conversation.json` contains the conversation envelope, responses, ordered
  items, and audio metadata.
- `turns/` contains every persisted user and assistant audio segment.
- `merged.wav` is the final stereo recording: caller on the left channel and
  Agent on the right.

Set `AZURE_VOICE_AGENTS_OUTPUT_DIR` in `samples/.env` to change the output
directory. For bring-your-own storage, the JSON manifest records returned blob
URIs instead of downloading WAV data through the service.

Conversation and audio download requires the Agent to have been created with
`store=true`. All Agents created by these common samples enable it.

## Reusable coding-agent skills

The related workflows are under [`../skills/`](../skills/):

- [`debug-local-session`](../skills/debug-local-session/) resolves and analyzes
  recordings created by the portal.
- [`voice-agent-preview`](../skills/voice-agent-preview/) creates and tests
  Voice Agents with Projects SDK 2.7.0 and its preview voice APIs.
- `provision-foundry-iq` creates a Foundry IQ knowledge base from local files.
- `provision-foundry-toolbox` creates an Azure AI Search index and Foundry
  Toolbox.

## Validate without Azure access

With the common sample dependencies installed, run from `VoiceAgent`:

```text
python -m compileall -q samples skills
python -m unittest discover -s tests -v
```

The tests exercise the released SDK's WebSocket handshake, authentication and
preview headers, PCM serialization, event decoding, function-call ordering,
Agent versioning, and conversation/audio downloads. Only network and microphone
boundaries are mocked; the tests use the real Projects SDK. They do not create
Azure resources or open the microphone.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| `401` or `403` | Sign in again and confirm Project access. |
| `404` during create or connect | Confirm preview enablement and region support. |
| Model not found | Set a voice-capable managed model or Foundry deployment. |
| MCP or Foundry IQ call fails | Verify the connection target, credential, and service reachability. |
| Microphone sample cannot start | Install PortAudio and `pyaudio`, then confirm microphone permission. |
| Trace query returns `403` | Grant the signed-in identity permission to query the Application Insights resource or its linked Log Analytics workspace. |

Never place access tokens, API keys, or connection secrets in source files.
Use Foundry Project connections or environment-based credentials.
