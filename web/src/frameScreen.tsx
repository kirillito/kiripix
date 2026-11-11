// A character's picture Stages (spec §6.3, §11): `render`, `palette`, `finish` and `sheet`. One screen for all four: a frame
// strip for the chosen Clip and Direction, an onion skin, a compass for the Direction, a Clip player at the Clip's frame rate
// and a normal-map view. It only reads the Stage's output files (`render.json` or `sheet.json`, and the frames or the atlases)
// through the file route and draws them; it holds no logic and sends no Command. Hover and play change nothing in the Project.
//
// Pixel art is drawn with no smoothing, on canvases of the frame's own size that CSS scales by a whole number.

import { useEffect, useRef, useState } from "react";
import { fileUrl, type Finding, type ShowData, type StageDetail } from "./api";
import { isTyping } from "./pixelCanvas";
import { outputOf, useDocument } from "./characterScreens";

export const FRAME_STAGES = ["render", "palette", "finish", "sheet"];
const ZOOMS = [1, 2, 3, 4, 6, 8];
const COMPASS = [
  ["nw", "n", "ne"],
  ["w", null, "e"],
  ["sw", "s", "se"],
] as const;
// The number pad's keys lie out as the compass does: 8 is up (n), 2 is down (s, facing the camera).
const PAD: Record<string, string> = { "7": "nw", "8": "n", "9": "ne", "4": "w", "6": "e", "1": "sw", "2": "s", "3": "se" };
const PAD_KEY = Object.fromEntries(Object.entries(PAD).map(([key, direction]) => [direction, key]));

interface Source {
  path: string;
  rect?: { x: number; y: number; width: number; height: number };
}

interface Frame {
  index: number;
  color: Source;
  normal: Source | null;
  pivot: [number, number];
}

interface ClipView {
  name: string;
  fps: number;
  loop: boolean;
  stationary: boolean;
  directions: Record<string, Frame[]>;
}

interface FrameSet {
  width: number;
  height: number;
  directions: string[];
  clips: ClipView[];
}

interface RenderDocument {
  frame: { width: number; height: number };
  pivot: [number, number];
  directions: string[];
  clips: {
    name: string;
    fps: number;
    loop: boolean;
    stationary: boolean;
    directions: Record<string, { index: number; files: { color: string; normal?: string }; pivot?: [number, number] }[]>;
  }[];
}

interface SheetDocument {
  files: { color: string; normal: string };
  cell: { width: number; height: number };
  pivot: { x: number; y: number };
  directions: string[];
  clips: {
    name: string;
    fps: number;
    loop: boolean;
    stationary: boolean;
    directions: Record<string, { index: number; rect: { x: number; y: number; width: number; height: number } }[]>;
  }[];
}

function folderOf(path: string): string {
  return path.slice(0, path.lastIndexOf("/"));
}

function fromRender(document: RenderDocument, base: string, normalBase: string | null): FrameSet | null {
  if (!Array.isArray(document.clips) || !document.frame) return null;
  return {
    width: document.frame.width,
    height: document.frame.height,
    directions: document.directions,
    clips: document.clips.map((clip) => ({
      name: clip.name,
      fps: clip.fps,
      loop: clip.loop,
      stationary: clip.stationary,
      directions: Object.fromEntries(
        Object.entries(clip.directions).map(([direction, frames]) => [
          direction,
          frames.map((frame) => ({
            index: frame.index,
            color: { path: `${base}/${frame.files.color}` },
            normal: normalBase && frame.files.normal ? { path: `${normalBase}/${frame.files.normal}` } : null,
            pivot: frame.pivot ?? document.pivot,
          })),
        ]),
      ),
    })),
  };
}

function fromSheet(document: SheetDocument, base: string): FrameSet | null {
  if (!Array.isArray(document.clips) || !document.files || !document.cell) return null;
  const pivot: [number, number] = [document.pivot.x, document.pivot.y];
  return {
    width: document.cell.width,
    height: document.cell.height,
    directions: document.directions,
    clips: document.clips.map((clip) => ({
      name: clip.name,
      fps: clip.fps,
      loop: clip.loop,
      stationary: clip.stationary,
      directions: Object.fromEntries(
        Object.entries(clip.directions).map(([direction, frames]) => [
          direction,
          frames.map((frame) => ({
            index: frame.index,
            color: { path: `${base}/${document.files.color}`, rect: frame.rect },
            normal: { path: `${base}/${document.files.normal}`, rect: frame.rect },
            pivot,
          })),
        ]),
      ),
    })),
  };
}

// What a finding says about a frame: `<clip>/<direction>/<index>` in its field (or `<clip>/<direction>` for a count), else the
// frame file's name (`color/<clip>/<direction>/<NNN>.png`).
export interface FrameFocus {
  clip: string;
  direction: string;
  index: number | null;
  count: number;
}

