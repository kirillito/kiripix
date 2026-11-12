// A sprite's first Stage (spec §6.4, §11): `frames`. It has no picture of its own to draw, so it is a screen of the imported sheets
// and two forms, and the Stage panel beside it stays the shared one (params, Checks, the primary action). Everything here is a
// Command: `import` with the role `sheet`, and `decide` for a `sheet` (how a PNG is cut) or a `clip` (its playback). It holds no
// logic: the Stage's own Checks say what is wrong (`frames.direction_missing` and the rest), and the panel shows them.
//
// The frames themselves are seen on `fit`, with the frame strip of frameScreen.tsx.

import { useState } from "react";
import type { ShowData, StageDescription, StageDetail } from "./api";
import { FileDrop, basename, outputOf, readableSize, useDocument, type ImportRole } from "./characterScreens";

export const SPRITE_KIND = "sprite";
export const SPRITE_FRAMES_STAGE = "frames";
const SHEET_DECISION = "sheet";
const CLIP_DECISION = "clip";
const COMPASS = ["s", "sw", "w", "nw", "n", "ne", "e", "se"];
const ORDER: Record<string, string[]> = {
  "8": COMPASS,
  "4": ["s", "w", "n", "e"],
  "1": ["s"],
};

interface FramesDocument {
  directions: string[];
  clips: { name: string; fps: number; loop: boolean; stationary: boolean; directions: Record<string, unknown[]> }[];
}

interface SheetData {
  file: string;
  clip?: string;
  layout?: "rows" | "columns";
  directions?: string[];
  frames?: number;
  clips?: Record<string, string>;
}

interface ClipData {
  name: string;
  fps?: number;
  loop?: boolean;
  stationary?: boolean;
}

// A `sheet` Decision names its sheet by the start of its hash, as a sheet's own name is.
function decisionFor(name: string, decisions: StageDetail["decisions"]): SheetData | null {
  let found: SheetData | null = null;
  for (const decision of decisions) {
    if (decision.name !== SHEET_DECISION) continue;
    const data = decision.data as unknown as SheetData;
    if (name.startsWith(data.file) || data.file.startsWith(name)) found = data;
  }
  return found;
}

