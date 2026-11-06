// The Masks on the canvas (ADR 0008): a plain class, so a stroke or a hover never goes through React state. The screen
// draws the built Masks tinted over the Plate, and the tools turn a gesture into one call, on release (spec §11): a
// stroke is one brush Decision, a click is one flood or click Decision. A hover only asks the segment-preview Probe.

import type { CanvasFrame, CanvasPixel, CanvasTool } from "./pixelCanvas";
import type { MaskPixels } from "./walkTest";

export type MaskToolName = "brush" | "erase" | "flood" | "click";

export interface MaskGestures {
  stroke(mask: string, erase: boolean, radius: number, points: [number, number][]): void;
  point(tool: "flood" | "click", mask: string, pixel: CanvasPixel, positive: boolean): void;
  // The Mask a click at the pixel would make, as runs of [y, x, length]; null when no preview can be made.
  preview(pixel: CanvasPixel, subtract: boolean): Promise<PreviewRuns | null>;
}

export interface PreviewRuns {
  width: number;
  height: number;
  pixels: number;
  runs: [number, number, number][];
}

const TINTS = ["#ff4d4d", "#4d7dff", "#4dd68c", "#ffb84d", "#c77dff", "#4dd6d6"];
const PREVIEW_TINT = "#ffe14d";
const SUBTRACT_TINT = "#ff3b6b";
const HOVER_DELAY_MS = 60; // a hover that has settled; the Probe is cheap but a moving pointer needn't ask at every pixel
export const MIN_RADIUS = 0;
export const MAX_RADIUS = 32;

export function tintOf(index: number): string {
  return TINTS[index % TINTS.length];
}

function tinted(width: number, height: number, set: (x: number, y: number) => boolean, colour: string): HTMLCanvasElement {
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d")!;
  context.fillStyle = colour;
  for (let y = 0; y < height; y++) {
    let start = -1;
    for (let x = 0; x <= width; x++) {
      const on = x < width && set(x, y);
      if (on && start < 0) start = x;
      if (!on && start >= 0) {
        context.fillRect(start, y, x - start, 1);
        start = -1;
      }
    }
  }
  return canvas;
}

interface Overlay {
  name: string;
  image: HTMLCanvasElement;
  count: number;
}

export class MaskTool implements CanvasTool {
  tool: MaskToolName = "brush";
  mask = "";
  radius = 2;
  opacity = 0.5;
  private names: string[] = [];
  private overlays: Overlay[] = [];
  private pixels = new Map<string, MaskPixels>();
  // What a Shift-hover can take away from: the Layer's own pixels, where the screen's masks aren't the thing edited.
  taking: MaskPixels | null = null;
  private preview: { image: HTMLCanvasElement; count: number; subtract: boolean } | null = null;
  private stroke: [number, number][] | null = null;
  private strokeImage: HTMLCanvasElement | null = null;
  private stamped = 0; // how many of the stroke's points are on strokeImage
  private stamps = 0; // fillRects made for the stroke, and in the latest frame: what the tests count
  private frameStamps = 0;
  private cursor: CanvasPixel | null = null;
  private shift = false;
  private asked = 0;
  private timer: number | undefined;

  constructor(
    private readonly gestures: MaskGestures,
    private readonly changed: () => void,
  ) {
    window.addEventListener("keydown", this.onKey);
    window.addEventListener("keyup", this.onKey);
  }

  destroy(): void {
    window.removeEventListener("keydown", this.onKey);
    window.removeEventListener("keyup", this.onKey);
    window.clearTimeout(this.timer);
    this.asked++;
  }

  setMasks(masks: { name: string; pixels: MaskPixels }[]): void {
    this.names = masks.map((entry) => entry.name);
    this.pixels = new Map(masks.map((entry) => [entry.name, entry.pixels]));
    this.overlays = masks.map(({ name, pixels }, index) => {
      let count = 0;
      for (const value of pixels.set) count += value;
      const image = tinted(pixels.width, pixels.height, (x, y) => pixels.set[y * pixels.width + x] === 1, tintOf(index));
      return { name, image, count };
    });
  }

