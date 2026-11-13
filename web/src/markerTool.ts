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

// The cells `area.ambiguous_cells` names, as the finding's message lists them (the finding has no field for them yet).
export function ambiguousCells(finding: { code: string; message: string }): { id: string; cells: CanvasPixel[] } | null {
  if (finding.code !== "area.ambiguous_cells") return null;
  const id = /the area '([^']+)'/.exec(finding.message)?.[1];
  const listed = /top-left pixels at (.*)$/.exec(finding.message)?.[1];
  if (!id || !listed) return null;
  const cells = [...listed.matchAll(/\((\d+), (\d+)\)/g)].map((found) => ({ x: Number(found[1]), y: Number(found[2]) }));
  return { id, cells };
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
  area: "#4ee0d0",
};
const UNREACHABLE = "#ff3b6b";
const SELECTED = "#ffffff";
const HIT_RADIUS = 6; // canvas pixels around a Marker

type Corner = "nw" | "ne" | "sw" | "se";
type Drag =
  | { marker: Marker; end: boolean; moved: boolean }
  | { start: CanvasPixel; at: CanvasPixel }
  | AreaDrag;
type AreaDrag = {
  area: Marker;
  origin: Marker;
  how: Corner | "move";
  from: CanvasPixel;
  room: { width: number; height: number };
  moved: boolean;
};

export function isDrawnFromTwoPoints(type: string): boolean {
  return type === "ysort" || type === "area";
}

export interface Box {
  x: number;
  y: number;
  x2: number;
  y2: number;
}

// The box between two corners, corners inclusive; with a `cell`, widened outward to whole cells from the room's top-left
// corner, as the Decision does it, so the box shown while dragging is the box that is kept.
export function boxBetween(a: CanvasPixel, b: CanvasPixel, cell: number | null): Box {
  const box = { x: Math.min(a.x, b.x), y: Math.min(a.y, b.y), x2: Math.max(a.x, b.x), y2: Math.max(a.y, b.y) };
  return cell ? snapOut(box, cell) : box;
}

function snapOut(box: Box, cell: number): Box {
  return {
    x: Math.floor(box.x / cell) * cell,
    y: Math.floor(box.y / cell) * cell,
    x2: (Math.floor(box.x2 / cell) + 1) * cell - 1,
    y2: (Math.floor(box.y2 / cell) + 1) * cell - 1,
  };
}

function cellOf(marker: Marker): number | null {
  return typeof marker.cell === "number" && marker.cell > 0 ? marker.cell : null;
}

function boxOf(marker: Marker): Box {
  return { x: marker.x, y: marker.y, x2: marker.x2 ?? marker.x, y2: marker.y2 ?? marker.y };
}

const AREA_ALPHA = "33";

export class MarkerTool implements CanvasTool {
  private markers: Marker[] = [];
  private unreachable = new Set<string>();
  private selected: string | null = null;
  private drag: Drag | null = null;
  private ambiguous = new Map<string, CanvasPixel[]>();
  private drawing: { type: string; cell: number | null } = { type: "", cell: null };

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

  // What a drag on empty canvas draws, for its preview.
  setDrawing(type: string, cell: number | null): void {
    this.drawing = { type, cell };
  }

  setAmbiguous(found: { id: string; cells: CanvasPixel[] }[]): void {
    this.ambiguous = new Map(found.map((entry) => [entry.id, entry.cells]));
  }

  // An area is resized by any corner, and moved by its inside once it is selected.
  private hitArea(pixel: CanvasPixel, zoom: number): { area: Marker; how: Corner | "move" } | null {
    const near = (x: number, y: number) =>
      Math.hypot((x - pixel.x) * zoom, (y - pixel.y) * zoom) <= Math.max(HIT_RADIUS, zoom);
    const areas = [...this.markers].reverse().filter((marker) => marker.type === "area");
    for (const area of areas) {
      const { x, y, x2, y2 } = boxOf(area);
      if (near(x, y)) return { area, how: "nw" };
      if (near(x2, y)) return { area, how: "ne" };
      if (near(x, y2)) return { area, how: "sw" };
      if (near(x2, y2)) return { area, how: "se" };
    }
    for (const area of areas) {
      const { x, y, x2, y2 } = boxOf(area);
      if (area.id === this.selected && pixel.x >= x && pixel.x <= x2 && pixel.y >= y && pixel.y <= y2) {
        return { area, how: "move" };
      }
    }
    return null;
  }

  private dragArea(drag: AreaDrag, pixel: CanvasPixel): void {
    const start = boxOf(drag.origin);
    const cell = cellOf(drag.origin);
    let box: Box;
    if (drag.how === "move") {
      let dx = pixel.x - drag.from.x;
      let dy = pixel.y - drag.from.y;
      if (cell) {
        dx = Math.round(dx / cell) * cell;
        dy = Math.round(dy / cell) * cell;
      }
      // Kept inside the room on all four sides; a box wider than the room keeps its top-left corner in.
      dx = Math.max(Math.min(dx, drag.room.width - 1 - start.x2), -start.x);
      dy = Math.max(Math.min(dy, drag.room.height - 1 - start.y2), -start.y);
      box = { x: start.x + dx, y: start.y + dy, x2: start.x2 + dx, y2: start.y2 + dy };
    } else {
      const fixed = { x: drag.how.endsWith("w") ? start.x2 : start.x, y: drag.how.startsWith("n") ? start.y2 : start.y };
      const inside = {
        x: Math.min(Math.max(0, pixel.x), drag.room.width - 1),
        y: Math.min(Math.max(0, pixel.y), drag.room.height - 1),
      };
      box = boxBetween(fixed, inside, cell);
    }
    Object.assign(drag.area, box);
  }

