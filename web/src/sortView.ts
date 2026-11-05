// The Layers of a room on the place screen and in the walk test (spec §6.1, §11, ticket 0054). Which Layers there are, and where
// each sorts, is what the Commands say: the Layer files of `palette` (or of `layers`, before it is built), and `show`'s `sort`
// of `place`. Nothing here works a sort position out.

import type { ShowData } from "./api";
import type { CanvasFrame, CanvasTool } from "./pixelCanvas";

const LAYER_FILE = /^layer\.(.+)\.png$/;

// The Layer ID a path names, by the file name the Stages give each Layer (`layer.<id>.png`), or undefined.
export function layerIdOf(path: string): string | undefined {
  return LAYER_FILE.exec(path.slice(path.lastIndexOf("/") + 1))?.[1];
}

// Each Layer's PNG, by ID: the mapped one from `palette` where it is built, else the cut one from `layers`.
export function layerFiles(show: ShowData): Map<string, string> {
  const files = new Map<string, string>();
  for (const name of ["layers", "palette"]) {
    for (const path of show.stages.find((entry) => entry.stage === name)?.outputs ?? []) {
      const id = layerIdOf(path);
      if (id !== undefined) files.set(id, path);
    }
  }
  return new Map([...files].sort(([one], [other]) => (one < other ? -1 : 1)));
}

export async function loadImage(url: string): Promise<HTMLImageElement> {
  const image = new Image();
  image.src = url;
  await image.decode();
  return image;
}

// One Layer's pixels as a wash of colour, so it stands out over the Plate it is already part of.
function tinted(image: HTMLImageElement, colour: string): HTMLCanvasElement {
  const wash = document.createElement("canvas");
  wash.width = image.naturalWidth;
  wash.height = image.naturalHeight;
  const context = wash.getContext("2d")!;
  context.drawImage(image, 0, 0);
  context.globalCompositeOperation = "source-in";
  context.fillStyle = colour;
  context.fillRect(0, 0, wash.width, wash.height);
  return wash;
}

// The Layer a y-sort line is being drawn for, shown over the image.
export class LayerHighlight implements CanvasTool {
  private id: string | null = null;
  private wash: HTMLCanvasElement | null = null;

  show(id: string | null, image: HTMLImageElement | null): void {
    this.id = image ? id : null;
    this.wash = image ? tinted(image, "#ff9b6b") : null;
  }

  draw(context: CanvasRenderingContext2D, frame: CanvasFrame): void {
    if (this.wash) {
      context.imageSmoothingEnabled = false;
      context.globalAlpha = 0.5;
      context.drawImage(this.wash, frame.left, frame.top, frame.width * frame.zoom, frame.height * frame.zoom);
      context.globalAlpha = 1;
    }
    frame.element.dataset.layerShown = this.id ?? "";
  }
}