  colourOf(name: string): string {
    return tintOf(Math.max(0, this.names.indexOf(name)));
  }

  setTool(tool: MaskToolName): void {
    this.tool = tool;
    this.clearPreview();
  }

  clearPreview(): void {
    window.clearTimeout(this.timer);
    this.asked++;
    if (this.preview) {
      this.preview = null;
      this.changed();
    }
  }

  // Shift picks the negative click; the preview follows it without the pointer having to move.
  private readonly onKey = (event: KeyboardEvent): void => {
    if (event.key !== "Shift" || this.shift === event.shiftKey) return;
    this.shift = event.shiftKey;
    if (this.cursor && this.tool === "click") this.ask(this.cursor);
    this.changed();
  };

  hover(pixel: CanvasPixel | null): void {
    this.cursor = pixel;
    if (!pixel || this.tool !== "click" || this.stroke) {
      if (this.preview) this.clearPreview();
      return;
    }
    window.clearTimeout(this.timer);
    this.timer = window.setTimeout(() => this.ask(pixel), HOVER_DELAY_MS);
  }

  private ask(pixel: CanvasPixel): void {
    if (!this.mask) return;
    const subtract = this.shift;
    const asked = ++this.asked;
    void this.gestures.preview(pixel, subtract).then((made) => {
      if (asked !== this.asked) return; // The pointer has moved on, or left.
      this.preview = made
        ? this.previewOf(made, subtract)
        : null;
      this.changed();
    });
  }

  // A Shift-click takes its segment away from the current Mask or Layer, so only the part of it that is there is tinted.
  private previewOf(made: PreviewRuns, subtract: boolean): { image: HTMLCanvasElement; count: number; subtract: boolean } {
    const canvas = document.createElement("canvas");
    canvas.width = made.width;
    canvas.height = made.height;
    const context = canvas.getContext("2d")!;
    context.fillStyle = subtract ? SUBTRACT_TINT : PREVIEW_TINT;
    if (!subtract) {
      for (const [y, x, length] of made.runs) context.fillRect(x, y, length, 1);
      return { image: canvas, count: made.pixels, subtract };
    }
    const there = this.taking ?? this.pixels.get(this.mask) ?? null;
    let count = 0;
    if (there && there.width === made.width && there.height === made.height) {
      for (const [y, x, length] of made.runs) {
        let start = -1;
        for (let at = x; at <= x + length; at++) {
          const on = at < x + length && there.set[y * there.width + at] === 1;
          if (on && start < 0) start = at;
          if (!on && start >= 0) {
            context.fillRect(start, y, at - start, 1);
            count += at - start;
            start = -1;
          }
        }
      }
    }
    return { image: canvas, count, subtract };
  }

  pointerDown(pixel: CanvasPixel): boolean {
    if (!this.mask) return false;
    this.clearPreview();
    this.strokeImage = null;
    this.stamped = 0;
    this.stamps = 0;
    this.frameStamps = 0;
    if (this.tool === "brush" || this.tool === "erase") this.stroke = [[pixel.x, pixel.y]];
    else this.stroke = null;
    this.cursor = pixel;
    return true;
  }

  pointerMove(pixel: CanvasPixel): void {
    this.cursor = pixel;
    const last = this.stroke?.at(-1);
    if (this.stroke && last && (last[0] !== pixel.x || last[1] !== pixel.y)) this.stroke.push([pixel.x, pixel.y]);
  }

  pointerUp(pixel: CanvasPixel): void {
    this.pointerMove(pixel);
    const stroke = this.stroke;
    this.stroke = null;
    this.strokeImage = null;
    if (stroke) this.gestures.stroke(this.mask, this.tool === "erase", this.radius, stroke);
    else if (this.tool === "flood" || this.tool === "click") this.gestures.point(this.tool, this.mask, pixel, !this.shift);
  }

  // The pixels from the previous point to this one, with the gap between two pointer events filled in.
  private segment(from: [number, number], point: [number, number], first: boolean): [number, number][] {
    const path: [number, number][] = [];
    const steps = Math.max(Math.abs(point[0] - from[0]), Math.abs(point[1] - from[1]), 1);
    for (let step = first ? steps : 1; step <= steps; step++) {
      path.push([
        Math.round(from[0] + ((point[0] - from[0]) * step) / steps),
        Math.round(from[1] + ((point[1] - from[1]) * step) / steps),
      ]);
    }
    return path;
  }

