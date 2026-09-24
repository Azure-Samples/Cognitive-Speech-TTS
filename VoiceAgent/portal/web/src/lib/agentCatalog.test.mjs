// Copyright (c) Microsoft. All rights reserved.

import test from "node:test";
import assert from "node:assert/strict";
import {
  assertBridgeCompatibleHostedAgent,
  asVoiceAgent,
  hostedAgentTargetPath,
  loadVoiceAgent,
  loadVoiceAgents,
  validateHostedAgentTarget,
} from "./agentCatalog.mjs";

function resource(name, kind, createdAt, definition = {}) {
  return {
    name,
    versions: {
      latest: {
        created_at: createdAt,
        definition: { kind, ...definition },
      },
    },
  };
}

test("normalizes voice agents and ignores other agent types", () => {
  assert.equal(asVoiceAgent(resource("prompt", "prompt", 1)), null);
  assert.deepEqual(
    asVoiceAgent(resource("voice", "voice", 2, {
      model_type: "self_deployed",
      model: "voice-deployment",
      store: true,
      audio: {
        input: {
          echo_cancellation: {
            type: "server_echo_cancellation",
            reference_source: "client",
            channels: 2,
          },
        },
        output: { voice: { name: "alloy" } },
      },
      avatar: {
        type: "video-avatar",
        character: "lisa",
        style: "casual-sitting",
        output_protocol: "webrtc",
      },
      greeting: {
        type: "template",
        text: "Hello.",
      },
      tools: [{ type: "function" }],
      handoff: { nodes: [], edges: [] },
    })),
    {
      name: "voice",
      model: "voice-deployment",
      voice: "alloy",
      avatar: {
        type: "video-avatar",
        character: "lisa",
        style: "casual-sitting",
        output_protocol: "webrtc",
      },
      greeting: {
        type: "template",
        text: "Hello.",
      },
      inferenceMode: "deployment",
      targetAgent: null,
      clientReferenceEc: true,
      store: true,
      toolCount: 1,
      handoff: { nodes: [], edges: [] },
      definition: {
        kind: "voice",
        model_type: "self_deployed",
        model: "voice-deployment",
        store: true,
        audio: {
          input: {
            echo_cancellation: {
              type: "server_echo_cancellation",
              reference_source: "client",
              channels: 2,
            },
          },
          output: { voice: { name: "alloy" } },
        },
        avatar: {
          type: "video-avatar",
          character: "lisa",
          style: "casual-sitting",
          output_protocol: "webrtc",
        },
        greeting: {
          type: "template",
          text: "Hello.",
        },
        tools: [{ type: "function" }],
        handoff: { nodes: [], edges: [] },
      },
      description: "",
      metadata: {},
      version: "",
      createdAt: 2,
    },
  );
});

test("normalizes hosted-agent voice wrappers", () => {
  const agent = asVoiceAgent(resource("voice-wrapper", "voice", 3, {
    model_type: "hosted_agent",
    target_agent: { name: "hosted-target", version: "2" },
    audio: { output: { voice: { name: "en-US-JennyNeural" } } },
  }));

  assert.equal(agent.inferenceMode, "hosted_agent");
  assert.deepEqual(agent.targetAgent, { name: "hosted-target", version: "2" });
  assert.equal(agent.model, "");
});

test("reads both current flat and legacy nested voice definitions", () => {
  for (const voice of ["en-US-AvaNeural", { type: "azure-standard", name: "en-US-AvaNeural" }]) {
    const agent = asVoiceAgent(resource("voice-agent", "voice", 3, {
      audio: { output: { voice, voice_type: "azure-standard" } },
    }));
    assert.equal(agent.voice, "en-US-AvaNeural");
    assert.deepEqual(agent.definition.audio.output.voice, voice);
  }
});

test("loads every page, filters voice agents, and sorts newest first", async () => {
  const calls = [];
  const pages = [
    {
      data: [
        resource("not-voice", "prompt", 30),
        resource("older-voice", "voice", 10, { model: "gpt-realtime" }),
      ],
      has_more: true,
      last_id: "older-voice",
    },
    {
      data: [resource("newer-voice", "voice", 20, {
        model_type: "managed",
        model: "gpt-realtime",
        audio_logging: "enabled",
      })],
      has_more: false,
    },
  ];
  const fetchImpl = async (path) => {
    calls.push(path);
    return { ok: true, json: async () => pages[calls.length - 1] };
  };

  const agents = await loadVoiceAgents(
    { apiVersion: "v1", foundryFeatures: "VoiceAgents=V1Preview" },
    fetchImpl,
  );

  assert.deepEqual(agents.map((agent) => agent.name), ["newer-voice", "older-voice"]);
  assert.equal(agents[0].store, true);
  assert.deepEqual(calls, [
    "/agents?api-version=v1&kind=voice&limit=100",
    "/agents?api-version=v1&kind=voice&limit=100&after=older-voice",
  ]);
});

