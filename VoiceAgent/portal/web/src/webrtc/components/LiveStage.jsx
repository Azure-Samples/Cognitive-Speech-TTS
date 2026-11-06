// Copyright (c) Microsoft. All rights reserved.
// Live phase: the running WebRTC voice session. Agent audio arrives as an inbound RTP track
// (not response.audio.delta), so it plays through a hidden <audio> bound to webrtcStream.
// Reuses the shared MessageBubble so transcript rendering matches the integrated demo.

import { useEffect, useRef } from "react";
import { MessageBubble } from "../../components/MessageBubble.jsx";

// Hidden media sink for the WebRTC inbound audio track.
function AudioSink({ stream }) {
  const audioRef = useRef(null);
  useEffect(() => {
    const el = audioRef.current;
    if (!el) return;
    el.srcObject = stream || null;
    if (stream) el.play().catch(() => {});
    return () => { if (el.srcObject === stream) el.srcObject = null; };
  }, [stream]);
  return <audio ref={audioRef} autoPlay style={{ display: "none" }} />;
}

export function LiveStage({ session, agent, onEnd }) {
  const { status, sessionId, conversationId, micMuted, isConnected, messages, webrtcStream, toggleMute } = session;
  const listRef = useRef(null);

  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [messages]);

  return (
    <section className="wrtc-stage">
      <div className="wrtc-stage-head">
        <div className="wrtc-stage-status">
          <span className={"wrtc-status " + (status.kind || "")}>{status.text}</span>
          <span className="wrtc-id">session: <code>{sessionId || "\u2014"}</code></span>
          <span className="wrtc-id">conversation: <code>{conversationId || "\u2014"}</code></span>
        </div>
        <div className="wrtc-stage-controls">
          <button onClick={toggleMute} disabled={!isConnected}>
            {micMuted ? "Unmute" : "Mute"}
          </button>
          <button className="wrtc-end" onClick={onEnd}>End &amp; review</button>
        </div>
      </div>

      <AudioSink stream={webrtcStream} />

      <div className="wrtc-transcript" ref={listRef}>
        {messages.length === 0 ? (
          <div className="wrtc-empty">Say hello — the agent is listening…</div>
        ) : null}
        {messages.map((m) => (
          <MessageBubble key={m.id} message={m} allMessages={messages} />
        ))}
      </div>
    </section>
  );
}
