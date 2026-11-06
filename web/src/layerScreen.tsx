// The room's layers screen (spec §11, tickets 0043, 0044, 0053): click an object to lift it into a Layer, Shift-click to take
// away from it, trim a rim with a brush, or import a Plate image and name the regions of its difference. Every gesture is one
// `decide` on release, a hover only asks the `segment-preview` Probe, and the Layers, the Plate and the hole shown are the
// Stage's own output files: the screen computes none of them.

import { useEffect, useRef, useState, type RefObject } from "react";
import { call, fileUrl, type Envelope, type StageDescription, type StageDetail } from "./api";
import { MAX_RADIUS, MaskTool, MIN_RADIUS, type PreviewRuns } from "./maskTool";
import { isTyping, type CanvasFrame, type CanvasPixel, type CanvasTool, type PixelCanvas } from "./pixelCanvas";
import { layerIdOf } from "./sortView";
import { loadMask, type MaskPixels } from "./walkTest";

export const LAYERS_STAGE = "layers";
export const LAYERS_DECISION = "trim"; // what marks the screen: the decisions only `layers` has
export const PLATE_DECISION = "plate";
const PREVIEW_PROBE = "segment-preview";

interface LayerImage {
  id: string;
  image: HTMLImageElement;
}

// The Layers as the Stage built them, drawn with their own pixels over the Plate, and the Plate itself on or off.
class LayerView implements CanvasTool {
  layers: LayerImage[] = [];
  shown = new Set<string>();
  plate = true;

  draw(context: CanvasRenderingContext2D, frame: CanvasFrame): void {
    context.imageSmoothingEnabled = false;
    const width = frame.width * frame.zoom;
    const height = frame.height * frame.zoom;
    if (!this.plate) {
      context.fillStyle = "#1c1c1c";
      context.fillRect(frame.left, frame.top, width, height);
    }
    for (const { id, image } of this.layers) {
      if (this.shown.has(id)) context.drawImage(image, frame.left, frame.top, width, height);
    }
    const data = frame.element.dataset;
    data.layersShown = this.layers.filter((layer) => this.shown.has(layer.id)).map((layer) => layer.id).join(" ");
    data.plateShown = String(this.plate);
  }
}

// A Layer's own pixels, from its image's alpha: what a Shift-click can take away from.
function pixelsOf(image: HTMLImageElement): MaskPixels {
  const canvas = document.createElement("canvas");
  canvas.width = image.naturalWidth;
  canvas.height = image.naturalHeight;
  const context = canvas.getContext("2d", { willReadFrequently: true })!;
  context.drawImage(image, 0, 0);
  const { data } = context.getImageData(0, 0, canvas.width, canvas.height);
  const set = new Uint8Array(canvas.width * canvas.height);
  for (let index = 0; index < set.length; index++) set[index] = data[index * 4 + 3] > 0 ? 1 : 0;
  return { width: canvas.width, height: canvas.height, set };
}

// Whether a positive click has lifted the Layer yet. A Layer has no other source, so `layers` refuses a negative click
// before one (ticket 0070); the screen says so before the click is recorded.
function lifted(decisions: StageDetail["decisions"], layer: string): boolean {
  return decisions.some((decision) => decision.name === "click" && decision.data.layer === layer && decision.data.positive);
}

function layerIds(detail: StageDetail): string[] {
  return detail.outputs
    .map(layerIdOf)
    .filter((id): id is string => id !== undefined);
}

