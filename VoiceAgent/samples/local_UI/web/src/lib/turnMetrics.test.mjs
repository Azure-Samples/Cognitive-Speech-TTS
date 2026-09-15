// Copyright (c) Microsoft. All rights reserved.

import test from "node:test";
import assert from "node:assert/strict";
import {
  addResponseUsage,
  applyResponseServerTiming,
  buildAllTurnLatencyTable,
  buildLatencySumAnalysis,
  createTurnTracker,
  describeMcpTool,
  elapsedMetricMs,
  finishToolCall,
  formatMetricMs,
  indexSessionTools,
  latencyBarWidthPx,
  latencyRulerTicks,
  markFirstAudio,
  markFirstPlayback,
  markFirstSpeech,
  markFirstToken,
  markSpeechStopped,
  markTimeoutTriggered,
  pcmVoiceOffsetsMs,
  shouldFinalizeOnResponseDone,
  snapshotTurnMetrics,
  startAssistantResponse,
  startToolCall,
} from "./turnMetrics.mjs";

test("captures TTFT, TTFA, and total tokens for a normal turn", () => {
  const turn = createTurnTracker(1000, "user_last_voiced");
  markSpeechStopped(turn, "input-1", 1008);
  assert.equal(startAssistantResponse(turn, "response-1", 1010), "response-1");
  assert.equal(markFirstToken(turn, 1125), true);
  assert.equal(markFirstToken(turn, 1140), false);
  assert.equal(markFirstAudio(turn, 1180), true);
  assert.equal(markFirstAudio(turn, 1190), false);
  assert.equal(markFirstSpeech(turn, 1180), true);
  assert.equal(markFirstPlayback(turn, 1195), true);
  addResponseUsage(turn, { response: { usage: { total_tokens: 21 } } });

  assert.equal(shouldFinalizeOnResponseDone(turn), true);
  const snapshot = snapshotTurnMetrics(turn);
  assert.equal(snapshot.startSource, "user_last_voiced");
  assert.equal(snapshot.ttftMs, 125);
  assert.equal(snapshot.ttfaMs, 180);
  assert.equal(snapshot.endToEndMs, 195);
  assert.equal(snapshot.endSource, "playback");
  assert.equal(snapshot.totalTokens, 21);
  assert.deepEqual(
    snapshot.atomicPhases.map((phase) => [
      phase.label,
      phase.durationMs,
      phase.calculation,
    ]),
    [
      ["Other \u00b7 before response", 10, "last voiced microphone PCM \u2192 response.created #1 (response-1)"],
      ["Model \u00b7 first token", 115, "response.created #1 (response-1) \u2192 first Agent text token"],
      ["TTS / speech pipeline", 55, "first Agent text token \u2192 first voiced PCM frame"],
      ["Playback buffer", 15, "first voiced PCM frame \u2192 scheduled playback of first speech"],
    ],
  );
  assert.deepEqual(
    snapshot.atomicPhases.map((phase) => phase.tone),
    ["other", "model", "tts", "playback"],
  );
});

test("does not split audio latency at a text token that arrived later", () => {
  const turn = createTurnTracker(1000, "user_last_voiced");
  startAssistantResponse(turn, "response-1", 1100);
  markFirstAudio(turn, 1200);
  markFirstToken(turn, 1250);
  markFirstSpeech(turn, 1300);
  markFirstPlayback(turn, 1320);

  const snapshot = snapshotTurnMetrics(turn);
  assert.deepEqual(
    snapshot.atomicPhases.map(({ label, durationMs }) => [label, durationMs]),
    [
      ["Other \u00b7 before response", 100],
      ["Model / speech (combined)", 100],
      ["Leading silence", 100],
      ["Playback buffer", 20],
    ],
  );
});