  // One row of the disc at a time, in pixels of the image: a stamp is 2r+1 fillRects whatever the stroke's length.
  private disc(context: CanvasRenderingContext2D, x: number, y: number): number {
    const radius = this.radius;
    let calls = 0;
    for (let dy = -radius; dy <= radius; dy++) {
      const half = Math.floor(Math.sqrt(radius * radius - dy * dy));
      context.fillRect(x - half, y + dy, 2 * half + 1, 1);
      calls++;
    }
    return calls;
  }

  // Stamps only the points the stroke has gained since the last frame onto the stroke's own canvas, at the image's
  // resolution; the frame then costs one drawImage.
  private stamp(frame: CanvasFrame, stroke: [number, number][]): number {
    if (!this.strokeImage || this.strokeImage.width !== frame.width || this.strokeImage.height !== frame.height) {
      this.strokeImage = document.createElement("canvas");
      this.strokeImage.width = frame.width;
      this.strokeImage.height = frame.height;
      this.stamped = 0;
    }
    const context = this.strokeImage.getContext("2d")!;
    context.fillStyle = this.tool === "erase" ? "#ffffff" : this.colourOf(this.mask);
    let calls = 0;
    for (let index = this.stamped; index < stroke.length; index++) {
      const point = stroke[index];
      for (const [x, y] of this.segment(stroke[index - 1] ?? point, point, index === 0)) calls += this.disc(context, x, y);
    }
    this.stamped = stroke.length;
    return calls;
  }

  draw(context: CanvasRenderingContext2D, frame: CanvasFrame): void {
    context.imageSmoothingEnabled = false;
    const width = frame.width * frame.zoom;
    const height = frame.height * frame.zoom;
    for (const overlay of this.overlays) {
      context.globalAlpha = overlay.name === this.mask ? this.opacity : this.opacity * 0.6;
      context.drawImage(overlay.image, frame.left, frame.top, width, height);
    }
    if (this.preview) {
      context.globalAlpha = Math.min(1, this.opacity + 0.2);
      context.drawImage(this.preview.image, frame.left, frame.top, width, height);
    }
    const painting = this.tool === "brush" || this.tool === "erase";
    if (this.stroke) {
      context.globalAlpha = 0.6;
      this.frameStamps = this.stamp(frame, this.stroke);
      this.stamps += this.frameStamps;
      context.drawImage(this.strokeImage!, frame.left, frame.top, width, height);
    } else if (painting && this.cursor) {
      context.globalAlpha = 0.35;
      context.fillStyle = this.tool === "erase" ? "#ffffff" : this.colourOf(this.mask);
      const { x, y } = this.cursor;
      const radius = this.radius;
      for (let dy = -radius; dy <= radius; dy++) {
        const half = Math.floor(Math.sqrt(radius * radius - dy * dy));
        context.fillRect(frame.left + (x - half) * frame.zoom, frame.top + (y + dy) * frame.zoom, (2 * half + 1) * frame.zoom, frame.zoom);
      }
    }
    context.globalAlpha = 1;
    if (this.cursor && !painting) {
      context.strokeStyle = this.shift && this.tool === "click" ? SUBTRACT_TINT : "#ffffff";
      context.strokeRect(
        frame.left + this.cursor.x * frame.zoom + 0.5,
        frame.top + this.cursor.y * frame.zoom + 0.5,
        frame.zoom - 1,
        frame.zoom - 1,
      );
    }
    const data = frame.element.dataset;
    data.masks = this.overlays.map((overlay) => `${overlay.name}:${overlay.count}`).join(" ");
    data.tool = this.tool;
    data.mask = this.mask;
    data.radius = String(this.radius);
    data.opacity = String(this.opacity);
    data.strokeStamps = String(this.stamps);
    data.strokeFrameStamps = String(this.frameStamps);
    data.preview = String(this.preview?.count ?? 0);
  }
}
