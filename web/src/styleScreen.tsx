// An Asset's style beside its references (ticket 0335, spec §11): the panel of the Stage the style Checks measure. It draws what
// `probe style` answers (ticket 0334) and holds no logic: a bar is a number between the references' ends, a measure is marked out
// when the Probe's findings name it, and the references' images are the Stages' own, shown at one whole-number zoom. "Make this a
// style reference" and "Remove reference" are `style-add` and `style-remove`, owner-only, so they send the session token.

import { useEffect, useRef, useState } from "react";
import { call, fileUrl, type Finding, type ShowData, type StyleProbe, type StyleRange } from "./api";

const MEASURES = [
  { name: "outline_density", label: "Outline density", code: "style.outline_density", note: "the share of edge pixels that are the outline colour" },
  { name: "pixel_scale", label: "Pixel scale", code: "style.pixel_scale", note: "the factor every colour run shares: 1 is the Project's own pixel" },
] as const;

type MeasureName = (typeof MEASURES)[number]["name"];

function valueOf(probe: StyleProbe, name: MeasureName): number | null {
  if (name === "outline_density") return probe.measures?.outline_density?.density ?? null;
  return probe.measures ? probe.measures.pixel_scale.gcd : null;
}

function limitOf(probe: StyleProbe, name: MeasureName): { at: number; label: string } {
  return name === "outline_density"
    ? { at: probe.limits.outline_density_floor, label: `warns below ${probe.limits.outline_density_floor}` }
    : { at: probe.limits.pixel_scale_gcd, label: `warns from ${probe.limits.pixel_scale_gcd}x` };
}

function Bar(props: { probe: StyleProbe; name: MeasureName; label: string; note: string; out: boolean }) {
  const { probe, name } = props;
  const value = valueOf(probe, name);
  const range: StyleRange | null = probe.range[name];
  if (value === null) return null;
  const limit = limitOf(probe, name);
  const top = Math.max(value, range?.high ?? 0, limit.at, 1) * 1.15;
  const at = (number: number) => `${Math.min(100, Math.max(0, (number / top) * 100))}%`;
  return (
    <div className="style-bar" data-testid={`style-bar-${name}`} data-out={props.out ? "true" : "false"} data-value={value}>
      <div className="style-bar-head">
        <span>{props.label}</span>
        <strong data-testid={`style-value-${name}`}>{Number.isInteger(value) ? `${value}x` : value.toFixed(2)}</strong>
        {props.out && (
          <span className="style-out" data-testid={`style-out-${name}`}>
            out of range
          </span>
        )}
      </div>
      <div className="style-track" title={props.note}>
        {range && (
          <span
            className="style-range"
            data-testid={`style-range-${name}`}
            data-low={range.low}
            data-high={range.high}
            style={{ left: at(range.low), width: `calc(${at(range.high)} - ${at(range.low)} + 2px)` }}
          />
        )}
        <span className="style-limit" style={{ left: at(limit.at) }} title={limit.label} />
        <span className="style-mark" data-testid={`style-mark-${name}`} style={{ left: at(value) }} />
      </div>
      <small className="hint">
        {range ? `References ${range.low.toFixed(2)} to ${range.high.toFixed(2)}${range.furthest ? `, furthest ${range.furthest}` : ""}` : "No other built reference"}
        {" · "}
        {limit.label}
      </small>
    </div>
  );
}

// The Stage's picture of an Asset, as a path in the Project: a room's or a Prop's image, a figure's first frame of its `idle` Clip
// facing `s` (the frame the Probe measures), read from the `render.json` its `finish` wrote. Display only.
interface RenderDocument {
  clips?: { name: string; directions: Record<string, { files: { color: string } }[]> }[];
}

async function imageOf(show: ShowData, stage: string): Promise<string | null> {
  const detail = show.stages.find((entry) => entry.stage === stage);
  if (!detail) return null;
  if (detail.image && detail.image.endsWith(".png")) return detail.image;
  const record = detail.outputs.find((path) => path.endsWith("/render.json"));
  if (!record) return null;
  const response = await fetch(fileUrl(record, 0), { cache: "no-store" });
  if (!response.ok) return null;
  const clips = ((await response.json()) as RenderDocument).clips ?? [];
  const clip = clips.find((entry) => entry.name === "idle") ?? clips[0];
  const directions = clip ? Object.keys(clip.directions) : [];
  const direction = directions.includes("s") ? "s" : directions[0];
  const file = clip && direction ? clip.directions[direction][0]?.files.color : undefined;
  return file ? `${record.slice(0, record.lastIndexOf("/"))}/${file}` : null;
}

function useImages(assets: { asset: string; stage: string }[], current: ShowData, refreshes: number): Record<string, string | null> {
  const [found, setFound] = useState<Record<string, string | null>>({});
  const key = assets.map((one) => `${one.asset}/${one.stage}`).join(",");
  useEffect(() => {
    let live = true;
    void (async () => {
      const next: Record<string, string | null> = {};
      for (const { asset, stage } of assets) {
        try {
          const shown = asset === current.asset ? current : (await call<ShowData>("show", { asset })).data;
          next[asset] = shown ? await imageOf(shown, stage) : null;
        } catch {
          next[asset] = null;
        }
      }
      if (live) setFound(next);
    })();
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, refreshes]);
  return found;
}

