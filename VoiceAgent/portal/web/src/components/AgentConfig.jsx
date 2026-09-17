// Copyright (c) Microsoft. All rights reserved.

import { isCascaded, modelGroups, voiceGroups } from "../config.js";
import { AVATAR_PRESETS } from "../lib/avatar.mjs";
import { DEFAULT_INSTRUCTIONS } from "../lib/agentForm.mjs";
import { LIMITS } from "../lib/authoringContract.mjs";
import { GREETING_MODES, GREETING_TOOL_CHOICES } from "../lib/greeting.mjs";
import { HANDOFF_ENTRYPOINT_INSTRUCTIONS } from "../lib/handoff.mjs";
import { Field, GroupedSelect, SectionHeading, Toggle } from "./ConfigControls.jsx";
import { StructuredInputsConfig } from "./StructuredInputsConfig.jsx";

export function AgentConfig({ cfg, draft, update, disabled, structuredInputConfigs, onStructuredInputsChange }) {
  const hosted = draft.inferenceMode === "hosted_agent";
  const greeting = draft.greeting;
  const updateGreeting = (key, value) => update("greeting", { ...greeting, [key]: value });
  const modes = cfg.inferenceModes || [
    { value: "model", label: "Managed model" },
    { value: "deployment", label: "BYOM deployment" },
    { value: "hosted_agent", label: "Hosted agent" },
  ];
  const modeLabels = { model: "Managed model", deployment: "Your deployment (BYOM)", hosted_agent: "Hosted agent" };

  return (
    <>
      <SectionHeading title="Agent & model" description="Set your agent’s purpose, model, and first message." />
      <Field label="Agent name" optional hint="Leave blank to generate a unique name.">
        <input type="text" value={draft.name} maxLength={LIMITS.name}
          placeholder="e.g. customer-support" disabled={disabled}
          onChange={(event) => update("name", event.target.value)} />
      </Field>
      <div className="field-grid">
        <Field label="Model source">
          <select value={draft.inferenceMode} disabled={disabled}
            onChange={(event) => update("inferenceMode", event.target.value)}>
            {modes.map((mode) => <option key={mode.value} value={mode.value}>{modeLabels[mode.value] || mode.label}</option>)}
          </select>
        </Field>
        {!hosted ? (
          <Field label={draft.inferenceMode === "deployment" ? "Model deployment" : "Model"}>
            <GroupedSelect value={draft.model} disabled={disabled}
              groups={modelGroups(cfg, draft.inferenceMode === "deployment")}
              onChange={(event) => update("model", event.target.value)} />
          </Field>
        ) : (
          <Field label="Target version" optional>
            <input type="text" value={draft.targetAgentVersion} placeholder="Latest version"
              disabled={disabled} onChange={(event) => update("targetAgentVersion", event.target.value)} />
          </Field>
        )}
      </div>
      {hosted ? (
        <>
          <Field label="Target hosted agent" hint="An existing, Voice Live-compatible hosted agent in this project.">
            <input type="text" value={draft.targetAgentName} placeholder="existing-hosted-agent"
              disabled={disabled} onChange={(event) => update("targetAgentName", event.target.value)} />
          </Field>
          <div className="info-note">
            The target owns its instructions, model, tools, and workflow.
            Configure the voice, greeting, and recording policy on this wrapper.
          </div>
        </>
      ) : (
        <>
          <div className="model-note">
            <span className="subtle-badge">{isCascaded(cfg, draft.model) ? "Cascaded" : "Realtime"}</span>
            <span>{draft.inferenceMode === "deployment"
              ? "Uses your Foundry deployment."
              : "Hosted and managed by Voice Live."}</span>
          </div>
          <Field label="Instructions" optional hint={draft.handoffEnabled
            ? "Leave blank to use the customer-care routing prompt. Custom instructions take precedence."
            : "Set the role, tone, and boundaries. Leave blank to use the helpful-assistant default."}>
            <textarea value={draft.instructions} rows={7} disabled={disabled}
              placeholder={draft.handoffEnabled ? HANDOFF_ENTRYPOINT_INSTRUCTIONS : DEFAULT_INSTRUCTIONS}
              onChange={(event) => update("instructions", event.target.value)} />
          </Field>
        </>
      )}
      <div className="form-divider" />
      <Field label="First message">
        <select value={greeting.mode} disabled={disabled}
          onChange={(event) => updateGreeting("mode", event.target.value)}>
          <option value={GREETING_MODES.NONE}>Wait for the user</option>
          <option value={GREETING_MODES.TEMPLATE}>Speak an exact greeting</option>
          <option value={GREETING_MODES.LLM_GENERATED}>Generate a greeting</option>
        </select>
      </Field>
      {greeting.mode === GREETING_MODES.TEMPLATE ? (
        <Field label="Greeting text" hint="Spoken exactly as written, without model generation.">
          <textarea rows={3} value={greeting.text} disabled={disabled}
            onChange={(event) => updateGreeting("text", event.target.value)} />
        </Field>
      ) : null}
      {greeting.mode === GREETING_MODES.LLM_GENERATED ? (
        <>
          <Field label="Greeting prompt">
            <textarea rows={3} value={greeting.prompt} disabled={disabled}
              onChange={(event) => updateGreeting("prompt", event.target.value)} />
          </Field>
          <Field label="Fallback greeting" optional hint="Used if generation fails before any greeting is spoken.">
            <textarea rows={2} value={greeting.fallbackText} disabled={disabled}
              onChange={(event) => updateGreeting("fallbackText", event.target.value)} />
          </Field>
          <Field label="Greeting tool choice" hint={hosted
            ? "Hosted wrappers cannot require wrapper-level tools."
            : "None is fastest. Auto or required can use the configured tools."}>
            <select value={greeting.toolChoice} disabled={disabled}
              onChange={(event) => updateGreeting("toolChoice", event.target.value)}>
              {GREETING_TOOL_CHOICES.filter((choice) => !hosted || choice !== "required").map((choice) => (
                <option key={choice} value={choice}>{choice}</option>
              ))}
            </select>
          </Field>
        </>
      ) : null}
      {!hosted ? (
        <section className="structured-input-settings" aria-label="Structured inputs">
          <h3>Structured inputs</h3>
          <p className="field-hint">
            Personalize instructions and greetings with variables. Defaults are saved with the agent;
            override their values in the playground’s Session settings.
          </p>
          <StructuredInputsConfig configs={structuredInputConfigs} disabled={disabled} onChange={onStructuredInputsChange} />
        </section>
      ) : null}
      <details className="advanced-details">
        <summary>Agent details</summary>
        <Field label="Description" optional>
          <input type="text" value={draft.description} maxLength={LIMITS.description}
            placeholder="A short description of this agent" disabled={disabled || hosted}
            onChange={(event) => update("description", event.target.value)} />
        </Field>
        {hosted ? <p className="field-hint">Hosted wrappers use a standard description.</p> : null}
      </details>
      <div className="setting-block">
        <Toggle label="Save conversations" checked={draft.store} disabled={disabled}
          onChange={(value) => update("store", value)}
          description="Persist transcripts and audio for playback and review." />
        {!draft.store ? (
          <p className="field-hint">Conversations and recordings are not saved. Service tracing is separate.</p>
        ) : null}
      </div>
    </>
  );
}

