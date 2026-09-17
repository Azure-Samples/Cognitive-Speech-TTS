// Copyright (c) Microsoft. All rights reserved.
// Mini "portal" trace experience for the standalone WebRTC review screen. Mirrors the Foundry
// portal's trace viewer (Trajectories span-tree + timeline + detail panel, and a User view of
// chat bubbles with audio + metadata). Everything is synthesized from the PERSISTED conversation
// (transcripts, per-turn voice_metrics, tool items, audio) — no App Insights access required, so
// it works with only the conversation read the demo already has.

import { useMemo, useState } from "react";
import { PlayerBar } from "./PlayerBar.jsx";

const TOOL_TYPES = new Set([
  "function_call", "function_call_output", "mcp_call", "mcp_approval_request", "mcp_approval_response",
]);

function itemText(item) {
  return ((item && item.content) || [])
    .map((p) => (p ? (typeof p.text === "string" ? p.text : (typeof p.transcript === "string" ? p.transcript : "")) : ""))
    .join("")
    .trim();
}

function hasAudioPart(item) {
  return ((item && item.content) || []).some((p) => p && (p.type === "input_audio" || p.type === "output_audio"));
}

function fmtDur(ms) {
  if (ms == null) return "—";
  return ms >= 1000 ? (ms / 1000).toFixed(2) + "s" : Math.round(ms) + "ms";
}

// Tokens/cost, when the service returns them (usage on the item, else voice_metrics).
function itemTokens(item) {
  const u = item && item.usage;
  if (u) {
    if (typeof u.total_tokens === "number") return u.total_tokens;
    if (typeof u.input_tokens === "number" || typeof u.output_tokens === "number") {
      return (u.input_tokens || 0) + (u.output_tokens || 0);
    }
  }
  const vm = item && (item.voice_metrics || item.voiceMetrics);
  if (vm) {
    if (typeof vm.total_tokens === "number") return vm.total_tokens;
    if (typeof vm.tokens === "number") return vm.tokens;
  }
  return null;
}

function itemCost(item) {
  const u = item && item.usage;
  if (u && typeof u.estimated_cost === "number") return u.estimated_cost;
  const vm = item && (item.voice_metrics || item.voiceMetrics);
  if (vm && typeof vm.cost === "number") return vm.cost;
  return null;
}

// Group flat items into turns: a user message + any tool items + the assistant reply.
function buildTurns(items) {
  const turns = [];
  let pendingUser = null;
  let pendingTools = [];
  for (const item of items) {
    if (item.type === "message") {
      const role = item.role || "";
      if (role === "user") {
        pendingUser = item;
      } else if (role === "assistant") {
        turns.push({ user: pendingUser, assistant: item, tools: pendingTools });
        pendingUser = null;
        pendingTools = [];
      }
    } else if (TOOL_TYPES.has(item.type)) {
      pendingTools.push(item);
    }
  }
  if (pendingUser || pendingTools.length) {
    turns.push({ user: pendingUser, assistant: null, tools: pendingTools });
  }
  return turns;
}

// Flatten a usage object (conversation- or response-level) into metadata rows.
function usageMeta(usage) {
  const m = {};
  if (!usage) return m;
  if (usage.total_tokens != null) m.Tokens = String(usage.total_tokens);
  if (usage.input_tokens != null) m["Input tokens"] = String(usage.input_tokens);
  if (usage.output_tokens != null) m["Output tokens"] = String(usage.output_tokens);
  const inD = usage.input_token_details || {};
  const outD = usage.output_token_details || {};
  if (inD.audio_tokens != null || outD.audio_tokens != null) m["Audio tokens (in/out)"] = `${inD.audio_tokens || 0} / ${outD.audio_tokens || 0}`;
  if (inD.text_tokens != null || outD.text_tokens != null) m["Text tokens (in/out)"] = `${inD.text_tokens || 0} / ${outD.text_tokens || 0}`;
  if (inD.cached_tokens) m["Cached tokens"] = String(inD.cached_tokens);
  return m;
}

