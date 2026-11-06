// Copyright (c) Microsoft. All rights reserved.

import test from "node:test";
import assert from "node:assert/strict";
import { AudioHandler, shouldRenderPcmOutput } from "./audio.js";

test("renders PCM only when the browser playback path is audible", () => {
  assert.equal(shouldRenderPcmOutput(false, false, "websocket"), true);
  assert.equal(shouldRenderPcmOutput(true, false, "websocket"), false);
  assert.equal(shouldRenderPcmOutput(false, true, "websocket"), false);
  assert.equal(shouldRenderPcmOutput(false, false, "webrtc"), false);
});

test("stops a microphone stream that arrives after disposal", async () => {
  const originalNavigator = globalThis.navigator;
  const originalAudioWorkletNode = globalThis.AudioWorkletNode;
  let resolveMedia;
  let stopped = 0;
  let sourceCreated = 0;
  const stream = {
    getTracks: () => [{ stop: () => { stopped += 1; } }],
  };
  Object.defineProperty(globalThis, "navigator", {
    configurable: true,
    value: {
      mediaDevices: {
        getUserMedia: () => new Promise((resolve) => { resolveMedia = resolve; }),
      },
    },
  });
  globalThis.AudioWorkletNode = class {};

  try {
    const handler = new AudioHandler();
    handler.context = {
      close: () => {},
      createMediaStreamSource: () => {
        sourceCreated += 1;
        return { connect: () => {} };
      },
    };
    handler.initialize = async () => {};

    const starting = handler.startRecording(() => {});
    await Promise.resolve();
    handler.dispose();
    resolveMedia(stream);
    await starting;

    assert.equal(stopped, 1);
    assert.equal(sourceCreated, 0);
    assert.equal(handler.stream, null);
  } finally {
    Object.defineProperty(globalThis, "navigator", {
      configurable: true,
      value: originalNavigator,
    });
    globalThis.AudioWorkletNode = originalAudioWorkletNode;
  }
});

test("routes microphone and rendered playback into a stereo capture worklet", async () => {
  const originalNavigator = globalThis.navigator;
  const originalAudioWorkletNode = globalThis.AudioWorkletNode;
  const connections = [];
  let mediaConstraints;
  let workletOptions;
  const destination = {};
  const stream = { getTracks: () => [] };
  const source = {
    connect: (...args) => connections.push(["microphone", ...args]),
    disconnect: () => {},
  };
  const playbackBus = {
    connect: (...args) => connections.push(["playback", ...args]),
    disconnect: () => {},
  };

  Object.defineProperty(globalThis, "navigator", {
    configurable: true,
    value: {
      mediaDevices: {
        getUserMedia: async (constraints) => {
          mediaConstraints = constraints;
          return stream;
        },
      },
    },
  });
  globalThis.AudioWorkletNode = class {
    constructor(_context, _name, options) {
      workletOptions = options;
      this.port = { onmessage: null, postMessage: () => {} };
    }
    disconnect() {}
  };

  try {
    const handler = new AudioHandler(undefined, { clientReferenceEc: true });
    handler.context = {
      currentTime: 0,
      destination,
      createGain: () => playbackBus,
      createMediaStreamSource: () => source,
    };
    handler.initialize = async () => handler.ensurePlaybackBus();

    await handler.startRecording(() => {});

    assert.deepEqual(mediaConstraints.audio, {
      channelCount: 1,
      echoCancellation: false,
      noiseSuppression: false,
      autoGainControl: false,
    });
    assert.deepEqual(workletOptions, {
      numberOfInputs: 2,
      numberOfOutputs: 1,
      outputChannelCount: [1],
      processorOptions: { channelCount: 2 },
    });
    assert.deepEqual(connections, [
      ["playback", destination],
      ["microphone", handler.workletNode, 0, 0],
      ["playback", handler.workletNode, 0, 1],
    ]);
  } finally {
    Object.defineProperty(globalThis, "navigator", {
      configurable: true,
      value: originalNavigator,
    });
    globalThis.AudioWorkletNode = originalAudioWorkletNode;
  }
});

