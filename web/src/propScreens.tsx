// The prop's hand-written screens (spec §6.2, §11): the footprint, a canvas tool for the collision polygon and the y-sort
// origin, and a Prop's states (ticket 0261): the strip, the crop of a state, the side-by-side view. Every other prop Stage
// is a shared screen rendered from `describe`.

import { useEffect, useRef, useState, type RefObject } from "react";
import { fileUrl, type Finding, type ShowData, type StageDetail } from "./api";
import { FootprintTool, type Footprint, type FootprintMode, type Point } from "./footprintTool";
import { isTyping, type PixelCanvas } from "./pixelCanvas";

export const FOOTPRINT_DECISION = "footprint";
export const FOOTPRINT_STAGE = "footprint";
export const STATE_DECISION = "state";
export const STATE_OFFSET_DECISION = "state_offset";

// A state is `null` for the default state, or its ID (a Decision with no `state` is the default's).
function stateOf(decision: { data: Record<string, unknown> }): string | null {
  return typeof decision.data.state === "string" ? decision.data.state : null;
}

// The latest Decision is the one that counts (the Stage's own rule); `show` lists only the Decisions that stand.
function standing(detail: StageDetail, state: string | null = null): Footprint {
  const found = detail.decisions.filter((decision) => decision.name === FOOTPRINT_DECISION && stateOf(decision) === state).at(-1);
  if (!found) return { polygon: [], origin: null };
  const { polygon, origin } = found.data as { polygon?: Point[]; origin?: Point };
  return { polygon: polygon ?? [], origin: origin ?? null };
}

export function FootprintPanel(props: {
  canvas: RefObject<PixelCanvas | null>;
  detail: StageDetail;
  state?: string | null; // a Prop's state; null or absent: the default state
  decide: (footprint: { polygon: Point[]; origin: Point }) => void;
  disabled: boolean;
}) {
  const { canvas, detail, decide, disabled } = props;
  const footprint = standing(detail, props.state ?? null);
  const [mode, setMode] = useState<FootprintMode>(footprint.origin ? "polygon" : "origin");
  const form = useRef({ decide, disabled });
  form.current = { decide, disabled };
  const tool = useRef<FootprintTool | null>(null);
  const shown = JSON.stringify(footprint);

  useEffect(() => {
    const drawing = new FootprintTool({
      change(next) {
        form.current.decide(next); // queued behind a Run, never dropped (ticket 0083)
      },
    });
    tool.current = drawing;
    canvas.current?.setTools([drawing]);
    return () => canvas.current?.setTools([]);
  }, [canvas]);

  // Every refresh brings the Decisions that stand, so a gesture that was refused goes back to where they are.
  useEffect(() => {
    if (!tool.current) return;
    tool.current.mode = mode;
    tool.current.set(JSON.parse(shown) as Footprint);
    canvas.current?.redraw();
  }, [canvas, shown, mode]);

  // `O` and `P` switch between the origin and the polygon.
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (isTyping(event.target) || event.ctrlKey || event.metaKey || event.altKey) return;
      if (event.code === "KeyO") setMode("origin");
      else if (event.code === "KeyP") setMode("polygon");
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const { polygon, origin } = footprint;
  const record = (next: Point[]) => {
    if (origin) decide({ polygon: next, origin });
  };

  return (
    <fieldset disabled={disabled} className="footprint-form">
      <h2>Footprint{props.state ? ` of ${props.state}` : ""}</h2>
      <div className="tools" role="group" aria-label="Tool">
        <button data-testid="footprint-origin" aria-pressed={mode === "origin"} onClick={() => setMode("origin")}>
          Origin (O)
        </button>
        <button
          data-testid="footprint-polygon"
          aria-pressed={mode === "polygon"}
          disabled={!origin}
          onClick={() => setMode("polygon")}
        >
          Polygon (P)
        </button>
      </div>
      <p className="hint" data-testid="footprint-hint">
        {mode === "origin"
          ? "Click the canvas to put the y-sort origin there, or drag it."
          : "Click the canvas to add a point to the collision polygon. Drag a point to move it."}
        {!origin && " Set the origin first."}
      </p>
      <p data-testid="footprint-summary">
        Origin: {origin ? `(${origin[0]}, ${origin[1]})` : "not set"}. Polygon: {polygon.length} point(s).
      </p>
      {origin && polygon.length > 0 && (
        <div className="decisions">
          <button data-testid="footprint-remove-last" onClick={() => record(polygon.slice(0, -1))}>
            Remove last point
          </button>
          <button data-testid="footprint-clear" onClick={() => record([])}>
            No collision
          </button>
        </div>
      )}
    </fieldset>
  );
}

