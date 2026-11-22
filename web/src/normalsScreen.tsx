// The room's normals screen (ticket 0343, ADR 0014): the Stage's parameters are rendered from `describe` by the shell, and this panel adds
// what a canvas needs: the room lit by a point light that follows the mouse (a preview drawn here, not Godot's), a switch to the raw
// normal image, and the fix. A `flatten` brush or polygon is one `decide` on release; the Override brush paints a normal by hand
// and is one `override` on release. Findings of `normals.not_flat_walkable` are drawn as their boxes and jump to them as others do.

import { useEffect, useRef, useState, type RefObject } from "react";
import { fileUrl, type Finding, type ShowData, type StageDescription, type StageDetail } from "./api";
import { LitTool, loadPixels, overlayPng, type Box } from "./normalsTool";
import { MAX_RADIUS, MaskTool, MIN_RADIUS, type MaskToolName } from "./maskTool";
import { isTyping, type PixelCanvas } from "./pixelCanvas";

export const NORMALS_STAGE = "normals";
export const NOT_FLAT_CODE = "normals.not_flat_walkable";
const FLATTEN = "flatten";
const OVERRIDE = "override";
const TINTS = { [FLATTEN]: "#4dd6d6", [OVERRIDE]: "#ff7bd5" };

type Edit = typeof FLATTEN | typeof OVERRIDE;

const TOOLS: { name: MaskToolName; key: string; label: string; hint: string; erases: boolean }[] = [
  { name: "brush", key: "b", label: "Brush", hint: "Drag to paint.", erases: false },
  { name: "erase", key: "e", label: "Unflatten brush", hint: "Drag to give the Stage's own normals back.", erases: true },
  {
    name: "polygon",
    key: "g",
    label: "Polygon",
    hint: "Click the corners; click the first point or press Enter to close. Backspace removes the last point, Esc drops it.",
    erases: false,
  },
  {
    name: "polygon-erase",
    key: "x",
    label: "Unflatten polygon",
    hint: "Click the corners; press Enter to close and give the Stage's own normals back.",
    erases: true,
  },
];

// The normals an Override can paint, as Godot's encoding gives them: a 45 degree tilt each way, or flat. The corners of a room's
// walls and ledges are what these are for; anything finer is painted in an image and imported.
const TILT = Math.SQRT1_2;
const NORMALS: { name: string; label: string; vector: [number, number, number] }[] = [
  { name: "flat", label: "Flat", vector: [0, 0, 1] },
  { name: "up", label: "Faces up", vector: [0, TILT, TILT] },
  { name: "down", label: "Faces down", vector: [0, -TILT, TILT] },
  { name: "left", label: "Faces left", vector: [-TILT, 0, TILT] },
  { name: "right", label: "Faces right", vector: [TILT, 0, TILT] },
];

function encode(vector: [number, number, number]): [number, number, number, number] {
  const byte = (value: number) => Math.round(((value + 1) / 2) * 255);
  return [byte(vector[0]), byte(vector[1]), byte(vector[2]), 255];
}

