---
ai-usage: ai-assisted
---

# Basic prompt subagent

Create a poetry prompt agent and a voice agent using typed Foundry SDK models,
talk through the SDK-based microphone client, and explicitly delete the agents
when finished.

## Prerequisites

- Python 3.10 or later.
- Azure CLI authenticated with `az login`, or another credential supported by
  `DefaultAzureCredential`.
- A Foundry project with voice agents enabled, access to a managed realtime
  voice model, and a text-model deployment.
- Permission to create and delete agents in the project.

## 1. Configure

From this folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

On Windows PowerShell, use `.venv\Scripts\Activate.ps1` and
`Copy-Item .env.example .env`.

Edit `.env` with your project endpoint and deployment names.
`SUBAGENT_MODEL_DEPLOYMENT` must be an existing text-model deployment in that
project. Neither script deploys models.

## 2. Create the agents

```bash
python create_agents.py
```

The SDK calls are visible in `create_agents.py`:

```python
with AIProjectClient(
    endpoint=endpoint,
    credential=credential,
    allow_preview=True,
) as project:
    subagent = project.agents.create_version(
        agent_name=subagent_name,
        definition=prompt_definition(subagent_model),
    )
    voice_agent = project.agents.create_version(
        agent_name=voice_agent_name,
        definition=voice_definition(voice_model, subagent_name, voice),
    )
```

`allow_preview=True` enables the SDK's preview feature headers.
`create_version()` creates the first version for each unique generated name;
calling it again with an existing name creates another version.

The definitions use `PromptAgentDefinition`, `VoiceAgentDefinition`, and typed
audio/subagent models, not raw REST dictionaries. Each `VoiceAgentSubagent`
owns its `VoiceAgentSubagentResponsePolicy(immediate_ack=True)`. Output audio
uses `VoiceAgentAudioOutputConfig(voice=voice, voice_type="azure-standard")`.

Keep the printed agent names and cleanup command. If creation fails partway,
the script reports the error and leaves cleanup explicit; run the printed
delete command to remove any agents that were created.

## 3. Talk

Set up the shared [microphone client](../client/README.md), including its
`requirements.txt` dependencies. From this sample folder on Linux/macOS:

```bash
../client/.venv/bin/python ../client/voice_client.py \
  --project-endpoint <project-endpoint> \
  --agent-name <voice-agent-name>
```

On Windows PowerShell:

```powershell
..\client\.venv\Scripts\python.exe ..\client\voice_client.py --project-endpoint <project-endpoint> --agent-name <voice-agent-name>
```

Use the printed launch command, which includes your project endpoint and
voice-agent name. No `.env` file is needed by the client; keep it for creation
and deletion.

The client uses the async Projects SDK's `project.beta.voice_agents.realtime.connect()` for
voice conversations, including microphone input and typed audio events.
PyAudio still captures and plays audio locally; it belongs to the client
environment, not this provisioning environment.

Try "What can you help me with?" followed by "Write a short poem about the
sea." The voice agent describes its poetry capability briefly and delegates
poem writing. Press `Ctrl+C` to disconnect.

## Write effective voice-agent instructions

Give the voice agent a focused identity and describe when it should ask the
subagent for help. Keep spoken responses concise and capability-focused;
do not advertise unrelated skills or expose internal tool and agent names.
The subagent's `agent_capabilities` should match what it actually does.

This sample enables only `immediate_ack` so users hear a brief acknowledgement
while the poem is prepared. More advanced scenarios can add gap filling or
progress updates; those messages should describe only known information.

## 4. Delete

```bash
python delete_agents.py \
  --voice-agent-name <voice-agent-name> \
  --subagent-name <subagent-name>
```

This uses `project.agents.delete()` to delete the named agents and their
versions. Missing agents are reported as already deleted; other errors
propagate. Only delete names printed by this sample that you no longer need.