export function SpriteFramesScreen(props: {
  show: ShowData;
  detail: StageDetail;
  description: StageDescription;
  refreshes: number;
  disabled: boolean;
  onImport: (files: File[], role: ImportRole) => void;
  decide: (name: string, data: Record<string, unknown>, label: string) => void;
}) {
  const { show, detail, description, refreshes } = props;
  const built = useDocument<FramesDocument>(outputOf(detail, "frames.json"), refreshes);
  const sheets = show.sheets ?? [];
  const wanted = String(detail.params.directions ?? "4");
  return (
    <div className="character-screen" data-testid="sprite-frames-screen">
      <h2>Sheets</h2>
      {sheets.length === 0 ? (
        <p className="hint" data-testid="sheets-empty">
          No sheet yet.
        </p>
      ) : (
        <ul className="model-list" data-testid="sheet-list">
          {sheets.map((sheet) => (
            <SheetRow key={sheet.name} sheet={sheet} detail={detail} wanted={wanted} description={description} disabled={props.disabled} decide={props.decide} />
          ))}
        </ul>
      )}
      <FileDrop testid="sheet-drop" accept=".png,.zip" multiple onFiles={(files) => props.onImport(files, "sheet")}>
        Drop a PNG sheet or a ZIP of frames here to add it. Or
      </FileDrop>
      <ClipForm detail={detail} description={description} built={built} disabled={props.disabled} decide={props.decide} />
      {built && (
        <table className="table" data-testid="clip-summary">
          <thead>
            <tr>
              <th>Clip</th>
              <th>Frames in each Direction</th>
              <th>Playback</th>
            </tr>
          </thead>
          <tbody>
            {built.clips.map((clip) => (
              <tr key={clip.name} data-testid={`clip-row-${clip.name}`}>
                <td>{clip.name}</td>
                <td>
                  {Object.entries(clip.directions)
                    .map(([direction, frames]) => `${direction} ${frames.length}`)
                    .join(", ")}
                </td>
                <td>
                  {clip.fps} frames a second, {clip.loop ? "loops" : "plays once"}
                  {clip.stationary ? ", stationary" : ""}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="hint">The frames are shown on fit, which puts them on one grid and one pivot.</p>
    </div>
  );
}

function SheetRow(props: {
  sheet: NonNullable<ShowData["sheets"]>[number];
  detail: StageDetail;
  wanted: string;
  description: StageDescription;
  disabled: boolean;
  decide: (name: string, data: Record<string, unknown>, label: string) => void;
}) {
  const { sheet, detail } = props;
  const zip = sheet.png_count !== null && sheet.png_count !== undefined;
  const decided = decisionFor(sheet.name, detail.decisions);
  const [editing, setEditing] = useState(false);
  return (
    <li data-testid={`sheet-${sheet.name}`} data-state={zip ? "zip" : decided ? "cut" : "uncut"}>
      <span className="model-name" data-testid={`sheet-name-${sheet.name}`}>
        {sheet.imported_as ?? basename(sheet.file)} <small title="The stored file">{sheet.name.slice(0, 8)}</small>
      </span>{" "}
      <span>
        {zip ? `ZIP, ${sheet.png_count} PNGs` : "PNG"}
        {sheet.size !== undefined ? `, ${readableSize(sheet.size)}` : ""}
      </span>{" "}
      {zip && <span>(its clips and Directions are read from its names)</span>}
      {!zip && decided && (
        <span data-testid={`sheet-cut-${sheet.name}`}>
          cut as {decided.clip}: {decided.layout}, {decided.directions?.join(" ")}, {decided.frames} {decided.frames === 1 ? "frame" : "frames"}{" "}
          <button className="link" data-testid={`sheet-recut-${sheet.name}`} onClick={() => setEditing(!editing)}>
            change
          </button>
        </span>
      )}
      {!zip && (!decided || editing) && (
        <SheetForm sheet={sheet} start={decided} wanted={props.wanted} description={props.description} disabled={props.disabled} decide={props.decide} onDone={() => setEditing(false)} />
      )}
    </li>
  );
}

// How a PNG is cut: one `sheet` Decision.
function SheetForm(props: {
  sheet: { name: string };
  start: SheetData | null;
  wanted: string;
  description: StageDescription;
  disabled: boolean;
  decide: (name: string, data: Record<string, unknown>, label: string) => void;
  onDone: () => void;
}) {
  const entry = props.description.decisions.find((item) => item.name === SHEET_DECISION);
  const variants = (entry?.entry_schema as { oneOf?: { properties?: { clip?: { pattern?: string } } }[] } | undefined)?.oneOf ?? [];
  const pattern = variants.map((variant) => variant.properties?.clip?.pattern).find((value) => value);
  const namePattern = pattern ? new RegExp(pattern) : null;
  const [clip, setClip] = useState(props.start?.clip ?? "idle");
  const [layout, setLayout] = useState<"rows" | "columns">(props.start?.layout ?? "rows");
  const [directions, setDirections] = useState((props.start?.directions ?? ORDER[props.wanted] ?? ORDER["4"]).join(" "));
  const [frames, setFrames] = useState(String(props.start?.frames ?? 1));
  const list = directions.split(/[\s,]+/).filter(Boolean);
  const count = Number(frames);
  const badDirection = list.find((name) => !COMPASS.includes(name)) ?? (new Set(list).size !== list.length ? "twice" : null);
  const problem = !clip.trim()
    ? "Name the clip."
    : namePattern && !namePattern.test(clip.trim())
      ? "A clip's name is lower-case snake_case and doesn't end in a Direction."
      : list.length === 0
        ? "Give the Directions, in the sheet's order."
        : badDirection
          ? `Directions are ${COMPASS.join(", ")}, each once.`
          : !Number.isInteger(count) || count < 1
            ? "Give the number of frames."
            : null;
  return (
    <fieldset disabled={props.disabled} className="bone-form" data-testid={`sheet-form-${props.sheet.name}`}>
      <p className="hint">Say how this sheet is cut: each {layout === "rows" ? "row is one Direction and its frames run across" : "column is one Direction and its frames run down"}.</p>
      <div className="param">
        <label htmlFor={`sheet-clip-${props.sheet.name}`}>Clip</label>
        <input id={`sheet-clip-${props.sheet.name}`} data-testid="sheet-clip" value={clip} onChange={(event) => setClip(event.target.value)} />
      </div>
      <div className="param">
        <label htmlFor={`sheet-layout-${props.sheet.name}`}>Layout</label>
        <select id={`sheet-layout-${props.sheet.name}`} data-testid="sheet-layout" value={layout} onChange={(event) => setLayout(event.target.value as "rows" | "columns")}>
          <option value="rows">One Direction per row</option>
          <option value="columns">One Direction per column</option>
        </select>
      </div>
      <div className="param">
        <label htmlFor={`sheet-directions-${props.sheet.name}`}>Directions, in order</label>
        <input id={`sheet-directions-${props.sheet.name}`} data-testid="sheet-directions" value={directions} onChange={(event) => setDirections(event.target.value)} />
      </div>
      <div className="param">
        <label htmlFor={`sheet-frames-${props.sheet.name}`}>Frames</label>
        <input id={`sheet-frames-${props.sheet.name}`} data-testid="sheet-frames" type="number" min={1} value={frames} onChange={(event) => setFrames(event.target.value)} />
      </div>
      {problem && (
        <p className="hint" data-testid="sheet-problem">
          {problem}
        </p>
      )}
      <button
        data-testid="sheet-cut"
        disabled={problem !== null}
        onClick={() => {
          props.decide(
            SHEET_DECISION,
            { file: props.sheet.name, clip: clip.trim(), layout, directions: list, frames: count },
            `Cutting the sheet into ${clip.trim()}`,
          );
          props.onDone();
        }}
      >
        Cut the sheet
      </button>
    </fieldset>
  );
}

// A clip's playback: one `clip` Decision under its name (deciding it again changes it).
function ClipForm(props: {
  detail: StageDetail;
  description: StageDescription;
  built: FramesDocument | null;
  disabled: boolean;
  decide: (name: string, data: Record<string, unknown>, label: string) => void;
}) {
  const { detail, built } = props;
  const latest = new Map<string, ClipData>();
  for (const decision of detail.decisions) {
    if (decision.name === CLIP_DECISION) {
      const data = decision.data as unknown as ClipData;
      latest.set(data.name, data);
    }
  }
  const pattern = props.description.decisions.find((item) => item.name === CLIP_DECISION)?.entry_schema?.properties?.name?.pattern;
  const namePattern = pattern ? new RegExp(pattern) : null;
  const [name, setName] = useState("");
  const [fps, setFps] = useState("8");
  const [loop, setLoop] = useState(true);
  const [stationary, setStationary] = useState(false);
  const known = built?.clips.map((clip) => clip.name) ?? [];

  function choose(value: string) {
    setName(value);
    const decided = latest.get(value);
    const source = built?.clips.find((clip) => clip.name === value);
    const from = decided ?? (source ? { fps: source.fps, loop: source.loop, stationary: source.stationary } : null);
    if (from) {
      setFps(String(from.fps ?? 8));
      setLoop(from.loop ?? true);
      setStationary(from.stationary ?? false);
    }
  }
  const rate = Number(fps);
  const problem = !name.trim()
    ? "Name the clip."
    : namePattern && !namePattern.test(name.trim())
      ? "A clip's name is lower-case snake_case and doesn't end in a Direction."
      : !Number.isInteger(rate) || rate < 1
        ? "The frame rate is a whole number, 1 or more."
        : null;
  return (
    <fieldset disabled={props.disabled} className="bone-form" data-testid="clip-form">
      <h2>Clip playback</h2>
      <p className="hint">A clip with no setting plays at 8 frames a second and loops; a one-frame clip is stationary.</p>
      <div className="param">
        <label htmlFor="sprite-clip-name">Clip</label>
        <input id="sprite-clip-name" data-testid="clip-name" list="sprite-clips" value={name} onChange={(event) => choose(event.target.value)} />
        <datalist id="sprite-clips">
          {known.map((entry) => (
            <option key={entry} value={entry} />
          ))}
        </datalist>
      </div>
      <div className="param">
        <label htmlFor="sprite-clip-fps">Frames a second</label>
        <input id="sprite-clip-fps" data-testid="clip-fps" type="number" min={1} value={fps} onChange={(event) => setFps(event.target.value)} />
      </div>
      <label className="toggle">
        <input type="checkbox" data-testid="clip-loop" checked={loop} onChange={(event) => setLoop(event.target.checked)} />
        Loops
      </label>
      <label className="toggle">
        <input type="checkbox" data-testid="clip-stationary" checked={stationary} onChange={(event) => setStationary(event.target.checked)} />
        Stationary (held to the pivot-drift Check)
      </label>
      {problem && name.trim() && (
        <p className="hint" data-testid="clip-problem">
          {problem}
        </p>
      )}
      <button
        data-testid="clip-set"
        disabled={problem !== null}
        onClick={() => props.decide(CLIP_DECISION, { name: name.trim(), fps: rate, loop, stationary }, `Setting the clip ${name.trim()}`)}
      >
        Set the clip
      </button>
      {latest.size > 0 && (
        <ul data-testid="clip-decisions">
          {[...latest.values()].map((clip) => (
            <li key={clip.name}>
              <button className="link" onClick={() => choose(clip.name)}>
                {clip.name}
              </button>
              : {clip.fps ?? 8} frames a second, {clip.loop === false ? "plays once" : "loops"}
              {clip.stationary ? ", stationary" : ""}
            </li>
          ))}
        </ul>
      )}
    </fieldset>
  );
}