test("expands opted-in server timing and reconciles transport residuals", () => {
  const turn = createTurnTracker(1000, "user_last_voiced");
  markSpeechStopped(turn, "input-1", 4000);
  startAssistantResponse(turn, "response-1", 4100);
  assert.equal(applyResponseServerTiming(turn, {
    type: "response.server_timing",
    input_item_id: "input-1",
    response_id: "response-1",
    server_timing: {
      version: 1,
      turn_detection_mode: "azure_semantic_vad",
      endpoint_candidate_wait_ms: 800,
      eou_inference_ms: 20,
      eou_hold_ms: 2000,
      eou_inference_count: 3,
      eou_forced_by_timeout: true,
      endpoint_delivery_ms: 10,
      endpoint_to_commit_sent_ms: 10,
      response_schedule_wait_ms: 20,
      response_dispatch_to_created_ms: 50,
    },
  }), true);
  markFirstAudio(turn, 4200);
  markFirstSpeech(turn, 4200);

  const snapshot = snapshotTurnMetrics(turn);
  assert.deepEqual(
    snapshot.atomicPhases.map((phase) => [phase.label, phase.durationMs]),
    [
      ["Endpoint candidate wait", 800],
      ["EOU inference", 20],
      ["EOU hold", 2000],
      ["Endpoint delivery", 10],
      ["Transport / pipeline residual", 170],
      ["Commit dispatch", 10],
      ["Response scheduling", 20],
      ["Upstream admission", 50],
      ["Transport / pipeline residual", 20],
      ["Model / speech (combined)", 100],
    ],
  );
  assert.deepEqual(
    snapshot.atomicPhases.map((phase) => phase.tone),
    [
      "vad",
      "vad",
      "vad",
      "orchestrator",
      "transport",
      "orchestrator",
      "orchestrator",
      "upstream",
      "transport",
      "model",
    ],
  );
  assert.equal(
    snapshot.atomicPhases.reduce((sum, phase) => sum + phase.durationMs, 0),
    snapshot.endToEndMs,
  );
  assert.equal(snapshot.serverTiming.eou_forced_by_timeout, true);
});

test("rejects server timing for another input or response", () => {
  const turn = createTurnTracker(1000, "user_last_voiced");
  markSpeechStopped(turn, "input-1", 1100);
  startAssistantResponse(turn, "response-1", 1200);
  const event = {
    input_item_id: "input-2",
    response_id: "response-1",
    server_timing: { version: 1 },
  };
  assert.equal(applyResponseServerTiming(turn, event), false);
  assert.equal(applyResponseServerTiming(turn, {
    ...event,
    input_item_id: "input-1",
    response_id: "response-2",
  }), false);
  assert.equal(turn.serverTiming, null);
});

test("reconciles a one-millisecond server/client rounding overflow", () => {
  const turn = createTurnTracker(1000, "user_last_voiced");
  markSpeechStopped(turn, "input-1", 1100);
  startAssistantResponse(turn, "response-1", 1200);
  markFirstAudio(turn, 1200);
  markFirstSpeech(turn, 1200);
  applyResponseServerTiming(turn, {
    input_item_id: "input-1",
    response_id: "response-1",
    server_timing: {
      version: 1,
      endpoint_candidate_wait_ms: 99,
      endpoint_delivery_ms: 2,
      endpoint_to_commit_sent_ms: 50,
      response_schedule_wait_ms: 51,
    },
  });

  assert.deepEqual(
    snapshotTurnMetrics(turn).atomicPhases.map((phase) => [phase.label, phase.durationMs]),
    [
      ["Endpoint candidate wait", 98],
      ["Endpoint delivery", 2],
      ["Commit dispatch", 50],
      ["Response scheduling", 50],
    ],
  );
  const adjusted = snapshotTurnMetrics(turn).atomicPhases.filter(
    (phase) => phase.boundaryAdjustmentMs,
  );
  assert.deepEqual(
    adjusted.map((phase) => [phase.label, phase.reportedDurationMs, phase.boundaryAdjustmentMs]),
    [
      ["Endpoint candidate wait", 99, -1],
      ["Response scheduling", 51, -1],
    ],
  );
});

