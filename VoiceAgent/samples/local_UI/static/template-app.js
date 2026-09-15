// Templates tab: the read-only template catalog, ported from
// docs/voice_agent/01_template_infa/01_template_v1/web/app.js (Templates page only).
//
// Every template has one fixed, published source agent. Voice preview talks to that agent directly;
// publishing creates a separate agent by copying the source's latest definition.

import { WorkflowGraph } from "./template-graph.js?v=20260915-1";

const $ = (id) => document.getElementById(id);

const state = {
  templates: [],
  template: null,
  service: null,
  building: false,
  publishedAgent: "",
};

const templateGraph = new WorkflowGraph($("graph-wrap"), {
  onSelectNode: (id) => showNode(templateGraph, state.template, id),
  onSelectEdge: (id) => showEdge(templateGraph, state.template, id),
});

/* ---------------- helpers ---------------- */

function make(tag, props = {}, ...children) {
  const node = Object.assign(document.createElement(tag), props);
  node.append(...children.filter((c) => c !== null && c !== undefined));
  return node;
}

let toastTimer = null;
function toast(text, bad = false) {
  const box = $("toast");
  box.textContent = text;
  box.classList.toggle("bad", bad);
  box.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (box.hidden = true), 4000);
}

async function api(path, options = undefined) {
  const response = await fetch(path, options);
  const text = await response.text();
  let payload = {};
  try {
    payload = text ? JSON.parse(text) : {};
  } catch {
    payload = { error: text };
  }
  if (!response.ok) throw new Error(payload.error || `${response.status} ${response.statusText}`);
  return payload;
}

function setResult(id, text, kind) {
  const box = $(id);
  box.hidden = false;
  box.className = `result${kind ? ` ${kind}` : ""}`;
  box.textContent = text;
}

function selectTab(scope, tab) {
  for (const button of scope.querySelectorAll(".tab")) {
    button.classList.toggle("active", button.dataset.tab === tab);
  }
  for (const panel of scope.querySelectorAll(".tab-panel")) {
    panel.classList.toggle("active", panel.dataset.panel === tab);
  }
}

function activateTabs(scope) {
  for (const tab of scope.querySelectorAll(".tab")) {
    tab.addEventListener("click", () => selectTab(scope, tab.dataset.tab));
  }
}

/* ---------------- renderers ---------------- */

function renderTags(tags = []) {
  if (!tags.length) return null;
  return make(
    "span",
    { className: "tag-row" },
    ...tags.map((tag) => make("span", { className: "tag", textContent: tag })),
  );
}

function renderBadges(box, detail, extra = []) {
  const chips = [
    ...extra,
    { text: `${detail.node_count ?? detail.graph.nodes.length - 1} nodes` },
    { text: `${detail.edge_count ?? detail.graph.edges.length} edges` },
    { text: `${detail.tool_count ?? (detail.tools || []).length} tools` },
  ];
  if (detail.error_count) chips.push({ text: `${detail.error_count} errors`, kind: "bad" });
  else chips.push({ text: "lint clean", kind: "good" });
  if (detail.warning_count) chips.push({ text: `${detail.warning_count} warnings`, kind: "warn" });
  box.replaceChildren(
    ...chips.map((c) => make("span", { className: `badge${c.kind ? ` ${c.kind}` : ""}`, textContent: c.text })),
  );
}

function renderConfig(box, groups) {
  box.replaceChildren();
  for (const group of groups) {
    const dl = make("dl", { className: "kv" });
    for (const item of group.items) {
      dl.append(
        make("dt", { textContent: item.label }),
        make("dd", { textContent: item.value }),
      );
    }
    box.append(make("div", { className: "config-group" }, make("h4", { textContent: group.title }), dl));
  }
}

function renderIssues(box, issues) {
  box.replaceChildren();
  if (!issues.length) {
    box.append(make("p", { className: "muted", textContent: "No lint errors or warnings." }));
    return;
  }
  for (const issue of issues) {
    box.append(
      make(
        "div",
        { className: `issue ${issue.severity}` },
        make("code", { textContent: issue.code }),
        make("span", { textContent: issue.message }),
      ),
    );
  }
}

