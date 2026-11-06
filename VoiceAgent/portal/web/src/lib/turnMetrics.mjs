// Copyright (c) Microsoft. All rights reserved.
// Browser-side turn metrics for the live Voice chat. The service remains the
// source of truth for persisted voice_metrics; these helpers mirror the same event
// boundaries so the demo can show TTFT/TTFA immediately and enrich them with usage
// when response.done arrives.

const isNumber = (value) => typeof value === "number" && Number.isFinite(value);

export const ALL_TURN_OUTLIER_PERCENT = 50;
export const LATENCY_VISUAL_REFERENCE_MS = 2000;

export const LATENCY_TONE_LEGEND = [
  { tone: "timeout", label: "Idle timeout" },
  { tone: "vad", label: "VAD / EOU" },
  { tone: "orchestrator", label: "Orchestrator" },
  { tone: "upstream", label: "Upstream admission" },
  { tone: "model", label: "Model" },
  { tone: "tts", label: "TTS / speech" },
  { tone: "transport", label: "Transport / residual" },
  { tone: "tool", label: "Tool" },
  { tone: "playback", label: "Playback" },
  { tone: "other", label: "Mixed / unobserved" },
];

export const LATENCY_CHECKPOINTS = [
  {
    key: "ttfaMs",
    label: "TTFA",
    tone: "audio",
    description: "Turn start to the first non-empty audio packet received by the browser.",
  },
  {
    key: "ttftMs",
    label: "TTFT",
    tone: "token",
    description: "Turn start to the first Agent text or audio-transcript token.",
  },
];

export function createTurnTracker(startedAtMs = null, startSource = null) {
  return {
    startedAtMs: isNumber(startedAtMs) ? startedAtMs : null,
    startSource: isNumber(startedAtMs) ? startSource : null,
    inputItemId: null,
    speechStoppedAtMs: null,
    timeoutTriggeredAtMs: null,
    timeoutWindowMs: null,
    serverTiming: null,
    responseStarts: [],
    firstTokenAtMs: null,
    firstAudioAtMs: null,
    firstSpeechAtMs: null,
    firstPlaybackAtMs: null,
    totalTokens: 0,
    hasUsage: false,
    assistantId: null,
    currentResponseHasContent: false,
    currentResponseHasToken: false,
    currentResponseStartedAfterTool: false,
    contentAfterLastTool: false,
    lastToolCompletedAtMs: null,
    responseDoneWhileToolPending: false,
    toolCalls: new Map(),
  };
}

export function markSpeechStopped(turn, inputItemId, nowMs) {
  if (!isNumber(nowMs)) return false;
  turn.inputItemId = inputItemId || turn.inputItemId;
  turn.speechStoppedAtMs = nowMs;
  return true;
}

export function markTimeoutTriggered(turn, inputItemId, nowMs, audioStartMs, audioEndMs) {
  if (!isNumber(nowMs)) return false;
  turn.inputItemId = inputItemId || turn.inputItemId;
  turn.timeoutTriggeredAtMs = nowMs;
  turn.timeoutWindowMs = isNumber(audioStartMs) && isNumber(audioEndMs) && audioEndMs >= audioStartMs
    ? Math.round(audioEndMs - audioStartMs)
    : null;
  return true;
}

export function applyResponseServerTiming(turn, event) {
  const timing = event?.server_timing;
  if (!timing || timing.version !== 1) return false;
  if (turn.inputItemId && event.input_item_id !== turn.inputItemId) return false;
  if (!turn.responseStarts.some((response) => response.id === event.response_id)) return false;

  const normalized = { version: 1 };
  for (const key of [
    "endpoint_candidate_wait_ms",
    "eou_inference_ms",
    "eou_hold_ms",
    "eou_inference_count",
    "endpoint_delivery_ms",
    "endpoint_to_commit_sent_ms",
    "response_schedule_wait_ms",
    "response_dispatch_to_created_ms",
  ]) {
    if (isNumber(timing[key]) && timing[key] >= 0) normalized[key] = Math.round(timing[key]);
  }
  if (typeof timing.eou_forced_by_timeout === "boolean") {
    normalized.eou_forced_by_timeout = timing.eou_forced_by_timeout;
  }
  if (typeof timing.turn_detection_mode === "string") {
    normalized.turn_detection_mode = timing.turn_detection_mode;
  }
  turn.serverTiming = normalized;
  return true;
}

function ensureStarted(turn, nowMs, startSource = "response_created") {
  if (!isNumber(turn.startedAtMs) && isNumber(nowMs)) {
    turn.startedAtMs = nowMs;
    turn.startSource = startSource;
  }
}

export function startAssistantResponse(turn, suggestedId, nowMs) {
  ensureStarted(turn, nowMs);
  if (
    isNumber(nowMs)
    && !turn.responseStarts.some((response) => Math.abs(response.atMs - nowMs) < 1)
  ) {
    turn.responseStarts.push({ id: suggestedId, atMs: nowMs });
  }
  if (!turn.assistantId) turn.assistantId = suggestedId;
  turn.currentResponseHasContent = false;
  turn.currentResponseHasToken = false;
  turn.currentResponseStartedAfterTool =
    turn.toolCalls.size > 0 &&
    pendingToolCallCount(turn) === 0 &&
    isNumber(turn.lastToolCompletedAtMs);
  return turn.assistantId;
}

function markAssistantContent(turn, nowMs) {
  ensureStarted(turn, nowMs);
  turn.currentResponseHasContent = true;
  if (isNumber(turn.lastToolCompletedAtMs) && nowMs >= turn.lastToolCompletedAtMs) {
    turn.contentAfterLastTool = true;
  }
}

export function markFirstToken(turn, nowMs) {
  markAssistantContent(turn, nowMs);
  turn.currentResponseHasToken = true;
  if (isNumber(turn.firstTokenAtMs)) return false;
  turn.firstTokenAtMs = nowMs;
  return true;
}

export function markFirstAudio(turn, nowMs) {
  markAssistantContent(turn, nowMs);
  if (isNumber(turn.firstAudioAtMs)) return false;
  turn.firstAudioAtMs = nowMs;
  return true;
}

export function markFirstSpeech(turn, nowMs) {
  markAssistantContent(turn, nowMs);
  if (isNumber(turn.firstSpeechAtMs)) return false;
  turn.firstSpeechAtMs = nowMs;
  return true;
}

export function markFirstPlayback(turn, nowMs) {
  if (!isNumber(nowMs) || isNumber(turn.firstPlaybackAtMs)) return false;
  turn.firstPlaybackAtMs = nowMs;
  return true;
}

