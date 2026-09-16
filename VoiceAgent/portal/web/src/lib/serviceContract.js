// Copyright (c) Microsoft. All rights reserved.
// Client-side builders for the REAL Agents service contract, so the browser sends the exact request
// the service expects (path + query + headers + payload). The demo backend is a transparent
// pass-through that injects ONLY the bearer token. Ported from common.py (build_voice_definition /
// build_voice_config / create_agent + generate_agent payloads).

// audio.output.voice object: OpenAI realtime voices are single lowercase words (e.g. "alloy"); Azure
// voices use locale-prefixed, hyphenated names (e.g. "en-US-AvaNeural") -> azure-standard.
export const DEFAULT_VOICE_INSTRUCTIONS =
  "You are a helpful voice assistant. Respond naturally and concisely.";

export function buildVoiceConfig(voice) {
  return voice && !voice.includes("-")
    ? { type: "openai", name: voice }
    : { type: "azure-standard", name: voice };
}

// This repository's Projects SDK uses flat voice/voice_type fields. Retain the
// legacy descriptor helper above for reading older definitions, not for writes.
export function buildVoiceOutput(voice) {
  const descriptor = buildVoiceConfig(voice);
  return { voice: descriptor.name, voice_type: descriptor.type };
}

// Creating the first version also creates the agent. Its name belongs in the
// URL, not the request body (same route as ../samples/simple_rest_lifecycle.py).
export function buildVersionCreateRequest(cfg, authoringBody) {
  const { name, ...body } = authoringBody;
  if (!name || !String(name).trim()) throw new Error("Agent name is required");
  return {
    path: withApiVersion(cfg, `/agents/${encodeURIComponent(name)}/versions`),
    body,
  };
}

export function agentResourceFromVersion(name, result) {
  if (result?.versions?.latest) return { ...result, name: result.name || name };
  return { name, versions: { latest: result } };
}

export function buildEndConversationTool(description = "") {
  const tool = { type: "system", name: "end_conversation" };
  const normalizedDescription = String(description || "").trim();
  if (normalizedDescription) tool.description = normalizedDescription;
  return tool;
}

export function resolveSubagentCapabilities(cfg, agent) {
  const name = agent?.name || agent?.id;
  return cfg?.subagentCapabilityOverrides?.[name]
    || agent?.description
    || agent?.versions?.latest?.description
    || "Specialist sub-agent.";
}

// The full voice AgentDefinition wired for live speech (server VAD, PCM16 @ 24 kHz in/out,
// audio output). `inferenceMode` selects model_type: "model" -> managed (Voice Live-hosted),
// anything else -> self_deployed (BYOM). `tools` are ALREADY service-shaped (ToolsConfig emits the
// service tool objects). No `architecture` field — the service derives realtime vs cascaded.
// `store` is the single logging switch: true logs everything (transcript + audio), false logs
// nothing. The service defaults it to false when omitted; the demo sends the user's explicit choice.
export function buildVoiceDefinition({
  model,
  voice,
  tools,
  inferenceMode,
  store,
  clientReferenceEc,
  inputTranscriptionModel,
  subagents,
  avatar,
  handoff,
  handoffInstructions,
  greeting,
  instructions,
  structuredInputs,
}) {
  const definition = {
    kind: "voice",
    model_type: inferenceMode === "model" ? "managed" : "self_deployed",
    model,
    instructions: DEFAULT_VOICE_INSTRUCTIONS,
    audio: {
      input: {
        format: { type: "audio/pcm", rate: 24000 },
        turn_detection: { type: "server_vad", threshold: 0.5, prefix_padding_ms: 300, silence_duration_ms: 500 },
        transcription: { model: inputTranscriptionModel || "azure-speech" },
      },
      output: {
        format: { type: "audio/pcm", rate: 24000 },
        ...buildVoiceOutput(voice),
      },
    },
    output_modalities: ["audio"],
  };
  if (clientReferenceEc) {
    definition.audio.input.echo_cancellation = {
      type: "server_echo_cancellation",
      reference_source: "client",
      channels: 2,
    };
  }
  if (typeof store === "boolean") definition.store = store;
  if (tools && tools.length) definition.tools = tools;
  if (avatar) definition.avatar = avatar;
  if (handoff) {
    definition.handoff = handoff;
    definition.tool_choice = "auto";
    // With a graph attached the entrypoint is a triage agent for a specific business, not a generic
    // assistant — a generic prompt makes it answer specialist questions itself and never route.
    if (handoffInstructions) definition.instructions = handoffInstructions;
  }
  // An explicitly authored prompt (a scenario demo, for instance) wins over both the generic
  // default above and the handoff entrypoint prompt: it is the one the caller actually chose.
  if (instructions && instructions.trim()) definition.instructions = instructions;
  if (structuredInputs && Object.keys(structuredInputs).length) {
    definition.structured_inputs = structuredInputs;
  }
  if (greeting) definition.greeting = greeting;
  // Sub-agents (design: subagent_config): existing agents the voice agent can forward turns to.
  // Each entry carries its own response_policy so concurrently running specialists can use
  // independent acknowledgement, gap-fill, and progress behavior.
  if (subagents && subagents.length) {
    definition.subagent_config = {
      subagents: subagents.map((subagent) => ({
        ...subagent,
        response_policy: subagent.response_policy || {
          immediate_ack: false,
          gap_filling_interval: 30,
        },
      })),
    };
  }
  return definition;
}