// Flatten turns into portal-style spans (depth + duration + detail) for the Trajectories tree/timeline.
function buildNodes(turns, conversationId, conversation, responsesById) {
  const responses = responsesById || {};
  const nodes = [];
  let totalDur = 0;
  turns.forEach((t, i) => {
    const vm = (t.assistant && (t.assistant.voice_metrics || t.assistant.voiceMetrics)) || {};
    const dur = vm.duration_ms != null ? vm.duration_ms : null;
    if (dur) totalDur += dur;
    const resp = (t.assistant && t.assistant.response_id && responses[t.assistant.response_id]) || null;
    const usage = resp && resp.usage;
    const tokens = usage && usage.total_tokens != null ? usage.total_tokens : itemTokens(t.assistant);
    const voice = resp && resp.audio && resp.audio.output && resp.audio.output.voice && resp.audio.output.voice.name;
    const rate = resp && resp.audio && resp.audio.output && resp.audio.output.format && resp.audio.output.format.rate;
    const modalities = resp && resp.output_modalities;
    const assistantText = t.assistant ? itemText(t.assistant) : "";
    const userText = t.user ? itemText(t.user) : "";
    const turnMeta = {
      "Time to first audio (TTFA)": vm.ttfa_ms != null ? fmtDur(vm.ttfa_ms) : "—",
      "Time to first token (TTFT)": vm.ttft_ms != null ? fmtDur(vm.ttft_ms) : "—",
      "Turn duration": dur != null ? fmtDur(dur) : "—",
      "Avg inter-token latency": vm.itl_avg_ms != null ? fmtDur(vm.itl_avg_ms) : "—",
      "Barge-in": vm.interrupted ? "yes" : "no",
      Modality: modalities ? modalities.join(", ") : "voice",
      ...usageMeta(usage),
      ...(voice ? { Voice: voice } : {}),
      ...(rate ? { "Sample rate": `${rate / 1000} kHz` } : {}),
    };
    nodes.push({
      key: `t${i}`, depth: 1, kind: "turn", tag: "Voice.turn", label: "Voice_live",
      durationMs: dur, tokens,
      input: userText || "Audio stream (16 kHz PCM) — caller speaking",
      output: assistantText || "(audio reply)",
      metadata: turnMeta,
      itemId: t.assistant && (t.assistant.id || t.assistant.item_id),
    });
    if (t.user || vm.stt_ms != null) {
      nodes.push({ key: `t${i}-stt`, depth: 2, kind: "stt", tag: "Speech_to_text", label: "transcription",
        durationMs: vm.stt_ms != null ? vm.stt_ms : null, input: "caller audio", output: userText || "—",
        metadata: { "STT latency": vm.stt_ms != null ? fmtDur(vm.stt_ms) : "—" },
        itemId: t.user && (t.user.id || t.user.item_id) });
    }
    nodes.push({ key: `t${i}-llm`, depth: 2, kind: "llm", tag: "LLM", label: "response",
      durationMs: vm.ttft_ms != null ? vm.ttft_ms : null, tokens: usage && usage.output_tokens != null ? usage.output_tokens : null,
      input: userText || "—", output: assistantText || "—",
      metadata: { "Time to first token": vm.ttft_ms != null ? fmtDur(vm.ttft_ms) : "—", ...usageMeta(usage) } });
    t.tools.forEach((tool, j) => {
      nodes.push({ key: `t${i}-tool${j}`, depth: 2, kind: "tool", tag: "Tool",
        label: tool.name || tool.server_label || tool.type,
        durationMs: tool.duration_ms != null ? tool.duration_ms : null,
        input: tool.arguments ? (typeof tool.arguments === "string" ? tool.arguments : JSON.stringify(tool.arguments)) : "—",
        output: tool.output != null ? (typeof tool.output === "string" ? tool.output : JSON.stringify(tool.output)) : "—",
        metadata: { Type: tool.type } });
    });
    nodes.push({ key: `t${i}-tts`, depth: 2, kind: "tts", tag: "Text_to_speech", label: "audio output",
      durationMs: vm.ttfa_ms != null ? vm.ttfa_ms : null, input: assistantText || "—",
      output: rate ? `Synthesized audio (${rate / 1000} kHz PCM)` : "Synthesized audio (PCM)",
      metadata: { "Time to first audio": vm.ttfa_ms != null ? fmtDur(vm.ttfa_ms) : "—", ...(voice ? { Voice: voice } : {}), ...(rate ? { "Sample rate": `${rate / 1000} kHz` } : {}) } });
  });
  const convUsage = conversation && conversation.usage;
  const totalTokens = convUsage && convUsage.total_tokens != null ? convUsage.total_tokens : null;
  const root = {
    key: "conv", depth: 0, kind: "conversation", tag: "Conversation", label: conversationId || "conversation",
    durationMs: totalDur || null, tokens: totalTokens,
    input: "voice conversation", output: `${turns.length} turn(s)`,
    metadata: {
      "Conversation id": conversationId || "—",
      Status: (conversation && conversation.status) || "—",
      Turns: String(turns.length),
      ...usageMeta(convUsage),
    },
  };
  return [root, ...nodes];
}

