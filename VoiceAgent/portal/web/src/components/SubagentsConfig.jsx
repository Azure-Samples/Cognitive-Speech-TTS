// Copyright (c) Microsoft. All rights reserved.
// Sub-agents configuration (subagents design §3.1), a section parallel to Tools. Lets the user attach
// one or more EXISTING sibling text agents that the voice agent can forward turns to
// (forward_to_subagent), and set each specialist's response-delivery policy:
//   - immediate_ack        — speak a short "let me check…" before forwarding (fills the otherwise
//                            silent function-call turn); off => the pre-forward turn is silent.
//   - gap_filling_interval — seconds with no subagent content + no user input before a gap-filling
//                            prompt ("still working on it…") is injected during a slow forward.
//   - enable_delta_progress / progress_update_interval — optionally narrate bounded streamed progress
//                            with an independent cadence for each consultation.
// Because a voice agent can only forward to an EXISTING agent, the user can also mint a plain
// text (kind: "prompt") sub-agent inline; on success it is auto-selected. The combined result
// { subagents } is lifted to the parent for inclusion in definition.subagent_config.

import { useEffect, useState } from "react";
import {
  withApiVersion,
  serviceHeaders,
  buildCreatePromptAgentBody,
  buildVersionCreateRequest,
  agentResourceFromVersion,
  newAgentName,
  resolveSubagentCapabilities,
} from "../lib/serviceContract.js";
import { Field, Icon, Toggle } from "./ConfigControls.jsx";

const DEFAULT_RESPONSE_POLICY = Object.freeze({
  immediate_ack: false,
  gap_filling_interval: 30,
  ack_instructions: "",
  gap_filling_instructions: "",
  enable_delta_progress: false,
  progress_instructions: "",
  progress_update_interval: 15,
});

function responsePolicyForWire(policy) {
  const result = {
    immediate_ack: Boolean(policy?.immediate_ack),
    gap_filling_interval: Number.isFinite(policy?.gap_filling_interval)
      ? policy.gap_filling_interval
      : DEFAULT_RESPONSE_POLICY.gap_filling_interval,
    enable_delta_progress: Boolean(policy?.enable_delta_progress),
    progress_update_interval: Number.isFinite(policy?.progress_update_interval)
      ? policy.progress_update_interval
      : DEFAULT_RESPONSE_POLICY.progress_update_interval,
  };
  for (const field of [
    "ack_instructions",
    "gap_filling_instructions",
    "progress_instructions",
  ]) {
    const value = String(policy?.[field] || "").trim();
    if (value) result[field] = value;
  }
  return result;
}

