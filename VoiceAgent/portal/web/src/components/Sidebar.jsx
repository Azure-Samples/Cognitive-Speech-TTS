// Copyright (c) Microsoft. All rights reserved.
// Agent authoring only. Session selection and overrides live in SessionControls;
// the request serializers and voice transport are deliberately unchanged.

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { buildAvatarDefinition } from "../lib/avatar.mjs";
import { createAgentDraft, draftCreateOptions, updateAgentDraft } from "../lib/agentForm.mjs";
import { describeRejection } from "../lib/authoringContract.mjs";
import { buildCustomerCareHandoff } from "../lib/handoff.mjs";
import { GREETING_MODES } from "../lib/greeting.mjs";
import {
  buildStructuredInputDefinitions, detectStructuredInputNames, reconcileStructuredInputConfigs,
} from "../lib/structuredInput.mjs";
import { AgentConfig, VoiceConfig } from "./AgentConfig.jsx";
import { EditorPanel, EditorTabs, Icon, SectionHeading, Toggle } from "./ConfigControls.jsx";
import { DigitDemoConfig } from "./DigitDemoConfig.jsx";
import { GenerateConfig } from "./GenerateConfig.jsx";
import { SubagentsConfig } from "./SubagentsConfig.jsx";
import { ToolsConfig } from "./ToolsConfig.jsx";

export const MODE_CREATE = "create";
export const MODE_GENERATE = "generate";

