// What a portrait's screens add to the canvas (ticket 0245): the selected emotion laid over the neutral at the canvas's size, so
// toggling it shows anything that moves, and `portrait.shimmer`'s boxes. Plain class: nothing here goes through React state.

import type { CanvasFrame, CanvasTool } from "./pixelCanvas";

export interface ShimmerBox {
  x: number;
  y: number;
  width: number;
  height: number;
  pixels?: number;
}

const BOX_COLOUR = "#ff3b6b";

export class FlipTool implements CanvasTool {
  emotion = ""; // the emotion that is laid over; "" when none is selected
  image: HTMLImageElement | null = null; // its image on this Stage
  flipped = false; // the emotion is shown over the neutral
  boxes: ShimmerBox[] = [];

  draw(context: CanvasRenderingContext2D, frame: CanvasFrame): void {
    context.save();
    context.imageSmoothingEnabled = false;
    if (this.flipped && this.image) {
      context.drawImage(this.image, frame.left, frame.top, this.image.naturalWidth * frame.zoom, this.image.naturalHeight * frame.zoom);
    }
    context.lineWidth = 2;
    context.setLineDash([6, 3]);
    context.strokeStyle = BOX_COLOUR;
    for (const box of this.boxes) {
      context.strokeRect(frame.left + box.x * frame.zoom, frame.top + box.y * frame.zoom, box.width * frame.zoom, box.height * frame.zoom);
    }
    context.restore();
    const data = frame.element.dataset;
    data.flip = this.flipped && this.image ? this.emotion : "";
    data.shimmer = this.boxes.map((box) => `${box.x},${box.y},${box.width},${box.height}`).join(" ");
  }
}
