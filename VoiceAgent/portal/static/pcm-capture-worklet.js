// Copyright (c) Microsoft. All rights reserved.
// AudioWorklet processor: captures microphone input and optionally interleaves
// rendered playback as [mic, reference] stereo PCM16. Runs in the AudioContext
// at 24 kHz, so no resampling is needed before sending to Voice Live.

class PcmCaptureProcessor extends AudioWorkletProcessor {
  constructor(options = {}) {
    super();
    // 24 kHz * 0.1 s = 2400 samples per batch.
    this.batchFrames = 2400;
    this.channelCount = options.processorOptions?.channelCount === 2 ? 2 : 1;
    this.buffer = new Int16Array(this.batchFrames * this.channelCount);
    this.offset = 0;
    this.muted = false;
    this.port.onmessage = (event) => {
      if (event.data?.type === "mute") this.muted = Boolean(event.data.muted);
    };
  }

  process(inputs) {
    const microphone = inputs[0]?.[0];
    if (!microphone) {
      return true;
    }
    const referenceChannels = inputs[1] || [];

    for (let i = 0; i < microphone.length; i++) {
      this.buffer[this.offset++] = this.toPcm16(this.muted ? 0 : microphone[i]);
      if (this.channelCount === 2) {
        let reference = 0;
        for (const channel of referenceChannels) reference += channel[i] || 0;
        if (referenceChannels.length) reference /= referenceChannels.length;
        this.buffer[this.offset++] = this.toPcm16(reference);
      }
      if (this.offset >= this.buffer.length) {
        // Transfer a copy so the worklet can keep filling its buffer.
        const out = this.buffer.slice(0, this.offset);
        this.port.postMessage(out.buffer, [out.buffer]);
        this.offset = 0;
      }
    }
    return true;
  }

  toPcm16(sample) {
    const clamped = Math.max(-1, Math.min(1, sample));
    return clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;
  }
}

registerProcessor('pcm-capture-processor', PcmCaptureProcessor);