export function extractResponseTotalTokens(event) {
  const response = event && event.response && typeof event.response === "object"
    ? event.response
    : event;
  const usage = response && response.usage && typeof response.usage === "object"
    ? response.usage
    : null;
  if (!usage) return null;
  if (isNumber(usage.total_tokens)) return usage.total_tokens;
  const input = isNumber(usage.input_tokens) ? usage.input_tokens : 0;
  const output = isNumber(usage.output_tokens) ? usage.output_tokens : 0;
  return isNumber(usage.input_tokens) || isNumber(usage.output_tokens) ? input + output : null;
}

export function addResponseUsage(turn, event) {
  const total = extractResponseTotalTokens(event);
  if (isNumber(total)) {
    turn.totalTokens += total;
    turn.hasUsage = true;
  }
}

function inferToolKind(tool) {
  const type = String((tool && tool.type) || "").toLowerCase();
  const label = String((tool && (tool.server_label || tool.serverLabel)) || "").toLowerCase();
  const url = String((tool && (tool.server_url || tool.serverUrl)) || "").toLowerCase();
  if (type === "foundry_toolbox") return "Toolbox";
  if (url.includes("/knowledgebases/") || label.includes("foundry-iq") || label.includes("foundry_iq")) {
    return "Foundry IQ";
  }
  return "MCP";
}

export function indexSessionTools(tools = []) {
  const index = {};
  for (const tool of tools || []) {
    if (!tool) continue;
    const serverLabel = tool.server_label || tool.serverLabel || tool.name;
    if (!serverLabel) continue;
    index[String(serverLabel).toLowerCase()] = {
      kind: inferToolKind(tool),
      serverLabel,
    };
  }
  return index;
}

export function describeMcpTool(item = {}, toolIndex = {}) {
  const serverLabel = item.server_label || item.serverLabel || "";
  const configured = serverLabel ? toolIndex[String(serverLabel).toLowerCase()] : null;
  return {
    kind: configured ? configured.kind : inferToolKind(item),
    serverLabel,
    name: item.name || "",
  };
}

function getOrCreateToolCall(turn, itemId) {
  let tool = turn.toolCalls.get(itemId);
  if (!tool) {
    tool = {
      id: itemId,
      kind: "MCP",
      serverLabel: "",
      name: "",
      status: "pending",
      startedAtMs: null,
      explicitStart: false,
      completedAtMs: null,
      durationMs: null,
    };
    turn.toolCalls.set(itemId, tool);
  }
  return tool;
}

export function updateToolCallDetails(turn, itemId, details = {}) {
  if (!itemId) return null;
  const tool = getOrCreateToolCall(turn, itemId);
  for (const field of ["kind", "serverLabel", "name"]) {
    if (details[field]) tool[field] = details[field];
  }
  return tool;
}

export function startToolCall(turn, itemId, nowMs, details = {}, explicit = false) {
  if (!itemId) return null;
  const tool = updateToolCallDetails(turn, itemId, details);
  if (explicit && !tool.explicitStart) {
    tool.startedAtMs = nowMs;
    tool.explicitStart = true;
  } else if (!isNumber(tool.startedAtMs)) {
    tool.startedAtMs = nowMs;
  }
  tool.status = "in_progress";
  turn.contentAfterLastTool = false;
  return tool;
}

export function finishToolCall(turn, itemId, nowMs, status, details = {}) {
  if (!itemId) return null;
  const tool = updateToolCallDetails(turn, itemId, details);
  tool.status = status;
  tool.completedAtMs = nowMs;
  tool.durationMs = isNumber(tool.startedAtMs) ? Math.max(0, nowMs - tool.startedAtMs) : null;
  turn.lastToolCompletedAtMs = nowMs;
  turn.contentAfterLastTool = false;
  return tool;
}

export function pendingToolCallCount(turn) {
  let count = 0;
  for (const tool of turn.toolCalls.values()) {
    if (tool.status === "in_progress") count++;
  }
  return count;
}

export function shouldFinalizeOnResponseDone(turn) {
  if (pendingToolCallCount(turn) > 0) {
    turn.responseDoneWhileToolPending = true;
    return false;
  }
  if (turn.toolCalls.size === 0) return true;
  return turn.contentAfterLastTool ||
    (turn.currentResponseStartedAfterTool && turn.currentResponseHasContent);
}

export function canFinalizeAfterToolFailure(turn) {
  return turn.responseDoneWhileToolPending && pendingToolCallCount(turn) === 0;
}

export function elapsedMetricMs(startedAtMs, completedAtMs) {
  return isNumber(startedAtMs) && isNumber(completedAtMs)
    ? Math.max(0, Math.round(completedAtMs - startedAtMs))
    : null;
}

function withinTurn(timestamp, turn, endAtMs) {
  return isNumber(timestamp)
    && timestamp >= turn.startedAtMs
    && timestamp <= endAtMs;
}

