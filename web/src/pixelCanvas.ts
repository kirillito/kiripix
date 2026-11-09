// The canvas widget (ADR 0008): a plain class that owns its pixels and gestures, so a hover or a drag never goes through
// React state. Integer zoom only, nearest-neighbour only (spec §11). `Z` and the wheel zoom, a drag, `Space`, the middle button, the
// arrow keys and the scrollbars pan, and `Home` returns to the fit view.

const MAX_ZOOM = 16;
const BEFORE_COLOUR = "#f2c14e";
const BAR = 8; // a scrollbar's thickness, in canvas pixels
const MIN_THUMB = 24;
const KEEP = 96; // at most this much of the image always stays on the canvas, in canvas pixels
const STEP = 32; // an arrow key pans by this much, in canvas pixels; Shift pans by four times as much
const BAR_COLOUR = "rgba(200, 200, 210, 0.55)";

// One scrollbar: its track and thumb along its axis, in canvas pixels.
interface Bar {
  track: number;
  start: number;
  length: number;
}

// A focused field takes the keys typed into it. A checkbox or a slider takes no letters, so the shortcuts still work there.
export function isTyping(target: EventTarget | null): boolean {
  if (target instanceof HTMLInputElement) return !["checkbox", "range"].includes(target.type);
  return target instanceof HTMLElement && /^(SELECT|TEXTAREA)$/.test(target.tagName);
}

const ARROWS: Record<string, [number, number]> = {
  ArrowLeft: [-1, 0],
  ArrowRight: [1, 0],
  ArrowUp: [0, -1],
  ArrowDown: [0, 1],
};

function takesSpace(target: EventTarget | null): boolean {
  if (target instanceof HTMLInputElement) return target.type === "checkbox";
  return target instanceof HTMLElement && target.tagName === "BUTTON";
}

export interface CanvasPixel {
  x: number;
  y: number;
}

// Where the image is on the canvas, in canvas pixels, and its size in its own.
export interface CanvasFrame {
  left: number;
  top: number;
  zoom: number;
  width: number;
  height: number;
  element: HTMLCanvasElement;
}

// What a Stage's screen adds to the canvas: it draws over the image, and takes a gesture on it that isn't a pan.
export interface CanvasTool {
  draw(context: CanvasRenderingContext2D, frame: CanvasFrame): void;
  pointerDown?(pixel: CanvasPixel, frame: CanvasFrame): boolean; // true: this tool takes the gesture
  pointerMove?(pixel: CanvasPixel): void;
  pointerUp?(pixel: CanvasPixel): void;
  hover?(pixel: CanvasPixel | null): void; // the pixel under the pointer between gestures; null when it leaves the image
  ownsArrowKeys?: boolean; // the arrow keys are this tool's, so they don't pan
}

// A checkerboard under the image, so transparent pixels read as transparent: screen-sized squares, not image pixels.
const CHECK = 8;
function drawChecker(context: CanvasRenderingContext2D, left: number, top: number, width: number, height: number): void {
  context.save();
  context.beginPath();
  context.rect(left, top, width, height);
  context.clip();
  context.fillStyle = "#3a3a3a";
  context.fillRect(left, top, width, height);
  context.fillStyle = "#4a4a4a";
  for (let y = 0; y * CHECK < height; y++) {
    for (let x = y % 2; x * CHECK < width; x += 2) context.fillRect(left + x * CHECK, top + y * CHECK, CHECK, CHECK);
  }
  context.restore();
}

function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error(`can't load ${url}`));
    image.src = url;
  });
}

export class PixelCanvas {
  readonly element = document.createElement("canvas");
  private after: HTMLImageElement | null = null;
  private before: HTMLImageElement | null = null;
  private request = 0;
  private zoom = 1;
  private fitted = false;
  private panX = 0;
  private panY = 0;
  private split = 0.5;
  private spaceHeld = false;
  private gesture: "pan" | "split" | "tool" | "bar-x" | "bar-y" | null = null;
  private grab = 0; // where on its thumb a scrollbar drag holds it
  private tools: CanvasTool[] = [];
  private active: CanvasTool | null = null;
  private gameFrame: [number, number] | null = null;
  private focused: { x: number; y: number } | null = null;
  private centrePending = false;
  private readonly observer: ResizeObserver;