// Authoring state includes name; buildVersionCreateRequest moves it to the URL.
export function buildCreateAgentBody({
  name,
  model,
  voice,
  tools,
  inferenceMode,
  store,
  clientReferenceEc,
  inputTranscriptionModel,
  subagents,
  avatar,
  handoff,
  handoffInstructions,
  greeting,
  instructions,
  structuredInputs,
  description,
  targetAgentName,
  targetAgentVersion,
}) {
  if (inferenceMode === "hosted_agent") {
    return buildHostedAgentVoiceBody({
      name,
      targetAgentName,
      targetAgentVersion,
      voice,
      store,
      clientReferenceEc,
      inputTranscriptionModel,
      avatar,
      greeting,
    });
  }
  return {
    name,
    description: description || "voice agent sample",
    definition: buildVoiceDefinition({
      model,
      voice,
      tools,
      inferenceMode,
      store,
      clientReferenceEc,
      inputTranscriptionModel,
      subagents,
      avatar,
      handoff,
      handoffInstructions,
      greeting,
      instructions,
      structuredInputs,
    }),
  };
}

// A hosted-agent voice wrapper carries only Voice Live-owned surface settings
// plus a reference to the existing same-project hosted target. Model, prompt,
// tools, subagents, and handoff belong to the target and are invalid here.
export function buildHostedAgentVoiceBody({
  name,
  targetAgentName,
  targetAgentVersion,
  voice,
  store,
  clientReferenceEc,
  inputTranscriptionModel,
  avatar,
  greeting,
}) {
  const targetName = String(targetAgentName || "").trim();
  if (!targetName) throw new Error("Target hosted agent name is required");
  const targetAgent = { name: targetName };
  const version = String(targetAgentVersion || "").trim();
  if (version) targetAgent.version = version;
  const outputVoiceName = String(voice || "").trim();
  if (!outputVoiceName || !outputVoiceName.includes("-")) {
    throw new Error(
      `Hosted-agent wrappers require an Azure voice name `
      + `(for example, "en-US-AvaNeural"); got "${outputVoiceName}"`,
    );
  }
  const definition = {
    kind: "voice",
    model_type: "hosted_agent",
    target_agent: targetAgent,
    store: Boolean(store),
    audio: {
      input: {
        format: { type: "audio/pcm", rate: 24000 },
        turn_detection: {
          type: "server_vad",
          threshold: 0.5,
          prefix_padding_ms: 300,
          silence_duration_ms: 500,
        },
        transcription: { model: inputTranscriptionModel || "azure-speech" },
      },
      output: {
        format: { type: "audio/pcm", rate: 24000 },
        ...buildVoiceOutput(outputVoiceName),
      },
    },
    output_modalities: ["audio"],
  };
  if (clientReferenceEc) {
    definition.audio.input.echo_cancellation = {
      type: "server_echo_cancellation",
      reference_source: "client",
      channels: 2,
    };
  }
  if (avatar) definition.avatar = avatar;
  if (greeting) {
    if (greeting.tool_choice === "required") {
      throw new Error(
        "Hosted-agent voice greeting tool_choice cannot be required",
      );
    }
    definition.greeting = greeting;
  }
  return {
    name,
    description: "Voice interface for an existing hosted agent",
    definition,
  };
}

