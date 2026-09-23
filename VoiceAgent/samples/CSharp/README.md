# Foundry voice agent C# sample

This standalone console application uses the published
[`Azure.AI.Projects`](https://www.nuget.org/packages/Azure.AI.Projects/3.0.0-beta.3)
and [`Azure.AI.Projects.Agents`](https://www.nuget.org/packages/Azure.AI.Projects.Agents/3.0.0-beta.3)
**3.0.0-beta.3** preview SDK packages. It is adapted
from the SDK's `Sample_VoiceAgent.cs` test fixture; no Azure SDK source checkout,
NUnit, or internal test framework is required.

The [walkthrough](Sample_VoiceAgent.md) explains agent creation and management,
Realtime WebSocket events, Azure voice pitch updates, the `end_conversation`
system tool, concurrent PCM audio streaming, and persisted conversations and
recordings. The complete implementation is in
[Sample_VoiceAgent.cs](Sample_VoiceAgent.cs).

## Prerequisites

- .NET 8 SDK or later.
- An Azure AI Foundry project endpoint:
  `https://<account>.services.ai.azure.com/api/projects/<project>`.
- Azure CLI sign-in (`az login`) or another `DefaultAzureCredential` identity
  with access to the project.
- A voice-capable model deployment or access to a service-managed voice model
  such as `gpt-realtime`.

No microphone, speaker, PortAudio, or Python installation is needed. This
sample sends a text turn and receives audio, then streams an audio turn using
a file or the temporary agent's first response. It does not play audio through
your speakers. For interactive microphone chat, use the
[Python samples](../README.md#run-the-agent-samples).

## Set up and run

From the repository root, in PowerShell:

```powershell
cd VoiceAgent\samples\CSharp
dotnet restore --configfile .\NuGet.Config
dotnet build --no-restore
az login

$env:FOUNDRY_PROJECT_ENDPOINT = "https://<account>.services.ai.azure.com/api/projects/<project>"
$env:FOUNDRY_VOICE_MODEL_TYPE = "managed"
$env:FOUNDRY_VOICE_MODEL_NAME = "gpt-realtime"

dotnet run --no-build
```

This creates a uniquely named temporary agent, exercises its lifecycle, and
deletes it in a `finally` block, including when a later operation fails. An
abrupt process termination can prevent cleanup; the agent name is printed so
you can remove it manually if needed. For a self-deployed model, set
`FOUNDRY_VOICE_MODEL_TYPE` to `self-deployed` and `FOUNDRY_VOICE_MODEL_NAME` to
your voice-capable deployment name.

To use an existing voice agent instead:

```powershell
$env:FOUNDRY_VOICE_AGENT_NAME = "<existing-voice-agent-name>"
dotnet run --no-build
```

Existing-agent mode uses the latest version without creating, disabling,
enabling, changing the stored definition, or deleting the agent. It does not
apply the temporary agent's pitch update. It still starts new conversations,
sends test prompts, and persists their transcripts and audio. Use an agent
configured for audio output; if supplying an input file, its session must accept
PCM16 mono at 24 kHz with server-side turn detection.

**Privacy:** Both modes set `Store = true` for the sessions so the sample can
read persisted conversations and recordings. Only send data you intend to
persist. Authentication uses Microsoft Entra ID; never put credentials in
source files.

## Configuration

This C# sample reads process environment variables, not the Python samples'
`.env` file or their `AZURE_VOICE_AGENTS_*` variables.

| Variable | Purpose |
| --- | --- |
| `FOUNDRY_PROJECT_ENDPOINT` | Required Foundry project HTTPS endpoint. |
| `FOUNDRY_VOICE_AGENT_NAME` | Optional existing agent name. Omit to create a temporary agent. |
| `FOUNDRY_VOICE_MODEL_NAME` | Model or deployment name for a new agent. Falls back to `FOUNDRY_MODEL_NAME`. Not required for an existing agent. |
| `FOUNDRY_VOICE_MODEL_TYPE` | `managed` or `self-deployed`; defaults to `self-deployed` for a new agent. |
| `FOUNDRY_VOICE_INPUT_AUDIO_PATH` | Optional raw, headerless PCM16 little-endian, mono, 24 kHz input file. WAV/MP3 files must be converted first. |
| `FOUNDRY_VOICE_OUTPUT_AUDIO_PATH` | Output file for the streamed response. Defaults to a unique `.pcm` file in the system temporary directory. An existing file at an explicit path is overwritten. |

For a temporary agent, omitting the input file reuses its first spoken response
as input. For an existing agent, the audio-input demonstration runs only when
an input file is supplied. The default temporary agent returns PCM16 mono at
24 kHz; an existing agent retains its configured output format.

The sample logs service events and persisted conversation IDs, downloads
whole-conversation and per-item WAV recordings into memory, and reports their
sizes. With bring-your-own storage, it reports the returned blob URI instead
of downloading audio. The streaming response is the only audio saved to disk;
it is raw audio, not a WAV file. Service errors, incomplete responses, and
unexpected session closure fail the run.

After building, use `dotnet run --no-build -- --help` to display configuration
without connecting to Azure.

## NuGet SDK packages

[`VoiceAgentSamples.csproj`](VoiceAgentSamples.csproj) pins both
`Azure.AI.Projects` and `Azure.AI.Projects.Agents` to the published
**3.0.0-beta.3** preview release. `AIProjectClient.ProjectsRealtimeClient`
opens the voice session using OpenAI's `RealtimeSessionClient` command and
event APIs. `AgentAdministrationClient` manages agents, and
`BetaVoiceAgentsConversations` retrieves persisted conversations and recordings.

The project also pins the published `Azure.AI.Extensions.OpenAI`
**3.0.0-beta.1** dependency rather than relying on the alpha minimum declared
by the Projects packages. `Azure.Identity` provides authentication.

[`NuGet.Config`](NuGet.Config) restores all dependencies from NuGet.org.
Its sample-local `.packages/nuget.org` cache keeps the published SDK separate
from the former bundled build, which used the same version in `.packages`.
No local `.nupkg` or Azure SDK source checkout is required.

If you previously ran the bundled preview sample, rerun the restore and build
commands above before using `dotnet run --no-build`. Use the explicit
`--configfile .\NuGet.Config` restore command and keep its isolated cache path
so the old bundled package cannot be reused.
