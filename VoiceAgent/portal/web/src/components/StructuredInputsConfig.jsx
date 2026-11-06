// Copyright (c) Microsoft. All rights reserved.

import {
  STRUCTURED_INPUT_TYPES,
  defaultStructuredInputValue,
} from "../lib/structuredInput.mjs";

function updateConfig(configs, index, patch, onChange) {
  const next = configs.map((item, itemIndex) => (
    itemIndex === index ? { ...item, ...patch } : item
  ));
  onChange(next);
}

function DefaultValueEditor({ config, disabled, onChange }) {
  if (config.type === "boolean") {
    return (
      <select
        aria-label={`Default value for ${config.name}`}
        value={config.defaultValue}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="false">false</option>
        <option value="true">true</option>
      </select>
    );
  }
  if (config.type === "object" || config.type === "array") {
    return (
      <textarea
        aria-label={`Default value for ${config.name}`}
        rows={2}
        value={config.defaultValue}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      />
    );
  }
  return (
    <input
      aria-label={`Default value for ${config.name}`}
      type="text"
      value={config.defaultValue}
      disabled={disabled}
      onChange={(event) => onChange(event.target.value)}
    />
  );
}

export function StructuredInputsConfig({ configs, disabled, onChange }) {
  if (!configs.length) {
    return (
      <div className="structured-inputs-empty hint">
        Add a Handlebars placeholder such as <code>{"{{customer_name}}"}</code> to the instructions
        or greeting to define a structured input automatically.
      </div>
    );
  }

  return (
    <div className="structured-inputs-config">
      <div className="structured-inputs-head">
        <span>Detected input</span>
        <span>Type</span>
        <span>Default value</span>
      </div>
      {configs.map((config, index) => (
        <div className="structured-input-row" key={config.name}>
          <code>{`{{${config.name}}}`}</code>
          <select
            aria-label={`Type for ${config.name}`}
            value={config.type}
            disabled={disabled}
            onChange={(event) => updateConfig(
              configs,
              index,
              {
                type: event.target.value,
                defaultValue: defaultStructuredInputValue(event.target.value),
              },
              onChange,
            )}
          >
            {STRUCTURED_INPUT_TYPES.map((type) => (
              <option value={type} key={type}>{type}</option>
            ))}
          </select>
          <DefaultValueEditor
            config={config}
            disabled={disabled}
            onChange={(defaultValue) => updateConfig(
              configs,
              index,
              { defaultValue },
              onChange,
            )}
          />
        </div>
      ))}
    </div>
  );
}
