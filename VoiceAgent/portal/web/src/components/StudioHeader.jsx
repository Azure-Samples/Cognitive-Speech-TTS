// Copyright (c) Microsoft. All rights reserved.

import { useEffect, useMemo, useState } from "react";

import {
  filterProjectsByName,
  projectDisplayValue,
  resolveProjectEndpoint,
} from "../lib/projectPicker.mjs";
import { Icon } from "./ConfigControls.jsx";

export function StudioHeader({ cfg, disabled }) {
  const [projects, setProjects] = useState([]);
  const [projectInput, setProjectInput] = useState(cfg.backend);
  const [resultsOpen, setResultsOpen] = useState(false);
  const [state, setState] = useState({ loading: true, error: "" });
  const filtered = useMemo(
    () => filterProjectsByName(projectInput, projects).slice(0, 30),
    [projectInput, projects],
  );

  useEffect(() => {
    fetch("/api/projects")
      .then(async (response) => {
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
        const visible = payload.projects || [];
        setProjects(visible);
        setProjectInput(projectDisplayValue(visible, cfg.host, cfg.backend));
        setState({ loading: false, error: "" });
      })
      .catch((error) => setState({ loading: false, error: String(error.message || error) }));
  }, [cfg.host, cfg.backend]);

  const selectProject = async (endpoint) => {
    if (!endpoint) return;
    if (endpoint === cfg.host) {
      setProjectInput(projectDisplayValue(projects, endpoint, cfg.backend));
      setResultsOpen(false);
      return;
    }
    setState({ loading: true, error: "" });
    try {
      const response = await fetch("/api/project", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ endpoint }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
      const url = new URL(window.location.href);
      url.searchParams.delete("agent");
      url.searchParams.delete("backend");
      window.location.assign(url.toString());
    } catch (error) {
      setState({ loading: false, error: String(error.message || error) });
    }
  };

  const submitProject = (event) => {
    event.preventDefault();
    const endpoint = resolveProjectEndpoint(projectInput, projects);
    if (!endpoint) {
      setState({
        loading: false,
        error: "Choose a matching suggestion or paste a full Foundry Project endpoint.",
      });
      return;
    }
    void selectProject(endpoint);
  };

  return (
    <>
    <header className="studio-header">
      <div className="studio-brand">
        <span className="brand-mark"><Icon name="wave" /></span>
        <div><h1>Voice agent <span>studio</span></h1><p>Configure. Connect. Converse.</p></div>
      </div>
      <nav className="portal-page-nav" aria-label="Portal pages">
        <span>Live session</span>
        <a href="/templates">Templates</a>
      </nav>
      <div className="studio-backend">
        <label htmlFor="studio-backend">Foundry project</label>
        <form className="project-search" onSubmit={submitProject}>
          <div className="project-search-row">
            <input id="studio-backend" type="text" value={projectInput}
              placeholder="Type a project name or paste its endpoint"
              title={state.error || cfg.host} aria-invalid={Boolean(state.error)}
              autoComplete="off" spellCheck="false" role="combobox"
              aria-autocomplete="list" aria-expanded={resultsOpen}
              aria-controls="portal-project-options"
              disabled={disabled || state.loading}
              onFocus={() => setResultsOpen(true)}
              onBlur={() => setResultsOpen(false)}
              onKeyDown={(event) => {
                if (event.key === "Escape") setResultsOpen(false);
              }}
              onChange={(event) => {
                setProjectInput(event.target.value);
                setResultsOpen(true);
                if (state.error) setState({ loading: false, error: "" });
              }} />
            <button type="submit" className="project-switch"
              disabled={disabled || state.loading || !projectInput.trim()}>
              Switch
            </button>
          </div>
          {resultsOpen && !disabled && !state.loading ? (
            <div id="portal-project-options" className="project-results" role="listbox"
              aria-label="Matching Foundry projects">
              {filtered.length ? filtered.map((project) => (
                <button key={project.endpoint} type="button" role="option"
                  aria-selected={project.endpoint === cfg.host} className="project-result"
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => selectProject(project.endpoint)}>
                  <span className="project-result-name">{project.name}</span>
                  <span className="project-result-account">{project.account}</span>
                </button>
              )) : (
                <span className="project-results-empty">No Project names match this search.</span>
              )}
            </div>
          ) : null}
          <span className={`project-search-hint ${state.error ? "error" : ""}`} role="status">
            {state.loading ? "Discovering visible projects…" : state.error
              || "Search by Project name. Choose a result to distinguish duplicate names."}
          </span>
        </form>
      </div>
    </header>
    {cfg.notice ? (
      <div className="portal-notice info-note" role="status">
        {cfg.notice}
        <span className="portal-nav">
          <a href="/">Studio</a>
          <a href="/webrtc">WebRTC</a>
          <a href="/static/demo/sessions.html">Local session logs</a>
          <a href="/static/demo/THIRD_PARTY_NOTICES.txt" target="_blank" rel="noopener noreferrer">Licenses</a>
        </span>
      </div>
    ) : null}
    </>
  );
}