export function Sidebar({ cfg, session, authorMode, onAuthorModeChange, onCreateAgent, onGenerateAgent }) {
  const [draft, setDraft] = useState(() => createAgentDraft(cfg));
  const [generateDraft, setGenerateDraft] = useState({
    name: "", goal: "", useCase: "", description: "", modelType: "", model: "", draft: false,
    store: cfg.defaultStore === true,
  });
  const [section, setSection] = useState("agent");
  const [generateSection, setGenerateSection] = useState("brief");
  const [tools, setTools] = useState([]);
  const [subagents, setSubagents] = useState([]);
  const [structuredInputConfigs, setStructuredInputConfigs] = useState([]);
  const [createState, setCreateState] = useState({ text: "", kind: "" });
  const [genState, setGenState] = useState({ text: "", kind: "" });
  const scrollRef = useRef(null);

  const generatingMode = authorMode === MODE_GENERATE;
  const hosted = draft.inferenceMode === "hosted_agent";
  const busy = createState.kind === "warn" || genState.kind === "warn";
  const disabled = session.isConnected || busy;
  const activeSection = generatingMode ? generateSection : section;
  const setActiveSection = generatingMode ? setGenerateSection : setSection;
  const update = (field, value) => setDraft((previous) => updateAgentDraft(cfg, previous, field, value));
  const updateGenerate = (field, value) => setGenerateDraft((previous) => ({ ...previous, [field]: value }));

  const structuredInputNames = useMemo(() => detectStructuredInputNames([
    draft.instructions,
    draft.greeting.mode === GREETING_MODES.TEMPLATE ? draft.greeting.text : "",
    draft.greeting.mode === GREETING_MODES.LLM_GENERATED ? draft.greeting.prompt : "",
    draft.greeting.mode === GREETING_MODES.LLM_GENERATED ? draft.greeting.fallbackText : "",
  ]), [draft.instructions, draft.greeting]);

  useEffect(() => {
    setStructuredInputConfigs((current) => reconcileStructuredInputConfigs(structuredInputNames, current));
  }, [structuredInputNames]);

  useLayoutEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = 0;
  }, [activeSection, authorMode]);

  // Stable callback: SubagentsConfig reports changes from an effect. An inline
  // callback would retrigger it on every render, rebuilding the selected array.
  const onSubagentsChange = useCallback(({ subagents }) => {
    setSubagents(subagents);
  }, []);

  const create = async () => {
    if (disabled) return;
    const rejection = describeRejection({
      name: draft.name.trim() || "generated-placeholder",
      description: draft.description,
      model: hosted ? undefined : draft.model,
    });
    if (rejection || (hosted && !draft.targetAgentName.trim())) {
      setCreateState({ text: rejection || "Target hosted agent name is required.", kind: "err" });
      setSection("agent");
      return;
    }
    setCreateState({ text: "Creating your agent…", kind: "warn" });
    try {
      const structuredInputs = hosted ? undefined : buildStructuredInputDefinitions(structuredInputConfigs);
      await onCreateAgent(draftCreateOptions(draft, tools, subagents, structuredInputs));
      setCreateState({ text: "Agent created. Ready in the playground.", kind: "ok" });
      update("name", "");
    } catch (error) {
      setCreateState({ text: error.message || String(error), kind: "err" });
    }
  };

  const generate = async () => {
    if (disabled || hosted) return;
    const rejection = describeRejection({
      ...generateDraft,
      name: generateDraft.name.trim() || "generated-placeholder",
    });
    if (rejection) {
      setGenState({ text: rejection, kind: "err" });
      setGenerateSection("brief");
      return;
    }
    setGenState({ text: "Generating your agent…", kind: "warn" });
    try {
      await onGenerateAgent({
        ...generateDraft,
        model: generateDraft.model.trim() || undefined,
        modelType: generateDraft.modelType || undefined,
        tools,
      });
      setGenState({ text: "Generated. Review the definition in the playground.", kind: "ok" });
      updateGenerate("name", "");
    } catch (error) {
      setGenState({ text: error.message || String(error), kind: "err" });
    }
  };

  const toolTab = { value: "tools", label: "Tools", icon: "tools", count: hosted ? 0 : tools.length };
  const tabs = generatingMode
    ? [{ value: "brief", label: "Brief", icon: "sparkles" }, toolTab]
    : [
      { value: "agent", label: "Agent", icon: "agent" },
      { value: "voice", label: "Voice", icon: "voice" },
      toolTab,
      { value: "workflow", label: "Workflow", icon: "workflow", count: subagents.length },
      { value: "demos", label: "Demos", icon: "flask" },
    ];
  const state = generatingMode ? genState : createState;

  return (
    <section className="sidebar" role="complementary" aria-label="Agent editor">
      <div className="mode-switch" role="group" aria-label="How to get an agent">
        <button type="button" aria-pressed={!generatingMode}
          className={`mode-tab${!generatingMode ? " active" : ""}`} disabled={session.isConnected}
          onClick={() => onAuthorModeChange(MODE_CREATE)}><Icon name="settings" />Configure</button>
        <button type="button" aria-pressed={generatingMode}
          className={`mode-tab${generatingMode ? " active" : ""}`} disabled={session.isConnected}
          onClick={() => onAuthorModeChange(MODE_GENERATE)}><Icon name="sparkles" />Generate</button>
      </div>
      <EditorTabs items={tabs} value={activeSection} onChange={setActiveSection} />
      <div className="editor-scroll" ref={scrollRef}>
        {session.isConnected ? <div className="editor-readonly">Session connected. Stop it to edit this configuration.</div> : null}
        <EditorPanel name="agent" active={!generatingMode && activeSection === "agent"}>
          <AgentConfig cfg={cfg} draft={draft} update={update} disabled={disabled}
            structuredInputConfigs={structuredInputConfigs} onStructuredInputsChange={setStructuredInputConfigs} />
        </EditorPanel>
        <EditorPanel name="voice" active={!generatingMode && activeSection === "voice"}>
          <VoiceConfig cfg={cfg} draft={draft} update={update} disabled={disabled} />
        </EditorPanel>
        <EditorPanel name="brief" active={generatingMode && activeSection === "brief"}>
          <GenerateConfig value={generateDraft} update={updateGenerate} disabled={disabled}
            hosted={hosted} toolCount={tools.length} onTools={() => setGenerateSection("tools")} />
        </EditorPanel>
        <EditorPanel name="tools" active={activeSection === "tools"}>
          <SectionHeading title="Knowledge & tools" description="Give your agent access to information and actions." />
          {hosted ? <div className="info-note">Configure tools on the target hosted agent, not on the voice wrapper. Your selections are retained for managed models and BYOM.</div> : null}
          <ToolsConfig cfg={cfg} disabled={disabled || hosted} onChange={setTools} />
        </EditorPanel>
        <EditorPanel name="workflow" active={!generatingMode && activeSection === "workflow"}>
          <SectionHeading title="Workflow" description="Route a conversation or bring a specialist into it." />
          {hosted ? <div className="info-note">The target hosted agent owns its workflow. These settings are not sent for a voice wrapper.</div> : null}
          <div className="setting-block handoff-config">
            <Toggle label="Customer-care handoff" checked={draft.handoffEnabled} disabled={disabled || hosted}
              onChange={(value) => update("handoffEnabled", value)}
              description="Route between billing and technical support, each with its own voice." />
            {draft.handoffEnabled ? (
              <>
                <div className="handoff-preview">
                  <span>Front desk</span><Icon name="arrow" /><span>Billing / Support</span>
                </div>
                <p className="field-hint">Server-managed transfers use the Contoso Mobile triage prompt unless you write your own instructions.</p>
                <details className="advanced-details">
                  <summary>Inspect handoff graph</summary>
                  <pre className="handoff-json">{JSON.stringify(buildCustomerCareHandoff(), null, 2)}</pre>
                </details>
              </>
            ) : null}
          </div>
          <SubagentsConfig cfg={cfg} session={session} disabled={disabled || hosted} onChange={onSubagentsChange} />
        </EditorPanel>
        <EditorPanel name="demos" active={!generatingMode && activeSection === "demos"}>
          <SectionHeading title="Ready-to-try demos" description="Explore a complete scenario without changing your draft." />
          {hosted ? <div className="info-note">The digit demo requires a managed model or BYOM.</div> : null}
          <DigitDemoConfig disabled={disabled || hosted} model={draft.model} voice={draft.voice}
            inferenceMode={draft.inferenceMode} store={draft.store} clientReferenceEc={draft.clientReferenceEc}
            avatar={buildAvatarDefinition(draft.avatarEnabled, draft.avatarPreset)} onCreateAgent={onCreateAgent} />
        </EditorPanel>
      </div>
      <div className="editor-footer">
        {state.text ? <div className={`form-feedback ${state.kind}`} role={state.kind === "err" ? "alert" : "status"}>{state.text}</div> : null}
        <div className="editor-footer-row">
          <span>{generatingMode ? "Review before connecting" : "Saved as a new agent"}</span>
          <button type="button" className="primary" disabled={disabled || (generatingMode && hosted)}
            onClick={generatingMode ? generate : create}>
            {busy ? (generatingMode ? "Generating…" : "Creating…") : (generatingMode ? "Generate agent" : "Create agent")}
            <Icon name={generatingMode ? "sparkles" : "arrow"} />
          </button>
        </div>
      </div>
    </section>
  );
}