function phaseDefinition(turn, startAtMs, endAtMs, tools, responses) {
  const midpoint = startAtMs + ((endAtMs - startAtMs) / 2);
  const activeTools = tools.filter((tool) => (
    tool.startedAtMs <= midpoint && tool.completedAtMs >= midpoint
  ));
  if (activeTools.length) {
    const names = activeTools.map((tool) => (
      `${tool.kind || "Tool"}${tool.name ? ` ${tool.name}` : ""}`
    ));
    return {
      category: "tool",
      label: names.join(" + "),
      tone: "tool",
      reason: "Tool execution",
    };
  }

  const isAt = (timestamp) => isNumber(timestamp) && Math.abs(timestamp - startAtMs) < 1;
  if (
    turn.startSource === "idle_timeout"
    && Math.abs(startAtMs - turn.startedAtMs) < 1
    && isNumber(turn.timeoutTriggeredAtMs)
    && Math.abs(endAtMs - turn.timeoutTriggeredAtMs) < 1
  ) {
    return {
      category: "idle_timeout_wait",
      label: "Idle timeout wait",
      tone: "timeout",
      reason: "Configured silence window accumulated before the timeout event fired",
    };
  }
  if (
    turn.startSource === "agent_playback_end"
    && Math.abs(startAtMs - turn.startedAtMs) < 1
  ) {
    return {
      category: "inter_response_pause",
      label: "Perceived pause",
      tone: "other",
      reason: "Silence from the end of the previous Agent utterance until this utterance became audible",
    };
  }
  if (turn.startSource === "idle_timeout" && isAt(turn.timeoutTriggeredAtMs)) {
    return {
      category: "timeout_response_startup",
      label: "Timeout response startup",
      tone: "orchestrator",
      reason: "Timeout event delivery, silence-item commit, and response creation",
    };
  }
  if (isAt(turn.firstSpeechAtMs)) {
    return {
      category: "playback",
      label: "Playback buffer",
      tone: "playback",
      reason: "Speech PCM was ready but waited in the browser playback queue",
    };
  }
  if (isAt(turn.firstAudioAtMs)) {
    return {
      category: "silence",
      label: "Leading silence",
      tone: "tts",
      reason: "The first audio packet arrived before its first voiced PCM frame",
    };
  }
  if (isAt(turn.firstTokenAtMs)) {
    return {
      category: "other_speech",
      label: "TTS / speech pipeline",
      tone: "tts",
      reason: "Sentence segmentation, TTS, and transport boundaries are not separately observable",
    };
  }

  const completedTool = tools.find((tool) => isAt(tool.completedAtMs));
  if (completedTool) {
    return {
      category: "other_continuation",
      label: "Other \u00b7 continuation",
      tone: "other",
      reason: "Post-tool response scheduling and continuation model work are not separately observable",
    };
  }

  const responseAtStart = responses.find((response) => isAt(response.atMs));
  if (turn.serverTiming && isAt(turn.speechStoppedAtMs)) {
    return {
      category: "response_startup",
      label: "Response startup",
      tone: "other",
      reason: "Endpoint decision to response.created",
    };
  }
  if (
    turn.serverTiming
    &&
    Math.abs(startAtMs - turn.startedAtMs) < 1
    && isNumber(turn.speechStoppedAtMs)
    && Math.abs(endAtMs - turn.speechStoppedAtMs) < 1
  ) {
    return {
      category: "endpointing_eou",
      label: "Endpointing + EOU",
      tone: "other",
      reason: "Last voiced microphone PCM to server speech_stopped",
    };
  }
  if (responseAtStart) {
    const nextIsToken = isNumber(turn.firstTokenAtMs) && Math.abs(turn.firstTokenAtMs - endAtMs) < 1;
    const nextIsTool = tools.some((tool) => Math.abs(tool.startedAtMs - endAtMs) < 1);
    const nextIsResponse = responses.some((response) => Math.abs(response.atMs - endAtMs) < 1);
    if (nextIsToken || nextIsTool) {
      return {
        category: "model",
        label: nextIsTool ? "Model \u00b7 tool planning" : "Model \u00b7 first token",
        tone: "model",
        reason: nextIsTool ? "Model work before the tool call" : "Model generation to first text token",
      };
    }
    if (nextIsResponse) {
      return {
        category: "other_response_transition",
        label: "Other \u00b7 response transition",
        tone: "other",
        reason: "The previous response existed before another response was created, but the client has no finer lifecycle or scheduling boundary between them",
      };
    }
    return {
      category: "other_native",
      label: "Model / speech (combined)",
      tone: "model",
      reason: "This path produced audio without an observable text or TTS boundary",
    };
  }

  if (Math.abs(startAtMs - turn.startedAtMs) < 1) {
    return {
      category: "other_preresponse",
      label: "Other \u00b7 before response",
      tone: "other",
      reason: turn.startSource === "text_input"
        ? "Client request handling and response scheduling are not separately observable"
        : "EOU, endpointing, and response scheduling are not separately observable",
    };
  }
  return {
    category: "other",
    label: "Other \u00b7 unobserved",
    tone: "other",
    reason: "No finer client-visible boundary is available for this interval",
  };
}

function milestoneLabel(turn, timestamp, tools, responses) {
  const isAt = (candidate) => isNumber(candidate) && Math.abs(candidate - timestamp) < 1;
  if (isAt(turn.startedAtMs)) {
    return {
      user_last_voiced: "last voiced microphone PCM",
      server_vad: "server speech_stopped",
      text_input: "text input sent",
      idle_timeout: "idle timeout window start",
      agent_playback_end: "previous Agent speech end",
      response_created: "response.created",
    }[turn.startSource] || "turn start";
  }
  if (turn.startSource === "idle_timeout" && isAt(turn.timeoutTriggeredAtMs)) {
    return "input_audio_buffer.timeout_triggered";
  }
  if (turn.serverTiming && isAt(turn.speechStoppedAtMs)) return "server speech_stopped";
  const toolStart = tools.find((tool) => isAt(tool.startedAtMs));
  if (toolStart) {
    return `${toolStart.kind || "Tool"}${toolStart.name ? ` ${toolStart.name}` : ""} in_progress`;
  }
  const toolEnd = tools.find((tool) => isAt(tool.completedAtMs));
  if (toolEnd) {
    return `${toolEnd.kind || "Tool"}${toolEnd.name ? ` ${toolEnd.name}` : ""} completed`;
  }
  const responseIndex = responses.findIndex((response) => isAt(response.atMs));
  if (responseIndex >= 0) {
    const response = responses[responseIndex];
    const shortId = response.id ? ` (${String(response.id).slice(0, 18)})` : "";
    return `response.created #${responseIndex + 1}${shortId}`;
  }
  if (isAt(turn.firstPlaybackAtMs)) return "scheduled playback of first speech";
  if (isAt(turn.firstSpeechAtMs)) return "first voiced PCM frame";
  if (isAt(turn.firstAudioAtMs)) return "first audio packet";
  if (isAt(turn.firstTokenAtMs)) return "first Agent text token";
  return "client-visible milestone";
}

export function buildAtomicLatencyPhases(turn) {
  if (!isNumber(turn.startedAtMs)) return [];
  const endAtMs = [turn.firstPlaybackAtMs, turn.firstSpeechAtMs].find(isNumber);
  if (!isNumber(endAtMs) || endAtMs <= turn.startedAtMs) return [];

  const tools = [...turn.toolCalls.values()]
    .filter((tool) => (
      withinTurn(tool.startedAtMs, turn, endAtMs)
      && withinTurn(tool.completedAtMs, turn, endAtMs)
      && tool.completedAtMs >= tool.startedAtMs
    ));
  const responses = turn.responseStarts.filter((response) => withinTurn(response.atMs, turn, endAtMs));
  const boundaries = [
    turn.startedAtMs,
    endAtMs,
    ...responses.map((response) => response.atMs),
    ...tools.flatMap((tool) => [tool.startedAtMs, tool.completedAtMs]),
    turn.serverTiming ? turn.speechStoppedAtMs : null,
    turn.timeoutTriggeredAtMs,
    !isNumber(turn.firstAudioAtMs) || turn.firstTokenAtMs <= turn.firstAudioAtMs
      ? turn.firstTokenAtMs
      : null,
    turn.firstAudioAtMs,
    turn.firstSpeechAtMs,
    turn.firstPlaybackAtMs,
  ]
    .filter((timestamp) => withinTurn(timestamp, turn, endAtMs))
    .sort((a, b) => a - b)
    .filter((timestamp, index, values) => index === 0 || Math.abs(timestamp - values[index - 1]) >= 1)
    .map((timestamp) => ({
      timestamp,
      offsetMs: Math.round(timestamp - turn.startedAtMs),
    }))
    .filter((point, index, values) => index === 0 || point.offsetMs !== values[index - 1].offsetMs);

  const phases = [];
  for (let index = 0; index < boundaries.length - 1; index++) {
    const startAtMs = boundaries[index].timestamp;
    const endAtMs = boundaries[index + 1].timestamp;
    const durationMs = boundaries[index + 1].offsetMs - boundaries[index].offsetMs;
    if (durationMs <= 0) continue;
    const definition = phaseDefinition(turn, startAtMs, endAtMs, tools, responses);
    const startLabel = milestoneLabel(turn, startAtMs, tools, responses);
    const endLabel = milestoneLabel(turn, endAtMs, tools, responses);
    const previous = phases[phases.length - 1];
    if (previous && previous.category === definition.category && previous.label === definition.label) {
      previous.durationMs += durationMs;
      previous.endLabel = endLabel;
      previous.calculation = `${previous.startLabel} \u2192 ${endLabel}`;
      continue;
    }
    phases.push({
      id: `phase-${index}`,
      ...definition,
      durationMs,
      startLabel,
      endLabel,
      calculation: `${startLabel} \u2192 ${endLabel}`,
    });
  }
  const expanded = expandServerTimingPhases(phases, turn.serverTiming);
  if (expanded) return expanded;
  return turn.serverTiming
    ? buildAtomicLatencyPhases({ ...turn, serverTiming: null })
    : phases;
}

