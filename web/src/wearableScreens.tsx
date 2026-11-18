// A body's Wearables (ticket 0295, spec §6.3, §11): what the status board shows under a body, and the stack preview on the body's
// `sheet` screen. The preview draws the body and the Wearables the Owner chose at 4x, for a Clip and a Direction, stacked by `order`
// or by depth. It reads only the Stages' output files (`sheet.json`, `render.json`, the atlases and the depth frames) through the
// file route and `show`; it holds no logic of the Project's and sends no Command. The stacking is display math, the same rule as
// `kiripix/ops/stack.py`: the lowest order first, each over the last where it has alpha; or the nearest depth, a tie to the later.

import { useEffect, useRef, useState } from "react";
import { call, fileUrl, type Finding, type ShowData, type StageDetail, type StatusData } from "./api";
import { outputOf } from "./characterScreens";

export const WEARABLE_KIND = "wearable";
export const STACK_CODE = "wearable.stack_differs";
const ZOOM = 4;
const FAR = 65535; // a depth where a cell has no pixel (spec §6.3)
const DEFAULT_ORDER = 10;

interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

interface SheetFrame {
  index: number;
  rect: Rect;
}

export interface SheetDocument {
  files: { color: string; normal?: string; depth?: string };
  cell: { width: number; height: number };
  pivot: { x: number; y: number };
  atlas: { width: number; height: number };
  directions: string[];
  order?: number;
  clips: { name: string; fps: number; directions: Record<string, SheetFrame[]> }[];
}

interface RenderDocument {
  frame?: { width: number; height: number };
  pivot?: [number, number];
  seconds?: { measure?: number; render?: number; frames?: number; per_frame?: number };
  clips?: {
    name: string;
    directions: Record<string, { index: number; files: { depth?: string }; pivot?: [number, number] }[]>;
  }[];
}

// A Wearable as the board and the preview need it, read from `show` and its output files.
export interface WearableInfo {
  id: string;
  body: string | null;
  order: number;
  seconds: number | null; // Blender's wall seconds of its `render`
  atlas: { width: number; height: number } | null; // its `sheet`'s atlas, in px
  sheetFolder: string | null;
  sheet: SheetDocument | null;
}

async function readJson<T>(path: string | null): Promise<T | null> {
  if (!path) return null;
  try {
    const response = await fetch(fileUrl(path, 0), { cache: "no-store" });
    return response.ok ? ((await response.json()) as T) : null;
  } catch {
    return null;
  }
}

function folderOf(path: string): string {
  return path.slice(0, path.lastIndexOf("/"));
}

function stageOf(show: ShowData, name: string): StageDetail | undefined {
  return show.stages.find((entry) => entry.stage === name);
}

// Each Wearable of the Project: its body, its `order`, and its cost. One `show` and two small files each, read again on every refresh.
export function useWearables(status: StatusData | null, refreshes: number): Record<string, WearableInfo> {
  const [found, setFound] = useState<Record<string, WearableInfo>>({});
  const ids = (status?.assets ?? []).filter((asset) => asset.kind === WEARABLE_KIND).map((asset) => asset.asset);
  const key = ids.join("\n");
  useEffect(() => {
    let live = true;
    void (async () => {
      const read = await Promise.all(
        (key ? key.split("\n") : []).map(async (id): Promise<WearableInfo | null> => {
          try {
            const shown = await call<ShowData>("show", { asset: id });
            if (!shown.data) return null;
            const sheetDetail = stageOf(shown.data, "sheet");
            const sheetPath = outputOf(sheetDetail, "sheet.json");
            const [sheet, render] = await Promise.all([
              readJson<SheetDocument>(sheetPath),
              readJson<RenderDocument>(outputOf(stageOf(shown.data, "render"), "render.json")),
            ]);
            const asked = Number(sheetDetail?.params.order);
            return {
              id,
              body: typeof shown.data.params.body === "string" ? shown.data.params.body : null,
              order: Number.isFinite(asked) && sheetDetail?.params.order !== undefined ? asked : (sheet?.order ?? DEFAULT_ORDER),
              seconds: typeof render?.seconds?.render === "number" ? render.seconds.render : null,
              atlas: sheet?.atlas ?? null,
              sheetFolder: sheetPath ? folderOf(sheetPath) : null,
              sheet,
            };
          } catch {
            return null;
          }
        }),
      );
      if (live) setFound(Object.fromEntries(read.filter((one): one is WearableInfo => one !== null).map((one) => [one.id, one])));
    })();
    return () => {
      live = false;
    };
  }, [key, refreshes]);
  return found;
}

