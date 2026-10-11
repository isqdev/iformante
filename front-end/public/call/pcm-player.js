/* Browser audio thread: PCM queue, linear resampling and playback acknowledgements. */
class CallPcmPlayer extends AudioWorkletProcessor {
  constructor() {
    super();
    this.reset(0);
    this.port.onmessage = ({ data }) => {
      if (data.type === "reset") this.reset(data.epoch);
      if (data.epoch !== this.epoch) return;
      if (data.type === "format") this.rate = data.sampleRate;
      if (data.type === "audio") {
        this.queue.push(data.samples);
        this.available += data.samples.length;
      }
      if (data.type === "end") this.finished = true;
    };
  }
  reset(epoch) {
    this.epoch = epoch;
    this.queue = [];
    this.position = 0;
    this.consumed = 0;
    this.available = 0;
    this.rate = 22050;
    this.finished = false;
    this.ended = false;
    this.waiting = true;
    this.counter = 0;
    this.energy = 0;
  }
  process(inputs, outputs) {
    const output = outputs[0][0];
    if (!output) return true;
    output.fill(0);
    if (this.waiting && (this.available >= this.rate * 0.12 || this.finished)) this.waiting = false;
    let played = false;
    if (!this.waiting) {
      for (let i = 0; i < output.length; i++) {
        while (this.queue.length && this.position >= this.queue[0].length) {
          const old = this.queue.shift();
          this.position -= old.length;
          this.consumed += old.length;
          this.available -= old.length;
        }
        if (!this.queue.length) {
          this.waiting = true;
          break;
        }
        const chunk = this.queue[0];
        const index = Math.floor(this.position);
        const next = index + 1 < chunk.length ? chunk[index + 1] : (this.queue[1]?.[0] ?? chunk[index]);
        output[i] = chunk[index] + (next - chunk[index]) * (this.position - index);
        this.position += this.rate / sampleRate;
        played = true;
      }
    }
    let energy = 0;
    for (const value of output) energy += value * value;
    this.energy += energy;
    this.counter += output.length;
    if (this.counter >= 1024) {
      this.port.postMessage({ type: "frame", epoch: this.epoch, time: (this.consumed + this.position) / this.rate,
        level: Math.sqrt(this.energy / this.counter), playing: played });
      this.counter = 0;
      this.energy = 0;
    }
    if (this.finished && !this.queue.length && !this.ended) {
      this.ended = true;
      this.port.postMessage({ type: "ended", epoch: this.epoch });
    }
    return true;
  }
}
registerProcessor("call-pcm-player", CallPcmPlayer);
