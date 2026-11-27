// Listening in the browser (ticket 0398). A Take is played by its span of the whole decoded recording (`source.wav`), a Variation from its
// own processed file, through the Web Audio API: it decodes every file the Project holds (float WAV, FLAC, OGG) and starts at a sample
// accurate offset. Nothing here decides anything; it only plays files the Commands wrote.

export interface Clip {
  url: string;
  startMs: number;
  endMs: number | null; // null: to the end of the file
  label: string;
}

export class Player {
  private context: AudioContext | null = null;
  private readonly cache = new Map<string, Promise<AudioBuffer>>();
  private readonly active = new Set<AudioBufferSourceNode>();
  private timers: number[] = [];
  private token = 0;

  private audio(): AudioContext {
    if (!this.context) this.context = new AudioContext();
    return this.context;
  }

  private buffer(url: string): Promise<AudioBuffer> {
    let found = this.cache.get(url);
    if (!found) {
      found = fetch(url)
        .then((response) => {
          if (!response.ok) throw new Error(`no file ${url}`);
          return response.arrayBuffer();
        })
        .then((bytes) => this.audio().decodeAudioData(bytes));
      found.catch(() => this.cache.delete(url));
      this.cache.set(url, found);
    }
    return found;
  }

  // Start a clip now, over whatever is still sounding (footsteps overlap as they do in the game).
  async play(clip: Clip): Promise<void> {
    const context = this.audio();
    if (context.state === "suspended") await context.resume();
    const buffer = await this.buffer(clip.url);
    const node = context.createBufferSource();
    node.buffer = buffer;
    node.connect(context.destination);
    this.active.add(node);
    node.onended = () => this.active.delete(node);
    const start = Math.max(0, clip.startMs) / 1000;
    node.start(0, start, clip.endMs === null ? undefined : Math.max(0.001, (clip.endMs - clip.startMs) / 1000));
  }

  // The clips one after another, each starting `intervalMs` after the one before it (a walking pace), not after it ended.
  sequence(clips: Clip[], intervalMs: number, onStart: (index: number, clip: Clip) => void, onDone: () => void): void {
    this.stop();
    const token = ++this.token;
    clips.forEach((clip, index) => {
      this.timers.push(
        window.setTimeout(() => {
          if (token !== this.token) return;
          onStart(index, clip);
          void this.play(clip).catch(() => undefined);
        }, index * intervalMs),
      );
    });
    // Done once the last one has had a moment to sound.
    this.timers.push(window.setTimeout(() => token === this.token && onDone(), clips.length * intervalMs + 50));
  }

  stop(): void {
    this.token += 1;
    for (const timer of this.timers) window.clearTimeout(timer);
    this.timers = [];
    for (const node of this.active) {
      node.onended = null;
      try {
        node.stop();
      } catch {
        // Already stopped.
      }
    }
    this.active.clear();
  }
}