function KindChip({ kind, tag }) {
  return <span className={"mp-chip mp-chip-" + kind}>{tag}</span>;
}

function DetailPanel({ node }) {
  if (!node) return <div className="mp-detail mp-detail-empty">Select a span to see details.</div>;
  return (
    <div className="mp-detail">
      <div className="mp-detail-head">
        <KindChip kind={node.kind} tag={node.tag} />
        <span className="mp-detail-title">{node.label}</span>
      </div>
      <div className="mp-detail-section">
        <div className="mp-detail-label">Input</div>
        <div className="mp-detail-box">{node.input}</div>
      </div>
      <div className="mp-detail-section">
        <div className="mp-detail-label">Output</div>
        <div className="mp-detail-box">{node.output}</div>
      </div>
      <div className="mp-detail-section">
        <div className="mp-detail-label">Metadata</div>
        <div className="mp-meta">
          {Object.entries(node.metadata || {}).map(([k, v]) => (
            <div className="mp-meta-row" key={k}><span className="mp-meta-k">{k}</span><span className="mp-meta-v">{v}</span></div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Trajectories({ nodes }) {
  const [selectedKey, setSelectedKey] = useState(nodes[0] && nodes[0].key);
  const maxDur = Math.max(1, ...nodes.map((n) => n.durationMs || 0));
  const selected = nodes.find((n) => n.key === selectedKey) || nodes[0];
  return (
    <div className="mp-traj">
      <div className="mp-rows">
        {nodes.map((n) => (
          <button
            key={n.key}
            className={"mp-row" + (n.key === selectedKey ? " selected" : "")}
            style={{ paddingLeft: `${0.5 + n.depth * 1.1}rem` }}
            onClick={() => setSelectedKey(n.key)}
          >
            <span className="mp-row-label"><KindChip kind={n.kind} tag={n.tag} />{n.label}</span>
            <span className="mp-row-track">
              <span className={"mp-bar mp-bar-" + n.kind} style={{ width: `${((n.durationMs || 0) / maxDur) * 100}%` }} />
              <span className="mp-row-dur">{fmtDur(n.durationMs)}</span>
              {n.tokens != null ? <span className="mp-row-tok">{n.tokens}t</span> : null}
            </span>
          </button>
        ))}
      </div>
      <DetailPanel node={selected} />
    </div>
  );
}

function UserView({ turns, segAudioUrl }) {
  const [selected, setSelected] = useState(null);
  const bubbles = [];
  turns.forEach((t, i) => {
    if (t.user) bubbles.push({ key: `u${i}`, role: "user", item: t.user });
    if (t.assistant) bubbles.push({ key: `a${i}`, role: "assistant", item: t.assistant });
  });
  const sel = bubbles.find((b) => b.key === selected);
  return (
    <div className="mp-userview">
      <div className="mp-chat">
        {bubbles.length === 0 ? <div className="wrtc-empty">No turns persisted yet.</div> : null}
        {bubbles.map((b) => {
          const text = itemText(b.item);
          const audio = hasAudioPart(b.item);
          const itemId = b.item.id || b.item.item_id;
          return (
            <div key={b.key} className={"mp-bubble-row " + b.role}>
              <button className={"mp-bubble " + b.role + (selected === b.key ? " selected" : "")} onClick={() => setSelected(b.key)}>
                <div className="mp-bubble-role">{b.role === "user" ? "User input" : "Agent"}</div>
                <div className="mp-bubble-text">{text || "\u2014"}</div>
                {audio && itemId && segAudioUrl ? (
                  <audio className="mp-bubble-audio" controls preload="none" src={segAudioUrl(itemId)} />
                ) : null}
              </button>
            </div>
          );
        })}
      </div>
      <div className="mp-detail">
        <div className="mp-detail-label">Metadata</div>
        {sel ? (
          <pre className="mp-json">{JSON.stringify(sel.item, null, 2)}</pre>
        ) : (
          <div className="mp-detail-empty">Select a message to see its metadata.</div>
        )}
      </div>
    </div>
  );
}

export function MiniPortal({ items, conversation, responsesById, conversationId, warn, onRestart, onChooseConversation, wholeAudioUrl, onLoadRecording, segAudioUrl }) {
  const [tab, setTab] = useState("trajectories");
  const turns = useMemo(() => buildTurns(items), [items]);
  const nodes = useMemo(
    () => buildNodes(turns, conversationId, conversation, responsesById),
    [turns, conversationId, conversation, responsesById],
  );
  const root = nodes[0];
  const segments = useMemo(
    () => turns.map((t, i) => ({
      label: `Turn ${i + 1}`,
      role: "turn",
      durationMs: ((t.assistant && (t.assistant.voice_metrics || t.assistant.voiceMetrics)) || {}).duration_ms || null,
    })),
    [turns],
  );

  return (
    <div className="mp">
      <div className="mp-topbar">
        <div className="mp-topbar-left">
          <span className="mp-conv" title={conversationId || ""}>{conversationId || "\u2014"}</span>
          <span className="mp-status">{(conversation && conversation.status) || "completed"}</span>
          {root && root.tokens != null ? <span className="mp-stat">{root.tokens} tokens</span> : null}
          {root && root.durationMs != null ? <span className="mp-stat">{fmtDur(root.durationMs)}</span> : null}
          <span
            className="mp-stat mp-trace"
            title="The distributed trace id (trc-…) lives in Application Insights, not in the persisted conversation. Viewing it needs Log Analytics Reader on the trace store."
          >trace ↗ App Insights</span>
        </div>
        <div className="mp-topbar-right">
          <button onClick={onChooseConversation}>Choose conversation</button>
          <button onClick={onLoadRecording} disabled={!conversationId}>Load recording</button>
          <button className="wrtc-start" onClick={onRestart}>New session</button>
        </div>
      </div>

      {warn ? <div className="wrtc-warn">{warn}</div> : null}
      {wholeAudioUrl ? (
        <div className="wrtc-recording">
          <div className="wrtc-recording-label">Merged recording</div>
          <audio controls preload="none" src={wholeAudioUrl} />
        </div>
      ) : null}

      <div className="mp-tabs">
        <button className={"mp-tab" + (tab === "trajectories" ? " active" : "")} onClick={() => setTab("trajectories")}>Trajectories</button>
        <button className={"mp-tab" + (tab === "userview" ? " active" : "")} onClick={() => setTab("userview")}>User view</button>
      </div>

      {tab === "trajectories" ? <Trajectories nodes={nodes} /> : <UserView turns={turns} segAudioUrl={segAudioUrl} />}

      <PlayerBar segments={segments} wholeAudioUrl={wholeAudioUrl} onLoadRecording={onLoadRecording} />
    </div>
  );
}
