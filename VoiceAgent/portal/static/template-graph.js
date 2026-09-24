/* Local UI handoff graph: layer -> row, order -> column.
   Nodes carry their tool whitelist and tool_choice, edges their routing condition.
   Live-call state stays in the dashboard Demo tab. */

const NS = "http://www.w3.org/2000/svg";
const W = 168;
const H = 58;
const GAP_X = 24;
const GAP_Y = 44;
const PAD = 20;

function el(name, attrs = {}, text) {
  const node = document.createElementNS(NS, name);
  for (const [k, v] of Object.entries(attrs)) {
    if (v !== undefined && v !== null) node.setAttribute(k, String(v));
  }
  if (text !== undefined) node.textContent = text;
  return node;
}

function clip(text, max) {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

export class WorkflowGraph {
  constructor(container, { onSelectNode, onSelectEdge } = {}) {
    this.container = container;
    this.onSelectNode = onSelectNode || (() => {});
    this.onSelectEdge = onSelectEdge || (() => {});
    this.positions = new Map();
    this.nodeEls = new Map();
    this.edgeEls = new Map();
  }

  render(graph) {
    this.container.replaceChildren();
    this.positions.clear();
    this.nodeEls.clear();
    this.edgeEls.clear();
    if (!graph || !graph.nodes.length) {
      this.container.append(
        Object.assign(document.createElement("p"), {
          className: "muted",
          textContent: "No graph to draw — the template.yaml does not parse.",
        }),
      );
      return;
    }

    const byLayer = new Map();
    for (const node of graph.nodes) {
      if (!byLayer.has(node.layer)) byLayer.set(node.layer, []);
      byLayer.get(node.layer).push(node);
    }
    const layers = [...byLayer.keys()].sort((a, b) => a - b);
    const widest = Math.max(...[...byLayer.values()].map((l) => l.length));

    const width = PAD * 2 + widest * W + (widest - 1) * GAP_X + 48; // 48 = room for back edges
    const height = PAD * 2 + layers.length * H + (layers.length - 1) * GAP_Y;

    const svg = el("svg", { width, height, viewBox: `0 0 ${width} ${height}` });
    const defs = el("defs");
    const marker = el("marker", {
      id: "arrow", viewBox: "0 0 8 8", refX: 7, refY: 4,
      markerWidth: 7, markerHeight: 7, orient: "auto-start-reverse",
    });
    marker.appendChild(el("path", { d: "M0,0 L8,4 L0,8 z", fill: "#c8c6c4" }));
    defs.appendChild(marker);
    svg.appendChild(defs);

    const edgeLayer = el("g");
    const nodeLayer = el("g");
    svg.append(edgeLayer, nodeLayer);

    layers.forEach((layer, li) => {
      const items = byLayer.get(layer);
      const rowWidth = items.length * W + (items.length - 1) * GAP_X;
      const left = PAD + (widest * W + (widest - 1) * GAP_X - rowWidth) / 2;
      items.forEach((node, ni) => {
        const x = left + ni * (W + GAP_X);
        const y = PAD + li * (H + GAP_Y);
        this.positions.set(node.id, { x, y });
        nodeLayer.appendChild(this._node(node, x, y));
      });
    });

    const rightmost = PAD + widest * W + (widest - 1) * GAP_X;
    for (const edge of graph.edges) {
      const from = this.positions.get(edge.from);
      const to = this.positions.get(edge.to);
      if (!from || !to) continue;
      edgeLayer.appendChild(this._edge(edge, from, to, rightmost));
    }

    this.container.appendChild(svg);
  }

  _edge(edge, from, to, rightmost) {
    const { d, mid } = this._path(from, to, rightmost);
    const g = el("g", { class: "gedge", "data-from": edge.from, "data-edge-id": edge.id });
    g.appendChild(el("title", {}, `${edge.id}: ${edge.description}`));
    g.appendChild(el("path", { class: "eline", d, "marker-end": "url(#arrow)" }));
    // A 1.5px curve is almost unclickable, so the pointer target is a fat invisible copy of it
    // plus a handle at the midpoint that is visible enough to aim at.
    g.appendChild(el("path", { class: "ghit", d }));
    g.appendChild(el("rect", {
      class: "ehandle", x: mid.x - 5, y: mid.y - 5, width: 10, height: 10, rx: 2, ry: 2,
    }));
    g.addEventListener("click", () => this.onSelectEdge(edge.id));
    this.edgeEls.set(edge.id, g);
    return g;
  }

  /** Both curves are cubic Béziers, so the midpoint is (P0 + 3P1 + 3P2 + P3) / 8 at t = 0.5. */
  _path(from, to, rightmost) {
    if (to.y > from.y) {
      const sx = from.x + W / 2;
      const sy = from.y + H;
      const tx = to.x + W / 2;
      const ty = to.y;
      const dy = Math.max(18, (ty - sy) / 2);
      return {
        d: `M${sx},${sy} C${sx},${sy + dy} ${tx},${ty - dy} ${tx},${ty}`,
        mid: { x: (sx + tx) / 2, y: (sy + ty) / 2 },
      };
    }
    // back or sibling edge: route around the right-hand side
    const sx = from.x + W;
    const sy = from.y + H / 2;
    const tx = to.x + W;
    const ty = to.y + H / 2;
    const bend = rightmost + 34;
    return {
      d: `M${sx},${sy} C${bend},${sy} ${bend},${ty} ${tx},${ty}`,
      mid: { x: (sx + 6 * bend + tx) / 8, y: (sy + ty) / 2 },
    };
  }

  _node(node, x, y) {
    const g = el("g", {
      class: `gnode ${node.kind || "node"}`,
      transform: `translate(${x},${y})`,
      "data-node-id": node.id,
    });
    g.appendChild(el("rect", { width: W, height: H }));
    g.appendChild(el("text", { class: "glabel", x: 10, y: 20 }, clip(node.label, 21)));
    const tools = node.tools || [];
    g.appendChild(
      el("text", { class: "gtools", x: 10, y: 35 }, tools.length ? clip(tools.join(", "), 28) : "no tools"),
    );
    if (node.tool_choice && node.tool_choice !== "auto") {
      g.appendChild(el("text", { class: "greq", x: 10, y: 49 }, `tool_choice: ${node.tool_choice}`));
    }
    g.addEventListener("click", () => this.onSelectNode(node.id));
    this.nodeEls.set(node.id, g);
    return g;
  }

  select(nodeId) {
    for (const [id, g] of this.nodeEls) g.classList.toggle("selected", id === nodeId);
    for (const g of this.edgeEls.values()) g.classList.remove("selected");
  }

  selectEdge(edgeId) {
    for (const [id, g] of this.edgeEls) {
      g.classList.toggle("selected", id === edgeId);
      g.classList.remove("outgoing");
    }
    for (const g of this.nodeEls.values()) g.classList.remove("selected");
  }

  highlightEdges(nodeId) {
    for (const g of this.edgeEls.values()) {
      g.classList.toggle("outgoing", Boolean(nodeId) && g.getAttribute("data-from") === nodeId);
    }
  }
}
