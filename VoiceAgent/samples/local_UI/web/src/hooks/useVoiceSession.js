// Copyright (c) Microsoft. All rights reserved.
// useVoiceSession: React hook that bridges the browser to a voice agent's /voice
// endpoint (relayed by demo_server.py) and speaks the Voice Live realtime protocol.
//
// Mirrors the message + audio handling of the Voice Live React sample
// (chat-interface.tsx): messages are kept as typed entries updated BY ID so streaming
// transcript deltas land in the right bubble; barge-in stops playback on
// input_audio_buffer.speech_started; user-speech transcription arrives via
// conversation.item.input_audio_transcription.{delta,completed}.

import { useCallback, useRef, useState } from "react";
import {
  AudioHandler,
  base64ToUint8,
  shouldRenderPcmOutput,
  uint8ToBase64,
} from "../lib/audio.js";
import { isWebRtcAvatar, toRtcIceServers } from "../lib/avatar.mjs";
import { WEBRTC_DATA_CHANNEL, defaultIceServers, isTerminalRtcError, waitForIceGatheringComplete } from "../lib/webrtcPeer.mjs";
import {
  describeSessionClose,
  insertBeforeMessage,
  shouldDrainSessionAudio,
} from "../lib/chatMessages.mjs";
import { activeHandoffNode, handoffMessage, shouldStartSessionResources } from "../lib/handoff.mjs";
import {
  COMPLETED_FUNCTION_ITEM_EVENTS,
  appendTranscript,
  functionCallFromArgumentsDone,
  functionCallFromItem,
  functionCallsFromResponseDone,
  functionErrorOutput,
  functionOutputItemFrame,
  isClientOwnedFunction,
  mergeFunctionCall,
  parseFunctionArguments,
  resolveFunctionArgumentsRaw,
  responseCreateFrame,
  serializeFunctionOutput,
} from "../lib/clientFunctions.mjs";
import {
  addResponseUsage,
  applyResponseServerTiming,
  canFinalizeAfterToolFailure,
  createTurnTracker,
  describeMcpTool,
  elapsedMetricMs,
  finishToolCall,
  indexSessionTools,
  markFirstAudio,
  markFirstPlayback,
  markFirstSpeech,
  markFirstToken,
  markSpeechStopped,
  markTimeoutTriggered,
  pendingToolCallCount,
  pcmVoiceOffsetsMs,
  shouldFinalizeOnResponseDone,
  snapshotTurnMetrics,
  startAssistantResponse,
  startToolCall,
  updateToolCallDetails,
} from "../lib/turnMetrics.mjs";
import {
  STRUCTURED_INPUT_QUERY_PARAMETER,
  normalizeStructuredInputJson,
} from "../lib/structuredInput.mjs";

let _seq = 0;
const nextLocalId = () => `local-${Date.now()}-${_seq++}`;
const monotonicNow = () => (
  typeof performance !== "undefined" && typeof performance.now === "function"
    ? performance.now()
    : Date.now()
);

// How long a client function may wait for Azure Speech to finish transcribing the turn that
// triggered it. In the cascaded pipeline the transcript always precedes the model's tool call;
// in the realtime pipeline input transcription runs BESIDE the audio-native model, so the call
// can land first. Waiting a moment is the difference between the demo answering from the real
// transcript and answering "no transcript yet".
const TRANSCRIPT_WAIT_MS = 4000;

