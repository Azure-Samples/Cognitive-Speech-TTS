// Copyright (c) Microsoft. All rights reserved.
// Top-level demo app: loads /config, owns agent-creation state, wires the voice-session
// hook, and lays out the editor and playground. Workflow and generated definitions
// are playground tabs so they don't squeeze the conversation on smaller screens.

import { useEffect, useMemo, useRef, useState } from "react";
import { loadConfig, loadDeployments, isCascaded } from "./config.js";
import {
  buildCreateAgentBody,
  buildVersionCreateRequest,
  agentResourceFromVersion,
  buildGenerateAgentBody,
  newAgentName,
  withApiVersion,
  serviceHeaders,
} from "./lib/serviceContract.js";
import { buildGreetingConfig } from "./lib/greeting.mjs";
import { createDigitDemoFunctions } from "./lib/digitDemo.mjs";
import { definitionFromResponse, shouldApplyGenerateResponse } from "./lib/agentReview.mjs";
import {
  asVoiceAgent,
  hostedAgentTargetPath,
  loadVoiceAgents,
  validateHostedAgentTarget,
} from "./lib/agentCatalog.mjs";
import { useVoiceSession } from "./hooks/useVoiceSession.js";
import { buildHandoffGraph } from "./lib/handoffGraph.mjs";
import { withSelectedAgent } from "./lib/agentUrl.mjs";
import { AgentDefinitionDialog } from "./components/AgentDefinitionDialog.jsx";
import { Icon } from "./components/ConfigControls.jsx";
import { Sidebar, MODE_CREATE, MODE_GENERATE } from "./components/Sidebar.jsx";
import { ReviewPanel } from "./components/ReviewPanel.jsx";
import { ChatPanel } from "./components/ChatPanel.jsx";
import { HandoffGraphPanel } from "./components/HandoffGraphPanel.jsx";
import { SessionControls } from "./components/SessionControls.jsx";
import { StudioHeader } from "./components/StudioHeader.jsx";

function forPortal(cfg, agent, sessionStores) {
  return agent ? {
    ...agent,
    ...(sessionStores?.has(agent.name) ? { sessionStoreDefault: sessionStores.get(agent.name) } : {}),
    // Hosted agents use the cascaded voice path; voice overrides must use Azure voices.
    cascaded: agent.inferenceMode === "hosted_agent" || isCascaded(cfg, agent.model),
  } : null;
}