test("expands the Finance local-session timing shape instead of falling back", () => {
  const turn = createTurnTracker(7000, "user_last_voiced");
  markSpeechStopped(turn, "item-finance", 7945);
  startAssistantResponse(turn, "response-finance", 8043);
  applyResponseServerTiming(turn, {
    input_item_id: "item-finance",
    response_id: "response-finance",
    server_timing: {
      version: 1,
      endpoint_candidate_wait_ms: 832,
      eou_inference_ms: 37,
      eou_hold_ms: 0,
      endpoint_delivery_ms: 0,
      endpoint_to_commit_sent_ms: 1,
      response_schedule_wait_ms: 0,
      response_dispatch_to_created_ms: 98,
    },
  });
  markFirstAudio(turn, 8500);
  markFirstSpeech(turn, 8500);

  const phases = snapshotTurnMetrics(turn).atomicPhases;
  assert.deepEqual(
    phases.map((phase) => [phase.label, phase.durationMs]),
    [
      ["Endpoint candidate wait", 832],
      ["EOU inference", 37],
      ["Transport / pipeline residual", 76],
      ["Commit dispatch", 1],
      ["Upstream admission", 97],
      ["Model / speech (combined)", 457],
    ],
  );
  assert.equal(phases.reduce((sum, phase) => sum + phase.durationMs, 0), 1500);
  assert.equal(phases[4].reportedDurationMs, 98);
  assert.equal(phases[4].boundaryAdjustmentMs, -1);
});

test("keeps the original bar when server durations materially exceed the observed interval", () => {
  const turn = createTurnTracker(1000, "user_last_voiced");
  markSpeechStopped(turn, "input-1", 1100);
  startAssistantResponse(turn, "response-1", 1200);
  markFirstAudio(turn, 1200);
  markFirstSpeech(turn, 1200);
  applyResponseServerTiming(turn, {
    input_item_id: "input-1",
    response_id: "response-1",
    server_timing: {
      version: 1,
      endpoint_candidate_wait_ms: 120,
      endpoint_to_commit_sent_ms: 120,
    },
  });

  assert.deepEqual(
    snapshotTurnMetrics(turn).atomicPhases.map((phase) => [phase.label, phase.durationMs]),
    [["Other \u00b7 before response", 200]],
  );
});

test("keeps the original bar when a server timing event has no usable durations", () => {
  const turn = createTurnTracker(1000, "user_last_voiced");
  markSpeechStopped(turn, "input-1", 1100);
  startAssistantResponse(turn, "response-1", 1200);
  markFirstAudio(turn, 1250);
  markFirstSpeech(turn, 1250);
  applyResponseServerTiming(turn, {
    input_item_id: "input-1",
    response_id: "response-1",
    server_timing: {
      version: 1,
      turn_detection_mode: "azure_semantic_vad",
      eou_forced_by_timeout: false,
    },
  });

  assert.deepEqual(
    snapshotTurnMetrics(turn).atomicPhases.map((phase) => [phase.label, phase.durationMs]),
    [
      ["Other \u00b7 before response", 200],
      ["Model / speech (combined)", 50],
    ],
  );
});

test("includes the silence window in an idle-timeout turn", () => {
  const turn = createTurnTracker(5000, "idle_timeout");
  markTimeoutTriggered(turn, "timeout-item", 20000, 70900, 85900);
  startAssistantResponse(turn, "timeout-response", 20572);
  markFirstAudio(turn, 21200);
  markFirstSpeech(turn, 21200);

  const snapshot = snapshotTurnMetrics(turn);
  assert.equal(snapshot.endToEndMs, 16200);
  assert.equal(snapshot.timeoutWindowMs, 15000);
  assert.deepEqual(
    snapshot.atomicPhases.map((phase) => [phase.label, phase.durationMs]),
    [
      ["Idle timeout wait", 15000],
      ["Timeout response startup", 572],
      ["Model / speech (combined)", 628],
    ],
  );
  assert.equal(
    snapshot.atomicPhases.reduce((sum, phase) => sum + phase.durationMs, 0),
    snapshot.endToEndMs,
  );

  const table = buildAllTurnLatencyTable([{
    id: "timeout-answer",
    type: "assistant",
    content: "Are you still there?",
    metrics: { ...snapshot, complete: true },
  }]);
  assert.equal(table.rows.length, 1);
  assert.equal(table.rows[0].values.subsystem_idle_timeout, 15000);
  assert.equal(table.rows[0].values.subsystem_unattributed, 1200);
});

test("still captures TTFT when audio arrives before the terminal transcript", () => {
  const turn = createTurnTracker(1000);
  startAssistantResponse(turn, "response-audio-first", 1010);
  assert.equal(markFirstAudio(turn, 1100), true);
  assert.equal(turn.currentResponseHasToken, false);
  assert.equal(markFirstToken(turn, 1220), true);

  assert.equal(snapshotTurnMetrics(turn).ttftMs, 220);
});

