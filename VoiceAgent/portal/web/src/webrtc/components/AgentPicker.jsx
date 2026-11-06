// Copyright (c) Microsoft. All rights reserved.
// Setup phase: pick one agent from the shared catalog and start a WebRTC session.
// Intentionally minimal — no agent authoring here (that stays in the integrated demo);
// this standalone experience is about running + reviewing a single voice session.

import { useState } from "react";

export function AgentPicker({ agents, state, onStart }) {
  const [selectedName, setSelectedName] = useState("");
  const selected = agents.find((a) => a.name === selectedName) || null;

  return (
    <section className="wrtc-setup">
      <h1>Start a voice session</h1>
      <p className="wrtc-sub">Pick an agent, then talk to it over WebRTC. When you end the
        session, the persisted conversation is shown right here.</p>

      {state.loading ? <div className="wrtc-loading">Loading agents…</div> : null}
      {state.error ? <div className="wrtc-error">Could not list agents: {state.error}</div> : null}

      {!state.loading && !state.error ? (
        <div className="wrtc-picker">
          <label className="wrtc-field">
            <span>Agent</span>
            <select value={selectedName} onChange={(e) => setSelectedName(e.target.value)}>
              <option value="">Select an agent…</option>
              {agents.map((a) => (
                <option key={a.name} value={a.name}>
                  {a.name}{a.model ? ` · ${a.model}` : ""}
                </option>
              ))}
            </select>
          </label>
          <button className="wrtc-start" disabled={!selected} onClick={() => onStart(selected)}>
            Start WebRTC session
          </button>
        </div>
      ) : null}
    </section>
  );
}