export function LayersPanel(props: {
  canvas: RefObject<PixelCanvas | null>;
  asset: string;
  detail: StageDetail;
  decisions: StageDescription["decisions"];
  imageVersion: number;
  disabled: boolean;
  rebuild: boolean;
  onRebuild: (rebuild: boolean) => void;
  decide: (decision: string, data: Record<string, unknown>) => void;
  importPlate: (file: File) => void;
}) {
  const { canvas, detail, imageVersion, disabled, rebuild, onRebuild } = props;
  const [tool, setTool] = useState<"click" | "trim">("click");
  const [layer, setLayer] = useState("layer1");
  const [radius, setRadius] = useState(2);
  const [hidden, setHidden] = useState<string[]>([]);
  const [plateOn, setPlateOn] = useState(true);
  const [holeOn, setHoleOn] = useState(false);
  const [unavailable, setUnavailable] = useState<string | null>(null);
  const [over, setOver] = useState(false);
  const ids = layerIds(detail);
  // A string, so the effect below reloads the images only when the files change, not on every new `show`.
  const idsKey = JSON.stringify(detail.outputs.filter((path) => layerIdOf(path) !== undefined));
  const pattern = props.decisions.find((entry) => entry.name === "click")?.entry_schema?.properties?.layer?.pattern;
  const valid = pattern ? new RegExp(pattern).test(layer) : /^[a-z0-9_]+$/.test(layer);
  const fromDifference = detail.decisions.some((decision) => decision.name === PLATE_DECISION);
  const hole = detail.outputs.find((path) => path.endsWith("foreground.png"));

  const latest = useRef({ ...props, layer, valid, ids, fromDifference });
  latest.current = { ...props, layer, valid, ids, fromDifference };
  const painter = useRef<MaskTool | null>(null);
  const view = useRef(new LayerView());
  const own = useRef(new Map<string, MaskPixels>());

  useEffect(() => {
    const painting = new MaskTool(
      {
        stroke(on, _erase, size, points) {
          const { disabled: off, decide, ids: known } = latest.current;
          if (off) return;
          if (!known.includes(on)) setUnavailable(`Nothing to trim: ${on} isn't a lifted Layer yet.`);
          else decide("trim", { layer: on, radius: size, points });
        },
        point(_kind, on, pixel: CanvasPixel, positive) {
          const { disabled: off, decide, detail: stage, valid: usable } = latest.current;
          if (off) return;
          if (!usable) setUnavailable("A Layer ID is lower-case letters, digits and underscores, and plate is reserved.");
          else if (!positive && !lifted(stage.decisions, on)) {
            setUnavailable(`Nothing to take away from: click an object to lift it into ${on} first.`);
          } else decide("click", { x: pixel.x, y: pixel.y, layer: on, positive });
        },
        async preview(pixel): Promise<PreviewRuns | null> {
          const { asset: id, fromDifference: planned, valid: usable } = latest.current;
          if (planned || !usable) return null; // A Plate image has no Runner to preview.
          // A Shift-click is segmented like a click: the Probe is asked for the click alone, and the tool tints the part
          // of the segment that is on the Layer.
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
    canvas.current?.setTools([view.current, painting]);
    return () => {
      painting.destroy();
      canvas.current?.setTools([]);
    };
  }, [canvas]);

  useEffect(() => {
    const painting = painter.current;
    if (!painting) return;
    painting.setTool(tool === "click" ? "click" : "brush");
    painting.mask = layer;
    painting.taking = own.current.get(layer) ?? null;
    painting.radius = radius;
    canvas.current?.redraw();
  }, [canvas, tool, layer, radius]);

  // The Layers and the hole as built; a refresh brings the new ones.
  const holeFile = hole ?? "";
  useEffect(() => {
    let current = true;
    const files = JSON.parse(idsKey) as string[];
    void Promise.all(
      files.map(async (file) => {
        const image = new Image();
        image.src = fileUrl(file, imageVersion);
        await image.decode();
        return { id: layerIdOf(file)!, image };
      }),
    )
      .then((loaded) => {
        if (!current) return;
        view.current.layers = loaded;
        own.current = new Map(loaded.map((entry) => [entry.id, pixelsOf(entry.image)]));
        if (painter.current) painter.current.taking = own.current.get(latest.current.layer) ?? null;
        canvas.current?.redraw();
      })
      .catch(() => undefined); // Rebuilt while it was read; the next refresh reads it again.
    return () => {
      current = false;
    };
  }, [canvas, idsKey, imageVersion]);

  useEffect(() => {
    let current = true;
    if (!holeOn || !holeFile) {
      painter.current?.setMasks([]);
      canvas.current?.redraw();
      return;
    }
    void loadMask(fileUrl(holeFile, imageVersion))
      .then((pixels) => {
        if (!current) return;
        painter.current?.setMasks([{ name: "hole", pixels }]);
        canvas.current?.redraw();
      })
      .catch(() => undefined);
    return () => {
      current = false;
    };
  }, [canvas, holeOn, holeFile, imageVersion]);

  useEffect(() => {
    view.current.shown = new Set(ids.filter((id) => !hidden.includes(id)));
    view.current.plate = plateOn;
    canvas.current?.redraw();
  }, [canvas, idsKey, hidden, plateOn]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (isTyping(event.target) || event.ctrlKey || event.metaKey || event.altKey) return;
      const key = event.key.toLowerCase();
      if (key === "c") setTool("click");
      else if (key === "t") setTool("trim");
      else if (event.key === "[") setRadius((size) => Math.max(MIN_RADIUS, size - 1));
      else if (event.key === "]") setRadius((size) => Math.min(MAX_RADIUS, size + 1));
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  // A Plate image dropped on the canvas is imported.
  const importPlate = props.importPlate;
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
      if (file && !latest.current.disabled) importPlate(file);
    };
    host.addEventListener("dragover", allow);
    host.addEventListener("dragleave", leave);
    host.addEventListener("drop", drop);
    return () => {
      host.removeEventListener("dragover", allow);
      host.removeEventListener("dragleave", leave);
      host.removeEventListener("drop", drop);
    };
  }, [canvas, importPlate]);

  const input = useRef<HTMLInputElement>(null);
  const newLayer = () => {
    let number = ids.length + 1;
    while (ids.includes(`layer${number}`)) number++;
    setLayer(`layer${number}`);
    setTool("click");
  };

  return (
    <fieldset disabled={disabled} className={over ? "mask-form over" : "mask-form"} data-testid="layers-panel">
      <h2>Tool</h2>
      <div className="tools" role="group" aria-label="Tool">
        <button data-testid="tool-click" aria-pressed={tool === "click"} title="Click to lift (C)" onClick={() => setTool("click")}>
          Lift an object <kbd>C</kbd>
        </button>
        <button data-testid="tool-trim" aria-pressed={tool === "trim"} title="Trim a rim (T)" onClick={() => setTool("trim")}>
          Trim <kbd>T</kbd>
        </button>
      </div>
      <p className="hint">
        {tool === "trim"
          ? "Drag over a rim of the Layer to give those pixels back to the Plate."
          : fromDifference
            ? "Click a region of the difference between the full image and the Plate image to name it a Layer."
            : "Click an object to add it; Shift-click an object to take it away. Hover shows what a click would do."}
      </p>
      <h2>Layer</h2>
      <div className="param">
        <label htmlFor="layer-id">Layer ID</label>
        <input
          id="layer-id"
          data-testid="layer-id"
          type="text"
          value={layer}
          aria-invalid={!valid}
          onChange={(event) => setLayer(event.target.value)}
        />
        <button data-testid="layer-new" onClick={newLayer}>
          New Layer
        </button>
      </div>
      {!valid && <p className="reason">A Layer ID is lower-case letters, digits and underscores, and plate is reserved.</p>}
      {ids.length === 0 ? (
        <p className="hint">No Layer is lifted yet: this room's foreground is empty.</p>
      ) : (
        <ul className="layer-list" data-testid="layer-list">
          {ids.map((id) => (
            <li key={id}>
              <button data-testid={`layer-${id}`} aria-pressed={layer === id} onClick={() => setLayer(id)}>
                {id}
              </button>
              <label className="toggle">
                <input
                  type="checkbox"
                  data-testid={`show-${id}`}
                  checked={!hidden.includes(id)}
                  onChange={(event) =>
                    setHidden((now) => (event.target.checked ? now.filter((one) => one !== id) : [...now, id]))
                  }
                />
                show
              </label>
            </li>
          ))}
        </ul>
      )}
      <label className="toggle">
        <input type="checkbox" data-testid="show-plate" checked={plateOn} onChange={(event) => setPlateOn(event.target.checked)} />
        Show the Plate
      </label>
      <label className="toggle">
        <input
          type="checkbox"
          data-testid="show-hole"
          checked={holeOn}
          disabled={!hole}
          onChange={(event) => setHoleOn(event.target.checked)}
        />
        Show the hole
      </label>
      {tool === "trim" && (
        <div className="param">
          <label htmlFor="layer-radius">Brush size</label>
          <input
            id="layer-radius"
            data-testid="layer-radius"
            type="number"
            min={MIN_RADIUS}
            max={MAX_RADIUS}
            value={radius}
            onChange={(event) =>
              setRadius(Math.min(MAX_RADIUS, Math.max(MIN_RADIUS, Math.trunc(Number(event.target.value)) || 0)))
            }
          />
        </div>
      )}
      <label className="toggle">
        <input
          type="checkbox"
          data-testid="layers-rebuild"
          checked={rebuild}
          onChange={(event) => onRebuild(event.target.checked)}
        />
        Re-run the Runner after each click
      </label>
      <p className="hint">
        <kbd>[</kbd> <kbd>]</kbd> change the brush size, <kbd>Z</kbd> zooms, <kbd>Space</kbd> pans, <kbd>Ctrl+Z</kbd> undoes.
      </p>
      {unavailable && (
        <p className="reason" data-testid="layers-notice">
          {unavailable}
        </p>
      )}
      <h2>Plate image</h2>
      <button data-testid="plate-import" onClick={() => input.current?.click()}>
        Import a Plate image
      </button>
      <input
        ref={input}
        type="file"
        accept="image/png,image/jpeg"
        hidden
        data-testid="plate-import-input"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) importPlate(file);
          event.target.value = "";
        }}
      />
      <p className="hint">Or drop a PNG or JPEG on the canvas. It is the full image without the objects, the Source's size.</p>
    </fieldset>
  );
}