test("keeps unrendered audio as TTFA diagnostics without ending audible latency", () => {
  const turn = createTurnTracker(1000, "user_last_voiced");
  startAssistantResponse(turn, "response-unrendered", 1100);
  markFirstAudio(turn, 1200);

  const snapshot = snapshotTurnMetrics(turn);
  assert.equal(snapshot.ttfaMs, 200);
  assert.equal(snapshot.speechGapMs, null);
  assert.equal(snapshot.playbackMs, null);
  assert.equal(snapshot.endToEndMs, null);
  assert.equal(snapshot.endSource, null);
  assert.deepEqual(snapshot.atomicPhases, []);
});

test("accumulates usage and carries a tool duration into the follow-up answer", () => {
  const turn = createTurnTracker(2000);
  assert.equal(startAssistantResponse(turn, "response-tool", 2010), "response-tool");
  startToolCall(turn, "call-1", 2150, { kind: "Toolbox", name: "web_search" }, true);
  addResponseUsage(turn, { response: { usage: { input_tokens: 4, output_tokens: 2 } } });
  assert.equal(shouldFinalizeOnResponseDone(turn), false);

  finishToolCall(turn, "call-1", 2650, "completed");
  assert.equal(startAssistantResponse(turn, "response-answer", 2700), "response-tool");
  markFirstToken(turn, 2750);
  markFirstAudio(turn, 2810);
  markFirstSpeech(turn, 2810);
  addResponseUsage(turn, { response: { usage: { total_tokens: 9 } } });

  assert.equal(shouldFinalizeOnResponseDone(turn), true);
  const snapshot = snapshotTurnMetrics(turn);
  assert.deepEqual(snapshot.tools, [{
      id: "call-1",
      kind: "Toolbox",
      name: "web_search",
      status: "completed",
      durationMs: 500,
  }]);
  assert.equal(snapshot.endToEndMs, 810);
  assert.equal(snapshot.atomicPhases.reduce((sum, phase) => sum + phase.durationMs, 0), 810);
  assert.deepEqual(
    snapshot.atomicPhases.map((phase) => [phase.label, phase.durationMs]),
    [
      ["Other \u00b7 before response", 10],
      ["Model \u00b7 tool planning", 140],
      ["Toolbox web_search", 500],
      ["Other \u00b7 continuation", 50],
      ["Model \u00b7 first token", 50],
      ["TTS / speech pipeline", 60],
    ],
  );
});

test("distinguishes consecutive response.created events from model-to-speech time", () => {
  const turn = createTurnTracker(1000, "user_last_voiced");
  startAssistantResponse(turn, "response-one", 1100);
  startAssistantResponse(turn, "response-two", 1400);
  markFirstAudio(turn, 1600);
  markFirstSpeech(turn, 1600);

  const phases = snapshotTurnMetrics(turn).atomicPhases;
  assert.deepEqual(
    phases.map((phase) => [phase.label, phase.calculation]),
    [
      ["Other \u00b7 before response", "last voiced microphone PCM \u2192 response.created #1 (response-one)"],
      ["Other \u00b7 response transition", "response.created #1 (response-one) \u2192 response.created #2 (response-two)"],
      ["Model / speech (combined)", "response.created #2 (response-two) \u2192 first voiced PCM frame"],
    ],
  );
});

test("classifies MCP, toolbox, and Foundry IQ calls from the session tool list", () => {
  const index = indexSessionTools([
    { type: "mcp", server_label: "crm", server_url: "https://crm.example/mcp" },
    { type: "foundry_toolbox", server_label: "foundry-tools-test" },
    {
      type: "mcp",
      server_label: "kb-foundry-iq",
      server_url: "https://search.example/knowledgebases/kb/mcp",
    },
  ]);

  assert.equal(describeMcpTool({ server_label: "crm", name: "lookup" }, index).kind, "MCP");
  assert.equal(
    describeMcpTool({ server_label: "foundry-tools-test", name: "web_search" }, index).kind,
    "Toolbox",
  );
  assert.equal(
    describeMcpTool({ server_label: "kb-foundry-iq", name: "knowledge_base_retrieve" }, index).kind,
    "Foundry IQ",
  );
});

