// The Markers on the canvas (ADR 0008): a plain class, so a drag never goes through React state. On the place screen a
// click places one, and a drag moves one or draws a y-sort line; each is one `decide`, on release (spec §11). On the reach
// screen the Markers only show, with the unreachable ones highlighted.

import type { CanvasFrame, CanvasPixel, CanvasTool } from "./pixelCanvas";

export interface Marker {
  id: string;
  type: string;
  x: number;
  y: number;
  x2?: number;
  y2?: number;
  [field: string]: unknown;
}

export interface MarkerGestures {
  place(pixel: CanvasPixel, end: CanvasPixel): void;
  move(marker: Marker): void;
  select(marker: Marker): void;
}

const COLOURS: Record<string, string> = {
  spawn: "#6fcf8e",
  exit: "#f2c14e",
  interactable: "#6fb7f2",
  light: "#fff1a8",
  emitter: "#c79bff",
  ysort: "#ff9b6b",
};
const UNREACHABLE = "#ff3b6b";
const SELECTED = "#ffffff";
const HIT_RADIUS = 6; // canvas pixels around a Marker

type Drag = { marker: Marker; end: boolean; moved: boolean } | { start: CanvasPixel; at: CanvasPixel };

export function isDrawnFromTwoPoints(type: string): boolean {
  return type === "ysort";
}

export class MarkerTool implements CanvasTool {
  private markers: Marker[] = [];
  private unreachable = new Set<string>();
  private selected: string | null = null;
  private drag: Drag | null = null;

  constructor(private readonly gestures: MarkerGestures | null) {}

  setMarkers(markers: Marker[]): void {
    if (!this.drag) this.markers = markers.map((marker) => ({ ...marker }));
  }

  setUnreachable(ids: string[]): void {
    this.unreachable = new Set(ids);
  }

  setSelected(id: string | null): void {
    this.selected = id;
  }

  private hit(pixel: CanvasPixel, zoom: number): { marker: Marker; end: boolean } | null {
    const near = (x: number, y: number) =>
      Math.hypot((x - pixel.x) * zoom, (y - pixel.y) * zoom) <= Math.max(HIT_RADIUS, zoom);
    for (const marker of [...this.markers].reverse()) {
      if (marker.x2 !== undefined && marker.y2 !== undefined && near(marker.x2, marker.y2)) return { marker, end: true };
      if (near(marker.x, marker.y)) return { marker, end: false };
    }
    return null;
  }

  pointerDown(pixel: CanvasPixel, frame: CanvasFrame): boolean {
    if (!this.gestures) return false;
    const found = this.hit(pixel, frame.zoom);
    this.drag = found ? { ...found, moved: false } : { start: pixel, at: pixel };
    return true;
  }

  pointerMove(pixel: CanvasPixel): void {
    if (!this.drag) return;
    if ("start" in this.drag) {
      this.drag.at = pixel;
    } else if (this.drag.end) {
      this.drag.moved ||= this.drag.marker.x2 !== pixel.x || this.drag.marker.y2 !== pixel.y;
      this.drag.marker.x2 = pixel.x;
      this.drag.marker.y2 = pixel.y;
    } else {
      this.drag.moved ||= this.drag.marker.x !== pixel.x || this.drag.marker.y !== pixel.y;
      this.drag.marker.x = pixel.x;
      this.drag.marker.y = pixel.y;
    }
  }

  pointerUp(pixel: CanvasPixel): void {
    this.pointerMove(pixel);
    const drag = this.drag;
    this.drag = null;
    if (!drag || !this.gestures) return;
    if ("start" in drag) this.gestures.place(drag.start, drag.at);
    else if (drag.moved) this.gestures.move({ ...drag.marker });
    else this.gestures.select(drag.marker);
  }

  draw(context: CanvasRenderingContext2D, frame: CanvasFrame): void {
    const at = (value: number, origin: number) => origin + (value + 0.5) * frame.zoom;
    if (this.drag && "start" in this.drag && this.drag.at !== this.drag.start) {
      context.strokeStyle = SELECTED;
      context.beginPath();
      context.moveTo(at(this.drag.start.x, frame.left), at(this.drag.start.y, frame.top));
      context.lineTo(at(this.drag.at.x, frame.left), at(this.drag.at.y, frame.top));
      context.stroke();
    }
    for (const marker of this.markers) {
      const x = at(marker.x, frame.left);
      const y = at(marker.y, frame.top);
      const colour = this.unreachable.has(marker.id) ? UNREACHABLE : (COLOURS[marker.type] ?? SELECTED);
      context.strokeStyle = colour;
      context.fillStyle = colour;
      context.lineWidth = marker.id === this.selected ? 2 : 1;
      if (marker.x2 !== undefined && marker.y2 !== undefined) {
        context.beginPath();
        context.moveTo(x, y);
        context.lineTo(at(marker.x2, frame.left), at(marker.y2, frame.top));
        context.stroke();
      }
      context.fillRect(x - 2, y - 2, 4, 4);
      if (marker.id === this.selected || this.unreachable.has(marker.id)) context.strokeRect(x - 5, y - 5, 10, 10);
      context.fillText(marker.id, x + 6, y - 4);
      context.lineWidth = 1;
    }
    frame.element.dataset.markers = this.markers.map((marker) => `${marker.id}@${marker.x},${marker.y}`).join(" ");
    frame.element.dataset.unreachable = [...this.unreachable].join(" ");
  }
}
