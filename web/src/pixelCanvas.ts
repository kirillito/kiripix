// The canvas widget (ADR 0008): a plain class that owns its pixels and gestures, so a hover or a drag never goes through
// React state. Integer zoom only, nearest-neighbour only (spec §11). `Z` zooms, `Space` and the middle button pan.

const MAX_ZOOM = 16;
const BEFORE_COLOUR = "#f2c14e";

function isTyping(target: EventTarget | null): boolean {
  return target instanceof HTMLElement && /^(INPUT|SELECT|TEXTAREA)$/.test(target.tagName);
}

function isButton(target: EventTarget | null): boolean {
  return target instanceof HTMLElement && target.tagName === "BUTTON";
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
  private gesture: "pan" | "split" | null = null;
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
  }

  private setZoom(zoom: number): void {
    this.zoom = Math.min(MAX_ZOOM, Math.max(1, Math.trunc(zoom)));
    this.element.dataset.zoom = String(this.zoom);
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
    context.drawImage(this.after, left, top, width, height);
    if (this.before) {
      const edge = Math.round(width * this.split);
      context.save();
      context.beginPath();
      context.rect(left, top, edge, height);
      context.clip();
      context.clearRect(left, top, edge, height);
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
  }

  private nearSplit(event: PointerEvent): boolean {
    if (!this.before || !this.after) return false;
    const [left] = this.origin();
    return Math.abs(event.offsetX - (left + this.after.naturalWidth * this.zoom * this.split)) <= 6;
  }

  private readonly onPointerDown = (event: PointerEvent): void => {
    if (event.button === 1 || this.spaceHeld) {
      this.gesture = "pan";
    } else if (this.nearSplit(event)) {
      this.gesture = "split";
    } else {
      return;
    }
    this.element.setPointerCapture(event.pointerId);
    event.preventDefault();
  };

  private readonly onPointerMove = (event: PointerEvent): void => {
    if (this.gesture === "pan") {
      this.panX += event.movementX;
      this.panY += event.movementY;
      this.draw();
    } else if (this.gesture === "split" && this.after) {
      const [left] = this.origin();
      this.split = Math.min(1, Math.max(0, (event.offsetX - left) / (this.after.naturalWidth * this.zoom)));
      this.draw();
    } else {
      this.element.style.cursor = this.spaceHeld ? "grab" : this.nearSplit(event) ? "ew-resize" : "default";
    }
  };

  private readonly onPointerUp = (event: PointerEvent): void => {
    if (this.gesture) this.element.releasePointerCapture(event.pointerId);
    this.gesture = null;
  };

  private readonly onWheel = (event: WheelEvent): void => {
    event.preventDefault();
    this.setZoom(this.zoom + (event.deltaY < 0 ? 1 : -1));
    this.draw();
  };

  private readonly onKeyDown = (event: KeyboardEvent): void => {
    if (isTyping(event.target) || event.ctrlKey || event.metaKey || event.altKey) return;
    if (event.code === "Space") {
      if (isButton(event.target)) return; // Space presses a focused button.
      this.spaceHeld = true;
      event.preventDefault();
    } else if (event.code === "KeyZ") {
      const next = this.zoom + (event.shiftKey ? -1 : 1);
      this.setZoom(next > MAX_ZOOM ? 1 : next);
      this.draw();
    }
  };

  private readonly onKeyUp = (event: KeyboardEvent): void => {
    if (event.code === "Space") this.spaceHeld = false;
  };
}
