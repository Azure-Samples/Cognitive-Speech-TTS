export function encodePcm(bytes) {
  let binary = '';
  for (let offset = 0; offset < bytes.length; offset += 8192)
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 8192));
  return btoa(binary);
}

export function decodePcm(base64) {
  const binary = atob(base64);
  if (binary.length % 2) throw new Error('Azure returned incomplete PCM16 audio.');
  const samples = new Float32Array(binary.length / 2);
  for (let i = 0; i < samples.length; i++) {
    const value = binary.charCodeAt(i * 2) | binary.charCodeAt(i * 2 + 1) << 8;
    samples[i] = (value >= 32768 ? value - 65536 : value) / 32768;
  }
  return samples;
}

export function validateAudioSession(session) {
  for (const side of ['input', 'output']) {
    const format = session?.audio?.[side]?.format ?? session?.[`${side}_audio_format`];
    if (format && format !== 'pcm16' && !(format.type === 'audio/pcm' && format.rate === 24000))
      throw new Error('WebSocket mode requires mono PCM16 at 24 kHz. Update the agent audio format in Foundry.');
  }
  const input = session?.audio?.input;
  const vad = input?.turn_detection ?? session?.turn_detection;
  if (input?.turn_detection === null || session?.turn_detection === null || vad?.create_response === false)
    throw new Error('Enable server-side turn detection and automatic responses in the Foundry agent.');
}

export class PcmAudio {
  constructor(onPlayback) {
    this.context = new AudioContext({sampleRate:24000});
    this.onPlayback = onPlayback;
    this.nodes = new Set();
    this.nextTime = 0;
    this.disposed = false;
    // Called directly from the Start click, before microphone permission awaits.
    this.resumePromise = this.context.resume();
  }
  async prepare(stream, onChunk) {
    await this.resumePromise;
    if (this.disposed) return;
    if (this.context.sampleRate !== 24000) throw new Error('This browser cannot capture 24 kHz PCM. Try WebRTC or another browser.');
    await this.context.audioWorklet.addModule('/pcm-capture.js');
    if (this.disposed) return;
    this.source = this.context.createMediaStreamSource(stream);
    this.capture = new AudioWorkletNode(this.context, 'pcm-capture');
    this.capture.port.onmessage = event => { if (!this.disposed) onChunk(encodePcm(new Uint8Array(event.data))); };
    this.silent = this.context.createGain(); this.silent.gain.value = 0;
    this.source.connect(this.capture); this.capture.connect(this.silent); this.silent.connect(this.context.destination);
  }
  mute(muted) { this.capture?.port.postMessage({muted}); }
  play(base64) {
    if (this.disposed) return;
    const samples = decodePcm(base64);
    if (!samples.length) return;
    if (this.nextTime - this.context.currentTime > 30)
      throw new Error('Speaker playback fell too far behind. Restart the conversation.');
    const buffer = this.context.createBuffer(1, samples.length, 24000);
    buffer.copyToChannel(samples, 0);
    const node = this.context.createBufferSource(); node.buffer = buffer;
    node.connect(this.context.destination); this.nodes.add(node);
    node.onended = () => {
      this.nodes.delete(node); node.disconnect();
      if (!this.nodes.size && !this.disposed) this.onPlayback(false);
    };
    const start = Math.max(this.context.currentTime + 0.02, this.nextTime);
    node.start(start); this.nextTime = start + buffer.duration; this.onPlayback(true);
  }
  interrupt() {
    for (const node of this.nodes) { node.onended = null; node.stop(); node.disconnect(); }
    this.nodes.clear(); this.nextTime = this.context.currentTime;
    if (!this.disposed) this.onPlayback(false);
  }
  dispose() {
    this.disposed = true; this.interrupt();
    if (this.capture) { this.capture.port.onmessage = null; this.capture.port.close(); this.capture.disconnect(); }
    this.source?.disconnect(); this.silent?.disconnect();
    this.context.close().catch(() => {});
  }
}