  constructor(private readonly host: HTMLElement) {
    this.element.dataset.testid = "canvas";
    host.append(this.element);
    this.observer = new ResizeObserver(() => this.resize());
    this.observer.observe(host);
    this.element.addEventListener("pointerdown", this.onPointerDown);
    this.element.addEventListener("pointermove", this.onPointerMove);
    this.element.addEventListener("pointerup", this.onPointerUp);
    this.element.addEventListener("pointerleave", this.onPointerLeave);
    this.element.addEventListener("wheel", this.onWheel, { passive: false });
    window.addEventListener("keydown", this.onKeyDown);
    window.addEventListener("keyup", this.onKeyUp);
  }

  destroy(): void {
    this.observer.disconnect();
    window.removeEventListener("keydown", this.onKeyDown);
    window.removeEventListener("keyup", this.onKeyUp);
    this.element.remove();
  }

  // Shows `after`, with `before` on the left of a draggable split when given. The old pixels stay until the new load.
  async show(after: string | null, before: string | null): Promise<void> {
    const request = ++this.request;
    this.element.dataset.after = after ?? "";
    this.element.dataset.before = before ?? "";
    try {
      const [afterImage, beforeImage] = await Promise.all([
        after ? loadImage(after) : null,
        before ? loadImage(before) : null,
      ]);
      if (request !== this.request) return;
      this.after = afterImage;
      this.before = beforeImage;
    } catch {
      if (request !== this.request) return;
      this.after = this.before = null; // Removed while loading; the next refresh brings the new state.
    }
    if (!this.fitted) this.fit();
    if (this.centrePending && this.after) this.centre();
    this.element.dataset.loaded = this.after ? `${this.after.naturalWidth}x${this.after.naturalHeight}` : "";
    this.draw();
  }

  setTools(tools: CanvasTool[]): void {
    this.tools = tools;
    this.active = null;
    this.draw();
  }

  redraw(): void {
    this.draw();
  }

  private frame(): CanvasFrame | null {
    if (!this.after) return null;
    const [left, top] = this.origin();
    return {
      left,
      top,
      zoom: this.zoom,
      width: this.after.naturalWidth,
      height: this.after.naturalHeight,
      element: this.element,
    };
  }

  // The image pixel under the pointer, held inside the image.
  private pixelAt(event: PointerEvent, frame: CanvasFrame): CanvasPixel {
    return {
      x: Math.min(frame.width - 1, Math.max(0, Math.floor((event.offsetX - frame.left) / frame.zoom))),
      y: Math.min(frame.height - 1, Math.max(0, Math.floor((event.offsetY - frame.top) / frame.zoom))),
    };
  }

  // A new Asset starts at the largest zoom that fits.
  refit(): void {
    this.fitted = false;
    this.focused = null;
    this.centrePending = false;
    delete this.element.dataset.focus;
  }

  setGameFrame(resolution: [number, number] | null): void {
    this.gameFrame = resolution;
    if (resolution) {
      this.setZoom(1);
    } else {
      this.fit();
    }
    this.panX = this.panY = 0;
    this.draw();
  }

  // Centres a finding's pixel and marks it.
  focus(x: number, y: number): void {
    this.focused = { x, y };
    this.element.dataset.focus = `${x},${y}`;
    if (this.fitted) this.centre();
    else this.centrePending = true; // On another Stage's image, still loading.
    this.draw();
  }

  private centre(): void {
    if (!this.focused) return;
    const [left, top] = this.origin();
    this.panX += this.element.width / 2 - (left + (this.focused.x + 0.5) * this.zoom);
    this.panY += this.element.height / 2 - (top + (this.focused.y + 0.5) * this.zoom);
    this.centrePending = false;
    this.clamp();
  }

  private setZoom(zoom: number): void {
    this.zoom = Math.min(MAX_ZOOM, Math.max(1, Math.trunc(zoom)));
    this.element.dataset.zoom = String(this.zoom);
  }

