// Copyright (c) Microsoft. All rights reserved.

import { LIMITS, MODEL_TYPE_OPTIONS, MODEL_TYPE_SELF_DEPLOYED, USE_CASE_GROUPS } from "../lib/authoringContract.mjs";
import { Field, GroupedSelect, Icon, SectionHeading, Toggle } from "./ConfigControls.jsx";

export function GenerateConfig({ value, update, disabled, hosted, toolCount, onTools }) {
  return (
    <>
      <SectionHeading title="Describe your agent" description="Start with a goal. Review the generated definition before you connect." />
      {hosted ? <div className="info-note">
        Guided authoring supports managed models and BYOM. Switch the model source in Configure → Agent to continue.
      </div> : null}
      <Field label="Goal" optional meta={`${value.goal.length} / ${LIMITS.goal}`}>
        <textarea rows={7} value={value.goal} maxLength={LIMITS.goal} disabled={disabled || hosted}
          placeholder="A warm, concise support agent that answers billing questions and routes technical issues to a specialist…"
          onChange={(event) => update("goal", event.target.value)} />
      </Field>
      <Field label="Use case" optional>
        <GroupedSelect value={value.useCase} placeholder="General-purpose assistant"
          groups={USE_CASE_GROUPS} disabled={disabled || hosted}
          onChange={(event) => update("useCase", event.target.value)} />
      </Field>
      <Field label="Generated agent name" optional hint="Leave blank to generate a unique name.">
        <input type="text" value={value.name} maxLength={LIMITS.name} disabled={disabled || hosted}
          placeholder="e.g. billing-assistant" onChange={(event) => update("name", event.target.value)} />
      </Field>
      <button className="tool-summary-link" type="button" onClick={onTools}>
        <Icon name="tools" />
        <span><strong>{toolCount ? `${toolCount} tool${toolCount === 1 ? "" : "s"} included` : "Add knowledge & tools"}</strong>
          <small>Shared with your manual configuration</small></span>
        <Icon name="chevron" />
      </button>
      <details className="advanced-details">
        <summary>Generation options</summary>
        <Field label="Generation model source">
          <select value={value.modelType} disabled={disabled || hosted}
            onChange={(event) => update("modelType", event.target.value)}>
            {MODEL_TYPE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.value === "" ? "Service default" : option.value === "managed" ? "Managed model" : "Your deployment (BYOM)"}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Generation model" optional={value.modelType !== MODEL_TYPE_SELF_DEPLOYED}
          hint={value.modelType === MODEL_TYPE_SELF_DEPLOYED
            ? "Required: enter an existing Foundry deployment name."
            : "Leave blank to let the service choose."}>
          <input type="text" value={value.model} maxLength={LIMITS.model} disabled={disabled || hosted}
            placeholder={value.modelType === MODEL_TYPE_SELF_DEPLOYED ? "Your deployment name" : "Service default"}
            onChange={(event) => update("model", event.target.value)} />
        </Field>
        <Field label="Generated agent description" optional>
          <input type="text" value={value.description} maxLength={LIMITS.description}
            disabled={disabled || hosted} placeholder="Let the service choose"
            onChange={(event) => update("description", event.target.value)} />
        </Field>
        <Toggle label="Create as a draft" checked={value.draft} disabled={disabled || hosted}
          onChange={(checked) => update("draft", checked)} />
      </details>
      <div className="field-hint">The service fills in instructions, voice, and audio settings. <code>kind: voice</code> is sent automatically.</div>
    </>
  );
}
