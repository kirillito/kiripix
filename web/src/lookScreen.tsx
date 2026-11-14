// The room's looks screen (ADR 0009, spec §6.1 and §11): the Looks of the room, the room and the Look toggled at integer zoom, a
// region by polygon, brush or `difference`, `look.drift`'s boxes, and the Look's own `solid`.
//
// The region tools are `MaskTool` (ADR 0008) with its Mask names turned into targets: "region" is what `brush` and `polygon`
// Decisions paint, "solid" what the `solid` Decision paints. Each gesture is one `decide`, followed by a `run` of the Stage while
// "rebuild" is on, and a hover asks nothing. `difference` is the one tool with a staged step: a dragged box is drawn and
// previewed, and the Decision is recorded by the button.

import { useEffect, useRef, useState, type RefObject } from "react";
import { fileUrl, type StageDescription, type ShowData, type StageDetail } from "./api";
import { LookTool, type Box, type DriftBox, type LookView, type Piece } from "./lookTool";
import { MAX_RADIUS, MaskTool, MIN_RADIUS, tintOf } from "./maskTool";
import { isTyping, type PixelCanvas } from "./pixelCanvas";
import { loadMask, type MaskPixels } from "./walkTest";

export const LOOKS_STAGE = "looks";
export const LOOKS_DECISION = "difference"; // what tells the looks Stage's screen from another's
const REGION = "region";
const SOLID = "solid";
const DEFAULT_TOLERANCE = 4; // the Stage's own default, in ΔE (spec §6.1)

type Tool = "brush" | "erase" | "polygon" | "polygon-erase" | "difference";
const TOOLS: { name: Tool; key: string; label: string; hint: string }[] = [
  { name: "brush", key: "b", label: "Brush", hint: "Drag to add to the Look's region." },
  { name: "erase", key: "e", label: "Erase", hint: "Drag to take from the Look's region." },
  { name: "polygon", key: "g", label: "Polygon", hint: "Click the corners; click the first point or press Enter to close and fill. Backspace removes the last point, Esc drops it." },
  { name: "polygon-erase", key: "x", label: "Erase polygon", hint: "Click the corners; click the first point or press Enter to close and clear." },
  { name: "difference", key: "d", label: "Difference", hint: "Drag a box round what the edit changed, set the tolerance, then record it: the region becomes the pixels that differ." },
];

interface BuiltLook {
  id: string;
  condition: string | null;
  edit: string;
  box: [number, number, number, number] | null;
  plate: string | null;
  layers: { id: string; file: string }[];
  solid: string | null;
  changed: number;
  drift: (DriftBox & { pixels: number })[];
}

interface Journal {
  name: string;
  data: Record<string, unknown>;
}

// The Looks any Decision names, with the edit picked and the Condition given (the latest of each counts).
export interface LookEntry {
  id: string;
  condition: string | null;
  edit: string | null;
  built: BuiltLook | null;
}

export function looksOf(decisions: Journal[], built: BuiltLook[]): LookEntry[] {
  const ids = new Set<string>(built.map((look) => look.id));
  for (const decision of decisions) if (typeof decision.data.look === "string") ids.add(decision.data.look);
  return [...ids].sort().map((id) => {
    const own = decisions.filter((decision) => decision.data.look === id);
    const named = own.filter((decision) => decision.name === "look").at(-1);
    const picked = own.filter((decision) => decision.name === "pick").at(-1);
    return {
      id,
      condition: typeof named?.data.condition === "string" ? named.data.condition : null,
      edit: typeof picked?.data.variant === "string" ? picked.data.variant : null,
      built: built.find((look) => look.id === id) ?? null,
    };
  });
}

// The room as the game shows it now: the `palette` Stage's picture. The screen draws the Look over it.
export function roomImageOf(show: ShowData): string | null {
  return show.stages.find((entry) => entry.stage === "palette")?.image ?? null;
}