export function VoiceConfig({ cfg, draft, update, disabled }) {
  const hosted = draft.inferenceMode === "hosted_agent";
  const azureOnly = hosted || draft.avatarEnabled || isCascaded(cfg, draft.model);
  return (
    <>
      <SectionHeading title="Voice & audio" description="Choose how your agent sounds and configure its audio." />
      <Field label="Voice" hint={azureOnly
        ? "Azure voices are required for this configuration."
        : "Choose a native realtime voice or an Azure voice."}>
        <GroupedSelect value={draft.voice} groups={voiceGroups(cfg, azureOnly)} disabled={disabled}
          onChange={(event) => update("voice", event.target.value)} />
      </Field>
      <div className="audio-format-note"><span>24 kHz PCM</span><span>Server VAD</span><span>Audio response</span></div>
      <div className="setting-block">
        <Toggle label="Live-reference echo cancellation" checked={draft.clientReferenceEc}
          disabled={disabled || draft.avatarEnabled}
          onChange={(value) => update("clientReferenceEc", value)}
          description="Send microphone and playback audio on separate WebSocket channels." />
      </div>
      <div className="setting-block">
        <Toggle label="Video avatar" checked={draft.avatarEnabled} disabled={disabled}
          onChange={(value) => update("avatarEnabled", value)}
          description="Add a speaking avatar. Uses an Azure voice and disables live-reference echo cancellation." />
        {draft.avatarEnabled ? (
          <Field label="Avatar preset">
            <select value={draft.avatarPreset} disabled={disabled}
              onChange={(event) => update("avatarPreset", event.target.value)}>
              {AVATAR_PRESETS.map((preset) => <option key={preset.id} value={preset.id}>{preset.label}</option>)}
            </select>
          </Field>
        ) : null}
      </div>
      <p className="field-hint">Additional audio settings remain available in the saved agent’s YAML definition.</p>
    </>
  );
}
