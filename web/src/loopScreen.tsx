// The room's loops screen (ticket 0191, spec §6.1 and §11): the room's Loops, a region by flood, polygon or brush, a colour cycle
// picked with an eyedropper, the timing, and a preview of the whole room with every Loop playing. The screen holds no logic of its
// own: each change is one Decision (`loop`, `cycle`, `timing`, `flood`, `polygon`, `brush`) and a Loop is what the Stage builds
// (`loops.json`). The preview steps in whole 60 Hz ticks by the `sequence` the export writes; it is not a CSS animation.
//
// The region tools are `MaskTool` (ADR 0008) with one Mask name, "region", that the screen fills from the built strips' alpha.

import { useEffect, useRef, useState, type RefObject } from "react";
import { fileUrl, type Finding, type ShowData, type StageDescription, type StageDetail } from "./api";
import { LoopTool, type PlayingLoop } from "./loopTool";
import { MAX_RADIUS, MaskTool, MIN_RADIUS, tintOf } from "./maskTool";
import { isTyping, type CanvasPixel, type PixelCanvas } from "./pixelCanvas";
import { paletteColours } from "./roomScreens";
import { layerFiles } from "./sortView";

export const LOOPS_STAGE = "loops";
export const LOOPS_DECISION = "cycle"; // what tells the loops Stage's screen from another's
const REGION = "region";
const PALETTE_FILE = "style/palette.gpl";
const PLATE = "plate";
const DEFAULT_TOLERANCE = 0.03; // the Stage's own default (a `flood` Decision without one; trial 0184)
const DEFAULT_EVEN_TICKS = 8;

type Tool = "brush" | "erase" | "polygon" | "polygon-erase" | "flood" | "eyedrop" | "anchor";
const TOOLS: { name: Tool; key: string; label: string; hint: string }[] = [
  { name: "flood", key: "f", label: "Flood", hint: "Click a pixel: the region gains the connected pixels of about its colour." },
  { name: "polygon", key: "g", label: "Polygon", hint: "Click the corners; click the first point or press Enter to close and fill. Backspace removes the last point, Esc drops it." },
  { name: "brush", key: "b", label: "Brush", hint: "Drag to add to the Loop's region." },
  { name: "erase", key: "e", label: "Erase", hint: "Drag to take from the Loop's region." },
  { name: "polygon-erase", key: "x", label: "Erase polygon", hint: "Click the corners; click the first point or press Enter to close and clear." },
  { name: "anchor", key: "r", label: "Anchor row", hint: "Click a row of the room: a sway holds that row still and moves what lies above it." },
  { name: "eyedrop", key: "i", label: "Eyedropper", hint: "Click the room: that pixel's colour joins the cycle, and the pixels of it in the region light up." },
];

export interface BuiltLoop {
  id: string;
  form: string;
  layer: string;
  light: string | null;
  phase: number;
  mode: string;
  colours: string[];
  depth: number | null;
  steps: number;
  emissive: boolean | null;
  box: [number, number, number, number] | null;
  frames: number;
  columns: number;
  plate: string | null;
  layers: { id: string; file: string }[];
  timing: Record<string, unknown>;
  sequence: [number, number][];
  ticks: number;
  pixels: number;
  source: string | null;
  op: string | null;
  params: Record<string, number> | null;
  kit: { frames: { frame: number; file: string }[] } | null;
}

export interface FramesData {
  source?: "op" | "kit";
  op?: "sway" | "shimmer" | "scroll";
  params?: Record<string, number>;
}

// The Ops' defaults (`kiripix/ops/frames.py`, placeholders until trial 0184), and the sliders each Op's parameter gets.
const OPS = ["sway", "shimmer", "scroll"] as const;
const OP_SLIDERS: Record<string, { key: string; label: string; min: number; max: number; fallback: number }[]> = {
  sway: [
    { key: "amplitude", label: "Amplitude (px)", min: 1, max: 8, fallback: 1 },
    { key: "frames", label: "Frames", min: 2, max: 12, fallback: 4 },
  ],
  shimmer: [
    { key: "amplitude", label: "Amplitude (px)", min: 1, max: 6, fallback: 1 },
    { key: "wavelength", label: "Wavelength (rows)", min: 2, max: 32, fallback: 6 },
    { key: "frames", label: "Frames", min: 2, max: 12, fallback: 6 },
  ],
  scroll: [
    { key: "dx", label: "Across a frame (px)", min: -8, max: 8, fallback: 1 },
    { key: "dy", label: "Down a frame (px)", min: -8, max: 8, fallback: 0 },
  ],
};

interface Journal {
  name: string;
  data: Record<string, unknown>;
}

export interface CycleData {
  colours: string[];
  mode: "rotate" | "pulse";
  depth?: number;
  steps?: number;
  emissive?: boolean;
}

export interface LoopEntry {
  id: string;
  form: string;
  layer: string;
  light: string | null;
  phase: number;
  cycle: CycleData | null;
  timing: Record<string, unknown> | null;
  frames: FramesData | null;
  built: BuiltLoop | null;
}

function latest(decisions: Journal[], name: string, id: string): Record<string, unknown> | null {
  const found = decisions.filter((decision) => decision.name === name && decision.data.loop === id).at(-1);
  return found ? found.data : null;
}

// A Loop exists once a `loop` Decision declares it; the latest `loop`, `cycle` and `timing` of each count.
export function loopsOf(decisions: Journal[], built: BuiltLoop[]): LoopEntry[] {
  const ids = [...new Set(decisions.filter((decision) => decision.name === "loop").map((decision) => String(decision.data.loop)))].sort();
  return ids.map((id) => {
    const loop = latest(decisions, "loop", id) ?? {};
    const cycle = latest(decisions, "cycle", id);
    const timing = latest(decisions, "timing", id);
    const framesOf = latest(decisions, "frames", id);
    const { loop: _loop, ...rest } = timing ?? {};
    return {
      id,
      form: typeof loop.form === "string" ? loop.form : "cycle",
      layer: typeof loop.layer === "string" ? loop.layer : PLATE,
      light: typeof loop.light === "string" ? loop.light : null,
      phase: typeof loop.phase === "number" ? loop.phase : 0,
      cycle: cycle
        ? {
            colours: Array.isArray(cycle.colours) ? (cycle.colours as string[]) : [],
            mode: cycle.mode === "pulse" ? "pulse" : "rotate",
            depth: typeof cycle.depth === "number" ? cycle.depth : undefined,
            steps: typeof cycle.steps === "number" ? cycle.steps : undefined,
            emissive: typeof cycle.emissive === "boolean" ? cycle.emissive : undefined,
          }
        : null,
      timing: timing ? rest : null,
      frames: framesOf ? (framesOf as FramesData) : null,
      built: built.find((one) => one.id === id) ?? null,
    };
  });
}

