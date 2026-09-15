// Copyright (c) Microsoft. All rights reserved.

import test from "node:test";
import assert from "node:assert/strict";
import {
  buildEndConversationTool,
  buildCreateAgentBody,
  buildGenerateAgentBody,
  buildHostedAgentVoiceBody,
  buildVoiceConfig,
  buildVoiceDefinition,
  resolveSubagentCapabilities,
} from "./serviceContract.js";

test("builds the end-conversation system tool with an optional description", () => {
  const description = "Say goodbye before ending the conversation.";
  assert.deepEqual(
    buildEndConversationTool(description),
    {
      type: "system",
      name: "end_conversation",
      description,
    },
  );
  assert.deepEqual(
    buildEndConversationTool("   "),
    { type: "system", name: "end_conversation" },
  );
});

test("builds canonical OpenAI and Azure voice types", () => {
  assert.deepEqual(buildVoiceConfig("alloy"), { type: "openai", name: "alloy" });
  assert.deepEqual(buildVoiceConfig("en-US-AvaNeural"), {
    type: "azure-standard",
    name: "en-US-AvaNeural",
  });
});

test("prefers configured routing capabilities over stale shadow descriptions", () => {
  const name = "hotel-booking-python-invocations-voicelive";
  const capability = "Help users search for and book hotels.";
  const cfg = {
    subagentCapabilityOverrides: {
      [name]: capability,
    },
  };
  const agent = {
    name,
    description: "Local route metadata for an Invocations hosted subagent.",
  };

  assert.equal(resolveSubagentCapabilities(cfg, agent), capability);
});

test("preserves greeting and handoff on the same voice definition", () => {
  const greeting = { type: "template", text: "Hello." };
  const handoff = {
    nodes: [{ id: "billing", description: "Billing", config: { tools: [] } }],
    edges: [{ id: "route", source: "$entrypoint", target: "billing", description: "Billing" }],
  };

  const definition = buildVoiceDefinition({
    model: "gpt-realtime",
    voice: "alloy",
    tools: [],
    inferenceMode: "model",
    store: true,
    greeting,
    handoff,
  });

  assert.deepEqual(definition.greeting, greeting);
  assert.deepEqual(definition.handoff, handoff);
  assert.equal(definition.tool_choice, "auto");
});

test("preserves authored instructions and structured-input definitions", () => {
  const structuredInputs = {
    customer_name: {
      default_value: "Ada",
      schema: { type: "string" },
    },
  };

  const definition = buildVoiceDefinition({
    model: "gpt-realtime",
    voice: "alloy",
    tools: [],
    inferenceMode: "model",
    instructions: "Help {{customer_name}}.",
    structuredInputs,
  });

  assert.equal(definition.instructions, "Help {{customer_name}}.");
  assert.deepEqual(definition.structured_inputs, structuredInputs);
});

test("configures stable v1 client-reference echo cancellation", () => {
  const definition = buildVoiceDefinition({
    model: "gpt-realtime",
    voice: "alloy",
    tools: [],
    inferenceMode: "model",
    clientReferenceEc: true,
  });

  assert.deepEqual(definition.audio.input.echo_cancellation, {
    type: "server_echo_cancellation",
    reference_source: "client",
    channels: 2,
  });
  assert.deepEqual(definition.audio.input.format, {
    type: "audio/pcm",
    rate: 24000,
  });
});

test("places response policy on each configured subagent", () => {
  const firstPolicy = {
    immediate_ack: true,
    gap_filling_interval: 5,
    ack_instructions: "Acknowledge the research request.",
    enable_delta_progress: true,
    progress_update_interval: 7,
  };
  const definition = buildVoiceDefinition({
    model: "gpt-realtime",
    voice: "alloy",
    tools: [],
    inferenceMode: "model",
    subagents: [
      {
        agent_name: "research-agent",
        agent_capabilities: "Research current information.",
        response_policy: firstPolicy,
      },
      {
        agent_name: "booking-agent",
        agent_capabilities: "Book hotels.",
      },
    ],
  });

  assert.equal("response_policy" in definition.subagent_config, false);
  assert.deepEqual(
    definition.subagent_config.subagents[0].response_policy,
    firstPolicy,
  );
  assert.deepEqual(
    definition.subagent_config.subagents[1].response_policy,
    {
      immediate_ack: false,
      gap_filling_interval: 30,
    },
  );
});

test("builds a strict hosted-agent voice wrapper through inference mode", () => {
  const greeting = { type: "llm_generated", tool_choice: "auto" };
  const avatar = { type: "video-avatar", character: "lisa" };
  const body = buildCreateAgentBody({
    name: "voice-wrapper",
    targetAgentName: "hosted-target",
    targetAgentVersion: "2",
    voice: "en-US-JennyNeural",
    store: false,
    clientReferenceEc: true,
    inferenceMode: "hosted_agent",
    model: "must-not-leak",
    tools: [{ type: "function" }],
    handoff: { nodes: [] },
    greeting,
    avatar,
  });

  assert.deepEqual(body.definition.target_agent, {
    name: "hosted-target",
    version: "2",
  });
  assert.equal(body.definition.model_type, "hosted_agent");
  assert.equal(body.definition.kind, "voice");
  assert.deepEqual(body.definition.greeting, greeting);
  assert.deepEqual(body.definition.avatar, avatar);
  assert.deepEqual(body.definition.audio.input.echo_cancellation, {
    type: "server_echo_cancellation",
    reference_source: "client",
    channels: 2,
  });
  for (const forbidden of ["model", "instructions", "tools", "handoff"]) {
    assert.equal(forbidden in body.definition, false);
  }
});