export function frameOf(finding: Finding): Omit<FrameFocus, "count"> | null {
  const stage = finding.position?.stage;
  if (!stage || !FRAME_STAGES.includes(stage)) return null;
  const field = /^([a-z0-9_]+)\/([a-z]+)(?:\/(\d+))?$/.exec(finding.position?.field ?? "");
  if (field) return { clip: field[1], direction: field[2], index: field[3] === undefined ? null : Number(field[3]) };
  const file = /(?:^|\/)(?:color|normal)\/([^/]+)\/([^/]+)\/(\d+)\.png$/.exec(finding.position?.file ?? "");
  return file ? { clip: file[1], direction: file[2], index: Number(file[3]) } : null;
}

// Images are loaded once and kept: a URL carries the version of the last changed image, so one never means another picture.
const loaded = new Map<string, HTMLImageElement>();
const loading = new Map<string, Promise<void>>();

function load(url: string): Promise<void> {
  let found = loading.get(url);
  if (!found) {
    found = new Promise<void>((done) => {
      const image = new Image();
      image.onload = () => {
        loaded.set(url, image);
        done();
      };
      image.onerror = () => done(); // a missing frame stays blank; the Stage's Checks say so
      image.src = url;
    });
    loading.set(url, found);
  }
  return found;
}

function useImages(urls: string[]): (url: string) => HTMLImageElement | undefined {
  const [, bump] = useState(0);
  const key = urls.join("\n");
  useEffect(() => {
    let live = true;
    for (const url of key ? key.split("\n") : []) {
      if (!loaded.has(url)) void load(url).then(() => live && bump((count) => count + 1));
    }
    return () => {
      live = false;
    };
  }, [key]);
  return (url) => loaded.get(url);
}

interface Layer {
  url: string;
  rect?: Source["rect"];
  alpha: number;
}

// Drawn at the frame's own size with no smoothing; CSS scales the canvas by a whole number and keeps its pixels square.
function FrameCanvas(props: {
  width: number;
  height: number;
  zoom: number;
  layers: Layer[];
  get: (url: string) => HTMLImageElement | undefined;
  testid?: string;
  pivot?: [number, number] | null;
}) {
  const { width, height, zoom, layers, get } = props;
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const context = canvas.current?.getContext("2d");
    if (!context) return;
    context.imageSmoothingEnabled = false;
    context.clearRect(0, 0, width, height);
    for (const layer of layers) {
      const image = get(layer.url);
      if (!image) continue;
      const rect = layer.rect ?? { x: 0, y: 0, width: image.naturalWidth, height: image.naturalHeight };
      context.globalAlpha = layer.alpha;
      context.drawImage(image, rect.x, rect.y, rect.width, rect.height, 0, 0, rect.width, rect.height);
    }
    context.globalAlpha = 1;
  });
  return (
    <span className="frame-box" style={{ width: width * zoom, height: height * zoom }}>
      <canvas
        ref={canvas}
        data-testid={props.testid}
        data-zoom={zoom}
        width={width}
        height={height}
        style={{ width: width * zoom, height: height * zoom }}
      />
      {props.pivot && (
        <i
          className="pivot-mark"
          data-testid={props.testid ? `${props.testid}-pivot` : undefined}
          style={{ left: Math.floor(props.pivot[0]) * zoom, top: Math.floor(props.pivot[1]) * zoom, width: zoom, height: zoom }}
        />
      )}
    </span>
  );
}

interface View {
  clip: string | null;
  direction: string | null;
  position: number;
  onion: boolean;
  normal: boolean;
  pivot: boolean;
  zoom: number;
}

// What the Owner chose stays while they go from one picture Stage to the next.
const views = new Map<string, View>();
const START: View = { clip: null, direction: null, position: 0, onion: false, normal: false, pivot: true, zoom: 4 };