test("loads one agent for the definition editor", async () => {
  const calls = [];
  const expected = resource("voice agent", "voice", 20, {
    model: "gpt-realtime",
  });
  const fetchImpl = async (path, options) => {
    calls.push({ path, options });
    return { ok: true, json: async () => expected };
  };

  const result = await loadVoiceAgent(
    { apiVersion: "v1", foundryFeatures: "VoiceAgents=V1Preview" },
    "voice agent",
    fetchImpl,
  );

  assert.equal(result, expected);
  assert.equal(
    calls[0].path,
    "/agents/voice%20agent?api-version=v1",
  );
  assert.equal(
    calls[0].options.headers["Foundry-Features"],
    "VoiceAgents=V1Preview",
  );
});

function bridgeTarget(name = "hosted-target", version = "5") {
  return {
    name,
    versions: {
      latest: {
        version,
        status: "active",
        metadata: {
          voiceLiveCompatible: "true",
          bridgeProtocolVersion: "1.0",
        },
        definition: {
          kind: "hosted",
          protocol_versions: [
            { protocol: "invocations_ws", version: "1.0.0" },
          ],
        },
      },
    },
  };
}

test("validates a bridge-compatible hosted target before wrapper creation", async () => {
  const cfg = { apiVersion: "v1", foundryFeatures: "VoiceAgents=V1Preview" };
  const calls = [];
  const fetchImpl = async (path, options) => {
    calls.push({ path, options });
    return { ok: true, status: 200, json: async () => bridgeTarget() };
  };

  const selected = await validateHostedAgentTarget(
    cfg,
    "hosted target",
    "",
    fetchImpl,
  );

  assert.equal(selected.version, "5");
  assert.equal(calls[0].path, "/agents/hosted%20target?api-version=v1");
});

test("reads and validates an explicitly pinned hosted target version", async () => {
  const cfg = { apiVersion: "v1", foundryFeatures: "VoiceAgents=V1Preview" };
  const selectedVersion = bridgeTarget().versions.latest;
  const fetchImpl = async (path) => {
    assert.equal(path, "/agents/hosted-target/versions/4?api-version=v1");
    return { ok: true, status: 200, json: async () => ({ ...selectedVersion, version: "4" }) };
  };

  const selected = await validateHostedAgentTarget(
    cfg,
    "hosted-target",
    "4",
    fetchImpl,
  );

  assert.equal(selected.version, "4");
  assert.equal(
    hostedAgentTargetPath(cfg, "hosted-target", "4"),
    "/agents/hosted-target/versions/4?api-version=v1",
  );
});

test("reports a missing hosted target explicitly", async () => {
  const fetchImpl = async () => ({
    ok: false,
    status: 404,
    json: async () => ({ error: { message: "not found" } }),
  });

  await assert.rejects(
    validateHostedAgentTarget(
      { apiVersion: "v1", foundryFeatures: "VoiceAgents=V1Preview" },
      "missing-target",
      "7",
      fetchImpl,
    ),
    /'missing-target:7' was not found in the selected Foundry project/,
  );
});

test("rejects a voice wrapper as a hosted target", () => {
  assert.throws(
    () => assertBridgeCompatibleHostedAgent(
      resource("voice-wrapper", "voice", 1, {
        model_type: "hosted_agent",
        target_agent: { name: "real-hosted-target" },
      }),
      "voice-wrapper",
      "",
    ),
    /kind 'voice'; expected a hosted agent/,
  );
});

test("reports every missing Bridge Protocol capability", () => {
  const target = bridgeTarget();
  target.versions.latest.definition.protocol_versions = [];
  target.versions.latest.metadata = {};

  assert.throws(
    () => assertBridgeCompatibleHostedAgent(target, "hosted-target", "5"),
    /missing invocations_ws 1.0.0, voiceLiveCompatible=true, bridgeProtocolVersion=1.0/,
  );
});
