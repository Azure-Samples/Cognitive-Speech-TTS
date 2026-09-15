// Copyright (c) Microsoft. All rights reserved.

import { useEffect, useRef, useState } from "react";

import { loadVoiceAgent } from "../lib/agentCatalog.mjs";
import {
  agentDefinitionToYaml,
  parseAgentDefinitionYaml,
} from "../lib/agentDefinition.mjs";
import {
  serviceHeaders,
  withApiVersion,
} from "../lib/serviceContract.js";

function responseError(data, fallback) {
  if (typeof data?.error === "string") return data.error;
  if (typeof data?.error?.message === "string") return data.error.message;
  if (typeof data?.message === "string") return data.message;
  return fallback;
}

function latestVersion(resource) {
  return resource?.versions?.latest || {};
}

export function AgentDefinitionDialog({
  cfg,
  agentName,
  open,
  logApi,
  onClose,
  onSaved,
}) {
  const dialogRef = useRef(null);
  const [yaml, setYaml] = useState("");
  const [versionContext, setVersionContext] = useState({
    description: "",
    metadata: {},
  });
  const [state, setState] = useState({
    loading: false,
    saving: false,
    kind: "",
    text: "",
  });

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  useEffect(() => {
    if (!open || !agentName) return undefined;
    let cancelled = false;
    setYaml("");
    setState({
      loading: true,
      saving: false,
      kind: "warn",
      text: "Loading current definition…",
    });

    loadVoiceAgent(cfg, agentName)
      .then((resource) => {
        if (cancelled) return;
        const latest = latestVersion(resource);
        setYaml(agentDefinitionToYaml(latest.definition));
        setVersionContext({
          description: latest.description || "",
          metadata: latest.metadata ? { ...latest.metadata } : {},
        });
        setState({
          loading: false,
          saving: false,
          kind: "",
          text: latest.version
            ? `Editing current version ${latest.version}`
            : "Editing current definition",
        });
      })
      .catch((error) => {
        if (cancelled) return;
        setState({
          loading: false,
          saving: false,
          kind: "err",
          text: String(error),
        });
      });

    return () => {
      cancelled = true;
    };
  }, [agentName, cfg, open]);

  const close = () => {
    if (!state.saving) onClose();
  };

  const save = async () => {
    setState((current) => ({
      ...current,
      saving: true,
      kind: "warn",
      text: "Creating a new version…",
    }));
    try {
      const definition = parseAgentDefinitionYaml(yaml);
      const body = { definition };
      if (versionContext.description) {
        body.description = versionContext.description;
      }
      if (Object.keys(versionContext.metadata).length) {
        body.metadata = versionContext.metadata;
      }

      const path = withApiVersion(
        cfg,
        `/agents/${encodeURIComponent(agentName)}/versions`,
      );
      logApi("POST", path);
      const response = await fetch(path, {
        method: "POST",
        headers: serviceHeaders(cfg, { "Content-Type": "application/json" }),
        body: JSON.stringify(body),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(
          responseError(
            data,
            `Create version failed with HTTP ${response.status}`,
          ),
        );
      }

      const resource = await loadVoiceAgent(cfg, agentName);
      const latest = latestVersion(resource);
      setYaml(agentDefinitionToYaml(latest.definition));
      setVersionContext({
        description: latest.description || "",
        metadata: latest.metadata ? { ...latest.metadata } : {},
      });
      onSaved(resource);
      setState({
        loading: false,
        saving: false,
        kind: "ok",
        text: `Version ${data.version || latest.version || "new"} created`,
      });
    } catch (error) {
      setState({
        loading: false,
        saving: false,
        kind: "err",
        text: String(error),
      });
    }
  };

  return (
    <dialog
      ref={dialogRef}
      className="definition-dialog"
      onCancel={(event) => {
        event.preventDefault();
        close();
      }}
      onClick={(event) => {
        if (event.target === dialogRef.current) close();
      }}
    >
      <div className="definition-dialog-shell">
        <header>
          <div>
            <h2>Edit agent definition</h2>
            <p>
              <code>{agentName}</code>
            </p>
          </div>
          <button
            type="button"
            className="dialog-close"
            aria-label="Close definition editor"
            disabled={state.saving}
            onClick={close}
          >
            ×
          </button>
        </header>
        <div className="definition-dialog-copy">
          Edit the current YAML definition. Saving validates it and creates an
          immutable new agent version.
        </div>
        <textarea
          className="definition-editor"
          aria-label="Agent definition YAML"
          value={yaml}
          disabled={state.loading || state.saving}
          spellCheck="false"
          onChange={(event) => setYaml(event.target.value)}
        />
        <footer>
          <span className={`definition-save-state ${state.kind || ""}`}>
            {state.text}
          </span>
          <div className="definition-dialog-actions">
            <button type="button" disabled={state.saving} onClick={close}>
              Cancel
            </button>
            <button
              type="button"
              className="primary"
              disabled={state.loading || state.saving || !yaml.trim()}
              onClick={save}
            >
              {state.saving ? "Saving…" : "Save as new version"}
            </button>
          </div>
        </footer>
      </div>
    </dialog>
  );
}
