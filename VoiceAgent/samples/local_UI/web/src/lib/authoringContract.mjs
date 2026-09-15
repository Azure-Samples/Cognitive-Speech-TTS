// Copyright (c) Microsoft. All rights reserved.
// The wire contract for POST /agents:generate, mirrored so the form can state the
// same limits the service enforces instead of guessing at them.
//
// Every value here is transcribed from Vienna's GenerateVoiceAgentRequestValidator
// and ValidationMessages (Agents/EntryPoints/Api/Controllers/V2/Validators/). Vienna
// is the layer that rejects a caller's input and names the field; Voice Live sits
// behind it and enforces its own, usually looser, bounds. When Vienna's numbers move,
// move these with them -- a form that advertises a limit the service does not hold to
// sends the user into a rejection they were told would not happen.

/* Field bounds. `name` is validated as a DNS label rather than by length alone, so the
 * number here is only the length half of that rule -- see NAME_PATTERN. */
export const LIMITS = {
  name: 63,
  useCase: 128,
  goal: 4096,
  model: 256,
  description: 512,
};

/* Vienna: IsValidDnsName -- alphanumeric at both ends, hyphens allowed in between. */
export const NAME_PATTERN = /^[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?$/;

/* `kind` is a required discriminator with exactly one accepted value, so it is a fact
 * about the request rather than a choice the user makes. Stated, never offered. */
export const KIND = "voice";

/* `model_type` is optional and extensible. Omitting it is a distinct, documented
 * choice -- Vienna's contract says the authoring service then uses `managed` and
 * resolves the model itself -- so it is offered as its own option rather than hidden
 * behind a checkbox that does not say what it does. */
export const MODEL_TYPE_OPTIONS = [
  { value: "", label: "Omit — service resolves (managed + default model)" },
  { value: "managed", label: "managed — Voice Live-hosted model" },
  { value: "self_deployed", label: "self_deployed — your own deployment" },
];

/* The use cases offered in the guided-authoring form, grouped the way the Foundry portal's
 * "Create an agent" dialog groups them. Unlike `MODEL_TYPES` this is a suggestion list, not
 * the accepted set: the service takes any string up to LIMITS.useCase, and the field stays
 * optional, so the form also offers no selection at all.
 *
 * The option text IS the wire value. Voice Live interpolates `use_case` into the generator's
 * brief as the subject to write for, so it has to read as prose -- a slug like
 * `retail_banking` would land in the brief verbatim. Anything added here must stay within
 * LIMITS.useCase, which authoringContract.test.mjs asserts. */
export const USE_CASE_GROUPS = [
  {
    label: "Finance",
    items: ["Retail banking self-service", "Insurance claims and policy servicing"],
  },
  {
    label: "Healthcare",
    items: ["Patient access and scheduling", "Health-plan member services"],
  },
  {
    label: "Travel",
    items: ["Airline and travel servicing", "Multilingual travel concierge"],
  },
  {
    label: "Education",
    items: ["AI tutor and role-play coach", "Recruiting and employee assessment"],
  },
];

/* The whole accepted set, not a suggestion list: both Vienna and Voice Live reject
 * anything else. `hosted_agent` is absent on purpose -- it wraps a customer's existing
 * text agent, which owns its prompt and tools, so there is nothing to generate. */
export const MODEL_TYPES = ["managed", "self_deployed"];

export const MODEL_TYPE_MANAGED = "managed";
export const MODEL_TYPE_SELF_DEPLOYED = "self_deployed";

/**
 * Why the request would be rejected, or null when it would be accepted.
 *
 * Mirrors the order Vienna's validator checks in, so the first complaint the user sees
 * here is the first one the service would have made.
 */
export function describeRejection({ name, useCase, goal, description, modelType, model }) {
  if (!name || !name.trim()) return "Agent name is required.";
  if (name.length > LIMITS.name) return `Agent name must be ${LIMITS.name} characters or fewer.`;
  if (!NAME_PATTERN.test(name)) {
    return "Agent name must start and end with a letter or digit, and may contain hyphens in between.";
  }
  // Optional on both sides. Omitting it is a real request: Voice Live opens the generator's
  // brief on a general-purpose assistant rather than on a scenario nobody named.
  if (useCase && useCase.length > LIMITS.useCase) {
    return `Use case must be ${LIMITS.useCase} characters or fewer.`;
  }
  if (goal && goal.length > LIMITS.goal) return `Goal must be ${LIMITS.goal} characters or fewer.`;
  if (model && model.length > LIMITS.model) {
    return `Model must be ${LIMITS.model} characters or fewer.`;
  }
  if (description && description.length > LIMITS.description) {
    return `Description must be ${LIMITS.description} characters or fewer.`;
  }
  // Vienna: "Optional model identifier. Required when model_type is self_deployed."
  if (modelType && !MODEL_TYPES.includes(modelType)) {
    return `model_type must be one of: ${MODEL_TYPES.join(", ")}.`;
  }
  if (modelType === MODEL_TYPE_SELF_DEPLOYED && !(model || "").trim()) {
    return "Model is required when model_type is self_deployed.";
  }
  return null;
}
