// Copyright (c) Microsoft. All rights reserved.
// AudioHandler: mic capture + streaming PCM16 playback with barge-in.
// Ported from the Voice Live React sample (src/lib/audio.ts), trimmed to the pieces
// this demo needs. Method names match the sample so its logic can be cloned directly:
//   startRecording / stopRecording / startStreamingPlayback / stopStreamingPlayback / playChunk
// Capture + playback are PCM16 @ 24 kHz. Client-reference EC sends interleaved
// [microphone, rendered playback] stereo frames.

export function shouldRenderPcmOutput(userSpeaking, avatarAudioAvailable, transport) {
  return !userSpeaking && !avatarAudioAvailable && transport !== "webrtc";
}

export class AudioHandler {
  constructor(
    workletUrl = "/static/pcm-capture-worklet.js",
    {
      clientReferenceEc = false,
      referenceAudioMode = "assistant",
    } = {},
  ) {
    this.workletUrl = workletUrl;
    this.sampleRate = 24000;
    this.clientReferenceEc = clientReferenceEc;
    this.referenceAudioMode = referenceAudioMode;
    this.context = null;
    this.stream = null;
    this.source = null;
    this.workletNode = null;
    this.playbackBus = null;
    this.sharedReferenceStream = null;
    this.sharedReferenceSource = null;
    this.recordingPromise = null;
    this.recordingGeneration = 0;
    this.disposed = false;
    this.muted = false;

    this.isPlaying = false;
    this.nextPlayTime = 0;
    this.lastScheduledSpeechEndAtMs = null;
    this.playbackQueue = []; // scheduled AudioBufferSourceNodes (for barge-in stop)
    this.playbackWaiters = new Set();
  }

