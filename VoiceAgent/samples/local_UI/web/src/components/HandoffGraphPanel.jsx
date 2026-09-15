// Copyright (c) Microsoft. All rights reserved.
// Live handoff diagram for the demo session: which node is speaking now, which edges the session
// has taken, which it may still take — and, on click, the prompt that node actually carries.
// Ported from the finance-agent voice web UI (docs/voice_agent/09_finance_agent/v1).

import { Fragment, useEffect, useMemo, useState } from "react";
import { centeredNodeBox, edgePath, graphSize } from "../lib/handoffGraph.mjs";

function signature(tool) {
  const params = Object.entries(tool.parameters || {});
  if (params.length) {
    return `(${params.map(([name, schema]) => `${name}: ${schema?.type || "?"}`).join(", ")})`;
  }
  return tool.kind === "function" ? "(no arguments)" : "";
}

/* An MCP tool's declaration cannot tell you whether the server answers: the URL is written by the
 * author, the credential lives in the project connection the service holds, and the allowed_tools
 * list is a claim about what the server exposes. Test calls the server for real and reports which
 * of those three is wrong, because "the agent silently does nothing" usually means one of them is. */
function McpToolCard({ tool, agentName, enableProbe, showServerUrl }) {
  const [result, setResult] = useState(null);
  const [running, setRunning] = useState(false);

  useEffect(() => setResult(null), [agentName, tool.serverLabel]);

  const test = async () => {
    setRunning(true);
    setResult({ state: "running", text: "testing…" });
    const startedAt = performance.now();
    try {
      const resp = await fetch("/api/mcp/probe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ agent: agentName, server_label: tool.serverLabel }),
      });
      const data = await resp.json();
      const roundTrip = Math.round(performance.now() - startedAt);
      if (data.ok) {
        setResult({
          state: "good",
          text: `ok · ${data.latency_ms} ms (init ${data.initialize_ms} + tools/list ${data.tools_ms})`
            + ` · ${data.tools.length} tools · ${roundTrip} ms round trip`,
          detail: data.server_name ? `${data.server_name} ${data.server_version}` : "",
        });
      } else if (data.no_mcp) {
        setResult({
          state: "warn",
          text: "published as a function tool — the agent carries the declaration itself,"
            + " so there is no MCP endpoint to call",
        });
      } else if (data.reached) {
        setResult({
          state: "warn",
          text: `reachable · HTTP ${data.http_status} in ${data.latency_ms} ms · ${data.error}`,
        });
      } else {
        setResult({ state: "bad", text: `unreachable · ${data.error || `HTTP ${resp.status}`}` });
      }
    } catch (error) {
      setResult({ state: "bad", text: `failed · ${error.message}` });
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="tool-card">
      <div className="tool-card-head">
        <span className="kind-chip mcp">MCP</span>
        <code>{tool.serverLabel || "mcp"}</code>
        <span className="tool-count">{tool.allowedTools.length || "all"} tools</span>
        {enableProbe ? (
          <button type="button" className="probe-btn" onClick={test} disabled={running || !agentName}>
            {running ? "testing…" : "Test"}
          </button>
        ) : null}
      </div>
      <div className="tool-card-meta">
        {showServerUrl && tool.serverUrl
          ? <span className="tool-url" title={tool.serverUrl}>{tool.serverUrl}</span>
          : null}
        {tool.projectConnectionId
          ? <span className="tool-conn">connection: {tool.projectConnectionId}</span>
          : null}
        <span className="tool-flag">approval: {tool.requireApproval}</span>
        {tool.responseScheduling
          ? <span className="tool-flag">scheduling: {tool.responseScheduling}</span>
          : null}
      </div>
      {result ? (
        <div className={`probe-status ${result.state}`} title={result.detail || ""}>{result.text}</div>
      ) : enableProbe ? (
        <div className="probe-status">not tested — the server is called live when you press Test</div>
      ) : null}
      {tool.allowedTools.length ? (
        <ul className="tool-name-list">
          {tool.allowedTools.map((name) => <li key={name}><code>{name}</code></li>)}
        </ul>
      ) : null}
    </div>
  );
}

