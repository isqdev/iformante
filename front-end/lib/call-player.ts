export type SpeechFrame = { level: number; phoneme: string; speaking: boolean };
export type Alignment = { phoneme: string; start: number; duration: number };

export class CallPlayer {
  readonly frame: SpeechFrame = { level: 0, phoneme: "", speaking: false };
  private node: AudioWorkletNode;
  private epoch = 0;
  private sequence = 0;
  private alignments: Alignment[] = [];
  private alignmentIndex = 0;
  private finished: Promise<void> = Promise.resolve();
  private resolveFinished: (() => void) | null = null;

  private constructor(readonly context: AudioContext, node: AudioWorkletNode) {
    this.node = node;
    node.connect(context.destination);
    node.port.onmessage = ({ data }) => {
      if (data.epoch !== this.epoch) return;
      if (data.type === "ended") {
        this.frame.level = 0;
        this.frame.phoneme = "";
        this.frame.speaking = false;
        this.resolveFinished?.();
        this.resolveFinished = null;
      } else if (data.type === "frame") {
        while (this.alignmentIndex + 1 < this.alignments.length && this.alignments[this.alignmentIndex + 1].start <= data.time) this.alignmentIndex++;
        const item = this.alignments[this.alignmentIndex];
        this.frame.level = data.playing ? data.level : 0;
        this.frame.speaking = data.playing && data.level > 0.002;
        this.frame.phoneme = this.frame.speaking && item && data.time >= item.start && data.time < item.start + item.duration ? item.phoneme : "";
      }
    };
  }

  static async create() {
    const context = new AudioContext({ latencyHint: "interactive" });
    try {
      // Prepare on page entry without waiting for autoplay permission. The
      // first hold-to-talk gesture resumes this context before sending audio.
      await context.audioWorklet.addModule("/call/pcm-player.js");
      return new CallPlayer(context, new AudioWorkletNode(context, "call-pcm-player", { outputChannelCount: [1] }));
    } catch (error) {
      await context.close();
      throw error;
    }
  }

  begin() {
    this.stop();
    this.finished = new Promise<void>((resolve) => { this.resolveFinished = resolve; });
  }

  format(sampleRate: number, channels: number, sampleWidth: number) {
    if (channels !== 1 || sampleWidth !== 2 || sampleRate < 8000 || sampleRate > 96000) throw new Error("Formato de áudio inválido.");
    this.node.port.postMessage({ type: "format", epoch: this.epoch, sampleRate });
  }

  append(sequence: number, encoded: string) {
    if (sequence !== this.sequence++) throw new Error("A transmissão de áudio foi interrompida. Tente novamente.");
    const raw = atob(encoded);
    if (raw.length % 2) throw new Error("Bloco de áudio inválido.");
    const samples = new Float32Array(raw.length / 2);
    for (let i = 0; i < samples.length; i++) {
      let value = raw.charCodeAt(i * 2) | (raw.charCodeAt(i * 2 + 1) << 8);
      if (value >= 32768) value -= 65536;
      samples[i] = value / 32768;
    }
    this.node.port.postMessage({ type: "audio", epoch: this.epoch, samples }, [samples.buffer]);
  }

  align(items: Alignment[]) { this.alignments.push(...items); }

  end() {
    this.node.port.postMessage({ type: "end", epoch: this.epoch });
    return this.finished;
  }

  stop() {
    this.epoch++;
    this.sequence = 0;
    this.alignments = [];
    this.alignmentIndex = 0;
    this.frame.level = 0;
    this.frame.phoneme = "";
    this.frame.speaking = false;
    this.node.port.postMessage({ type: "reset", epoch: this.epoch });
    this.resolveFinished?.();
    this.resolveFinished = null;
  }

  async close() {
    this.stop();
    this.node.disconnect();
    await this.context.close();
  }
}
