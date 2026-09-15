// Copyright (c) Microsoft. All rights reserved.

import { Icon } from "./ConfigControls.jsx";

export function StudioHeader({ cfg, disabled, onBackendChange }) {
  return (
    <>
    <header className="studio-header">
      <div className="studio-brand">
        <span className="brand-mark"><Icon name="wave" /></span>
        <div><h1>Voice agent <span>studio</span></h1><p>Configure. Connect. Converse.</p></div>
      </div>
      <div className="studio-backend">
        <label htmlFor="studio-backend">Agent backend</label>
        <select id="studio-backend" value={cfg.backend} disabled={disabled}
          title={cfg.host} onChange={(event) => onBackendChange(event.target.value)}>
          {(cfg.backends || [cfg.backend]).map((backend) => (
            <option key={backend} value={backend}>{backend}</option>
          ))}
        </select>
      </div>
    </header>
    {cfg.voiceWsOverride ? (
      <div className="local-voice-ws info-note" role="status">
        Voice session → local Voice Live ({cfg.voiceWsOverride}). Agent list and definitions still come from {cfg.backend}.
      </div>
    ) : null}
    </>
  );
}
