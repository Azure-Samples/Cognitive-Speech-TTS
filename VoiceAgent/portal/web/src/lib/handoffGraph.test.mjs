// Copyright (c) Microsoft. All rights reserved.

import test from "node:test";
import assert from "node:assert/strict";
import { buildHandoffGraph, ENTRYPOINT_NODE_ID, toolLabels } from "./handoffGraph.mjs";
import { buildCustomerCareHandoff } from "./handoff.mjs";

const definition = {
  instructions: "You are the front-line agent.",
  model: "gpt-realtime",
  tools: [{ type: "mcp", server_label: "store" }],
  audio: { output: { voice: { type: "azure-standard", name: "en-US-Ava:DragonHDLatestNeural" } } },
  handoff: buildCustomerCareHandoff(),
};

const sessionState = {
  pipeline_family: "realtime",
  active_node_id: "billing",
  node_generation: 2,
  transfer_count: 1,
  attempt_count: 1,
  available_edge_ids: ["billing_to_technical_support"],
  nodes: [
    { id: ENTRYPOINT_NODE_ID, description: "Top-level session configuration.", implicit: true },
    { id: "billing", description: "The billing desk.", implicit: false },
    { id: "technical_support", description: "The technical support desk.", implicit: false },
  ],
  edges: buildCustomerCareHandoff().edges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    target_response: "auto",
    transfer_message: null,
    cancel_on_interruption: false,
    delay_ms: 0,
  })),
};

test("reads tool labels from every tool shape the service accepts", () => {
  assert.deepEqual(
    toolLabels([{ type: "function", name: "get_invoice" }, { type: "mcp", server_label: "store" }, { type: "foundry_toolbox" }]),
    ["get_invoice", "store", "foundry_toolbox"],
  );
});

test("returns null when the agent has no handoff graph", () => {
  assert.equal(buildHandoffGraph({ definition: { instructions: "plain" } }), null);
  assert.equal(buildHandoffGraph({}), null);
});

test("draws the authored graph before any session exists", () => {
  const graph = buildHandoffGraph({ definition });
  assert.equal(graph.source, "definition");
  assert.equal(graph.activeNodeId, null);
  assert.deepEqual(graph.nodes.map((node) => node.id), [ENTRYPOINT_NODE_ID, "billing", "technical_support"]);
  assert.equal(graph.edges.length, 4);
});

test("carries the prompt each node actually runs with", () => {
  const graph = buildHandoffGraph({ definition });
  const byId = Object.fromEntries(graph.nodes.map((node) => [node.id, node]));
  assert.equal(byId[ENTRYPOINT_NODE_ID].instructions, "You are the front-line agent.");
  assert.deepEqual(byId[ENTRYPOINT_NODE_ID].tools, ["store"]);
  assert.equal(byId[ENTRYPOINT_NODE_ID].model, "gpt-realtime");
  assert.match(byId.billing.instructions, /billing specialist/);
  assert.equal(byId.billing.voice, "en-US-EmmaNeural");
  assert.equal(byId.billing.toolChoice, "auto");
});

test("classifies the entrypoint and marks a node with no outgoing edge as terminal", () => {
  const graph = buildHandoffGraph({
    definition: {
      handoff: {
        nodes: [{ id: "triage", description: "d", config: {} }, { id: "end", description: "d", config: {} }],
        edges: [{ id: "e1", source: ENTRYPOINT_NODE_ID, target: "triage", description: "d" },
          { id: "e2", source: "triage", target: "end", description: "d" }],
      },
    },
  });
  const kinds = Object.fromEntries(graph.nodes.map((node) => [node.id, node.kind]));
  assert.deepEqual(kinds, { [ENTRYPOINT_NODE_ID]: "entry", triage: "node", end: "terminal" });
});

test("layers nodes by longest path from the entrypoint, ignoring back edges", () => {
  const graph = buildHandoffGraph({ definition });
  const layers = Object.fromEntries(graph.nodes.map((node) => [node.id, node.layer]));
  assert.equal(layers[ENTRYPOINT_NODE_ID], 0);
  // billing -> technical_support is a forward edge; the reverse one must not push billing down.
  assert.equal(layers.billing, 1);
  assert.equal(layers.technical_support, 2);
  const perLayer = graph.nodes.filter((node) => node.layer === 1).map((node) => node.order);
  assert.deepEqual(perLayer, [0]);
});

test("prefers the compiled session topology once a session is live", () => {
  const graph = buildHandoffGraph({ definition, handoffState: sessionState });
  assert.equal(graph.source, "session");
  assert.equal(graph.activeNodeId, "billing");
  assert.equal(graph.availableNodeId, "billing");
  assert.deepEqual(graph.availableEdgeIds, ["billing_to_technical_support"]);
  assert.equal(graph.stats.transferCount, 1);
  assert.equal(graph.stats.maxTransfers, 6);
  assert.equal(graph.nodes.find((node) => node.id === ENTRYPOINT_NODE_ID).implicit, true);
  // Edge descriptions are prompt text and are absent from HandoffEdgeState.
  assert.match(graph.edges.find((edge) => edge.id === "entrypoint_to_billing").description, /invoices/);
});

test("still draws a node the session compiled but the definition never described", () => {
  const graph = buildHandoffGraph({
    definition,
    handoffState: { ...sessionState, nodes: [...sessionState.nodes, { id: "escalation", description: "Implicit.", implicit: true }] },
  });
  const node = graph.nodes.find((item) => item.id === "escalation");
  assert.equal(node.authored, false);
  assert.equal(node.instructions, "");
  assert.equal(node.description, "Implicit.");
});

test("carries MCP declarations through structurally so a node can be probed", () => {
  const graph = buildHandoffGraph({
    definition: {
      handoff: {
        edges: [{ id: "e", source: "$entrypoint", target: "ask" }],
        nodes: [{
          id: "ask",
          config: {
            tools: [{
              type: "mcp",
              server_label: "interview-practice",
              server_url: "https://example.invalid/mcp/interview",
              project_connection_id: "conn-1",
              allowed_tools: ["get_next_question", "record_answer"],
              require_approval: "never",
              response_scheduling: "when_idle",
            }],
          },
        }],
      },
    },
  });
  const [spec] = graph.nodes.find((node) => node.id === "ask").toolSpecs;
  assert.equal(spec.kind, "mcp");
  assert.equal(spec.serverUrl, "https://example.invalid/mcp/interview");
  assert.equal(spec.projectConnectionId, "conn-1");
  assert.deepEqual(spec.allowedTools, ["get_next_question", "record_answer"]);
  assert.equal(spec.responseScheduling, "when_idle");
});

test("a function tool is never mistaken for something probeable", () => {
  const graph = buildHandoffGraph({
    definition: {
      handoff: {
        edges: [{ id: "e", source: "$entrypoint", target: "ask" }],
        nodes: [{
          id: "ask",
          config: {
            tools: [{
              type: "function",
              name: "lookup_employee",
              description: "Resolve an employee.",
              parameters: { properties: { staff_id: { type: "string" } } },
            }],
          },
        }],
      },
    },
  });
  const [spec] = graph.nodes.find((node) => node.id === "ask").toolSpecs;
  assert.equal(spec.kind, "function");
  assert.equal(spec.label, "lookup_employee");
  assert.equal(spec.serverUrl, undefined);
  assert.deepEqual(Object.keys(spec.parameters), ["staff_id"]);
});