const SERVER_TIMING_PHASES = {
  endpointing_eou: [
    {
      key: "endpoint_candidate_wait_ms",
      category: "endpoint_candidate",
      label: "Endpoint candidate wait",
      tone: "vad",
      reason: "Acoustic speech end to the first VAD endpoint candidate",
    },
    {
      key: "eou_inference_ms",
      category: "eou_inference",
      label: "EOU inference",
      tone: "vad",
      reason: "Total Smart EOU model inference time",
    },
    {
      key: "eou_hold_ms",
      category: "eou_hold",
      label: "EOU hold",
      tone: "vad",
      reason: "First rejected endpoint candidate to EOU acceptance or forced timeout",
    },
    {
      key: "endpoint_delivery_ms",
      category: "endpoint_delivery",
      label: "Endpoint delivery",
      tone: "orchestrator",
      reason: "Generated VAD END event to audio-pipeline handling",
    },
  ],
  response_startup: [
    {
      key: "endpoint_to_commit_sent_ms",
      category: "commit_dispatch",
      label: "Commit dispatch",
      tone: "orchestrator",
      reason: "Endpoint handling to input-audio commit sent upstream",
    },
    {
      key: "response_schedule_wait_ms",
      category: "response_schedule",
      label: "Response scheduling",
      tone: "orchestrator",
      reason: "Commit dispatch to response request dispatch",
    },
    {
      key: "response_dispatch_to_created_ms",
      category: "upstream_admission",
      label: "Upstream admission",
      tone: "upstream",
      reason: "Response request dispatch to upstream response.created",
    },
  ],
};

const SERVER_TIMING_ROUNDING_TOLERANCE_MS = 5;

function expandServerTimingPhases(phases, serverTiming) {
  if (!serverTiming) return null;
  const expanded = [];
  let detailedPhaseCount = 0;
  for (const phase of phases) {
    const definitions = SERVER_TIMING_PHASES[phase.category];
    if (!definitions) {
      expanded.push(phase);
      continue;
    }
    const available = definitions
      .filter((definition) => isNumber(serverTiming[definition.key]))
      .map((definition) => ({
        ...definition,
        durationMs: serverTiming[definition.key],
      }));
    const serverTotal = available.reduce((sum, detail) => sum + detail.durationMs, 0);
    const overflowMs = serverTotal - phase.durationMs;
    if (overflowMs > SERVER_TIMING_ROUNDING_TOLERANCE_MS) {
      return null;
    }
    if (overflowMs > 0) {
      const adjustable = available.reduce(
        (largest, detail) => detail.durationMs > largest.durationMs ? detail : largest,
        available[0],
      );
      adjustable.reportedDurationMs = adjustable.durationMs;
      adjustable.durationMs -= overflowMs;
      adjustable.boundaryAdjustmentMs = -overflowMs;
    }
    if (!available.length) {
      expanded.push(phase);
      continue;
    }
    for (const detail of available) {
      if (detail.durationMs <= 0) continue;
      detailedPhaseCount += 1;
      expanded.push({
        id: `${phase.id}-${detail.key}`,
        category: detail.category,
        label: detail.label,
        tone: detail.tone,
        reason: detail.reason,
        durationMs: detail.durationMs,
        reportedDurationMs: detail.reportedDurationMs,
        boundaryAdjustmentMs: detail.boundaryAdjustmentMs,
        startLabel: detail.label,
        endLabel: detail.label,
        calculation: detail.boundaryAdjustmentMs
          ? `${detail.label} reported as ${detail.reportedDurationMs} ms; adjusted ${detail.boundaryAdjustmentMs} ms to match the rounded client-observed envelope`
          : `${detail.label} reported by Voice Live server timing`,
      });
    }
    const residualMs = phase.durationMs - serverTotal;
    if (residualMs > 0) {
      expanded.push({
        id: `${phase.id}-transport-residual`,
        category: "transport_residual",
        label: "Transport / pipeline residual",
        tone: "transport",
        reason: "Client-observed interval not covered by same-clock server durations",
        durationMs: residualMs,
        startLabel: phase.startLabel,
        endLabel: phase.endLabel,
        calculation: `${phase.durationMs} ms observed minus ${serverTotal} ms server timing`,
      });
    }
  }
  return detailedPhaseCount > 0 ? expanded : null;
}

export function snapshotTurnMetrics(turn) {
  const tools = [...turn.toolCalls.values()]
    .filter((tool) => isNumber(tool.durationMs))
    .sort((a, b) => (a.startedAtMs || 0) - (b.startedAtMs || 0))
    .map((tool) => ({
      id: tool.id,
      kind: tool.kind,
      name: tool.name,
      status: tool.status,
      durationMs: Math.round(tool.durationMs),
    }));
  return {
    startSource: turn.startSource,
    ...(isNumber(turn.timeoutWindowMs) ? { timeoutWindowMs: turn.timeoutWindowMs } : {}),
    ttftMs: elapsedMetricMs(turn.startedAtMs, turn.firstTokenAtMs),
    ttfaMs: elapsedMetricMs(turn.startedAtMs, turn.firstAudioAtMs),
    speechGapMs: elapsedMetricMs(turn.startedAtMs, turn.firstSpeechAtMs),
    playbackMs: elapsedMetricMs(turn.startedAtMs, turn.firstPlaybackAtMs),
    endToEndMs: elapsedMetricMs(
      turn.startedAtMs,
      [turn.firstPlaybackAtMs, turn.firstSpeechAtMs].find(isNumber),
    ),
    endSource: isNumber(turn.firstPlaybackAtMs)
      ? "playback"
      : isNumber(turn.firstSpeechAtMs) ? "speech_pcm" : null,
    atomicPhases: buildAtomicLatencyPhases(turn),
    serverTiming: turn.serverTiming,
    totalTokens: turn.hasUsage ? Math.round(turn.totalTokens) : null,
    tools,
  };
}