  // Zooms so the image pixel under (x, y), in canvas pixels, stays under it.
  private zoomAbout(zoom: number, x: number, y: number): void {
    if (!this.after) return this.setZoom(zoom);
    const [left, top] = this.origin();
    const u = (x - left) / this.zoom;
    const v = (y - top) / this.zoom;
    this.setZoom(zoom);
    this.panX = x - u * this.zoom - (this.element.width - this.after.naturalWidth * this.zoom) / 2;
    this.panY = y - v * this.zoom - (this.element.height - this.after.naturalHeight * this.zoom) / 2;
    this.clamp();
    this.draw();
  }

  // Part of the image always stays on the canvas.
  private clamp(): void {
    if (!this.after) return;
    const width = this.after.naturalWidth * this.zoom;
    const height = this.after.naturalHeight * this.zoom;
    const keep = Math.min(KEEP, this.element.width / 4, this.element.height / 4);
    const limit = (size: number, extent: number): number => Math.max(0, (extent + size) / 2 - Math.min(keep, size));
    const maxX = limit(width, this.element.width);
    const maxY = limit(height, this.element.height);
    this.panX = Math.min(maxX, Math.max(-maxX, this.panX));
    this.panY = Math.min(maxY, Math.max(-maxY, this.panY));
  }

  private panBy(dx: number, dy: number): void {
    this.panX += dx;
    this.panY += dy;
    this.clamp();
    this.draw();
  }

  // The scrollbars: only on an axis the image overflows.
  private bars(): { x: Bar | null; y: Bar | null } {
    if (!this.after) return { x: null, y: null };
    const [left, top] = this.origin();
    const width = this.after.naturalWidth * this.zoom;
    const height = this.after.naturalHeight * this.zoom;
    const overflowX = width > this.element.width;
    const overflowY = height > this.element.height;
    const make = (size: number, extent: number, origin: number, other: boolean): Bar => {
      const track = extent - (other ? BAR : 0);
      const length = Math.min(track, Math.max(MIN_THUMB, Math.round((track * extent) / size)));
      const start = Math.min(track - length, Math.max(0, Math.round((-origin / size) * track)));
      return { track, start, length };
    };
    return {
      x: overflowX ? make(width, this.element.width, left, overflowY) : null,
      y: overflowY ? make(height, this.element.height, top, overflowX) : null,
    };
  }

  // Which scrollbar is under the pointer, if any.
  private barAt(event: PointerEvent): "bar-x" | "bar-y" | null {
    const { x, y } = this.bars();
    if (y && event.offsetX >= this.element.width - BAR && event.offsetY < y.track) return "bar-y";
    if (x && event.offsetY >= this.element.height - BAR && event.offsetX < x.track) return "bar-x";
    return null;
  }

  // Moves the thumb to follow the pointer at `position` along its track, which scrolls the image.
  private dragBar(axis: "bar-x" | "bar-y", position: number): void {
    if (!this.after) return;
    const bar = this.bars()[axis === "bar-x" ? "x" : "y"];
    if (!bar) return;
    const start = Math.min(bar.track - bar.length, Math.max(0, position - this.grab));
    if (axis === "bar-x") {
      const width = this.after.naturalWidth * this.zoom;
      this.panX = -(start / bar.track) * width - (this.element.width - width) / 2;
    } else {
      const height = this.after.naturalHeight * this.zoom;
      this.panY = -(start / bar.track) * height - (this.element.height - height) / 2;
    }
    this.clamp();
    this.draw();
  }

  private fit(): void {
    if (!this.after) return;
    const fits = Math.min(this.element.width / this.after.naturalWidth, this.element.height / this.after.naturalHeight);
    this.setZoom(this.gameFrame ? 1 : Math.floor(fits));
    this.panX = this.panY = 0;
    this.fitted = true;
  }

  private resize(): void {
    const { clientWidth, clientHeight } = this.host;
    if (this.element.width === clientWidth && this.element.height === clientHeight) return;
    this.element.width = clientWidth;
    this.element.height = clientHeight;
    this.clamp();
    this.draw();
  }

