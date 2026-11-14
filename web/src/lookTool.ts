// What the looks screen adds to the canvas besides the region brush (that is `MaskTool`, ADR 0008): the room and the Look
// toggled at integer zoom, the pieces of the Look laid over the room as the game will switch them, `look.drift`'s boxes, and
// the box a `difference` is measured in. Plain class: a drag or a hover never goes through React state.

import type { CanvasFrame, CanvasPixel, CanvasTool } from "./pixelCanvas";

export type LookView = "room" | "look";

export interface DriftBox {
  x: number;
  y: number;
  width: number;
  height: number;
  pixels?: number;
}

// A piece of a Look, cropped to the Look's box: laid at its offset.
export interface Piece {
  image: HTMLCanvasElement;
  x: number;
  y: number;
}

export interface Box {
  x0: number;
  y0: number;
  x1: number;
  y1: number; // both corners included, as the `difference` Decision has them
}

const DRIFT_COLOUR = "#ff3b6b";
const BOX_COLOUR = "#ffe14d";

export class LookTool implements CanvasTool {
  view: LookView = "room";
  pieces: Piece[] = [];
  drift: DriftBox[] = [];
  boxing = false; // the difference tool is the active tool: a drag makes a box instead of a stroke
  staged: Box | null = null; // dragged, not yet recorded
  // The pixels the staged box would pick out, as an image the size of the room (a rough preview, see lookScreen).
  preview: HTMLCanvasElement | null = null;
  private dragging: CanvasPixel | null = null;

  constructor(
    private readonly changed: () => void,
    private readonly staging: (box: Box) => void,
  ) {}

  private corners(from: CanvasPixel, to: CanvasPixel): Box {
    return { x0: Math.min(from.x, to.x), y0: Math.min(from.y, to.y), x1: Math.max(from.x, to.x), y1: Math.max(from.y, to.y) };
  }

  pointerDown(pixel: CanvasPixel): boolean {
    if (!this.boxing) return false;
    this.dragging = pixel;
    this.staged = this.corners(pixel, pixel);
    return true;
  }

  pointerMove(pixel: CanvasPixel): void {
    if (this.dragging) this.staged = this.corners(this.dragging, pixel);
  }

  pointerUp(pixel: CanvasPixel): void {
    if (!this.dragging) return;
    this.staged = this.corners(this.dragging, pixel);
    this.dragging = null;
    this.staging(this.staged);
    this.changed();
  }

  clearBox(): void {
    this.staged = null;
    this.preview = null;
    this.dragging = null;
    this.changed();
  }

  draw(context: CanvasRenderingContext2D, frame: CanvasFrame): void {
    context.imageSmoothingEnabled = false;
    const width = frame.width * frame.zoom;
    const height = frame.height * frame.zoom;
    if (this.view === "look") {
      for (const piece of this.pieces) {
        context.drawImage(piece.image, frame.left + piece.x * frame.zoom, frame.top + piece.y * frame.zoom, piece.image.width * frame.zoom, piece.image.height * frame.zoom);
      }
    }
    if (this.preview) {
      context.globalAlpha = 0.6;
      context.drawImage(this.preview, frame.left, frame.top, width, height);
      context.globalAlpha = 1;
    }
    context.save();
    context.lineWidth = 2;
    context.font = "12px monospace";
    context.textBaseline = "top";
    for (const box of this.drift) {
      context.strokeStyle = DRIFT_COLOUR;
      context.setLineDash([6, 3]);
      context.strokeRect(frame.left + box.x * frame.zoom, frame.top + box.y * frame.zoom, box.width * frame.zoom, box.height * frame.zoom);
    }
    if (this.staged) {
      const { x0, y0, x1, y1 } = this.staged;
      context.strokeStyle = BOX_COLOUR;
      context.setLineDash([]);
      context.strokeRect(frame.left + x0 * frame.zoom, frame.top + y0 * frame.zoom, (x1 - x0 + 1) * frame.zoom, (y1 - y0 + 1) * frame.zoom);
    }
    context.restore();
    const data = frame.element.dataset;
    data.lookView = this.view;
    data.lookPieces = String(this.pieces.length);
    data.drift = this.drift.map((box) => `${box.x},${box.y},${box.width},${box.height}`).join(" ");
    data.staged = this.staged ? `${this.staged.x0},${this.staged.y0},${this.staged.x1},${this.staged.y1}` : "";
  }
}
