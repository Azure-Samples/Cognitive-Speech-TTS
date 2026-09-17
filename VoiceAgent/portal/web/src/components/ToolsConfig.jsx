// Copyright (c) Microsoft. All rights reserved.
// Tool configuration, grouped into three independent tool kinds the user can attach to
// the agent being created:
//   1. MCP        — a Voice Live-executed MCP tool; sub-options select the AUTH (direct URL with
//                   no-auth/OAuth, or a project connection with no-auth/api-key/Entra).
//   2. Toolbox    — a Foundry toolbox reference (web/file search, etc.) via the toolbox MCP.
//   3. Foundry IQ — a knowledge base: a plain `mcp` tool carrying BOTH an explicit KB MCP server_url
//                   AND a project_connection_id whose (Azure AI Search) credential the service resolves.
//   4. End conversation — a Voice Live-executed platform control represented by the public
//                   `{type: "system", name: "end_conversation"}` shape.
// Each group emits its public agent-definition shape; the combined array is lifted via onChange so the
// parent can include it in /create-agent. At session construction the service adds
// `response_scheduling: "when_idle"` only to ordinary Voice Live `mcp` tools. Foundry IQ and toolbox
// use specialized in-service types that schedule their own follow-up responses.

import { useEffect, useState } from "react";
import { buildEndConversationTool } from "../lib/serviceContract.js";
import { Field, Icon, Toggle } from "./ConfigControls.jsx";

function ToolCard({ title, description, icon, enabled, onChange, disabled, children }) {
  return (
    <div className={`tool-card${enabled ? " enabled" : ""}`}>
      <div className="tool-card-heading">
        <span className="tool-icon"><Icon name={icon} /></span>
        <Toggle label={title} description={description} checked={enabled} onChange={onChange} disabled={disabled} />
      </div>
      <div className="tool-card-body" hidden={!enabled}>{children}</div>
    </div>
  );
}

// Parse a comma / whitespace / newline-separated list of tool names into a string array.
function parseToolList(s) {
  return (s || "").split(/[\s,]+/).map((x) => x.trim()).filter(Boolean);
}

