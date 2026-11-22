// The room's normals on the canvas (ticket 0343): the room lit by a point light that follows the mouse, a preview drawn here
// from the built `normal.png` and the room's image (a 2D dot-product, never Godot's light), and the boxes of the
// `normals.not_flat_walkable` findings. It holds no logic about the Stage: the normals are read as the Stage wrote them.
// Painting is the masks screen's `MaskTool`; this tool only draws under it.

import type { CanvasFrame, CanvasPixel, CanvasTool } from "./pixelCanvas";

const AMBIENT = 0.35; // as `preview --overlay lit`: ambient 0.35, a flat pixel keeps its colour under the light overhead
const BRIGHTEST = 1.5;
const BOX_COLOUR = "#ffb84d";

export interface Pixels {
  width: number;
  height: number;
  data: Uint8ClampedArray;
}

export async function loadPixels(url: string): Promise<Pixels> {
  const image = new Image();
  await new Promise<void>((resolve, reject) => {
    image.onload = () => resolve();
    image.onerror = () => reject(new Error(`can't load ${url}`));
    image.src = url;
  });
  const canvas = document.createElement("canvas");
  canvas.width = image.naturalWidth;
  canvas.height = image.naturalHeight;
  const context = canvas.getContext("2d", { willReadFrequently: true })!;
  context.drawImage(image, 0, 0);
  return { width: canvas.width, height: canvas.height, data: context.getImageData(0, 0, canvas.width, canvas.height).data };
}

export interface Box {
  x: number;
  y: number;
  width: number;
  height: number;
}

export class LitTool implements CanvasTool {
  lit = true;
  normals: Pixels | null = null;
  base: Pixels | null = null;
  boxes: Box[] = [];
  private light: CanvasPixel | null = null;
  private scratch: HTMLCanvasElement | null = null;

  hover(pixel: CanvasPixel | null): void {
    this.light = pixel; // leaving the image keeps the light where it was
  }

  // The room lit from (lx, ly) at a height of about a tenth of the room's longer side.
  private shade(normals: Pixels, base: Pixels, light: CanvasPixel): ImageData {
    const { width, height } = normals;
    const out = new ImageData(width, height);
    const lz = Math.max(12, Math.max(width, height) / 8);
    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        const at = (y * width + x) * 4;
        const nx = (normals.data[at] / 255) * 2 - 1;
        const ny = -((normals.data[at + 1] / 255) * 2 - 1); // the encoding's y is up; the image's is down
        const nz = (normals.data[at + 2] / 255) * 2 - 1;
        const dx = light.x - x;
        const dy = light.y - y;
        const length = Math.hypot(dx, dy, lz);
        const flat = lz / length; // what a flat pixel takes from this light
        const dot = (nx * dx + ny * dy + nz * lz) / length;
        const factor = dot <= 0 ? AMBIENT : Math.min(BRIGHTEST, AMBIENT + (1 - AMBIENT) * (dot / flat));
        out.data[at] = base.data[at] * factor;
        out.data[at + 1] = base.data[at + 1] * factor;
        out.data[at + 2] = base.data[at + 2] * factor;
        out.data[at + 3] = base.data[at + 3];
      }
    }
    return out;
  }

  draw(context: CanvasRenderingContext2D, frame: CanvasFrame): void {
    const data = frame.element.dataset;
    const normals = this.normals;
    const base = this.base;
    const light = this.light ?? { x: 0, y: 0 };
    const showing = this.lit && normals !== null && base !== null && normals.width === frame.width && normals.height === frame.height &&
      base.width === normals.width && base.height === normals.height;
    data.view = showing ? "lit" : "normals";
    data.light = `${light.x},${light.y}`;
    if (showing) {
      if (!this.scratch) this.scratch = document.createElement("canvas");
      this.scratch.width = frame.width;
      this.scratch.height = frame.height;
      this.scratch.getContext("2d")!.putImageData(this.shade(normals, base, light), 0, 0);
      context.imageSmoothingEnabled = false;
      context.drawImage(this.scratch, frame.left, frame.top, frame.width * frame.zoom, frame.height * frame.zoom);
      data.litSample = [...this.scratch.getContext("2d")!.getImageData(frame.width >> 1, frame.height >> 1, 1, 1).data].join(","); // the middle pixel, for the tests
    } else {
      delete data.litSample;
    }
    context.save();
    context.strokeStyle = BOX_COLOUR;
    context.lineWidth = 2;
    context.setLineDash([4, 3]);
    for (const box of this.boxes) {
      context.strokeRect(frame.left + box.x * frame.zoom, frame.top + box.y * frame.zoom, box.width * frame.zoom, box.height * frame.zoom);
    }
    context.restore();
    data.normalBoxes = this.boxes.map((box) => `${box.x},${box.y},${box.width},${box.height}`).join(" ");
  }
}

// The Override a brush stroke or a polygon makes: the room's size, the painted pixels in `rgba`, the rest clear. Rasterised by
// hand, on pixel centres, so no pixel is half-painted by smoothing.
export function overlayPng(
  width: number,
  height: number,
  shape: { kind: "brush"; radius: number; points: [number, number][] } | { kind: "polygon"; points: [number, number][] },
  rgba: [number, number, number, number],
): Promise<Blob> {
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d")!;
  const image = context.createImageData(width, height);
  const set = (x: number, y: number) => {
    if (x < 0 || y < 0 || x >= width || y >= height) return;
    image.data.set(rgba, (y * width + x) * 4);
  };
  if (shape.kind === "brush") {
    const { radius, points } = shape;
    let previous = points[0];
    points.forEach((point, index) => {
      const steps = Math.max(Math.abs(point[0] - previous[0]), Math.abs(point[1] - previous[1]), 1);
      for (let step = index === 0 ? steps : 1; step <= steps; step++) {
        const x = Math.round(previous[0] + ((point[0] - previous[0]) * step) / steps);
        const y = Math.round(previous[1] + ((point[1] - previous[1]) * step) / steps);
        for (let dy = -radius; dy <= radius; dy++) {
          const half = Math.floor(Math.sqrt(radius * radius - dy * dy));
          for (let dx = -half; dx <= half; dx++) set(x + dx, y + dy);
        }
      }
      previous = point;
    });
  } else {
    const { points } = shape;
    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        let inside = false;
        for (let a = 0, b = points.length - 1; a < points.length; b = a++) {
          const [ax, ay] = points[a];
          const [bx, by] = points[b];
          if ((ay > y) !== (by > y) && x < ((bx - ax) * (y - ay)) / (by - ay) + ax) inside = !inside;
        }
        if (inside) set(x, y);
      }
    }
    for (const [x, y] of points) set(x, y); // the corners themselves
  }
  context.putImageData(image, 0, 0);
  return new Promise((resolve, reject) => canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("no PNG"))), "image/png"));
}