test("measures tool execution from in_progress rather than argument generation", () => {
  const turn = createTurnTracker(0);
  startToolCall(turn, "call-2", 100, { kind: "MCP", name: "lookup" }, false);
  startToolCall(turn, "call-2", 160, {}, true);
  finishToolCall(turn, "call-2", 460, "completed");

  assert.equal(snapshotTurnMetrics(turn).tools[0].durationMs, 300);
});

test("measures STT from speech start to transcription completion", () => {
  assert.equal(elapsedMetricMs(1000, 1465), 465);
  assert.equal(elapsedMetricMs(null, 1465), null);
});

test("formats compact latency values for the message footer", () => {
  assert.equal(formatMetricMs(null), "\u2014");
  assert.equal(formatMetricMs(347), "347 ms");
  assert.equal(formatMetricMs(1250), "1.25 s");
  assert.equal(formatMetricMs(12000), "12 s");
});

test("detects first and last voiced PCM frames", () => {
  const samples = new Int16Array(480 * 3);
  samples.fill(1200, 480, 960);

  assert.deepEqual(pcmVoiceOffsetsMs(new Uint8Array(samples.buffer)), {
    durationMs: 60,
    firstVoicedMs: 20,
    lastVoicedMs: 40,
  });
});

test("uses an uncapped fixed 160-pixel-per-second latency scale", () => {
  assert.equal(latencyBarWidthPx(0), 0);
  assert.equal(latencyBarWidthPx(1000), 160);
  assert.equal(latencyBarWidthPx(2500), 400);
  assert.deepEqual(latencyRulerTicks(2500), [0, 1, 2, 3]);
});

test("atomic phase rounding always adds up to the end-to-end checkpoint", () => {
  const turn = createTurnTracker(1000.2, "user_last_voiced");
  startAssistantResponse(turn, "response-fractional", 1100.7);
  markFirstToken(turn, 1200.2);
  markFirstAudio(turn, 1300.7);
  markFirstSpeech(turn, 1310.2);
  markFirstPlayback(turn, 1320.7);

  const snapshot = snapshotTurnMetrics(turn);
  assert.equal(
    snapshot.atomicPhases.reduce((sum, phase) => sum + phase.durationMs, 0),
    snapshot.endToEndMs,
  );
});

test("builds all-turn averages, deltas, and high outlier flags", () => {
  const message = (id, total, model, tokens) => ({
    id,
    type: "assistant",
    content: `answer ${id}`,
    metrics: {
      complete: true,
      startSource: "user_last_voiced",
      endToEndMs: total,
      ttftMs: total - 200,
      ttfaMs: total - 100,
      totalTokens: tokens,
      atomicPhases: [{
        category: "model",
        durationMs: model,
      }],
    },
  });
  const table = buildAllTurnLatencyTable([
    message("one", 1000, 100, 100),
    message("two", 1000, 100, 100),
    message("three", 2500, 1000, 400),
  ]);

  assert.deepEqual(
    table.columns.map((column) => [column.key, column.average]),
    [
      ["total", 1500],
      ["subsystem_model", 400],
      ["tokens", 200],
    ],
  );
  assert.equal(table.rows[2].cells.total.deltaPercent, 67);
  assert.equal(table.rows[2].cells.total.outlier, true);
  assert.equal(table.rows[2].cells.subsystem_model.deltaPercent, 150);
  assert.equal(table.rows[2].cells.subsystem_model.outlier, true);
  assert.equal(table.rows[0].cells.total.deltaPercent, -33);
  assert.equal(table.rows[0].cells.total.outlier, false);
  assert.equal(table.columns.every((column) => (
    column.description.length > 0
    && column.scope.length > 0
    && column.startLabel.length > 0
    && column.endLabel.length > 0
    && column.interpretation.length > 0
    && column.caveats.length > 0
  )), true);
});