function renderTools(box, detail) {
  box.replaceChildren();
  const servers = make("div", { className: "config-group" }, make("h4", { textContent: "Tool servers" }));
  for (const server of detail.tool_servers) {
    servers.append(
      make(
        "div",
        { className: "tool-row" },
        make("code", { textContent: server.id }),
        make("span", { className: "tool-kind", textContent: server.kind || "mcp" }),
        make("span", { className: "muted", textContent: server.module }),
      ),
    );
  }
  box.append(servers);

  const tools = make("div", { className: "config-group" }, make("h4", { textContent: `Tools (${detail.tools.length})` }));
  for (const tool of detail.tools) {
    const params = Object.entries(tool.parameters || {})
      .map(([name, schema]) => `${name}: ${schema.type || "?"}`)
      .join(", ");
    tools.append(
      make(
        "div",
        { className: "tool-row" },
        make("code", { textContent: tool.name }),
        make("span", { className: "tool-kind", textContent: tool.server || tool.kind || "function" }),
        make("span", { className: "muted", textContent: tool.description || "" }),
        make("span", { className: "tool-params", textContent: params ? `(${params})` : "(no arguments)" }),
      ),
    );
  }
  box.append(tools);
}

/* ---------------- node / edge modal ---------------- */

function closeModal() {
  const box = $("node-modal");
  box.hidden = true;
  box.replaceChildren();
  templateGraph.select(null);
  templateGraph.highlightEdges(null);
}

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !$("node-modal").hidden) closeModal();
});

function openModal(title, chips, ...sections) {
  const box = $("node-modal");
  box.replaceChildren(
    make("div", { className: "node-modal-backdrop", onclick: closeModal }),
    make(
      "div",
      { className: "node-modal-card", role: "dialog" },
      make(
        "header",
        { className: "node-modal-head" },
        title,
        make("div", { className: "node-modal-chips" }, ...chips),
        make("button", {
          type: "button",
          className: "node-modal-close",
          textContent: "✕",
          onclick: closeModal,
          ariaLabel: "Close",
        }),
      ),
      make("div", { className: "node-modal-body" }, ...sections),
    ),
  );
  box.hidden = false;
}

const chip = (text) => make("span", { className: "hg-chip", textContent: text });

function signature(tool) {
  const params = Object.entries(tool.parameters || {})
    .map(([name, schema]) => `${name}: ${schema.type || "?"}`)
    .join(", ");
  return params ? `(${params})` : "(no arguments)";
}

/* A template declares tool NAMES per node and servers separately, so the card is assembled from
 * both. `transport` is what the tool will actually be published as: a `kind: mcp` tool whose
 * server is not deployed still ships as a function declaration, and there is nothing to probe. */
function toolCard(tool, server, agentName) {
  const isMcp = tool.transport === "mcp";
  const status = make("div", {
    className: "probe-status",
    textContent: "not tested — Test calls the published agent's MCP server live",
  });

  const test = async () => {
    test.disabled = true;
    button.disabled = true;
    button.textContent = "testing…";
    status.className = "probe-status running";
    status.textContent = "testing…";
    try {
      const resp = await fetch("/api/mcp/probe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ agent: agentName, server_label: server?.server_label || server?.id || "" }),
      });
      const data = await resp.json();
      if (data.server_url) {
        url.textContent = data.server_url;
        url.hidden = false;
      }
      if (data.ok) {
        status.className = "probe-status good";
        status.textContent = `ok · ${data.latency_ms} ms · ${data.tools.length} tools on the server`;
      } else if (data.no_mcp) {
        status.className = "probe-status warn";
        status.textContent = "published as a function tool — the agent carries the declaration itself, "
          + "so there is no MCP endpoint to call";
      } else if (data.reached) {
        status.className = "probe-status warn";
        status.textContent = `reachable · HTTP ${data.http_status} in ${data.latency_ms} ms · ${data.error}`;
      } else {
        status.className = "probe-status bad";
        status.textContent = `unreachable · ${data.error || `HTTP ${resp.status}`}`;
      }
    } catch (error) {
      status.className = "probe-status bad";
      status.textContent = `failed · ${error.message}`;
    } finally {
      button.disabled = false;
      button.textContent = "Test";
    }
  };

  const button = make("button", {
    type: "button",
    className: "probe-btn",
    textContent: "Test",
    onclick: test,
    disabled: !agentName,
  });
  const url = make("span", { className: "tool-url", textContent: server?.server_url || "", hidden: !server?.server_url });

  return make(
    "div",
    { className: "tool-card" },
    make(
      "div",
      { className: "tool-card-head" },
      make("span", { className: `kind-chip ${isMcp ? "mcp" : "fn"}`,
        textContent: isMcp ? "MCP" : "FUNCTION" }),
      make("code", { textContent: tool.name }),
      server ? make("span", { className: "tool-count", textContent: server.id }) : null,
      isMcp ? button : null,
    ),
    tool.description ? make("p", { className: "tool-desc", textContent: tool.description }) : null,
    make("div", { className: "tool-params", textContent: signature(tool) }),
    make("div", { className: "tool-card-meta" },
      url,
      server?.module ? make("span", { textContent: `module: ${server.module}` }) : null),
    isMcp ? status : null,
  );
}

