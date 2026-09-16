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
        <select id="studio-backend" value={cfg.backend}
          disabled={disabled || (cfg.backends || []).length < 2}
          title={cfg.host} onChange={(event) => onBackendChange(event.target.value)}>
          {(cfg.backends || [cfg.backend]).map((backend) => (
            <option key={backend} value={backend}>{backend}</option>
          ))}
        </select>
      </div>
    </header>
    {cfg.notice ? (
      <div className="portal-notice info-note" role="status">
        {cfg.notice}
        <span className="portal-nav">
          <a href="/">Studio</a>
          <a href="/webrtc">WebRTC</a>
          <a href="/static/demo/sessions.html">Local session logs</a>
        </span>
      </div>
    ) : null}
    </>
  );
}
