// What the loops screen adds to the canvas besides the region tools (that is `MaskTool`, ADR 0008): the room's Loops playing over
// the room, stepped in whole 60 Hz ticks by the same `sequence` the export writes, the pixels of the colour being looked at, and
// the eyedropper's click. Plain class: a tick or a hover never goes through React state.

import type { CanvasFrame, CanvasPixel, CanvasTool } from "./pixelCanvas";

export const TICKS_PER_SECOND = 60;

// A built Loop, as the preview needs it: its strips (one canvas a piece) cropped to `box`, tile n at row n // columns.
export interface PlayingLoop {
  id: string;
  box: [number, number, number, number];
  columns: number;
  sequence: [number, number][];
  period: number;
  phase: number;
  pieces: HTMLCanvasElement[];
}

// The frame a Loop shows at a tick: its `sequence` (frame, ticks), walked from the Loop's phase.
export function frameAt(loop: Pick<PlayingLoop, "sequence" | "period" | "phase">, tick: number): number {
  if (loop.period <= 0) return 0;
  let left = (((tick + loop.phase) % loop.period) + loop.period) % loop.period;
  for (const [frame, ticks] of loop.sequence) {
    if (left < ticks) return frame;
    left -= ticks;
  }
  return 0;
}

export class LoopTool implements CanvasTool {
  loops: PlayingLoop[] = [];
  tick = 0;
  playing = false; // paused: the room, which is every Loop's frame 0
  solo: string | null = null;
  picking = false; // the eyedropper is the active tool: a click names a pixel
  inspect: { id: string; frame: number } | null = null; // one frame of one Loop shown alone, with the one before it faint
  anchorRow: number | null = null; // a sway's anchor row, a line across the room
  lit: HTMLCanvasElement | null = null; // the pixels of the colour being looked at, an image the size of the room
  private frame = 0; // the request animation frame
  private last = 0;
  private spare = 0; // ticks not yet whole

  constructor(
    private readonly changed: () => void,
    private readonly picked: (pixel: CanvasPixel) => void,
  ) {}

  destroy(): void {
    this.stop();
  }

  play(): void {
    if (this.playing) return;
    this.playing = true;
    this.last = performance.now();
    this.spare = 0;
    const step = (now: number) => {
      if (!this.playing) return;
      this.spare += ((now - this.last) * TICKS_PER_SECOND) / 1000;
      this.last = now;
      const whole = Math.floor(this.spare);
      if (whole > 0) {
        this.spare -= whole;
        this.tick += whole;
        this.changed();
      }
      this.frame = requestAnimationFrame(step);
    };
    this.frame = requestAnimationFrame(step);
    this.changed();
  }

  // Pausing shows frame 0 again: the room, as the export would draw it with no Loop moving.
  pause(): void {
    this.stop();
    this.tick = 0;
    this.changed();
  }

  step(): void {
    this.stop();
    this.tick += 1;
    this.changed();
  }

  private stop(): void {
    this.playing = false;
    cancelAnimationFrame(this.frame);
  }

  pointerDown(): boolean {
    return this.picking;
  }

  pointerMove(): void {}

  pointerUp(pixel: CanvasPixel): void {
    if (this.picking) this.picked(pixel);
  }

  // What shows at a tick: each Loop's frame, or none while paused at frame 0 (the room itself).
  frames(): { id: string; frame: number }[] {
    return this.loops.filter((loop) => this.solo === null || loop.id === this.solo).map((loop) => {
      if (!this.playing && this.inspect?.id === loop.id) return { id: loop.id, frame: this.inspect.frame };
      return { id: loop.id, frame: !this.playing && this.tick === 0 ? 0 : frameAt(loop, this.tick) };
    });
  }

  draw(context: CanvasRenderingContext2D, frame: CanvasFrame): void {
    context.imageSmoothingEnabled = false;
    const shown = this.frames();
    for (const { id, frame: n } of shown) {
      const loop = this.loops.find((entry) => entry.id === id)!;
      const [x, y, width, height] = loop.box;
      const draw = (at: number) => {
        const column = at % loop.columns;
        const row = Math.floor(at / loop.columns);
        for (const piece of loop.pieces) {
          context.drawImage(piece, column * width, row * height, width, height, frame.left + x * frame.zoom, frame.top + y * frame.zoom, width * frame.zoom, height * frame.zoom);
        }
      };
      const inspected = !this.playing && this.inspect?.id === id;
      if (inspected && n > 0) {
        context.globalAlpha = 0.3; // the onion skin: the frame before
        draw(n - 1);
        context.globalAlpha = 1;
      }
      draw(n);
    }
    if (this.anchorRow !== null) {
      context.fillStyle = "#ffe14d";
      context.fillRect(frame.left, frame.top + this.anchorRow * frame.zoom, frame.width * frame.zoom, Math.max(1, Math.floor(frame.zoom / 2)));
    }
    if (this.lit) {
      context.globalAlpha = 0.7;
      context.drawImage(this.lit, frame.left, frame.top, frame.width * frame.zoom, frame.height * frame.zoom);
      context.globalAlpha = 1;
    }
    const data = frame.element.dataset;
    data.loopTick = String(this.tick);
    data.loopPlaying = String(this.playing);
    data.loopFrames = shown.map((entry) => `${entry.id}:${entry.frame}`).join(" ");
    data.loopSolo = this.solo ?? "";
    data.loopInspect = this.inspect && !this.playing ? `${this.inspect.id}:${this.inspect.frame}` : "";
    data.loopAnchor = this.anchorRow === null ? "" : String(this.anchorRow);
  }
}