export function App() {
  const [cfg, setCfg] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [agent, setAgent] = useState(null); // { name, model, voice, cascaded }
  const [agents, setAgents] = useState([]);
  const [agentListState, setAgentListState] = useState({ loading: true, error: "" });
  const [editingAgentName, setEditingAgentName] = useState("");
  const [authorMode, setAuthorMode] = useState(MODE_CREATE);
  const [configurationCollapsed, setConfigurationCollapsed] = useState(false);
  const [debugCollapsed, setDebugCollapsed] = useState(true);
  // What the last generate returned, kept so the review stage has something
  // to show. Cleared when the caller switches away from generating, because a
  // definition left on screen would describe an agent they are no longer making.
  const [generated, setGenerated] = useState(null);
  /* Generate is a slow round trip the user can walk away from. Each request takes a
   * token; leaving the Generate tab bumps the counter, so a response that lands after
   * the user moved on is dropped instead of repopulating the review they abandoned. */
  const generateToken = useRef(0);
  // A generation preference is a session override, never an unsupported field
  // on /agents:generate or a silent rewrite of the service's returned version.
  const generatedSessionStores = useRef(new Map());
  const session = useVoiceSession();
  const { setClientFunctions } = session;
  const connectedRef = useRef(session.isConnected);
  connectedRef.current = session.isConnected;

  const toggleConfigurationPanel = () => {
    if (configurationCollapsed) {
      setConfigurationCollapsed(false);
      setDebugCollapsed(true);
    } else {
      setConfigurationCollapsed(true);
    }
  };

  const toggleDebugPanel = () => {
    if (debugCollapsed) {
      setDebugCollapsed(false);
      setConfigurationCollapsed(true);
    } else {
      setDebugCollapsed(true);
    }
  };

  useEffect(() => {
    if (session.isConnected) {
      setConfigurationCollapsed(true);
      setDebugCollapsed(false);
    }
  }, [session.isConnected]);

  /* Client-executed `function` tools are fulfilled by this page, not by Voice Live, so the
   * handlers have to be installed before a session can call one. The digit-accuracy demo is the
   * only one shipped today; registering it unconditionally is harmless for agents that declare no
   * function tool, because the registry is consulted only when a `function_call` actually arrives. */
  useEffect(() => {
    setClientFunctions(createDigitDemoFunctions());
  }, [setClientFunctions]);

  /* The workflow tab exists only for agents that have one. An agent selected from the
   * list carries its full definition; one just created here carries only the handoff block.
   * Either is enough to draw the graph before a session exists, and a live session refines
   * it with the compiled topology. The conversation keeps its full width. */
  const handoffGraph = useMemo(() => {
    const definition = agent?.definition || (agent?.handoff ? { handoff: agent.handoff } : null);
    if (!definition && !session.handoffState) return null;
    return buildHandoffGraph({ definition, handoffState: session.handoffState });
  }, [agent, session.handoffState]);

  useEffect(() => {
    loadConfig()
      .then(async (cfg) => {
        // Merge dynamically-discovered BYOM deployments over the static /config fallback so BYOM mode
        // reflects the actual Foundry project. Discovery failures keep the static lists from /config.
        try {
          const dep = await loadDeployments();
          const realtime = (dep.realtime || []).map((d) => d.deployment).filter(Boolean);
          const cascaded = (dep.cascaded || []).map((d) => d.deployment).filter(Boolean);
          if (realtime.length) cfg.byomRealtimeModels = realtime;
          if (cascaded.length) cfg.byomCascadedModels = cascaded;
          cfg.byomAccount = dep.account || null;
          cfg.byomDeploymentSource = dep.source || null;
        } catch (e) {
          console.warn("BYOM deployment discovery failed; using static /config lists", e);
        }
        try {
          const listed = await loadVoiceAgents(cfg);
          const portalAgents = listed.map((item) => forPortal(cfg, item, generatedSessionStores.current));
          setAgents(portalAgents);
          // The Templates tab runs a template by opening this page with the agent it was
          // published as, so an agent named in the URL is a selection, not a filter.
          const requested = new URLSearchParams(window.location.search).get("agent");
          if (requested) {
            const match = portalAgents.find((item) => item.name === requested);
            if (match) setAgent(match);
            else session.logError(`Agent '${requested}' is not in backend '${cfg.backend}'`);
          }
          setAgentListState({ loading: false, error: "" });
        } catch (e) {
          console.warn("Voice agent discovery failed", e);
          setAgentListState({ loading: false, error: String(e) });
        }
        setCfg(cfg);
      })
      .catch((e) => setLoadError(String(e)));
  }, []);

  /* `keepReview` is false for every caller except the generate flow itself. The review
   * describes one specific agent at one specific version; the moment the connection
   * points somewhere else -- a different agent from the dropdown, or the same name after
   * an edit saved a new version -- the text on screen no longer describes what Connect
   * will talk to. Reading one agent and speaking to another is precisely the failure
   * this review step exists to prevent, so the review is dropped rather than left to
   * look authoritative. */
  const selectAndRememberAgent = (selected, { keepReview = false } = {}) => {
    const portalAgent = forPortal(cfg, selected, generatedSessionStores.current);
    if (!portalAgent) return;
    setAgents((current) => [
      portalAgent,
      ...current.filter((item) => item.name !== portalAgent.name),
    ]);
    // Creation may finish after the user connected to an existing agent. Keep
    // the new resource in the picker without relabelling the active session.
    if (connectedRef.current) return;
    setAgent(portalAgent);
    window.history.replaceState(null, "", withSelectedAgent(window.location.href, portalAgent.name));
    if (!keepReview) setGenerated(null);
  };

  const onSelectAgent = (name) => {
    const selected = agents.find((item) => item.name === name) || null;
    setAgent(selected);
    window.history.replaceState(null, "", withSelectedAgent(window.location.href, selected?.name));
    setGenerated(null);
  };

  const onBackendChange = (backend) => {
    if (!backend || backend === cfg.backend) return;
    const url = new URL(window.location.href);
    url.searchParams.set("backend", backend);
    window.location.assign(url.toString());
  };

  const onRefreshAgents = async () => {
    setAgentListState({ loading: true, error: "" });
    try {
      const listed = (await loadVoiceAgents(cfg)).map((item) => forPortal(cfg, item, generatedSessionStores.current));
      setAgents(listed);
      setAgent((current) => (
        current ? listed.find((item) => item.name === current.name) || null : null
      ));
      setAgentListState({ loading: false, error: "" });
    } catch (e) {
      setAgentListState({ loading: false, error: String(e) });
    }
  };

  // Agent URLs select only. Starting a credentialed/microphone session always
  // requires the local operator to press Connect; ignore legacy autostart links.

  const onCreateAgent = async ({
    name: requestedName, model, voice, tools, subagents, inferenceMode, store, avatar,
    greeting, handoff, handoffInstructions, targetAgentName, targetAgentVersion, clientReferenceEc,
    instructions, structuredInputs, description, namePrefix,
  }) => {
    // Build the REAL service create request: name (client-generated) + full AgentDefinition body,
    // the api-version query, and Foundry-Features + Content-Type headers — matching the service
    // contract exactly. The demo backend forwards it verbatim and injects only the bearer token.
    if (inferenceMode === "hosted_agent") {
      session.logApi(
        "GET",
        hostedAgentTargetPath(cfg, targetAgentName, targetAgentVersion),
      );
      await validateHostedAgentTarget(
        cfg,
        targetAgentName,
        targetAgentVersion,
      );
    }
    const name = requestedName?.trim() || newAgentName(
      namePrefix || (inferenceMode === "hosted_agent" ? "web-voice-hosted" : "web-voice"),
    );
    const body = buildCreateAgentBody({
      name, model, voice, tools, subagents, inferenceMode, store, avatar, handoff,
      handoffInstructions, targetAgentName, targetAgentVersion, clientReferenceEc,
      instructions, structuredInputs, description,
      greeting: buildGreetingConfig(greeting),
      inputTranscriptionModel: cfg.inputTranscriptionModel,
    });
    const { path, body: requestBody } = buildVersionCreateRequest(cfg, body);
    session.logApi("POST", path);
    const resp = await fetch(path, {
      method: "POST",
      headers: serviceHeaders(cfg, { "Content-Type": "application/json" }),
      body: JSON.stringify(requestBody),
    });
    const result = await resp.json();
    if (!resp.ok) throw new Error(result.error?.message || result.error || result.message || `HTTP ${resp.status}`);
    const data = agentResourceFromVersion(name, result);
    const definition = body.definition;
    selectAndRememberAgent(asVoiceAgent(data) || {
      name,
      version: data.versions?.latest?.version || "",
      model: definition.model || "",
      voice: typeof definition.audio?.output?.voice === "string"
        ? definition.audio.output.voice : definition.audio?.output?.voice?.name || voice,
      avatar: definition.avatar || null,
      greeting: definition.greeting || null,
      toolCount: (definition.tools || []).length,
      inferenceMode,
      targetAgent: definition.target_agent || null,
      clientReferenceEc,
      store: typeof definition.store === "boolean" ? definition.store : false,
      handoff: definition.handoff || null,
      definition,
    });
    return data;
  };

  // Guided authoring: the service expands {useCase, goal?} into a full voice agent — generating
  // the instructions, audio stack, and defaults. Post agentic-creation refactor only `useCase` is
  // required: `model`/`inferenceMode` are optional (the service defaults to a managed
  // gpt-realtime), and `description`/`draft` fall back to values chosen by VOICE LIVE, not by
  // the service or this client. See buildGenerateAgentBody for the full contract.
  const onGenerateAgent = async ({
    name: requestedName, model, modelType, useCase, goal, tools, description, draft, store = false,
  }) => {
    const name = requestedName?.trim() || newAgentName("web-voice-gen");
    const body = buildGenerateAgentBody({
      name, model, modelType, useCase, goal, tools, description, draft,
    });
    const path = withApiVersion(cfg, "/agents:generate");
    session.logApi("POST", path);
    // Wall-clock from here rather than a server-reported duration: the caller is
    // waiting on the whole round trip, and the service does not report its own.
    // A failure must not leave the previous definition on screen beside it.
    setGenerated(null);
    const startedAt = Date.now();
    // Per-request, not per-tab: two generates in flight must not share an identity.
    const token = (generateToken.current += 1);
    const resp = await fetch(path, {
      method: "POST",
      headers: serviceHeaders(cfg, { "Content-Type": "application/json" }),
      body: JSON.stringify(body),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || data.message || `HTTP ${resp.status}`);
    // Real service response: { name, versions: { latest: { definition } }, ... }.
    const found = definitionFromResponse(data);
    if (!found) throw new Error("service returned no agent definition");
    const { definition: def, latest } = found;
    /* A generate the user walked away from must have no effect at all. Guarding only
     * the review panel was not enough: `selectAndRememberAgent` decides which agent
     * Connect talks to, so a late response could leave the panel showing one agent
     * while the microphone was wired to another -- the exact mismatch this review step
     * exists to prevent. Both the display and the selection sit inside the guard.
     *
     * Connecting counts as walking away. Connect lives in the footer, outside the panes,
     * and is enabled the moment an agent is selected -- so it can be pressed while a
     * generate is still outstanding. The session then binds to the agent that was
     * selected at that moment, and a response landing afterwards would repoint `agent`
     * and the review at the generated one while the microphone stayed on the first. */
    const apply = shouldApplyGenerateResponse({
      requestToken: token,
      currentToken: generateToken.current,
      isConnected: connectedRef.current,
    });
    if (!apply) return data;
    generatedSessionStores.current.set(data.name || name, store === true);

    const identity = {
      name: data.name || name,
      version: latest.version,
      description: latest.description,
      draft: latest.draft,
    };
    const elapsedMs = Date.now() - startedAt;
    setGenerated({ definition: def, identity, elapsedMs });

    const genModel = def.model;
    const outputVoice = def.audio?.output?.voice;
    const voice = typeof outputVoice === "string" ? outputVoice : outputVoice?.name;
    selectAndRememberAgent(asVoiceAgent(data) || {
      name: data.name || name,
      model: genModel,
      voice,
      toolCount: (tools || []).length,
      // Derive the inference mode from what the SERVICE returned rather than what the user picked —
      // when model_type is omitted the service resolves it, and connect needs the resolved value to
      // pick the right model family.
      inferenceMode: def.model_type === "self_deployed" ? "deployment" : "model",
      store: def.store === true,
      definition: def,
      generated: true,
      instructions: def.instructions,
      avatar: def.avatar || null,
    }, { keepReview: true });
    return data;
  };

  if (loadError) return <div className="studio-loading" role="alert">Could not load configuration: {loadError}</div>;
  if (!cfg) return <div className="studio-loading" role="status">Loading your voice workspace…</div>;

  return (
    <div className="studio">
      <StudioHeader cfg={cfg} disabled={session.isConnected} onBackendChange={onBackendChange} />
      <div className="shell">
        <aside className="studio-side-column" aria-label="Agent creation and debugging">
          <section className={`studio-panel studio-config-panel${configurationCollapsed ? " is-collapsed" : ""}`}>
            <button
              type="button"
              className="studio-panel-header-button"
              aria-expanded={!configurationCollapsed}
              aria-controls="agent-creation-panel"
              onClick={toggleConfigurationPanel}
            >
              <span className="studio-panel-heading-copy">
                <span className="eyebrow">BUILD</span>
                <span className="studio-panel-heading-title" role="heading" aria-level="2">Agent Creation</span>
                <span className="studio-panel-heading-hint">
                  Click to {configurationCollapsed ? "expand" : "collapse"}
                </span>
              </span>
              <span className="studio-panel-heading-actions">
                <span className="subtle-badge">New agent</span>
                <span className="studio-panel-fold-control">
                  <span>{configurationCollapsed ? "Expand panel" : "Collapse panel"}</span>
                  <Icon name="chevron" />
                </span>
              </span>
            </button>
            <div id="agent-creation-panel" className="studio-panel-content" hidden={configurationCollapsed}>
              <Sidebar
                cfg={cfg}
                session={session}
                onCreateAgent={onCreateAgent}
                onGenerateAgent={onGenerateAgent}
                authorMode={authorMode}
                onAuthorModeChange={(next) => {
                  setAuthorMode(next);
                  if (next !== MODE_GENERATE) {
                    generateToken.current += 1;
                    setGenerated(null);
                  }
                }}
              />
            </div>
          </section>
          <section className={`studio-panel studio-workflow-panel${debugCollapsed ? " is-collapsed" : ""}`}
            aria-label="Agent debug">
            <button
              type="button"
              className="studio-panel-header-button"
              aria-expanded={!debugCollapsed}
              aria-controls="agent-debug-panel"
              onClick={toggleDebugPanel}
            >
              <span className="studio-panel-heading-copy">
                <span className="eyebrow">DEBUG</span>
                <span className="studio-panel-heading-title" role="heading" aria-level="2">Agent Debug</span>
                <span className="studio-panel-heading-hint">
                  Click to {debugCollapsed ? "expand" : "collapse"}
                </span>
              </span>
              <span className="studio-panel-heading-actions">
                {session.activeHandoffNodeId ? (
                  <span className="subtle-badge">Active: {session.activeHandoffNodeId}</span>
                ) : null}
                <span className="studio-panel-fold-control">
                  <span>{debugCollapsed ? "Expand panel" : "Collapse panel"}</span>
                  <Icon name="chevron" />
                </span>
              </span>
            </button>
            <div id="agent-debug-panel" className="studio-workflow-content" hidden={debugCollapsed}>
              {handoffGraph ? (
                <HandoffGraphPanel
                  graph={handoffGraph}
                  activeNodeId={session.activeHandoffNodeId}
                  takenEdgeIds={session.takenEdgeIds}
                  trail={session.handoffTrail}
                  agentName={agent?.name || ""}
                />
              ) : (
                <div className="workflow-empty">
                  Select an agent with a handoff graph to follow its active node while the session runs.
                </div>
              )}
            </div>
          </section>
        </aside>
        <section className="playground-column" aria-label="Agent playground">
          <SessionControls cfg={cfg} session={session} agent={agent} agents={agents}
            agentListState={agentListState} onSelectAgent={onSelectAgent} onRefreshAgents={onRefreshAgents}
            onEditAgent={() => setEditingAgentName(agent?.name || "")} />
          <ReviewPanel
            definition={authorMode === MODE_GENERATE ? generated?.definition : null}
            identity={generated?.identity}
            elapsedMs={generated?.elapsedMs}
          >
            <ChatPanel session={session} agent={agent} cfg={cfg} />
          </ReviewPanel>
        </section>
      </div>
      <AgentDefinitionDialog
        cfg={cfg}
        agentName={editingAgentName}
        open={Boolean(editingAgentName)}
        logApi={session.logApi}
        onClose={() => setEditingAgentName("")}
        onSaved={(resource) => selectAndRememberAgent(asVoiceAgent(resource))}
      />
    </div>
  );
}
