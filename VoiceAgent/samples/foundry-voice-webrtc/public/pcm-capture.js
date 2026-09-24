// AudioContext runs at 24 kHz. Batch 100 ms of mono little-endian PCM16.
class PcmCapture extends AudioWorkletProcessor {
  constructor() {
    super();
    this.buffer = new ArrayBuffer(4800);
    this.view = new DataView(this.buffer);
    this.offset = 0;
    this.muted = false;
    this.port.onmessage = event => { this.muted = Boolean(event.data.muted); };
  }
  process(inputs) {
    const input = inputs[0]?.[0];
    if (!input) return true;
    for (const value of input) {
      const sample = this.muted ? 0 : Math.max(-1, Math.min(1, value));
      this.view.setInt16(this.offset, sample < 0 ? sample * 32768 : sample * 32767, true);
      this.offset += 2;
      if (this.offset === this.buffer.byteLength) {
        this.port.postMessage(this.buffer, [this.buffer]);
        this.buffer = new ArrayBuffer(4800);
        this.view = new DataView(this.buffer);
        this.offset = 0;
      }
    }
    // Outputs remain silent: this node never feeds mic sound into the speakers.
    return true;
  }
}
registerProcessor('pcm-capture', PcmCapture);