  async initialize() {
    if (!this.context) {
      this.context = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: this.sampleRate });
      await this.context.audioWorklet.addModule(this.workletUrl);
    }
    this.ensurePlaybackBus();
    if (this.context.state === "suspended") await this.context.resume();
  }

  ensurePlaybackBus() {
    if (!this.clientReferenceEc || !this.context || this.playbackBus) return;
    this.playbackBus = this.context.createGain();
    this.playbackBus.connect(this.context.destination);
  }

  usesSharedReference() {
    return this.clientReferenceEc && this.referenceAudioMode !== "assistant";
  }

  usesAssistantReference() {
    return this.clientReferenceEc && this.referenceAudioMode !== "shared-system";
  }

  async prepareReferenceCapture(onEnded) {
    if (!this.usesSharedReference() || this.sharedReferenceStream) return;
    if (!navigator.mediaDevices?.getDisplayMedia) {
      throw new Error("This browser does not support shared audio capture");
    }

    // Invoke getDisplayMedia before the first await so the browser sees the Connect click's
    // transient user activation and can open its tab/window/screen picker.
    const capture = navigator.mediaDevices.getDisplayMedia({
      video: true,
      audio: true,
    });
    const stream = await capture;
    const audioTracks = stream.getAudioTracks();
    if (!audioTracks.length) {
      stream.getTracks().forEach((track) => track.stop());
      throw new Error("The selected share has no audio. Enable Share audio and try again");
    }
    this.sharedReferenceStream = stream;
    for (const track of stream.getTracks()) {
      track.onended = () => {
        if (this.sharedReferenceStream === stream && onEnded) onEnded();
      };
    }
  }

  // Start mic capture. onChunk receives a Uint8Array of PCM16 samples (~100 ms batches).
  async startRecording(onChunk) {
    if (this.disposed) return;
    if (this.stream || this.workletNode) return;
    if (!this.recordingPromise) {
      const generation = ++this.recordingGeneration;
      const recordingPromise = (async () => {
        await this.initialize();
        if (this.disposed || generation !== this.recordingGeneration) return;
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            channelCount: 1,
            echoCancellation: !this.clientReferenceEc,
            noiseSuppression: !this.clientReferenceEc,
            autoGainControl: !this.clientReferenceEc,
          },
        });
        if (this.disposed || generation !== this.recordingGeneration || !this.context) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }
        this.stream = stream;
        this.source = this.context.createMediaStreamSource(this.stream);
        if (this.usesSharedReference()) {
          if (!this.sharedReferenceStream) {
            throw new Error("Shared reference audio was not selected before microphone capture");
          }
          this.sharedReferenceSource = this.context.createMediaStreamSource(
            this.sharedReferenceStream,
          );
        }
        this.ensurePlaybackBus();
        this.workletNode = new AudioWorkletNode(
          this.context,
          "pcm-capture-processor",
          this.clientReferenceEc ? {
            numberOfInputs: 2,
            numberOfOutputs: 1,
            outputChannelCount: [1],
            processorOptions: { channelCount: 2 },
          } : undefined,
        );
        this.workletNode.port.onmessage = (e) => {
          if (this.muted && !this.clientReferenceEc) return;
          onChunk(new Uint8Array(e.data));
        };
        this.source.connect(this.workletNode, 0, 0);
        if (this.playbackBus && this.usesAssistantReference()) {
          this.playbackBus.connect(this.workletNode, 0, 1);
        }
        if (this.sharedReferenceSource) {
          this.sharedReferenceSource.connect(this.workletNode, 0, 1);
        }
        this.nextPlayTime = this.context.currentTime;
      })();
      this.recordingPromise = recordingPromise;
    }
    const recordingPromise = this.recordingPromise;
    try {
      await recordingPromise;
    } finally {
      if (this.recordingPromise === recordingPromise) this.recordingPromise = null;
    }
  }

  stopRecording() {
    this.recordingGeneration += 1;
    this.recordingPromise = null;
    if (this.playbackBus && this.workletNode) {
      try { this.playbackBus.disconnect(this.workletNode); } catch { /* noop */ }
    }
    if (this.sharedReferenceSource) { try { this.sharedReferenceSource.disconnect(); } catch { /* noop */ } this.sharedReferenceSource = null; }
    if (this.sharedReferenceStream) {
      this.sharedReferenceStream.getTracks().forEach((track) => { track.onended = null; track.stop(); });
      this.sharedReferenceStream = null;
    }
    if (this.workletNode) { try { this.workletNode.port.onmessage = null; this.workletNode.disconnect(); } catch { /* noop */ } this.workletNode = null; }
    if (this.source) { try { this.source.disconnect(); } catch { /* noop */ } this.source = null; }
    if (this.stream) { this.stream.getTracks().forEach((t) => t.stop()); this.stream = null; }
    this.muted = false;
  }

  setMuted(muted) {
    this.muted = muted;
    if (this.clientReferenceEc && this.workletNode) {
      this.workletNode.port.postMessage({ type: "mute", muted });
    }
  }

  startStreamingPlayback() {
    this.isPlaying = true;
    this.nextPlayTime = this.context ? this.context.currentTime : 0;
  }

  beginResponsePlayback() {
    this.lastScheduledSpeechEndAtMs = null;
  }

  getLastScheduledSpeechEndAtMs() {
    return this.lastScheduledSpeechEndAtMs;
  }

  _resolvePlaybackWaiters() {
    if (this.playbackQueue.length > 0) return;
    this.isPlaying = false;
    for (const resolve of this.playbackWaiters) resolve();
    this.playbackWaiters.clear();
  }

  waitForPlaybackComplete() {
    if (this.playbackQueue.length === 0) return Promise.resolve();
    return new Promise((resolve) => this.playbackWaiters.add(resolve));
  }

  // Barge-in: stop + flush every scheduled audio source so the agent goes silent at once.
  stopStreamingPlayback() {
    this.isPlaying = false;
    this.lastScheduledSpeechEndAtMs = null;
    this.playbackQueue.forEach((src) => {
      try { src.onended = null; } catch { /* noop */ }
      try { src.disconnect(); } catch { /* noop */ }
      try { src.stop(); } catch { /* noop */ }
    });
    this.playbackQueue = [];
    if (this.context) this.nextPlayTime = this.context.currentTime;
    this._resolvePlaybackWaiters();
  }

  // Schedule one PCM16 chunk (Uint8Array) for gapless playback. When a speech
  // offset is supplied, return its estimated monotonic playback time.
  playChunk(chunk, speechOffsetMs = null, speechEndOffsetMs = null) {
    if (!this.context) return null;
    const int16 = new Int16Array(chunk.buffer, chunk.byteOffset, Math.floor(chunk.byteLength / 2));
    if (int16.length === 0) return null;
    const buffer = this.context.createBuffer(1, int16.length, this.sampleRate);
    const channel = buffer.getChannelData(0);
    for (let i = 0; i < int16.length; i++) channel[i] = int16[i] / 0x8000;
    const src = this.context.createBufferSource();
    src.buffer = buffer;
    src.connect(this.playbackBus || this.context.destination);
    if (this.nextPlayTime < this.context.currentTime) this.nextPlayTime = this.context.currentTime;
    const chunkStartTime = this.nextPlayTime;
    const scheduledSpeechAtMs = Number.isFinite(speechOffsetMs)
      ? performance.now()
        + Math.max(0, chunkStartTime - this.context.currentTime) * 1000
        + Math.max(0, speechOffsetMs)
      : null;
    if (Number.isFinite(speechEndOffsetMs)) {
      const boundedSpeechEndOffsetMs = Math.min(
        Math.max(0, speechEndOffsetMs),
        buffer.duration * 1000,
      );
      this.lastScheduledSpeechEndAtMs = performance.now()
        + Math.max(0, chunkStartTime - this.context.currentTime) * 1000
        + boundedSpeechEndOffsetMs;
    }
    src.start(chunkStartTime);
    this.nextPlayTime += buffer.duration;
    this.playbackQueue.push(src);
    src.onended = () => {
      const i = this.playbackQueue.indexOf(src);
      if (i > -1) this.playbackQueue.splice(i, 1);
      this._resolvePlaybackWaiters();
    };
    return scheduledSpeechAtMs;
  }

  dispose() {
    this.disposed = true;
    this.stopStreamingPlayback();
    this.stopRecording();
    if (this.playbackBus) { try { this.playbackBus.disconnect(); } catch { /* noop */ } this.playbackBus = null; }
    if (this.context) { try { this.context.close(); } catch { /* noop */ } this.context = null; }
  }
}

// ---- base64 helpers (Voice Live audio is base64-encoded PCM16) ----
export function uint8ToBase64(bytes) {
  let binary = ""; const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
  return btoa(binary);
}
export function base64ToUint8(b64) {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}
