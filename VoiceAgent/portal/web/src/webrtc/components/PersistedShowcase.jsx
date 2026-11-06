// Copyright (c) Microsoft. All rights reserved.
// Review phase loader. Use the captured conversation ID or require an explicit
// historical selection before fetching transcripts, tool results, or audio.

import { useCallback, useEffect, useState } from "react";
import { MiniPortal } from "./MiniPortal.jsx";

const enc = encodeURIComponent;

export function PersistedShowcase({ cfg, agent, conversationId, onRestart }) {
  const agentName = agent && agent.name;
  const apiVersion = (cfg && cfg.apiVersion) || "v1";
  const foundryFeatures = (cfg && cfg.foundryFeatures) || "VoiceAgents=V1Preview";

  const [state, setState] = useState({ loading: true, error: "", warn: "" });
  const [resolvedId, setResolvedId] = useState(conversationId || null);
  const [choice, setChoice] = useState("");
  const [choices, setChoices] = useState([]);
  const [historyState, setHistoryState] = useState({ loading: false, error: "" });
  const [historyRevision, setHistoryRevision] = useState(0);
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

  useEffect(() => {
    setResolvedId(conversationId || null);
    setChoice("");
    setAudioUrl(null);
  }, [agentName, conversationId]);

  useEffect(() => {
    if (resolvedId || !agentName) return;
    let cancelled = false;
    setChoices([]);
    setHistoryState({ loading: true, error: "" });
    (async () => {
      try {
        const r = await apiFetch(convsPath);
        const d = await r.json();
        if (!r.ok) throw new Error(d.error?.message || d.error || `HTTP ${r.status}`);
        if (cancelled) return;
        setChoices((d.data || []).filter((entry) => entry.id).slice()
          .sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0)));
        setHistoryState({ loading: false, error: "" });
      } catch (error) {
        if (!cancelled) setHistoryState({ loading: false, error: String(error.message || error) });
      }
    })();
    return () => { cancelled = true; };
  }, [resolvedId, agentName, apiFetch, convsPath, historyRevision]);

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
  }, [apiFetch, convsPath]);

  // Conversation object (carries the authoritative `usage` token breakdown + status). Tolerant.
  const loadConversation = useCallback(async (id) => {
    try {
      const r = await apiFetch(convPath(id));
      return r.ok ? await r.json() : null;
    } catch { return null; }
  }, [apiFetch, convsPath]);

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
  }, [apiFetch, convsPath]);

  useEffect(() => {
    if (!resolvedId) return;
    let cancelled = false;
    setState({ loading: true, error: "", warn: "" });
    setItems([]);
    setConv(null);
    setResponses({});
    setAudioUrl(null);
    (async () => {
      try {
        const id = resolvedId;
        const warn = id === conversationId ? "" : "You selected a historical conversation. Shared agents can contain other users' sessions.";
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
  }, [resolvedId, conversationId, loadAllItems, loadConversation, loadResponses]);

  const chooseConversation = () => {
    setResolvedId(null);
    setChoice("");
    setAudioUrl(null);
  };

  const loadRecording = () => {
    if (resolvedId) setAudioUrl(svc(audioContentPath(resolvedId)));
  };
  const segAudioUrl = useCallback(
    (itemId) => (resolvedId ? svc(itemAudioContentPath(resolvedId, itemId)) : null),
    [svc, resolvedId],
  );

  if (!resolvedId) {
    return (
      <section className="wrtc-review" aria-label="Choose a saved conversation">
        <h2>Choose a saved conversation</h2>
        <p>No transcript, tools, or audio are loaded until you choose a conversation.
          Shared agents may contain other users' sessions.</p>
        <form onSubmit={(event) => {
          event.preventDefault();
          if (!choice.trim()) return;
          setState({ loading: true, error: "", warn: "" });
          setResolvedId(choice.trim());
        }}>
          <label htmlFor="wrtc-conversation-choice">Conversation ID</label>{" "}
          <input id="wrtc-conversation-choice" list="wrtc-conversation-choices" autoComplete="off"
            value={choice} onChange={(event) => setChoice(event.target.value)} required
            placeholder="Choose a recent ID or paste an older ID" />
          <datalist id="wrtc-conversation-choices">
            {choices.map((entry) => <option key={entry.id} value={entry.id}>{entry.created_at || entry.id}</option>)}
          </datalist>{" "}
          <button type="submit" disabled={!choice.trim()}>Open conversation</button>
        </form>
        <p role="status">{historyState.loading ? "Loading recent conversation IDs…"
          : historyState.error ? `Could not list conversations: ${historyState.error}. You can still paste a known ID.`
            : choices.length ? "Choose a recent ID or paste another ID."
              : "No recent conversations found. You can still paste a known ID."}</p>
        <button onClick={() => setHistoryRevision((value) => value + 1)} disabled={historyState.loading}>
          Refresh conversations
        </button>{" "}
        <button className="wrtc-start" onClick={onRestart}>New session</button>
      </section>
    );
  }
  if (state.loading) {
    return <section className="wrtc-review"><div className="wrtc-loading">Loading persisted conversation…</div></section>;
  }
  if (state.error) {
    return (
      <section className="wrtc-review">
        <div className="wrtc-error">Could not load conversation: {state.error}</div>
        <div><button onClick={chooseConversation}>Choose conversation</button>{" "}
          <button className="wrtc-start" onClick={onRestart}>New session</button></div>
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
      onChooseConversation={chooseConversation}
      wholeAudioUrl={audioUrl}
      onLoadRecording={loadRecording}
      segAudioUrl={segAudioUrl}
    />
  );
}
