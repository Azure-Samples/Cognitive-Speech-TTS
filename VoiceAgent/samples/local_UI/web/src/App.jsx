import { useEffect, useMemo, useState } from "react";
import { asVoiceAgent } from "./lib/agentCatalog.mjs";
import { buildHandoffGraph } from "./lib/handoffGraph.mjs";
import {
  filterProjectsByName,
  projectDisplayValue,
  resolveProjectEndpoint,
} from "./lib/projectPicker.mjs";
import { useVoiceSession } from "./hooks/useVoiceSession.js";
import { ChatPanel } from "./components/ChatPanel.jsx";
import { HandoffGraphPanel } from "./components/HandoffGraphPanel.jsx";
import { Icon } from "./components/ConfigControls.jsx";

function errorMessage(error) {
  return error instanceof Error ? error.message : String(error);
}

function customerConfig(payload) {
  return {
    apiVersion: payload.api_version,
    foundryFeatures: payload.foundry_features,
    backend: payload.project || "Not configured",
    host: payload.endpoint || "",
    configured: Boolean(payload.configured),
  };
}

async function readJson(path, options) {
  const response = await fetch(path, options);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `${response.status} ${response.statusText}`);
  return payload;
}

export function App() {
  const [cfg, setCfg] = useState(null);
  const [agents, setAgents] = useState([]);
  const [agent, setAgent] = useState(null);
  const [projects, setProjects] = useState([]);
  const [projectInput, setProjectInput] = useState("");
  const [projectResultsOpen, setProjectResultsOpen] = useState(false);
  const [projectsState, setProjectsState] = useState({ loading: true, error: "" });
  const [agentListState, setAgentListState] = useState({ loading: true, error: "" });
  const session = useVoiceSession();

  const handoffGraph = useMemo(() => {
    if (!agent?.definition && !session.handoffState) return null;
    return buildHandoffGraph({
      definition: agent?.definition || null,
      handoffState: session.handoffState,
    });
  }, [agent, session.handoffState]);

  const filteredProjects = useMemo(
    () => filterProjectsByName(projectInput, projects).slice(0, 30),
    [projectInput, projects],
  );

  const loadAgents = async (preferredName = "") => {
    setAgentListState({ loading: true, error: "" });
    try {
      const payload = await readJson("/api/agents");
      const listed = (payload.agents || []).map(asVoiceAgent).filter(Boolean);
      setAgents(listed);
      const requested = preferredName
        || new URLSearchParams(window.location.search).get("agent")
        || agent?.name
        || "";
      const selected = listed.find((item) => item.name === requested) || listed[0] || null;
      setAgent(selected);
      setAgentListState({ loading: false, error: "" });
    } catch (error) {
      setAgentListState({ loading: false, error: errorMessage(error) });
    }
  };

  const loadProjects = async (currentEndpoint = "") => {
    setProjectsState({ loading: true, error: "" });
    try {
      const payload = await readJson("/api/projects");
      const visibleProjects = payload.projects || [];
      setProjects(visibleProjects);
      setProjectInput((current) => projectDisplayValue(
        visibleProjects,
        currentEndpoint,
        current || cfg?.backend || "",
      ));
      setProjectsState({ loading: false, error: "" });
    } catch (error) {
      setProjectsState({ loading: false, error: errorMessage(error) });
    }
  };

  useEffect(() => {
    readJson("/api/config")
      .then((payload) => {
        setCfg(customerConfig(payload));
        setProjectInput(payload.project || payload.endpoint || "");
        void loadProjects(payload.endpoint || "");
        if (payload.configured) return loadAgents();
        setAgentListState({
          loading: false,
          error: "Set AZURE_AI_PROJECT_ENDPOINT in local_UI/.env and restart the server.",
        });
        return undefined;
      })
      .catch((error) => {
        setAgentListState({ loading: false, error: errorMessage(error) });
      });
  }, []);

  const selectAgent = (name) => {
    const selected = agents.find((item) => item.name === name) || null;
    setAgent(selected);
    if (selected) {
      const url = new URL(window.location.href);
      url.searchParams.set("agent", selected.name);
      window.history.replaceState(null, "", url);
    }
  };

  const connect = () => {
    if (!agent || !cfg) return;
    session.connect(agent.name, "", "", cfg.apiVersion, "websocket");
  };

  const selectProject = async (endpoint) => {
    if (!endpoint) return;
    if (endpoint === cfg.host) {
      setProjectInput(projectDisplayValue(projects, endpoint, cfg.backend));
      setProjectResultsOpen(false);
      return;
    }
    setProjectsState({ loading: true, error: "" });
    setAgent(null);
    setAgents([]);
    try {
      const selected = await readJson("/api/project", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ endpoint }),
      });
      setCfg((current) => ({
        ...current,
        backend: selected.project,
        host: selected.endpoint,
        configured: true,
      }));
      setProjectInput(projectDisplayValue(projects, selected.endpoint, selected.project));
      setProjectResultsOpen(false);
      await loadAgents();
      setProjectsState({ loading: false, error: "" });
    } catch (error) {
      setProjectsState({ loading: false, error: errorMessage(error) });
    }
  };

  const submitProject = async (event) => {
    event.preventDefault();
    const endpoint = resolveProjectEndpoint(projectInput, projects);
    if (!endpoint) {
      setProjectsState({
        loading: false,
        error: "Choose a matching suggestion or paste a full Foundry Project endpoint.",
      });
      return;
    }
    await selectProject(endpoint);
  };

  if (!cfg) {
    return <div className="studio-loading">Loading Voice Agent project…</div>;
  }

  return (
    <div className="studio customer-studio">
      <header className="studio-header">
        <div className="studio-brand">
          <span className="brand-mark"><Icon name="wave" /></span>
          <div>
            <h1>Voice agent <span>playground</span></h1>
            <p>Connect. Converse. Follow every handoff.</p>
          </div>
        </div>
        <nav className="customer-nav" aria-label="Local UI pages">
          <span className="customer-nav-active">Live session</span>
          <a href="/templates">Templates</a>
        </nav>
        <div className="studio-backend">
          <label htmlFor="customer-project">Foundry project</label>
          <form className="project-search" onSubmit={submitProject}>
            <div className="project-search-row">
              <input
                id="customer-project"
                type="text"
                value={projectInput}
                placeholder="Type a project name or paste its endpoint"
                title={projectsState.error || cfg.host}
                aria-describedby="customer-project-hint"
                aria-invalid={Boolean(projectsState.error)}
                autoComplete="off"
                spellCheck="false"
                role="combobox"
                aria-autocomplete="list"
                aria-expanded={projectResultsOpen}
                aria-controls="customer-project-options"
                disabled={session.isConnected || projectsState.loading}
                onFocus={() => setProjectResultsOpen(true)}
                onBlur={() => setProjectResultsOpen(false)}
                onKeyDown={(event) => {
                  if (event.key === "Escape") {
                    setProjectResultsOpen(false);
                  }
                }}
                onChange={(event) => {
                  setProjectInput(event.target.value);
                  setProjectResultsOpen(true);
                  if (projectsState.error) {
                    setProjectsState({ loading: false, error: "" });
                  }
                }}
              />
              <button
                type="submit"
                className="project-switch"
                disabled={
                  session.isConnected
                  || projectsState.loading
                  || !projectInput.trim()
                }
              >
                Switch
              </button>
            </div>
            {projectResultsOpen && !session.isConnected && !projectsState.loading ? (
              <div
                id="customer-project-options"
                className="project-results"
                role="listbox"
                aria-label="Matching Foundry projects"
              >
                {filteredProjects.length ? filteredProjects.map((project) => (
                  <button
                    key={project.endpoint}
                    type="button"
                    role="option"
                    aria-selected={project.endpoint === cfg.host}
                    className="project-result"
                    onMouseDown={(event) => event.preventDefault()}
                    onClick={() => selectProject(project.endpoint)}
                  >
                    <span className="project-result-name">{project.name}</span>
                    <span className="project-result-account">{project.account}</span>
                  </button>
                )) : (
                  <span className="project-results-empty">
                    No Project names match this search.
                  </span>
                )}
              </div>
            ) : null}
            <span
              id="customer-project-hint"
              className={`project-search-hint ${projectsState.error ? "error" : ""}`}
              role="status"
            >
              {projectsState.loading
                ? "Discovering visible projects…"
                : projectsState.error
                  || "Search by Project name. Choose a result to distinguish duplicate names."}
            </span>
          </form>
        </div>
      </header>

      <div className="shell customer-shell">
        <section className="studio-panel customer-workflow-panel" aria-label="Agent workflow">
          <div className="customer-panel-heading">
            <div>
              <span className="eyebrow">HANDOFF</span>
              <h2>Agent workflow</h2>
            </div>
            {session.activeHandoffNodeId ? (
              <span className="subtle-badge">Active: {session.activeHandoffNodeId}</span>
            ) : null}
          </div>
          <div className="customer-workflow-content">
            {handoffGraph ? (
              <HandoffGraphPanel
                graph={handoffGraph}
                activeNodeId={session.activeHandoffNodeId}
                takenEdgeIds={session.takenEdgeIds}
                trail={session.handoffTrail}
                agentName={agent?.name || ""}
                showMcpServerUrl={false}
              />
            ) : (
              <div className="workflow-empty">
                {agent
                  ? "This Agent has no handoff graph. The conversation remains fully available."
                  : "Choose a published Voice Agent to inspect its workflow."}
              </div>
            )}
          </div>
        </section>

        <section className="playground-column customer-playground" aria-label="Agent playground">
          <section className="session-controls" aria-label="Session controls">
            <div className="playground-heading">
              <div><span className="eyebrow">TRY IT LIVE</span><h2>Playground</h2></div>
              <span className={`connection-status ${session.status.kind || ""}`} role="status">
                <span className="status-dot" />
                {session.status.text === "not connected" ? "Not connected" : session.status.text}
              </span>
            </div>
            <div className="agent-picker-row">
              <label className="form-field customer-agent-field">
                <span className="field-label">Published Voice Agent</span>
                <select
                  value={agent?.name || ""}
                  disabled={session.isConnected || agentListState.loading}
                  onChange={(event) => selectAgent(event.target.value)}
                >
                  <option value="">
                    {agentListState.loading ? "Loading voice agents…" : "Choose an Agent"}
                  </option>
                  {agents.map((item) => (
                    <option key={item.name} value={item.name}>
                      {item.name}{item.model ? ` · ${item.model}` : ""}
                    </option>
                  ))}
                </select>
              </label>
              <button
                className="icon-button"
                type="button"
                title="Refresh Agents"
                aria-label="Refresh Agents"
                disabled={session.isConnected || agentListState.loading}
                onClick={() => loadAgents(agent?.name || "")}
              >
                <Icon name="refresh" className={agentListState.loading ? "spin" : ""} />
              </button>
            </div>
            {agentListState.error ? (
              <div className="form-feedback err" role="alert">{agentListState.error}</div>
            ) : null}
            {agent ? (
              <div className="selected-agent-meta">
                <span className="subtle-badge">{agent.handoff ? "Handoff" : "Single Agent"}</span>
                <span title={agent.model}>{agent.model || "Default model"}</span>
                <span title={agent.voice}>{agent.voice || "Default voice"}</span>
                <span>v{agent.version || "latest"}</span>
              </div>
            ) : null}
            <div className="session-actions customer-session-actions">
              {!session.isConnected ? (
                <button className="primary" type="button" disabled={!agent || !cfg.configured} onClick={connect}>
                  <Icon name="voice" />Connect
                </button>
              ) : (
                <>
                  <button type="button" disabled={!session.sessionReady} onClick={session.toggleMute}>
                    <Icon name={session.micMuted ? "muted" : "voice"} />
                    {session.micMuted ? "Unmute" : "Mute"}
                  </button>
                  <button className="danger" type="button" onClick={session.stopSession}>
                    Stop session
                  </button>
                </>
              )}
              <label className="customer-developer-toggle">
                <input
                  type="checkbox"
                  checked={session.verbose}
                  onChange={(event) => session.setVerbose(event.target.checked)}
                />
                Developer events
              </label>
            </div>
          </section>

          <ChatPanel session={session} agent={agent} showExternalLinks={false} />
        </section>
      </div>
    </div>
  );
}
