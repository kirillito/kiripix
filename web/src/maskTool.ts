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
  private preview: { image: HTMLCanvasElement; count: number; subtract: boolean } | null = null;
  private stroke: [number, number][] | null = null;
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
        ? { image: this.runsImage(made, subtract), count: made.pixels, subtract }
        : null;
      this.changed();
    });
  }

  private runsImage(made: PreviewRuns, subtract: boolean): HTMLCanvasElement {
    const canvas = document.createElement("canvas");
    canvas.width = made.width;
    canvas.height = made.height;
    const context = canvas.getContext("2d")!;
    context.fillStyle = subtract ? SUBTRACT_TINT : PREVIEW_TINT;
    for (const [y, x, length] of made.runs) context.fillRect(x, y, length, 1);
    return canvas;
  }

  pointerDown(pixel: CanvasPixel): boolean {
    if (!this.mask) return false;
    this.clearPreview();
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
    if (stroke) this.gestures.stroke(this.mask, this.tool === "erase", this.radius, stroke);
    else if (this.tool === "flood" || this.tool === "click") this.gestures.point(this.tool, this.mask, pixel, !this.shift);
  }

  // The pixels of a stroke, with the gaps between two pointer events filled in.
  private along(points: [number, number][]): [number, number][] {
    const path: [number, number][] = [];
    points.forEach((point, index) => {
      const from = points[index - 1] ?? point;
      const steps = Math.max(Math.abs(point[0] - from[0]), Math.abs(point[1] - from[1]), 1);
      for (let step = index ? 1 : steps; step <= steps; step++) {
        path.push([
          Math.round(from[0] + ((point[0] - from[0]) * step) / steps),
          Math.round(from[1] + ((point[1] - from[1]) * step) / steps),
        ]);
      }
    });
    return path;
  }

  private disc(context: CanvasRenderingContext2D, frame: CanvasFrame, x: number, y: number): void {
    const radius = this.radius;
    for (let dy = -radius; dy <= radius; dy++) {
      for (let dx = -radius; dx <= radius; dx++) {
        if (dx * dx + dy * dy <= radius * radius) {
          context.fillRect(frame.left + (x + dx) * frame.zoom, frame.top + (y + dy) * frame.zoom, frame.zoom, frame.zoom);
        }
      }
    }
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
      context.fillStyle = this.tool === "erase" ? "#ffffff" : this.colourOf(this.mask);
      for (const [x, y] of this.along(this.stroke)) this.disc(context, frame, x, y);
    } else if (painting && this.cursor) {
      context.globalAlpha = 0.35;
      context.fillStyle = this.tool === "erase" ? "#ffffff" : this.colourOf(this.mask);
      this.disc(context, frame, this.cursor.x, this.cursor.y);
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
    data.preview = String(this.preview?.count ?? 0);
  }
}