// What a Decision of this Loop's `cycle` says: every field it has, since the latest Decision replaces the one before.
export function cycleData(id: string, cycle: CycleData): Record<string, unknown> {
  const data: Record<string, unknown> = { loop: id, mode: cycle.mode };
  if (cycle.colours.length > 0) data.colours = cycle.colours;
  if (cycle.depth !== undefined) data.depth = cycle.depth;
  if (cycle.steps !== undefined) data.steps = cycle.steps;
  if (cycle.emissive !== undefined) data.emissive = cycle.emissive;
  return data;
}

// The Decision a finding's `fix` command carries: the screen sends it as the same Command, not by running the text.
export function fixDecision(finding: Finding): { name: string; data: Record<string, unknown> } | null {
  const text = finding.fix?.match(/--decision '(.*)'\s*$/)?.[1];
  if (!text) return null;
  try {
    const parsed = JSON.parse(text) as { decision?: string; data?: Record<string, unknown> };
    return parsed.decision && parsed.data ? { name: parsed.decision, data: parsed.data } : null;
  } catch {
    return null;
  }
}

function findingLoop(finding: Finding, ids: string[]): string | null {
  const fixed = fixDecision(finding)?.data.loop;
  if (typeof fixed === "string") return fixed;
  return ids.find((id) => new RegExp(`(^|[^a-z0-9_.])${id.replace(/\./g, "\\.")}($|[^a-z0-9_.])`).test(finding.message)) ?? null;
}

function hexOf(data: Uint8ClampedArray, at: number): string {
  return "#" + [0, 1, 2].map((offset) => data[at + offset].toString(16).padStart(2, "0")).join("");
}

async function loadImage(url: string): Promise<HTMLImageElement> {
  const image = new Image();
  image.src = url;
  await image.decode();
  return image;
}

async function canvasOf(url: string): Promise<HTMLCanvasElement> {
  const image = await loadImage(url);
  const canvas = document.createElement("canvas");
  canvas.width = image.naturalWidth;
  canvas.height = image.naturalHeight;
  canvas.getContext("2d")!.drawImage(image, 0, 0);
  return canvas;
}

async function readPixels(url: string): Promise<ImageData> {
  const canvas = await canvasOf(url);
  return canvas.getContext("2d", { willReadFrequently: true })!.getImageData(0, 0, canvas.width, canvas.height);
}

// A number field that is committed (one Decision) on Enter or when it loses focus, not at each key.
function NumberField(props: { id: string; testid: string; value: string; placeholder?: string; min?: number; step?: number; onCommit: (text: string) => void }) {
  const [text, setText] = useState(props.value);
  const sent = useRef<string | null>(null); // what was committed and hasn't come back yet: Enter then blur is one commit
  useEffect(() => {
    setText(props.value);
    sent.current = null;
  }, [props.value]);
  const commit = () => {
    const typed = text.trim();
    if (typed === "") setText(props.value);
    else if (typed !== props.value && typed !== sent.current) {
      sent.current = typed;
      props.onCommit(typed);
    }
  };
  return (
    <input
      id={props.id}
      data-testid={props.testid}
      type="text"
      inputMode="decimal"
      placeholder={props.placeholder}
      value={text}
      onChange={(event) => setText(event.target.value)}
      onBlur={commit}
      onKeyDown={(event) => {
        if (event.key === "Enter") {
          commit();
          (event.target as HTMLInputElement).blur();
        }
      }}
    />
  );
}

// A slider that is committed (one Decision) when it is let go, not at each step of the drag.
function Slider(props: { id: string; testid: string; min: number; max: number; value: number; onCommit: (value: number) => void }) {
  const [now, setNow] = useState(props.value);
  const input = useRef<HTMLInputElement>(null);
  const commit = useRef(props.onCommit);
  commit.current = props.onCommit;
  useEffect(() => setNow(props.value), [props.value]);
  useEffect(() => {
    const element = input.current;
    if (!element) return;
    const done = () => commit.current(Number(element.value)); // `change` is the release of a drag, or one step of a key
    element.addEventListener("change", done);
    return () => element.removeEventListener("change", done);
  }, []);
  return (
    <>
      <input ref={input} id={props.id} data-testid={props.testid} type="range" min={props.min} max={props.max} step={1} value={now} onChange={(event) => setNow(Number(event.target.value))} />
      <output data-testid={`${props.testid}-value`}>{now}</output>
    </>
  );
}

const FRAME_CODES = ["loop.drift", "loop.misaligned", "loop.flicker", "loop.outside_region", "loop.off_palette", "loop.partial_alpha"];
const FRAME_SCALE = 4;

// One thumbnail of a frame: the Loop's pieces cut to the tile, at x4 and nearest.
function Thumbnail(props: { loop: PlayingLoop; frame: number }) {
  const { loop, frame } = props;
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const target = ref.current;
    if (!target) return;
    const [, , width, height] = loop.box;
    target.width = width;
    target.height = height;
    const context = target.getContext("2d")!;
    context.imageSmoothingEnabled = false;
    context.clearRect(0, 0, width, height);
    for (const piece of loop.pieces) {
      context.drawImage(piece, (frame % loop.columns) * width, Math.floor(frame / loop.columns) * height, width, height, 0, 0, width, height);
    }
  }, [loop, frame]);
  const [, , width, height] = loop.box;
  return <canvas ref={ref} className="thumb" style={{ width: width * FRAME_SCALE, height: height * FRAME_SCALE, imageRendering: "pixelated" }} />;
}