// ---------------------------------------------------------------------------------------------------------------------
// A Prop's states (ticket 0261).

// A Stage's image (or input image) for a state, as `show` lists it; the default's is the Stage's own.
export function stateImage(
  show: ShowData | null,
  stage: string | undefined,
  state: string | null,
  which: "image" | "input_image",
): string | null {
  if (!show || !stage) return null;
  if (state === null) return show.stages.find((entry) => entry.stage === stage)?.[which] ?? null;
  const own = show.states?.find((entry) => entry.state === state)?.images?.find((entry) => entry.stage === stage);
  return own?.[which] ?? null;
}

// What a state's thumbnail shows: the furthest built Stage's image, else the picked Source. The first that loads counts.
function thumbnailSources(show: ShowData, state: string | null): string[] {
  const built = ["finish", "palette", "fit", "cutout", "source"]
    .map((name) => stateImage(show, name, state, "image"))
    .filter((path): path is string => path !== null);
  const own = state === null ? { variants: show.variants, picked: show.picked } : show.states?.find((entry) => entry.state === state);
  const picked = own?.variants.find((variant) => variant.name === own.picked)?.file;
  return [...built, ...(picked ? [picked] : [])];
}

// Pixel art at a whole-number scale that fits the box, never smoothed (the CSS pixelates it).
function Thumbnail(props: { sources: string[]; version: number; box: number; label: string }) {
  const [tried, setTried] = useState(0);
  const [scale, setScale] = useState(1);
  const source = props.sources[tried];
  if (!source) return <span className="state-thumb empty" />;
  return (
    <img
      className="state-thumb"
      alt={props.label}
      src={fileUrl(source, props.version)}
      style={{ width: "auto", height: "auto", zoom: scale }}
      onLoad={(event) => {
        const { naturalWidth: w, naturalHeight: h } = event.currentTarget;
        setScale(Math.max(1, Math.floor(props.box / Math.max(w, h, 1))));
      }}
      onError={() => setTried((n) => n + 1)}
    />
  );
}

// The findings that are about a state carry it as `position.state`; the default's carry none.
function aboutState(finding: Finding, state: string | null): boolean {
  return (finding.position?.state ?? null) === state;
}

function worst(findings: Finding[]): string {
  if (findings.some((finding) => finding.severity === "error")) return "error";
  return findings.length > 0 ? "warning" : "ok";
}