export function NormalsPanel(props: {
  canvas: RefObject<PixelCanvas | null>;
  asset: string;
  show: ShowData;
  detail: StageDetail;
  decisions: StageDescription["decisions"];
  imageVersion: number;
  disabled: boolean;
  rebuild: boolean;
  onRebuild: (rebuild: boolean) => void;
  findings: Finding[];
  decide: (decision: string, data: Record<string, unknown>, settled?: () => void) => void;
  overridePng: (file: File, settled?: () => void) => void;
}) {
  const { canvas, detail, imageVersion, disabled } = props;
  const [edit, setEdit] = useState<Edit>(FLATTEN);
  const [tool, setTool] = useState<MaskToolName>("brush");
  const [radius, setRadius] = useState(3);
  const [walkable, setWalkable] = useState(false);
  const [lit, setLit] = useState(true);
  const [normal, setNormal] = useState("flat");
  const [error, setError] = useState<string | null>(null);
  const built = detail.image !== null && detail.image.endsWith(".png") && String(detail.params.mode) !== "off";
  const normalFile = built ? detail.image : null;
  const palette = props.show.stages.find((entry) => entry.stage === "palette");
  const baseFile = palette?.image ?? detail.input_image;
  const boxes: Box[] = props.findings
    .filter((finding) => finding.code === NOT_FLAT_CODE && finding.position?.x != null && finding.position?.y != null)
    .map((finding) => ({
      x: finding.position!.x!,
      y: finding.position!.y!,
      width: finding.position!.width ?? 1,
      height: finding.position!.height ?? 1,
    }));
  const boxesKey = JSON.stringify(boxes);

  const latest = useRef({ ...props, edit, walkable, normal, size: { width: 0, height: 0 } });
  latest.current = { ...props, edit, walkable, normal, size: latest.current.size };
  const painter = useRef<MaskTool | null>(null);
  const light = useRef<LitTool | null>(null);

  useEffect(() => {
    const lighting = new LitTool();
    const painting = new MaskTool(
      {
        stroke(_mask, erase, size, points) {
          const now = latest.current;
          if (now.edit === FLATTEN) {
            const settled = painter.current?.addMark({ kind: "stroke", mask: FLATTEN, erase, radius: size, points });
            now.decide(FLATTEN, { shape: "brush", points, radius: size, ...(erase ? { erase: true } : {}), ...(now.walkable ? { walkable: true } : {}) }, settled);
          } else if (!erase) {
            const settled = painter.current?.addMark({ kind: "stroke", mask: OVERRIDE, erase, radius: size, points });
            void paint({ kind: "brush", radius: size, points }, settled);
          }
        },
        polygon(_mask, erase, points) {
          const now = latest.current;
          if (now.edit === FLATTEN) {
            const settled = painter.current?.addMark({ kind: "polygon", mask: FLATTEN, erase, points });
            now.decide(FLATTEN, { shape: "polygon", points, ...(erase ? { erase: true } : {}), ...(now.walkable ? { walkable: true } : {}) }, settled);
          } else if (!erase) {
            const settled = painter.current?.addMark({ kind: "polygon", mask: OVERRIDE, erase, points });
            void paint({ kind: "polygon", points }, settled);
          }
        },
        point() {
          // The point tools aren't offered on this screen.
        },
        async preview() {
          return null;
        },
      },
      () => canvas.current?.redraw(),
    );
    // One Override of the room's size, painted with the picked normal, on release.
    async function paint(shape: Parameters<typeof overlayPng>[2], settled?: () => void): Promise<void> {
      const now = latest.current;
      const vector = NORMALS.find((entry) => entry.name === now.normal)!.vector;
      const { width, height } = now.size;
      try {
        const blob = await overlayPng(width, height, shape, encode(vector));
        now.overridePng(new File([blob], "override.png", { type: "image/png" }), settled);
      } catch {
        settled?.();
        setError("The room's normals aren't loaded yet.");
      }
    }
    painting.maskColours.set(FLATTEN, TINTS[FLATTEN]);
    painting.maskColours.set(OVERRIDE, TINTS[OVERRIDE]);
    painting.mask = FLATTEN;
    painter.current = painting;
    light.current = lighting;
    canvas.current?.setTools([lighting, painting]);
    return () => {
      painting.destroy();
      canvas.current?.setTools([]);
    };
  }, [canvas]);

  // What the normals and the room are, read from the built files; a rebuild brings the new ones.
  useEffect(() => {
    let current = true;
    const lighting = light.current;
    if (!lighting) return;
    if (!normalFile) {
      lighting.normals = lighting.base = null;
      canvas.current?.redraw();
      return;
    }
    void Promise.all([loadPixels(fileUrl(normalFile, imageVersion)), baseFile ? loadPixels(fileUrl(baseFile, imageVersion)) : null])
      .then(([normals, base]) => {
        if (!current) return;
        lighting.normals = normals;
        lighting.base = base;
        latest.current.size = { width: normals.width, height: normals.height };
        canvas.current?.redraw();
      })
      .catch(() => undefined); // Rebuilt while it was read; the next refresh reads it again.
    return () => {
      current = false;
    };
  }, [canvas, normalFile, baseFile, imageVersion]);

  useEffect(() => {
    const painting = painter.current;
    if (!painting) return;
    painting.setTool(tool);
    painting.mask = edit;
    painting.radius = radius;
    canvas.current?.redraw();
  }, [canvas, tool, edit, radius]);

  useEffect(() => {
    if (!light.current) return;
    light.current.lit = lit;
    light.current.boxes = JSON.parse(boxesKey) as Box[];
    canvas.current?.redraw();
  }, [canvas, lit, boxesKey, normalFile]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (isTyping(event.target) || event.ctrlKey || event.metaKey || event.altKey) return;
      const key = event.key.toLowerCase();
      const chosen = TOOLS.find((entry) => entry.key === key);
      if (chosen) {
        if (chosen.erases && latest.current.edit === OVERRIDE) return;
        setTool(chosen.name);
      } else if (key === "f") setEdit(FLATTEN);
      else if (key === "o") setEdit(OVERRIDE);
      else if (key === "l") setLit((now) => !now);
      else if (event.key === "[") setRadius((size) => Math.max(MIN_RADIUS, size - 1));
      else if (event.key === "]") setRadius((size) => Math.min(MAX_RADIUS, size + 1));
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  // Switching to Override leaves an unflatten tool for the brush.
  useEffect(() => {
    if (edit === OVERRIDE && TOOLS.find((entry) => entry.name === tool)?.erases) setTool("brush");
  }, [edit, tool]);

  const active = TOOLS.find((entry) => entry.name === tool)!;
  const off = String(detail.params.mode) === "off";

  return (
    <fieldset disabled={disabled} className="mask-form" data-testid="normals-panel">
      {off && (
        <p className="hint" data-testid="normals-off">
          The room's normals are off. Set <code>mode</code> to depth, run the Stage and accept the depth result.
        </p>
      )}
      {!off && !built && <p className="hint">Run the Stage to build the room's normals; then flatten them here.</p>}
      <h2>View</h2>
      <div className="tools" role="group" aria-label="View">
        <button data-testid="view-lit" aria-pressed={lit} disabled={!built} onClick={() => setLit(true)} title="The room lit by a light that follows the mouse (L)">
          Lit <kbd>L</kbd>
        </button>
        <button data-testid="view-normals" aria-pressed={!lit} disabled={!built} onClick={() => setLit(false)} title="The raw normal image (L)">
          Normals <kbd>L</kbd>
        </button>
      </div>
      <p className="hint">The light follows the mouse. This is a preview, not Godot's light.</p>
      <h2>Fix</h2>
      <div className="tools" role="group" aria-label="Edit">
        <button data-testid="edit-flatten" aria-pressed={edit === FLATTEN} disabled={!built} onClick={() => setEdit(FLATTEN)} title="Make the normal face the camera (F)">
          Flatten <kbd>F</kbd>
        </button>
        <button data-testid="edit-override" aria-pressed={edit === OVERRIDE} disabled={!built} onClick={() => setEdit(OVERRIDE)} title="Paint a normal by hand (O)">
          Override <kbd>O</kbd>
        </button>
      </div>
      <div className="tools" role="group" aria-label="Tool">
        {TOOLS.filter((entry) => !(entry.erases && edit === OVERRIDE)).map((entry) => (
          <button
            key={entry.name}
            data-testid={`tool-${entry.name}`}
            aria-pressed={tool === entry.name}
            disabled={!built}
            title={`${entry.label} (${entry.key.toUpperCase()})`}
            onClick={() => setTool(entry.name)}
          >
            {entry.label} <kbd>{entry.key.toUpperCase()}</kbd>
          </button>
        ))}
      </div>
      <p className="hint">{active.hint}</p>
      {edit === FLATTEN ? (
        <label className="toggle" title="Flatten only the pixels the Body can walk on">
          <input type="checkbox" data-testid="normals-walkable" checked={walkable} onChange={(event) => setWalkable(event.target.checked)} />
          Walkable pixels only
        </label>
      ) : (
        <div className="tools" role="group" aria-label="Normal">
          {NORMALS.map((entry) => (
            <button key={entry.name} data-testid={`normal-${entry.name}`} aria-pressed={normal === entry.name} onClick={() => setNormal(entry.name)}>
              {entry.label}
            </button>
          ))}
        </div>
      )}
      <div className="param">
        <label htmlFor="normals-radius">Brush size</label>
        <input
          id="normals-radius"
          data-testid="normals-radius"
          type="number"
          min={MIN_RADIUS}
          max={MAX_RADIUS}
          value={radius}
          onChange={(event) => setRadius(Math.min(MAX_RADIUS, Math.max(MIN_RADIUS, Math.trunc(Number(event.target.value)) || 0)))}
        />
      </div>
      <label className="toggle">
        <input type="checkbox" data-testid="normals-rebuild" checked={props.rebuild} onChange={(event) => props.onRebuild(event.target.checked)} />
        Rebuild the normals after each edit
      </label>
      <p className="hint">
        <kbd>[</kbd> <kbd>]</kbd> change the brush size, <kbd>Z</kbd> zooms, hold <kbd>Space</kbd> and drag to pan, <kbd>Ctrl+Z</kbd> undoes.
      </p>
      {error && <p className="reason">{error}</p>}
    </fieldset>
  );
}