  // The canvas position of the image's top-left pixel: whole pixels, so every zoomed pixel is the same size.
  private origin(): [number, number] {
    const width = (this.after?.naturalWidth ?? 0) * this.zoom;
    const height = (this.after?.naturalHeight ?? 0) * this.zoom;
    return [
      Math.round((this.element.width - width) / 2 + this.panX),
      Math.round((this.element.height - height) / 2 + this.panY),
    ];
  }

  private draw(): void {
    const context = this.element.getContext("2d");
    if (!context) return;
    context.clearRect(0, 0, this.element.width, this.element.height);
    context.imageSmoothingEnabled = false;
    if (!this.after) return;
    const [left, top] = this.origin();
    const width = this.after.naturalWidth * this.zoom;
    const height = this.after.naturalHeight * this.zoom;
    drawChecker(context, left, top, width, height);
    context.drawImage(this.after, left, top, width, height);
    if (this.before) {
      const edge = Math.round(width * this.split);
      context.save();
      context.beginPath();
      context.rect(left, top, edge, height);
      context.clip();
      context.clearRect(left, top, edge, height);
      drawChecker(context, left, top, edge, height);
      context.drawImage(this.before, left, top, width, height); // A Source is larger than its fit: same frame, same place.
      context.restore();
      context.fillStyle = BEFORE_COLOUR;
      context.fillRect(left + edge - 1, top, 2, height);
      context.font = "12px system-ui, sans-serif";
      context.fillText("before", left + edge - 44, top - 5);
      context.fillText("after", left + edge + 5, top - 5);
      this.element.dataset.split = this.split.toFixed(2);
    }
    if (this.gameFrame) {
      context.strokeStyle = BEFORE_COLOUR;
      context.strokeRect(left - 0.5, top - 0.5, this.gameFrame[0] * this.zoom + 1, this.gameFrame[1] * this.zoom + 1);
    }
    if (this.focused) {
      context.strokeStyle = "#ff3b6b";
      context.lineWidth = 2;
      context.strokeRect(
        left + this.focused.x * this.zoom - 3,
        top + this.focused.y * this.zoom - 3,
        this.zoom + 6,
        this.zoom + 6,
      );
      context.lineWidth = 1;
    }
    const frame = this.frame();
    if (frame) {
      this.element.dataset.origin = `${frame.left},${frame.top}`;
      for (const tool of this.tools) tool.draw(context, frame);
    }
    this.drawBars(context);
  }

  private drawBars(context: CanvasRenderingContext2D): void {
    const { x, y } = this.bars();
    context.fillStyle = BAR_COLOUR;
    if (x) context.fillRect(x.start, this.element.height - BAR, x.length, BAR);
    if (y) context.fillRect(this.element.width - BAR, y.start, BAR, y.length);
    for (const [name, bar] of [["scrollX", x], ["scrollY", y]] as const) {
      if (bar) this.element.dataset[name] = `${bar.start},${bar.length},${bar.track}`;
      else delete this.element.dataset[name];
    }
  }

  private nearSplit(event: PointerEvent): boolean {
    if (!this.before || !this.after) return false;
    const [left] = this.origin();
    return Math.abs(event.offsetX - (left + this.after.naturalWidth * this.zoom * this.split)) <= 6;
  }

  private readonly onPointerDown = (event: PointerEvent): void => {
    if (document.activeElement instanceof HTMLElement) document.activeElement.blur(); // a press here takes the keys back from a focused button
    const bar = event.button === 0 ? this.barAt(event) : null;
    if (bar) {
      this.gesture = bar;
      const found = this.bars()[bar === "bar-x" ? "x" : "y"]!;
      const at = bar === "bar-x" ? event.offsetX : event.offsetY;
      this.grab = at >= found.start && at < found.start + found.length ? at - found.start : found.length / 2;
      this.dragBar(bar, at);
    } else if (event.button === 1 || this.spaceHeld) {
      this.gesture = "pan";
    } else if (this.nearSplit(event)) {
      this.gesture = "split";
    } else {
      const frame = this.frame();
      const inside =
        frame &&
        event.offsetX >= frame.left &&
        event.offsetY >= frame.top &&
        event.offsetX < frame.left + frame.width * frame.zoom &&
        event.offsetY < frame.top + frame.height * frame.zoom;
      this.active = inside
        ? (this.tools.find((tool) => tool.pointerDown?.(this.pixelAt(event, frame), frame)) ?? null)
        : null;
      if (this.active) {
        this.gesture = "tool";
        this.draw();
      } else if (event.button === 0) {
        this.gesture = "pan"; // a drag that no tool takes pans
      } else {
        return;
      }
    }
    this.element.setPointerCapture(event.pointerId);
    event.preventDefault();
  };