export function useVoiceSession() {
  const [status, setStatus] = useState({ text: "not connected", kind: "" });
  const [sessionId, setSessionId] = useState(null);
  const [conversationId, setConversationId] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const [sessionReady, setSessionReady] = useState(false);
  const [micMuted, setMicMuted] = useState(false);
  const [messages, setMessages] = useState([]);
  const [verbose, setVerbose] = useState(false);
  /* The raw frame stream, shown beside the chat. The transcript says what was said; this says what
   * the protocol did -- which is the thing you actually debug. Audio frames are dropped (they are
   * base64 PCM arriving every few tens of ms) and the list is capped, so a long call cannot grow
   * without bound in the tab. */
  const [events, setEvents] = useState([]);
  const eventSeq = useRef(0);
  const sessionStartRef = useRef(0);
  const [avatarActive, setAvatarActive] = useState(false);
  const [avatarStatus, setAvatarStatus] = useState("off");
  const [avatarStream, setAvatarStream] = useState(null);
  const [webrtcActive, setWebrtcActive] = useState(false);
  const [webrtcStatus, setWebrtcStatus] = useState("off");
  const [webrtcStream, setWebrtcStream] = useState(null);
  const [activeHandoffNodeId, setActiveHandoffNodeId] = useState(null);
  // The service republishes session.updated after every committed transfer, so this stays the
  // authoritative topology (including implicit nodes and the edges still within budget).
  const [handoffState, setHandoffState] = useState(null);
  const [handoffTrail, setHandoffTrail] = useState([]);
  const [takenEdgeIds, setTakenEdgeIds] = useState([]);

  const wsRef = useRef(null);
  const audioRef = useRef(null);
  const avatarPeerRef = useRef(null);
  const avatarRemoteStreamRef = useRef(null);
  const avatarConnectStartedRef = useRef(false);
  const avatarAudioAvailableRef = useRef(false);
  const transportRef = useRef("websocket");
  const clientReferenceEcRef = useRef(false);
  const referenceAudioModeRef = useRef("assistant");
  const webrtcPeerRef = useRef(null);
  const webrtcRemoteStreamRef = useRef(null);
  const webrtcMicStreamRef = useRef(null);
  const webrtcAudioAvailableRef = useRef(false);
  const webrtcStartedRef = useRef(false);
  const isUserSpeaking = useRef(false);
  const currentAssistantId = useRef(null);
  const turnTrackerRef = useRef(createTurnTracker());
  const sessionToolIndexRef = useRef({});
  const transcriptionTimingRef = useRef(new Map());
  const activeUserItemIdRef = useRef(null);
  const latestInputVoiceAtRef = useRef(null);
  const activeInputVoiceAtRef = useRef(null);
  // Client-executed `function` tools (design §6.1). `clientFunctionsRef` is the name -> handler
  // registry the app installs; the rest is the per-session state needed to answer a call exactly
  // once, from the transcript history the client has actually received.
  const clientFunctionsRef = useRef({});
  const userTranscriptsRef = useRef([]);
  const transcriptWaitersRef = useRef([]);
  const pendingFunctionCallsRef = useRef(new Map());
  const answeredFunctionCallsRef = useRef(new Set());
  // Output items waiting to be sent, how many responses are in flight, and how many client
  // functions are still running. All three gate the single `response.create` that answers a batch.
  const queuedFunctionItemsRef = useRef([]);
  const activeResponseCountRef = useRef(0);
  const runningFunctionCountRef = useRef(0);
  const verboseRef = useRef(false);
  const sessionReadyRef = useRef(false);
  const clientCloseRequestedRef = useRef(false);
  verboseRef.current = verbose;

  // ---- message helpers (setMessages by id, like the sample's setMessages) ----
  /* Messages carry the same clock as protocol frames. The transcript and the event stream are read
   * as one timeline -- "which frames happened before I said this" -- and that question needs a
   * shared origin, not two independently ordered lists. */
  const relativeAt = useCallback(() => {
    if (!sessionStartRef.current) sessionStartRef.current = performance.now();
    return (performance.now() - sessionStartRef.current) / 1000;
  }, []);

  const addMessage = useCallback((msg) => {
    const id = msg.id || nextLocalId();
    setMessages((prev) => [...prev, { id, at: relativeAt(), ...msg }]);
    return id;
  }, [relativeAt]);

  const upsertById = useCallback((id, type, updater, metricsPatch = null) => {
    setMessages((prev) => {
      const idx = prev.findIndex((m) => m.id === id);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = {
          ...next[idx],
          content: updater(next[idx].content || ""),
          ...(metricsPatch ? { metrics: { ...(next[idx].metrics || {}), ...metricsPatch } } : {}),
        };
        return next;
      }
      return [...prev, {
        id,
        type,
        at: relativeAt(),
        content: updater(""),
        ...(metricsPatch ? { metrics: metricsPatch } : {}),
      }];
    });
  }, [relativeAt]);

  const beginTurn = useCallback((startedAtMs = monotonicNow(), startSource = "server_vad") => {
    turnTrackerRef.current = createTurnTracker(startedAtMs, startSource);
    currentAssistantId.current = null;
  }, []);

  const attachTurnMetrics = useCallback(() => {
    const turn = turnTrackerRef.current;
    const assistantId = turn.assistantId || currentAssistantId.current;
    if (assistantId) {
      const metrics = { ...snapshotTurnMetrics(turn), complete: true };
      setMessages((prev) => prev.map((message) => (
        message.id === assistantId && message.type === "assistant"
          ? { ...message, metrics: { ...(message.metrics || {}), ...metrics } }
          : message
      )));
    }
    turnTrackerRef.current = createTurnTracker();
    currentAssistantId.current = null;
  }, []);

  // ---- MCP tool helpers (design §6): surface tool listing, calls, and approval in the chat ----
  const asText = (v) => (v == null ? undefined : typeof v === "string" ? v : JSON.stringify(v));

  // Add/refresh an `mcp_call` bubble keyed by the call item id, merging in any new fields.
  const upsertMcpCall = useCallback((id, patch) => {
    const assistantId = turnTrackerRef.current.assistantId;
    setMessages((prev) => {
      const idx = prev.findIndex((m) => m.id === id && m.type === "mcp_call");
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = { ...next[idx], mcpCall: { ...(next[idx].mcpCall || {}), ...patch } };
        return next;
      }
      const message = { id, at: relativeAt(), type: "mcp_call", mcpCall: { status: "in_progress", ...patch } };
      return insertBeforeMessage(prev, message, assistantId);
    });
  }, [relativeAt]);

  // Add an `mcp_approval` bubble (deduped by approval-request item id) with Approve/Reject pending.
  const addApproval = useCallback((item) => {
    const id = item.id || nextLocalId();
    const assistantId = turnTrackerRef.current.assistantId;
    setMessages((prev) => {
      if (prev.some((m) => m.id === id)) return prev;
      const message = {
        id,
        at: relativeAt(),
        type: "mcp_approval",
        mcpApproval: {
          approvalRequestId: item.id || id,
          serverLabel: item.server_label || item.serverLabel || "",
          name: item.name || "",
          arguments: asText(item.arguments) || "{}",
          handled: false,
        },
      };
      return insertBeforeMessage(prev, message, assistantId);
    });
  }, []);

  // Route an item (from preview or stable conversation/response item events) to the right bubble.
  const handleMcpItem = useCallback((item) => {
    if (!item || !item.type) return;
    if (item.type === "mcp_approval_request") {
      addApproval(item);
    } else if (item.type === "mcp_call") {
      const itemId = item.id || nextLocalId();
      updateToolCallDetails(
        turnTrackerRef.current,
        itemId,
        describeMcpTool(item, sessionToolIndexRef.current),
      );
      const patch = { serverLabel: item.server_label || "", name: item.name || "", arguments: asText(item.arguments) };
      if (item.output != null) { patch.status = "completed"; patch.output = asText(item.output); }
      if (item.error != null) { patch.status = "failed"; patch.error = asText(item.error); }
      upsertMcpCall(itemId, patch);
    }
  }, [addApproval, upsertMcpCall]);

  // Patch an existing `mcp_call` bubble by item id (for the response.mcp_call.* status events).
  const patchMcpCall = useCallback((itemId, patch) => {
    if (!itemId) return;
    upsertMcpCall(itemId, patch);
  }, [upsertMcpCall]);

  /* A handoff is not a frame the service emits -- it is state the page derives from
   * session.handoff.* events. It belongs beside the frames that explain it, not in the transcript,
   * which is why it lands in the event stream. Upserted by handoff id so started -> completed
   * updates one row instead of stacking two. */
  const upsertHandoff = useCallback((event) => {
    const message = handoffMessage(event);
    if (!message) return;
    if (!sessionStartRef.current) sessionStartRef.current = performance.now();
    const at = (performance.now() - sessionStartRef.current) / 1000;
    setEvents((previous) => {
      const index = previous.findIndex((item) => item.handoffId === message.id);
      const entry = {
        id: index < 0 ? (eventSeq.current += 1) : previous[index].id,
        at: index < 0 ? at : previous[index].at,
        kind: "handoff",
        handoffId: message.id,
        handoff: message.handoff,
      };
      if (index < 0) return [...previous, entry];
      const next = [...previous];
      next[index] = entry;
      return next;
    });
  }, []);

  // Keep the original main-timeline status labels. Protocol frames are a separate Developer mode
  // surface; these concise yellow labels remain the operator-facing session narrative.
  const logStatus = useCallback((text) => addMessage({ type: "status", content: text }), [addMessage]);
  const logError = useCallback((text) => addMessage({ type: "error", content: text }), [addMessage]);
  // Every Voice Live frame is already captured structurally by recordFrame. The old bare event-name
  // bubbles duplicated that stream without offering the expandable payload.
  const logEvent = useCallback(() => {}, []);

  const MAX_EVENTS = 4000;
  const AUDIO_FRAME = /(audio\.delta|audio_buffer\.append|audio\.done)$/;
  // Token-level deltas are dropped at the source: they were over half the stream and their `.done`
  // twin carries the assembled content, so keeping them only buried the frames that decide behaviour.
  const DELTA_FRAME = /\.delta$/;

  const recordFrame = useCallback((dir, frame) => {
    const type = String(frame?.type || "");
    if (!type || AUDIO_FRAME.test(type) || DELTA_FRAME.test(type)) return;
    if (!sessionStartRef.current) sessionStartRef.current = performance.now();
    const at = (performance.now() - sessionStartRef.current) / 1000;
    setEvents((current) => {
      const next = current.length >= MAX_EVENTS ? current.slice(current.length - MAX_EVENTS + 1) : current.slice();
      next.push({ id: (eventSeq.current += 1), at, dir, type, frame });
      return next;
    });
  }, []);

  /* A turn boundary in the same stream as the frames. Reading "which events happened because of
   * what I just said" is the whole point of showing them beside the transcript, and that question
   * is unanswerable in a flat list of protocol types. */
  const markTurn = useCallback((speaker, text) => {
    if (!sessionStartRef.current) sessionStartRef.current = performance.now();
    const at = (performance.now() - sessionStartRef.current) / 1000;
    setEvents((current) => {
      const next = current.length >= MAX_EVENTS ? current.slice(current.length - MAX_EVENTS + 1) : current.slice();
      next.push({ id: (eventSeq.current += 1), at, kind: "turn", speaker, text: String(text || "").slice(0, 90) });
      return next;
    });
  }, []);

  const clearEvents = useCallback(() => { setEvents([]); eventSeq.current = 0; }, []);
  // Announce the Agents service API the portal is calling in the original yellow status labels.
  const logApi = useCallback(
    (method, path) => addMessage({ type: "status", content: `\u2192 API ${method} ${path}` }),
    [addMessage],
  );
  const clearMessages = useCallback(() => setMessages([]), []);

  // ---- client-executed function tools (design §6.1) ----
  // Voice Live declares a `function` tool to the model but does NOT run it: it forwards the
  // `function_call` here and relays whatever `function_call_output` this client sends back. The
  // app installs handlers with setClientFunctions; a call for an unregistered name is answered
  // with an error output rather than left hanging, which would stall the conversation.
  const setClientFunctions = useCallback((functions) => {
    clientFunctionsRef.current = functions || {};
  }, []);

  const resetClientFunctionState = useCallback(() => {
    userTranscriptsRef.current = [];
    for (const waiter of transcriptWaitersRef.current) waiter.resolve(null);
    transcriptWaitersRef.current = [];
    pendingFunctionCallsRef.current = new Map();
    answeredFunctionCallsRef.current = new Set();
    queuedFunctionItemsRef.current = [];
    activeResponseCountRef.current = 0;
    runningFunctionCountRef.current = 0;
  }, []);

  // Every completed user turn, from the SPEECH RECOGNIZER rather than the model: this is the
  // accurate reading a client function hands back when the model mishears digits.
  const recordUserTranscript = useCallback((transcript, source) => {
    const text = String(transcript || "").trim();
    if (!text) return;
    const entry = { transcript: text, source, atMs: monotonicNow() };
    userTranscriptsRef.current = appendTranscript(userTranscriptsRef.current, entry);
    const waiters = transcriptWaitersRef.current;
    transcriptWaitersRef.current = [];
    for (const waiter of waiters) waiter.resolve(entry);
  }, []);

  // Resolve as soon as a user transcript newer than `sinceMs` exists — immediately when the
  // recognizer already won the race, otherwise on the next completed transcription.
  const waitForUserTranscript = useCallback((sinceMs, timeoutMs = TRANSCRIPT_WAIT_MS) => {
    const history = userTranscriptsRef.current;
    const newest = history[history.length - 1];
    if (newest && (!Number.isFinite(sinceMs) || newest.atMs >= sinceMs)) {
      return Promise.resolve(newest);
    }
    return new Promise((resolve) => {
      const waiter = { resolve: (value) => { clearTimeout(timer); resolve(value); } };
      const timer = setTimeout(() => {
        transcriptWaitersRef.current = transcriptWaitersRef.current.filter((x) => x !== waiter);
        resolve(null);
      }, timeoutMs);
      transcriptWaitersRef.current = [...transcriptWaitersRef.current, waiter];
    });
  }, []);

  // Add/refresh a `function_call` bubble so the demo shows the arguments the model sent and the
  // output the browser returned — the visible proof that the client, not the service, answered.
  const upsertFunctionCall = useCallback((id, patch) => {
    const assistantId = turnTrackerRef.current.assistantId;
    setMessages((prev) => {
      const idx = prev.findIndex((m) => m.id === id && m.type === "function_call");
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = { ...next[idx], functionCall: { ...(next[idx].functionCall || {}), ...patch } };
        return next;
      }
      const message = {
        id,
        at: relativeAt(),
        type: "function_call",
        functionCall: { status: "in_progress", ...patch },
      };
      return insertBeforeMessage(prev, message, assistantId);
    });
  }, [relativeAt]);

  // Send the answers to a batch of client function calls: every output item, then exactly ONE
  // `response.create`. Three conditions must hold first, or the follow-up answer is lost:
  //   * no client function still running — otherwise its output lands after the response starts;
  //   * no response in flight — a `response.create` during one is refused as
  //     `conversation_already_has_active_response`;
  //   * something to send.
  // Unlike an MCP tool, which Voice Live executes and schedules the answer for itself, a client
  // function is answered by this peer, so this peer also requests the response.
  const flushFunctionOutputs = useCallback(() => {
    if (runningFunctionCountRef.current > 0) return;
    if (activeResponseCountRef.current > 0) return;
    const items = queuedFunctionItemsRef.current;
    if (!items.length) return;
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      queuedFunctionItemsRef.current = [];
      logError("client function output could not be sent: the session is closed");
      return;
    }
    queuedFunctionItemsRef.current = [];
    for (const frame of items) ws.send(JSON.stringify(frame));
    ws.send(JSON.stringify(responseCreateFrame()));
    setStatus({ text: "thinking...", kind: "warn" });
  }, [logError]);

  const runClientFunction = useCallback(async (call) => {
    const callId = call && call.callId;
    if (!callId || answeredFunctionCallsRef.current.has(callId)) return;
    answeredFunctionCallsRef.current.add(callId);
    pendingFunctionCallsRef.current.delete(callId);
    runningFunctionCountRef.current += 1;

    const bubbleId = call.itemId || `function-${callId}`;
    const name = call.name || "";
    const argumentsRaw = resolveFunctionArgumentsRaw(call);
    const startedAtMs = monotonicNow();
    // Anchor the transcript wait to when THIS user turn began, not to when the call started
    // running: in the cascaded pipeline the recognizer finishes first, and waiting for something
    // newer than the call itself would stall on a transcript that is already in hand.
    const turnStartedAtMs = turnTrackerRef.current.startedAtMs;
    startToolCall(
      turnTrackerRef.current,
      bubbleId,
      startedAtMs,
      { kind: "Function", name, serverLabel: "client" },
      true,
    );
    upsertFunctionCall(bubbleId, {
      name,
      callId,
      arguments: argumentsRaw || "{}",
      status: "in_progress",
    });
    setStatus({ text: "running client function...", kind: "warn" });

    const args = parseFunctionArguments(argumentsRaw);
    let outputText = "";
    let status = "completed";
    let errorText = "";
    try {
      const handler = clientFunctionsRef.current[name];
      if (typeof handler !== "function") {
        throw new Error(`no client handler is registered for function '${name}'`);
      }
      const result = await handler(args, {
        callId,
        name,
        turnStartedAtMs,
        recentUserTranscripts: () => [...userTranscriptsRef.current],
        waitForUserTranscript: (timeoutMs) => waitForUserTranscript(turnStartedAtMs, timeoutMs),
      });
      outputText = serializeFunctionOutput(result);
    } catch (error) {
      status = "failed";
      errorText = error instanceof Error ? error.message : String(error);
      outputText = serializeFunctionOutput(functionErrorOutput(name, error));
      logError(`client function ${name || "(unnamed)"} failed: ${errorText}`);
    }

    const tool = finishToolCall(
      turnTrackerRef.current,
      bubbleId,
      monotonicNow(),
      status,
      { kind: "Function", name },
    );
    upsertFunctionCall(bubbleId, {
      status,
      output: outputText,
      ...(errorText ? { error: errorText } : {}),
      ...(tool && tool.durationMs != null ? { durationMs: Math.round(tool.durationMs) } : {}),
    });

    // Every call is answered, even a failed one — an outstanding `function_call` would leave the
    // conversation waiting forever. Sending is deferred to the flush below.
    queuedFunctionItemsRef.current = [
      ...queuedFunctionItemsRef.current,
      functionOutputItemFrame(callId, outputText),
    ];
    runningFunctionCountRef.current = Math.max(0, runningFunctionCountRef.current - 1);
    flushFunctionOutputs();
  }, [flushFunctionOutputs, logError, upsertFunctionCall, waitForUserTranscript]);

  // A call is described across several events (`response.output_item.added`, the argument deltas,
  // `response.function_call_arguments.done`, `response.output_item.done`). Merge whatever arrives
  // and run it as soon as it has both a call_id and a name.
  const noteFunctionCall = useCallback((patch) => {
    if (!patch) return;
    const key = patch.callId || patch.itemId;
    if (!key || (patch.callId && answeredFunctionCallsRef.current.has(patch.callId))) return;
    const merged = mergeFunctionCall(pendingFunctionCallsRef.current.get(key), patch);
    pendingFunctionCallsRef.current.set(key, merged);
    // Wait for the event that carries the finished arguments: the model streams them, so an
    // item announced up front would otherwise be executed with an empty argument object.
    if (!(merged.callId && merged.name && merged.complete)) return;
    // Server-owned system tools (end_conversation) arrive as `function_call` items too, but the
    // SERVICE executes them and closes the session itself. Answering one would push a bogus
    // output into a terminating conversation and show a failed call for a feature that worked.
    if (!isClientOwnedFunction(merged.name, clientFunctionsRef.current)) {
      pendingFunctionCallsRef.current.delete(key);
      logEvent(`function_call ${merged.name} is server-owned; not answered by this client`);
      return;
    }
    runClientFunction(merged);
  }, [logEvent, runClientFunction]);

  const ensureAudio = () => {
    if (!audioRef.current) {
      audioRef.current = new AudioHandler(undefined, {
        clientReferenceEc: clientReferenceEcRef.current,
        referenceAudioMode: referenceAudioModeRef.current,
      });
    }
    return audioRef.current;
  };

  const startMic = useCallback(async () => {
    const audio = ensureAudio();
    try {
      await audio.startRecording((bytes) => {
        const receivedAtMs = monotonicNow();
        const channels = clientReferenceEcRef.current ? 2 : 1;
        const voice = pcmVoiceOffsetsMs(bytes, { channels });
        if (voice.lastVoicedMs != null) {
          const lastVoicedAtMs = receivedAtMs - voice.durationMs + voice.lastVoicedMs;
          latestInputVoiceAtRef.current = lastVoicedAtMs;
          if (isUserSpeaking.current) activeInputVoiceAtRef.current = lastVoicedAtMs;
        }
        const ws = wsRef.current;
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "input_audio_buffer.append", audio: uint8ToBase64(bytes) }));
        }
      });
      audio.setMuted(false);
      setMicMuted(false);
      setStatus({ text: "listening (server VAD)", kind: "ok" });
    } catch (err) {
      logError("getUserMedia failed: " + err);
      setStatus({ text: "microphone error", kind: "err" });
    }
  }, [logError]);

  const cleanupAvatar = useCallback(() => {
    const peer = avatarPeerRef.current;
    if (peer) {
      peer.ontrack = null;
      peer.onconnectionstatechange = null;
      try { peer.close(); } catch { /* noop */ }
    }
    const stream = avatarRemoteStreamRef.current;
    if (stream) stream.getTracks().forEach((track) => track.stop());
    avatarPeerRef.current = null;
    avatarRemoteStreamRef.current = null;
    avatarConnectStartedRef.current = false;
    avatarAudioAvailableRef.current = false;
    setAvatarStream(null);
    setAvatarActive(false);
    setAvatarStatus("off");
  }, []);

  const startAvatarConnection = useCallback(async (avatar) => {
    if (!isWebRtcAvatar(avatar) || avatarConnectStartedRef.current) return;
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    if (typeof RTCPeerConnection === "undefined" || typeof MediaStream === "undefined") {
      logError("This browser does not support WebRTC avatar playback.");
      setAvatarStatus("unsupported");
      return;
    }

    cleanupAvatar();
    avatarConnectStartedRef.current = true;
    setAvatarActive(true);
    setAvatarStatus("negotiating");

    try {
      const peer = new RTCPeerConnection({ iceServers: toRtcIceServers(avatar) });
      const remoteStream = new MediaStream();
      avatarPeerRef.current = peer;
      avatarRemoteStreamRef.current = remoteStream;

      peer.ontrack = (event) => {
        if (!remoteStream.getTracks().some((track) => track.id === event.track.id)) {
          remoteStream.addTrack(event.track);
        }
        if (event.track.kind === "audio") {
          avatarAudioAvailableRef.current = true;
          if (audioRef.current) audioRef.current.stopStreamingPlayback();
        }
        setAvatarStream(new MediaStream(remoteStream.getTracks()));
      };
      peer.onconnectionstatechange = () => {
        if (peer.connectionState === "connected") {
          setAvatarStatus("idle");
          logStatus("Avatar WebRTC connected");
        } else if (peer.connectionState === "failed") {
          setAvatarStatus("failed");
          logError("Avatar WebRTC connection failed.");
        } else if (peer.connectionState === "disconnected") {
          setAvatarStatus("disconnected");
        }
      };

      // Match the Voice Live React sample: request both remote tracks and create the event channel
      // before generating the SDP offer.
      peer.addTransceiver("video", { direction: "sendrecv" });
      peer.addTransceiver("audio", { direction: "sendrecv" });
      const eventChannel = peer.createDataChannel("eventChannel");
      eventChannel.onmessage = (event) => logEvent(`avatar data channel: ${event.data}`);

      const offer = await peer.createOffer();
      await peer.setLocalDescription(offer);
      await waitForIceGatheringComplete(peer);
      if (!peer.localDescription) throw new Error("WebRTC local description was not created");

      ws.send(JSON.stringify({
        type: "session.avatar.connect",
        client_sdp: btoa(JSON.stringify(peer.localDescription)),
      }));
      logStatus("Avatar WebRTC offer sent");
    } catch (error) {
      setAvatarStatus("failed");
      logError("Error establishing avatar connection: " + error);
    }
  }, [cleanupAvatar, logError, logEvent, logStatus]);

  const applyAvatarAnswer = useCallback(async (serverSdp) => {
    const peer = avatarPeerRef.current;
    if (!peer || !serverSdp) return;
    try {
      const description = JSON.parse(atob(serverSdp));
      await peer.setRemoteDescription(description);
      setAvatarStatus("connecting");
      logStatus("Avatar WebRTC answer applied");
    } catch (error) {
      setAvatarStatus("failed");
      logError("Invalid avatar WebRTC answer: " + error);
    }
  }, [logError, logStatus]);

  // ---- WebRTC media transport (design features/webrtc_voice_first_agent_demo/design.md) ----
  // The browser peers directly with Voice Live: mic + agent audio ride RTP and the voice-live-events
  // data channel is peer-to-peer; only the rtc.call.sdp.* signaling crosses the bridged control WS.
  const cleanupWebRtc = useCallback(() => {
    const peer = webrtcPeerRef.current;
    if (peer) {
      peer.ontrack = null;
      peer.onconnectionstatechange = null;
      try { peer.close(); } catch { /* noop */ }
    }
    const remote = webrtcRemoteStreamRef.current;
    if (remote) remote.getTracks().forEach((track) => track.stop());
    const mic = webrtcMicStreamRef.current;
    if (mic) mic.getTracks().forEach((track) => track.stop());
    webrtcPeerRef.current = null;
    webrtcRemoteStreamRef.current = null;
    webrtcMicStreamRef.current = null;
    webrtcStartedRef.current = false;
    webrtcAudioAvailableRef.current = false;
    setWebrtcStream(null);
    setWebrtcActive(false);
    setWebrtcStatus("off");
  }, []);

  const startWebRtcSession = useCallback(async () => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN || webrtcStartedRef.current) return;
    if (typeof RTCPeerConnection === "undefined" || typeof MediaStream === "undefined") {
      logError("This browser does not support WebRTC.");
      setWebrtcStatus("unsupported");
      return;
    }
    cleanupWebRtc();
    webrtcStartedRef.current = true;
    setWebrtcActive(true);
    setWebrtcStatus("negotiating");
    try {
      const peer = new RTCPeerConnection({ iceServers: defaultIceServers() });
      const remoteStream = new MediaStream();
      webrtcPeerRef.current = peer;
      webrtcRemoteStreamRef.current = remoteStream;

      peer.ontrack = (event) => {
        if (!remoteStream.getTracks().some((track) => track.id === event.track.id)) {
          remoteStream.addTrack(event.track);
        }
        if (event.track.kind === "audio") {
          webrtcAudioAvailableRef.current = true;
          if (audioRef.current) audioRef.current.stopStreamingPlayback();
        }
        setWebrtcStream(new MediaStream(remoteStream.getTracks()));
      };
      peer.onconnectionstatechange = () => {
        const state = peer.connectionState;
        if (state === "connected") { setWebrtcStatus("connected"); logStatus("WebRTC media connected"); }
        else if (state === "failed") { setWebrtcStatus("failed"); logError("WebRTC connection failed. Switch to the WebSocket transport to retry."); }
        else if (state === "disconnected") setWebrtcStatus("disconnected");
      };

      // Mic -> RTP (replaces the PCM-over-WS uplink for this transport).
      const micStream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
      });
      webrtcMicStreamRef.current = micStream;
      micStream.getTracks().forEach((track) => peer.addTrack(track, micStream));

      // The data channel must exist BEFORE createOffer so m=application is negotiated. It is
      // observational only in the demo; the control WS stays the source of truth for events.
      const dataChannel = peer.createDataChannel(WEBRTC_DATA_CHANNEL);
      dataChannel.onmessage = (event) => logEvent(`webrtc data channel: ${event.data}`);

      const offer = await peer.createOffer();
      await peer.setLocalDescription(offer);
      await waitForIceGatheringComplete(peer);
      if (!peer.localDescription) throw new Error("WebRTC local description was not created");

      ws.send(JSON.stringify({ type: "rtc.call.sdp.create", sdp_offer: peer.localDescription.sdp }));
      logStatus("WebRTC offer sent (rtc.call.sdp.create)");
    } catch (error) {
      webrtcStartedRef.current = false;
      // Negotiation failed after getUserMedia — tear down the peer + stop the captured mic tracks.
      cleanupWebRtc();
      setWebrtcStatus("failed");
      logError("Error establishing WebRTC session: " + error);
    }
  }, [cleanupWebRtc, logError, logEvent, logStatus]);

  const applyWebRtcAnswer = useCallback(async (sdpAnswer) => {
    const peer = webrtcPeerRef.current;
    if (!peer || !sdpAnswer) return;
    try {
      await peer.setRemoteDescription({ type: "answer", sdp: sdpAnswer });
      setWebrtcStatus("connecting");
      logStatus("WebRTC answer applied (rtc.call.sdp.created)");
    } catch (error) {
      setWebrtcStatus("failed");
      logError("Invalid WebRTC answer: " + error);
    }
  }, [logError, logStatus]);

  const handleEvent = useCallback((evt) => {
    const t = evt.type || "(none)";
    // Capture OUR conversation id from any event that carries it (conversation.created is canonical,
    // but keep this robust across transports where its delivery to the client isn't guaranteed). The
    // first-seen id lets "View persisted" reference THIS session, not the shared agent's latest.
    const anyConversationId = evt.conversation_id || (evt.conversation && evt.conversation.id);
    if (anyConversationId) setConversationId((prev) => prev || anyConversationId);
    switch (t) {
      case "session.created": {
        const sid = evt.session && evt.session.id;
        if (sid) setSessionId(sid);
        logStatus(`session.created${sid ? ` \u2014 session id: ${sid}` : ""}`);
        break;
      }
      case "session.updated": {
        const isInitialSessionUpdate = shouldStartSessionResources(sessionReadyRef.current);
        sessionReadyRef.current = true;
        const sid = evt.session && evt.session.id;
        if (sid) setSessionId(sid);
        sessionToolIndexRef.current = indexSessionTools((evt.session && evt.session.tools) || []);
        const activeNode = activeHandoffNode(evt.session);
        setHandoffState((evt.session && evt.session.handoff) || null);
        setActiveHandoffNodeId(activeNode);
        if (activeNode) logStatus(`Active handoff node: ${activeNode}`);
        setSessionReady(true);
        setStatus({ text: "ready - listening", kind: "ok" });
        if (clientReferenceEcRef.current) {
          const echoCancellation = evt.session?.audio?.input?.echo_cancellation
            || evt.session?.input_audio_echo_cancellation;
          if (echoCancellation?.reference_source === "client" && echoCancellation?.channels === 2) {
            logStatus("Live-reference echo cancellation active (stereo PCM16)");
          } else {
            logError("Live-reference echo cancellation was requested but is not active in session.updated");
          }
        }
        // Avatar is out of scope for the WebRTC media transport (separate WebRTC implementation),
        // so only negotiate the avatar on the WebSocket transport.
        const avatar = evt.session && evt.session.avatar;
        if (isWebRtcAvatar(avatar) && transportRef.current !== "webrtc") {
          setAvatarActive(true);
          setAvatarStatus("negotiating");
          startAvatarConnection(avatar);
        }
        // A Foundry Toolbox is declared as a single `foundry_toolbox` tool that Voice Live executes
        // in-service (no `mcp_list_tools.*` event is surfaced, unlike a native `mcp` tool). Announce it
        // here from the session's tool list so the toolbox is visible in the log the same way MCP tools
        // are. The individual toolbox tools (web/file search, …) are resolved server-side, so only the
        // toolbox label (and any `allowed_tools` allowlist) is available client-side.
        const toolboxes = ((evt.session && evt.session.tools) || []).filter((x) => x && x.type === "foundry_toolbox");
        for (const tb of toolboxes) {
          const label = tb.server_label || "toolbox";
          const allowed = Array.isArray(tb.allowed_tools) && tb.allowed_tools.length ? `: ${tb.allowed_tools.join(", ")}` : "";
          logStatus(`Foundry Toolbox available \u2014 ${label}${allowed}`);
        }
        if (isInitialSessionUpdate && transportRef.current !== "webrtc") {
          startMic(); // auto-start mic once (PCM-over-WS); WebRTC carries the mic on the peer instead
        }
        break;
      }
      case "session.handoff.started":
        upsertHandoff(evt);
        setStatus({ text: "handoff in progress...", kind: "warn" });
        break;
      case "session.handoff.completed":
        upsertHandoff(evt);
        setActiveHandoffNodeId(evt.to_node_id || null);
        setTakenEdgeIds((previous) => (
          evt.edge_id && !previous.includes(evt.edge_id) ? [...previous, evt.edge_id] : previous
        ));
        setHandoffTrail((previous) => [...previous, {
          nodeId: evt.to_node_id || "",
          edgeId: evt.edge_id || "",
          at: Date.now(),
        }]);
        setStatus({ text: `active: ${evt.to_node_id || "handoff target"}`, kind: "ok" });
        break;
      case "session.handoff.aborted":
        upsertHandoff(evt);
        setActiveHandoffNodeId(evt.from_node_id || null);
        setStatus({ text: `handoff aborted: ${evt.reason || "error"}`, kind: "err" });
        break;
      case "session.avatar.connecting":
        applyAvatarAnswer(evt.server_sdp || evt.serverSdp);
        break;
      case "session.avatar.switch_to_speaking":
        setAvatarStatus("speaking");
        logEvent("session.avatar.switch_to_speaking");
        break;
      case "session.avatar.switch_to_idle":
        setAvatarStatus("idle");
        logEvent("session.avatar.switch_to_idle");
        break;
      case "rtc.call.sdp.created":
        applyWebRtcAnswer(evt.sdp_answer || evt.sdpAnswer);
        break;
      case "rtc.call.error": {
        const rtcErr = evt.error || {};
        const rtcCode = rtcErr.code || rtcErr.type || "";
        if (isTerminalRtcError(rtcCode)) {
          // Terminal (design §4.4): the call is dead — tear down the peer; a fresh connect is needed.
          logError("WebRTC error (terminal): " + JSON.stringify(rtcErr));
          setStatus({ text: "webrtc error: " + (rtcErr.message || rtcCode || "see log"), kind: "err" });
          cleanupWebRtc();
        } else {
          // Recoverable: keep the control WS + peer open; surface a warning only.
          logError("WebRTC error (recoverable): " + JSON.stringify(rtcErr));
          setWebrtcStatus("error");
        }
        break;
      }
      case "conversation.created": {
        // The voice orchestrator auto-creates the conversation and is its sole writer (design §4.4);
        // it surfaces the id here so the client can read the persisted turns back.
        if (evt.conversation_id) {
          setConversationId(evt.conversation_id);
          logStatus(`conversation.created \u2014 server is persisting this session: ${evt.conversation_id}`);
        }
        break;
      }
      case "input_audio_buffer.speech_started": {
        // Barge-in: user started talking -> stop agent playback immediately.
        const now = monotonicNow();
        const userItemId = evt.item_id || null;
        isUserSpeaking.current = true;
        activeUserItemIdRef.current = userItemId;
        activeInputVoiceAtRef.current = (
          latestInputVoiceAtRef.current != null && now - latestInputVoiceAtRef.current <= 1500
            ? latestInputVoiceAtRef.current
            : null
        );
        if (userItemId) {
          transcriptionTimingRef.current.set(userItemId, {
            speechStartedAtMs: now,
            speechStoppedAtMs: null,
          });
        }
        ensureAudio().stopStreamingPlayback();
        setStatus({ text: "listening...", kind: "ok" });
        logEvent("input_audio_buffer.speech_started (barge-in)");
        if (userItemId) upsertById(userItemId, "user", () => "\u2026");
        break;
      }
      case "input_audio_buffer.speech_stopped": {
        const now = monotonicNow();
        const userItemId = evt.item_id || activeUserItemIdRef.current;
        if (userItemId) {
          const timing = transcriptionTimingRef.current.get(userItemId) || {};
          transcriptionTimingRef.current.set(userItemId, {
            ...timing,
            speechStoppedAtMs: now,
          });
        }
        isUserSpeaking.current = false;
        const lastVoicedAtMs = activeInputVoiceAtRef.current;
        const hasRecentVoice = lastVoicedAtMs != null && now - lastVoicedAtMs <= 10000;
        beginTurn(
          hasRecentVoice ? lastVoicedAtMs : now,
          hasRecentVoice ? "user_last_voiced" : "server_vad",
        );
        markSpeechStopped(turnTrackerRef.current, userItemId, now);
        activeInputVoiceAtRef.current = null;
        setStatus({ text: "thinking...", kind: "warn" });
        logEvent("input_audio_buffer.speech_stopped");
        break;
      }
      case "input_audio_buffer.timeout_triggered": {
        const now = monotonicNow();
        const timeoutWindowMs = (
          Number.isFinite(evt.audio_start_ms)
          && Number.isFinite(evt.audio_end_ms)
          && evt.audio_end_ms >= evt.audio_start_ms
        )
          ? evt.audio_end_ms - evt.audio_start_ms
          : 0;
        beginTurn(now - timeoutWindowMs, "idle_timeout");
        markTimeoutTriggered(
          turnTrackerRef.current,
          evt.item_id || null,
          now,
          evt.audio_start_ms,
          evt.audio_end_ms,
        );
        setStatus({ text: "idle timeout - responding...", kind: "warn" });
        logEvent(`input_audio_buffer.timeout_triggered (${Math.round(timeoutWindowMs)} ms silence)`);
        break;
      }
      case "conversation.item.input_audio_transcription.delta":
        if (evt.delta && evt.item_id) {
          upsertById(evt.item_id, "user", (c) => (c === "\u2026" ? "" : c) + evt.delta);
        }
        break;
      case "conversation.item.input_audio_transcription.completed":
        markTurn("user", evt.transcript || "");
        if (evt.item_id) {
          const timing = transcriptionTimingRef.current.get(evt.item_id);
          const sttStart = timing && (
            timing.speechStartedAtMs != null
              ? timing.speechStartedAtMs
              : timing.speechStoppedAtMs
          );
          const sttMs = elapsedMetricMs(sttStart, monotonicNow());
          upsertById(
            evt.item_id,
            "user",
            () => evt.transcript || "",
            sttMs != null ? { sttMs } : null,
          );
          // The recognizer's reading of this turn, kept for client functions to hand back. In a
          // realtime session a function call for the same turn may already be waiting on it.
          recordUserTranscript(evt.transcript, "azure-speech (client-side input transcription)");
          transcriptionTimingRef.current.delete(evt.item_id);
          if (activeUserItemIdRef.current === evt.item_id) activeUserItemIdRef.current = null;
        }
        break;
      case "response.created":
        activeResponseCountRef.current += 1;
        currentAssistantId.current = startAssistantResponse(
          turnTrackerRef.current,
          (evt.response && evt.response.id) || nextLocalId(),
          monotonicNow(),
        );
        // Do not insert the response bubble yet. A tool-only response emits its tool item first;
        // creating the bubble lazily on first text/audio keeps the visible order tool -> answer.
        // Tool follow-up responses still reuse this one per-turn assistant id.
        logEvent("response.created");
        break;
      case "response.server_timing": {
        if (applyResponseServerTiming(turnTrackerRef.current, evt)) {
          const assistantId = turnTrackerRef.current.assistantId || currentAssistantId.current;
          const metrics = snapshotTurnMetrics(turnTrackerRef.current);
          if (assistantId) {
            setMessages((prev) => prev.map((message) => (
              message.id === assistantId && message.type === "assistant"
                ? { ...message, metrics: { ...(message.metrics || {}), ...metrics } }
                : message
            )));
          }
          logEvent("response.server_timing");
        } else {
          logError("Ignored uncorrelated response.server_timing event");
        }
        break;
      }
      case "response.audio_transcript.delta":
      case "response.output_audio_transcript.delta":
      case "response.text.delta":
      case "response.output_text.delta":
        if (evt.delta && currentAssistantId.current) {
          const first = markFirstToken(turnTrackerRef.current, monotonicNow());
          const metrics = first ? snapshotTurnMetrics(turnTrackerRef.current) : null;
          upsertById(
            currentAssistantId.current,
            "assistant",
            (c) => c + evt.delta,
            first ? { ttftMs: metrics.ttftMs } : null,
          );
        }
        break;
      case "response.audio_transcript.done":
      case "response.output_audio_transcript.done":
      case "response.text.done":
      case "response.output_text.done": {
        const text = evt.transcript || evt.text || "";
        if (text && currentAssistantId.current) {
          // The terminal event repeats the completed transcript. Count it as the first token only
          // when no delta/audio content was observed for this response; otherwise it could arrive
          // after a tool finishes and falsely look like post-tool answer content.
          if (!turnTrackerRef.current.currentResponseHasToken) {
            const first = markFirstToken(turnTrackerRef.current, monotonicNow());
            const metrics = first ? snapshotTurnMetrics(turnTrackerRef.current) : null;
            upsertById(
              currentAssistantId.current,
              "assistant",
              (content) => content || text,
              first ? { ttftMs: metrics.ttftMs } : null,
            );
          } else {
            upsertById(currentAssistantId.current, "assistant", (content) => content || text);
          }
        }
        break;
      }
      case "response.audio.delta":
      case "response.output_audio.delta":
        if (evt.delta && currentAssistantId.current) {
          const receivedAtMs = monotonicNow();
          const bytes = base64ToUint8(evt.delta);
          const voice = pcmVoiceOffsetsMs(bytes);
          markFirstAudio(turnTrackerRef.current, receivedAtMs);
          const willRender = shouldRenderPcmOutput(
            isUserSpeaking.current,
            avatarAudioAvailableRef.current,
            transportRef.current,
          );
          if (willRender) {
            if (voice.firstVoicedMs != null) {
              markFirstSpeech(turnTrackerRef.current, receivedAtMs + voice.firstVoicedMs);
            }
            const audio = ensureAudio();
            if (!audio.isPlaying) audio.startStreamingPlayback();
            const playbackAtMs = audio.playChunk(bytes, voice.firstVoicedMs);
            if (voice.firstVoicedMs != null) {
              markFirstPlayback(turnTrackerRef.current, playbackAtMs);
            }
          }
          const metrics = snapshotTurnMetrics(turnTrackerRef.current);
          // Audio can precede its transcript. Create the (temporarily empty) response bubble now
          // so the latency bars are visible at the instant playable audio arrives.
          upsertById(
            currentAssistantId.current,
            "assistant",
            (content) => content,
            metrics,
          );
        }
        break;
      case "response.audio.done":
      case "response.output_audio.done":
        logEvent("response.audio.done");
        break;
      case "response.done": {
        const turn = turnTrackerRef.current;
        // `response.output` restates the response's items in final form, so a function call whose
        // per-item events were missed is still picked up here (already-answered calls are ignored).
        for (const call of functionCallsFromResponseDone(evt)) noteFunctionCall(call);
        activeResponseCountRef.current = Math.max(0, activeResponseCountRef.current - 1);
        addResponseUsage(turn, evt);
        const finalize = shouldFinalizeOnResponseDone(turn);
        currentAssistantId.current = null;
        if (finalize) {
          attachTurnMetrics();
          markTurn("agent", "");
          setStatus({ text: "ready - listening", kind: "ok" });
        } else {
          setStatus({
            text: pendingToolCallCount(turn) > 0 ? "running tool..." : "thinking...",
            kind: "warn",
          });
        }
        logEvent("response.done");
        // The response that carried a client function call has ended, so its answer can now be
        // requested without colliding with it.
        flushFunctionOutputs();
        break;
      }

      // ---- MCP tools (design §6): listing, the call lifecycle, and approval requests ----
      case "mcp_list_tools.in_progress":
        logEvent("mcp_list_tools.in_progress");
        break;
      case "mcp_list_tools.completed": {
        const tools = (evt.tools || (evt.item && evt.item.tools) || []);
        const names = tools.map((x) => x && x.name).filter(Boolean);
        logStatus("MCP tools available" + (names.length ? `: ${names.join(", ")}` : ""));
        break;
      }
      case "mcp_list_tools.failed":
        logError("mcp_list_tools.failed: " + JSON.stringify(evt.error || evt));
        break;
      case "conversation.item.created":
      case "conversation.item.added":
      case "conversation.item.done":
      case "response.output_item.added":
      case "response.output_item.done":
        // These carry conversation items; MCP approval-request and mcp_call items are surfaced as
        // their own bubbles. Non-MCP items fall through to the verbose event log.
        if (evt.item) handleMcpItem(evt.item);
        // A `function_call` item is the client's own work: it names the call and (on the `.done`
        // events) carries the complete arguments, so it is the fallback path when the dedicated
        // `response.function_call_arguments.done` event is not delivered.
        if (evt.item) {
          noteFunctionCall(
            functionCallFromItem(evt.item, COMPLETED_FUNCTION_ITEM_EVENTS.has(t)),
          );
        }
        logEvent(t);
        break;

      // ---- client-executed function tools (design §6.1) ----
      case "response.function_call_arguments.delta":
        if (evt.item_id || evt.call_id) {
          noteFunctionCall({
            itemId: evt.item_id || "",
            callId: evt.call_id || "",
            name: evt.name || "",
            // Accumulated as the fallback arguments: a terminal item event may restate the call
            // with an empty `arguments` string, and the deltas are then the only complete copy.
            argumentsDelta: typeof evt.delta === "string" ? evt.delta : "",
          });
        }
        logEvent("response.function_call_arguments.delta");
        break;
      case "response.function_call_arguments.done":
        logEvent("response.function_call_arguments.done");
        noteFunctionCall(functionCallFromArgumentsDone(evt));
        break;
      case "response.mcp_call_arguments.done":
        if (evt.item_id) {
          startToolCall(
            turnTrackerRef.current,
            evt.item_id,
            monotonicNow(),
            describeMcpTool(evt, sessionToolIndexRef.current),
            false,
          );
          if (evt.arguments != null) patchMcpCall(evt.item_id, { arguments: asText(evt.arguments) });
        }
        break;
      case "response.mcp_call.in_progress":
        if (evt.item_id) {
          startToolCall(
            turnTrackerRef.current,
            evt.item_id,
            monotonicNow(),
            describeMcpTool(evt, sessionToolIndexRef.current),
            true,
          );
          patchMcpCall(evt.item_id, { status: "in_progress" });
        }
        setStatus({ text: "running tool...", kind: "warn" });
        logEvent("response.mcp_call.in_progress");
        break;
      case "response.mcp_call.completed": {
        if (evt.item_id) {
          const tool = finishToolCall(
            turnTrackerRef.current,
            evt.item_id,
            monotonicNow(),
            "completed",
            describeMcpTool(evt, sessionToolIndexRef.current),
          );
          patchMcpCall(evt.item_id, {
            status: "completed",
            ...(evt.output != null ? { output: asText(evt.output) } : {}),
            ...(tool && tool.durationMs != null ? { durationMs: Math.round(tool.durationMs) } : {}),
          });
        }
        setStatus({ text: "thinking...", kind: "warn" });
        logEvent("response.mcp_call.completed");
        // Voice Live automatically schedules the post-tool answer. Plain MCP session tools use
        // `response_scheduling: "when_idle"`; Foundry IQ and toolbox tools schedule in-service.
        break;
      }
      case "response.mcp_call.failed": {
        if (evt.item_id) {
          const tool = finishToolCall(
            turnTrackerRef.current,
            evt.item_id,
            monotonicNow(),
            "failed",
            describeMcpTool(evt, sessionToolIndexRef.current),
          );
          patchMcpCall(evt.item_id, {
            status: "failed",
            ...(evt.error != null ? { error: asText(evt.error) } : {}),
            ...(tool && tool.durationMs != null ? { durationMs: Math.round(tool.durationMs) } : {}),
          });
        }
        logError("response.mcp_call.failed: " + JSON.stringify(evt.error || ""));
        if (canFinalizeAfterToolFailure(turnTrackerRef.current)) {
          attachTurnMetrics();
          setStatus({ text: "ready - listening", kind: "ok" });
        }
        break;
      }

      case "error": {
        // Asking for a response while one is already active (realtime auto-continues after an MCP
        // call) is benign — log it quietly instead of surfacing an error bubble.
        const code = evt.error && evt.error.code;
        if (code === "conversation_already_has_active_response" || code === "response_cancel_not_active") {
          logEvent("ignored benign error: " + code);
          break;
        }
        logError("Voice Live error: " + JSON.stringify(evt.error || evt));
        setStatus({ text: "error: " + ((evt.error && evt.error.message) || "see log"), kind: "err" });
        break;
      }
      default:
        logEvent(t);
        break;
    }
  }, [
    attachTurnMetrics,
    beginTurn,
    flushFunctionOutputs,
    handleMcpItem,
    logError,
    logEvent,
    logStatus,
    markTurn,
    noteFunctionCall,
    patchMcpCall,
    recordUserTranscript,
    applyAvatarAnswer,
    applyWebRtcAnswer,
    cleanupWebRtc,
    startAvatarConnection,
    startMic,
    upsertHandoff,
    upsertById,
  ]);

  const connect = useCallback(async (
    agentName,
    voiceOverride,
    storeOverride,
    apiVersion,
    transport,
    clientReferenceEc = false,
    referenceAudioMode = "assistant",
    structuredInput = "",
  ) => {
    if (!agentName) { logError("Create an agent first"); return; }
    let normalizedStructuredInput = "";
    try {
      normalizedStructuredInput = normalizeStructuredInputJson(structuredInput);
    } catch (error) {
      logError(error instanceof Error ? error.message : String(error));
      setStatus({ text: "invalid structured input", kind: "err" });
      return;
    }
    if (clientReferenceEc && transport === "webrtc") {
      logError("Live-reference echo cancellation requires the WebSocket PCM transport");
      return;
    }
    transportRef.current = transport === "webrtc" ? "webrtc" : "websocket";
    clientReferenceEcRef.current = Boolean(clientReferenceEc);
    referenceAudioModeRef.current = clientReferenceEc
      ? referenceAudioMode
      : "assistant";
    if (clientReferenceEc && referenceAudioModeRef.current !== "assistant") {
      setStatus({ text: "choose reference audio to share...", kind: "warn" });
      logStatus("Select a tab, window, or screen and enable Share audio");
      try {
        await ensureAudio().prepareReferenceCapture(() => {
          logError("Shared reference audio ended; reconnect to restore echo cancellation");
          setStatus({ text: "shared reference ended", kind: "err" });
        });
      } catch (error) {
        logError("Shared reference audio failed: " + error);
        setStatus({ text: "shared audio not selected", kind: "err" });
        if (audioRef.current) { audioRef.current.dispose(); audioRef.current = null; }
        return;
      }
      logStatus("Shared reference audio is ready");
    }
    const proto = location.protocol === "https:" ? "wss" : "ws";
    // The portal WS route mirrors the service voice endpoint:
    // /agents/{agent}/endpoint/protocols/voice, and the browser
    // sends api-version + agent_session_id, plus store and per-session overrides. A browser can't
    // set custom WS headers: the backend converts voiceOverride and structured_input to service
    // headers (the deployed Foundry WS endpoint currently rejects the structured_input query).
    const agentSessionId = `web-${Math.random().toString(16).slice(2, 10)}`;
    let url = `${proto}://${location.host}/agents/${encodeURIComponent(agentName)}/endpoint/protocols/voice`;
    const qs = [];
    if (apiVersion) qs.push(`api-version=${encodeURIComponent(apiVersion)}`);
    qs.push(`agent_session_id=${encodeURIComponent(agentSessionId)}`);
    if (storeOverride) qs.push(`store=${encodeURIComponent(storeOverride)}`);
    if (normalizedStructuredInput) {
      qs.push(
        `${STRUCTURED_INPUT_QUERY_PARAMETER}=${encodeURIComponent(normalizedStructuredInput)}`,
      );
    }
    if (voiceOverride) qs.push(`voiceOverride=${encodeURIComponent(voiceOverride)}`);
    if (transportRef.current === "webrtc") qs.push("transport=webrtc");
    if (qs.length) url += `?${qs.join("&")}`;
    const loggedQs = qs.map((value) => (
      value.startsWith(`${STRUCTURED_INPUT_QUERY_PARAMETER}=`)
        ? `${STRUCTURED_INPUT_QUERY_PARAMETER}=<redacted>`
        : value
    ));
    logApi("WS", `/agents/${agentName}/endpoint/protocols/voice?${loggedQs.join("&")}`);

    setSessionId(null);
    setConversationId(null);
    setSessionReady(false);
    sessionReadyRef.current = false;
    clientCloseRequestedRef.current = false;
    setActiveHandoffNodeId(null);
    setHandoffState(null);
    setHandoffTrail([]);
    setTakenEdgeIds([]);
    cleanupAvatar();
    cleanupWebRtc();
    isUserSpeaking.current = false;
    currentAssistantId.current = null;
    turnTrackerRef.current = createTurnTracker();
    sessionToolIndexRef.current = {};
    transcriptionTimingRef.current.clear();
    activeUserItemIdRef.current = null;
    latestInputVoiceAtRef.current = null;
    activeInputVoiceAtRef.current = null;
    resetClientFunctionState();
    setStatus({ text: "connecting...", kind: "warn" });
    const overrideNote = [
      voiceOverride ? `voice override: ${voiceOverride}` : null,
      storeOverride ? `store: ${storeOverride}` : null,
      normalizedStructuredInput ? "structured input: provided" : null,
      clientReferenceEc ? "live-reference EC" : null,
      clientReferenceEc && referenceAudioModeRef.current !== "assistant"
        ? `reference: ${referenceAudioModeRef.current}`
        : null,
    ].filter(Boolean).join(", ");
    logStatus(`Connecting to ${agentName}${overrideNote ? ` (${overrideNote})` : " (agent defaults)"} ...`);

    const ws = new WebSocket(url);
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      setStatus({ text: "connected (waiting for session)", kind: "warn" });
      logStatus("WebSocket open; backend connecting to Voice Live...");
      // WebRTC transport: the rtc.call.sdp.create frame OPENS the call, so offer on ws.onopen —
      // not on session.updated (which arrives after the answer).
      if (transportRef.current === "webrtc") startWebRtcSession();
    };
    ws.onmessage = (ev) => {
      if (typeof ev.data !== "string") return;
      let evt; try { evt = JSON.parse(ev.data); } catch { return; }
      recordFrame("down", evt);
      handleEvent(evt);
    };
    ws.onerror = () => { logError("WebSocket error"); setStatus({ text: "error", kind: "err" }); };
    ws.onclose = async (e) => {
      logStatus(`WebSocket closed (code ${e.code}${e.reason ? `, ${e.reason}` : ""})`);
      setSessionReady(false);
      sessionReadyRef.current = false;
      setSessionId(null);
      setActiveHandoffNodeId(null);
      isUserSpeaking.current = false;
      currentAssistantId.current = null;
      turnTrackerRef.current = createTurnTracker();
      sessionToolIndexRef.current = {};
      transcriptionTimingRef.current.clear();
      activeUserItemIdRef.current = null;
      latestInputVoiceAtRef.current = null;
      activeInputVoiceAtRef.current = null;
      resetClientFunctionState();
      cleanupAvatar();
      cleanupWebRtc();
      const audio = audioRef.current;
      const shouldDrain = shouldDrainSessionAudio(
        e.code,
        e.reason,
        clientCloseRequestedRef.current,
      );
      if (shouldDrain && audio) {
        setStatus({ text: "finishing final audio...", kind: "warn" });
        audio.stopRecording();
        await audio.waitForPlaybackComplete();
      }
      if (!clientCloseRequestedRef.current) {
        setStatus(describeSessionClose(e.code, e.reason));
      }
      setIsConnected(false);
      if (audioRef.current === audio && audio) {
        audio.dispose();
        audioRef.current = null;
      }
      clientCloseRequestedRef.current = false;
      if (wsRef.current === ws) wsRef.current = null;
    };
  }, [cleanupAvatar, cleanupWebRtc, resetClientFunctionState, startWebRtcSession, handleEvent, logStatus, logError, logApi]);

  const stopSession = useCallback(() => {
    logStatus("Stopping session...");
    clientCloseRequestedRef.current = true;
    const ws = wsRef.current;
    if (ws) { try { ws.close(1000, "client stopped session"); } catch { /* noop */ } }
    cleanupAvatar();
    cleanupWebRtc();
    if (audioRef.current) { audioRef.current.dispose(); audioRef.current = null; }
    setStatus({ text: "session stopped - connect to start a new one", kind: "" });
  }, [cleanupAvatar, cleanupWebRtc, logStatus]);

  const toggleMute = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    const next = !micMuted;
    audio.setMuted(next);
    setMicMuted(next);
    setStatus({ text: next ? "muted" : "listening (server VAD)", kind: next ? "warn" : "ok" });
  }, [micMuted]);

  const sendText = useCallback((text) => {
    const ws = wsRef.current;
    const trimmed = (text || "").trim();
    if (!trimmed || !ws || ws.readyState !== WebSocket.OPEN) return;
    beginTurn(monotonicNow(), "text_input");
    markTurn("user", trimmed);
    const item = {
      type: "conversation.item.create",
      item: { type: "message", role: "user", content: [{ type: "input_text", text: trimmed }] },
    };
    const create = { type: "response.create" };
    recordFrame("up", item);
    ws.send(JSON.stringify(item));
    recordFrame("up", create);
    ws.send(JSON.stringify(create));
    addMessage({ type: "user", content: trimmed });
    // Typed turns never pass through speech recognition, so record them here: a client function
    // asking for "what the user actually said" must still work when the demo is driven by text.
    recordUserTranscript(trimmed, "typed text (no speech recognition)");
  }, [addMessage, beginTurn, markTurn, recordFrame, recordUserTranscript]);

  // Answer an MCP approval request (design §6.2): send the `mcp_approval_response` item upstream and
  // let Voice Live run (or skip) the tool. Do NOT send `response.create` here or when the call
  // completes: Voice Live owns post-tool response scheduling, and a client request would race or
  // duplicate the automatically generated answer.
  const sendMcpApprovalResponse = useCallback((messageId, approvalRequestId, approve) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN && approvalRequestId) {
      const frame = {
        type: "conversation.item.create",
        item: { type: "mcp_approval_response", approve: !!approve, approval_request_id: approvalRequestId },
      };
      recordFrame("up", frame);
      ws.send(JSON.stringify(frame));
    }
    setMessages((prev) => prev.map((m) => (m.id === messageId
      ? { ...m, mcpApproval: { ...m.mcpApproval, handled: true, approved: !!approve } }
      : m)));
    logStatus(`MCP tool ${approve ? "approved" : "denied"}`);
  }, [logStatus, recordFrame]);

  return {
    status, sessionId, conversationId, activeHandoffNodeId, isConnected, sessionReady, micMuted, messages, verbose,
    handoffState, handoffTrail, takenEdgeIds,
    events, clearEvents,
    avatarActive, avatarStatus, avatarStream,
    webrtcActive, webrtcStatus, webrtcStream,
    setVerbose, connect, stopSession, toggleMute, sendText, clearMessages, sendMcpApprovalResponse, logApi,
    logError, setClientFunctions,
  };
}