export function StateStrip(props: {
  show: ShowData;
  state: string | null;
  findings: Finding[];
  imageVersion: number;
  disabled: boolean;
  sideBySide: boolean;
  onSelect: (state: string | null) => void;
  onSideBySide: (on: boolean) => void;
  declare: (id: string, width: number, height: number) => void;
  importFiles: (files: File[]) => void;
}) {
  const { show, state, findings, imageVersion, disabled } = props;
  const brief = show.stages.find((entry) => entry.stage === "brief")?.params ?? {};
  const [id, setId] = useState("");
  const [width, setWidth] = useState(String(brief.width ?? 16));
  const [height, setHeight] = useState(String(brief.height ?? 16));
  const input = useRef<HTMLInputElement>(null);
  const defaultId = show.default_state ?? "default";
  const entries = [
    { id: null as string | null, name: defaultId, picked: show.picked, size: null as string | null },
    ...(show.states ?? []).map((entry) => ({
      id: entry.state as string | null,
      name: entry.state,
      picked: entry.picked,
      size: `${entry.width}x${entry.height}`,
    })),
  ];
  const valid = /^[a-z][a-z0-9]*(_[a-z0-9]+)*$/.test(id) && Number(width) > 0 && Number(height) > 0;

  return (
    <section className="state-strip" data-testid="state-strip" aria-label="States">
      <h2>States</h2>
      <div className="state-list" role="group" aria-label="State">
        {entries.map((entry) => {
          const mine = findings.filter((finding) => aboutState(finding, entry.id));
          return (
            <button
              key={entry.name}
              className="state-card"
              data-testid={`state-${entry.name}`}
              data-findings={worst(mine)}
              aria-pressed={entry.id === state}
              title={mine.map((finding) => finding.code).join(", ")}
              onClick={() => props.onSelect(entry.id)}
            >
              <Thumbnail sources={thumbnailSources(show, entry.id)} version={imageVersion} box={48} label={`State ${entry.name}`} />
              <span>
                {entry.name}
                {entry.id === null && " (default)"}
              </span>
              <span className="hint" data-testid={`state-${entry.name}-pick`}>
                {entry.picked ? `Source ${entry.picked.slice(0, 8)}` : "no Source picked"}
                {entry.size && ` · ${entry.size}`}
                {mine.length > 0 && ` · ${mine.length} finding(s)`}
              </span>
            </button>
          );
        })}
      </div>
      <div className="decisions">
        <button data-testid="states-side-by-side" aria-pressed={props.sideBySide} onClick={() => props.onSideBySide(!props.sideBySide)}>
          Side by side
        </button>
        {state && (
          <>
            <button data-testid="state-import" disabled={disabled} onClick={() => input.current?.click()}>
              Import an image for {state}
            </button>
            <input
              ref={input}
              data-testid="state-import-input"
              type="file"
              accept="image/png,image/jpeg"
              multiple
              hidden
              onChange={(event) => {
                props.importFiles([...(event.target.files ?? [])]);
                event.target.value = "";
              }}
            />
          </>
        )}
      </div>
      <fieldset disabled={disabled} className="state-declare">
        <legend>Declare a state</legend>
        <label>
          ID
          <input data-testid="state-id" value={id} placeholder="toppled" onChange={(event) => setId(event.target.value)} />
        </label>
        <label>
          Width
          <input data-testid="state-width" type="number" min={1} value={width} onChange={(event) => setWidth(event.target.value)} />
        </label>
        <label>
          Height
          <input data-testid="state-height" type="number" min={1} value={height} onChange={(event) => setHeight(event.target.value)} />
        </label>
        <button
          data-testid="state-declare"
          disabled={!valid}
          onClick={() => {
            props.declare(id, Number(width), Number(height));
            setId("");
          }}
        >
          Declare
        </button>
      </fieldset>
    </section>
  );
}

// `fit` in `downscale` mode: where a state's crop starts, which its own `state_offset` Decision gives (a state otherwise
// takes the Stage's parameters). One Decision on Enter or blur.
export function StateOffsetPanel(props: {
  detail: StageDetail;
  state: string;
  disabled: boolean;
  decide: (offsetX: number, offsetY: number) => void;
}) {
  const standingOffset = props.detail.decisions.filter((d) => d.name === STATE_OFFSET_DECISION && stateOf(d) === props.state).at(-1);
  const nowX = standingOffset ? Number(standingOffset.data.offset_x) : Number(props.detail.params.offset_x ?? 0);
  const nowY = standingOffset ? Number(standingOffset.data.offset_y) : Number(props.detail.params.offset_y ?? 0);
  const [x, setX] = useState(String(nowX));
  const [y, setY] = useState(String(nowY));
  useEffect(() => {
    setX(String(nowX));
    setY(String(nowY));
  }, [nowX, nowY, props.state]);
  const commit = () => {
    const [nx, ny] = [Number(x), Number(y)];
    if (Number.isInteger(nx) && Number.isInteger(ny) && nx >= 0 && ny >= 0 && (nx !== nowX || ny !== nowY)) props.decide(nx, ny);
  };
  return (
    <fieldset disabled={props.disabled} className="state-declare">
      <legend>Crop of {props.state}</legend>
      <label>
        Offset x
        <input data-testid="state-offset-x" type="number" min={0} value={x} onChange={(e) => setX(e.target.value)} onBlur={commit} onKeyDown={(e) => e.key === "Enter" && commit()} />
      </label>
      <label>
        Offset y
        <input data-testid="state-offset-y" type="number" min={0} value={y} onChange={(e) => setY(e.target.value)} onBlur={commit} onKeyDown={(e) => e.key === "Enter" && commit()} />
      </label>
    </fieldset>
  );
}

