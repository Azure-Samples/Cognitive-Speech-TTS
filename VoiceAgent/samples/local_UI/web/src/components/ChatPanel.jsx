// Copyright (c) Microsoft. All rights reserved.
// Right column: header (status badge + session id + conversation id + stop/clear) and the chat
// panel (scrolling message bubbles + a text composer). The conversation id surfaces the
// server-side conversation the voice orchestrator writes; "View persisted" opens that conversation
// in a new, full-height browser tab (static/persisted.html) — design §4.4.

import { useEffect, useMemo, useRef, useState } from "react";
import { MessageBubble } from "./MessageBubble.jsx";
import { Icon } from "./ConfigControls.jsx";

function AvatarStage({ stream, status }) {
  const videoRef = useRef(null);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    video.srcObject = stream || null;
    if (stream) video.play().catch(() => {});
    return () => {
      if (video.srcObject === stream) video.srcObject = null;
    };
  }, [stream]);

  return (
    <section className="avatar-stage" aria-label="Live avatar">
      {stream ? (
        <video ref={videoRef} className="avatar-video" autoPlay playsInline controls />
      ) : (
        <div className="avatar-placeholder">
          <div className="avatar-placeholder-icon">👤</div>
          <div>Waiting for avatar video…</div>
        </div>
      )}
      <span className={"avatar-state " + (status === "speaking" ? "speaking" : "")}>
        avatar: {status}
      </span>
    </section>
  );
}

// Hidden <audio> sink for the WebRTC media transport: the agent audio arrives as an inbound RTP
// track (not response.audio.delta), so it plays through a MediaStream element rather than WebAudio.
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

/* The protocol beside the transcript.
 *
 * The transcript says what was said; it cannot say why the agent went quiet, which node it moved
 * to, or whether a tool was even attempted. Those are frames, and until now the only way to read
 * them live was Developer mode -- which printed a bare type name, and only for events the page did
 * not already handle. Developer mode now owns this complete stream and each expandable payload. */
function EventRow({ e, openId, setOpenId }) {
  if (e.kind === "handoff") {
    const h = e.handoff;
    return (
      <div className="event-row handoff">
        <button type="button" className="event-line" onClick={() => setOpenId(openId === e.id ? null : e.id)}>
          <span className="event-at">{e.at.toFixed(2)}</span>
          <span className="event-dir">⇄</span>
          <span className="event-type">
            handoff {h.fromNodeId} → {h.toNodeId}
            <span className={"handoff-state " + h.status}>{h.status}</span>
          </span>
        </button>
        {openId === e.id ? <pre className="event-payload">{JSON.stringify(h, null, 2)}</pre> : null}
      </div>
    );
  }
  return (
    <div className={"event-row " + e.dir + (openId === e.id ? " open" : "")}>
      <button type="button" className="event-line" onClick={() => setOpenId(openId === e.id ? null : e.id)}>
        <span className="event-at">{e.at.toFixed(2)}</span>
        <span className="event-dir">{e.dir === "up" ? "▲" : "▼"}</span>
        <span className="event-type">{e.type}</span>
      </button>
      {openId === e.id ? <pre className="event-payload">{JSON.stringify(e.frame, null, 2)}</pre> : null}
    </div>
  );
}

/* Transcript and frames as ONE timeline, not two lists side by side.
 *
 * Each row is a message together with every frame that arrived before it, so "which events happened
 * because of what I just said" is answered by reading across -- the frames above a line of speech
 * are, by construction, the ones that preceded it. Two independently scrolling columns could not
 * answer that: the same vertical position meant nothing on both sides.
 *
 * Whichever side is shorter is padded with blank space rather than being allowed to drift. */
function Timeline({ messages, events, filter, showEvents, onApproval, listRef, onScroll, emptyContent }) {
  const [openId, setOpenId] = useState(null);

  useEffect(() => {
    if (!showEvents) setOpenId(null);
  }, [showEvents]);

  const rows = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    const frames = showEvents
      ? events.filter((e) =>
        e.kind !== "turn" && (!needle || (e.type || "handoff").toLowerCase().includes(needle)))
      : [];
    const out = [];
    let cursor = 0;
    for (const message of messages) {
      const before = [];
      // A message inserted out of order (a tool card placed above the reply it belongs to) simply
      // takes no frames; it stays where it reads correctly instead of stealing another row's.
      while (cursor < frames.length && frames[cursor].at <= (message.at ?? Infinity)) {
        before.push(frames[cursor++]);
      }
      out.push({ key: `m-${message.id}`, message, events: before });
    }
    if (cursor < frames.length) {
      out.push({ key: "tail", message: null, events: frames.slice(cursor) });
    }
    return out;
  }, [messages, events, filter, showEvents]);

  return (
    <div className={"timeline " + (showEvents ? "developer-events" : "conversation-only")} ref={listRef} onScroll={onScroll}>
      {rows.map((row) => (
        <div className="timeline-row" key={row.key}>
          {showEvents ? <div className="timeline-events">
            {row.events.map((e) => (
              <EventRow key={e.id} e={e} openId={openId} setOpenId={setOpenId} />
            ))}
          </div> : null}
          <div className="timeline-message">
            {row.message ? (
              <MessageBubble message={row.message} allMessages={messages} onApproval={onApproval} />
            ) : null}
          </div>
        </div>
      ))}
      {rows.length ? null : !showEvents ? emptyContent : (
        <p className="event-empty">
          {showEvents
            ? "Speech and protocol frames appear here as the session runs."
            : "Conversation and session status appear here as the session runs."}
        </p>
      )}
    </div>
  );
}

