// Copyright (c) Microsoft. All rights reserved.
// Review phase data loader. Resolves the conversation (given id, else the agent's latest — same
// contract as static/persisted.html: api-version on every call + Foundry-Features header + item
// pagination) and hands the persisted items to <MiniPortal> for the Foundry-style trace UI.

import { useCallback, useEffect, useState } from "react";
import { MiniPortal } from "./MiniPortal.jsx";

const enc = encodeURIComponent;

export function PersistedShowcase({ cfg, agent, conversationId, onRestart }) {
  const agentName = agent && agent.name;
  const apiVersion = (cfg && cfg.apiVersion) || "v1";
  const foundryFeatures = (cfg && cfg.foundryFeatures) || "VoiceAgents=V1Preview";

  const [state, setState] = useState({ loading: true, error: "", warn: "" });
  const [resolvedId, setResolvedId] = useState(conversationId || null);
  const [items, setItems] = useState([]);
  const [conv, setConv] = useState(null);
  const [responses, setResponses] = useState({});
  const [audioUrl, setAudioUrl] = useState(null);

  // Append api-version with the correct ?/& separator (matches persisted.html svc()).
  const svc = useCallback(
    (path) => path + (path.includes("?") ? "&" : "?") + "api-version=" + enc(apiVersion),
    [apiVersion],
  );
  const apiFetch = useCallback(
    (path, opts) => {
      const o = opts || {};
      o.headers = Object.assign({ "Foundry-Features": foundryFeatures }, o.headers || {});
      return fetch(svc(path), o);
    },
    [svc, foundryFeatures],
  );

  const convsPath = `/agents/${enc(agentName)}/endpoint/protocols/voice/conversations`;
  const convPath = (conv) => `${convsPath}/${enc(conv)}`;
  const itemsPath = (conv, after) =>
    `${convPath(conv)}/items?limit=100&order=asc&include_metrics=true${after ? `&after=${enc(after)}` : ""}`;
  const responsePath = (conv, rid) => `${convPath(conv)}/responses/${enc(rid)}`;
  const audioContentPath = (conv) => `${convPath(conv)}/audio/content`;
  const itemAudioContentPath = (conv, item) => `${convPath(conv)}/items/${enc(item)}/audio/content`;

  const resolveConversationId = useCallback(async () => {
    if (conversationId) return { id: conversationId, warn: "" };
    // Fallback (same as persisted.html): pick the agent's most recent conversation. On a SHARED
    // agent this may not be *your* session, so we warn.
    const r = await apiFetch(convsPath);
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`);
    const convs = (d.data || [])
      .slice()
      .sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));
    const latest = convs[0] && convs[0].id;
    if (!latest) throw new Error("no conversations found for this agent");
    return { id: latest, warn: "No live conversation id was captured; showing the agent's most recent conversation." };
  }, [conversationId, apiFetch, convsPath]);

  const loadAllItems = useCallback(async (id) => {
    const all = [];
    let after = null;
    for (let page = 0; page < 20; page++) {
      const r = await apiFetch(itemsPath(id, after));
      const d = await r.json();
      if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`);
      all.push(...(d.data || []));
      if (!d.has_more || !d.last_id || d.last_id === after) return all;
      after = d.last_id;
    }
    return all;
  }, [apiFetch]);

  // Conversation object (carries the authoritative `usage` token breakdown + status). Tolerant.
  const loadConversation = useCallback(async (id) => {
    try {
      const r = await apiFetch(convPath(id));
      return r.ok ? await r.json() : null;
    } catch { return null; }
  }, [apiFetch]);

  // Per-turn response objects (real tokens + voice + sample rate), keyed by response_id. Tolerant.
  const loadResponses = useCallback(async (id, loadedItems) => {
    const ids = [...new Set(loadedItems.map((it) => it.response_id).filter(Boolean))].slice(0, 40);
    const map = {};
    await Promise.all(ids.map(async (rid) => {
      try {
        const r = await apiFetch(responsePath(id, rid));
        if (r.ok) map[rid] = await r.json();
      } catch { /* skip */ }
    }));
    return map;
  }, [apiFetch]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { id, warn } = await resolveConversationId();
        if (cancelled) return;
        setResolvedId(id);
        const [convObj, loaded] = await Promise.all([loadConversation(id), loadAllItems(id)]);
        if (cancelled) return;
        const responsesById = await loadResponses(id, loaded);
        if (cancelled) return;
        setConv(convObj);
        setItems(loaded);
        setResponses(responsesById);
        setState({ loading: false, error: "", warn });
      } catch (e) {
        if (!cancelled) setState({ loading: false, error: String(e && e.message ? e.message : e), warn: "" });
      }
    })();
    return () => { cancelled = true; };
  }, [resolveConversationId, loadAllItems, loadConversation, loadResponses]);

  const loadRecording = () => {
    if (resolvedId) setAudioUrl(svc(audioContentPath(resolvedId)));
  };
  const segAudioUrl = useCallback(
    (itemId) => (resolvedId ? svc(itemAudioContentPath(resolvedId, itemId)) : null),
    [svc, resolvedId],
  );

  if (state.loading) {
    return <section className="wrtc-review"><div className="wrtc-loading">Loading persisted conversation…</div></section>;
  }
  if (state.error) {
    return (
      <section className="wrtc-review">
        <div className="wrtc-error">Could not load conversation: {state.error}</div>
        <div><button className="wrtc-start" onClick={onRestart}>New session</button></div>
      </section>
    );
  }

  return (
    <MiniPortal
      items={items}
      conversation={conv}
      responsesById={responses}
      conversationId={resolvedId}
      warn={state.warn}
      onRestart={onRestart}
      wholeAudioUrl={audioUrl}
      onLoadRecording={loadRecording}
      segAudioUrl={segAudioUrl}
    />
  );
}
