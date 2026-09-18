---
ai-usage: ai-assisted
---

# Hosted GitHub Copilot subagent

Create a voice agent that delegates research, analysis, learning, and coding
tasks to an existing hosted GitHub Copilot agent, then talk using the
Projects SDK-based microphone client.

The hosted-agent implementation comes from the
[GitHub Copilot Responses VoiceLive sample](https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/python/hosted-agents/bring-your-own/voicelive/github-copilot-responses-voicelive).
This folder only references that deployed agent; it does not copy, deploy,
modify, or delete the hosted implementation.

## Prerequisites

- Python 3.10 or later.
- Azure CLI authenticated with `az login`, or another credential supported by
  `DefaultAzureCredential`.
- A Foundry project with voice agents enabled and access to a managed realtime
  voice model.
- Permission to create and delete agents in that project.

## 1. Deploy the hosted agent

Follow the deployment and role-assignment instructions in the
[hosted-agent sample](https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/python/hosted-agents/bring-your-own/voicelive/github-copilot-responses-voicelive).
Deploy it to the same Foundry project used here and record its deployed name.
If it is already deployed and running, reuse it.

## 2. Configure

From this folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

On Windows PowerShell, use `.venv\Scripts\Activate.ps1` and
`Copy-Item .env.example .env`.

The requirements pin **`azure-ai-projects==2.7.0a20260906001`** from the
[public Azure SDK feed](https://pkgs.dev.azure.com/azure-sdk/public/_packaging/azure-sdk-for-python/pypi/simple/azure-ai-projects/),
matching the prompt-basic sample. The direct wheel URL and SHA-256 select
that exact development preview build without changing the package index for
other dependencies. Its APIs may change; use this sample's own environment.

Edit `.env`:

- `PROJECT_ENDPOINT`: the project containing both agents.
- `VOICE_MODEL_DEPLOYMENT`: the managed realtime model name, such as `gpt-realtime`.
- `HOSTED_SUBAGENT_NAME`: the already-deployed GitHub Copilot agent name.
- `VOICE_NAME`: the Azure Speech voice used for output.

This script does not deploy models or hosted agents.

## 3. Create the voice agent

```bash
python create_voice_agent.py
```

The scenario definition and SDK call are visible in `create_voice_agent.py`:

```python
with AIProjectClient(
    endpoint=endpoint,
    credential=credential,
    allow_preview=True,
) as project:
    agent = project.agents.create_version(
        agent_name=voice_agent_name,
        definition=voice_definition(voice_model, hosted_agent_name, voice),
    )
```

The typed `VoiceAgentDefinition` references the existing hosted agent through
`VoiceAgentSubagent(agent_name=hosted_agent_name, ...)`, with
`VoiceAgentSubagentResponsePolicy(immediate_ack=True)` on that entry.
`allow_preview=True` enables the SDK's preview feature headers.

Each run generates a unique voice-agent name and creates its first version.
Keep the printed name and cleanup command. If creation fails after the
service has accepted the request, run that cleanup command explicitly.
The hosted agent remains untouched.

## 4. Talk

Set up the shared [microphone client](../client/README.md), including its
`requirements.txt` dependencies. From this folder on Linux/macOS:

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

The client uses `project.realtime.connect()` and the saved voice-agent
configuration. PyAudio captures and plays audio locally. It displays
transcripts and subagent lifecycle events; press `Ctrl+C` to disconnect.

Try "Explain Python async functions in simple terms" or "Help me write a
function that removes duplicate strings." For an explicit delegation request,
say "Ask GitHub Copilot to explain Python async functions in simple terms."
Simple questions may be answered directly; look for `Subagent started` and
`Subagent completed` in the client output to see when the hosted agent is used.
The hosted sample can stream short tool-status messages while Copilot works.

## 5. Delete the voice agent

```bash
python delete_voice_agent.py --voice-agent-name <voice-agent-name>
```

This calls `project.agents.delete()` for the supplied voice-agent name and
its versions. Use only the voice-agent name printed by this sample, not the
hosted subagent's name. Missing agents are reported as already deleted;
other errors propagate. Remove the hosted agent separately through its own
deployment workflow only when you no longer need it.
