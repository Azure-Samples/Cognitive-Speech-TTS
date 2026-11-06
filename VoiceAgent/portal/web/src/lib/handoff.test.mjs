// Copyright (c) Microsoft. All rights reserved.

import test from "node:test";
import assert from "node:assert/strict";
import {
  activeHandoffNode,
  buildCustomerCareHandoff,
  handoffMessage,
  HANDOFF_ENTRYPOINT_INSTRUCTIONS,
  shouldStartSessionResources,
} from "./handoff.mjs";
import { buildVoiceDefinition } from "./serviceContract.js";

test("builds a reachable cyclic customer-care graph", () => {
  const graph = buildCustomerCareHandoff();
  assert.equal(graph.nodes.length, 2);
  assert.equal(graph.edges.length, 4);
  assert.ok(graph.edges.some((edge) => edge.source === "$entrypoint" && edge.target === "billing"));
  assert.ok(graph.edges.some((edge) => edge.source === "billing" && edge.target === "technical_support"));
  assert.ok(graph.edges.some((edge) => edge.source === "technical_support" && edge.target === "billing"));
});

test("gives every node its own fixed voice, distinct from the Ava HD entrypoint default", () => {
  const graph = buildCustomerCareHandoff();
  const byId = Object.fromEntries(graph.nodes.map((node) => [node.id, node.config.voice]));
  assert.deepEqual(byId.billing, { type: "azure-standard", name: "en-US-EmmaNeural" });
  assert.deepEqual(byId.technical_support, { type: "azure-standard", name: "en-US-AndrewNeural" });
  for (const voice of Object.values(byId)) {
    assert.notEqual(voice.name, "en-US-Ava:DragonHDLatestNeural");
  }
});

test("omits unsupported transfer messages from realtime handoff graphs", () => {
  const graph = buildCustomerCareHandoff();
  for (const edge of graph.edges) {
    assert.equal(edge.transfer_message, undefined, `${edge.id} has a realtime transfer_message`);
  }
});

test("announces every cascaded transfer in the current agent's voice before handing over", () => {
  const graph = buildCustomerCareHandoff({ supportsTransferMessage: true });
  for (const edge of graph.edges) {
    assert.ok(edge.transfer_message, `${edge.id} has no transfer_message`);
    assert.ok(edge.transfer_message.length <= 500, `${edge.id} transfer_message exceeds 500 chars`);
  }
});

test("describes each desk in online-phone-store terms so routing has something to match on", () => {
  const graph = buildCustomerCareHandoff();
  const byId = Object.fromEntries(graph.nodes.map((node) => [node.id, node]));
  assert.match(byId.billing.description, /refund/i);
  assert.match(byId.technical_support.description, /battery|connectivity/i);
  for (const node of graph.nodes) {
    assert.ok(node.description.length > 80, `${node.id} description is too thin to route on`);
    assert.match(node.config.instructions, /Contoso Mobile/);
  }
  assert.match(HANDOFF_ENTRYPOINT_INSTRUCTIONS, /Contoso Mobile/);
  assert.match(HANDOFF_ENTRYPOINT_INSTRUCTIONS, /before every handoff/i);
});

test("uses the store-specific entrypoint instructions only when a handoff graph is attached", () => {
  const withHandoff = buildVoiceDefinition({
    model: "gpt-realtime",
    voice: "en-US-Ava:DragonHDLatestNeural",
    inferenceMode: "model",
    handoff: buildCustomerCareHandoff(),
    handoffInstructions: HANDOFF_ENTRYPOINT_INSTRUCTIONS,
  });
  assert.equal(withHandoff.instructions, HANDOFF_ENTRYPOINT_INSTRUCTIONS);
  assert.equal(withHandoff.tool_choice, "auto");

  const plain = buildVoiceDefinition({
    model: "gpt-realtime",
    voice: "en-US-Ava:DragonHDLatestNeural",
    inferenceMode: "model",
  });
  assert.match(plain.instructions, /helpful voice assistant/);
});

test("normalizes completed lifecycle events for rendering", () => {
  assert.deepEqual(handoffMessage({
    type: "session.handoff.completed",
    event_id: "event_1",
    handoff_id: "handoff_1",
    edge_id: "entrypoint_to_billing",
    from_node_id: "$entrypoint",
    to_node_id: "billing",
    duration_ms: 42,
    prepare_duration_ms: 12,
  }), {
    id: "handoff-handoff_1",
    type: "handoff",
    handoff: {
      status: "completed",
      handoffId: "handoff_1",
      edgeId: "entrypoint_to_billing",
      fromNodeId: "$entrypoint",
      toNodeId: "billing",
      reason: null,
      durationMs: 42,
      prepareDurationMs: 12,
      error: null,
    },
  });
});

test("reads the active node from session.updated state", () => {
  assert.equal(activeHandoffNode({ handoff: { active_node_id: "billing" } }), "billing");
  assert.equal(activeHandoffNode({}), null);
});

test("starts session resources only for the initial session update", () => {
  assert.equal(shouldStartSessionResources(false), true);
  assert.equal(shouldStartSessionResources(true), false);
});