test("rejects required greeting tool choice for hosted-agent voice", () => {
  assert.throws(
    () => buildHostedAgentVoiceBody({
      name: "voice-wrapper",
      targetAgentName: "hosted-target",
      voice: "en-US-JennyNeural",
      greeting: { type: "llm_generated", tool_choice: "required" },
    }),
    /cannot be required/,
  );
});

test("requires an Azure output voice for hosted-agent wrappers", () => {
  assert.throws(
    () => buildHostedAgentVoiceBody({
      name: "voice-wrapper",
      targetAgentName: "hosted-target",
      voice: "alloy",
    }),
    /require an Azure voice name.*alloy/,
  );

  const body = buildHostedAgentVoiceBody({
    name: "voice-wrapper",
    targetAgentName: "hosted-target",
    voice: "  en-US-AvaNeural  ",
  });
  assert.deepEqual(body.definition.audio.output.voice, {
    type: "azure-standard",
    name: "en-US-AvaNeural",
  });
});

test("rejects hosted-agent guided authoring", () => {
  assert.throws(
    () => buildGenerateAgentBody({
      name: "voice-wrapper",
      modelType: "hosted_agent",
      model: "ignored",
      useCase: "support",
      goal: "Help users",
    }),
    /does not support hosted-agent wrappers/,
  );
});

// The service never invents a customer's BYOM deployment name, so a self_deployed body without a
// `model` is unfillable. Fail here rather than let the service reject it.
test("rejects BYOM guided authoring without a model", () => {
  assert.throws(
    () => buildGenerateAgentBody({
      name: "generated-agent",
      modelType: "self_deployed",
      useCase: "customer_support",
    }),
    /requires a non-empty "model"/,
  );
});

test("guided authoring identifies the requested agent kind as voice", () => {
  const body = buildGenerateAgentBody({
    name: "generated-agent",
    model: "gpt-realtime",
    modelType: "managed",
    useCase: "customer_support",
    goal: "Help customers with their orders.",
    tools: [],
  });

  assert.equal(body.kind, "voice");
});

test("guided authoring sends only kind + name + use_case at the minimum", () => {
  // Post agentic-creation refactor this is the whole required payload — the
  // `azd voice-agent create --name X --use-case Y` path. Anything extra on the wire would
  // mask a server-side default instead of exercising it.
  const body = buildGenerateAgentBody({
    name: "minimal-agent",
    useCase: "customer_support",
  });

  assert.deepEqual(Object.keys(body).sort(), ["kind", "name", "use_case"]);
  assert.equal(body.use_case, "customer_support");
});

test("guided authoring omits model_type and model when the caller does not choose them", () => {
  // Leaving them off the wire is what makes the service resolve managed + default model.
  const body = buildGenerateAgentBody({
    name: "defaults-agent",
    useCase: "reception",
    goal: "Greet visitors.",
  });

  assert.equal("model_type" in body, false);
  assert.equal("model" in body, false);
  assert.equal(body.goal, "Greet visitors.");
});

test("guided authoring no longer sends the removed agent_type field", () => {
  const body = buildGenerateAgentBody({
    name: "no-agent-type",
    useCase: "sales",
    goal: "Qualify leads.",
    modelType: "managed",
  });

  assert.equal("agent_type" in body, false);
});

test("guided authoring carries description and draft only when supplied", () => {
  // Both have Voice Live-owned fallbacks, so a blank value must stay off the wire rather than
  // overriding the orchestrator's resolution with an empty string.
  const blank = buildGenerateAgentBody({
    name: "blank-optional",
    useCase: "support",
    description: "   ",
  });
  assert.equal("description" in blank, false);
  assert.equal("draft" in blank, false);

  const supplied = buildGenerateAgentBody({
    name: "supplied-optional",
    useCase: "support",
    description: "Loan servicing bot",
    draft: true,
  });
  assert.equal(supplied.description, "Loan servicing bot");
  assert.equal(supplied.draft, true);
});

test("guided authoring keeps an explicit draft=false on the wire", () => {
  // `false` is a caller-supplied choice, not an omission — collapsing it would silently flip
  // the meaning if the service-side fallback ever changes.
  const body = buildGenerateAgentBody({
    name: "explicit-false",
    useCase: "support",
    draft: false,
  });

  assert.equal(body.draft, false);
});

test("guided authoring sends only kind and name at the minimum", () => {
  // The whole required payload. `use_case` is optional on both sides now, and a blank one
  // is an omission rather than an empty scenario: Voice Live interpolates it into the
  // generator's brief as the subject to write for, so sending "" would ask for an agent
  // about nothing, where omitting it opens the brief on a general-purpose assistant.
  const minimal = buildGenerateAgentBody({ name: "minimal" });
  const blank = buildGenerateAgentBody({ name: "minimal", useCase: "   " });
  const supplied = buildGenerateAgentBody({ name: "minimal", useCase: "support line" });

  assert.deepEqual(Object.keys(minimal).sort(), ["kind", "name"]);
  assert.deepEqual(Object.keys(blank).sort(), ["kind", "name"]);
  assert.equal(supplied.use_case, "support line");
});

test("guided authoring sends model_type in the service's own vocabulary", () => {
  // Not the UI's "model" / "deployment" -- the wire field takes `managed` /
  // `self_deployed`, and a mistranslation here would be accepted by the validator and
  // silently build the wrong kind of agent.
  const managed = buildGenerateAgentBody({ name: "a", useCase: "support", modelType: "managed" });
  const byom = buildGenerateAgentBody({
    name: "b", useCase: "support", modelType: "self_deployed", model: "my-deployment",
  });

  assert.equal(managed.model_type, "managed");
  assert.equal(byom.model_type, "self_deployed");
  assert.equal(byom.model, "my-deployment");
});