  private readonly onPointerMove = (event: PointerEvent): void => {
    if (this.gesture === "tool") {
      const frame = this.frame();
      if (frame) this.active?.pointerMove?.(this.pixelAt(event, frame));
      this.draw();
    } else if (this.gesture === "pan") {
      this.panBy(event.movementX, event.movementY);
    } else if (this.gesture === "bar-x") {
      this.dragBar("bar-x", event.offsetX);
    } else if (this.gesture === "bar-y") {
      this.dragBar("bar-y", event.offsetY);
    } else if (this.gesture === "split" && this.after) {
      const [left] = this.origin();
      this.split = Math.min(1, Math.max(0, (event.offsetX - left) / (this.after.naturalWidth * this.zoom)));
      this.draw();
    } else {
      this.element.style.cursor = this.spaceHeld ? "grab" : this.nearSplit(event) ? "ew-resize" : "default";
      this.hoverAt(this.barAt(event) ? null : event);
    }
  };

  private hoverAt(event: PointerEvent | null): void {
    const frame = this.frame();
    const inside =
      event &&
      frame &&
      !this.spaceHeld &&
      event.offsetX >= frame.left &&
      event.offsetY >= frame.top &&
      event.offsetX < frame.left + frame.width * frame.zoom &&
      event.offsetY < frame.top + frame.height * frame.zoom;
    const pixel = inside ? this.pixelAt(event, frame) : null;
    for (const tool of this.tools) tool.hover?.(pixel);
    if (this.tools.some((tool) => tool.hover)) this.draw();
  }

  private readonly onPointerLeave = (): void => {
    if (!this.gesture) this.hoverAt(null);
  };

  private readonly onPointerUp = (event: PointerEvent): void => {
    if (this.gesture) this.element.releasePointerCapture(event.pointerId);
    if (this.gesture === "tool") {
      const frame = this.frame();
      if (frame) this.active?.pointerUp?.(this.pixelAt(event, frame));
      this.active = null;
      this.draw();
    }
    this.gesture = null;
  };

  private readonly onWheel = (event: WheelEvent): void => {
    event.preventDefault();
    this.zoomAbout(this.zoom + (event.deltaY < 0 ? 1 : -1), event.offsetX, event.offsetY);
  };

  private readonly onKeyDown = (event: KeyboardEvent): void => {
    if (isTyping(event.target) || event.ctrlKey || event.metaKey || event.altKey) return;
    if (event.code === "Space") {
      if (takesSpace(event.target)) return; // Space presses a focused button or checkbox.
      this.spaceHeld = true;
      event.preventDefault();
    } else if (event.code === "KeyZ") {
      const next = this.zoom + (event.shiftKey ? -1 : 1);
      this.zoomAbout(next > MAX_ZOOM ? 1 : next, this.element.width / 2, this.element.height / 2);
    } else if (event.code === "Home") {
      this.fit();
      this.draw();
    } else if (event.key in ARROWS && this.after) {
      if (event.target instanceof HTMLInputElement && event.target.type === "range") return; // a slider's arrows
      if (this.tools.some((tool) => tool.ownsArrowKeys)) return; // the walk test walks with them
      const [dx, dy] = ARROWS[event.key];
      const step = event.shiftKey ? STEP * 4 : STEP;
      this.panBy(-dx * step, -dy * step); // an arrow scrolls the view that way, so the image moves the other way
      event.preventDefault();
    }
  };

  private readonly onKeyUp = (event: KeyboardEvent): void => {
    if (event.code === "Space") this.spaceHeld = false;
  };
}