function showNode(graph, detail, nodeId) {
  graph.select(nodeId);
  graph.highlightEdges(nodeId);
  const node = detail?.graph.nodes.find((n) => n.id === nodeId);
  if (!node) return;

  const byName = new Map((detail.tools || []).map((tool) => [tool.name, tool]));
  const serverById = new Map((detail.tool_servers || []).map((server) => [server.id, server]));
  const used = (node.tools || []).map((name) => byName.get(name) || { name, kind: "function" });
  const outgoing = detail.graph.edges.filter((edge) => edge.from === nodeId);

  const title = make(
    "div",
    { className: "node-modal-title" },
    make("span", { className: "node-modal-kind", textContent: node.kind || "node" }),
    make("b", { textContent: node.label }),
    make("span", { className: "node-modal-sub", textContent: node.id }),
  );

  const chips = [
    chip(`tool_choice: ${node.tool_choice}`),
    chip(`${used.length} tools`),
    chip(`${outgoing.length} outgoing edges`),
  ];

  const instructions = make(
    "section",
    { className: "node-modal-section" },
    make("h4", { textContent: "Instructions" }),
    make("pre", { textContent: node.instructions || "(this node inherits the template instructions)" }),
  );

  const tools = make(
    "section",
    { className: "node-modal-section" },
    make("h4", { textContent: `Tools (${used.length})` }),
    used.length ? null : make("p", { className: "node-modal-empty", textContent: "This node carries no tools." }),
    ...used.map((tool) => toolCard(tool, serverById.get(tool.server), detail.agent_name)),
  );

  const edges = outgoing.length
    ? make(
      "section",
      { className: "node-modal-section" },
      make("h4", { textContent: "Outgoing edges" }),
      make("ul", { className: "node-modal-edges" }, ...outgoing.map((edge) => make(
        "li",
        {},
        make("button", {
          type: "button",
          className: "edge-jump",
          textContent: `→ ${edge.to}`,
          onclick: () => showNode(graph, detail, edge.to),
        }),
        make("span", { className: "edge-desc", textContent: edge.description }),
        chip(`target_response: ${edge.target_response}`),
      ))),
    )
    : null;

  openModal(title, chips, instructions, make("div", { className: "node-modal-col" }, tools, edges));
}

// An edge's description is not documentation: it is the routing condition the model is given,
// so it belongs next to the node prompts rather than in a tooltip alone.
function showEdge(graph, detail, edgeId) {
  graph.selectEdge(edgeId);
  const edge = detail?.graph.edges.find((e) => e.id === edgeId);
  if (!edge) return;

  const title = make(
    "div",
    { className: "node-modal-title" },
    make("span", { className: "node-modal-kind", textContent: "edge" }),
    make("b", { textContent: `${edge.from} → ${edge.to}` }),
    make("span", { className: "node-modal-sub", textContent: edge.id }),
  );

  openModal(
    title,
    [chip(`target_response: ${edge.target_response}`)],
    make(
      "section",
      { className: "node-modal-section" },
      make("h4", { textContent: "Transfer condition" }),
      make("pre", { textContent: edge.description || "(no condition described)" }),
      make("p", { className: "node-modal-empty" },
        make("button", {
          type: "button",
          className: "edge-jump",
          textContent: `open ${edge.to}`,
          onclick: () => showNode(graph, detail, edge.to),
        })),
    ),
  );
}

/* ---------------- catalog ---------------- */