async function readPixels(url: string): Promise<ImageData> {
  const image = new Image();
  image.src = url;
  await image.decode();
  const canvas = document.createElement("canvas");
  canvas.width = image.naturalWidth;
  canvas.height = image.naturalHeight;
  const context = canvas.getContext("2d", { willReadFrequently: true })!;
  context.drawImage(image, 0, 0);
  return context.getImageData(0, 0, canvas.width, canvas.height);
}

async function pieceOf(url: string, x: number, y: number): Promise<{ piece: Piece; alpha: Uint8ClampedArray }> {
  const image = new Image();
  image.src = url;
  await image.decode();
  const canvas = document.createElement("canvas");
  canvas.width = image.naturalWidth;
  canvas.height = image.naturalHeight;
  const context = canvas.getContext("2d", { willReadFrequently: true })!;
  context.drawImage(image, 0, 0);
  return { piece: { image: canvas, x, y }, alpha: context.getImageData(0, 0, canvas.width, canvas.height).data };
}

function oklab(r: number, g: number, b: number): [number, number, number] {
  const lin = (value: number) => {
    const c = value / 255;
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  const [lr, lg, lb] = [lin(r), lin(g), lin(b)];
  const l = Math.cbrt(0.4122214708 * lr + 0.5363325363 * lg + 0.0514459929 * lb);
  const m = Math.cbrt(0.2119034982 * lr + 0.6806995451 * lg + 0.1073969566 * lb);
  const s = Math.cbrt(0.0883024619 * lr + 0.2817188376 * lg + 0.6299787005 * lb);
  return [0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s, 1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s, 0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s];
}

// A rough preview of a `difference`: the edit scaled to the room's size against the mapped room, on the 3x3 mean, in ΔE. The
// Stage measures the fitted images before the palette and drops specks, so its region differs; this only shows where to look.
function previewOf(room: ImageData, edit: HTMLImageElement, box: Box, tolerance: number): HTMLCanvasElement {
  const { width, height } = room;
  const scaled = document.createElement("canvas");
  scaled.width = width;
  scaled.height = height;
  const own = scaled.getContext("2d", { willReadFrequently: true })!;
  own.imageSmoothingQuality = "high";
  own.drawImage(edit, 0, 0, width, height);
  const other = own.getImageData(0, 0, width, height).data;
  const mean = (data: Uint8ClampedArray | Uint8Array, x: number, y: number): [number, number, number] => {
    let r = 0;
    let g = 0;
    let b = 0;
    let n = 0;
    for (let dy = -1; dy <= 1; dy++) {
      for (let dx = -1; dx <= 1; dx++) {
        const px = x + dx;
        const py = y + dy;
        if (px < 0 || py < 0 || px >= width || py >= height) continue;
        const at = (py * width + px) * 4;
        r += data[at];
        g += data[at + 1];
        b += data[at + 2];
        n++;
      }
    }
    return [r / n, g / n, b / n];
  };
  const out = document.createElement("canvas");
  out.width = width;
  out.height = height;
  const paint = out.getContext("2d")!;
  paint.fillStyle = "#ffe14d";
  for (let y = Math.max(0, box.y0); y <= Math.min(height - 1, box.y1); y++) {
    for (let x = Math.max(0, box.x0); x <= Math.min(width - 1, box.x1); x++) {
      const a = oklab(...mean(room.data, x, y));
      const b = oklab(...mean(other, x, y));
      if (100 * Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]) >= tolerance) paint.fillRect(x, y, 1, 1);
    }
  }
  return out;
}

async function loadImage(url: string): Promise<HTMLImageElement> {
  const image = new Image();
  image.src = url;
  await image.decode();
  return image;
}

