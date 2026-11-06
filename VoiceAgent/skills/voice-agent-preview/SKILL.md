---
name: voice-agent-preview
description: >-
  Create, configure, test, and troubleshoot Azure AI Foundry voice
  agents in preview. Use when asked to create a basic
  voice agent, add an MCP or Foundry IQ knowledge tool, connect with the Voice
  Agent SDK, diagnose preview access errors, or produce safe customer-ready
  voice-agent sample code.
---

# Voice Agent preview

Use the customer package next to this skill. Keep examples concise, use
environment-based authentication, and never place credentials in generated
files.

## Workflow

1. Confirm the Foundry project endpoint, model, and requested lifecycle:
   simple REST, simple SDK, MCP microphone, or Foundry IQ microphone.
2. Confirm that the customer can access the Foundry project.
3. Copy `samples/.env.example` to `samples/.env` and populate only the values
   required by the selected scenario.
4. From `VoiceAgent`, run `python -m pip install -r samples/requirements.txt`.
  The requirements file installs `azure-ai-projects` 2.7.0 or later
  package from PyPI, its `[voice]` extra, and all other sample dependencies.
5. Run the matching sample:
   - `python samples/simple_rest_lifecycle.py`
   - `python samples/basic_voice_agent.py`
   - `python samples/voice_agent_with_mcp.py`
   - `python samples/voice_agent_with_foundry_iq.py`
   - `python samples/voice_agent_with_local_function.py`
   - `python samples/voice_agent_with_toolbox.py`
   - `python samples/download_conversation_artifacts.py <agent-name> <conversation-id>`
   - `python samples/download_conversation_traces.py <conversation-id>`
6. For a microphone lifecycle, use a headset, verify the live transcript and
   tool events, and press Ctrl-C to obtain the persisted conversation id and
   direct Foundry Traces-tab URL.
7. Keep the printed agent name for continued testing. Never delete the agent
   automatically; make cleanup an explicit user action.
8. Download persisted JSON/audio only when requested, using the separate
   conversation-artifact downloader.

## Scenario rules

- For simple REST, demonstrate creation with explicit preview headers.
- For the basic SDK sample, demonstrate `client.agents.create_version` for
  initial creation and definition updates, live microphone chat, and
  conversation-id capture. Read the returned identifier from `version.version`.
- For `mcp`, require `AZURE_VOICE_AGENTS_MCP_CONNECTION_ID`; prefer a Foundry
  project connection instead of inline headers or tokens. Run a live microphone
  session, print the MCP arguments and output, and capture the conversation id.
- For `foundry_iq`, require both the knowledge-base MCP URL and its Foundry
  project connection. Instruct the agent to ground factual answers in the
  knowledge base, run a live microphone session, print MCP arguments and output,
  and capture the conversation id.
- For local functions, declare a `VoiceAgentFunctionTool` with
  `RealtimeFunctionToolParameters`, execute it in the connected client, then
  wait for `response.done` before sending
  `RealtimeConversationItemFunctionCallOutput` and requesting the follow-up response.
  The voice function tool has no `strict` option.
- For Toolbox, attach a versioned `VoiceAgentToolboxTool`, run a microphone session,
  and print the MCP arguments and output.
- For MCP and Foundry IQ, use `VoiceAgentMcpTool`.
- Use models from `azure.ai.projects.models`, including
  `VoiceAgentAudioConfig` and `RealtimeAudioFormatsAudioPcm`. Set audio output
  `voice` to the voice-name string and `voice_type` to `VoiceType.AZURE_STANDARD`.
- Use `model_type=managed` for a service-managed model.
- Use `model_type=self_deployed` only when `model` is a deployment in the
  customer's Foundry project.

## Required preview behavior

- Add `Foundry-Features: VoiceAgents=V1Preview` to direct REST requests.
- Use `azure.ai.projects.aio.AIProjectClient(allow_preview=True, ...)`.
  Reuse this client for `client.beta.voice_agents.realtime.connect(agent_name=agent_name)`.
  The SDK supplies the WebSocket URL, authentication, and preview headers;
  do not use `azure-ai-voicelive` or override private connection methods.
  Send raw PCM bytes with `connection.input_audio_buffer.append(audio=pcm)`.
  Conversation operations under `client.beta.voice_agents.conversations` also
  supply their preview header when `allow_preview=True`.
- Use the project endpoint form
  `https://<account>.services.ai.azure.com/api/projects/<project>`.
- Enable persistence (`store=True`) when creating agents so artifacts can be
  downloaded after microphone sessions.
- Accept an optional existing agent name for every agent sample. Use
  `client.agents.get(agent_name=agent_name)` and skip creation and modification
  when a name is supplied.
- Build the Foundry traces-page URL by discovering the account resource through
  Azure Resource Graph and applying the UI's compact ARM resource encoding.
- Download microphone artifacts only in the standalone downloader, under
  `AZURE_VOICE_AGENTS_OUTPUT_DIR`. For customer-owned storage, record `blob_uri`
  instead of calling the service's audio-download methods.
- Download correlated Application Insights rows by conversation id. Read the
  component ARM resource ID from `.env`, save the KQL and JSON results beside
  the conversation artifacts, and allow for ingestion delay.

## Validation

- Run `python -m compileall samples`.
- Run `python -m unittest discover -s tests -v` for offline SDK contract tests.
- Import every sample with SDK 2.7.0 or later installed.
- Validate this skill with the skill creator's `quick_validate.py`.
- Scan the customer package for secrets, internal host names, local paths,
  private repository links, and placeholder values outside `.env.example`.
- Do not run live creation or deletion without the customer's endpoint,
  permission, and explicit intent.

## Troubleshooting

- For `401` or `403`, refresh authentication and verify project access.
- For create/connect `404`, verify preview enablement and region support.
- For model errors, verify that the configured model or deployment supports
  voice.
- For MCP errors, verify connection scope, target URL, identity permissions,
  and server reachability.
