// Copyright (c) Microsoft. All rights reserved.

import test from "node:test";
import assert from "node:assert/strict";
import { createAgentDraft, draftCreateOptions, updateAgentDraft, DEFAULT_INSTRUCTIONS } from "./agentForm.mjs";
import { buildCreateAgentBody } from "./serviceContract.js";
import { buildGreetingConfig } from "./greeting.mjs";
import { HANDOFF_ENTRYPOINT_INSTRUCTIONS } from "./handoff.mjs";

const cfg = {
  defaultModel: "gpt-realtime",
  defaultVoice: "en-US-AvaNeural",
  defaultAzureVoice: "en-US-AvaNeural",
  realtimeModels: ["gpt-realtime"],
  cascadedModels: ["gpt-4.1"],
  byomRealtimeModels: ["my-realtime"],
  byomCascadedModels: ["my-cascaded"],
};
const policy = { immediate_ack: true, gap_filling_interval: 12 };
const tools = [{ type: "system", name: "end_conversation" }];
const subagents = [{ agent_name: "specialist", agent_capabilities: "Billing", response_policy: policy }];
const body = (draft) => {
  const options = draftCreateOptions(draft, tools, subagents);
  return buildCreateAgentBody({ ...options, greeting: buildGreetingConfig(options.greeting) });
};

test("editor defaults preserve the existing managed voice request", () => {
  const draft = createAgentDraft(cfg);
  const request = body(draft);
  assert.equal(request.definition.kind, "voice");
  assert.equal(request.definition.model_type, "managed");
  assert.equal(request.definition.model, cfg.defaultModel);
  assert.equal(request.definition.instructions, DEFAULT_INSTRUCTIONS);
  assert.equal(request.definition.store, true);
  assert.deepEqual(request.definition.audio.input.echo_cancellation, {
    type: "server_echo_cancellation", reference_source: "client", channels: 2,
  });
  assert.equal("greeting" in request.definition, false);
});

test("a backend can still default conversation storage off", () => {
  assert.equal(createAgentDraft({ ...cfg, defaultStore: false }).store, false);
});

test("switching sources picks a valid model and does not erase the draft", () => {
  const original = { ...createAgentDraft(cfg), name: "keep-me", instructions: "Be concise." };
  const byom = updateAgentDraft(cfg, original, "inferenceMode", "deployment");
  assert.equal(byom.model, "my-realtime");
  assert.equal(body(byom).definition.model_type, "self_deployed");
  assert.equal(byom.name, "keep-me");
  assert.equal(byom.instructions, "Be concise.");
  assert.equal(updateAgentDraft(cfg, byom, "inferenceMode", "model").model, "gpt-realtime");
  assert.equal(original.inferenceMode, "model");
});

test("avatar and client-reference echo cancellation remain mutually exclusive", () => {
  const draft = { ...createAgentDraft(cfg), voice: "alloy" };
  const avatar = updateAgentDraft(cfg, draft, "avatarEnabled", true);
  assert.equal(avatar.voice, cfg.defaultAzureVoice);
  assert.equal(avatar.clientReferenceEc, false);
  assert.ok(body(avatar).definition.avatar);
  const echo = updateAgentDraft(cfg, avatar, "clientReferenceEc", true);
  assert.equal(echo.avatarEnabled, false);
  assert.equal("avatar" in body(echo).definition, false);
});

test("changing models with an avatar keeps an Azure voice", () => {
  const draft = updateAgentDraft(cfg, createAgentDraft(cfg), "avatarEnabled", true);
  const next = updateAgentDraft({ ...cfg, defaultAzureVoice: "", defaultVoice: "alloy", azureVoices: ["en-US-JennyNeural"] },
    draft, "model", "gpt-realtime");
  assert.equal(next.voice, "en-US-JennyNeural");
});

test("hosted wrappers exclude target-owned fields without destroying local selections", () => {
  const initial = {
    ...createAgentDraft(cfg), instructions: "Keep my custom instructions", handoffEnabled: true,
    greeting: { mode: "llm_generated", prompt: "Greet the caller", fallbackText: "Hello", toolChoice: "required" },
  };
  const hosted = {
    ...updateAgentDraft(cfg, initial, "inferenceMode", "hosted_agent"),
    targetAgentName: " hosted-target ", targetAgentVersion: " 2 ",
  };
  const definition = body(hosted).definition;
  assert.equal(definition.model_type, "hosted_agent");
  assert.deepEqual(definition.target_agent, { name: "hosted-target", version: "2" });
  for (const key of ["model", "instructions", "tools", "handoff", "subagent_config"]) {
    assert.equal(key in definition, false, key);
  }
  assert.equal(definition.greeting.tool_choice, "auto");
  assert.equal(initial.greeting.toolChoice, "required");
  const restored = body(updateAgentDraft(cfg, hosted, "inferenceMode", "model")).definition;
  assert.deepEqual(restored.tools, tools);
  assert.deepEqual(restored.subagent_config, { subagents });
  assert.equal(restored.instructions, initial.instructions);
  assert.ok(restored.handoff);
});

test("backend-default hosted wrappers start with an Azure voice", () => {
  const draft = createAgentDraft({ ...cfg, defaultInferenceMode: "hosted_agent", defaultVoice: "alloy" });
  assert.equal(draft.inferenceMode, "hosted_agent");
  assert.equal(draft.voice, cfg.defaultAzureVoice);
});

test("handoff prompt remains the default unless instructions are explicitly authored", () => {
  const draft = { ...createAgentDraft(cfg), handoffEnabled: true };
  assert.equal(body(draft).definition.instructions, HANDOFF_ENTRYPOINT_INSTRUCTIONS);
  assert.equal(body({ ...draft, instructions: "My explicit routing instructions" }).definition.instructions,
    "My explicit routing instructions");
});

test("template and generated greetings survive draft-to-request conversion", () => {
  const draft = createAgentDraft(cfg);
  draft.greeting = { ...draft.greeting, mode: "template", text: "Hello {{name}}!" };
  assert.deepEqual(body(draft).definition.greeting, { type: "template", text: "Hello {{name}}!" });
  draft.greeting = { mode: "llm_generated", prompt: "Greet warmly", fallbackText: "Hello", toolChoice: "auto" };
  assert.deepEqual(body(draft).definition.greeting, {
    type: "llm_generated", prompt: "Greet warmly", fallback_text: "Hello", tool_choice: "auto",
  });
});

test("structured input definitions reach managed and BYOM agents, but not hosted wrappers", () => {
  const structuredInputs = { customer_name: { schema: { type: "string" }, default_value: "Ada" } };
  const draft = { ...createAgentDraft(cfg), instructions: "Help {{customer_name}}." };
  for (const inferenceMode of ["model", "deployment", "hosted_agent"]) {
    const options = draftCreateOptions(
      { ...draft, inferenceMode, targetAgentName: "hosted-target" }, tools, subagents, structuredInputs,
    );
    const definition = buildCreateAgentBody(options).definition;
    assert.deepEqual(definition.structured_inputs, inferenceMode === "hosted_agent" ? undefined : structuredInputs);
  }
});