export function latencyBarPercent(value, total) {
  if (!isNumber(value) || !isNumber(total) || total <= 0) return 0;
  return Math.max(0, Math.min(100, (value / total) * 100));
}

export function latencyRulerTicks(value) {
  if (!isNumber(value) || value <= 0) return [0];
  const intervals = Math.min(4, Math.max(1, Math.ceil(value / 1000)));
  return Array.from(
    { length: intervals + 1 },
    (_, index) => Math.round((value * index) / intervals),
  );
}

const ALL_TURN_PHASE_DEFINITIONS = [
  {
    key: "phase_idle_timeout_wait",
    category: "idle_timeout_wait",
    label: "Idle timeout wait",
    description: "Configured silent audio window before input_audio_buffer.timeout_triggered.",
    scope: "atomic",
    startLabel: "Idle window start",
    endLabel: "timeout_triggered",
    interpretation: "A high value usually reflects the configured idle timeout policy rather than slow model execution.",
    caveats: [
      "The duration comes from timeout event audio_end_ms - audio_start_ms.",
      "This is a silence-policy wait, not user speech processing latency.",
    ],
  },
  {
    key: "phase_timeout_response_startup",
    category: "timeout_response_startup",
    label: "Timeout startup",
    description: "input_audio_buffer.timeout_triggered to response.created for an automatic continuation.",
    scope: "atomic",
    startLabel: "timeout_triggered",
    endLabel: "response.created",
    interpretation: "A high value points to silence-item commit, response scheduling, or upstream admission after the timeout fired.",
    caveats: [
      "Current response.server_timing diagnostics cover speech endpoint turns, not idle-timeout commits.",
      "This phase therefore combines internal timeout commit and response-startup boundaries.",
    ],
  },
  {
    key: "phase_endpointing_eou",
    category: "endpointing_eou",
    label: "Endpointing + EOU",
    description: "Last voiced microphone PCM to input_audio_buffer.speech_stopped.",
    scope: "atomic",
    startLabel: "Last voiced PCM",
    endLabel: "speech_stopped",
    interpretation: "A high value places the delay before the server accepted the end of the user turn.",
    caveats: ["Without server timing, VAD wait, EOU inference, holding, and transport remain combined."],
  },
  {
    key: "phase_response_startup",
    category: "response_startup",
    label: "Response startup",
    description: "input_audio_buffer.speech_stopped to response.created.",
    scope: "atomic",
    startLabel: "speech_stopped",
    endLabel: "response.created",
    interpretation: "A high value places the delay after endpoint acceptance but before the response object existed.",
    caveats: ["Without server timing, commit, scheduling, admission, and transport remain combined."],
  },
  ...[
    ["endpoint_candidate", "Endpoint candidate", "Acoustic speech end to the first VAD endpoint candidate."],
    ["eou_inference", "EOU inference", "Smart EOU inference wall time."],
    ["eou_hold", "EOU hold", "Smart EOU waiting after its first rejected candidate."],
    ["endpoint_delivery", "Endpoint delivery", "VAD END generation to pipeline handling."],
    ["commit_dispatch", "Commit dispatch", "Endpoint handling to upstream audio commit."],
    ["response_schedule", "Response scheduling", "Commit dispatch to response request dispatch."],
    ["upstream_admission", "Upstream admission", "Response dispatch to upstream response.created."],
    ["transport_residual", "Transport residual", "Client-observed time not covered by server durations."],
  ].map(([category, label, description]) => ({
    key: `phase_${category}`,
    category,
    label,
    description,
    scope: "atomic",
    startLabel: "Server timing start",
    endLabel: "Server timing end",
    interpretation: `A high ${label} value identifies this server or transport phase as an optimization target.`,
    caveats: ["Available only when local Dashboard server-timing diagnostics are enabled."],
  })),
  {
    key: "phase_other_preresponse",
    category: "other_preresponse",
    label: "Before response",
    description: "Turn start to response.created; EOU, endpointing, and scheduling are not separately observable.",
    scope: "atomic",
    startLabel: "Turn start",
    endLabel: "response.created",
    interpretation: "A high value means delay happened before the first response object existed. For voice input this can include endpointing, EOU/VAD handling, transcription readiness, queueing, and response scheduling.",
    caveats: [
      "The browser cannot separate EOU, service queueing, and response scheduling inside this interval.",
      "Voice proxy turns begin at server speech_stopped rather than the true last voiced microphone sample.",
    ],
  },
  {
    key: "phase_model",
    category: "model",
    label: "Model",
    description: "Observable model work from response.created to first text token or tool execution start.",
    scope: "atomic",
    startLabel: "response.created",
    endLabel: "First token / tool start",
    interpretation: "A high value points to model startup, prompt/context processing, or tool-selection planning after the response was scheduled.",
    caveats: [
      "For Native S2S paths, a text-token boundary may not exist; that time is reported under Model/speech.",
      "This is client-observed elapsed time and includes delivery of the milestone event to the browser.",
    ],
  },
  {
    key: "phase_tool",
    category: "tool",
    label: "Tool",
    description: "Total time inside observed MCP, Toolbox, Foundry IQ, or client function execution.",
    scope: "atomic",
    startLabel: "tool in_progress",
    endLabel: "tool completed / failed",
    interpretation: "A high value points to the external tool, its network path, or a client-side function handler. Multiple observed tools in one turn are added in this column.",
    caveats: [
      "Parallel overlapping tools are represented by the observable union in the turn timeline, while this aggregate is grouped by phase category.",
      "Time after tool completion belongs to Continuation, not Tool.",
    ],
  },
  {
    key: "phase_other_continuation",
    category: "other_continuation",
    label: "Continuation",
    description: "Tool completion to the next observable response milestone; scheduling and model work cannot be separated.",
    scope: "atomic",
    startLabel: "Tool completed",
    endLabel: "Next response milestone",
    interpretation: "A high value means the tool finished, but the Agent took time to schedule and begin the follow-up response.",
    caveats: [
      "Continuation scheduling and follow-up model startup are not separately visible to the browser.",
      "This phase appears only on turns that use a tool.",
    ],
  },
  {
    key: "phase_other_response_transition",
    category: "other_response_transition",
    label: "Response transition",
    description: "One response.created event to the next response.created event when no finer client-visible boundary exists.",
    scope: "atomic",
    startLabel: "response.created #N",
    endLabel: "response.created #N+1",
    interpretation: "A high value means one response had begun but the next response was not created promptly. This can indicate response lifecycle completion, internal scheduling, or an unobserved continuation boundary.",
    caveats: [
      "The two boundaries are different response IDs even though they share the same event type.",
      "This interval must not be described as model-to-speech unless its end boundary is actually first audio.",
    ],
  },
  {
    key: "phase_other_speech",
    category: "other_speech",
    label: "Speech pipeline",
    description: "First text token to first audio; sentence segmentation, TTS, and transport cannot be separated.",
    scope: "atomic",
    startLabel: "First text token",
    endLabel: "First audio packet",
    interpretation: "A high value points somewhere after text generation began and before audio reached the browser: sentence chunking, TTS startup, service transport, or network delivery.",
    caveats: [
      "The browser does not receive separate TTS-request and TTS-first-byte timestamps.",
      "This phase is unavailable when audio arrives before any observable text token.",
    ],
  },
  {
    key: "phase_other_native",
    category: "other_native",
    label: "Model/speech",
    description: "response.created to audio on a path without an observable text or TTS boundary.",
    scope: "atomic",
    startLabel: "response.created",
    endLabel: "First audio packet",
    interpretation: "A high value identifies the combined model-to-speech path, typically on Native S2S, but cannot attribute the delay to model generation versus speech synthesis.",
    caveats: [
      "This combined phase is intentionally used only when no trustworthy intermediate text boundary exists.",
      "Do not compare it directly with Model or Speech pipeline as though they were simultaneous columns.",
    ],
  },
  {
    key: "phase_silence",
    category: "silence",
    label: "Leading silence",
    description: "First audio packet to the first voiced PCM frame contained in returned audio.",
    scope: "atomic",
    startLabel: "First audio packet",
    endLabel: "First voiced PCM",
    interpretation: "A high value means audio bytes arrived, but the returned PCM began with silence before audible speech.",
    caveats: [
      "Speech onset uses a 20ms peak detector with a 0.015 amplitude threshold.",
      "Low-volume speech or background noise can shift the detected onset.",
    ],
  },
  {
    key: "phase_playback",
    category: "playback",
    label: "Playback buffer",
    description: "First voiced PCM frame to the browser's scheduled playback time for that frame.",
    scope: "atomic",
    startLabel: "First voiced PCM",
    endLabel: "Scheduled playback",
    interpretation: "A high value means audible PCM was available but waited in the browser's Web Audio playback queue.",
    caveats: [
      "This is scheduled browser playback, not a hardware measurement of sound leaving the speaker.",
      "It is unavailable when media bypasses the PCM/Web Audio path, such as some WebRTC or Avatar flows.",
    ],
  },
  {
    key: "phase_other",
    category: "other",
    label: "Other",
    description: "Client-visible time for which no finer milestone boundary is available.",
    scope: "atomic",
    startLabel: "Observed milestone",
    endLabel: "Next observed milestone",
    interpretation: "A high value identifies a real measured gap, but the browser lacks enough intermediate events to assign it to a narrower subsystem.",
    caveats: [
      "The duration is measured, while its internal cause is unknown.",
      "Use protocol events, server traces, and orchestrator telemetry for further attribution.",
    ],
  },
];

