// The room's masks screen (spec §11): brush, erase, flood and click-to-segment on the Plate, with the built Masks tinted over
// it. Every gesture records one `decide` (or `mask-import`), followed by a `run` of the Stage while "rebuild" is on, and a
// hover only asks the `segment-preview` Probe, which records nothing.

import { useEffect, useRef, useState, type RefObject } from "react";
import { call, fileUrl, type Envelope, type StageDescription, type StageDetail } from "./api";
import { MAX_RADIUS, MaskTool, MIN_RADIUS, tintOf, type MaskToolName, type PreviewRuns } from "./maskTool";
import { isTyping, type CanvasPixel, type PixelCanvas } from "./pixelCanvas";
import { loadMask } from "./walkTest";

export const MASKS_STAGE = "masks";
const PREVIEW_PROBE = "segment-preview";
// Flood's tolerance (D6 of ticket 0037): the range comes from `describe`; 0.04 is the UI's starting guess.
const TOLERANCE_DEFAULT = 0.04;
const TOLERANCE_RANGE = { minimum: 0, maximum: 0.2 };

const TOOLS: { name: MaskToolName; key: string; label: string; hint: string }[] = [
  { name: "brush", key: "b", label: "Brush", hint: "Drag to paint the Mask." },
  { name: "erase", key: "e", label: "Erase", hint: "Drag to clear the Mask." },
  {
    name: "polygon",
    key: "g",
    label: "Polygon",
    hint: "Click the corners; click the first point or press Enter to close and fill. Backspace removes the last point, Esc drops it.",
  },
  {
    name: "polygon-erase",
    key: "x",
    label: "Erase polygon",
    hint: "Click the corners; click the first point or press Enter to close and clear. Backspace removes the last point, Esc drops it.",
  },
  { name: "flood", key: "f", label: "Flood", hint: "Click to fill the region of one colour on the Plate." },
  {
    name: "click",
    key: "c",
    label: "Click to segment",
    hint: "Click an object to add it; Shift-click an object to take it away. Hover shows what a click would do.",
  },
];
const SIDES = ["top", "right", "bottom", "left"] as const;
const TOOL_KEYS = new Set(TOOLS.map((tool) => tool.key));

// The painted Masks of the built Stage, from its output files: `solid.png` is the Mask `solid`.
function maskFiles(detail: StageDetail): { name: string; file: string }[] {
  return detail.outputs
    .filter((path) => path.endsWith(".png"))
    .map((file) => ({ name: file.slice(file.lastIndexOf("/") + 1, -".png".length), file }));
}

// Each Mask gets the first letter of its name that no tool or earlier Mask has taken.
export function maskKeys(names: string[]): Record<string, string> {
  const taken = new Set(TOOL_KEYS);
  const keys: Record<string, string> = {};
  for (const name of names) {
    const letter = [...name.toLowerCase()].find((candidate) => /[a-y]/.test(candidate) && !taken.has(candidate));
    if (letter) {
      taken.add(letter);
      keys[letter] = name;
    }
  }
  return keys;
}

