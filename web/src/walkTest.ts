// The walk test (spec §6.1, §11): the Body walks the room with the arrow keys, on what `place` built. It reads walkable,
// which says where its footprint fits without touching `solid` or a pit, and never works collision out for itself.
// The foreground Layers are drawn over it by their y-sort lines, from the sort positions `place` gives (ticket 0054).

import type { Body } from "./api";
import { isTyping, type CanvasFrame, type CanvasTool } from "./pixelCanvas";

const PIXELS_PER_SECOND = 90;
const BODY_COLOUR = "#ffffff";
const KEYS: Record<string, [number, number]> = {
  ArrowLeft: [-1, 0],
  ArrowRight: [1, 0],
  ArrowUp: [0, -1],
  ArrowDown: [0, 1],
};

export interface MaskPixels {
  width: number;
  height: number;
  set: Uint8Array;
}

// A 1-bit Mask from a Command's output, one byte a pixel.
export async function loadMask(url: string): Promise<MaskPixels> {
  const image = new Image();
  image.src = url;
  await image.decode();
  const canvas = document.createElement("canvas");
  canvas.width = image.naturalWidth;
  canvas.height = image.naturalHeight;
  const context = canvas.getContext("2d", { willReadFrequently: true })!;
  context.drawImage(image, 0, 0);
  const { data } = context.getImageData(0, 0, canvas.width, canvas.height);
  const set = new Uint8Array(canvas.width * canvas.height);
  for (let index = 0; index < set.length; index++) set[index] = data[index * 4] > 127 ? 1 : 0;
  return { width: canvas.width, height: canvas.height, set };
}

function isSet(spots: MaskPixels, x: number, y: number): boolean {
  return x >= 0 && y >= 0 && x < spots.width && y < spots.height && spots.set[y * spots.width + x] === 1;
}

// A Layer's own pixels and its sort position, as `place` gives it: `y` is None for a Layer that is always above.
export interface SortedLayer {
  id: string;
  image: HTMLImageElement;
  above: boolean;
  y: number | null;
}

// Read at every draw, so a rebuilt Layer or line shows without sending the Body back to the Spawn.
export interface SortedLayers {
  layers: SortedLayer[];
}

export class WalkTest implements CanvasTool {
  private readonly held = new Set<string>();
  private frameRequest = 0;
  private last = 0;
  private owed = 0;

  constructor(
    private walkable: MaskPixels,
    private clear: MaskPixels,
    private readonly body: Body,
    private x: number,
    private y: number,
    private readonly redraw: () => void,
    private readonly sorted: SortedLayers = { layers: [] },
  ) {
    window.addEventListener("keydown", this.onKeyDown);
    window.addEventListener("keyup", this.onKeyUp);
  }

  destroy(): void {
    cancelAnimationFrame(this.frameRequest);
    window.removeEventListener("keydown", this.onKeyDown);
    window.removeEventListener("keyup", this.onKeyUp);
  }

  // A rebuild reloads the Masks under a Body already walking: it stays where it is, with its keys still held, unless
  // the rebuilt ground no longer has room for it there, and then it goes back to (x, y).
  setMasks(walkable: MaskPixels, clear: MaskPixels, x: number, y: number): void {
    this.walkable = walkable;
    this.clear = clear;
    if (!isSet(walkable, this.x, this.y)) {
      this.x = x;
      this.y = y;
    }
    this.redraw();
  }

  private walk(dx: number, dy: number): void {
    if (isSet(this.walkable, this.x + dx, this.y + dy)) {
      this.x += dx;
      this.y += dy;
    }
  }

  // Shift and an arrow: over a pit, to the first walkable spot beyond it. Only `solid` stops it, as in `reach`, and a
  // footprint clears a pit only by its own size more.
  private dash(dx: number, dy: number): void {
    if (!this.body.dash || isSet(this.walkable, this.x + dx, this.y + dy)) return;
    const across = dx ? this.body.size[0] : this.body.size[1];
    for (let distance = 1; distance <= this.body.dash + across; distance++) {
      const x = this.x + dx * distance;
      const y = this.y + dy * distance;
      if (!isSet(this.clear, x, y)) return;
      if (isSet(this.walkable, x, y)) {
        this.x = x;
        this.y = y;
        return;
      }
    }
  }

  private readonly tick = (time: number): void => {
    this.owed += ((time - this.last) / 1000) * PIXELS_PER_SECOND;
    this.last = time;
    const steps = Math.floor(this.owed);
    this.owed -= steps;
    const directions = [...this.held].map((key) => KEYS[key]);
    for (let count = 0; count < steps; count++) {
      for (const [dx, dy] of directions) this.walk(dx, dy); // One axis at a time, so the Body slides along a wall.
    }
    this.redraw();
    if (this.held.size) this.frameRequest = requestAnimationFrame(this.tick);
  };

  private readonly onKeyDown = (event: KeyboardEvent): void => {
    if (!(event.key in KEYS) || event.ctrlKey || event.metaKey || event.altKey) return;
    if (isTyping(event.target) || (event.target instanceof HTMLInputElement && event.target.type === "range")) return; // a slider's arrows
    event.preventDefault();
    if (event.shiftKey) {
      if (!event.repeat) this.dash(...KEYS[event.key]);
      this.redraw();
      return;
    }
    if (this.held.has(event.key)) return;
    this.walk(...KEYS[event.key]); // A tap moves one pixel, however short it is.
    this.redraw();
    if (!this.held.size) {
      this.last = performance.now();
      this.owed = 0;
      this.frameRequest = requestAnimationFrame(this.tick);
    }
    this.held.add(event.key);
  };

  private readonly onKeyUp = (event: KeyboardEvent): void => {
    this.held.delete(event.key);
  };

  draw(context: CanvasRenderingContext2D, frame: CanvasFrame): void {
    const [width, height] = this.body.size;
    const left = frame.left + (this.x - Math.floor(width / 2)) * frame.zoom;
    const top = frame.top + (this.y - Math.floor(height / 2)) * frame.zoom;
    context.strokeStyle = BODY_COLOUR;
    context.strokeRect(left - 0.5, top - 0.5, width * frame.zoom + 1, height * frame.zoom + 1);
    // A Layer is over the Body when the Body is north of its line (smaller y), or when it is always above. The Body's
    // position is its footprint's middle; on the line itself the Body is in front.
    context.imageSmoothingEnabled = false;
    const over = this.sorted.layers.filter((layer) => layer.above || (layer.y !== null && this.y < layer.y));
    for (const { image } of over) context.drawImage(image, frame.left, frame.top, frame.width * frame.zoom, frame.height * frame.zoom);
    frame.element.dataset.body = `${this.x},${this.y}`;
    frame.element.dataset.layersOver = over.map((layer) => layer.id).join(" ");
  }
}