test("mixes shared tab audio with assistant playback in the reference channel", async () => {
  const originalNavigator = globalThis.navigator;
  const originalAudioWorkletNode = globalThis.AudioWorkletNode;
  const connections = [];
  const microphoneStream = { getTracks: () => [] };
  const sharedTracks = [
    { kind: "audio", stop: () => {}, onended: null },
    { kind: "video", stop: () => {}, onended: null },
  ];
  const sharedStream = {
    getAudioTracks: () => sharedTracks.filter((track) => track.kind === "audio"),
    getTracks: () => sharedTracks,
  };
  const microphoneSource = {
    connect: (...args) => connections.push(["microphone", ...args]),
    disconnect: () => {},
  };
  const sharedSource = {
    connect: (...args) => connections.push(["shared", ...args]),
    disconnect: () => {},
  };
  const playbackBus = {
    connect: (...args) => connections.push(["playback", ...args]),
    disconnect: () => {},
  };

  Object.defineProperty(globalThis, "navigator", {
    configurable: true,
    value: {
      mediaDevices: {
        getDisplayMedia: async () => sharedStream,
        getUserMedia: async () => microphoneStream,
      },
    },
  });
  globalThis.AudioWorkletNode = class {
    constructor() { this.port = { onmessage: null, postMessage: () => {} }; }
    disconnect() {}
  };

  try {
    const handler = new AudioHandler(undefined, {
      clientReferenceEc: true,
      referenceAudioMode: "shared-additive",
    });
    const destination = {};
    handler.context = {
      currentTime: 0,
      destination,
      createGain: () => playbackBus,
      createMediaStreamSource: (stream) => (
        stream === sharedStream ? sharedSource : microphoneSource
      ),
    };
    handler.initialize = async () => handler.ensurePlaybackBus();

    await handler.prepareReferenceCapture();
    await handler.startRecording(() => {});

    assert.deepEqual(connections, [
      ["playback", destination],
      ["microphone", handler.workletNode, 0, 0],
      ["playback", handler.workletNode, 0, 1],
      ["shared", handler.workletNode, 0, 1],
    ]);
  } finally {
    Object.defineProperty(globalThis, "navigator", {
      configurable: true,
      value: originalNavigator,
    });
    globalThis.AudioWorkletNode = originalAudioWorkletNode;
  }
});

test("rejects a screen share that does not include audio", async () => {
  const originalNavigator = globalThis.navigator;
  let stopped = 0;
  Object.defineProperty(globalThis, "navigator", {
    configurable: true,
    value: {
      mediaDevices: {
        getDisplayMedia: async () => ({
          getAudioTracks: () => [],
          getTracks: () => [{ stop: () => { stopped += 1; } }],
        }),
      },
    },
  });

  try {
    const handler = new AudioHandler(undefined, {
      clientReferenceEc: true,
      referenceAudioMode: "shared-system",
    });
    await assert.rejects(
      handler.prepareReferenceCapture(),
      /selected share has no audio/,
    );
    assert.equal(stopped, 1);
  } finally {
    Object.defineProperty(globalThis, "navigator", {
      configurable: true,
      value: originalNavigator,
    });
  }
});

test("uses a full system mix without duplicating the direct assistant tap", async () => {
  const handler = new AudioHandler(undefined, {
    clientReferenceEc: true,
    referenceAudioMode: "shared-system",
  });

  assert.equal(handler.usesSharedReference(), true);
  assert.equal(handler.usesAssistantReference(), false);
});

test("waits for every scheduled playback source to finish", async () => {
  const sources = [];
  const handler = new AudioHandler();
  handler.context = {
    currentTime: 0,
    destination: {},
    createBuffer: (_channels, length, sampleRate) => ({
      duration: length / sampleRate,
      getChannelData: () => new Float32Array(length),
    }),
    createBufferSource: () => {
      const source = {
        buffer: null,
        connect: () => {},
        disconnect: () => {},
        start: () => {},
        stop: () => {},
        onended: null,
      };
      sources.push(source);
      return source;
    },
  };
  handler.startStreamingPlayback();
  handler.playChunk(new Uint8Array([0, 0, 1, 0]));
  handler.playChunk(new Uint8Array([2, 0, 3, 0]));

  let finished = false;
  const waiting = handler.waitForPlaybackComplete().then(() => {
    finished = true;
  });
  await Promise.resolve();
  assert.equal(finished, false);

  sources[0].onended();
  await Promise.resolve();
  assert.equal(finished, false);

  sources[1].onended();
  await waiting;
  assert.equal(finished, true);
  assert.equal(handler.isPlaying, false);
});

test("explicit playback stop releases waiters and discards scheduled speech end", async () => {
  const handler = new AudioHandler();
  handler.lastScheduledSpeechEndAtMs = performance.now() + 1000;
  handler.playbackQueue = [{
    onended: () => {},
    disconnect: () => {},
    stop: () => {},
  }];
  const waiting = handler.waitForPlaybackComplete();

  handler.stopStreamingPlayback();

  await waiting;
  assert.deepEqual(handler.playbackQueue, []);
  assert.equal(handler.getLastScheduledSpeechEndAtMs(), null);
});

test("records the scheduled end of voiced playback for the next perceived-latency origin", () => {
  const handler = new AudioHandler();
  handler.context = {
    currentTime: 1,
    destination: {},
    createBuffer: (_channels, length, sampleRate) => ({
      duration: length / sampleRate,
      getChannelData: () => new Float32Array(length),
    }),
    createBufferSource: () => ({
      buffer: null,
      connect: () => {},
      start: () => {},
      onended: null,
    }),
  };
  handler.startStreamingPlayback();
  handler.beginResponsePlayback();
  const before = performance.now();

  handler.playChunk(new Uint8Array(4800), 20, 80);

  const speechEnd = handler.getLastScheduledSpeechEndAtMs();
  assert.ok(speechEnd >= before + 80);
  assert.ok(speechEnd <= performance.now() + 80);
});