const LONG = 120; // px: the zoom starts where the longest side of the largest picture is about this long (the panel is narrow)

function Picture(props: { path: string | null | undefined; version: number; zoom: number; label: string; onSize: (side: number) => void }) {
  if (!props.path) return <span className="hint">not built yet</span>;
  return (
    <img
      className="style-picture"
      alt={props.label}
      src={fileUrl(props.path, props.version)}
      style={{ display: "block", width: "auto", height: "auto", zoom: props.zoom }}
      onLoad={(event) => props.onSize(Math.max(event.currentTarget.naturalWidth, event.currentTarget.naturalHeight))}
    />
  );
}

export function StylePanel(props: {
  probe: StyleProbe;
  show: ShowData;
  findings: Finding[]; // the Stage's own findings, to mark a `style.*` one that was jumped to
  focus: number; // counts the jumps to a `style.*` finding
  refreshes: number;
  imageVersion: number;
  disabled: boolean;
  setReference: (add: boolean) => void;
}) {
  const { probe, show } = props;
  const stage = probe.stage ?? "";
  const listed = probe.references.some((entry) => entry.asset === probe.asset);
  const others = probe.references.filter((entry) => !entry.left_out && entry.built && entry.stage);
  const shown = [{ asset: probe.asset, stage }, ...others.map((entry) => ({ asset: entry.asset, stage: entry.stage! }))];
  const images = useImages(shown, show, props.refreshes);
  const furthest = probe.range.pixel_scale?.furthest ?? probe.range.outline_density?.furthest ?? null;
  const [zoom, setZoom] = useState<number | null>(null);
  const [largest, setLargest] = useState<Record<string, number>>({});
  const best = Math.max(0, ...Object.values(largest));
  const zoomed = zoom ?? (best > 0 ? Math.max(1, Math.min(8, Math.floor(LONG / best))) : 1);
  const root = useRef<HTMLElement>(null);
  const [flash, setFlash] = useState(false);
  useEffect(() => {
    if (props.focus === 0) return;
    root.current?.scrollIntoView?.({ block: "nearest" });
    setFlash(true);
    const timer = window.setTimeout(() => setFlash(false), 1200);
    return () => window.clearTimeout(timer);
  }, [props.focus]);
  const out = (code: string) => probe.findings.some((finding) => finding.code === code) || props.findings.some((finding) => finding.code === code);
  const messages = probe.findings.filter((finding) => finding.severity !== "info");

  return (
    <section ref={root} className="style-panel" data-testid="style-panel" data-focused={flash ? "true" : "false"} data-reference={listed ? "true" : "false"}>
      <h2>Style</h2>
      {probe.references.length === 0 && <p className="hint">No style reference yet: make an Asset of this Kind that you like one, and the others are measured against it.</p>}
      {!probe.built && <p className="hint">Nothing is built on {stage} yet, so there is nothing to measure.</p>}
      {MEASURES.map((measure) => (
        <Bar key={measure.name} probe={probe} name={measure.name} label={measure.label} note={measure.note} out={out(measure.code)} />
      ))}
      {messages.length > 0 && (
        <ul className="findings" data-testid="style-findings">
          {messages.map((finding, index) => (
            <li key={`${finding.code}-${index}`} data-severity={finding.severity} data-testid={`style-finding-${finding.code}`}>
              {finding.message}
            </li>
          ))}
        </ul>
      )}
      {probe.built && others.length > 0 && (
        <div data-testid="style-compare" data-zoom={zoomed}>
          <div className="decisions">
            <span>
              Beside the references at {zoomed}x
            </span>
            <button data-testid="style-zoom-out" disabled={zoomed <= 1} onClick={() => setZoom(zoomed - 1)}>
              -
            </button>
            <button data-testid="style-zoom-in" disabled={zoomed >= 8} onClick={() => setZoom(zoomed + 1)}>
              +
            </button>
          </div>
          <div className="style-row">
            {shown.map((entry) => (
              <figure key={entry.asset} className="style-figure" data-testid={`style-figure-${entry.asset}`} data-self={entry.asset === probe.asset}>
                <Picture
                  path={images[entry.asset]}
                  version={props.imageVersion}
                  zoom={zoomed}
                  label={entry.asset}
                  onSize={(side) => setLargest((now) => (now[entry.asset] === side ? now : { ...now, [entry.asset]: side }))}
                />
                <figcaption>
                  {entry.asset === probe.asset ? "this Asset" : entry.asset}
                  {entry.asset === furthest && " (furthest)"}
                </figcaption>
              </figure>
            ))}
          </div>
        </div>
      )}
      <div className="style-reference">
        {listed ? (
          <button data-testid="style-remove" disabled={props.disabled} onClick={() => props.setReference(false)}>
            Remove reference
          </button>
        ) : (
          <button data-testid="style-add" disabled={props.disabled} onClick={() => props.setReference(true)}>
            Make this a style reference
          </button>
        )}
        {listed && <span className="hint">A style reference: left out of its own range.</span>}
      </div>
    </section>
  );
}