const ALL_TURN_SUBSYSTEM_COLUMNS = [
  {
    key: "subsystem_input_speech",
    label: "Endpointing / EOU",
    tone: "vad",
    categories: ["endpointing_eou", "endpoint_candidate", "eou_inference", "eou_hold"],
    description: "Critical-path input speech endpointing and end-of-utterance decision time.",
    owner: "Voice Live turn detection",
    interpretation: "A high value points to VAD silence policy, Smart EOU inference, or EOU hold behavior.",
    actions: [
      "Candidate wait high: tune VAD profile/silence duration, while monitoring false endpoints and user truncation.",
      "EOU hold high: review Smart EOU threshold and timeout policy, including resumed-speech behavior.",
      "EOU inference high: profile model runtime, CPU scheduling, and inference frequency.",
    ],
    caveats: [
      "Transcript-completion STT is asynchronous and overlaps this critical path, so it is not added to Sum.",
      "Detailed attribution requires response.server_timing.",
    ],
  },
  {
    key: "subsystem_idle_timeout",
    label: "Idle timeout",
    tone: "other",
    categories: ["idle_timeout_wait"],
    description: "Configured silence-policy wait before an automatic timeout continuation.",
    owner: "Voice Live idle policy",
    interpretation: "A high value is normally the configured timeout duration, not slow inference.",
    actions: ["Review the configured idle timeout only if the product should prompt sooner."],
    caveats: [
      "This column appears only for timeout-triggered turns.",
      "It is derived from audio_end_ms - audio_start_ms in the timeout event.",
    ],
  },
  {
    key: "subsystem_orchestration",
    label: "Orchestration",
    tone: "orchestrator",
    categories: ["endpoint_delivery", "commit_dispatch", "response_schedule"],
    description: "Voice Live-owned endpoint delivery, audio commit, and response scheduling time.",
    owner: "Voice Live orchestration",
    interpretation: "A high value points to Voice Live queueing, commit handling, response ownership, or waiting for the previous response.",
    actions: [
      "Endpoint delivery high: inspect audio-pipeline backlog and event-loop starvation.",
      "Commit dispatch high: inspect audio draining, upstream write backpressure, and commit serialization.",
      "Response scheduling high: inspect previous-response completion, locks, response ownership, and admission guards.",
    ],
    caveats: [
      "Only phases with a server-owned boundary are assigned here.",
      "Unknown before-response time remains Unattributed rather than being blamed on Orchestration.",
    ],
  },
  {
    key: "subsystem_upstream",
    label: "Upstream admission",
    tone: "upstream",
    categories: ["upstream_admission"],
    description: "Response request dispatch to the upstream response.created acknowledgement.",
    owner: "Upstream deployment and network path",
    interpretation: "A high value points to provider network, deployment queueing, capacity, or admission latency before generation starts.",
    actions: [
      "Compare regions/deployments and P50/P95/P99 response dispatch-to-created latency.",
      "Check deployment capacity, throttling, connection reuse, and network path.",
    ],
    caveats: [
      "Upstream admission can include provider network and queue time, not only model compute.",
      "It ends at response.created and does not include model token generation.",
    ],
  },
  {
    key: "subsystem_model",
    label: "Model",
    tone: "model",
    categories: ["model"],
    description: "Observable model work from response.created to the first token or tool execution.",
    owner: "Model selection, prompt, and context",
    interpretation: "A high value points to model startup, prompt/context processing, reasoning, or tool-selection planning.",
    actions: [
      "Reduce prompt/context and unnecessary tool schemas; inspect token volume.",
      "Compare model/deployment latency and reasoning settings.",
      "Separate tool-planning turns from answer-generation turns before tuning.",
    ],
    caveats: [
      "Native speech-to-speech without a text boundary is left Unattributed rather than assigned to Model.",
      "This is client-observed and includes delivery of the first token event.",
    ],
  },
  {
    key: "subsystem_tools",
    label: "MCP / tools",
    tone: "tool",
    categories: ["tool"],
    description: "Observed MCP, Toolbox, Foundry IQ, and client function execution time.",
    owner: "Tool service and its caller",
    interpretation: "A high value points to the external tool, its service/network path, or the client-side function handler.",
    actions: [
      "Inspect per-tool duration and backend logs; optimize the slowest tool rather than the aggregate.",
      "Reuse connections, reduce payloads, parallelize independent calls, and review retries/timeouts.",
      "For MCP, separate initialize/tools/list overhead from tools/call execution.",
    ],
    caveats: [
      "This category includes non-MCP tools as well as MCP.",
      "Post-tool continuation time remains Unattributed unless a narrower boundary exists.",
    ],
  },
  {
    key: "subsystem_tts",
    label: "TTS / speech",
    tone: "tts",
    categories: ["other_speech", "silence"],
    description: "Text-to-audio speech pipeline time and leading silence in returned audio.",
    owner: "Voice Live speech output and TTS provider",
    interpretation: "A high value points to sentence segmentation, TTS startup, speech transport, or generated leading silence.",
    actions: [
      "Inspect text segmentation/flush timing and TTS request-to-first-byte latency.",
      "Compare voice/model/region and verify TTS connection reuse.",
      "If leading silence is high, inspect generated PCM and trim policy separately from synthesis startup.",
    ],
    caveats: [
      "The browser does not receive separate TTS request and first-byte timestamps.",
      "This category can include transport between Voice Live and the browser.",
    ],
  },
  {
    key: "subsystem_transport",
    label: "Transport",
    tone: "transport",
    categories: ["transport_residual"],
    description: "Client-observed time not covered by same-clock server timing durations.",
    owner: "Browser, proxy, network, or missing instrumentation",
    interpretation: "A high value points to browser, proxy, network, audio-pipeline, or another not-yet-instrumented boundary.",
    actions: [
      "Compare browser receive timestamps with server logs and inspect proxy/network RTT.",
      "Inspect chunk sizing, buffering, backpressure, and event-loop stalls.",
      "Add the next missing timing boundary before assigning the residual to one owner.",
    ],
    caveats: [
      "Residual is measured but not uniquely attributable to network.",
      "It preserves the invariant that subsystem columns add up to Total.",
    ],
  },
  {
    key: "subsystem_playback",
    label: "Playback",
    tone: "playback",
    categories: ["playback"],
    description: "Browser playback-queue time after voiced PCM is available.",
    owner: "Dashboard browser playback",
    interpretation: "A high value points to the browser Web Audio queue or local playback scheduling.",
    actions: [
      "Inspect queued audio depth, scheduling lead time, AudioContext state, and device/browser behavior.",
      "Reduce unnecessary client buffering without introducing underruns.",
    ],
    caveats: [
      "This is scheduled playback, not a hardware measurement.",
      "It can be unavailable for WebRTC or Avatar media paths.",
    ],
  },
  {
    key: "subsystem_unattributed",
    label: "Unattributed",
    tone: "other",
    categories: [
      "response_startup",
      "timeout_response_startup",
      "other_preresponse",
      "other_continuation",
      "other_response_transition",
      "other_native",
      "other",
    ],
    description: "Measured atomic phases that cannot be assigned to one optimization owner.",
    owner: "Unknown until another boundary is instrumented",
    interpretation: "A high value means another event boundary is needed before choosing an optimization owner.",
    actions: [
      "Do not tune a subsystem from this number alone.",
      "Inspect the turn's detailed timeline and server trace, then add the missing boundary or event.",
      "For Native model/speech, add a trustworthy model-to-speech boundary before assigning ownership.",
    ],
    caveats: [
      "This is real measured time, not an error or missing sample.",
      "Unknown future phase categories also fall back here rather than being silently dropped.",
    ],
  },
].map((column) => ({
  ...column,
  kind: "latency",
  scope: "subsystem",
  startLabel: "Included atomic phases",
  endLabel: `${column.label} total`,
  calculation: `Sum mutually exclusive atomic phases assigned to ${column.label}`,
  includedPhases: column.categories.map((category) => (
    ALL_TURN_PHASE_DEFINITIONS.find((definition) => definition.category === category)?.label
    || category
  )),
}));

