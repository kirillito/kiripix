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

export type EmitterShape =
  | { type: "point" }
  | { type: "line" | "box"; x2: number; y2: number }
  | { type: "polygon"; points: [number, number][] };

export type EmitterMode = "shape" | "direction" | "eyedrop";

// What the Owner drew with an emitter selected; the panel turns each into one `marker` Decision.
export type EmitterGesture =
  | { kind: "box" | "line"; start: CanvasPixel; end: CanvasPixel }
  | { kind: "polygon"; points: [number, number][] }
  | { kind: "direction"; end: CanvasPixel }
  | { kind: "pick"; pixel: CanvasPixel };

export function shapeOf(marker: Marker): EmitterShape | null {
  return (marker.shape as EmitterShape | null | undefined) ?? null;
}

export function directionOf(marker: Marker): CanvasPixel | null {
  return (marker.direction as CanvasPixel | null | undefined) ?? null;
}

export function coloursOf(marker: Marker): string[] {
  return (marker.colours as string[] | null | undefined) ?? [];
}

// The length of an emitter's arrow, in px, to the nearest whole px.
export function arrowLength(marker: Marker): number | null {
  const direction = directionOf(marker);
  return direction ? Math.round(Math.hypot(direction.x - marker.x, direction.y - marker.y)) : null;
}

export interface MarkerGestures {
  place(pixel: CanvasPixel, end: CanvasPixel): void;
  move(marker: Marker): void;
  select(marker: Marker): void;
  emitter?(gesture: EmitterGesture): void;
}

// Every pixel an emitter's drawing reaches.
function reach(marker: Marker): [number, number][] {
  const found: [number, number][] = [[marker.x, marker.y]];
  const shape = shapeOf(marker);
  if (shape?.type === "line" || shape?.type === "box") found.push([shape.x2, shape.y2]);
  if (shape?.type === "polygon") found.push(...shape.points);
  const direction = directionOf(marker);
  if (direction) found.push([direction.x, direction.y]);
  return found;
}

// An emitter moved as one: its point, its shape and its arrow, kept inside the room.
function translated(origin: Marker, dx: number, dy: number, room: { width: number; height: number }): Marker {
  const points = reach(origin);
  const xs = points.map(([x]) => x);
  const ys = points.map(([, y]) => y);
  dx = Math.max(Math.min(dx, room.width - 1 - Math.max(...xs)), -Math.min(...xs));
  dy = Math.max(Math.min(dy, room.height - 1 - Math.max(...ys)), -Math.min(...ys));
  const moved: Marker = { ...origin, x: origin.x + dx, y: origin.y + dy };
  const shape = shapeOf(origin);
  if (shape?.type === "line" || shape?.type === "box") moved.shape = { ...shape, x2: shape.x2 + dx, y2: shape.y2 + dy };
  if (shape?.type === "polygon") moved.shape = { type: "polygon", points: shape.points.map(([x, y]) => [x + dx, y + dy]) };
  const direction = directionOf(origin);
  if (direction) moved.direction = { x: direction.x + dx, y: direction.y + dy };
  return moved;
}