// A plain prompt (text) AgentDefinition — the kind used for a sub-agent the voice agent forwards to
// (design: subagent_config). Mirrors the E2E `createSubagent` payload (kind: 'prompt', model,
// instructions). Create one of these, then attach it by name under a voice agent's sub-agents.
export function buildCreatePromptAgentBody({ name, model, instructions, description }) {
  return {
    name,
    description: description || "prompt (text) sub-agent",
    definition: {
      kind: "prompt",
      model,
      instructions: instructions || "You are a helpful assistant. Answer directly and concisely.",
    },
  };
}

// The guided-authoring body: POST /agents:generate
//   { kind: "voice", name, use_case, goal?, model_type?, model?, description?, draft?, tools? }.
//
// Contract (post agentic-creation refactor — Vienna PR 2231935 / Voice Live PR 38478):
//   - `kind` is the route discriminator for the shared /agents:generate endpoint; always "voice" here.
//   - `name` is the only other REQUIRED field. That is the
//     `azd voice-agent create --name X` minimum.
//   - `use_case` is optional: an arbitrary non-empty string (<=128 chars) when present. The old enum
//     whitelist was dropped — stage 1 does not vary the generated definition by use_case.
//   - `goal` is optional; omitting it still produces a working agent.
//   - `model_type` is optional (the service defaults to `managed`). `model` is required ONLY when
//     `model_type=self_deployed` — the service never invents a customer's BYOM deployment name.
//     Both are omitted from the body when unset, so the server-side defaults are actually exercised
//     rather than masked by a client-side value.
//   - `description` and `draft` are optional. Their fallbacks are decided by VOICE LIVE
//     (user-supplied wins, otherwise a fixed default) — Vienna is a pure pass-through, so omitting
//     them here exercises the orchestrator's resolution path.
//   - `agent_type` was REMOVED from the contract; persona is derived from `goal` + `use_case`.
export function buildGenerateAgentBody({
  name,
  model,
  modelType,
  useCase,
  goal,
  tools,
  description,
  draft,
}) {
  // `model_type` on the wire takes the service's own vocabulary -- `managed` /
  // `self_deployed` -- so the caller passes that rather than the UI's `inferenceMode`
  // ("model" / "deployment"). One translation, at the edge that owns the picker.
  if (modelType === "hosted_agent") {
    throw new Error("Guided authoring does not support hosted-agent wrappers");
  }
  // `kind` and `name` are the only always-required fields.
  const body = { kind: "voice", name };
  // A blank `use_case` is an omission, not an empty scenario. Voice Live interpolates it
  // into the generator's brief as the subject to write for, so sending "" would be asking
  // for an agent about nothing; omitted, the brief opens on a general-purpose assistant.
  if (useCase && useCase.trim()) body.use_case = useCase;
  // Only send model_type/model when the caller actually chose them, so the "omitted -> managed
  // default" server path stays reachable from this demo. BYOM still needs both.
  if (modelType) {
    if (modelType === "self_deployed" && !String(model || "").trim()) {
      throw new Error('model_type=self_deployed (BYOM) requires a non-empty "model"');
    }
    body.model_type = modelType;
  }
  if (model) body.model = model;
  if (goal && goal.trim()) body.goal = goal;
  if (description && description.trim()) body.description = description;
  if (typeof draft === "boolean") body.draft = draft;
  if (tools && tools.length) body.tools = tools;
  return body;
}

function rand8() {
  const uuid = (typeof crypto !== "undefined" && crypto.randomUUID)
    ? crypto.randomUUID().replace(/-/g, "")
    : Math.random().toString(16).slice(2);
  return uuid.slice(0, 8);
}

export const newAgentName = (prefix = "web-voice") => `${prefix}-${rand8()}`;
export const newSessionId = () => `web-${rand8()}`;

// ---- request shaping so the browser matches the service contract ----
// Append the `api-version` query param the service requires (the backend forwards it verbatim).
export function withApiVersion(cfg, path) {
  const sep = path.includes("?") ? "&" : "?";
  return `${path}${sep}api-version=${encodeURIComponent(cfg.apiVersion)}`;
}

// Headers that are part of the client contract and are sent by the browser (the backend injects only
// the bearer token). `Foundry-Features` gates the voice preview; `Content-Type` for JSON bodies.
export function serviceHeaders(cfg, extra) {
  const headers = { "Foundry-Features": cfg.foundryFeatures };
  return extra ? { ...headers, ...extra } : headers;
}