const SUMMARY_SUBSYSTEM_BY_PHASE_CATEGORY = new Map(
  ALL_TURN_SUBSYSTEM_COLUMNS.flatMap((column) => (
    column.categories.map((category) => [category, column.key])
  )),
);

function mean(values) {
  const available = values.filter(isNumber);
  return available.length
    ? Math.round(available.reduce((sum, value) => sum + value, 0) / available.length)
    : null;
}

function subsystemValuesForPhases(phases = []) {
  const values = {};
  for (const phase of phases) {
    if (!isNumber(phase?.durationMs) || phase.durationMs < 0) continue;
    const key = SUMMARY_SUBSYSTEM_BY_PHASE_CATEGORY.get(phase.category)
      || "subsystem_unattributed";
    values[key] = (values[key] || 0) + phase.durationMs;
  }
  return values;
}

export function buildAllTurnLatencyTable(messages = []) {
  const turns = messages
    .filter((message) => (
      message?.type === "assistant"
      && message.metrics?.complete
      && isNumber(message.metrics.endToEndMs)
      && ["user_last_voiced", "server_vad", "text_input", "idle_timeout", "agent_playback_end"].includes(
        message.metrics.startSource,
      )
    ))
    .map((message, index) => {
      const values = {
        total: message.metrics.endToEndMs,
        tokens: message.metrics.totalTokens,
      };
      Object.assign(values, subsystemValuesForPhases(message.metrics.atomicPhases));
      return {
        id: message.id || `turn-${index + 1}`,
        turn: index + 1,
        responsePreview: String(message.content || "").replace(/\s+/g, " ").trim().slice(0, 100),
        values,
      };
    });

  const definitions = [
    {
      key: "total",
      label: "Total",
      kind: "latency",
      description: "Perceived wait to scheduled playback of this reply: from user/timeout start for the first reply, or from the previous Agent speech end for a consecutive reply.",
      scope: "envelope",
      startLabel: "Previous audible turn boundary",
      endLabel: "Agent speech/playback",
      interpretation: "This is the full observed wait before the Agent became audible. On idle-timeout turns, a high value is expected because Total includes the configured silence-policy window.",
      caveats: [
        "The preferred voice start is the last voiced microphone PCM sample; server speech_stopped is used only as an explicit proxy.",
        "Consecutive Agent replies start at the scheduled end of the previous reply's last voiced PCM frame.",
        "Idle-timeout turns start at timeout_triggered receipt minus the event's audio window duration.",
        "The preferred end is scheduled playback of first speech; first voiced PCM or first audio packet may be used when playback is unavailable.",
        "Total equals the sum of the mutually exclusive atomic phase columns.",
        "Per-turn TTFT and TTFA checkpoints overlap Total and are intentionally omitted from this summary table.",
      ],
    },
    ...ALL_TURN_SUBSYSTEM_COLUMNS
      .filter((definition) => turns.some((turn) => isNumber(turn.values[definition.key])))
      .map((definition) => ({ ...definition })),
    {
      key: "tokens",
      label: "Tokens",
      kind: "count",
      description: "Total model tokens reported across all responses belonging to this turn.",
      scope: "count",
      startLabel: "First response",
      endLabel: "Final response.done",
      interpretation: "A high token count indicates a larger prompt/context and/or generated output across the response chain. It can correlate with latency but is not itself a duration.",
      caveats: [
        "Tokens aggregate all response usage reported for the turn, including tool-call and continuation responses.",
        "Different models and tokenizers are not directly comparable.",
      ],
    },
  ];
  const columns = definitions.map((definition) => ({
    ...definition,
    average: mean(turns.map((turn) => turn.values[definition.key])),
  }));

  return {
    columns,
    rows: turns.map((turn) => ({
      ...turn,
      cells: Object.fromEntries(columns.map((column) => {
        const value = turn.values[column.key];
        const deltaPercent = isNumber(value) && isNumber(column.average) && column.average > 0
          ? Math.round(((value - column.average) / column.average) * 100)
          : null;
        const minimumDifference = column.kind === "latency" ? 100 : 50;
        return [column.key, {
          value,
          deltaPercent,
          outlier: isNumber(deltaPercent)
            && deltaPercent >= ALL_TURN_OUTLIER_PERCENT
            && value - column.average >= minimumDifference,
        }];
      })),
    })),
  };
}

