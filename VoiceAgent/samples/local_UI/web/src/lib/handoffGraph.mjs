// Copyright (c) Microsoft. All rights reserved.
// Turns a handoff agent into something drawable: the topology to render, the prompt each node
// actually carries, and which edges the live session can still take.
//
// Two sources describe the same graph and neither is sufficient alone:
//   - the authored definition (`definition.handoff`) carries the node prompts, tools and edge
//     descriptions, and is the only source available before a session exists;
//   - the live session state (`session.handoff`, HandoffState) is what the service compiled — it
//     includes `$entrypoint` and any implicit node, and it alone knows the active node and which
//     edges remain within the transfer/attempt budget.
// So topology comes from the session when one is live, prompts always from the definition.

export const ENTRYPOINT_NODE_ID = "$entrypoint";

const NODE_W = 168;
const NODE_H = 54;
const GAP_X = 24;
const GAP_Y = 30;
const PAD = 16;

export const GRAPH_GEOMETRY = { NODE_W, NODE_H, GAP_X, GAP_Y, PAD };

const asArray = (value) => (Array.isArray(value) ? value : []);
const asText = (value) => (typeof value === "string" ? value : "");

function toolLabel(tool) {
  if (typeof tool === "string") return tool;
  if (!tool || typeof tool !== "object") return "";
  return asText(tool.name) || asText(tool.server_label) || asText(tool.type);
}

export function toolLabels(tools) {
  return asArray(tools).map(toolLabel).filter(Boolean);
}

/* The label alone cannot answer "is this tool actually going to work": that needs the server URL
 * to call, the label to probe by, and the allowed_tools to compare against what the server lists.
 * So the declaration is carried through structurally, not flattened to a name. */
export function toolSpecs(tools) {
  return asArray(tools).map((tool) => {
    if (typeof tool === "string") return { kind: "function", label: tool, allowedTools: [] };
    if (!tool || typeof tool !== "object") return null;
    const type = asText(tool.type);
    if (type === "mcp") {
      return {
        kind: "mcp",
        label: asText(tool.server_label) || "mcp",
        serverLabel: asText(tool.server_label),
        serverUrl: asText(tool.server_url),
        projectConnectionId: asText(tool.project_connection_id),
        allowedTools: asArray(tool.allowed_tools).map(String),
        requireApproval: asText(tool.require_approval) || "never",
        responseScheduling: asText(tool.response_scheduling),
      };
    }
    return {
      kind: type === "toolbox" ? "toolbox" : "function",
      label: asText(tool.name) || asText(tool.toolbox_id) || type || "tool",
      description: asText(tool.description),
      parameters: tool.parameters?.properties || null,
      toolboxVersion: asText(tool.version),
      allowedTools: asArray(tool.allowed_tools).map(String),
    };
  }).filter(Boolean);
}

// The $entrypoint is never listed in `definition.handoff.nodes`: it IS the agent's own top-level
// configuration, so its prompt and tools are read from the definition root.
function authoredNodeIndex(definition) {
  const index = new Map([
    [ENTRYPOINT_NODE_ID, {
      description: "Top-level session configuration.",
      instructions: asText(definition?.instructions),
      tools: toolLabels(definition?.tools),
      toolSpecs: toolSpecs(definition?.tools),
      toolChoice: definition?.tool_choice || "auto",
      voice: asText(definition?.audio?.output?.voice?.name),
      model: asText(definition?.model),
    }],
  ]);
  for (const node of asArray(definition?.handoff?.nodes)) {
    if (!node?.id) continue;
    const config = node.config || {};
    index.set(String(node.id), {
      description: asText(node.description),
      instructions: asText(config.instructions),
      tools: toolLabels(config.tools),
      toolSpecs: toolSpecs(config.tools),
      toolChoice: config.tool_choice || "auto",
      voice: asText(config.voice?.name) || asText(config.voice),
      model: asText(config.model),
    });
  }
  return index;
}