export function ChatPanel({ session, agent, showExternalLinks = true }) {
  const {
    sessionId,
    conversationId,
    activeHandoffNodeId,
    isConnected,
    sessionReady,
    messages,
    avatarActive,
    avatarStatus,
    avatarStream,
    webrtcActive,
    webrtcStatus,
    webrtcStream,
    verbose,
    sendText,
    clearMessages,
    sendMcpApprovalResponse,
    events,
    clearEvents,
  } = session;
  const [text, setText] = useState("");
  const [eventFilter, setEventFilter] = useState("");
  const [follow, setFollow] = useState(true);
  const listRef = useRef(null);
  const visibleEventCount = verbose ? events.length : 0;

  // Following the tail is what you want while talking; scrolling up to read a frame must not be
  // yanked back by the next event, so following pauses until you return to the bottom.
  useEffect(() => {
    if (!follow || !listRef.current) return;
    listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [messages, visibleEventCount, follow]);

  const onScroll = () => {
    const box = listRef.current;
    if (!box) return;
    setFollow(box.scrollHeight - box.scrollTop - box.clientHeight < 40);
  };

  const onSend = () => {
    if (!isConnected || !sessionReady || !text.trim()) return;
    sendText(text);
    setText("");
  };

  const agentName = agent && agent.name;

  // Open the server-persisted conversation in a new tab (full height). The page resolves the
  // conversation itself (uses the live id when present, else the agent's latest).
  const openPersisted = () => {
    if (!agentName) return;
    const q = new URLSearchParams({ agent: agentName });
    if (conversationId) q.set("conversation", conversationId);
    window.open(`/static/demo/persisted.html?${q.toString()}`, "_blank", "noopener");
  };

  const openTrace = () => {
    if (!agentName) return;
    const query = new URLSearchParams({ agent: agentName });
    window.open(`/foundry-trace?${query.toString()}`, "_blank", "noopener");
  };

  return (
    <main className="main" aria-label="Live conversation">
      <div className="main-header">
        <div className="header-left">
          <span className="conversation-label">Conversation</span>
          {sessionId || conversationId ? (
            <details className="session-identifiers">
              <summary>Session details</summary>
              <dl>
                <div><dt>Session ID</dt><dd>{sessionId || "\u2014"}</dd></div>
                <div><dt>Conversation ID</dt><dd>{conversationId || "\u2014"}</dd></div>
                {webrtcActive ? <div><dt>WebRTC</dt><dd>{webrtcStatus}</dd></div> : null}
                {activeHandoffNodeId ? <div><dt>Active node</dt><dd>{activeHandoffNodeId}</dd></div> : null}
              </dl>
            </details>
          ) : null}
        </div>
        <div className="header-right">
          {showExternalLinks ? (
            <>
              <button className="text-button" disabled={!agentName} onClick={openPersisted} title="Open the server-persisted conversation in a new tab">
                View persisted <Icon name="external" />
              </button>
              <button
                className="text-button" disabled={!agentName}
                onClick={openTrace}
                title="Open this agent's traces in Microsoft Foundry"
              >
                View trace <Icon name="external" />
              </button>
            </>
          ) : null}
          <button
            className="text-button"
            onClick={() => { clearMessages(); clearEvents(); }}
            disabled={messages.length === 0 && (!verbose || events.length === 0)}
          >
            Clear chat
          </button>
        </div>
      </div>

      {verbose ? <div className="event-controls">
        <input className="event-filter" aria-label="Filter protocol frames" placeholder="Filter frames…"
          value={eventFilter} onChange={(e) => setEventFilter(e.target.value)} />
        {["", "mcp", "handoff", "session.", "error"].map((preset) => (
          <button key={preset || "all"} type="button"
            className={"event-preset" + (eventFilter === preset ? " active" : "")}
            onClick={() => setEventFilter(preset)}>
            {preset || "all"}
          </button>
        ))}
      </div> : null}

      <div className={"live-body " + (avatarActive ? "with-avatar" : "")}>
        {avatarActive ? <AvatarStage stream={avatarStream} status={avatarStatus} /> : null}
        <AudioSink stream={webrtcStream} />
        <div className="live-main">
          {verbose ? <div className="timeline-head">
            <span>Protocol frames</span>
            <span>Conversation</span>
          </div> : null}
          <Timeline
            messages={messages}
            events={events}
            filter={eventFilter}
            showEvents={verbose}
            onApproval={sendMcpApprovalResponse}
            listRef={listRef}
            onScroll={onScroll}
            emptyContent={(
            <div className="conversation-empty">
              <div className="voice-emblem"><Icon name="wave" /></div>
              <span className="eyebrow">YOUR AGENT, IN CONVERSATION</span>
              <h3>{agent ? "Ready when you are" : "Hear it come to life"}</h3>
              <p>{agent
                ? "Connect to speak with your agent, or send a message once the session is ready."
                : "Build an agent on the left, or choose an existing one above. Then connect and start talking."}</p>
              <div className="empty-capabilities">
                <span><Icon name="voice" />Natural voice</span>
                <span><Icon name="tools" />Live tool calls</span>
                <span><Icon name="code" />Full traces</span>
              </div>
            </div>
            )}
          />
        </div>
      </div>

      <div className="composer">
        <input
          type="text"
          aria-label="Message your agent"
          placeholder={isConnected ? "Message your agent…" : "Connect to start a conversation…"}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.nativeEvent.isComposing) onSend(); }}
        />
        <button className="primary" disabled={!isConnected || !sessionReady || !text.trim()} onClick={onSend}>Send<Icon name="arrow" /></button>
      </div>
    </main>
  );
}