function inside(points: [number, number][], x: number, y: number): boolean {
  let found = false;
  for (let i = 0, j = points.length - 1; i < points.length; j = i++) {
    const [xi, yi] = points[i];
    const [xj, yj] = points[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) found = !found;
  }
  return found;
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
type Handle = "direction" | "end" | "move" | Corner | { point: number };
type Drag =
  | { marker: Marker; end: boolean; moved: boolean }
  | { start: CanvasPixel; at: CanvasPixel }
  | AreaDrag
  | { kind: "emitter"; marker: Marker; origin: Marker; how: Handle; from: CanvasPixel; room: { width: number; height: number }; moved: boolean }
  | { kind: "aim"; aim: "shape" | "direction"; start: CanvasPixel; at: CanvasPixel }
  | { kind: "pick"; at: CanvasPixel }
  | { kind: "click"; at: CanvasPixel };
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
  private mode: EmitterMode = "shape";
  private shapeKind = "point";
  private polygonDrawing = false;
  private draft: [number, number][] = [];
  private cursor: CanvasPixel | null = null;

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

  // What a drag on the room does with an emitter selected: the tool, the shape being drawn, and whether a polygon is open.
  setEmitter(mode: EmitterMode, shapeKind: string, polygonDrawing: boolean): void {
    this.mode = mode;
    this.shapeKind = shapeKind;
    if (!polygonDrawing) this.draft = [];
    this.polygonDrawing = polygonDrawing;
  }

  // The open polygon, closed with the points so far (null when it has fewer than three).
  closePolygon(): [number, number][] | null {
    const points = this.draft;
    this.draft = [];
    return points.length >= 3 ? points : null;
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

  private selectedEmitter(): Marker | null {
    return this.markers.find((marker) => marker.id === this.selected && marker.type === "emitter") ?? null;
  }

  // What of the selected emitter is under the pointer: its arrow's end, a corner or point of its shape, its own point, or
  // (for a box or polygon) its inside, which moves the whole emitter.
  private hitEmitter(emitter: Marker, pixel: CanvasPixel, zoom: number): { how: Handle; from: CanvasPixel } | null {
    const near = (x: number, y: number) => Math.hypot((x - pixel.x) * zoom, (y - pixel.y) * zoom) <= Math.max(HIT_RADIUS, zoom);
    const direction = directionOf(emitter);
    if (direction && near(direction.x, direction.y)) return { how: "direction", from: pixel };
    const shape = shapeOf(emitter);
    if (shape?.type === "box") {
      for (const [how, x, y] of [["nw", emitter.x, emitter.y], ["ne", shape.x2, emitter.y], ["sw", emitter.x, shape.y2], ["se", shape.x2, shape.y2]] as const) {
        if (near(x, y)) return { how, from: pixel };
      }
    }
    if (shape?.type === "line" && near(shape.x2, shape.y2)) return { how: "end", from: pixel };
    if (shape?.type === "polygon") {
      for (let index = shape.points.length - 1; index >= 0; index--) {
        if (near(shape.points[index][0], shape.points[index][1])) return { how: { point: index }, from: pixel };
      }
    }
    if (near(emitter.x, emitter.y)) return { how: "move", from: { x: emitter.x, y: emitter.y } };
    if (shape?.type === "box" && pixel.x >= emitter.x && pixel.x <= shape.x2 && pixel.y >= emitter.y && pixel.y <= shape.y2) {
      return { how: "move", from: pixel };
    }
    if (shape?.type === "polygon" && inside(shape.points, pixel.x, pixel.y)) return { how: "move", from: pixel };
    return null;
  }

  private dragEmitter(drag: Extract<Drag, { kind: "emitter" }>, pixel: CanvasPixel): void {
    const { origin, how, marker } = drag;
    const shape = shapeOf(origin);
    if (how === "direction") {
      marker.direction = { x: pixel.x, y: pixel.y };
    } else if (how === "end" && shape && shape.type !== "point" && shape.type !== "polygon") {
      marker.shape = { ...shape, x2: pixel.x, y2: pixel.y };
    } else if (how === "move") {
      Object.assign(marker, translated(origin, pixel.x - drag.from.x, pixel.y - drag.from.y, drag.room));
    } else if (typeof how === "object" && shape?.type === "polygon") {
      marker.shape = { type: "polygon", points: shape.points.map((point, index) => (index === how.point ? [pixel.x, pixel.y] : point)) };
    } else if (typeof how === "string" && shape?.type === "box") {
      const fixed = { x: how.endsWith("w") ? shape.x2 : origin.x, y: how.startsWith("n") ? shape.y2 : origin.y };
      const box = boxBetween(fixed, pixel, null);
      marker.x = box.x;
      marker.y = box.y;
      marker.shape = { type: "box", x2: box.x2, y2: box.y2 };
    }
    drag.moved = JSON.stringify([marker.x, marker.y, marker.shape, marker.direction]) !== JSON.stringify([origin.x, origin.y, origin.shape, origin.direction]);
  }

  private pointerDownEmitter(emitter: Marker, pixel: CanvasPixel, frame: CanvasFrame): boolean {
    if (this.mode === "eyedrop") {
      this.drag = { kind: "pick", at: pixel };
      return true;
    }
    if (this.polygonDrawing) {
      this.drag = { kind: "click", at: pixel };
      return true;
    }
    const room = { width: frame.width, height: frame.height };
    const found = this.mode === "direction" ? this.hitEmitterDirection(emitter, pixel, frame.zoom) : this.hitEmitter(emitter, pixel, frame.zoom);
    if (found) {
      this.drag = { kind: "emitter", marker: emitter, origin: { ...emitter }, how: found.how, from: found.from, room, moved: false };
      return true;
    }
    if (this.mode === "direction") {
      this.drag = { kind: "aim", aim: "direction", start: pixel, at: pixel };
      return true;
    }
    if (this.shapeKind === "box" || this.shapeKind === "line") {
      this.drag = { kind: "aim", aim: "shape", start: pixel, at: pixel };
      return true;
    }
    return false;
  }

  private hitEmitterDirection(emitter: Marker, pixel: CanvasPixel, zoom: number): { how: Handle; from: CanvasPixel } | null {
    const direction = directionOf(emitter);
    const near = direction && Math.hypot((direction.x - pixel.x) * zoom, (direction.y - pixel.y) * zoom) <= Math.max(HIT_RADIUS, zoom);
    return near ? { how: "direction", from: pixel } : null;
  }

  pointerDown(pixel: CanvasPixel, frame: CanvasFrame): boolean {
    if (!this.gestures) return false;
    const emitter = this.selectedEmitter();
    if (emitter && this.gestures.emitter && this.pointerDownEmitter(emitter, pixel, frame)) return true;
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

  hover(pixel: CanvasPixel | null): void {
    this.cursor = pixel;
  }

  pointerMove(pixel: CanvasPixel): void {
    if (!this.drag) return;
    if ("kind" in this.drag) {
      if (this.drag.kind === "emitter") this.dragEmitter(this.drag, pixel);
      else this.drag.at = pixel;
    } else if ("area" in this.drag) {
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
    if ("kind" in drag) {
      if (drag.kind === "emitter") {
        if (drag.moved) this.gestures.move({ ...drag.marker });
        else this.gestures.select(drag.marker);
      } else if (drag.kind === "pick") {
        this.gestures.emitter?.({ kind: "pick", pixel: drag.at });
      } else if (drag.kind === "click") {
        const first = this.draft[0];
        if (first && this.draft.length >= 3 && first[0] === drag.at.x && first[1] === drag.at.y) {
          this.gestures.emitter?.({ kind: "polygon", points: this.closePolygon() ?? [] });
        } else if (!this.draft.some(([x, y]) => x === drag.at.x && y === drag.at.y)) {
          this.draft.push([drag.at.x, drag.at.y]);
        }
      } else if (drag.aim === "direction") {
        this.gestures.emitter?.({ kind: "direction", end: drag.at });
      } else if (drag.start.x !== drag.at.x || drag.start.y !== drag.at.y) {
        this.gestures.emitter?.({ kind: this.shapeKind === "line" ? "line" : "box", start: drag.start, end: drag.at });
      }
    } else if ("area" in drag) {
      if (drag.moved) this.gestures.move({ ...drag.area });
      else this.gestures.select(drag.area);
    } else if ("start" in drag) this.gestures.place(drag.start, drag.at);
    else if (drag.moved) this.gestures.move({ ...drag.marker });
    else this.gestures.select(drag.marker);
  }

  // The arrow from an emitter to `end`, its length in px, and a few still dots along it in the chosen colours.
  private arrow(context: CanvasRenderingContext2D, frame: CanvasFrame, emitter: Marker, end: CanvasPixel, colours: string[]): void {
    const at = (value: number, origin: number) => origin + (value + 0.5) * frame.zoom;
    const [x1, y1, x2, y2] = [at(emitter.x, frame.left), at(emitter.y, frame.top), at(end.x, frame.left), at(end.y, frame.top)];
    context.strokeStyle = SELECTED;
    context.fillStyle = SELECTED;
    context.beginPath();
    context.moveTo(x1, y1);
    context.lineTo(x2, y2);
    const angle = Math.atan2(y2 - y1, x2 - x1);
    for (const side of [-0.45, 0.45]) {
      context.moveTo(x2, y2);
      context.lineTo(x2 - 9 * Math.cos(angle + side), y2 - 9 * Math.sin(angle + side));
    }
    context.stroke();
    const size = Math.max(2, frame.zoom);
    const dots = 5;
    for (let index = 0; index < dots; index++) {
      const along = (index + 1) / (dots + 1);
      context.fillStyle = colours[index % colours.length];
      context.fillRect(x1 + (x2 - x1) * along - size / 2, y1 + (y2 - y1) * along - size / 2, size, size);
    }
    context.fillStyle = SELECTED;
    context.fillText(`${Math.round(Math.hypot(end.x - emitter.x, end.y - emitter.y))} px`, (x1 + x2) / 2 + 6, (y1 + y2) / 2 - 6);
  }

  // An emitter's shape at low opacity in its first colour, its arrow, and, once it is selected, handles on its shape.
  private drawEmitter(
    context: CanvasRenderingContext2D,
    frame: CanvasFrame,
    emitter: Marker,
    grid: (box: Box, cell: number | null, colour: string) => void,
  ): void {
    const at = (value: number, origin: number) => origin + (value + 0.5) * frame.zoom;
    const colours = coloursOf(emitter);
    const colour = colours[0] ?? COLOURS.emitter;
    const shape = shapeOf(emitter);
    context.lineWidth = 1;
    if (shape?.type === "box") {
      grid({ x: emitter.x, y: emitter.y, x2: shape.x2, y2: shape.y2 }, null, colour);
    } else if (shape?.type === "line" || shape?.type === "polygon") {
      const points: [number, number][] = shape.type === "polygon" ? shape.points : [[emitter.x, emitter.y], [shape.x2, shape.y2]];
      context.strokeStyle = colour;
      context.fillStyle = colour + AREA_ALPHA;
      context.beginPath();
      points.forEach(([x, y], index) => (index === 0 ? context.moveTo(at(x, frame.left), at(y, frame.top)) : context.lineTo(at(x, frame.left), at(y, frame.top))));
      if (shape.type === "polygon") {
        context.closePath();
        context.fill();
      }
      context.stroke();
    }
    const direction = directionOf(emitter);
    if (direction) this.arrow(context, frame, emitter, direction, colours.length > 0 ? colours : [colour]);
    if (emitter.id !== this.selected) return;
    context.fillStyle = SELECTED;
    const handles: [number, number][] = [];
    if (shape?.type === "box") handles.push([shape.x2, emitter.y], [emitter.x, shape.y2], [shape.x2, shape.y2]);
    if (shape?.type === "line") handles.push([shape.x2, shape.y2]);
    if (shape?.type === "polygon") handles.push(...shape.points);
    if (direction) handles.push([direction.x, direction.y]);
    for (const [x, y] of handles) context.fillRect(at(x, frame.left) - 3, at(y, frame.top) - 3, 6, 6);
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
    const plain = this.drag && !("kind" in this.drag) ? this.drag : null;
    if (this.drag && "kind" in this.drag && this.drag.kind === "aim") {
      const { start, at: end } = this.drag;
      context.strokeStyle = SELECTED;
      if (this.drag.aim === "direction") {
        const emitter = this.selectedEmitter();
        if (emitter) this.arrow(context, frame, emitter, end, [SELECTED]);
      } else if (this.shapeKind === "line") {
        context.beginPath();
        context.moveTo(at(start.x, frame.left), at(start.y, frame.top));
        context.lineTo(at(end.x, frame.left), at(end.y, frame.top));
        context.stroke();
      } else {
        grid(boxBetween(start, end, null), null, SELECTED);
      }
    }
    if (this.polygonDrawing && this.draft.length > 0) {
      context.strokeStyle = SELECTED;
      context.fillStyle = SELECTED;
      context.beginPath();
      this.draft.forEach(([x, y], index) => (index === 0 ? context.moveTo(at(x, frame.left), at(y, frame.top)) : context.lineTo(at(x, frame.left), at(y, frame.top))));
      if (this.cursor) context.lineTo(at(this.cursor.x, frame.left), at(this.cursor.y, frame.top));
      context.stroke();
      this.draft.forEach(([x, y], index) => {
        const size = index === 0 ? 8 : 5; // the first point is bigger: a click on it closes the polygon
        context.fillRect(at(x, frame.left) - size / 2, at(y, frame.top) - size / 2, size, size);
      });
    }
    if (plain && "start" in plain && this.drawing.type === "area") {
      grid(boxBetween(plain.start, plain.at, this.drawing.cell), this.drawing.cell, SELECTED);
    } else if (plain && "start" in plain && plain.at !== plain.start) {
      context.strokeStyle = SELECTED;
      context.beginPath();
      context.moveTo(at(plain.start.x, frame.left), at(plain.start.y, frame.top));
      context.lineTo(at(plain.at.x, frame.left), at(plain.at.y, frame.top));
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
      if (marker.type === "emitter") this.drawEmitter(context, frame, marker, grid);
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
    frame.element.dataset.emitters = this.markers
      .filter((marker) => marker.type === "emitter")
      .map((marker) => {
        const direction = directionOf(marker);
        return `${marker.id}:${shapeOf(marker)?.type ?? "none"}:${direction ? `${direction.x},${direction.y}` : "-"}:${coloursOf(marker).join("|")}`;
      })
      .join(" ");
    frame.element.dataset.markers = this.markers
      .map((marker) => `${marker.id}@${marker.x},${marker.y}${marker.type === "area" ? `-${marker.x2},${marker.y2}` : ""}`)
      .join(" ");
    frame.element.dataset.ambiguous = [...this.ambiguous]
      .flatMap(([id, cells]) => cells.map((found) => `${id}@${found.x},${found.y}`))
      .join(" ");
    frame.element.dataset.unreachable = [...this.unreachable].join(" ");
  }
}