export function LooksPanel(props: {
  canvas: RefObject<PixelCanvas | null>;
  asset: string;
  show: ShowData;
  detail: StageDetail;
  decisions: StageDescription["decisions"];
  imageVersion: number;
  refreshes: number;
  disabled: boolean;
  rebuild: boolean;
  onRebuild: (rebuild: boolean) => void;
  decide: (decision: string, data: Record<string, unknown>, settled?: () => void) => void;
  importEdit: (file: File, look: string) => void;
}) {
  const { canvas, show, detail, imageVersion, refreshes, disabled, rebuild, onRebuild } = props;
  const [built, setBuilt] = useState<BuiltLook[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [newLook, setNewLook] = useState("");
  const [condition, setCondition] = useState("");
  const [tool, setTool] = useState<Tool>("polygon");
  const [target, setTarget] = useState(REGION);
  const [view, setView] = useState<LookView>("look");
  const [radius, setRadius] = useState(2);
  const [opacity, setOpacity] = useState(40);
  const [tolerance, setTolerance] = useState(DEFAULT_TOLERANCE);
  const [staged, setStaged] = useState<Box | null>(null);
  const [over, setOver] = useState(false);
  const [room, setRoom] = useState<ImageData | null>(null);

  const entries = looksOf(detail.decisions, built);
  const current = entries.find((entry) => entry.id === selected) ?? entries[0] ?? null;
  const latest = useRef({ ...props, current, newLook, entries });
  latest.current = { ...props, current, newLook, entries };
  const painter = useRef<MaskTool | null>(null);
  const looker = useRef<LookTool | null>(null);

  const roomFile = roomImageOf(show);
  const folder = roomFile ? roomFile.slice(0, roomFile.indexOf("/work/")) : "";
  const builtFile = detail.outputs.find((path) => path.endsWith("/looks.json"));
  const stageFolder = builtFile ? builtFile.slice(0, builtFile.lastIndexOf("/")) : "";

  // The tools, made once; their gestures read the latest props through the ref.
  useEffect(() => {
    const painting = new MaskTool(
      {
        stroke(on, erase, size, points) {
          const { decide, current: here } = latest.current;
          if (!here) return;
          const done = painter.current?.addMark({ kind: "stroke", mask: on, erase, radius: size, points });
          decide(on === SOLID ? "solid" : "brush", { look: here.id, erase, radius: size, points }, done);
        },
        polygon(on, erase, points) {
          const { decide, current: here } = latest.current;
          if (!here) return;
          const done = painter.current?.addMark({ kind: "polygon", mask: on, erase, points });
          decide(on === SOLID ? "solid" : "polygon", { look: here.id, erase, points }, done);
        },
        point() {},
        async preview() {
          return null;
        },
      },
      () => canvas.current?.redraw(),
    );
    const looking = new LookTool(
      () => canvas.current?.redraw(),
      (box) => setStaged(box),
    );
    painter.current = painting;
    looker.current = looking;
    canvas.current?.setTools([looking, painting]); // the Look is drawn first, the region tint over it
    return () => {
      painting.destroy();
      canvas.current?.setTools([]);
    };
  }, [canvas]);

  useEffect(() => {
    const painting = painter.current;
    const looking = looker.current;
    if (!painting || !looking) return;
    const boxing = tool === "difference";
    looking.boxing = boxing;
    if (!boxing) looking.clearBox();
    painting.setTool(boxing ? "flood" : tool);
    painting.mask = boxing ? "" : target;
    painting.radius = radius;
    painting.opacity = opacity / 100;
    looking.view = view;
    canvas.current?.redraw();
  }, [canvas, tool, target, radius, opacity, view]);

  // The built looks.json, read again at each refresh: a drift box can change with no picture changing.
  useEffect(() => {
    if (!builtFile) {
      setBuilt([]);
      return;
    }
    let live = true;
    void fetch(fileUrl(builtFile, refreshes))
      .then((response) => response.json() as Promise<{ looks: BuiltLook[] }>)
      .then((document) => live && setBuilt(document.looks))
      .catch(() => undefined); // Rebuilt while it was read; the next refresh reads it again.
    return () => {
      live = false;
    };
  }, [builtFile, refreshes]);

  // The room's pixels, for the difference preview.
  useEffect(() => {
    if (!roomFile) return;
    let live = true;
    void readPixels(fileUrl(roomFile, imageVersion))
      .then((pixels) => live && setRoom(pixels))
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [roomFile, imageVersion]);

  // The selected Look's pieces, its region (from their alpha) and its `solid`, and the drift of them all.
  const shown = JSON.stringify({ look: current?.built ?? null, base: folder });
  useEffect(() => {
    let live = true;
    const read = JSON.parse(shown) as { look: BuiltLook | null; base: string };
    const painting = painter.current;
    const looking = looker.current;
    if (!painting || !looking || !room) return;
    const { width, height } = room;
    looking.drift = built.flatMap((look) => look.drift);
    void (async () => {
      const files = read.look ? [...(read.look.plate ? [read.look.plate] : []), ...read.look.layers.map((layer) => layer.file)] : [];
      const [x, y] = read.look?.box ?? [0, 0];
      const parts = await Promise.all(files.map((file) => pieceOf(fileUrl(`${stageFolder}/${file}`, imageVersion), x, y)));
      const region = new Uint8Array(width * height);
      for (const { piece, alpha } of parts) {
        for (let py = 0; py < piece.image.height; py++) {
          for (let px = 0; px < piece.image.width; px++) {
            if (alpha[(py * piece.image.width + px) * 4 + 3] > 0) region[(piece.y + py) * width + piece.x + px] = 1;
          }
        }
      }
      // A Look with no `solid` of its own uses the room's.
      const solidFile = read.look?.solid ? `${stageFolder}/${read.look.solid}` : `${read.base}/work/masks/solid.png`;
      const none: MaskPixels = { width, height, set: new Uint8Array(width * height) };
      const solid = await loadMask(fileUrl(solidFile, imageVersion)).catch(() => none);
      if (!live) return;
      looking.pieces = parts.map((part) => part.piece);
      painting.setMasks([
        { name: REGION, pixels: { width, height, set: region } },
        { name: SOLID, pixels: solid },
      ]);
      canvas.current?.redraw();
    })().catch(() => undefined);
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shown, room, imageVersion, built, stageFolder]);

  // The staged box's rough preview.
  useEffect(() => {
    const looking = looker.current;
    if (!looking) return;
    if (!staged || !room || !current?.edit) {
      looking.preview = null;
      canvas.current?.redraw();
      return;
    }
    let live = true;
    void loadImage(fileUrl(`${folder}/src/looks/${current.id}/${current.edit}.png`, 0))
      .then((edit) => {
        if (!live) return;
        looking.preview = previewOf(room, edit, staged, tolerance);
        canvas.current?.redraw();
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [canvas, staged, tolerance, room, current?.id, current?.edit, folder]);

  useEffect(() => setCondition(current?.condition ?? ""), [current?.id, current?.condition]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (isTyping(event.target)) return;
      if (event.ctrlKey || event.metaKey || event.altKey) return;
      const key = event.key.toLowerCase();
      const chosen = TOOLS.find((entry) => entry.key === key);
      if (chosen) {
        setTool(chosen.name);
        if (chosen.name === "difference") setTarget(REGION);
      } else if (key === "r") setTarget(REGION);
      else if (key === "s") setTarget(SOLID);
      else if (key === "v") setView((now) => (now === "look" ? "room" : "look"));
      else if (/^[1-9]$/.test(key)) {
        const one = latest.current.entries[Number(key) - 1];
        if (one) setSelected(one.id);
      } else if (event.key === "[") setRadius((size) => Math.max(MIN_RADIUS, size - 1));
      else if (event.key === "]") setRadius((size) => Math.min(MAX_RADIUS, size + 1));
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  // A PNG dropped on the canvas is an edit of the Look being named, or of the selected one.
  useEffect(() => {
    const host = canvas.current?.element.parentElement;
    if (!host) return;
    const allow = (event: DragEvent) => {
      if (!event.dataTransfer?.types.includes("Files")) return;
      event.preventDefault();
      setOver(true);
    };
    const leave = () => setOver(false);
    const drop = (event: DragEvent) => {
      event.preventDefault();
      setOver(false);
      const file = [...(event.dataTransfer?.files ?? [])].find((entry) => /\.(png|jpe?g)$/i.test(entry.name));
      const { current: here, newLook: typed, disabled: busy } = latest.current;
      const look = typed.trim() || here?.id;
      if (file && look && !busy) {
        latest.current.importEdit(file, look);
        setSelected(look);
        setNewLook("");
            if (document.activeElement instanceof HTMLElement) document.activeElement.blur(); // the tool keys work again
      }
    };
    host.addEventListener("dragover", allow);
    host.addEventListener("dragleave", leave);
    host.addEventListener("drop", drop);
    return () => {
      host.removeEventListener("dragover", allow);
      host.removeEventListener("dragleave", leave);
      host.removeEventListener("drop", drop);
    };
  }, [canvas]);

  const input = useRef<HTMLInputElement>(null);
  const id = newLook.trim();
  const valid = /^[a-z0-9_]+(\.[a-z0-9_]+)*$/.test(id);
  const active = TOOLS.find((entry) => entry.name === tool)!;
  const drifting = built.filter((look) => look.drift.length > 0);

  function record() {
    if (!staged || !current) return;
    const { x0, y0, x1, y1 } = staged;
    props.decide("difference", { look: current.id, x0, y0, x1, y1, tolerance }, () => {
      looker.current?.clearBox();
      setStaged(null);
    });
  }

  return (
    <fieldset disabled={disabled} className={over ? "mask-form over" : "mask-form"} data-testid="look-panel">
      <h2>Looks</h2>
      {entries.length === 0 ? (
        <p className="hint">This room has no Looks. Name one and import an edit of the room's Source below.</p>
      ) : (
        <ul className="looks" data-testid="look-list">
          {entries.map((entry, index) => (
            <li key={entry.id}>
              <button data-testid={`look-${entry.id}`} aria-pressed={current?.id === entry.id} onClick={() => setSelected(entry.id)}>
                {index < 9 && <kbd>{index + 1}</kbd>} {entry.id}
                {entry.condition && <span className="condition"> when {entry.condition}</span>}
              </button>
              <small>
                {entry.built === null ? "not built yet" : entry.built.box === null ? "no region" : `${entry.built.changed} px change`}
                {entry.built && entry.built.drift.length > 0 && `, ${entry.built.drift.length} redrawn outside`}
              </small>
            </li>
          ))}
        </ul>
      )}
      <div className="param">
        <label htmlFor="look-new">New Look</label>
        <input id="look-new" data-testid="look-new" type="text" placeholder="circuit_hall_off" value={newLook} onChange={(event) => setNewLook(event.target.value)} />
      </div>
      {id !== "" && !valid && <p className="reason">A Look ID is lower-case letters, digits and underscores, with dots between parts.</p>}
      <button
        data-testid="look-import"
        disabled={!(current || valid) || (id !== "" && !valid)}
        onClick={() => input.current?.click()}
      >
        Import an edit of {id !== "" ? id : (current?.id ?? "a Look")}
      </button>
      <input
        ref={input}
        type="file"
        accept="image/png,image/jpeg"
        hidden
        data-testid="look-import-input"
        onChange={(event) => {
          const file = event.target.files?.[0];
          const look = id || current?.id;
          if (file && look) {
            props.importEdit(file, look);
            setSelected(look);
            setNewLook("");
            if (document.activeElement instanceof HTMLElement) document.activeElement.blur(); // the tool keys work again
          }
          event.target.value = "";
        }}
      />
      <p className="hint">Or drop a PNG on the canvas. The edit is made from the room's Source, and is picked as the Look's edit at once.</p>
      {current && (
        <>
          <div className="param">
            <label htmlFor="look-condition">Condition of {current.id}</label>
            <input id="look-condition" data-testid="look-condition" type="text" placeholder="circuit.hall:off" value={condition} onChange={(event) => setCondition(event.target.value)} />
            <small>The label the game shows this Look under. Kiripix doesn't read it.</small>
          </div>
          <button
            data-testid="look-condition-set"
            disabled={condition.trim() === "" || condition.trim() === (current.condition ?? "") || current.edit === null}
            onClick={() => props.decide("look", { look: current.id, condition: condition.trim() })}
          >
            Set the Condition
          </button>
        </>
      )}
      <h2>View</h2>
      <div className="tools" role="group" aria-label="View">
        <button data-testid="view-room" aria-pressed={view === "room"} onClick={() => setView("room")}>
          Room
        </button>
        <button data-testid="view-look" aria-pressed={view === "look"} onClick={() => setView("look")}>
          Look
        </button>
      </div>
      <p className="hint">
        <kbd>V</kbd> toggles. Only the Look's region differs between the two.
      </p>
      <h2>Region</h2>
      <div className="tools" role="group" aria-label="Tool">
        {TOOLS.map((entry) => (
          <button key={entry.name} data-testid={`tool-${entry.name}`} aria-pressed={tool === entry.name} title={`${entry.label} (${entry.key.toUpperCase()})`} onClick={() => {
            setTool(entry.name);
            if (entry.name === "difference") setTarget(REGION);
          }}>
            {entry.label} <kbd>{entry.key.toUpperCase()}</kbd>
          </button>
        ))}
      </div>
      <p className="hint">{active.hint}</p>
      <div className="tools" role="group" aria-label="Paint">
        {[
          [REGION, "Region", "r"],
          [SOLID, "Solid", "s"],
        ].map(([name, label, letter], index) => (
          <button key={name} data-testid={`target-${name}`} aria-pressed={target === name} disabled={tool === "difference" && name === SOLID} onClick={() => setTarget(name)}>
            <span className="swatch" style={{ background: tintOf(index) }} /> {label} <kbd>{letter.toUpperCase()}</kbd>
          </button>
        ))}
      </div>
      {tool === "difference" && (
        <>
          <div className="param">
            <label htmlFor="look-tolerance">Tolerance</label>
            <input id="look-tolerance" data-testid="look-tolerance" type="range" min={0} max={20} step={0.5} value={tolerance} onChange={(event) => setTolerance(Number(event.target.value))} />
            <output data-testid="look-tolerance-value">{tolerance.toFixed(1)}</output>
            <small>ΔE: how much a pixel must differ from the room. The yellow preview is rough; the Stage measures before the palette.</small>
          </div>
          <button data-testid="difference-record" disabled={!staged || !current || current.edit === null} onClick={record}>
            Record the difference
          </button>
        </>
      )}
      <div className="param">
        <label htmlFor="look-radius">Brush size</label>
        <input id="look-radius" data-testid="look-radius" type="number" min={MIN_RADIUS} max={MAX_RADIUS} value={radius} onChange={(event) => setRadius(Math.min(MAX_RADIUS, Math.max(MIN_RADIUS, Math.trunc(Number(event.target.value)) || 0)))} />
      </div>
      <div className="param">
        <label htmlFor="look-opacity">Overlay opacity</label>
        <input id="look-opacity" data-testid="look-opacity" type="range" min={0} max={100} value={opacity} onChange={(event) => setOpacity(Number(event.target.value))} />
      </div>
      <label className="toggle">
        <input type="checkbox" data-testid="look-rebuild" checked={rebuild} onChange={(event) => onRebuild(event.target.checked)} />
        Rebuild the Looks after each edit
      </label>
      {drifting.length > 0 && (
        <p className="hint" data-testid="drift-hint">
          The edit redrew pixels outside the region of {drifting.map((look) => look.id).join(", ")}: the red dashed boxes. Click the finding to go to
          the largest.
        </p>
      )}
      <p className="hint">
        <kbd>[</kbd> <kbd>]</kbd> change the brush size, <kbd>Z</kbd> zooms, hold <kbd>Space</kbd> and drag to pan, <kbd>Enter</kbd> closes a polygon,{" "}
        <kbd>Ctrl+Z</kbd> undoes.
      </p>
    </fieldset>
  );
}
