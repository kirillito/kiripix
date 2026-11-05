// The prop's footprint on the canvas (spec §6.2, §11): the collision polygon and the y-sort origin, in the sprite's own
// pixels. A plain class, so a drag never goes through React state. Every gesture is one `decide` on release: a click adds
// a point (polygon mode) or moves the origin (origin mode), and a drag moves a point or the origin.

import type { CanvasFrame, CanvasPixel, CanvasTool } from "./pixelCanvas";

export type Point = [number, number];
export type FootprintMode = "polygon" | "origin";

export interface Footprint {
  polygon: Point[];
  origin: Point | null;
}

export interface FootprintGestures {
  change(footprint: { polygon: Point[]; origin: Point }): void;
}

const POLYGON_COLOUR = "#6fb7f2";
const ORIGIN_COLOUR = "#f2c14e";
const HIT_RADIUS = 6; // canvas pixels

type Grab = { kind: "origin" } | { kind: "point"; index: number } | { kind: "empty" };

export class FootprintTool implements CanvasTool {
  private polygon: Point[] = [];
  private origin: Point | null = null;
  private grab: Grab | null = null;
  private moved = false;
  mode: FootprintMode = "origin";

  constructor(private readonly gestures: FootprintGestures) {}

  set(footprint: Footprint): void {
    if (this.grab) return; // what stands is shown again once the gesture is released
    this.polygon = footprint.polygon.map(([x, y]) => [x, y]);
    this.origin = footprint.origin ? [footprint.origin[0], footprint.origin[1]] : null;
  }

  private hit(pixel: CanvasPixel, zoom: number): Grab {
    const near = (x: number, y: number) =>
      Math.hypot((x - pixel.x) * zoom, (y - pixel.y) * zoom) <= Math.max(HIT_RADIUS, zoom);
    if (this.origin && near(this.origin[0], this.origin[1])) return { kind: "origin" };
    for (let index = this.polygon.length - 1; index >= 0; index--) {
      if (near(this.polygon[index][0], this.polygon[index][1])) return { kind: "point", index };
    }
    return { kind: "empty" };
  }

  pointerDown(pixel: CanvasPixel, frame: CanvasFrame): boolean {
    this.grab = this.hit(pixel, frame.zoom);
    this.moved = false;
    return true;
  }

  pointerMove(pixel: CanvasPixel): void {
    const grab = this.grab;
    if (!grab || grab.kind === "empty") return;
    const to: Point = [pixel.x, pixel.y];
    const from = grab.kind === "origin" ? this.origin : this.polygon[grab.index];
    if (from && (from[0] !== to[0] || from[1] !== to[1])) this.moved = true;
    if (grab.kind === "origin") this.origin = to;
    else this.polygon[grab.index] = to;
  }

  pointerUp(pixel: CanvasPixel): void {
    this.pointerMove(pixel);
    const grab = this.grab;
    this.grab = null;
    if (!grab) return;
    const at: Point = [pixel.x, pixel.y];
    if (grab.kind === "empty") {
      if (this.mode === "origin") {
        this.gestures.change({ polygon: this.polygon, origin: at });
      } else if (this.origin) {
        this.gestures.change({ polygon: [...this.polygon, at], origin: this.origin });
      }
    } else if (this.moved && this.origin) {
      this.gestures.change({ polygon: this.polygon, origin: this.origin });
    }
  }

  draw(context: CanvasRenderingContext2D, frame: CanvasFrame): void {
    const at = (value: number, base: number) => base + (value + 0.5) * frame.zoom;
    if (this.polygon.length > 0) {
      context.beginPath();
      this.polygon.forEach(([x, y], index) => {
        const px = at(x, frame.left);
        const py = at(y, frame.top);
        if (index === 0) context.moveTo(px, py);
        else context.lineTo(px, py);
      });
      if (this.polygon.length >= 3) {
        context.closePath();
        context.fillStyle = "rgba(111, 183, 242, 0.3)";
        context.fill();
      }
      context.strokeStyle = POLYGON_COLOUR;
      context.stroke();
      context.fillStyle = POLYGON_COLOUR;
      for (const [x, y] of this.polygon) context.fillRect(at(x, frame.left) - 2, at(y, frame.top) - 2, 5, 5);
    }
    if (this.origin) {
      const x = at(this.origin[0], frame.left);
      const y = at(this.origin[1], frame.top);
      context.strokeStyle = ORIGIN_COLOUR;
      context.beginPath();
      context.moveTo(x - 7, y);
      context.lineTo(x + 7, y);
      context.moveTo(x, y - 7);
      context.lineTo(x, y + 7);
      context.stroke();
      context.strokeRect(x - 3, y - 3, 6, 6);
    }
    frame.element.dataset.footprint = this.polygon.map(([x, y]) => `${x},${y}`).join(" ");
    frame.element.dataset.footprintOrigin = this.origin ? `${this.origin[0]},${this.origin[1]}` : "";
  }
}