function authoredEdgeIndex(definition) {
  const index = new Map();
  for (const edge of asArray(definition?.handoff?.edges)) {
    if (!edge?.id) continue;
    index.set(String(edge.id), edge);
  }
  return index;
}

/** Top-down layering: layer = longest path from the entrypoint, order = position within it. */
export function layoutGraph(nodes, edges, entry) {
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const outgoing = new Map(nodes.map((node) => [node.id, []]));
  for (const edge of edges) {
    if (outgoing.has(edge.source) && byId.has(edge.target)) outgoing.get(edge.source).push(edge.target);
  }

  // DFS first, so a back edge (billing -> support -> billing) does not distort the layering.
  const backEdges = new Set();
  const color = new Map();
  const visit = (start) => {
    const stack = [[start, outgoing.get(start)?.[Symbol.iterator]() ?? [][Symbol.iterator]()]];
    color.set(start, 1);
    while (stack.length) {
      const [node, children] = stack[stack.length - 1];
      const next = children.next();
      if (next.done) {
        color.set(node, 2);
        stack.pop();
        continue;
      }
      const child = next.value;
      if (color.get(child) === 1) backEdges.add(`${node}\u0000${child}`);
      else if (!color.get(child)) {
        color.set(child, 1);
        stack.push([child, outgoing.get(child)?.[Symbol.iterator]() ?? [][Symbol.iterator]()]);
      }
    }
  };

  if (byId.has(entry)) visit(entry);
  for (const node of nodes) if (!color.get(node.id)) visit(node.id);

  const dag = new Map(
    [...outgoing].map(([source, targets]) => [
      source,
      targets.filter((target) => !backEdges.has(`${source}\u0000${target}`)),
    ]),
  );
  const indegree = new Map(nodes.map((node) => [node.id, 0]));
  for (const targets of dag.values()) {
    for (const target of targets) indegree.set(target, (indegree.get(target) || 0) + 1);
  }

  const depth = new Map(nodes.map((node) => [node.id, 0]));
  const queue = [...indegree].filter(([, degree]) => degree === 0).map(([id]) => id);
  while (queue.length) {
    const current = queue.shift();
    for (const next of dag.get(current) || []) {
      depth.set(next, Math.max(depth.get(next) || 0, (depth.get(current) || 0) + 1));
      indegree.set(next, indegree.get(next) - 1);
      if (indegree.get(next) === 0) queue.push(next);
    }
  }

  const perLayer = new Map();
  for (const node of nodes) {
    const layer = depth.get(node.id) || 0;
    node.layer = layer;
    node.order = perLayer.get(layer) || 0;
    perLayer.set(layer, node.order + 1);
  }
  return nodes;
}