async function loadTemplates(reload = false) {
  const payload = await api(`/api/templates${reload ? "?reload=1" : ""}`);
  if (!payload.available) {
    $("page-templates").hidden = true;
    $("page-unavailable").hidden = false;
    $("unavailable-reason").textContent = payload.reason || "catalog unavailable";
    return;
  }
  $("page-unavailable").hidden = true;
  $("page-templates").hidden = false;

  const templates = payload.templates;
  state.templates = templates;
  $("template-count").textContent = `${templates.length} available`;

  const list = $("template-list");
  list.replaceChildren();
  for (const t of templates) {
    const meta = make(
      "div",
      { className: "tc-meta" },
      make("span", { textContent: `${t.node_count} nodes` }),
      make("span", { textContent: `${t.tool_count} tools` }),
      make("span", { textContent: `${t.input_count} inputs` }),
    );
    if (t.error_count) meta.append(make("span", { className: "bad", textContent: `${t.error_count} errors` }));
    else if (t.warning_count) meta.append(make("span", { className: "warn", textContent: `${t.warning_count} warnings` }));

    const card = make(
      "button",
      { type: "button", className: `template-card${t.featured ? " featured" : ""}` },
      t.featured ? make("span", { className: "featured-label", textContent: "Featured MCP" }) : null,
      make("span", { className: "tc-cat", textContent: t.category }),
      make("span", { className: "tc-name", textContent: t.name }),
      make("span", { className: "tc-id", textContent: t.id }),
      make("p", { className: "tc-sum", textContent: t.summary }),
      renderTags(t.tags),
      meta,
    );
    card.style.setProperty("--accent", t.accent_color);
    card.dataset.templateId = t.id;
    card.addEventListener("click", () => selectTemplate(t.id));
    list.append(card);
  }
  for (const broken of payload.errors) {
    list.append(
      make(
        "div",
        { className: "issue error" },
        make("code", { textContent: broken.id }),
        make("span", { textContent: broken.error.split("\n")[0] }),
      ),
    );
  }
  if (templates.length) await selectTemplate(state.template?.id || templates[0].id);
}

async function selectTemplate(templateId) {
  const detail = await api(`/api/templates/${encodeURIComponent(templateId)}`);
  state.template = detail;
  for (const card of document.querySelectorAll("#template-list .template-card")) {
    card.classList.toggle("selected", card.dataset.templateId === templateId);
  }

  $("detail-name").textContent = detail.name;
  $("detail-desc").textContent = detail.description;
  $("detail-tags").replaceChildren(renderTags(detail.tags) || make("span", { className: "muted tiny-inline", textContent: "no tags" }));
  renderBadges($("detail-badges"), detail, [{ text: detail.category }]);
  templateGraph.render(detail.graph);
  closeModal();
  renderConfig($("config-body"), detail.config_groups);
  renderTools($("tools-body"), detail);
  renderIssues($("lint-body"), detail.issues);
  $("yaml-body").textContent = detail.yaml;
  const mcp = detail.mcp || {};
  $("publish-mcp-fields").hidden = !detail.requires_mcp;
  $("publish-mcp-token").value = "";
  $("publish-mcp-token-field").hidden = Boolean(mcp.auth_configured);
  $("publish-mcp-token").required = Boolean(
    detail.requires_mcp && !mcp.auth_configured,
  );
  $("publish-mcp-auth-state").textContent = mcp.auth_configured
    ? "Token configured by the local server."
    : "Paste a scoped token once; it is stored only in the new Foundry connection.";
  state.publishedAgent = "";
  $("tpl-result").hidden = true;
  refreshActionState();
  setResult("tpl-result", "Ready to publish a new independent Agent.", "");
}

/* ---------------- voice preview / publish ---------------- */

function openAgentInDemo(agent) {
  if (!agent) return;
  window.location.assign(`/?agent=${encodeURIComponent(agent)}`);
}

function startVoiceChat() {
  if (!state.template || state.building) return;
  if (state.publishedAgent) {
    openAgentInDemo(state.publishedAgent);
    return;
  }
  void publishMyAgent(true);
}

let buildProgressTimer = null;
let buildProgressValue = 8;

function setBuildProgress(value, title, detail) {
  buildProgressValue = Math.max(buildProgressValue, Math.min(100, Math.round(value)));
  $("build-progress-title").textContent = title;
  $("build-progress-detail").textContent = detail;
  $("build-progress-fill").style.width = `${buildProgressValue}%`;
  $("build-progress-bar").setAttribute("aria-valuenow", String(buildProgressValue));
  $("build-stage-copy").className = buildProgressValue >= 12 ? "active" : "";
  $("build-stage-publish").className = buildProgressValue >= 42 ? "active" : "";
  $("build-stage-launch").className = buildProgressValue >= 100 ? "active" : "";
}

