// Copyright (c) Microsoft. All rights reserved.
// UI draft state, not a second wire schema. serviceContract.js remains the only
// serializer. Field ownership follows the voice-agent definition contract.

import { defaultVoiceFor, modelGroups } from "../config.js";
import { DEFAULT_AVATAR_PRESET_ID, buildAvatarDefinition } from "./avatar.mjs";
import { GREETING_MODES } from "./greeting.mjs";
import { buildCustomerCareHandoff, HANDOFF_ENTRYPOINT_INSTRUCTIONS } from "./handoff.mjs";
export { DEFAULT_VOICE_INSTRUCTIONS as DEFAULT_INSTRUCTIONS } from "./serviceContract.js";

export function azureDefaultVoice(cfg) {
  return cfg.defaultAzureVoice || cfg.azureVoices?.[0] || "en-US-JennyNeural";
}

export function createAgentDraft(cfg) {
  const inferenceMode = cfg.defaultInferenceMode || "model";
  return {
    name: "",
    description: "",
    instructions: "",
    inferenceMode,
    model: cfg.defaultModel,
    voice: inferenceMode === "hosted_agent" ? azureDefaultVoice(cfg) : cfg.defaultVoice,
    targetAgentName: "",
    targetAgentVersion: "",
    clientReferenceEc: true,
    store: cfg.defaultStore !== false,
    avatarEnabled: false,
    avatarPreset: DEFAULT_AVATAR_PRESET_ID,
    handoffEnabled: false,
    greeting: {
      mode: GREETING_MODES.NONE,
      text: "Hello! How can I help?",
      prompt: "Greet the caller warmly in one short sentence and ask how you can help.",
      fallbackText: "Hello! How can I help?",
      toolChoice: "none",
    },
  };
}

export function updateAgentDraft(cfg, draft, field, value) {
  const next = { ...draft, [field]: value };
  if (field === "model") next.voice = defaultVoiceFor(cfg, value);
  if (field === "inferenceMode") {
    if (value === "hosted_agent") {
      next.voice = azureDefaultVoice(cfg);
      if (next.greeting.toolChoice === "required") {
        next.greeting = { ...next.greeting, toolChoice: "auto" };
      }
    } else {
      next.model = modelGroups(cfg, value === "deployment")[0]?.items[0] || "";
      next.voice = defaultVoiceFor(cfg, next.model);
    }
  }
  if (field === "avatarEnabled" && value) {
    next.clientReferenceEc = false;
  }
  if (field === "clientReferenceEc" && value) next.avatarEnabled = false;
  if (next.avatarEnabled && !next.voice?.includes("-")) next.voice = azureDefaultVoice(cfg);
  return next;
}

export function draftCreateOptions(draft, tools, subagents, structuredInputs) {
  const hosted = draft.inferenceMode === "hosted_agent";
  return {
    name: draft.name,
    description: draft.description,
    instructions: hosted ? undefined : draft.instructions,
    inferenceMode: draft.inferenceMode,
    model: draft.model,
    voice: draft.voice,
    store: draft.store,
    clientReferenceEc: draft.clientReferenceEc,
    avatar: buildAvatarDefinition(draft.avatarEnabled, draft.avatarPreset),
    greeting: { ...draft.greeting },
    tools: hosted ? [] : tools,
    subagents: hosted ? [] : subagents,
    structuredInputs: hosted ? undefined : structuredInputs,
    handoff: !hosted && draft.handoffEnabled ? buildCustomerCareHandoff() : null,
    handoffInstructions: !hosted && draft.handoffEnabled ? HANDOFF_ENTRYPOINT_INSTRUCTIONS : null,
    targetAgentName: hosted ? draft.targetAgentName.trim() : null,
    targetAgentVersion: hosted ? draft.targetAgentVersion.trim() : null,
  };
}
