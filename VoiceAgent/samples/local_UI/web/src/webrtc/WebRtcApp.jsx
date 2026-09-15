// Copyright (c) Microsoft. All rights reserved.
// Standalone WebRTC app shell. Three phases drive a single-agent, WebRTC-only experience:
//   setup  -> pick an agent (reuses the shared agent catalog + /config).
//   live   -> WebRTC voice session (transport forced to "webrtc" on connect).
//   review -> INLINE persisted showcase for the just-finished conversation (no new tab).
// It deliberately reuses the shared useVoiceSession hook and config loaders; only the
// layout/feel is different from the integrated demo (App.jsx), which is left untouched.

import { useCallback, useEffect, useState } from "react";
import { loadConfig } from "../config.js";
import { loadVoiceAgents } from "../lib/agentCatalog.mjs";
import { useVoiceSession } from "../hooks/useVoiceSession.js";
import { AgentPicker } from "./components/AgentPicker.jsx";
import { LiveStage } from "./components/LiveStage.jsx";
import { PersistedShowcase } from "./components/PersistedShowcase.jsx";

export function WebRtcApp() {
  const [cfg, setCfg] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [agents, setAgents] = useState([]);
  const [agentsState, setAgentsState] = useState({ loading: true, error: "" });
  const [agent, setAgent] = useState(null);
  const [phase, setPhase] = useState("setup"); // "setup" | "live" | "review"
  const [reviewConversationId, setReviewConversationId] = useState(null);
  const session = useVoiceSession();

  useEffect(() => {
    loadConfig()
      .then(async (loaded) => {
        try {
          setAgents(await loadVoiceAgents(loaded));
          setAgentsState({ loading: false, error: "" });
        } catch (e) {
          setAgentsState({ loading: false, error: String(e) });
        }
        setCfg(loaded);
      })
      .catch((e) => setLoadError(String(e)));
  }, []);

  const start = useCallback((selected) => {
    if (!selected) return;
    setAgent(selected);
    setReviewConversationId(null);
    session.clearMessages();
    setPhase("live");
    // 5th arg forces the WebRTC transport (see useVoiceSession.connect signature).
    session.connect(selected.name, undefined, undefined, undefined, "webrtc");
  }, [session]);

  const end = useCallback(() => {
    // Capture the conversation id BEFORE teardown so the review phase can showcase it inline.
    setReviewConversationId(session.conversationId || null);
    session.stopSession();
    setPhase("review");
  }, [session]);

  const restart = useCallback(() => {
    session.clearMessages();
    setReviewConversationId(null);
    setAgent(null);
    setPhase("setup");
  }, [session]);

  if (loadError) return <div className="wrtc-error">Could not load /config: {loadError}</div>;
  if (!cfg) return <div className="wrtc-loading">Loading…</div>;

  return (
    <div className="wrtc-shell">
      <header className="wrtc-header">
        <div className="wrtc-title">Voice Agent <span className="wrtc-chip">WebRTC</span></div>
        <div className="wrtc-header-right">
          {agent ? <span className="wrtc-agent">{agent.name}</span> : null}
          <span className={"wrtc-badge wrtc-" + (session.webrtcStatus || "off")}>
            webrtc: {session.webrtcStatus || "off"}
          </span>
        </div>
      </header>

      <main className="wrtc-body">
        {phase === "setup" ? (
          <AgentPicker agents={agents} state={agentsState} onStart={start} />
        ) : null}
        {phase === "live" ? (
          <LiveStage session={session} agent={agent} onEnd={end} />
        ) : null}
        {phase === "review" ? (
          <PersistedShowcase
            cfg={cfg}
            agent={agent}
            conversationId={reviewConversationId}
            onRestart={restart}
          />
        ) : null}
      </main>
    </div>
  );
}