export function SubagentsConfig({ cfg, session, disabled, onChange }) {
  // ---- Existing agents (list + selection) ----
  const [agents, setAgents] = useState(null); // null = not loaded yet; [] = loaded, none found
  const [agentsState, setAgentsState] = useState({ text: "", kind: "" });
  // name -> { agent, responsePolicy } for the selected sub-agents.
  const [selectedAgents, setSelectedAgents] = useState({});
  const [search, setSearch] = useState("");

  // ---- Create a text (prompt) sub-agent inline ----
  const [subName, setSubName] = useState("");
  const [subModel, setSubModel] = useState("gpt-4.1");
  const [subDesc, setSubDesc] = useState("");
  const [subInstr, setSubInstr] = useState(
    'You are a specialist. Answer the user\'s question directly and concisely. '
    + 'Begin every reply with "The specialist says:".');
  const [createState, setCreateState] = useState({ text: "", kind: "" });

  const agentName = (a, i) => a?.name || a?.id || `(unnamed #${i + 1})`;

  // Best-effort capability text for a sub-agent, from the service agent's description.
  const agentCapabilities = (a) => resolveSubagentCapabilities(cfg, a);

  // Pull one displayable model name out of a service agent object (best-effort across shapes).
  const agentModel = (a) => {
    const def = a?.versions?.latest?.definition || a?.definition;
    return def?.model || null;
  };

  // Best-effort agent kind ("prompt" text vs "voice"/"prompt_voice") across service object shapes.
  const agentKind = (a) => {
    const def = a?.versions?.latest?.definition || a?.definition;
    return def?.kind || a?.kind || null;
  };

  // Exclude only legacy voice agents (kind: "prompt_voice"); all other kinds are kept.
  const isSelectableSubagent = (a) => agentKind(a) !== "prompt_voice";

  const toggleAgent = (a, i) => {
    const name = agentName(a, i);
    setSelectedAgents((prev) => {
      const next = { ...prev };
      if (next[name]) delete next[name];
      else {
        next[name] = {
          agent: a,
          responsePolicy: { ...DEFAULT_RESPONSE_POLICY },
        };
      }
      return next;
    });
  };

  const updateResponsePolicy = (name, patch) => {
    setSelectedAgents((prev) => {
      const selected = prev[name];
      if (!selected) return prev;
      return {
        ...prev,
        [name]: {
          ...selected,
          responsePolicy: {
            ...selected.responsePolicy,
            ...patch,
          },
        },
      };
    });
  };

  // Lift the complete per-subagent contract whenever selection or policy changes.
  useEffect(() => {
    if (!onChange) return;
    const subagents = Object.entries(selectedAgents).map(([name, selected]) => ({
      agent_name: name,
      agent_capabilities: agentCapabilities(selected.agent),
      response_policy: responsePolicyForWire(selected.responsePolicy),
    }));
    onChange({ subagents });
  }, [selectedAgents, onChange]);

  const listAgents = async () => {
    if (disabled || agentsState.kind === "warn") return;
    setAgentsState({ text: "listing…", kind: "warn" });
    try {
      // Fetch up to 50 agents in one request. The Foundry v1 agents API uses `limit` (1–100,
      // default 20) — NOT `top` — so a larger limit surfaces hosted and other agents beyond the
      // default page. The backend forwards the query verbatim to the service.
      const path = `${withApiVersion(cfg, "/agents")}&limit=50`;
      session?.logApi?.("GET", path);
      const resp = await fetch(path, { headers: serviceHeaders(cfg) });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || data.message || `HTTP ${resp.status}`);
      // Azure list convention: { value: [...] }; tolerate a couple of alternates.
      const raw = data.value || data.data || (Array.isArray(data) ? data : []);
      // Drop legacy voice agents (kind: "prompt_voice") — they aren't valid forward targets.
      const items = raw.filter(isSelectableSubagent);
      const hidden = raw.length - items.length;
      setAgents(items);
      const suffix = hidden > 0 ? ` (${hidden} prompt_voice hidden)` : "";
      setAgentsState({ text: `${items.length} agent${items.length === 1 ? "" : "s"}${suffix}`, kind: "ok" });
    } catch (e) {
      setAgents(null);
      setAgentsState({ text: `list failed: ${e.message || e}`, kind: "err" });
    }
  };

  // Create a text (prompt) agent, then refresh the list and auto-select it as a sub-agent.
  const createPromptAgent = async () => {
    if (disabled || createState.kind === "warn") return;
    const name = (subName || "").trim() || newAgentName("web-text-sub");
    if (!subModel.trim()) {
      setCreateState({ text: "model required", kind: "err" });
      return;
    }
    setCreateState({ text: "creating…", kind: "warn" });
    try {
      const body = buildCreatePromptAgentBody({
        name, model: subModel.trim(), instructions: subInstr.trim(),
        description: subDesc.trim(),
      });
      const { path, body: requestBody } = buildVersionCreateRequest(cfg, body);
      session?.logApi?.("POST", path);
      const resp = await fetch(path, {
        method: "POST",
        headers: serviceHeaders(cfg, { "Content-Type": "application/json" }),
        body: JSON.stringify(requestBody),
      });
      const result = await resp.json();
      if (!resp.ok) throw new Error(result.error?.message || result.error || result.message || `HTTP ${resp.status}`);
      const data = agentResourceFromVersion(name, result);
      const created = data.name;
      setCreateState({ text: `created ${created}`, kind: "ok" });
      setSubName("");
      // Auto-select the new agent as a sub-agent. Prefer the description as the capabilities text
      // (it's what `agent_capabilities` uses when re-selected from the list), then instructions.
      setSelectedAgents((prev) => ({
        ...prev,
        [created]: {
          agent: {
            name: created,
            description: subDesc.trim() || subInstr.trim() || "Specialist sub-agent.",
          },
          responsePolicy: { ...DEFAULT_RESPONSE_POLICY },
        },
      }));
      await listAgents();
    } catch (e) {
      setCreateState({ text: `create failed: ${e.message || e}`, kind: "err" });
    }
  };

  return (
    <div className="subagents-config">
      <div className="subsection-heading">
        <div><h3>Specialist subagents</h3><p>Forward a task to another agent in this project.</p></div>
        <button type="button" className="text-button" onClick={listAgents}
          disabled={disabled || agentsState.kind === "warn"}>
          <Icon name="refresh" />{agents === null ? "List agents" : "Refresh"}
        </button>
      </div>
      {agentsState.text ? <div className={`form-feedback ${agentsState.kind}`} role="status">{agentsState.text}</div> : null}
      {agents !== null ? (
        <>
          <Field label="Find a specialist">
            <input type="search" value={search} onChange={(event) => setSearch(event.target.value)}
              placeholder="Search agents by name" />
          </Field>
          <ul className="specialist-list">
            {agents.filter((agent, index) => agentName(agent, index).toLowerCase().includes(search.toLowerCase())).map((agent, index) => {
              const name = agentName(agent, index);
              return (
                <li key={name}>
                  <label>
                    <input type="checkbox" checked={Boolean(selectedAgents[name])} disabled={disabled}
                      onChange={() => toggleAgent(agent, index)} />
                    <span><strong>{name}</strong><small>{agentModel(agent) || agentKind(agent) || "Agent"}</small></span>
                  </label>
                </li>
              );
            })}
          </ul>
          {!agents.length ? <p className="field-hint">No agents found in this project.</p> : null}
        </>
      ) : <div className="small-empty"><Icon name="workflow" /><p>List existing agents to choose your specialists, or create one below.</p></div>}
      {Object.keys(selectedAgents).length ? (
        <div className="selected-specialists">{Object.keys(selectedAgents).map((name) => (
          <span className="subtle-badge" key={name} title={name}>{name}</span>
        ))}</div>
      ) : null}

      {Object.entries(selectedAgents).map(([name, { responsePolicy: policy }]) => (
        <details className="advanced-details specialist-policy" key={name}>
          <summary title={name}>Response policy · {name}</summary>
          <Toggle label="Immediate acknowledgement" checked={policy.immediate_ack} disabled={disabled}
            onChange={(immediate_ack) => updateResponsePolicy(name, { immediate_ack })}
            description="Say “let me check” before forwarding to this specialist." />
          <Field label="Acknowledgement instructions" optional>
            <textarea value={policy.ack_instructions} disabled={disabled} rows={2}
              onChange={(event) => updateResponsePolicy(name, { ack_instructions: event.target.value })} />
          </Field>
          <Field label="Gap-filling interval (seconds)" hint="Silence before the agent says it is still working on the request.">
            <input type="number" min="0" step="1" value={policy.gap_filling_interval} disabled={disabled}
              onChange={(event) => updateResponsePolicy(name, { gap_filling_interval: Number(event.target.value) })} />
          </Field>
          <Field label="Gap-filling instructions" optional>
            <textarea value={policy.gap_filling_instructions} disabled={disabled} rows={2}
              onChange={(event) => updateResponsePolicy(name, { gap_filling_instructions: event.target.value })} />
          </Field>
          <Toggle label="Stream progress updates" checked={policy.enable_delta_progress} disabled={disabled}
            onChange={(enable_delta_progress) => updateResponsePolicy(name, { enable_delta_progress })}
            description="Narrate partial progress during this consultation." />
          <Field label="Progress update interval (seconds)">
            <input type="number" min="0" step="1" value={policy.progress_update_interval} disabled={disabled}
              onChange={(event) => updateResponsePolicy(name, { progress_update_interval: Number(event.target.value) })} />
          </Field>
          <Field label="Progress instructions" optional>
            <textarea value={policy.progress_instructions} disabled={disabled} rows={2}
              onChange={(event) => updateResponsePolicy(name, { progress_instructions: event.target.value })} />
          </Field>
        </details>
      ))}
      <details className="advanced-details">
        <summary>Create a text subagent</summary>
        <p className="field-hint">Creates a prompt agent and selects it as a specialist.</p>
        <Field label="Subagent name" optional>
          <input type="text" value={subName} disabled={disabled} onChange={(event) => setSubName(event.target.value)}
            placeholder="Auto-generated when blank" />
        </Field>
        <Field label="Subagent model">
          <input type="text" value={subModel} disabled={disabled} onChange={(event) => setSubModel(event.target.value)} placeholder="gpt-4.1" />
        </Field>
        <Field label="Specialist capabilities" optional hint="Stored as the description and used to decide when to forward. Defaults to the instructions.">
          <input type="text" value={subDesc} disabled={disabled} onChange={(event) => setSubDesc(event.target.value)}
            placeholder="e.g. Resolves billing questions" />
        </Field>
        <Field label="Subagent instructions">
          <textarea value={subInstr} disabled={disabled} rows={4} onChange={(event) => setSubInstr(event.target.value)} />
        </Field>
        <button type="button" onClick={createPromptAgent} disabled={disabled || createState.kind === "warn"}>
          {createState.kind === "warn" ? "Creating…" : "Create text agent"}<Icon name="arrow" />
        </button>
        {createState.text ? <div className={`form-feedback ${createState.kind}`} role="status">{createState.text}</div> : null}
      </details>
    </div>
  );
}