test("groups all-turn phases by optimization subsystem instead of timeline order", () => {
  const atomicPhases = [
    ["endpoint_candidate", 10],
    ["eou_hold", 20],
    ["endpoint_delivery", 5],
    ["response_schedule", 7],
    ["upstream_admission", 30],
    ["model", 40],
    ["other_native", 50],
    ["tool", 60],
    ["other_speech", 70],
    ["silence", 10],
    ["transport_residual", 20],
    ["playback", 15],
    ["other_preresponse", 25],
  ].map(([category, durationMs]) => ({ category, durationMs }));
  const table = buildAllTurnLatencyTable([{
    id: "grouped",
    type: "assistant",
    content: "grouped answer",
    metrics: {
      complete: true,
      startSource: "user_last_voiced",
      endToEndMs: 362,
      totalTokens: 10,
      atomicPhases,
    },
  }]);

  assert.deepEqual(
    table.columns.map((column) => column.key),
    [
      "total",
      "subsystem_input_speech",
      "subsystem_orchestration",
      "subsystem_upstream",
      "subsystem_model",
      "subsystem_tools",
      "subsystem_tts",
      "subsystem_transport",
      "subsystem_playback",
      "subsystem_unattributed",
      "tokens",
    ],
  );
  assert.deepEqual(
    table.columns.slice(1, -1).map((column) => table.rows[0].cells[column.key].value),
    [30, 12, 30, 40, 60, 80, 20, 15, 75],
  );
  assert.equal(
    table.columns.slice(1, -1).reduce(
      (sum, column) => sum + table.rows[0].cells[column.key].value,
      0,
    ),
    table.rows[0].cells.total.value,
  );
  assert.equal(table.columns[1].scope, "subsystem");
  assert.deepEqual(
    table.columns[1].includedPhases,
    ["Endpointing + EOU", "Endpoint candidate", "EOU inference", "EOU hold"],
  );
});

test("sums only completed user-speech replies and explains every excluded response", () => {
  const assistant = (id, startSource, durationMs, atomicPhases, complete = true) => ({
    id,
    type: "assistant",
    content: `answer ${id}`,
    metrics: {
      complete,
      startSource,
      endToEndMs: durationMs,
      atomicPhases,
    },
  });
  const analysis = buildLatencySumAnalysis([
    assistant("greeting", "response_created", 100, [{ category: "model", durationMs: 100 }]),
    { id: "user-1", type: "user", content: "hello" },
    assistant("voice-1", "user_last_voiced", 300, [
      { category: "endpoint_candidate", durationMs: 100 },
      { category: "response_schedule", durationMs: 50 },
      { category: "model", durationMs: 150 },
    ]),
    assistant("idle", "idle_timeout", 5000, [{ category: "idle_timeout_wait", durationMs: 5000 }]),
    assistant("text", "text_input", 200, [{ category: "model", durationMs: 200 }]),
    assistant("voice-2", "server_vad", 500, [
      { category: "tool", durationMs: 300 },
      { category: "other_speech", durationMs: 150 },
    ]),
    assistant("streaming", "user_last_voiced", 100, [{ category: "model", durationMs: 100 }], false),
  ]);

  assert.deepEqual(analysis.includedTurns.map((turn) => turn.id), ["voice-1", "voice-2"]);
  assert.equal(analysis.totalDurationMs, 800);
  assert.deepEqual(
    analysis.subsystems.map(({ label, durationMs, percent }) => [label, durationMs, percent]),
    [
      ["MCP / tools", 300, 37.5],
      ["Model", 150, 18.8],
      ["TTS / speech", 150, 18.8],
      ["Endpointing / EOU", 100, 12.5],
      ["Orchestration", 50, 6.3],
      ["Unattributed", 50, 6.3],
    ],
  );
  assert.deepEqual(
    analysis.subsystems.map(({ label, averageMs, averageTurnPercent }) => (
      [label, averageMs, averageTurnPercent]
    )),
    [
      ["MCP / tools", 150, 30],
      ["Model", 75, 25],
      ["TTS / speech", 75, 15],
      ["Endpointing / EOU", 50, 16.7],
      ["Orchestration", 25, 8.3],
      ["Unattributed", 25, 5],
    ],
  );
  assert.deepEqual(
    analysis.excludedTurns.map((turn) => [turn.id, turn.reason]),
    [
      ["greeting", "Initial greeting; no preceding user speech"],
      ["idle", "Idle timeout response; no new user speech"],
      ["text", "Text input; Sum includes spoken user turns only"],
      ["streaming", "Response is not complete"],
    ],
  );
  assert.equal(
    analysis.subsystems.reduce((sum, subsystem) => sum + subsystem.durationMs, 0),
    analysis.totalDurationMs,
  );
});