export function FrameScreen(props: {
  stage: string;
  show: ShowData;
  detail: StageDetail;
  refreshes: number;
  imageVersion: number;
  focus: FrameFocus | null;
}) {
  const { stage, show, detail, refreshes, imageVersion } = props;
  const sheet = stage === "sheet";
  const path = outputOf(detail, sheet ? "sheet.json" : "render.json");
  const document = useDocument<RenderDocument | SheetDocument>(path, refreshes);
  // The palette Stage makes colour frames only: its normals are the render Stage's.
  const renderDetail = show.stages.find((entry) => entry.stage === "render");
  const renderPath = stage === "palette" ? outputOf(renderDetail, "render.json") : null;
  const frameSet: FrameSet | null =
    document && path
      ? sheet
        ? fromSheet(document as SheetDocument, folderOf(path))
        : fromRender(document as RenderDocument, folderOf(path), renderPath ? folderOf(renderPath) : folderOf(path))
      : null;

  const [view, setView] = useState<View>(() => views.get(show.asset) ?? START);
  const [playing, setPlaying] = useState(false);
  useEffect(() => {
    views.set(show.asset, view);
  }, [show.asset, view]);
  const change = (next: Partial<View>) => setView((before) => ({ ...before, ...next }));

  const clip = frameSet?.clips.find((entry) => entry.name === view.clip) ?? frameSet?.clips[0] ?? null;
  const direction =
    frameSet && view.direction && frameSet.directions.includes(view.direction)
      ? view.direction
      : frameSet?.directions.includes("s")
        ? "s"
        : (frameSet?.directions[0] ?? null);
  const frames = (clip && direction ? clip.directions[direction] : null) ?? [];
  const position = Math.max(0, Math.min(view.position, frames.length - 1));

  // A finding's jump: its Clip, Direction and frame (the first frame when it names none).
  const applied = useRef(0);
  useEffect(() => {
    const focus = props.focus;
    if (!focus || !frameSet || focus.count === applied.current) return;
    applied.current = focus.count;
    const target = frameSet.clips.find((entry) => entry.name === focus.clip);
    const at = target?.directions[focus.direction]?.findIndex((entry) => entry.index === focus.index) ?? -1;
    setPlaying(false);
    change({ clip: focus.clip, direction: focus.direction, position: Math.max(0, at) });
  }, [props.focus, frameSet]);

  const step = (by: number) => {
    setPlaying(false);
    if (frames.length > 0) change({ position: (((position + by) % frames.length) + frames.length) % frames.length });
  };
  const play = () => {
    if (frames.length < 2) return;
    // A Clip that plays once and has ended starts again from its first frame.
    if (!playing && clip && !clip.loop && position === frames.length - 1) change({ position: 0 });
    setPlaying(!playing);
  };

  // The player: the frame is where the clock says, so a slow browser skips frames and never slows the Clip.
  const here = useRef(position);
  here.current = position;
  const fps = clip?.fps ?? 12;
  const loops = clip?.loop ?? true;
  const count = frames.length;
  useEffect(() => {
    if (!playing || count < 2) return;
    const from = here.current;
    const start = performance.now();
    let id = 0;
    const tick = (now: number) => {
      const target = from + Math.floor(((now - start) * fps) / 1000);
      if (loops) {
        change({ position: target % count });
      } else if (target >= count - 1) {
        change({ position: count - 1 });
        setPlaying(false);
        return;
      } else {
        change({ position: target });
      }
      id = requestAnimationFrame(tick);
    };
    id = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(id);
  }, [playing, clip?.name, direction, fps, loops, count]);

  // The keys. Letters switch what is shown, the number pad picks the Direction, `Z` zooms, `Space` plays.
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (isTyping(event.target) || event.ctrlKey || event.metaKey || event.altKey || !frameSet) return;
      const named = event.code.replace(/^(Numpad|Digit)/, "");
      if (/^(Numpad|Digit)[1-9]$/.test(event.code) && PAD[named]) {
        if (frameSet.directions.includes(PAD[named])) change({ direction: PAD[named] });
      } else if (event.code === "ArrowLeft" || event.code === "Comma") step(-1);
      else if (event.code === "ArrowRight" || event.code === "Period") step(1);
      else if (event.code === "ArrowUp" || event.code === "ArrowDown") {
        const at = frameSet.clips.findIndex((entry) => entry.name === clip?.name);
        const next = frameSet.clips[at + (event.code === "ArrowUp" ? -1 : 1)];
        if (next) {
          setPlaying(false);
          change({ clip: next.name, position: 0 });
        }
      } else if (event.code === "KeyP") play();
      else if (event.code === "Space") {
        // Space presses a focused button or link, as it does everywhere.
        if (event.target instanceof HTMLElement && event.target.closest("button, a, summary")) return;
        play();
      } else if (event.code === "KeyO") change({ onion: !view.onion });
      else if (event.code === "KeyN") change({ normal: !view.normal });
      else if (event.code === "KeyZ") change({ zoom: ZOOMS[(ZOOMS.indexOf(view.zoom) + 1) % ZOOMS.length] ?? 4 });
      else return;
      event.preventDefault();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  });

  const pick = (item: Frame | undefined, normal: boolean): Source | null => (normal ? (item?.normal ?? null) : (item?.color ?? null));
  const normalShown = view.normal && frames.some((item) => item.normal);
  const layerOf = (item: Frame | undefined, alpha: number): Layer[] => {
    const source = pick(item, normalShown);
    return source ? [{ url: fileUrl(source.path, imageVersion), rect: source.rect, alpha }] : [];
  };
  const current = frames[position];
  const layers: Layer[] = [
    ...(view.onion ? [...layerOf(frames[position - 1], 0.3), ...layerOf(frames[position + 1], 0.3)] : []),
    ...layerOf(current, 1),
  ];
  // Every frame of the Direction is loaded for the strip and the player (one atlas, on `sheet`).
  const urls = frames.flatMap((item) => layerOf(item, 1).map((layer) => layer.url));
  const get = useImages([...new Set(urls)]);

  if (!frameSet) {
    return (
      <div className="character-screen frame-screen" data-testid="frame-screen">
        <h2>Frames</h2>
        <p className="hint" data-testid="frames-empty">
          {path ? "Reading the frames…" : `No frames yet: run ${stage} to make them.`}
        </p>
      </div>
    );
  }

  return (
    <div className="character-screen frame-screen" data-testid="frame-screen">
      <div className="frame-top">
        <div className="clip-tabs" role="group" aria-label="Clip" data-testid="clip-tabs">
          {frameSet.clips.map((entry) => (
            <button
              key={entry.name}
              data-testid={`clip-tab-${entry.name}`}
              aria-pressed={entry.name === clip?.name}
              onClick={() => {
                setPlaying(false);
                change({ clip: entry.name, position: 0 });
              }}
            >
              {entry.name}
            </button>
          ))}
        </div>
        <div className="compass" role="group" aria-label="Direction" data-testid="compass">
          {COMPASS.flat().map((name, index) =>
            name === null ? (
              <span key={index} />
            ) : (
              <button
                key={name}
                data-testid={`direction-${name}`}
                aria-pressed={name === direction}
                disabled={!frameSet.directions.includes(name)}
                title={`${name} (number pad ${PAD_KEY[name]})`}
                onClick={() => change({ direction: name })}
              >
                {name} <kbd>{PAD_KEY[name]}</kbd>
              </button>
            ),
          )}
        </div>
      </div>

      <div
        className="frame-stage"
        data-testid="frame-view"
        data-clip={clip?.name ?? ""}
        data-direction={direction ?? ""}
        data-frame={current?.index ?? ""}
        data-position={position}
        data-playing={playing}
        data-onion={view.onion}
        data-normal={normalShown}
      >
        {current ? (
          <FrameCanvas
            width={frameSet.width}
            height={frameSet.height}
            zoom={view.zoom}
            layers={layers}
            get={get}
            testid="frame-canvas"
            pivot={view.pivot ? current.pivot : null}
          />
        ) : (
          <p className="hint" data-testid="frame-missing">
            This Clip has no frames in this Direction.
          </p>
        )}
      </div>

      <div className="player" role="group" aria-label="Player">
        <button data-testid="player-prev" onClick={() => step(-1)} title="Previous frame (, or left arrow)">
          ◀
        </button>
        <button data-testid="player-play" aria-pressed={playing} onClick={play} title="Play or pause (Space or P)">
          {playing ? "Pause" : "Play"}
        </button>
        <button data-testid="player-next" onClick={() => step(1)} title="Next frame (. or right arrow)">
          ▶
        </button>
        <span data-testid="player-info">
          Frame {current?.index ?? "-"} of {frames.length} · {clip?.fps ?? "-"} frames a second · {clip?.loop ? "loops" : "plays once"}
          {clip?.stationary ? " · stationary" : ""}
        </span>
      </div>

      <div className="frame-options">
        <label className="toggle">
          <input type="checkbox" data-testid="onion" checked={view.onion} onChange={(event) => change({ onion: event.target.checked })} />
          Onion skin <kbd>O</kbd>
        </label>
        <label className="toggle">
          <input
            type="checkbox"
            data-testid="normal-view"
            checked={normalShown}
            disabled={!frames.some((item) => item.normal)}
            onChange={(event) => change({ normal: event.target.checked })}
          />
          Normal map <kbd>N</kbd>
        </label>
        <label className="toggle">
          <input type="checkbox" data-testid="pivot-view" checked={view.pivot} onChange={(event) => change({ pivot: event.target.checked })} />
          Pivot
        </label>
        <button
          data-testid="zoom"
          onClick={() => change({ zoom: ZOOMS[(ZOOMS.indexOf(view.zoom) + 1) % ZOOMS.length] ?? 4 })}
          title="Zoom (Z)"
        >
          ×{view.zoom} <kbd>Z</kbd>
        </button>
      </div>

      <div className="frame-strip" data-testid="frame-strip" role="group" aria-label="Frames">
        {frames.map((item, index) => (
          <button
            key={item.index}
            className="frame-thumb"
            data-testid={`frame-${item.index}`}
            aria-pressed={index === position}
            onClick={() => {
              setPlaying(false);
              change({ position: index });
            }}
          >
            <FrameCanvas width={frameSet.width} height={frameSet.height} zoom={1} layers={layerOf(item, 1)} get={get} />
            <small>{item.index}</small>
          </button>
        ))}
      </div>
    </div>
  );
}