function FunctionToolCard({ tool }) {
  return (
    <div className="tool-card">
      <div className="tool-card-head">
        <span className={`kind-chip ${tool.kind === "toolbox" ? "toolbox" : "fn"}`}>
          {tool.kind === "toolbox" ? "TOOLBOX" : "FUNCTION"}
        </span>
        <code>{tool.label}</code>
        {tool.toolboxVersion ? <span className="tool-count">v{tool.toolboxVersion}</span> : null}
      </div>
      {tool.description ? <p className="tool-desc">{tool.description}</p> : null}
      {signature(tool) ? <div className="tool-params">{signature(tool)}</div> : null}
      {tool.allowedTools?.length ? (
        <ul className="tool-name-list">
          {tool.allowedTools.map((name) => <li key={name}><code>{name}</code></li>)}
        </ul>
      ) : null}
    </div>
  );
}

/* A modal rather than a panel under the diagram: a node's prompt runs to hundreds of words and its
 * tools each need a URL, an allow-list and a test result beside them. In a column that also holds
 * the graph that reads through a slot; over the page it reads as a page. */
function NodeModal({
  node, graph, agentName, enableMcpProbe, showMcpServerUrl, onClose, onOpenNode,
}) {
  const specs = node.toolSpecs || [];
  const mcp = specs.filter((tool) => tool.kind === "mcp");
  const functions = specs.filter((tool) => tool.kind !== "mcp");
  const outgoing = graph.edges.filter((edge) => edge.source === node.id);

  useEffect(() => {
    const onKey = (event) => { if (event.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="node-modal">
      <div className="node-modal-backdrop" onClick={onClose} />
      <div className="node-modal-card" role="dialog" aria-modal="true">
        <header className="node-modal-head">
          <div className="node-modal-title">
            <span className="node-modal-kind">{node.kind}</span>
            <b>{node.label}</b>
            <span className="node-modal-sub">{node.id}</span>
          </div>
          <div className="node-modal-chips">
            <span className="hg-chip">tool_choice: {node.toolChoice}</span>
            <span className="hg-chip">{mcp.length} MCP servers</span>
            {functions.length ? <span className="hg-chip">{functions.length} function tools</span> : null}
            <span className="hg-chip">{outgoing.length} outgoing edges</span>
            {node.voice ? <span className="hg-chip">voice: {node.voice}</span> : null}
            {node.model ? <span className="hg-chip">model: {node.model}</span> : null}
          </div>
          <button type="button" className="node-modal-close" onClick={onClose} aria-label="Close">✕</button>
        </header>

        <div className="node-modal-body">
          <section className="node-modal-section">
            <h4>Instructions</h4>
            {node.description ? <p className="node-modal-desc">{node.description}</p> : null}
            <pre>
              {node.instructions
                || (node.authored
                  ? "(no node instructions — this node inherits the session instructions)"
                  : "(this node was compiled by the service; the agent definition does not describe it)")}
            </pre>
          </section>

          <div className="node-modal-col">
            <section className="node-modal-section">
              <h4>Tools ({specs.length})</h4>
              {specs.length ? null : <p className="node-modal-empty">This node carries no tools.</p>}
              {mcp.map((tool) => (
                <McpToolCard
                  key={tool.serverLabel || tool.label}
                  tool={tool}
                  agentName={agentName}
                  enableProbe={enableMcpProbe}
                  showServerUrl={showMcpServerUrl}
                />
              ))}
              {functions.map((tool) => <FunctionToolCard key={tool.label} tool={tool} />)}
            </section>

            {outgoing.length ? (
              <section className="node-modal-section">
                <h4>Outgoing edges</h4>
                <ul className="node-modal-edges">
                  {outgoing.map((edge) => (
                    <li key={edge.id}>
                      <button type="button" className="edge-jump" onClick={() => onOpenNode(edge.target)}>
                        → {edge.target}
                      </button>
                      <span className="edge-desc">{edge.description}</span>
                      <span className="hg-chip">target_response: {edge.targetResponse}</span>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}

export function HandoffGraphPanel({
  graph, activeNodeId, takenEdgeIds, trail, agentName, enableMcpProbe = true,
  showMcpServerUrl = true,
}) {
  const [selectedId, setSelectedId] = useState(null);

  const { widest, width, height } = useMemo(() => graphSize(graph.nodes), [graph]);
  const boxes = useMemo(
    () => new Map(graph.nodes.map((node) => [node.id, centeredNodeBox(node, graph.nodes, widest)])),
    [graph, widest],
  );

  const taken = new Set(takenEdgeIds || []);
  const available = new Set(
    graph.availableNodeId && graph.availableNodeId === activeNodeId ? graph.availableEdgeIds : [],
  );
  const visited = new Set([graph.entrypoint, ...(trail || []).map((step) => step.nodeId)]);
  if (activeNodeId) visited.add(activeNodeId);
  const selected = graph.nodes.find((node) => node.id === selectedId) || null;
  const activeBox = activeNodeId ? boxes.get(activeNodeId) : null;
  const rightmost = width - 48;

  const { stats } = graph;
  const badges = [
    graph.source === "session" ? "live" : "authored",
    stats.transferCount
      ? `transfers: ${stats.transferCount}${stats.maxTransfers ? `/${stats.maxTransfers}` : ""}`
      : null,
    stats.pipelineFamily || null,
  ].filter(Boolean);

  return (
    <section className="handoff-graph">
      <div className="handoff-graph-head">
        <h3>Handoff graph</h3>
        <span className="handoff-active">
          active node: <code>{activeNodeId || graph.entrypoint}</code>
        </span>
        {badges.map((badge) => <span key={badge} className="handoff-badge">{badge}</span>)}
        <span className="handoff-hint">click a node to read its prompt</span>
      </div>

      <div className="handoff-graph-body">
        <div className="graph-wrap">
          <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
            <defs>
              <marker id="hg-arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                <path d="M0,0 L8,4 L0,8 z" fill="#c8c6c4" />
              </marker>
              <marker id="hg-arrow-active" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                <path d="M0,0 L8,4 L0,8 z" fill="#1a73e8" />
              </marker>
            </defs>

            <g>
              {graph.edges.map((edge) => {
                const from = boxes.get(edge.source);
                const to = boxes.get(edge.target);
                if (!from || !to) return null;
                const isTaken = taken.has(edge.id);
                const classes = ["gedge", isTaken ? "taken" : "", available.has(edge.id) ? "available" : ""];
                return (
                  <g key={edge.id} className={classes.filter(Boolean).join(" ")}>
                    <path
                      d={edgePath(from, to, rightmost)}
                      markerEnd={isTaken ? "url(#hg-arrow-active)" : "url(#hg-arrow)"}
                    >
                      <title>
                        {`${edge.id} (target_response: ${edge.targetResponse})`}
                        {edge.description ? `\n${edge.description}` : ""}
                        {edge.transferMessage ? `\ntransfer message: ${edge.transferMessage}` : ""}
                      </title>
                    </path>
                  </g>
                );
              })}
            </g>

            <g>
              {graph.nodes.map((node) => {
                const box = boxes.get(node.id);
                const classes = [
                  "gnode",
                  node.kind,
                  node.id === activeNodeId ? "active" : "",
                  visited.has(node.id) ? "visited" : "",
                  node.id === selectedId ? "selected" : "",
                ];
                const tools = node.tools.length ? node.tools.join(", ") : "no tools";
                return (
                  <g
                    key={node.id}
                    className={classes.filter(Boolean).join(" ")}
                    transform={`translate(${box.x},${box.y})`}
                    onClick={() => setSelectedId((current) => (current === node.id ? null : node.id))}
                  >
                    <rect width={box.width} height={box.height} />
                    <text className="glabel" x="10" y="20">{node.label}</text>
                    <text className="gtools" x="10" y="35">{tools}</text>
                    {node.toolChoice === "required"
                      ? <text className="greq" x="10" y="49">tool_choice: required</text>
                      : null}
                    <title>{node.description || node.label}</title>
                  </g>
                );
              })}
            </g>

            {activeBox ? (
              <g className="active-ring" transform={`translate(${activeBox.x},${activeBox.y})`}>
                <rect x="-5" y="-5" width={activeBox.width + 10} height={activeBox.height + 10} rx="9" ry="9" />
              </g>
            ) : null}
          </svg>
        </div>

        <ol className="handoff-trail">
          {(trail || []).map((step) => (
            <li key={`${step.at}-${step.nodeId}`}>
              <code>{step.nodeId}</code>
              {step.edgeId ? <span className="handoff-trail-edge">via {step.edgeId}</span> : null}
            </li>
          ))}
          {trail && trail.length ? null : <li className="handoff-trail-empty">no transfer yet</li>}
        </ol>
      </div>

      {selected ? (
        <NodeModal
          node={selected}
          graph={graph}
          agentName={agentName}
          enableMcpProbe={enableMcpProbe}
          showMcpServerUrl={showMcpServerUrl}
          onClose={() => setSelectedId(null)}
          onOpenNode={(id) => setSelectedId(id)}
        />
      ) : null}
    </section>
  );
}