export function MasksPanel(props: {
  canvas: RefObject<PixelCanvas | null>;
  asset: string;
  detail: StageDetail;
  decisions: StageDescription["decisions"];
  imageVersion: number;
  disabled: boolean;
  rebuild: boolean;
  onRebuild: (rebuild: boolean) => void;
  decide: (decision: string, data: Record<string, unknown>, settled?: () => void) => void;
  importPng: (file: File) => void;
}) {
  const { canvas, asset, detail, imageVersion, disabled, rebuild, onRebuild } = props;
  const [tool, setTool] = useState<MaskToolName>("brush");
  const [mask, setMask] = useState("solid");
  const [radius, setRadius] = useState(2);
  const [opacity, setOpacity] = useState(50);
  const [unavailable, setUnavailable] = useState<string | null>(null);
  const [over, setOver] = useState(false);
  const [sides, setSides] = useState<string[]>([...SIDES]);
  const hasBorder = props.decisions.some((entry) => entry.name === "border");
  const range = props.decisions.find((entry) => entry.name === "flood")?.entry_schema?.properties?.tolerance;
  const lowest = range?.minimum ?? TOLERANCE_RANGE.minimum;
  const highest = range?.maximum ?? TOLERANCE_RANGE.maximum;
  const [tolerance, setTolerance] = useState(TOLERANCE_DEFAULT);
  const toleranceNow = Math.min(highest, Math.max(lowest, tolerance));
  const files = maskFiles(detail);
  const names = files.map((entry) => entry.name);
  const shown = JSON.stringify(files);

  // The tool's gestures read the latest props through a ref, so the tool is made once.
  const latest = useRef({ ...props, mask, names, tolerance: toleranceNow });
  latest.current = { ...props, mask, names, tolerance: toleranceNow };
  const painter = useRef<MaskTool | null>(null);

  useEffect(() => {
    const painting = new MaskTool(
      {
        stroke(on, erase, size, points) {
          const { decide } = latest.current;
          decide("brush", { mask: on, erase, radius: size, points }, painter.current?.addMark({ kind: "stroke", mask: on, erase, radius: size, points }));
        },
        polygon(on, erase, points) {
          const { decide } = latest.current;
          decide("polygon", { mask: on, erase, points }, painter.current?.addMark({ kind: "polygon", mask: on, erase, points }));
        },
        point(kind, on, pixel: CanvasPixel, positive) {
          const { decide, tolerance: within } = latest.current;
          if (kind === "flood") {
            decide("flood", { x: pixel.x, y: pixel.y, mask: on, tolerance: within }, painter.current?.addMark({ kind: "point", x: pixel.x, y: pixel.y, positive: true }));
          } else {
            decide("click", { x: pixel.x, y: pixel.y, mask: on, positive }, painter.current?.addMark({ kind: "point", x: pixel.x, y: pixel.y, positive }));
          }
        },
        async preview(pixel): Promise<PreviewRuns | null> {
          const { asset: id } = latest.current;
          // A Shift-click is segmented like a click: the Probe is asked for the click alone, and the tool tints the part
          // of the segment that is in the Mask.
          const here = `${pixel.x},${pixel.y}`;
          try {
            const result = (await call("probe", { name: PREVIEW_PROBE, asset: id, args: [here] })) as Envelope<{
              result: PreviewRuns;
            }>;
            setUnavailable(result.ok ? null : (result.findings[0]?.message ?? "No preview."));
            return result.ok && result.data ? result.data.result : null;
          } catch {
            return null; // The connection banner says so.
          }
        },
      },
      () => canvas.current?.redraw(),
    );
    painter.current = painting;
    canvas.current?.setTools([painting]);
    return () => {
      painting.destroy();
      canvas.current?.setTools([]);
    };
  }, [canvas]);

  useEffect(() => {
    const painting = painter.current;
    if (!painting) return;
    painting.setTool(tool);
    painting.mask = mask;
    painting.radius = radius;
    painting.opacity = opacity / 100;
    canvas.current?.redraw();
  }, [canvas, tool, mask, radius, opacity]);

  // The Masks as built, tinted over the Plate; a refresh brings the new ones.
  useEffect(() => {
    let current = true;
    const read = JSON.parse(shown) as { name: string; file: string }[];
    void Promise.all(read.map(async (entry) => ({ name: entry.name, pixels: await loadMask(fileUrl(entry.file, imageVersion)) })))
      .then((loaded) => {
        if (!current) return;
        painter.current?.setMasks(loaded);
        canvas.current?.redraw();
      })
      .catch(() => undefined); // Rebuilt while it was read; the next refresh reads it again.
    return () => {
      current = false;
    };
  }, [canvas, shown, imageVersion]);

  useEffect(() => {
    if (names.length > 0 && !names.includes(mask)) setMask(names[0]);
  }, [names, mask]);

  const keys = maskKeys(names);
  const keyed = useRef(keys);
  keyed.current = keys;
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (isTyping(event.target)) return;
      if (event.ctrlKey || event.metaKey || event.altKey) return;
      const key = event.key.toLowerCase();
      const chosen = TOOLS.find((entry) => entry.key === key);
      if (chosen) setTool(chosen.name);
      else if (keyed.current[key]) setMask(keyed.current[key]);
      else if (event.key === "[") setRadius((size) => Math.max(MIN_RADIUS, size - 1));
      else if (event.key === "]") setRadius((size) => Math.min(MAX_RADIUS, size + 1));
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  // A painted image dropped on the canvas is imported.
  const importPng = props.importPng;
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
      const file = [...(event.dataTransfer?.files ?? [])].find((entry) => /\.png$/i.test(entry.name));
      if (file && !latest.current.disabled) importPng(file);
    };
    host.addEventListener("dragover", allow);
    host.addEventListener("dragleave", leave);
    host.addEventListener("drop", drop);
    return () => {
      host.removeEventListener("dragover", allow);
      host.removeEventListener("dragleave", leave);
      host.removeEventListener("drop", drop);
    };
  }, [canvas, importPng]);

  const input = useRef<HTMLInputElement>(null);
  const active = TOOLS.find((entry) => entry.name === tool)!;

  return (
    <fieldset disabled={disabled} className={over ? "mask-form over" : "mask-form"} data-testid="mask-panel">
      <h2>Tool</h2>
      <div className="tools" role="group" aria-label="Tool">
        {TOOLS.map((entry) => (
          <button
            key={entry.name}
            data-testid={`tool-${entry.name}`}
            aria-pressed={tool === entry.name}
            title={`${entry.label} (${entry.key.toUpperCase()})`}
            onClick={() => setTool(entry.name)}
          >
            {entry.label} <kbd>{entry.key.toUpperCase()}</kbd>
          </button>
        ))}
      </div>
      <p className="hint">{active.hint}</p>
      <h2>Mask</h2>
      {names.length === 0 ? (
        <p className="hint">Run the Stage to build the Masks; then paint them here.</p>
      ) : (
        <div className="tools" role="group" aria-label="Mask">
          {names.map((name, index) => {
            const letter = Object.keys(keys).find((key) => keys[key] === name);
            return (
              <button key={name} data-testid={`mask-${name}`} aria-pressed={mask === name} onClick={() => setMask(name)}>
                <span className="swatch" style={{ background: tintOf(index) }} /> {name}
                {letter && <kbd>{letter.toUpperCase()}</kbd>}
              </button>
            );
          })}
        </div>
      )}
      {tool === "flood" && (
        <div className="param">
          <label htmlFor="mask-tolerance">Flood tolerance</label>
          <input
            id="mask-tolerance"
            data-testid="mask-tolerance"
            type="range"
            min={lowest}
            max={highest}
            step={0.005}
            value={toleranceNow}
            onChange={(event) => setTolerance(Number(event.target.value))}
          />
          <output data-testid="mask-tolerance-value">{toleranceNow.toFixed(3)}</output>
        </div>
      )}
      <div className="param">
        <label htmlFor="mask-radius">Brush size</label>
        <input
          id="mask-radius"
          data-testid="mask-radius"
          type="number"
          min={MIN_RADIUS}
          max={MAX_RADIUS}
          value={radius}
          onChange={(event) =>
            setRadius(Math.min(MAX_RADIUS, Math.max(MIN_RADIUS, Math.trunc(Number(event.target.value)) || 0)))
          }
        />
      </div>
      <div className="param">
        <label htmlFor="mask-opacity">Overlay opacity</label>
        <input
          id="mask-opacity"
          data-testid="mask-opacity"
          type="range"
          min={0}
          max={100}
          value={opacity}
          onChange={(event) => setOpacity(Number(event.target.value))}
        />
      </div>
      {hasBorder && (
        <>
          <h2>Edges</h2>
          <div className="tools" role="group" aria-label="Sides to wall off">
            {SIDES.map((side) => (
              <label key={side} className="toggle">
                <input
                  type="checkbox"
                  data-testid={`border-${side}`}
                  checked={sides.includes(side)}
                  onChange={(event) =>
                    setSides((now) => SIDES.filter((one) => (one === side ? event.target.checked : now.includes(one))))
                  }
                />
                {side}
              </label>
            ))}
          </div>
          <button
            data-testid="border-wall"
            disabled={names.length === 0 || sides.length === 0}
            onClick={() => props.decide("border", { mask, sides })}
          >
            Wall off edges
          </button>
          <p className="hint">Paints the chosen sides of the {mask} Mask.</p>
        </>
      )}
      <label className="toggle">
        <input
          type="checkbox"
          data-testid="mask-rebuild"
          checked={rebuild}
          onChange={(event) => onRebuild(event.target.checked)}
        />
        Rebuild the Masks after each edit
      </label>
      <p className="hint">
        <kbd>[</kbd> <kbd>]</kbd> change the brush size, <kbd>Z</kbd> zooms, hold <kbd>Space</kbd> and drag or use the arrow keys to pan, <kbd>Home</kbd> fits,{" "}
        <kbd>Enter</kbd> closes a polygon, <kbd>Backspace</kbd> removes its last point, <kbd>Esc</kbd> drops it, <kbd>Ctrl+Z</kbd> undoes.
        {tool.startsWith("polygon") && " A click with this tool places a point, so drag with Space held to pan."}
      </p>
      {unavailable && (
        <p className="reason" data-testid="mask-notice">
          {unavailable}
        </p>
      )}
      <h2>Painted image</h2>
      <button data-testid="mask-import" onClick={() => input.current?.click()}>
        Import a painted Mask image
      </button>
      <input
        ref={input}
        type="file"
        accept="image/png"
        hidden
        data-testid="mask-import-input"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) importPng(file);
          event.target.value = "";
        }}
      />
      <p className="hint">Or drop a PNG on the canvas. {asset ? "It is split into one Mask per colour." : ""}</p>
    </fieldset>
  );
}
