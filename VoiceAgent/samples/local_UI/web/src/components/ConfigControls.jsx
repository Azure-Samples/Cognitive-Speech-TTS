// Copyright (c) Microsoft. All rights reserved.
// Small, accessible controls shared by the agent editor and the session panel.

import { cloneElement, useId } from "react";

const ICONS = {
  wave: <><path d="M3 10v4m4-8v12m5-15v18m5-15v12m4-8v4" /></>,
  agent: <><rect x="4" y="6" width="16" height="14" rx="4" /><path d="M12 3v3m-4 5v2m8-2v2m-7 3h6" /></>,
  sparkles: <><path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3Zm7-1v4m-2-2h4" /></>,
  voice: <><rect x="9" y="3" width="6" height="12" rx="3" /><path d="M5 11a7 7 0 0 0 14 0m-7 7v3m-3 0h6" /></>,
  muted: <><path d="m3 3 18 18M9 9v3a3 3 0 0 0 5 2m1-5V6a3 3 0 0 0-5.6-1.5M5 11a7 7 0 0 0 12 5m2-5a7 7 0 0 1-.2 1.5M12 18v3m-3 0h6" /></>,
  tools: <><path d="m14 6 4 4 3-3a6 6 0 0 1-8 7l-6 6a2.1 2.1 0 0 1-3-3l6-6a6 6 0 0 1 7-8l-3 3Z" /></>,
  workflow: <><rect x="8" y="2" width="8" height="5" rx="1.5" /><rect x="2" y="17" width="8" height="5" rx="1.5" /><rect x="14" y="17" width="8" height="5" rx="1.5" /><path d="M12 7v5M6 17v-5h12v5" /></>,
  flask: <><path d="M9 3h6m-5 0v6l-6 10a1.3 1.3 0 0 0 1 2h14a1.3 1.3 0 0 0 1-2L14 9V3M7 15h10" /></>,
  settings: <><path d="M3 6h6m4 0h8M3 12h12m4 0h2M3 18h2m4 0h12" /><circle cx="11" cy="6" r="2" /><circle cx="17" cy="12" r="2" /><circle cx="7" cy="18" r="2" /></>,
  refresh: <><path d="M20 7v5h-5M4 17v-5h5" /><path d="M6 7a7 7 0 0 1 12-1l2 3M4 15l2 3a7 7 0 0 0 12-1" /></>,
  code: <><path d="m7 7-5 5 5 5m10-10 5 5-5 5M14 4l-4 16" /></>,
  arrow: <><path d="M4 12h16m-6-6 6 6-6 6" /></>,
  chevron: <><path d="m9 5 7 7-7 7" /></>,
  external: <><path d="M14 3h7v7m0-7L11 13M10 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-5" /></>,
  book: <><path d="M12 5v16M3 3h4a5 5 0 0 1 5 2 5 5 0 0 1 5-2h4v16h-4a5 5 0 0 0-5 2 5 5 0 0 0-5-2H3V3Z" /></>,
  box: <><rect x="3" y="6" width="18" height="15" rx="2" /><path d="M8 6V3h8v3M3 12h18m-11 0v3h4v-3" /></>,
  stop: <><rect x="6" y="6" width="12" height="12" rx="2" /></>,
  phone: <><path d="M5 3h4l2 5-3 2a16 16 0 0 0 6 6l2-3 5 2v4a2 2 0 0 1-2 2A18 18 0 0 1 3 5a2 2 0 0 1 2-2Z" /></>,
};

export function Icon({ name, className = "", ...props }) {
  return (
    <svg className={`icon ${className}`} width="18" height="18" viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round"
      strokeLinejoin="round" aria-hidden="true" {...props}>
      {ICONS[name] || ICONS.settings}
    </svg>
  );
}

export function Field({ label, hint, optional, meta, children, className = "" }) {
  const generatedId = useId();
  const id = children.props.id || generatedId;
  const hintId = `${id}-hint`;
  return (
    <div className={`form-field ${className}`}>
      <label className="field-label" htmlFor={id}>
        <span>{label}{optional ? <> <span className="field-optional">Optional</span></> : null}</span>
        {meta ? <span className="field-meta" aria-hidden="true">{meta}</span> : null}
      </label>
      {cloneElement(children, { id, "aria-describedby": hint ? hintId : undefined })}
      {hint ? <div className="field-hint" id={hintId}>{hint}</div> : null}
    </div>
  );
}

export function Toggle({ label, description, checked, onChange, disabled }) {
  return (
    <label className={`switch-field${disabled ? " is-disabled" : ""}`}>
      <span className="switch-copy">
        <span className="field-label">{label}</span>
        {description ? <span className="field-hint">{description}</span> : null}
      </span>
      <input type="checkbox" className="switch-input" checked={checked}
        disabled={disabled} onChange={(event) => onChange(event.target.checked)} />
      <span className="switch-track" aria-hidden="true" />
    </label>
  );
}

export function GroupedSelect({ groups, placeholder, ...props }) {
  return (
    <select {...props}>
      {placeholder ? <option value="">{placeholder}</option> : null}
      {groups.map((group) => (
        <optgroup key={group.label} label={group.label}>
          {group.items.map((item) => <option key={item} value={item}>{item}</option>)}
        </optgroup>
      ))}
    </select>
  );
}

export function SectionHeading({ title, description, icon, children }) {
  return (
    <div className="section-heading">
      <div>
        <h2>{icon ? <Icon name={icon} /> : null}{title}</h2>
        {description ? <p>{description}</p> : null}
      </div>
      {children}
    </div>
  );
}

// Changing an editor tab hides, rather than unmounts, its panel. Tools, subagents,
// generated drafts, and in-flight requests must survive navigation.
export function EditorTabs({ items, value, onChange }) {
  const enabled = items.filter((item) => !item.disabled);
  const onKeyDown = (event) => {
    const index = enabled.findIndex((item) => item.value === value);
    const nextIndex = {
      ArrowRight: (index + 1) % enabled.length,
      ArrowLeft: (index - 1 + enabled.length) % enabled.length,
      Home: 0,
      End: enabled.length - 1,
    }[event.key];
    if (nextIndex === undefined) return;
    event.preventDefault();
    const next = enabled[nextIndex].value;
    onChange(next);
    document.getElementById(`editor-tab-${next}`)?.focus();
  };
  return (
    <div className="editor-tabs" role="tablist" aria-label="Agent configuration" onKeyDown={onKeyDown}>
      {items.map((item) => (
        <button type="button" role="tab" key={item.value} id={`editor-tab-${item.value}`}
          aria-controls={`editor-panel-${item.value}`} aria-selected={value === item.value}
          tabIndex={value === item.value ? 0 : -1} disabled={item.disabled}
          className={`editor-tab${value === item.value ? " active" : ""}`}
          onClick={() => onChange(item.value)}>
          <Icon name={item.icon} />{item.label}
          {item.count > 0 ? <span className="tab-count" aria-hidden="true">{item.count}</span> : null}
        </button>
      ))}
    </div>
  );
}

export function EditorPanel({ name, active, children }) {
  return (
    <section id={`editor-panel-${name}`} role="tabpanel" aria-labelledby={`editor-tab-${name}`}
      className="editor-panel" hidden={!active} tabIndex={0}>
      {children}
    </section>
  );
}
