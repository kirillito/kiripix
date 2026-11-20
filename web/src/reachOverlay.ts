// The reach screen's view of what `reach` built (spec §6.1, ADR 0013): the reachable Mask of the room, or of a chosen Look,
// tinted over the room, and the islands from report.json boxed. It draws what the files say and works nothing out.

import type { CanvasFrame, CanvasTool } from "./pixelCanvas";
import type { MaskPixels } from "./walkTest";

export interface IslandBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

const REACHED = [0, 200, 120, 90];
const ISLAND = "#ffb000";

export class ReachOverlay implements CanvasTool {
  private picture: HTMLCanvasElement | null = null;
  private spots = 0;
  private islands: IslandBox[] = [];
  private look = "";

  set(mask: MaskPixels | null, islands: IslandBox[], look: string): void {
    this.look = look;
    this.islands = islands;
    this.spots = 0;
    this.picture = null;
    if (!mask) return;
    const picture = document.createElement("canvas");
    picture.width = mask.width;
    picture.height = mask.height;
    const context = picture.getContext("2d")!;
    const pixels = context.createImageData(mask.width, mask.height);
    for (let index = 0; index < mask.set.length; index++) {
      if (!mask.set[index]) continue;
      pixels.data.set(REACHED, index * 4);
      this.spots++;
    }
    context.putImageData(pixels, 0, 0);
    this.picture = picture;
  }

  draw(context: CanvasRenderingContext2D, frame: CanvasFrame): void {
    if (this.picture) {
      context.imageSmoothingEnabled = false;
      context.drawImage(this.picture, frame.left, frame.top, frame.width * frame.zoom, frame.height * frame.zoom);
    }
    context.strokeStyle = ISLAND;
    for (const island of this.islands) {
      context.strokeRect(
        frame.left + island.x * frame.zoom - 0.5,
        frame.top + island.y * frame.zoom - 0.5,
        island.width * frame.zoom + 1,
        island.height * frame.zoom + 1,
      );
    }
    frame.element.dataset.reachLook = this.look;
    frame.element.dataset.reachSpots = String(this.spots);
    frame.element.dataset.reachIslands = this.islands.map((island) => `${island.x},${island.y},${island.width},${island.height}`).join(" ");
  }
}
