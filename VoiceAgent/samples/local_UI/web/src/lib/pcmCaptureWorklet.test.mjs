// Copyright (c) Microsoft. All rights reserved.

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { runInNewContext } from "node:vm";

async function createProcessor(channelCount = 2) {
  let Processor;
  const messages = [];
  class MockAudioWorkletProcessor {
    constructor() {
      this.port = {
        onmessage: null,
        postMessage: (message) => messages.push(message),
      };
    }
  }

  const source = await readFile(
    path.resolve(process.cwd(), "../static/pcm-capture-worklet.js"),
    "utf8",
  );
  runInNewContext(source, {
    AudioWorkletProcessor: MockAudioWorkletProcessor,
    registerProcessor(_name, constructor) { Processor = constructor; },
  });

  return {
    processor: new Processor({ processorOptions: { channelCount } }),
    messages,
  };
}

test("interleaves microphone and downmixed playback reference as stereo PCM16", async () => {
  const { processor, messages } = await createProcessor();
  const microphone = new Float32Array(2400).fill(0.5);
  const playbackLeft = new Float32Array(2400).fill(0.25);
  const playbackRight = new Float32Array(2400).fill(0.75);

  assert.equal(processor.process([[microphone], [playbackLeft, playbackRight]]), true);
  assert.equal(messages.length, 1);
  const samples = new Int16Array(messages[0]);
  assert.equal(samples.length, 4800);
  assert.equal(samples[0], 16383);
  assert.equal(samples[1], 16383);
  assert.equal(samples[4798], 16383);
  assert.equal(samples[4799], 16383);
});

test("keeps the playback reference flowing while the microphone is muted", async () => {
  const { processor, messages } = await createProcessor();
  processor.port.onmessage({ data: { type: "mute", muted: true } });

  processor.process([
    [new Float32Array(2400).fill(0.5)],
    [new Float32Array(2400).fill(0.25)],
  ]);

  const samples = new Int16Array(messages[0]);
  assert.equal(samples[0], 0);
  assert.equal(samples[1], 8191);
  assert.equal(samples[4798], 0);
  assert.equal(samples[4799], 8191);
});