export function costText(info: WearableInfo | undefined): string {
  if (!info) return "";
  const parts = [];
  if (info.seconds !== null) parts.push(`render ${info.seconds.toFixed(1)} s`);
  if (info.atlas) parts.push(`atlas ${info.atlas.width} x ${info.atlas.height} px`);
  return parts.join(" · ");
}

// A gray PNG of 8 or 16 bits, which is what a depth pass is (`<canvas>` would cut a 16 bit value to 8). Values in 0 to 65535.
interface Gray {
  width: number;
  height: number;
  data: Uint16Array;
}

async function inflate(bytes: Uint8Array): Promise<Uint8Array> {
  const stream = new Blob([bytes as BlobPart]).stream().pipeThrough(new DecompressionStream("deflate"));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

export async function decodeGray(buffer: ArrayBuffer): Promise<Gray | null> {
  const bytes = new Uint8Array(buffer);
  const view = new DataView(buffer);
  let at = 8;
  let width = 0;
  let height = 0;
  let depth = 0;
  let type = -1;
  let interlace = 0;
  const parts: Uint8Array[] = [];
  while (at + 8 <= bytes.length) {
    const length = view.getUint32(at);
    const name = String.fromCharCode(...bytes.subarray(at + 4, at + 8));
    const body = bytes.subarray(at + 8, at + 8 + length);
    if (name === "IHDR") {
      width = view.getUint32(at + 8);
      height = view.getUint32(at + 12);
      depth = bytes[at + 16];
      type = bytes[at + 17];
      interlace = bytes[at + 20];
    } else if (name === "IDAT") parts.push(body);
    else if (name === "IEND") break;
    at += 12 + length;
  }
  if (type !== 0 || (depth !== 8 && depth !== 16) || interlace !== 0 || width === 0) return null;
  const joined = new Uint8Array(parts.reduce((sum, part) => sum + part.length, 0));
  let place = 0;
  for (const part of parts) {
    joined.set(part, place);
    place += part.length;
  }
  const raw = await inflate(joined);
  const step = depth / 8;
  const stride = width * step;
  const lines = new Uint8Array(stride * height);
  for (let y = 0; y < height; y++) {
    const filter = raw[y * (stride + 1)];
    const from = y * (stride + 1) + 1;
    for (let x = 0; x < stride; x++) {
      const left = x >= step ? lines[y * stride + x - step] : 0;
      const up = y > 0 ? lines[(y - 1) * stride + x] : 0;
      const corner = x >= step && y > 0 ? lines[(y - 1) * stride + x - step] : 0;
      let value = raw[from + x];
      if (filter === 1) value += left;
      else if (filter === 2) value += up;
      else if (filter === 3) value += (left + up) >> 1;
      else if (filter === 4) {
        const guess = left + up - corner;
        const near = [Math.abs(guess - left), Math.abs(guess - up), Math.abs(guess - corner)];
        value += near[0] <= near[1] && near[0] <= near[2] ? left : near[1] <= near[2] ? up : corner;
      }
      lines[y * stride + x] = value & 255;
    }
  }
  const data = new Uint16Array(width * height);
  for (let index = 0; index < data.length; index++) {
    data[index] = depth === 16 ? (lines[index * 2] << 8) | lines[index * 2 + 1] : lines[index];
  }
  return { width, height, data };
}

const pictures = new Map<string, Promise<ImageData | null>>();
const grays = new Map<string, Promise<Gray | null>>();

function picture(url: string): Promise<ImageData | null> {
  let found = pictures.get(url);
  if (!found) {
    found = (async () => {
      try {
        const response = await fetch(url);
        if (!response.ok) return null;
        const bitmap = await createImageBitmap(await response.blob(), { premultiplyAlpha: "none", colorSpaceConversion: "none" });
        const canvas = new OffscreenCanvas(bitmap.width, bitmap.height);
        const context = canvas.getContext("2d", { willReadFrequently: true });
        if (!context) return null;
        context.drawImage(bitmap, 0, 0);
        return context.getImageData(0, 0, bitmap.width, bitmap.height);
      } catch {
        return null;
      }
    })();
    pictures.set(url, found);
  }
  return found;
}

function gray(url: string): Promise<Gray | null> {
  let found = grays.get(url);
  if (!found) {
    found = (async () => {
      try {
        const response = await fetch(url);
        return response.ok ? await decodeGray(await response.arrayBuffer()) : null;
      } catch {
        return null;
      }
    })();
    grays.set(url, found);
  }
  return found;
}

// One image in the stack (the body or a Wearable), ready for one frame: colour of the cell's size, and a depth for each pixel of it.
interface Stacked {
  id: string;
  order: number;
  colour: Uint8ClampedArray;
  depth: Uint16Array;
}

// The cell's pixels from an atlas' rect.
function cut(atlas: ImageData, rect: Rect, cell: { width: number; height: number }): Uint8ClampedArray {
  const out = new Uint8ClampedArray(cell.width * cell.height * 4);
  for (let y = 0; y < Math.min(rect.height, cell.height); y++) {
    for (let x = 0; x < Math.min(rect.width, cell.width); x++) {
      const from = ((rect.y + y) * atlas.width + rect.x + x) * 4;
      out.set(atlas.data.subarray(from, from + 4), (y * cell.width + x) * 4);
    }
  }
  return out;
}

function cutDepth(atlas: Gray, rect: Rect, cell: { width: number; height: number }): Uint16Array {
  const out = new Uint16Array(cell.width * cell.height).fill(FAR);
  for (let y = 0; y < Math.min(rect.height, cell.height); y++) {
    for (let x = 0; x < Math.min(rect.width, cell.width); x++) {
      out[y * cell.width + x] = atlas.data[(rect.y + y) * atlas.width + rect.x + x];
    }
  }
  return out;
}

export function stack(stacked: Stacked[], cell: { width: number; height: number }, byDepth: boolean): Uint8ClampedArray<ArrayBuffer> {
  const out = new Uint8ClampedArray(new ArrayBuffer(cell.width * cell.height * 4));
  const sorted = [...stacked].sort((a, b) => a.order - b.order || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
  for (let pixel = 0; pixel < cell.width * cell.height; pixel++) {
    let best = -1;
    for (let index = 0; index < sorted.length; index++) {
      if (sorted[index].colour[pixel * 4 + 3] === 0) continue;
      if (!byDepth || best < 0 || sorted[index].depth[pixel] <= sorted[best].depth[pixel]) best = index; // a tie: the later
    }
    if (best >= 0) out.set(sorted[best].colour.subarray(pixel * 4, pixel * 4 + 4), pixel * 4);
  }
  return out;
}

interface Box {
  x: number;
  y: number;
  width: number;
  height: number;
}

function boxOf(finding: Finding): (Box & { clip: string; direction: string; index: number }) | null {
  const place = finding.position;
  const field = /^([a-z0-9_]+)\/([a-z]+)\/(\d+)$/.exec(place?.field ?? "");
  if (!place || !field || place.x == null || place.y == null || place.width == null || place.height == null) return null;
  return { clip: field[1], direction: field[2], index: Number(field[3]), x: place.x, y: place.y, width: place.width, height: place.height };
}

// The body's depth for a cell: the render's depth frame, put in the cell as `sheet` puts the colour one (the frame's pivot, rounded,
// on the cell's pivot).
async function bodyDepth(
  render: RenderDocument | null,
  folder: string,
  clip: string,
  direction: string,
  index: number,
  sheet: SheetDocument,
): Promise<Uint16Array | null> {
  const frame = render?.clips?.find((entry) => entry.name === clip)?.directions[direction]?.find((entry) => entry.index === index);
  if (!frame?.files.depth) return null;
  const depth = await gray(fileUrl(`${folder}/${frame.files.depth}`, 0));
  if (!depth) return null;
  const pivot = frame.pivot ?? render?.pivot ?? [sheet.pivot.x, sheet.pivot.y];
  const dx = sheet.pivot.x - Math.floor(pivot[0] + 0.5);
  const dy = sheet.pivot.y - Math.floor(pivot[1] + 0.5);
  const out = new Uint16Array(sheet.cell.width * sheet.cell.height).fill(FAR);
  for (let y = 0; y < sheet.cell.height; y++) {
    for (let x = 0; x < sheet.cell.width; x++) {
      const sx = x - dx;
      const sy = y - dy;
      if (sx >= 0 && sy >= 0 && sx < depth.width && sy < depth.height) out[y * sheet.cell.width + x] = depth.data[sy * depth.width + sx];
    }
  }
  return out;
}

type Stacking = "order" | "depth";

export function StackPreview(props: {
  show: ShowData; // the body
  wearables: WearableInfo[];
  findings: Finding[];
  refreshes: number;
  imageVersion: number;
}) {
  const { show, wearables, findings, imageVersion } = props;
  const sheetDetail = stageOf(show, "sheet");
  const renderDetail = stageOf(show, "render");
  const sheetPath = outputOf(sheetDetail, "sheet.json");
  const renderPath = outputOf(renderDetail, "render.json");
  const [sheet, setSheet] = useState<SheetDocument | null>(null);
  const [render, setRender] = useState<RenderDocument | null>(null);
  useEffect(() => {
    let live = true;
    void readJson<SheetDocument>(sheetPath).then((value) => live && setSheet(value));
    void readJson<RenderDocument>(renderPath).then((value) => live && setRender(value));
    return () => {
      live = false;
    };
  }, [sheetPath, renderPath, props.refreshes]);

  const [off, setOff] = useState<string[]>([]); // the Wearables not worn
  const [stacking, setStacking] = useState<Stacking>("order");
  const [clipName, setClipName] = useState<string | null>(null);
  const [direction, setDirection] = useState<string | null>(null);
  const [position, setPosition] = useState(0);
  const [playing, setPlaying] = useState(false);
  const canvas = useRef<HTMLCanvasElement>(null);

  const clip = sheet?.clips.find((entry) => entry.name === clipName) ?? sheet?.clips[0];
  const shownDirection = direction && clip?.directions[direction] ? direction : (clip ? Object.keys(clip.directions)[0] : undefined);
  const frames = clip && shownDirection ? clip.directions[shownDirection] : [];
  const frame = frames.length ? frames[((position % frames.length) + frames.length) % frames.length] : undefined;
  const worn = wearables.filter((one) => !off.includes(one.id) && one.sheet && one.sheetFolder);

  useEffect(() => {
    if (!playing || !clip || frames.length < 2) return;
    const timer = window.setInterval(() => setPosition((at) => at + 1), 1000 / (clip.fps || 10));
    return () => window.clearInterval(timer);
  }, [playing, clip, frames.length]);

  const wornKey = worn.map((one) => `${one.id}:${one.order}`).join(",");
  useEffect(() => {
    const target = canvas.current;
    if (!target || !sheet || !sheetPath || !clip || !shownDirection || !frame) return;
    let live = true;
    void (async () => {
      const base = folderOf(sheetPath);
      const stacked: Stacked[] = [];
      const colour = await picture(fileUrl(`${base}/${sheet.files.color}`, imageVersion));
      if (colour) {
        const depth = await bodyDepth(render, folderOf(renderPath ?? sheetPath), clip.name, shownDirection, frame.index, sheet);
        stacked.push({ id: "", order: 0, colour: cut(colour, frame.rect, sheet.cell), depth: depth ?? new Uint16Array(sheet.cell.width * sheet.cell.height) });
      }
      for (const one of worn) {
        const mine = one.sheet!;
        const place = mine.clips.find((entry) => entry.name === clip.name)?.directions[shownDirection]?.find((entry) => entry.index === frame.index);
        if (!place || !mine.files.depth) continue;
        const [atlas, depth] = await Promise.all([
          picture(fileUrl(`${one.sheetFolder}/${mine.files.color}`, imageVersion)),
          gray(fileUrl(`${one.sheetFolder}/${mine.files.depth}`, imageVersion)),
        ]);
        if (atlas && depth) stacked.push({ id: one.id, order: one.order, colour: cut(atlas, place.rect, sheet.cell), depth: cutDepth(depth, place.rect, sheet.cell) });
      }
      if (!live) return;
      const context = target.getContext("2d");
      if (!context) return;
      context.imageSmoothingEnabled = false;
      context.putImageData(new ImageData(stack(stacked, sheet.cell, stacking === "depth"), sheet.cell.width, sheet.cell.height), 0, 0);
      target.dataset.stacked = String(stacked.length);
    })();
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sheet, render, sheetPath, renderPath, clip?.name, shownDirection, frame?.index, stacking, wornKey, imageVersion]);

  const stackFindings = findings.filter((finding) => finding.code === STACK_CODE);
  const boxes = stackFindings.map(boxOf).filter((box): box is NonNullable<ReturnType<typeof boxOf>> => box !== null);
  const here = boxes.filter((box) => box.clip === clip?.name && box.direction === shownDirection && box.index === frame?.index);

  return (
    <section className="stack-preview" data-testid="stack-preview" aria-label="Stack preview">
      <h2>Stack preview</h2>
      {!sheet ? (
        <p className="hint" data-testid="stack-empty">The sheet isn't built yet: run it to see the body with its Wearables.</p>
      ) : (
        <>
          <div className="stack-controls">
            <div role="group" aria-label="Stacking" className="tool-row">
              <button data-testid="stack-order" aria-pressed={stacking === "order"} onClick={() => setStacking("order")}>
                By order
              </button>
              <button data-testid="stack-depth" aria-pressed={stacking === "depth"} onClick={() => setStacking("depth")}>
                By depth
              </button>
            </div>
            <label>
              Clip{" "}
              <select data-testid="stack-clip" value={clip?.name ?? ""} onChange={(event) => { setClipName(event.target.value); setPosition(0); }}>
                {sheet.clips.map((entry) => (
                  <option key={entry.name} value={entry.name}>{entry.name}</option>
                ))}
              </select>
            </label>
            <label>
              Direction{" "}
              <select data-testid="stack-direction" value={shownDirection ?? ""} onChange={(event) => setDirection(event.target.value)}>
                {Object.keys(clip?.directions ?? {}).map((name) => (
                  <option key={name} value={name}>{name}</option>
                ))}
              </select>
            </label>
            <button data-testid="stack-play" aria-pressed={playing} onClick={() => setPlaying(!playing)}>
              {playing ? "Pause" : "Play"}
            </button>
            <span data-testid="stack-frame">frame {frame?.index ?? "-"} of {frames.length}</span>
          </div>
          <ul className="stack-worn" data-testid="stack-worn">
            <li>
              <span>{show.asset}</span> <span className="hint">order 0</span>
            </li>
            {wearables.map((one) => (
              <li key={one.id} data-testid={`stack-wearable-${one.id}`}>
                <label>
                  <input
                    type="checkbox"
                    data-testid={`stack-wear-${one.id}`}
                    checked={!off.includes(one.id)}
                    disabled={!one.sheet}
                    onChange={(event) => setOff(event.target.checked ? off.filter((id) => id !== one.id) : [...off, one.id])}
                  />{" "}
                  {one.id}
                </label>{" "}
                <span className="hint">order {one.order}</span>
                {costText(one) && <span className="hint" data-testid={`stack-cost-${one.id}`}> · {costText(one)}</span>}
                {!one.sheet && <span className="hint"> · its sheet isn't built</span>}
              </li>
            ))}
          </ul>
          <span className="frame-box" style={{ width: sheet.cell.width * ZOOM, height: sheet.cell.height * ZOOM }}>
            <canvas
              ref={canvas}
              data-testid="stack-canvas"
              data-stack={stacking}
              data-zoom={ZOOM}
              width={sheet.cell.width}
              height={sheet.cell.height}
              style={{ width: sheet.cell.width * ZOOM, height: sheet.cell.height * ZOOM, imageRendering: "pixelated" }}
            />
            {here.map((box, number) => (
              <i
                key={number}
                className="stack-box"
                data-testid="stack-box"
                data-box={`${box.x},${box.y},${box.width},${box.height}`}
                title="Pixels where stacking by order and by depth differ"
                style={{ left: box.x * ZOOM, top: box.y * ZOOM, width: box.width * ZOOM, height: box.height * ZOOM }}
              />
            ))}
          </span>
          {stackFindings.length > 0 && (
            <ul className="stack-findings" data-testid="stack-findings">
              {stackFindings.map((finding) => {
                const box = boxOf(finding);
                return (
                  <li key={finding.message}>
                    {finding.message}{" "}
                    {box && (
                      <button
                        data-testid="stack-jump"
                        onClick={() => {
                          setClipName(box.clip);
                          setDirection(box.direction);
                          const at = sheet.clips.find((entry) => entry.name === box.clip)?.directions[box.direction]?.findIndex((entry) => entry.index === box.index);
                          setPosition(at && at > 0 ? at : 0);
                          setPlaying(false);
                        }}
                      >
                        Show the worst frame
                      </button>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </>
      )}
    </section>
  );
}