function sumExclusionReason(message, ordinal) {
  const metrics = message?.metrics;
  const source = metrics?.startSource;
  if (source === "idle_timeout") return "Idle timeout response; no new user speech";
  if (source === "text_input") return "Text input; Sum includes spoken user turns only";
  if (source === "response_created") {
    return ordinal === 1
      ? "Initial greeting; no preceding user speech"
      : "Server-triggered response; no user-speech boundary";
  }
  if (!["user_last_voiced", "server_vad", "agent_playback_end"].includes(source)) {
    return "No recorded audible trigger boundary";
  }
  if (!metrics.complete) return "Response is not complete";
  if (!isNumber(metrics.endToEndMs)) return "No measurable Agent speech/playback";
  const phaseTotal = (metrics.atomicPhases || []).reduce(
    (sum, phase) => sum + (isNumber(phase?.durationMs) ? phase.durationMs : 0),
    0,
  );
  if (phaseTotal > metrics.endToEndMs + 1) {
    return "Phase durations exceed the measured turn total";
  }
  return null;
}

export function buildLatencySumAnalysis(messages = []) {
  const assistantMessages = messages.filter((message) => message?.type === "assistant");
  const included = [];
  const excluded = [];

  assistantMessages.forEach((message, index) => {
    const ordinal = index + 1;
    const reason = sumExclusionReason(message, ordinal);
    const entry = {
      id: message.id || `response-${ordinal}`,
      turn: ordinal,
      responsePreview: String(message.content || "").replace(/\s+/g, " ").trim().slice(0, 100),
    };
    if (reason) {
      excluded.push({ ...entry, reason });
      return;
    }

    const metrics = message.metrics;
    const values = subsystemValuesForPhases(metrics.atomicPhases);
    const phaseTotal = Object.values(values).reduce((sum, value) => sum + value, 0);
    const missingDuration = Math.max(0, metrics.endToEndMs - phaseTotal);
    if (missingDuration > 0) {
      values.subsystem_unattributed = (values.subsystem_unattributed || 0) + missingDuration;
    }
    included.push({ ...entry, durationMs: metrics.endToEndMs, values });
  });

  const totalDurationMs = included.reduce((sum, turn) => sum + turn.durationMs, 0);
  const subsystems = ALL_TURN_SUBSYSTEM_COLUMNS
    .filter((column) => column.key !== "subsystem_idle_timeout")
    .map((column) => {
      const durationMs = included.reduce((sum, turn) => sum + (turn.values[column.key] || 0), 0);
      return {
        key: column.key,
        label: column.label,
        tone: column.tone,
        description: column.description,
        owner: column.owner,
        actions: column.actions,
        caveats: column.caveats,
        includedPhases: column.includedPhases,
        durationMs,
        averageMs: included.length ? Math.round(durationMs / included.length) : null,
        averageTurnPercent: included.length
          ? Math.round(
            (
              included.reduce(
                (sum, turn) => sum + ((turn.values[column.key] || 0) / turn.durationMs) * 100,
                0,
              ) / included.length
            ) * 10,
          ) / 10
          : 0,
        percent: totalDurationMs > 0
          ? Math.round((durationMs / totalDurationMs) * 1000) / 10
          : 0,
      };
    })
    .filter((subsystem) => subsystem.durationMs > 0)
    .sort((left, right) => right.durationMs - left.durationMs);

  return {
    includedTurns: included,
    excludedTurns: excluded,
    totalDurationMs,
    subsystems,
  };
}

export function pcmVoiceOffsetsMs(
  bytes,
  {
    sampleRate = 24000,
    channels = 1,
    frameMs = 20,
    peakThreshold = 0.015,
  } = {},
) {
  if (!bytes || !bytes.byteLength || channels < 1 || sampleRate <= 0) {
    return { durationMs: 0, firstVoicedMs: null, lastVoicedMs: null };
  }
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const sampleCount = Math.floor(bytes.byteLength / 2);
  const audioFrameCount = Math.floor(sampleCount / channels);
  const detectorFrameSamples = Math.max(1, Math.round(sampleRate * frameMs / 1000));
  let firstVoicedFrame = null;
  let lastVoicedFrame = null;

  for (let frameStart = 0; frameStart < audioFrameCount; frameStart += detectorFrameSamples) {
    const frameEnd = Math.min(audioFrameCount, frameStart + detectorFrameSamples);
    let peak = 0;
    for (let audioFrame = frameStart; audioFrame < frameEnd; audioFrame++) {
      const sample = view.getInt16((audioFrame * channels) * 2, true);
      peak = Math.max(peak, Math.abs(sample) / 32768);
    }
    if (peak >= peakThreshold) {
      if (firstVoicedFrame == null) firstVoicedFrame = frameStart;
      lastVoicedFrame = frameEnd;
    }
  }

  return {
    durationMs: (audioFrameCount / sampleRate) * 1000,
    firstVoicedMs: firstVoicedFrame == null ? null : (firstVoicedFrame / sampleRate) * 1000,
    lastVoicedMs: lastVoicedFrame == null ? null : (lastVoicedFrame / sampleRate) * 1000,
  };
}

export function formatMetricMs(value) {
  if (!isNumber(value)) return "\u2014";
  const rounded = Math.max(0, Math.round(value));
  if (rounded < 1000) return `${rounded} ms`;
  const seconds = rounded / 1000;
  return `${seconds.toFixed(seconds >= 10 ? 1 : 2).replace(/\.?0+$/, "")} s`;
}