// Every state at one scale on one ground line, each at its own origin, so the Owner sees that they match in size. The scale
// is 1x, and a whole number when raised.
export function SideBySide(props: { show: ShowData; imageVersion: number }) {
  const { show } = props;
  const [zoom, setZoom] = useState(1);
  const [sizes, setSizes] = useState<Record<string, [number, number]>>({});
  const footprint = show.stages.find((entry) => entry.stage === FOOTPRINT_STAGE);
  const entries = [
    { id: null as string | null, name: show.default_state ?? "default" },
    ...(show.states ?? []).map((entry) => ({ id: entry.state as string | null, name: entry.state })),
  ];
  const items = entries.map((entry) => {
    const origin = footprint ? standing(footprint, entry.id).origin : null;
    const sources = footprint
      ? [stateImage(show, FOOTPRINT_STAGE, entry.id, "image"), stateImage(show, FOOTPRINT_STAGE, entry.id, "input_image")].filter(
          (path): path is string => path !== null,
        )
      : thumbnailSources(show, entry.id);
    return { ...entry, origin, sources, size: sizes[entry.name] };
  });
  // Without an origin a state stands on its bottom edge.
  const originY = (item: (typeof items)[number]) => item.origin?.[1] ?? item.size?.[1] ?? 0;
  const ground = Math.max(0, ...items.map(originY));
  return (
    <div className="side-by-side" data-testid="side-by-side" data-zoom={zoom}>
      <div className="decisions">
        <span>Side by side at {zoom}x</span>
        <button data-testid="side-zoom-out" disabled={zoom <= 1} onClick={() => setZoom(zoom - 1)}>
          -
        </button>
        <button data-testid="side-zoom-in" disabled={zoom >= 8} onClick={() => setZoom(zoom + 1)}>
          +
        </button>
      </div>
      <div className="side-row">
        <div className="side-ground" style={{ top: ground * zoom }} />
        {items.map((item) => (
          <figure
            key={item.name}
            className="side-state"
            data-testid={`side-${item.name}`}
            data-origin={item.origin ? item.origin.join(",") : ""}
            style={{ marginTop: (ground - originY(item)) * zoom }}
          >
            <div className="side-sprite">
              <SideImage
                sources={item.sources}
                version={props.imageVersion}
                zoom={zoom}
                label={`State ${item.name}`}
                testid={`side-img-${item.name}`}
                onSize={(w, h) =>
                  setSizes((now) => (now[item.name]?.[0] === w && now[item.name]?.[1] === h ? now : { ...now, [item.name]: [w, h] }))
                }
              />
              {item.origin && <span className="side-origin" style={{ left: item.origin[0] * zoom, top: item.origin[1] * zoom }} />}
            </div>
            <figcaption>
              {item.name}
              {!item.origin && " (no origin)"}
            </figcaption>
          </figure>
        ))}
      </div>
    </div>
  );
}

function SideImage(props: {
  sources: string[];
  version: number;
  zoom: number;
  label: string;
  testid: string;
  onSize: (width: number, height: number) => void;
}) {
  const [tried, setTried] = useState(0);
  const source = props.sources[tried];
  if (!source) return <span className="hint">not built yet</span>;
  return (
    <img
      data-testid={props.testid}
      alt={props.label}
      src={fileUrl(source, props.version)}
      style={{ display: "block", width: "auto", height: "auto", zoom: props.zoom }}
      onLoad={(event) => props.onSize(event.currentTarget.naturalWidth, event.currentTarget.naturalHeight)}
      onError={() => setTried((n) => n + 1)}
    />
  );
}