  private hit(pixel: CanvasPixel, zoom: number): { marker: Marker; end: boolean } | null {
    const near = (x: number, y: number) =>
      Math.hypot((x - pixel.x) * zoom, (y - pixel.y) * zoom) <= Math.max(HIT_RADIUS, zoom);
    for (const marker of [...this.markers].reverse().filter((one) => one.type !== "area")) {
      if (marker.x2 !== undefined && marker.y2 !== undefined && near(marker.x2, marker.y2)) return { marker, end: true };
      if (near(marker.x, marker.y)) return { marker, end: false };
    }
    return null;
  }

  pointerDown(pixel: CanvasPixel, frame: CanvasFrame): boolean {
    if (!this.gestures) return false;
    const inArea = this.hitArea(pixel, frame.zoom);
    if (inArea) {
      const room = { width: frame.width, height: frame.height };
      this.drag = { area: inArea.area, origin: { ...inArea.area }, how: inArea.how, from: pixel, room, moved: false };
      return true;
    }
    const found = this.hit(pixel, frame.zoom);
    this.drag = found ? { ...found, moved: false } : { start: pixel, at: pixel };
    return true;
  }

  pointerMove(pixel: CanvasPixel): void {
    if (!this.drag) return;
    if ("area" in this.drag) {
      this.dragArea(this.drag, pixel);
      const [now, was] = [boxOf(this.drag.area), boxOf(this.drag.origin)];
      this.drag.moved = now.x !== was.x || now.y !== was.y || now.x2 !== was.x2 || now.y2 !== was.y2;
    } else if ("start" in this.drag) {
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
    if ("area" in drag) {
      if (drag.moved) this.gestures.move({ ...drag.area });
      else this.gestures.select(drag.area);
    } else if ("start" in drag) this.gestures.place(drag.start, drag.at);
    else if (drag.moved) this.gestures.move({ ...drag.marker });
    else this.gestures.select(drag.marker);
  }

  draw(context: CanvasRenderingContext2D, frame: CanvasFrame): void {
    const at = (value: number, origin: number) => origin + (value + 0.5) * frame.zoom;
    const grid = (box: Box, cell: number | null, colour: string) => {
      const left = frame.left + box.x * frame.zoom;
      const top = frame.top + box.y * frame.zoom;
      const width = (box.x2 - box.x + 1) * frame.zoom;
      const height = (box.y2 - box.y + 1) * frame.zoom;
      context.strokeStyle = colour;
      context.fillStyle = colour + AREA_ALPHA;
      context.fillRect(left, top, width, height);
      context.strokeRect(left + 0.5, top + 0.5, width - 1, height - 1);
      if (cell) {
        context.beginPath();
        for (let x = box.x + cell; x <= box.x2; x += cell) {
          context.moveTo(frame.left + x * frame.zoom + 0.5, top);
          context.lineTo(frame.left + x * frame.zoom + 0.5, top + height);
        }
        for (let y = box.y + cell; y <= box.y2; y += cell) {
          context.moveTo(left, frame.top + y * frame.zoom + 0.5);
          context.lineTo(left + width, frame.top + y * frame.zoom + 0.5);
        }
        context.stroke();
      }
    };
    if (this.drag && "start" in this.drag && this.drawing.type === "area") {
      grid(boxBetween(this.drag.start, this.drag.at, this.drawing.cell), this.drawing.cell, SELECTED);
    } else if (this.drag && "start" in this.drag && this.drag.at !== this.drag.start) {
      context.strokeStyle = SELECTED;
      context.beginPath();
      context.moveTo(at(this.drag.start.x, frame.left), at(this.drag.start.y, frame.top));
      context.lineTo(at(this.drag.at.x, frame.left), at(this.drag.at.y, frame.top));
      context.stroke();
    }
    for (const marker of this.markers) {
      if (marker.type === "area") {
        const box = boxOf(marker);
        const cell = cellOf(marker);
        const colour = this.unreachable.has(marker.id) ? UNREACHABLE : COLOURS.area;
        grid(box, cell, colour);
        for (const found of this.ambiguous.get(marker.id) ?? []) {
          const size = (cell ?? 1) * frame.zoom;
          context.fillStyle = "#ffd400aa";
          context.fillRect(frame.left + found.x * frame.zoom, frame.top + found.y * frame.zoom, size, size);
        }
        context.fillStyle = colour;
        for (const [cx, cy] of [[box.x, box.y], [box.x2, box.y], [box.x, box.y2], [box.x2, box.y2]]) {
          context.fillRect(at(cx, frame.left) - 3, at(cy, frame.top) - 3, 6, 6);
        }
        if (marker.id === this.selected) {
          context.strokeStyle = SELECTED;
          context.lineWidth = 2;
          context.strokeRect(
            frame.left + box.x * frame.zoom,
            frame.top + box.y * frame.zoom,
            (box.x2 - box.x + 1) * frame.zoom,
            (box.y2 - box.y + 1) * frame.zoom,
          );
          context.lineWidth = 1;
        }
        context.fillStyle = colour;
        context.fillText(marker.id, frame.left + box.x * frame.zoom + 4, frame.top + box.y * frame.zoom + 12);
        continue;
      }
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
    frame.element.dataset.markers = this.markers
      .map((marker) => `${marker.id}@${marker.x},${marker.y}${marker.type === "area" ? `-${marker.x2},${marker.y2}` : ""}`)
      .join(" ");
    frame.element.dataset.ambiguous = [...this.ambiguous]
      .flatMap(([id, cells]) => cells.map((found) => `${id}@${found.x},${found.y}`))
      .join(" ");
    frame.element.dataset.unreachable = [...this.unreachable].join(" ");
  }
}