export function buildHandoffGraph({ definition = null, handoffState = null } = {}) {
  const runtimeNodes = asArray(handoffState?.nodes);
  const runtimeEdges = asArray(handoffState?.edges);
  const authoredGraph = definition?.handoff;
  const live = runtimeNodes.length > 0 && runtimeEdges.length > 0;
  if (!live && !asArray(authoredGraph?.edges).length) return null;

  const prompts = authoredNodeIndex(definition);
  const authoredEdges = authoredEdgeIndex(definition);

  const edges = (live ? runtimeEdges : asArray(authoredGraph?.edges)).map((edge) => {
    const authored = authoredEdges.get(String(edge.id)) || {};
    return {
      id: String(edge.id),
      source: String(edge.source),
      target: String(edge.target),
      // HandoffEdgeState carries no description (it is prompt text), so it only ever comes from
      // the definition — which is also what the model was given to choose this edge with.
      description: asText(authored.description),
      targetResponse: edge.target_response || authored.target_response || "auto",
      transferMessage: asText(edge.transfer_message ?? authored.transfer_message),
      cancelOnInterruption: Boolean(edge.cancel_on_interruption ?? authored.cancel_on_interruption),
      delayMs: Number(edge.delay_ms ?? authored.delay_ms ?? 0),
    };
  });

  const ids = live
    ? runtimeNodes.map((node) => String(node.id))
    : [ENTRYPOINT_NODE_ID, ...asArray(authoredGraph?.nodes).map((node) => String(node.id))];
  const runtimeById = new Map(runtimeNodes.map((node) => [String(node.id), node]));
  const sources = new Set(edges.map((edge) => edge.source));

  const nodes = ids.map((id) => {
    const prompt = prompts.get(id) || {};
    const runtime = runtimeById.get(id) || {};
    return {
      id,
      label: id === ENTRYPOINT_NODE_ID ? "entrypoint" : id,
      kind: id === ENTRYPOINT_NODE_ID ? "entry" : sources.has(id) ? "node" : "terminal",
      description: asText(runtime.description) || asText(prompt.description),
      instructions: asText(prompt.instructions),
      tools: prompt.tools || [],
      toolSpecs: prompt.toolSpecs || [],
      toolChoice: prompt.toolChoice || "auto",
      voice: asText(prompt.voice),
      model: asText(prompt.model),
      implicit: Boolean(runtime.implicit),
      // A node the session compiled but the definition never described has no prompt to show.
      authored: prompts.has(id),
    };
  });

  layoutGraph(nodes, edges, ENTRYPOINT_NODE_ID);

  return {
    source: live ? "session" : "definition",
    entrypoint: ENTRYPOINT_NODE_ID,
    nodes,
    edges,
    activeNodeId: asText(handoffState?.active_node_id) || null,
    availableEdgeIds: asArray(handoffState?.available_edge_ids).map(String),
    // `available_edge_ids` is scoped to the node that was active when this state was published.
    // Kept beside it so a caller can tell a stale list from a current one instead of guessing.
    availableNodeId: asText(handoffState?.active_node_id) || null,
    stats: {
      pipelineFamily: asText(handoffState?.pipeline_family),
      nodeGeneration: Number(handoffState?.node_generation ?? 0),
      transferCount: Number(handoffState?.transfer_count ?? 0),
      attemptCount: Number(handoffState?.attempt_count ?? 0),
      maxTransfers: Number(authoredGraph?.max_transfers ?? 0),
    },
  };
}

export function graphSize(nodes) {
  const layers = new Set(nodes.map((node) => node.layer));
  const widest = Math.max(1, ...[...layers].map(
    (layer) => nodes.filter((node) => node.layer === layer).length,
  ));
  return {
    widest,
    // +48 leaves the lane a back edge is routed through on the right-hand side.
    width: PAD * 2 + widest * NODE_W + (widest - 1) * GAP_X + 48,
    height: PAD * 2 + layers.size * NODE_H + (layers.size - 1) * GAP_Y,
  };
}

/** Centres each layer under the widest one, so the diagram reads as a funnel. */
export function centeredNodeBox(node, nodes, widest) {
  const row = nodes.filter((item) => item.layer === node.layer).length;
  const rowWidth = row * NODE_W + (row - 1) * GAP_X;
  const left = PAD + (widest * NODE_W + (widest - 1) * GAP_X - rowWidth) / 2;
  return {
    x: left + node.order * (NODE_W + GAP_X),
    y: PAD + node.layer * (NODE_H + GAP_Y),
    width: NODE_W,
    height: NODE_H,
  };
}

export function edgePath(from, to, rightmost) {
  if (to.y > from.y) {
    const sx = from.x + NODE_W / 2;
    const sy = from.y + NODE_H;
    const tx = to.x + NODE_W / 2;
    const ty = to.y;
    const dy = Math.max(18, (ty - sy) / 2);
    return `M${sx},${sy} C${sx},${sy + dy} ${tx},${ty - dy} ${tx},${ty}`;
  }
  // Back or sibling edge: route around the right-hand side rather than through the nodes.
  const sx = from.x + NODE_W;
  const sy = from.y + NODE_H / 2;
  const tx = to.x + NODE_W;
  const ty = to.y + NODE_H / 2;
  const bend = rightmost + 34;
  return `M${sx},${sy} C${bend},${sy} ${bend},${ty} ${tx},${ty}`;
}