export function ToolsConfig({ cfg, disabled, onChange }) {
  const allPresets = cfg?.mcpAuthPresets || [];
  // MCP group offers only the auth presets (url / connection); Foundry IQ has its own group below.
  const mcpAuthPresets = allPresets.filter((p) => p.mode !== "foundry_iq");
  const foundryIqPreset = allPresets.find((p) => p.mode === "foundry_iq");

  // ---- 1. MCP tool state (auth sub-options only) ----
  const [mcpOn, setMcpOn] = useState(false);
  const [mcpLabel, setMcpLabel] = useState("mcp");
  const [mcpMode, setMcpMode] = useState("url"); // "url" | "connection"
  const [mcpUrl, setMcpUrl] = useState("");
  const [mcpAuth, setMcpAuth] = useState("");
  const [mcpConn, setMcpConn] = useState("");
  const [mcpApproval, setMcpApproval] = useState(false); // require approval before each MCP call
  const [mcpAllowed, setMcpAllowed] = useState(""); // optional allowed_tools allowlist
  const [mcpPreset, setMcpPreset] = useState(""); // selected auth preset (fills the fields below)

  // Apply a one-click MCP auth preset: fill mode + url/connection + label so each
  // auth mode (no-auth, OAuth, API-key/CustomKeys, Entra/ProjectManagedIdentity) is one selection.
  const applyPreset = (value) => {
    setMcpPreset(value);
    const p = mcpAuthPresets.find((x) => x.value === value);
    if (!p) return;
    setMcpMode(p.mode || "url");
    setMcpLabel(p.server_label || "mcp");
    setMcpUrl(p.server_url || "");
    setMcpAuth(p.authorization || "");
    setMcpConn(p.project_connection_id || "");
    setMcpAllowed(p.allowed_tools || "");
  };

  // ---- 2. Toolbox tool state ----
  // Pre-fill the default toolbox (e.g. foundry-tools-test v2) from config so the user can enable it
  // with one click; values stay editable.
  const [tbOn, setTbOn] = useState(false);
  const [tbName, setTbName] = useState(cfg?.defaultToolbox?.name || "");
  const [tbVer, setTbVer] = useState(cfg?.defaultToolbox?.version || "");
  const [tbAllowed, setTbAllowed] = useState(""); // optional allowed_tools allowlist

  // ---- 3. Foundry IQ knowledge base state ----
  // Pre-fill from the backend's foundry_iq preset (when configured) so it's one click to enable.
  const [fiqOn, setFiqOn] = useState(false);
  const [fiqLabel, setFiqLabel] = useState(foundryIqPreset?.server_label || "kb-foundry-iq");
  const [fiqUrl, setFiqUrl] = useState(foundryIqPreset?.server_url || "");
  const [fiqConn, setFiqConn] = useState(foundryIqPreset?.project_connection_id || "");
  const [fiqApproval, setFiqApproval] = useState(false);
  const [fiqAllowed, setFiqAllowed] = useState("");

  // ---- 4. End-conversation system tool state ----
  const [endConversationOn, setEndConversationOn] = useState(false);
  const [endConversationDescription, setEndConversationDescription] = useState("");

  // Rebuild the tools array whenever any field changes and lift it to the parent.
  useEffect(() => {
    const tools = [];
    // 1. MCP
    if (mcpOn) {
      const t = { type: "mcp", server_label: mcpLabel || "mcp", require_approval: mcpApproval ? "always" : "never" };
      if (mcpMode === "connection") {
        if (mcpConn.trim()) t.project_connection_id = mcpConn.trim();
      } else {
        if (mcpUrl.trim()) t.server_url = mcpUrl.trim();
        if (mcpAuth.trim()) t.authorization = mcpAuth.trim();
      }
      const allowed = parseToolList(mcpAllowed);
      if (allowed.length) t.allowed_tools = allowed;
      // Only include the tool once it has a URL or a connection.
      if (t.server_url || t.project_connection_id) tools.push(t);
    }
    // 2. Toolbox
    if (tbOn && tbName.trim() && tbVer.trim()) {
      const t = { type: "toolbox", toolbox_name: tbName.trim(), toolbox_version: tbVer.trim() };
      const allowed = parseToolList(tbAllowed);
      if (allowed.length) t.allowed_tools = allowed;
      tools.push(t);
    }
    // 3. Foundry IQ — a plain mcp tool carrying BOTH the explicit KB server_url AND a
    // project_connection_id whose credential the service resolves (keeping the explicit URL).
    if (fiqOn) {
      const t = { type: "mcp", server_label: fiqLabel || "kb-foundry-iq", require_approval: fiqApproval ? "always" : "never" };
      if (fiqUrl.trim()) t.server_url = fiqUrl.trim();
      if (fiqConn.trim()) t.project_connection_id = fiqConn.trim();
      const allowed = parseToolList(fiqAllowed);
      if (allowed.length) t.allowed_tools = allowed;
      // Include only once it has the explicit KB URL (a Foundry IQ tool is defined by its server_url).
      if (t.server_url) tools.push(t);
    }
    // 4. End conversation — the Agents service maps this public system-tool shape to Voice Live's
    // native end_conversation discriminator. A supplied description replaces Voice Live's default
    // model-facing guidance.
    if (endConversationOn) {
      tools.push(buildEndConversationTool(endConversationDescription));
    }
    onChange(tools);
  }, [
    mcpOn, mcpLabel, mcpMode, mcpUrl, mcpAuth, mcpConn, mcpApproval, mcpAllowed,
    tbOn, tbName, tbVer, tbAllowed,
    fiqOn, fiqLabel, fiqUrl, fiqConn, fiqApproval, fiqAllowed,
    endConversationOn, endConversationDescription,
    onChange,
  ]);

  return (
    <div className="tools-config">
      <ToolCard title="MCP server" icon="tools" enabled={mcpOn} onChange={setMcpOn} disabled={disabled}
        description="Connect external tools through an MCP endpoint.">
        {mcpAuthPresets.length ? (
          <Field label="Authentication preset" hint="Quick-fill no-auth, OAuth, API-key, or Microsoft Entra settings.">
            <select value={mcpPreset} disabled={disabled} onChange={(event) => applyPreset(event.target.value)}>
              <option value="">Custom configuration</option>
              {mcpAuthPresets.map((preset) => <option key={preset.value} value={preset.value}>{preset.label}</option>)}
            </select>
          </Field>
        ) : null}
        <Field label="MCP server label">
          <input type="text" value={mcpLabel} disabled={disabled} onChange={(event) => setMcpLabel(event.target.value)} placeholder="mcp" />
        </Field>
        <Field label="Authentication source">
          <select value={mcpMode} disabled={disabled} onChange={(event) => setMcpMode(event.target.value)}>
            <option value="url">Direct URL · no auth / OAuth</option>
            <option value="connection">Project connection · API key / Entra / no auth</option>
          </select>
        </Field>
        {mcpMode === "url" ? (
          <>
            <Field label="MCP server URL">
              <input type="text" value={mcpUrl} disabled={disabled} onChange={(event) => setMcpUrl(event.target.value)}
                placeholder="https://your-server.example/mcp" />
            </Field>
            <Field label="Authorization token" optional hint="Leave blank for an unauthenticated server.">
              <input type="password" autoComplete="off" value={mcpAuth} disabled={disabled}
                onChange={(event) => setMcpAuth(event.target.value)} placeholder="OAuth bearer token" />
            </Field>
          </>
        ) : (
          <Field label="MCP project connection ID" hint="The service resolves the connection’s URL and credentials.">
            <input type="text" value={mcpConn} disabled={disabled} onChange={(event) => setMcpConn(event.target.value)}
              placeholder="/subscriptions/…/connections/…" />
          </Field>
        )}
        <Toggle label="Approve MCP calls" checked={mcpApproval} disabled={disabled} onChange={setMcpApproval}
          description="Show an Approve / Reject prompt before each call." />
        <Field label="Allowed MCP tools" optional hint="Comma-separated tool names. Blank allows all tools.">
          <input type="text" value={mcpAllowed} disabled={disabled} onChange={(event) => setMcpAllowed(event.target.value)}
            placeholder="add, search" />
        </Field>
        {!(mcpMode === "url" ? mcpUrl.trim() : mcpConn.trim()) ? (
          <p className="field-hint validation-hint">Add a URL or connection to include this tool.</p>
        ) : null}
      </ToolCard>

      <ToolCard title="Foundry IQ" icon="book" enabled={fiqOn} onChange={setFiqOn} disabled={disabled}
        description="Ground answers in an Azure AI Search knowledge base.">
        <Field label="Knowledge base server label">
          <input type="text" value={fiqLabel} disabled={disabled} onChange={(event) => setFiqLabel(event.target.value)} />
        </Field>
        <Field label="Knowledge base MCP URL">
          <input type="text" value={fiqUrl} disabled={disabled} onChange={(event) => setFiqUrl(event.target.value)}
            placeholder="https://your-search.search.windows.net/knowledgebases/…/mcp" />
        </Field>
        <Field label="Knowledge base connection ID" hint="Supplies the Search credential; the MCP URL above is preserved.">
          <input type="text" value={fiqConn} disabled={disabled} onChange={(event) => setFiqConn(event.target.value)}
            placeholder="/subscriptions/…/connections/…" />
        </Field>
        <Toggle label="Approve knowledge base calls" checked={fiqApproval} disabled={disabled} onChange={setFiqApproval} />
        <Field label="Allowed knowledge base tools" optional hint="Blank allows all tools.">
          <input type="text" value={fiqAllowed} disabled={disabled} onChange={(event) => setFiqAllowed(event.target.value)} placeholder="knowledge_base_retrieve" />
        </Field>
        {!fiqUrl.trim() ? <p className="field-hint validation-hint">Add a knowledge base URL to include this tool.</p> : null}
      </ToolCard>

      <ToolCard title="Foundry Toolbox" icon="box" enabled={tbOn} onChange={setTbOn} disabled={disabled}
        description="Use a versioned collection of search and action tools.">
        <div className="field-grid">
          <Field label="Toolbox name">
            <input type="text" value={tbName} disabled={disabled} onChange={(event) => setTbName(event.target.value)} placeholder="foundry-tools-test" />
          </Field>
          <Field label="Toolbox version">
            <input type="text" value={tbVer} disabled={disabled} onChange={(event) => setTbVer(event.target.value)} placeholder="1" />
          </Field>
        </div>
        <Field label="Allowed toolbox tools" optional hint="Comma-separated tool names. Blank allows all tools.">
          <input type="text" value={tbAllowed} disabled={disabled} onChange={(event) => setTbAllowed(event.target.value)}
            placeholder="web_search, file_search" />
        </Field>
        {!tbName.trim() || !tbVer.trim() ? <p className="field-hint validation-hint">A name and version are required to include this toolbox.</p> : null}
      </ToolCard>

      <ToolCard title="End conversation" icon="phone" enabled={endConversationOn} onChange={setEndConversationOn}
        disabled={disabled} description="Let your agent end a session when its work is done.">
        <Field label="End-conversation instructions" optional
          hint="Tell the model to say any farewell before calling end_conversation. Voice Live closes the session.">
          <textarea rows={4} value={endConversationDescription} disabled={disabled}
            onChange={(event) => setEndConversationDescription(event.target.value)}
            placeholder="Leave blank to use Voice Live’s default guidance." />
        </Field>
      </ToolCard>
      <p className="field-hint">Tools are saved with the agent version and shared by Configure and Generate. Edit the saved YAML to update them or add further tool definitions.</p>
    </div>
  );
}