function openBuildProgress(template) {
  clearInterval(buildProgressTimer);
  buildProgressValue = 8;
  $("build-progress").className = "build-progress";
  $("build-progress").hidden = false;
  $("build-progress-close").hidden = true;
  setBuildProgress(
    8,
    "Building your voice agent",
    `Preparing ${template.name}…`,
  );
  buildProgressTimer = setInterval(() => {
    const next = Math.min(92, buildProgressValue + Math.max(1, (92 - buildProgressValue) * 0.08));
    const detail = next < 42
      ? `Materializing the ${template.name} workflow…`
      : "Publishing a new independent Agent to the selected Project…";
    setBuildProgress(next, "Building your voice agent", detail);
  }, 500);
}

function showBuildFailure(message) {
  clearInterval(buildProgressTimer);
  $("build-progress").className = "build-progress failed";
  $("build-progress-title").textContent = "Build did not complete";
  $("build-progress-detail").textContent = message;
  $("build-progress-close").hidden = false;
}

function setBuildLocked(locked) {
  $("reload").disabled = locked;
  $("btn-voice").disabled = locked || !(state.publishedAgent || canPublish());
  $("btn-publish").disabled = locked || !canPublish();
  for (const card of document.querySelectorAll("#template-list .template-card")) {
    card.disabled = locked;
  }
}

function canPublish() {
  if (!state.template) return false;
  if (!state.template.requires_mcp) return true;
  return Boolean(
    state.template.mcp?.auth_configured
      || $("publish-mcp-token").value.trim(),
  );
}

function refreshActionState() {
  if (state.building) return;
  $("btn-voice").disabled = !(state.publishedAgent || canPublish());
  $("btn-publish").disabled = !canPublish();
}

async function publishMyAgent(autoOpen = false) {
  const template = state.template;
  if (!template || state.building) return;
  const templateId = template.id;
  state.building = true;
  setBuildLocked(true);
  openBuildProgress(template);
  try {
    const published = await api(
      `/api/templates/${encodeURIComponent(templateId)}/publish`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mcp_auth_token: $("publish-mcp-token").value.trim(),
        }),
      },
    );
    if (state.template?.id !== templateId) {
      throw new Error("The selected template changed while the agent was being built.");
    }
    clearInterval(buildProgressTimer);
    const version = published.version ? ` (version ${published.version})` : "";
    setResult(
      "tpl-result",
      `${published.agent_name}${version} was published in '${published.backend}'.`,
      "good",
    );
    setBuildProgress(
      100,
      "Your agent is ready",
      `${published.agent_name}${version} is ready to open in Live session.`,
    );
    state.publishedAgent = published.agent_name;
    toast(`built ${published.agent_name}`);
    await new Promise((resolve) => setTimeout(resolve, 500));
    $("build-progress").hidden = true;
    state.building = false;
    setBuildLocked(false);
    $("publish-mcp-token").value = "";
    refreshActionState();
    if (autoOpen) openAgentInDemo(published.agent_name);
  } catch (error) {
    $("publish-mcp-token").value = "";
    if (state.template?.id === templateId) {
      const message = `Build failed: ${error.message}`;
      state.building = false;
      setResult("tpl-result", message, "bad");
      showBuildFailure(message);
      toast(message, true);
    }
    refreshActionState();
  }
}

/* ---------------- boot ---------------- */

async function loadEnv() {
  const env = await api("/api/templates/env");
  $("roots").textContent = env.templates_root || "—";
}

activateTabs($("page-templates"));
$("btn-voice").addEventListener("click", () => startVoiceChat());
$("btn-publish").addEventListener("click", () => publishMyAgent(false));
$("publish-mcp-token").addEventListener("input", refreshActionState);
$("build-progress-close").addEventListener("click", () => {
  $("build-progress").hidden = true;
  setBuildLocked(false);
});
$("reload").addEventListener("click", async () => {
  try {
    await loadTemplates(true);
    toast("catalog reloaded");
  } catch (error) {
    toast(String(error.message), true);
  }
});

loadEnv().catch(() => {});
loadTemplates().catch((error) => toast(String(error.message), true));