export function LoopsPanel(props: {
  canvas: RefObject<PixelCanvas | null>;
  show: ShowData;
  detail: StageDetail;
  decisions: StageDescription["decisions"];
  findings: Finding[];
  imageVersion: number;
  refreshes: number;
  disabled: boolean;
  rebuild: boolean;
  onRebuild: (rebuild: boolean) => void;
  roomImage: string | null;
  decide: (decision: string, data: Record<string, unknown>, settled?: () => void) => void;
  writeKit: (loop: string, folder: string, frames: number, force: boolean, written: (folder: string | null) => void) => void;
  importFrames: (loop: string, paths: string[]) => void;
  onStage: (stage: string) => void;
}) {
  const { canvas, show, detail, imageVersion, refreshes, disabled, rebuild, onRebuild, roomImage, findings } = props;
  const [built, setBuilt] = useState<BuiltLoop[]>([]);
  const [playing, setPlaying] = useState<PlayingLoop[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [newLoop, setNewLoop] = useState("");
  const [tool, setTool] = useState<Tool>("flood");
  const [radius, setRadius] = useState(2);
  const [opacity, setOpacity] = useState(40);
  const [tolerance, setTolerance] = useState(DEFAULT_TOLERANCE);
  const [room, setRoom] = useState<ImageData | null>(null);
  const [palette, setPalette] = useState<string[]>([]);
  const [lit, setLit] = useState<string | null>(null);
  const [hint, setHint] = useState("");
  const [running, setRunning] = useState(false);
  const [solo, setSolo] = useState(false);
  const [region, setRegion] = useState<Uint8Array | null>(null);
  const sentFrames = useRef<{ id: string; data: FramesData } | null>(null);
  const [newForm, setNewForm] = useState("cycle");
  const [inspect, setInspect] = useState<number | null>(null);
  const [kitFolder, setKitFolder] = useState("");
  const [kitFrames, setKitFrames] = useState("4");
  const [kitForce, setKitForce] = useState(false);
  const [kitWritten, setKitWritten] = useState<Record<string, string>>({});
  const [flicker, setFlicker] = useState<{ mean: string; spread: string; length: string }>({ mean: "", spread: "", length: "" });

  const entries = loopsOf(detail.decisions, built);
  const current = entries.find((entry) => entry.id === selected) ?? entries[0] ?? null;
  const latestProps = useRef({ ...props, current, entries, palette, room, region, tolerance, tool });
  latestProps.current = { ...props, current, entries, palette, room, region, tolerance, tool };
  const painter = useRef<MaskTool | null>(null);
  const player = useRef<LoopTool | null>(null);

  const roomFile = roomImage;
  const builtFile = detail.outputs.find((path) => path.endsWith("/loops.json"));
  const stageFolder = builtFile ? builtFile.slice(0, builtFile.lastIndexOf("/")) : "";
  const floodSpec = props.decisions.find((entry) => entry.name === "flood")?.entry_schema?.properties?.tolerance;
  const mostTolerance = floodSpec?.maximum ?? 0.2;
  const layers = [...layerFiles(show).keys()];

  // The tools, made once; their gestures read the latest props through the ref.
  useEffect(() => {
    const painting = new MaskTool(
      {
        stroke(_on, erase, size, points) {
          const { decide, current: here } = latestProps.current;
          if (!here) return;
          const done = painter.current?.addMark({ kind: "stroke", mask: REGION, erase, radius: size, points });
          decide("brush", { loop: here.id, erase, radius: size, points }, done);
        },
        polygon(_on, erase, points) {
          const { decide, current: here } = latestProps.current;
          if (!here) return;
          const done = painter.current?.addMark({ kind: "polygon", mask: REGION, erase, points });
          decide("polygon", { loop: here.id, erase, points }, done);
        },
        point(_tool, _on, pixel) {
          const { decide, current: here, tolerance: within } = latestProps.current;
          if (!here) return;
          const done = painter.current?.addMark({ kind: "point", x: pixel.x, y: pixel.y, positive: true });
          decide("flood", { loop: here.id, x: pixel.x, y: pixel.y, ...(within !== DEFAULT_TOLERANCE ? { tolerance: within } : {}) }, done);
        },
        async preview() {
          return null;
        },
      },
      () => canvas.current?.redraw(),
    );
    const playingTool = new LoopTool(
      () => canvas.current?.redraw(),
      (pixel) => pickColour(pixel),
    );
    painter.current = painting;
    player.current = playingTool;
    canvas.current?.setTools([playingTool, painting]); // the Loops are drawn first, the region tint over them
    return () => {
      painting.destroy();
      playingTool.destroy();
      canvas.current?.setTools([]);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canvas]);

  useEffect(() => {
    const painting = painter.current;
    const playingTool = player.current;
    if (!painting || !playingTool) return;
    const picking = tool === "eyedrop" || tool === "anchor";
    playingTool.picking = picking;
    painting.setTool(picking ? "flood" : tool);
    painting.mask = picking ? "" : REGION;
    painting.radius = radius;
    painting.opacity = opacity / 100;
    canvas.current?.redraw();
  }, [canvas, tool, radius, opacity]);

  // The built loops.json, read again at each refresh.
  useEffect(() => {
    if (!builtFile) {
      setBuilt([]);
      return;
    }
    let live = true;
    void fetch(fileUrl(builtFile, refreshes))
      .then((response) => response.json() as Promise<{ loops: BuiltLoop[] }>)
      .then((document) => live && setBuilt(document.loops))
      .catch(() => undefined); // Rebuilt while it was read; the next refresh reads it again.
    return () => {
      live = false;
    };
  }, [builtFile, refreshes]);

  // The room's pixels for the eyedropper, and the Project palette for the swatches.
  useEffect(() => {
    let live = true;
    if (roomFile) {
      void readPixels(fileUrl(roomFile, imageVersion))
        .then((pixels) => live && setRoom(pixels))
        .catch(() => undefined);
    }
    void fetch(fileUrl(PALETTE_FILE, imageVersion))
      .then((response) => (response.ok ? response.text() : ""))
      .then((text) => live && setPalette(paletteColours(text).map((colour) => colour.toLowerCase())))
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [roomFile, imageVersion]);

  // The built Loops' strips, for the preview; and the selected Loop's region, from the alpha of its frame 0.
  const shown = JSON.stringify(built.map((loop) => [loop.id, loop.box, loop.columns, loop.plate, loop.layers, loop.sequence, loop.ticks, loop.phase]));
  useEffect(() => {
    let live = true;
    void (async () => {
      const loops: PlayingLoop[] = [];
      for (const loop of built) {
        if (!loop.box || !loop.sequence.length) continue;
        const files = [...(loop.plate ? [loop.plate] : []), ...loop.layers.map((layer) => layer.file)];
        const pieces = await Promise.all(files.map((file) => canvasOf(fileUrl(`${stageFolder}/${file}`, imageVersion))));
        loops.push({ id: loop.id, box: loop.box, columns: Math.max(1, loop.columns), sequence: loop.sequence, period: loop.ticks, phase: loop.phase, pieces });
      }
      if (!live) return;
      setPlaying(loops);
    })().catch(() => undefined);
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shown, stageFolder, imageVersion]);

  useEffect(() => {
    const playingTool = player.current;
    if (!playingTool) return;
    playingTool.loops = playing;
    canvas.current?.redraw();
  }, [canvas, playing]);

  useEffect(() => {
    if (!room) return;
    const { width, height } = room;
    const set = new Uint8Array(width * height);
    const here = playing.find((loop) => loop.id === current?.id);
    if (here) {
      const [x, y, w, h] = here.box;
      for (const piece of here.pieces) {
        const alpha = piece.getContext("2d", { willReadFrequently: true })!.getImageData(0, 0, w, h).data;
        for (let py = 0; py < h; py++) for (let px = 0; px < w; px++) if (alpha[(py * w + px) * 4 + 3] > 0) set[(y + py) * width + x + px] = 1;
      }
    }
    painter.current?.setMasks([{ name: REGION, pixels: { width, height, set } }]);
    setRegion(set);
    canvas.current?.redraw();
  }, [canvas, room, playing, current?.id]);

  // The pixels of the lit colour, in the region when there is one and in the whole room when the Loop isn't built yet.
  useEffect(() => {
    const playingTool = player.current;
    if (!playingTool) return;
    if (!lit || !room) {
      playingTool.lit = null;
      canvas.current?.redraw();
      return;
    }
    const { width, height } = room;
    const overlay = document.createElement("canvas");
    overlay.width = width;
    overlay.height = height;
    const paint = overlay.getContext("2d")!;
    paint.fillStyle = "#ffe14d";
    const inRegion = region && region.some((value) => value === 1) ? region : null;
    let count = 0;
    for (let at = 0; at < width * height; at++) {
      if (room.data[at * 4 + 3] === 0 || hexOf(room.data, at * 4) !== lit) continue;
      if (inRegion && inRegion[at] !== 1) continue;
      paint.fillRect(at % width, Math.floor(at / width), 1, 1);
      count++;
    }
    playingTool.lit = overlay;
    overlay.dataset.count = String(count);
    canvas.current?.element.setAttribute("data-lit", `${lit}:${count}`);
    canvas.current?.redraw();
  }, [canvas, lit, room, region]);
  useEffect(() => () => canvas.current?.element.removeAttribute("data-lit"), [canvas]);

  useEffect(() => {
    const playingTool = player.current;
    if (!playingTool) return;
    playingTool.solo = solo && current ? current.id : null;
    canvas.current?.redraw();
  }, [canvas, solo, current?.id]);

  // The frame looked at alone, with the one before it faint; a play or another Loop puts the whole room back.
  useEffect(() => {
    const playingTool = player.current;
    if (!playingTool) return;
    playingTool.inspect = inspect !== null && current ? { id: current.id, frame: inspect } : null;
    canvas.current?.redraw();
  }, [canvas, inspect, current?.id, playing]);
  useEffect(() => setInspect(null), [current?.id]);
  useEffect(() => {
    sentFrames.current = null; // the journal caught up
  }, [JSON.stringify(current?.frames)]);
  useEffect(() => {
    const playingTool = player.current;
    if (!playingTool) return;
    playingTool.anchorRow = current?.frames?.op === "sway" && typeof current.frames.params?.anchor_row === "number" ? current.frames.params.anchor_row : null;
    canvas.current?.redraw();
  }, [canvas, current?.id, JSON.stringify(current?.frames)]);

  useEffect(() => {
    const entry = entries.find((one) => one.id === current?.id);
    const flickering = entry?.timing?.flicker as Record<string, number> | undefined;
    setFlicker({
      mean: flickering?.mean_ticks !== undefined ? String(flickering.mean_ticks) : "",
      spread: flickering?.spread !== undefined ? String(flickering.spread) : "",
      length: flickering?.length_ticks !== undefined ? String(flickering.length_ticks) : "",
    });
    setHint("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [current?.id, JSON.stringify(current?.timing)]);

  function playOrPause() {
    const playingTool = player.current;
    if (!playingTool) return;
    if (playingTool.playing) playingTool.pause();
    else playingTool.play();
    setRunning(playingTool.playing);
  }

  function stepOne() {
    player.current?.step();
    setRunning(false);
  }

  function pickColour(pixel: CanvasPixel) {
    const { room: image, current: here, palette: colours, tool: active } = latestProps.current;
    if (active === "anchor") {
      if (here) setFramesOp({ ...(here.frames ?? {}), source: "op", op: "sway", params: { ...(here.frames?.params ?? {}), anchor_row: pixel.y } });
      return;
    }
    if (!image || !here) return;
    const at = (pixel.y * image.width + pixel.x) * 4;
    if (image.data[at + 3] === 0) {
      setHint("That pixel is transparent; it has no colour to add.");
      return;
    }
    const hex = hexOf(image.data, at);
    setLit(hex);
    if (colours.length > 0 && !colours.includes(hex)) setHint(`${hex} is not on the Project palette, so a cycle can't use it.`);
    else addColour(hex);
  }

  // The latest `frames` Decision replaces the one before, so each change sends the Op and every parameter it has.
  function setFramesOp(next: FramesData) {
    const { current: here, decide } = latestProps.current;
    if (!here) return;
    sentFrames.current = { id: here.id, data: next }; // two quick changes: the second builds on the first, not on the journal as it was
    decide("frames", { loop: here.id, ...next });
  }

  function chooseOp(op: (typeof OPS)[number]) {
    if (!current) return;
    setFramesOp({ source: "op", op, params: op === "scroll" ? { dx: 1 } : {} });
  }

  function setOpParam(key: string, value: number) {
    const base = sentFrames.current?.id === current?.id ? sentFrames.current!.data : current?.frames;
    if (!current || !base?.op) return;
    const params = { ...(base.params ?? {}), [key]: value };
    if (base.op === "scroll" && (key === "dx" || key === "dy")) {
      if (value !== 0) delete params[key === "dx" ? "dy" : "dx"]; // one of the two moves
      else if (!params.dx && !params.dy) params.dx = 1;
    }
    setFramesOp({ ...base, source: "op", params });
  }

  function setCycle(patch: Partial<CycleData>) {
    if (!current) return;
    const base: CycleData = current.cycle ?? { colours: [], mode: "rotate" };
    props.decide("cycle", cycleData(current.id, { ...base, ...patch }));
  }

  function addColour(hex: string) {
    const { current: here } = latestProps.current;
    if (!here) return;
    const colours = here.cycle?.colours ?? [];
    if (colours.includes(hex)) {
      setHint(`${hex} is already in the cycle.`);
      return;
    }
    setHint("");
    const base: CycleData = here.cycle ?? { colours: [], mode: "rotate" };
    props.decide("cycle", cycleData(here.id, { ...base, colours: [...colours, hex] }));
  }

  function reorder(index: number, by: number) {
    const colours = [...(current?.cycle?.colours ?? [])];
    [colours[index], colours[index + by]] = [colours[index + by], colours[index]];
    setCycle({ colours });
  }

  function setTiming(timing: Record<string, unknown>) {
    if (current) props.decide("timing", { loop: current.id, ...timing });
  }

  function setLoop(patch: Record<string, unknown>) {
    if (!current) return;
    const data: Record<string, unknown> = { loop: current.id, form: current.form, layer: current.layer, phase: current.phase };
    if (current.light) data.light = current.light;
    props.decide("loop", { ...data, ...patch });
  }

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (isTyping(event.target)) return;
      if (event.ctrlKey || event.metaKey || event.altKey) return;
      const key = event.key.toLowerCase();
      const chosen = TOOLS.find((entry) => entry.key === key);
      if (chosen) setTool(chosen.name);
      else if (key === "p") playOrPause();
      else if (key === "n") stepOne();
      else if (key === "o") setSolo((now) => !now);
      else if (/^[1-9]$/.test(key)) {
        const one = latestProps.current.entries[Number(key) - 1];
        if (one) setSelected(one.id);
      } else if (event.key === "[") setRadius((size) => Math.max(MIN_RADIUS, size - 1));
      else if (event.key === "]") setRadius((size) => Math.min(MAX_RADIUS, size + 1));
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const id = newLoop.trim();
  const valid = /^[a-z0-9_]+(\.[a-z0-9_]+)*$/.test(id);
  const active = TOOLS.find((entry) => entry.name === tool)!;
  const ids = entries.map((entry) => entry.id);
  const mine = current ? findings.filter((finding) => finding.code.startsWith("loop.") && findingLoop(finding, ids) === current.id) : [];
  const inline = (code: string) => mine.filter((finding) => finding.code === code);
  const timing = current?.timing ?? null;
  const flickering = timing !== null && "flicker" in timing;
  const flickerSeed = flickering ? Number((timing!.flicker as Record<string, number>).seed) : 0;
  const ticksNow = timing && "ticks" in timing ? timing.ticks : (current?.built?.timing.ticks ?? DEFAULT_EVEN_TICKS);
  const pingpong = timing?.pingpong === true;
  const cycle = current?.cycle ?? null;
  const colours = cycle?.colours ?? [];
  const mode = cycle?.mode ?? "rotate";

  const isFrames = current?.form === "frames";
  const kitImported = (current?.built?.kit?.frames.length ?? 0) > 0;
  const source: "op" | "kit" | null = current?.frames?.source ?? (current?.frames?.op ? "op" : kitImported ? "kit" : null);
  const opName = source === "op" ? (current?.frames?.op ?? null) : null;
  const playingHere = playing.find((loop) => loop.id === current?.id) ?? null;
  const NO_FILL = mine.find((finding) => finding.code === "loop.no_fill")?.message ?? "A sway on the plate has no fill for what it uncovers: lift the object onto its own Layer first.";

  // The findings that belong to one frame: a kit frame's by its file, any other by the frame number in its message.
  function frameFindings(n: number): Finding[] {
    const file = current?.built?.kit?.frames.find((entry) => entry.frame === n)?.file;
    return mine.filter((finding) => {
      if (!FRAME_CODES.includes(finding.code)) return false;
      if (file && finding.position?.file === file) return true;
      return new RegExp(`frame ${n}\b`).test(finding.message);
    });
  }

  function importKit() {
    if (!current) return;
    const folder = (kitFolder.trim() || kitWritten[current.id] || `kits/${current.id}`).replace(/[\/]+$/, "");
    const count = Math.trunc(Number(kitFrames)) || 4;
    const imported = current.built?.kit?.frames.length;
    const total = Math.max(2, kitFolder.trim() || kitWritten[current.id] ? count : (imported ?? 0) + 1);
    props.importFrames(current.id, Array.from({ length: total - 1 }, (_, at) => `${folder}/frame_${String(at + 1).padStart(3, "0")}.png`));
  }

  function sendFlicker(patch: { seed?: number; mean?: string; spread?: string; length?: string }) {
    const next = { mean: patch.mean ?? flicker.mean, spread: patch.spread ?? flicker.spread, length: patch.length ?? flicker.length };
    setFlicker(next);
    const flickerOf: Record<string, number> = { seed: patch.seed ?? flickerSeed };
    for (const [key, text] of [["mean_ticks", next.mean], ["spread", next.spread], ["length_ticks", next.length]] as const) {
      if (text.trim() !== "" && Number.isFinite(Number(text))) flickerOf[key] = Number(text);
    }
    setTiming({ flicker: flickerOf });
  }

  function ticksFrom(text: string): number | number[] | null {
    const parts = text.split(/[\s,]+/).filter(Boolean).map(Number);
    if (parts.length === 0 || parts.some((value) => !Number.isInteger(value) || value < 1)) return null;
    return parts.length === 1 ? parts[0] : parts;
  }

  return (
    <fieldset disabled={disabled} className="mask-form" data-testid="loop-panel">
      <h2>Loops</h2>
      {entries.length === 0 ? (
        <p className="hint">This room has no Loops. Name one below to start: a Loop always plays, over and over, cut to a region.</p>
      ) : (
        <ul className="looks" data-testid="loop-list">
          {entries.map((entry, index) => {
            const own = findings.filter((finding) => finding.code.startsWith("loop.") && findingLoop(finding, ids) === entry.id && finding.severity !== "info");
            return (
              <li key={entry.id}>
                <button data-testid={`loop-${entry.id}`} aria-pressed={current?.id === entry.id} onClick={() => setSelected(entry.id)}>
                  {index < 9 && <kbd>{index + 1}</kbd>} {entry.id}
                </button>
                <small>
                  {entry.form}, on {entry.layer}
                  {entry.built === null ? ", not built yet" : entry.built.box === null ? ", no region" : `, ${entry.built.pixels} px, ${entry.built.frames} frames, ${entry.built.ticks} ticks`}
                  {own.length > 0 && <span data-testid={`loop-findings-${entry.id}`}>{`, ${own.map((finding) => finding.code).join(" ")}`}</span>}
                </small>
              </li>
            );
          })}
        </ul>
      )}
      <div className="param">
        <label htmlFor="loop-new">New Loop</label>
        <input id="loop-new" data-testid="loop-new" type="text" placeholder="lamp_glow" value={newLoop} onChange={(event) => setNewLoop(event.target.value)} />
      </div>
      {id !== "" && !valid && <p className="reason">A Loop ID is lower-case letters, digits and underscores, with dots between parts.</p>}
      <div className="param">
        <label htmlFor="loop-new-form">Form</label>
        <select id="loop-new-form" data-testid="loop-new-form" value={newForm} onChange={(event) => setNewForm(event.target.value)}>
          <option value="cycle">Colour cycle</option>
          <option value="frames">Frames</option>
        </select>
      </div>
      <button
        data-testid="loop-add"
        disabled={!valid}
        onClick={() => {
          props.decide("loop", { loop: id, form: newForm });
          setSelected(id);
          setNewLoop("");
        }}
      >
        Add the Loop {id}
      </button>
      <p className="hint">A Loop and a Look can't share an ID. Renaming or deleting a Loop has no Command yet, so a wrong one waits for undo.</p>
      {current && (
        <>
          <h2>{current.id}</h2>
          <div className="param">
            <label htmlFor="loop-form">Form</label>
            <select id="loop-form" data-testid="loop-form" value={current.form} onChange={(event) => setLoop({ form: event.target.value })}>
              <option value="cycle">Colour cycle</option>
              <option value="frames">Frames</option>
            </select>
          </div>
          <div className="param">
            <label htmlFor="loop-layer">Sits on</label>
            <select id="loop-layer" data-testid="loop-layer" value={current.layer} onChange={(event) => setLoop({ layer: event.target.value })}>
              <option value={PLATE}>the plate</option>
              {[...new Set([...layers, ...(layers.includes(current.layer) || current.layer === PLATE ? [] : [current.layer])])].map((layer) => (
                <option key={layer} value={layer}>
                  Layer {layer}
                </option>
              ))}
            </select>
            <small>The region is cut to a Layer's alpha when the Loop sits on one.</small>
          </div>
          <div className="param">
            <label htmlFor="loop-light">Light</label>
            <NumberField id="loop-light" testid="loop-light" value={current.light ?? ""} placeholder="a light Marker's ID" onCommit={(text) => setLoop({ light: text })} />
            <small>The light Marker that follows this Loop.</small>
          </div>
          <div className="param">
            <label htmlFor="loop-phase">Phase (ticks)</label>
            <NumberField id="loop-phase" testid="loop-phase" value={String(current.phase)} onCommit={(text) => Number.isInteger(Number(text)) && Number(text) >= 0 && setLoop({ phase: Number(text) })} />
          </div>
        </>
      )}
      <h2>Region</h2>
      <div className="tools" role="group" aria-label="Tool">
        {TOOLS.filter((entry) => entry.name !== "eyedrop" && entry.name !== "anchor").map((entry) => (
          <button key={entry.name} data-testid={`tool-${entry.name}`} aria-pressed={tool === entry.name} title={`${entry.label} (${entry.key.toUpperCase()})`} onClick={() => setTool(entry.name)}>
            {entry.label} <kbd>{entry.key.toUpperCase()}</kbd>
          </button>
        ))}
      </div>
      <p className="hint">{active.hint}</p>
      {tool === "flood" && (
        <div className="param">
          <label htmlFor="loop-tolerance">Tolerance</label>
          <input id="loop-tolerance" data-testid="loop-tolerance" type="range" min={0} max={mostTolerance} step={0.01} value={tolerance} onChange={(event) => setTolerance(Number(event.target.value))} />
          <output data-testid="loop-tolerance-value">{tolerance.toFixed(2)}</output>
          <small>How far a pixel's colour may be from the clicked one (OKLab); 0 is exactly equal.</small>
        </div>
      )}
      <div className="param">
        <label htmlFor="loop-radius">Brush size</label>
        <input id="loop-radius" data-testid="loop-radius" type="number" min={MIN_RADIUS} max={MAX_RADIUS} value={radius} onChange={(event) => setRadius(Math.min(MAX_RADIUS, Math.max(MIN_RADIUS, Math.trunc(Number(event.target.value)) || 0)))} />
      </div>
      <div className="param">
        <label htmlFor="loop-opacity">Overlay opacity</label>
        <input id="loop-opacity" data-testid="loop-opacity" type="range" min={0} max={100} value={opacity} onChange={(event) => setOpacity(Number(event.target.value))} />
        <span className="swatch" style={{ background: tintOf(0) }} />
      </div>
      {current && isFrames && (
        <>
          <h2>Frames</h2>
          <div className="tools" role="group" aria-label="Frame source">
            <button data-testid="source-op" aria-pressed={source === "op"} onClick={() => source !== "op" && chooseOp(current.frames?.op ?? "sway")}>
              Op
            </button>
            <button data-testid="source-kit" aria-pressed={source === "kit"} onClick={() => source !== "kit" && setFramesOp({ source: "kit" })}>
              Kit
            </button>
          </div>
          <p className="hint">Edits (frames made by an image model) wait for trial 0184; an Op or a hand-painted kit make the frames for now.</p>
          {source !== "kit" && (
            <>
              <div className="tools" role="group" aria-label="Op">
                {OPS.map((op) => {
                  const blocked = op === "sway" && current.layer === PLATE;
                  return (
                    <button key={op} data-testid={`op-${op}`} aria-pressed={current.frames?.op === op} disabled={blocked} title={blocked ? NO_FILL : op} onClick={() => current.frames?.op !== op && chooseOp(op)}>
                      {op[0].toUpperCase() + op.slice(1)}
                    </button>
                  );
                })}
              </div>
              {current.layer === PLATE && (
                <p className="hint" data-testid="op-no-fill">
                  {NO_FILL}{" "}
                  <button data-testid="open-layers" onClick={() => props.onStage("layers")}>
                    Open the layers screen
                  </button>
                </p>
              )}
              {opName === "sway" && (
                <p className="hint">
                  Pick the Anchor row tool (<kbd>R</kbd>) and click the canvas: that row stays still. Now{" "}
                  <span data-testid="anchor-row">{typeof current.frames?.params?.anchor_row === "number" ? `row ${current.frames.params.anchor_row}` : "the bottom of the region"}</span>.
                  <button data-testid="tool-anchor" aria-pressed={tool === "anchor"} onClick={() => setTool("anchor")}>
                    Anchor row <kbd>R</kbd>
                  </button>
                </p>
              )}
              {opName &&
                OP_SLIDERS[opName].map((slider) => {
                  const given = current.frames?.params?.[slider.key] ?? current.built?.params?.[slider.key];
                  const value = given ?? (opName === "scroll" && slider.key === "dy" ? 0 : slider.fallback);
                  return (
                    <div key={`${current.id}-${opName}-${slider.key}`} className="param">
                      <label htmlFor={`op-${slider.key}`}>{slider.label}</label>
                      <Slider id={`op-${slider.key}`} testid={`op-${slider.key}`} min={slider.min} max={slider.max} value={value} onCommit={(next) => setOpParam(slider.key, next)} />
                    </div>
                  );
                })}
            </>
          )}
          {source === "kit" && (
            <>
              <div className="param">
                <label htmlFor="kit-folder">Kit folder (on this machine)</label>
                <input id="kit-folder" data-testid="kit-folder" type="text" placeholder={`kits/${current.id}`} value={kitFolder} onChange={(event) => setKitFolder(event.target.value)} />
              </div>
              <div className="param">
                <label htmlFor="kit-frames">Frames</label>
                <input id="kit-frames" data-testid="kit-frames" type="number" min={2} max={64} value={kitFrames} onChange={(event) => setKitFrames(event.target.value)} />
              </div>
              <label className="toggle">
                <input type="checkbox" data-testid="kit-force" checked={kitForce} onChange={(event) => setKitForce(event.target.checked)} />
                Write over frames already in the folder
              </label>
              <button
                data-testid="kit-write"
                onClick={() => props.writeKit(current.id, kitFolder.trim() || `kits/${current.id}`, Math.trunc(Number(kitFrames)) || 4, kitForce, (folder) => folder && setKitWritten((now) => ({ ...now, [current.id]: folder })))}
              >
                Write kit
              </button>
              {kitWritten[current.id] && (
                <p className="hint" data-testid="kit-path">
                  Wrote the kit to {kitWritten[current.id]}. Paint over copies of frame_001 onward there, with the palette beside them, then import them.
                </p>
              )}
              <button data-testid="kit-import" disabled={!kitFolder.trim() && !kitWritten[current.id]} onClick={() => importKit()}>
                Import frames
              </button>
              <p className="hint">Imports frame_001 onward from the kit folder. A browser sends one file at a time, so the frames are read from the folder, on this machine.</p>
            </>
          )}
        </>
      )}
      {current && !isFrames && (
        <>
          <h2>Cycle</h2>
          <div className="tools" role="group" aria-label="Cycle mode">
            {(["rotate", "pulse"] as const).map((name) => (
              <button key={name} data-testid={`mode-${name}`} aria-pressed={mode === name} onClick={() => mode !== name && setCycle({ mode: name })}>
                {name === "rotate" ? "Rotate" : "Pulse"}
              </button>
            ))}
          </div>
          <p className="hint">
            {mode === "rotate"
              ? "Each pixel of the region in a listed colour steps to the next colour in the list. At least two colours."
              : "Each pixel of the region moves up its own colour ramp and back. Colours are optional: with some, only pixels of those colours pulse."}
          </p>
          <button data-testid="tool-eyedrop" aria-pressed={tool === "eyedrop"} title="Eyedropper (I)" onClick={() => setTool("eyedrop")}>
            Eyedropper <kbd>I</kbd>
          </button>
          <div className="strip" data-testid="cycle-colours">
            {colours.length === 0 && <span className="hint">No colours yet.</span>}
            {colours.map((colour, index) => (
              <span key={colour} className="chip" data-testid={`cycle-colour-${index}`} title={colour} onMouseEnter={() => setLit(colour)} onMouseLeave={() => setLit(null)}>
                <button className="chip-colour-button" aria-label={`Show the pixels of ${colour}`} onClick={() => setLit(colour)}>
                  <span className="chip-colour" style={{ background: colour }} />
                </button>
                <button aria-label={`Move ${colour} earlier`} disabled={index === 0} onClick={() => reorder(index, -1)}>
                  {"‹"}
                </button>
                <button aria-label={`Move ${colour} later`} disabled={index === colours.length - 1} onClick={() => reorder(index, 1)}>
                  {"›"}
                </button>
                <button aria-label={`Remove ${colour}`} data-testid={`cycle-colour-remove-${index}`} onClick={() => setCycle({ colours: colours.filter((_, at) => at !== index) })}>
                  {"×"}
                </button>
              </span>
            ))}
          </div>
          {hint && (
            <p className="hint" data-testid="loop-hint">
              {hint}
            </p>
          )}
          <div className="swatches" data-testid="palette-swatches">
            {palette.map((colour) => (
              <button key={colour} className="palette-swatch" data-testid={`palette-${colour}`} title={colour} aria-label={`Add ${colour}`} style={{ background: colour }} onClick={() => addColour(colour)} />
            ))}
          </div>
          <div className="param">
            <label htmlFor="loop-steps">Steps (frames)</label>
            <NumberField id="loop-steps" testid="loop-steps" value={cycle?.steps !== undefined ? String(cycle.steps) : ""} placeholder={mode === "rotate" ? "one a colour" : "default"} onCommit={(text) => Number.isInteger(Number(text)) && Number(text) >= 2 && setCycle({ steps: Number(text) })} />
          </div>
          {mode === "pulse" && (
            <>
              <div className="param">
                <label htmlFor="loop-depth">Depth (ramp places)</label>
                <NumberField id="loop-depth" testid="loop-depth" value={cycle?.depth !== undefined ? String(cycle.depth) : ""} placeholder="default" onCommit={(text) => Number.isInteger(Number(text)) && Number(text) >= 1 && setCycle({ depth: Number(text) })} />
              </div>
              <label className="toggle">
                <input type="checkbox" data-testid="loop-emissive" checked={cycle?.emissive !== false} onChange={(event) => setCycle({ emissive: event.target.checked })} />
                Emissive: the pulse lights what is around it
              </label>
              {inline("loop.pulse_spills").map((finding, index) => (
                <p key={index} className="hint" data-testid="loop-finding-loop.pulse_spills">
                  {finding.message}. {finding.owner_action}
                </p>
              ))}
            </>
          )}
        </>
      )}
      {current && (
        <>
          <h2>Timing</h2>
          <div className="tools" role="group" aria-label="Timing">
            <button data-testid="timing-even" aria-pressed={!flickering} onClick={() => flickering && setTiming({ ticks: DEFAULT_EVEN_TICKS })}>
              Ticks a frame
            </button>
            <button data-testid="timing-flicker" aria-pressed={flickering} onClick={() => !flickering && setTiming({ flicker: { seed: 1 } })}>
              Flicker
            </button>
          </div>
          {!flickering ? (
            <>
              <div className="param">
                <label htmlFor="loop-ticks">Ticks a frame (60 a second)</label>
                <NumberField
                  id="loop-ticks"
                  testid="loop-ticks"
                  value={Array.isArray(ticksNow) ? ticksNow.join(", ") : String(ticksNow)}
                  onCommit={(text) => {
                    const ticks = ticksFrom(text);
                    if (ticks !== null) setTiming({ ticks, ...(pingpong ? { pingpong: true } : {}) });
                  }}
                />
                <small>One number, or one a frame, separated by commas.</small>
              </div>
              <label className="toggle">
                <input type="checkbox" data-testid="loop-pingpong" checked={pingpong} onChange={(event) => setTiming({ ticks: ticksNow, pingpong: event.target.checked })} />
                Ping-pong: play back and forth, so the wrap repeats no frame
              </label>
            </>
          ) : (
            <>
              <div className="param">
                <label htmlFor="loop-seed">Seed</label>
                <NumberField id="loop-seed" testid="loop-seed" value={String(flickerSeed)} onCommit={(text) => Number.isInteger(Number(text)) && Number(text) >= 0 && sendFlicker({ seed: Number(text) })} />
                <button data-testid="loop-reroll" onClick={() => sendFlicker({ seed: Math.floor(Math.random() * 1_000_000) })}>
                  Reroll
                </button>
              </div>
              {(
                [
                  ["mean", "Mean hold (ticks)"],
                  ["spread", "Spread (0 to 1)"],
                  ["length", "Length (ticks)"],
                ] as const
              ).map(([name, label]) => (
                <div key={name} className="param">
                  <label htmlFor={`loop-flicker-${name}`}>{label}</label>
                  <NumberField id={`loop-flicker-${name}`} testid={`loop-flicker-${name}`} value={flicker[name]} placeholder="default" onCommit={(text) => Number.isFinite(Number(text)) && sendFlicker({ [name]: text })} />
                </div>
              ))}
            </>
          )}
          {current.built?.box && playingHere && (
            <>
              <h2>Frames of {current.id}</h2>
              <p className="hint">Frame 0 is the room's. Click a frame to see it alone, with the one before it faint; click it again to put the room back.</p>
              <div className="frame-strip" data-testid="frame-strip">
                {Array.from({ length: current.built.frames }, (_, n) => {
                  const badges = frameFindings(n);
                  const ticks = Array.isArray(ticksNow) ? ticksNow[n] : ticksNow;
                  return (
                    <div key={n} className="frame-cell" data-testid={`frame-${n}`} data-selected={inspect === n}>
                      <button className="frame-thumb" aria-pressed={inspect === n} aria-label={`Show frame ${n}`} data-testid={`frame-show-${n}`} onClick={() => setInspect(inspect === n ? null : n)}>
                        <Thumbnail loop={playingHere} frame={n} />
                      </button>
                      <span>{n === 0 ? "0 (the room's)" : n}</span>
                      <NumberField
                        id={`frame-ticks-${n}`}
                        testid={`frame-ticks-${n}`}
                        value={String(ticks ?? DEFAULT_EVEN_TICKS)}
                        onCommit={(text) => {
                          const one = Number(text);
                          if (!Number.isInteger(one) || one < 1) return;
                          const all = Array.from({ length: current.built!.frames }, (_, at) => (Array.isArray(ticksNow) ? ticksNow[at] : ticksNow) as number);
                          all[n] = one;
                          setTiming({ ticks: all, ...(pingpong ? { pingpong: true } : {}) });
                        }}
                      />
                      {badges.map((finding, at) => (
                        <span key={at} className="badge" data-severity={finding.severity} data-testid={`frame-badge-${n}-${finding.code}`} title={finding.message}>
                          {finding.code.replace("loop.", "")}
                        </span>
                      ))}
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </>
      )}
      <h2>Preview</h2>
      <div className="tools" role="group" aria-label="Preview">
        <button data-testid="loop-play" aria-pressed={running} onClick={playOrPause} title="Play or pause (P)">
          {running ? "Pause" : "Play"} <kbd>P</kbd>
        </button>
        <button data-testid="loop-step" onClick={stepOne} title="Step one tick (N)">
          Step a tick <kbd>N</kbd>
        </button>
        <button data-testid="loop-solo" aria-pressed={solo} onClick={() => setSolo((now) => !now)} title="Play only this Loop (O)">
          Solo <kbd>O</kbd>
        </button>
      </div>
      <p className="hint">The whole room at game resolution, in whole 60 Hz ticks by the Loops' sequence. Paused shows frame 0, which is the room.</p>
      {mine.filter((finding) => finding.code !== "loop.pulse_spills" && finding.code !== "loop.texture").length > 0 && (
        <>
          <h2>Findings of {current?.id}</h2>
          <ul className="findings" data-testid="loop-findings">
            {mine
              .filter((finding) => finding.code !== "loop.pulse_spills" && finding.code !== "loop.texture")
              .map((finding, index) => {
                const fix = fixDecision(finding);
                return (
                  <li key={`${finding.code}-${index}`} data-severity={finding.severity} data-testid={`loop-finding-${finding.code}`}>
                    <p>{finding.message}</p>
                    {finding.owner_action && <p className="remedy">{finding.owner_action}</p>}
                    {finding.code === "loop.no_fill" && (
                      <button data-testid="loop-finding-open-layers" onClick={() => props.onStage("layers")}>
                        Open the layers screen
                      </button>
                    )}
                    {fix && (
                      <button data-testid={`loop-fix-${finding.code}`} onClick={() => props.decide(fix.name, fix.data)}>
                        {finding.code === "loop.seam" ? "Ping-pong it" : "Apply the fix"}
                      </button>
                    )}
                  </li>
                );
              })}
          </ul>
        </>
      )}
      <label className="toggle">
        <input type="checkbox" data-testid="loop-rebuild" checked={rebuild} onChange={(event) => onRebuild(event.target.checked)} />
        Rebuild the Loops after each edit
      </label>
      <p className="hint">
        <kbd>[</kbd> <kbd>]</kbd> change the brush size, <kbd>Z</kbd> zooms, hold <kbd>Space</kbd> and drag to pan, <kbd>Enter</kbd> closes a polygon,{" "}
        <kbd>Ctrl+Z</kbd> undoes.
      </p>
    </fieldset>
  );
}
