// A character's first three Stages (spec §6.3, §11): the Model, the rig and the clips. They have no image to draw on, so each
// is a screen of files and a form, and the Stage panel beside it stays the shared one (params, Decisions, Checks, the
// primary action). Everything here is a Command: `import` with a role, `pick`, `decide` for a `bone` or a `clip`, and the
// read-only `inspect` Probe, which lists a file's actions and bones (it starts Blender, so it is shown and can be cancelled).

import { useEffect, useRef, useState, type DragEvent, type ReactNode } from "react";
import { call, cancelJob, fileUrl, type Envelope, type HeldThing, type FileEntry, type ShowData, type StageDescription, type StageDetail } from "./api";

export const CHARACTER_KIND = "character";
export const MODEL_STAGE = "model";
export const RIG_STAGE = "rig";
export const CLIPS_STAGE = "clips";
export const CHARACTER_SCREENS = [MODEL_STAGE, RIG_STAGE, CLIPS_STAGE];
export const BONE_DECISION = "bone";
export const CLIP_DECISION = "clip";
export const TRANSITION_DECISION = "transition";

export type ImportRole = "variant" | "clip-source" | "rigged" | "sheet" | "parameters" | "thing";
export const MODEL_FILES = ".glb,.fbx,.blend";
export const PARAMETER_FILES = ".toml,.json";
export const REMOVE_DECISION = "remove";
const BASE_MISMATCH = "rig.base_mismatch"; // the rig's finding when the Model's skeleton isn't its base's

interface ModelDocument {
  source: string;
  bounds: { min: number[]; max: number[] };
  armature: string | null;
  bones: string[];
  fps?: number; // the file's frame rate; absent in a model.json built before it was recorded
  actions: { name: string; start: number; end: number }[];
}

interface RigDocument {
  source: "model" | "rigged";
  file: string;
  armature: string;
  mapping: Record<string, string>;
  bones: number;
}

interface ClipsDocument {
  clips: { name: string; frames: number[]; root_motion: boolean; stationary: boolean }[];
}

export function outputOf(detail: StageDetail | undefined, name: string): string | null {
  return detail?.outputs.find((path) => path.endsWith(`/${name}`)) ?? null;
}

// A file the Stage built, read through the file route. It is read again whenever `key` changes (every refresh).
export function useDocument<T>(path: string | null, key: unknown): T | null {
  const [found, setFound] = useState<{ path: string; value: T } | null>(null);
  useEffect(() => {
    if (!path) return;
    let live = true;
    fetch(fileUrl(path, 0), { cache: "no-store" })
      .then((response) => (response.ok ? (response.json() as Promise<T>) : null))
      .then((value) => live && setFound(value ? { path, value } : null))
      .catch(() => live && setFound(null));
    return () => {
      live = false;
    };
  }, [path, key]);
  return path && found?.path === path ? found.value : null;
}

// What the `inspect` Probe says a character's file holds (ticket 0123).
interface FileRead {
  file: string;
  armature: string | null;
  bones: string[];
  fps: number;
  actions: { name: string; short: string; start: number; end: number }[];
}

const INSPECT_PROBE = "inspect";
// Answers are kept for the page's life: a file's stored name holds its content hash, so a name never means another file.
const fileReads = new Map<string, FileRead>();

// Reads the named files with the Probe, one at a time (each starts Blender, which is slow the first time). `reading` names
// the file being read; `cancel` stops the read and the ones after it, and `retry` starts again.
function useFileReads(asset: string, files: { name: string; path: string }[], enabled: boolean) {
  const [, tick] = useState(0);
  const [state, setState] = useState<{ reading: string | null; stopped: boolean; failed: string | null }>({
    reading: null,
    stopped: false,
    failed: null,
  });
  const job = useRef<string | null>(null);
  const [round, setRound] = useState(0);
  const key = files.map((file) => `${file.name}=${file.path}`).join("|");
  useEffect(() => {
    if (!enabled) return;
    let live = true;
    const wanted = files.filter((file) => !fileReads.has(`${asset}/${file.path}`));
    if (wanted.length === 0) {
      setState({ reading: null, stopped: false, failed: null });
      return;
    }
    void (async () => {
      let failed: string | null = null; // a file that can't be read doesn't stop the others
      for (const file of wanted) {
        if (!live) return;
        const id = crypto.randomUUID();
        job.current = id;
        setState({ reading: file.name, stopped: false, failed: null });
        let result: Envelope<{ result: FileRead }>;
        try {
          result = await call("probe", { name: INSPECT_PROBE, asset, args: [file.name] }, id);
        } catch {
          job.current = null;
          failed ??= `Couldn't read ${file.name}.`;
          continue;
        }
        job.current = null;
        if (!live) return;
        if (!result.ok || !result.data) {
          if (result.findings.some((finding) => finding.code === "run.cancelled")) {
            setState({ reading: null, stopped: true, failed: null });
            return;
          }
          failed ??= result.findings[0]?.message ?? `Couldn't read ${file.name}.`;
          continue;
        }
        fileReads.set(`${asset}/${file.path}`, result.data.result);
        tick((count) => count + 1);
      }
      if (live) setState({ reading: null, stopped: false, failed });
    })();
    return () => {
      live = false;
      if (job.current) void cancelJob(job.current);
      job.current = null;
    };
    // `files` is read through `key`: a new array each render must not start another read.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [asset, key, enabled, round]);
  const read = (path: string): FileRead | null => fileReads.get(`${asset}/${path}`) ?? null;
  return {
    read,
    reading: state.reading,
    stopped: state.stopped,
    failed: state.failed,
    cancel: () => {
      if (job.current) void cancelJob(job.current);
    },
    retry: () => setRound((count) => count + 1),
  };
}

// Shows that a file is being read, and lets the Owner stop it.
function ReadingNote(props: { reads: ReturnType<typeof useFileReads> }) {
  const { reads } = props;
  if (reads.reading)
    return (
      <p className="hint file-reading" data-testid="file-reading">
        Reading {reads.reading} (the first read takes a few seconds)…{" "}
        <button data-testid="file-reading-cancel" onClick={reads.cancel}>
          Cancel
        </button>
      </p>
    );
  if (reads.stopped || reads.failed)
    return (
      <p className="hint" data-testid="file-read-stopped">
        {reads.stopped ? "Reading was cancelled." : reads.failed}{" "}
        <button className="link" data-testid="file-read-retry" onClick={reads.retry}>
          Read again
        </button>
      </p>
    );
  return null;
}

export function readableSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function basename(path: string): string {
  return path.split("/").at(-1) ?? path;
}

// A drop target that is also a button: dropped or chosen files go to `onFiles`.
export function FileDrop(props: { testid: string; accept: string; multiple?: boolean; onFiles: (files: File[]) => void; children: ReactNode }) {
  const [over, setOver] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  function drop(event: DragEvent) {
    event.preventDefault();
    setOver(false);
    props.onFiles([...event.dataTransfer.files]);
  }
  return (
    <div
      className="file-drop"
      data-testid={props.testid}
      data-over={over}
      onDragOver={(event) => {
        event.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={drop}
    >
      <p className="hint">
        {props.children}{" "}
        <button className="link" onClick={() => input.current?.click()}>
          choose files
        </button>
        .
      </p>
      <input
        ref={input}
        data-testid={`${props.testid}-input`}
        type="file"
        accept={props.accept}
        multiple={props.multiple}
        hidden
        onChange={(event) => {
          props.onFiles([...(event.target.files ?? [])]);
          event.target.value = "";
        }}
      />
    </div>
  );
}

// A link to the character this one is made from (ADR 0012).
function BaseLink(props: { base: string; onOpen: (asset: string) => void }) {
  return (
    <p data-testid="base-note">
      Made from{" "}
      <button className="link" data-testid="base-link" onClick={() => props.onOpen(props.base)}>
        {props.base}
      </button>
      : it takes the base's skeleton, clips and Stage parameters unless it sets its own.
    </p>
  );
}

// The Model: its Variants as a list, each with its file's name and size and, for the one `model` built, its bounds.
function ModelScreen(props: {
  show: ShowData;
  detail: StageDetail;
  refreshes: number;
  onPick: (variant: string) => void;
  onImport: (files: File[], role: ImportRole) => void;
  onOpen: (asset: string) => void;
}) {
  const { show, detail, refreshes } = props;
  const model = useDocument<ModelDocument>(outputOf(detail, "model.json"), refreshes);
  const still = outputOf(detail, "still.png");
  return (
    <div className="character-screen" data-testid="model-screen">
      <h2>{show.parameters ? "Model" : "Models"}</h2>
      {show.base && <BaseLink base={show.base} onOpen={props.onOpen} />}
      {still && model && (
        <img className="model-still" data-testid="model-still" alt={`The picked Model, ${model.source}`} src={fileUrl(still, refreshes)} />
      )}
      {show.parameters ? (
        <div data-testid="parameters">
          <p>
            Built from the parameter file <code data-testid="parameters-name">{show.parameters.imported_as ?? basename(show.parameters.file)}</code>{" "}
            {show.parameters.size !== undefined && <small>{readableSize(show.parameters.size)}</small>} by the Project's generator. There is
            nothing to pick.
          </p>
          <FileDrop testid="parameters-drop" accept={PARAMETER_FILES} onFiles={(files) => props.onImport(files.slice(0, 1), "parameters")}>
            Drop another .toml or .json parameter file here to replace it. Or
          </FileDrop>
        </div>
      ) : show.variants.length === 0 ? (
        <p className="hint">No Model yet.</p>
      ) : (
        <ul className="model-list" data-testid="model-list">
          {show.variants.map((variant, index) => (
            <ModelRow
              key={variant.name}
              variant={variant}
              index={index}
              picked={show.picked === variant.name}
              bounds={model && model.source === basename(variant.file) ? model.bounds : null}
              onPick={props.onPick}
            />
          ))}
        </ul>
      )}
      {!show.parameters && (
        <FileDrop testid="model-drop" accept={MODEL_FILES} multiple onFiles={(files) => props.onImport(files, "variant")}>
          Drop a .glb, .fbx or .blend Model here to add it, then pick it with its number key. Or
        </FileDrop>
      )}
      {!show.parameters && show.variants.length === 0 && (
        <FileDrop testid="parameters-start-drop" accept={PARAMETER_FILES} onFiles={(files) => props.onImport(files.slice(0, 1), "parameters")}>
          Or drop a .toml or .json parameter file here, for a Model the Project's generator builds. Or
        </FileDrop>
      )}
      <p className="hint">There is no 3D view: the render Stage shows the character.</p>
    </div>
  );
}

function ModelRow(props: {
  variant: FileEntry;
  index: number;
  picked: boolean;
  bounds: ModelDocument["bounds"] | null;
  onPick: (variant: string) => void;
}) {
  const { variant, index, picked, bounds } = props;
  const size = variant.size ?? null;
  return (
    <li>
      <button className="variant model-row" data-testid={`variant-${variant.name}`} aria-pressed={picked} onClick={() => props.onPick(variant.name)}>
        {index < 9 && <kbd>{index + 1}</kbd>}
        <span className="model-name" data-testid={`variant-name-${variant.name}`}>
          {variant.imported_as ?? basename(variant.file)}{" "}
          {variant.imported_as && <small title="The stored file">{basename(variant.file)}</small>}
        </span>
        <span data-testid={`variant-size-${variant.name}`}>{size === null ? "" : readableSize(size)}</span>
        <span data-testid={`variant-bounds-${variant.name}`}>
          {bounds ? `bounds ${bounds.max.map((top, axis) => (top - bounds.min[axis]).toFixed(2)).join(" × ")}` : ""}
        </span>
        {picked && <span>picked</span>}
      </button>
    </li>
  );
}

// "Rig it ... 1. Upload ... 2. ..." -> the sentence before the steps, and the steps.
export function numberedSteps(text: string): { intro: string; steps: string[] } {
  const [intro, ...steps] = text.split(/\s(?=\d+\.\s)/);
  return { intro, steps: steps.map((step) => step.replace(/^\d+\.\s+/, "")) };
}

const ROLE_LABELS: Record<string, string> = {
  hips: "hips",
  spine: "spine",
  head: "head",
  left_arm: "left arm",
  right_arm: "right arm",
  left_leg: "left leg",
  right_leg: "right leg",
  left_foot: "left foot",
  right_foot: "right foot",
};

function RigScreen(props: {
  show: ShowData;
  detail: StageDetail;
  description: StageDescription;
  ownerAction: string | null;
  refreshes: number;
  disabled: boolean;
  onImport: (files: File[], role: ImportRole) => void;
  decide: (name: string, data: Record<string, unknown>, label: string) => void;
  onOpen: (asset: string) => void;
}) {
  const { show, detail, description, ownerAction, refreshes } = props;
  const rig = useDocument<RigDocument>(outputOf(detail, "rig.json"), refreshes);
  const upload = outputOf(show.stages.find((entry) => entry.stage === MODEL_STAGE), "mixamo_upload.fbx");
  const mapped = detail.decisions.filter((decision) => decision.name === BONE_DECISION);
  const roles = description.decisions.find((entry) => entry.name === BONE_DECISION)?.entry_schema?.properties?.role?.enum ?? [];
  const [role, setRole] = useState("");
  const [bone, setBone] = useState("");
  const chosenRole = role || roles[0] || "";
  // A character made from a base needs no Mixamo trip: its Model carries the base's skeleton.
  const steps = ownerAction && !show.base ? numberedSteps(ownerAction) : null;
  // The bones to choose from are the rig's: the rigged file's if there is one, else the picked Model's.
  const rigFile = show.rigged ?? show.variants.find((variant) => variant.name === show.picked) ?? null;
  const formShown = (detail.status === "failed" || mapped.length > 0) && roles.length > 0;
  const reads = useFileReads(show.asset, rigFile ? [{ name: rigFile.name, path: rigFile.file }] : [], formShown && rigFile !== null);
  const bones = rigFile ? (reads.read(rigFile.file)?.bones ?? []) : [];
  return (
    <div className="character-screen" data-testid="rig-screen">
      <h2>Rig</h2>
      {show.base && <BaseLink base={show.base} onOpen={props.onOpen} />}
      {show.base && (
        <p className="hint" data-testid="base-rig-note">
          The Model's own armature must have the base's bones, by name and under the same parents. Extra bones are fine, and rest
          proportions may differ. No rigged file is needed.
        </p>
      )}
      {detail.failure_code === BASE_MISMATCH && (
        <p className="reason" data-testid="base-mismatch" data-code={detail.failure_code}>
          {detail.failure_code}: {detail.reason}
        </p>
      )}
      {rig && (
        <div data-testid="rig-summary">
          <p>
            {rig.source === "rigged" ? "The rigged file from Mixamo" : "The Model's own rig"}: {rig.file}, armature {rig.armature},{" "}
            {rig.bones} bones.
          </p>
          <table className="table" data-testid="rig-mapping">
            <thead>
              <tr>
                <th>Role</th>
                <th>Bone</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(rig.mapping).map(([name, boneName]) => (
                <tr key={name}>
                  <td>{ROLE_LABELS[name] ?? name}</td>
                  <td>{boneName}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {steps && steps.steps.length > 0 && (
        <div data-testid="mixamo">
          <p>{steps.intro}</p>
          <ol data-testid="mixamo-steps">
            {steps.steps.map((step, index) => (
              <li key={index}>{step}</li>
            ))}
          </ol>
        </div>
      )}
      {steps && steps.steps.length === 0 && <p data-testid="rig-owner-action">{ownerAction}</p>}
      {show.base && ownerAction && <p data-testid="rig-owner-action">{ownerAction}</p>}
      {upload && !show.base && (
        <p>
          The file to upload to Mixamo: <code data-testid="upload-path">{upload}</code>{" "}
          <a href={fileUrl(upload, 0)} download data-testid="upload-link">
            Download
          </a>
        </p>
      )}
      {show.rigged && (
        <p data-testid="rigged-file">
          Rigged file: <code>{basename(show.rigged.file)}</code>
        </p>
      )}
      {!show.base && (
        <FileDrop testid="rigged-drop" accept={MODEL_FILES} onFiles={(files) => props.onImport(files.slice(0, 1), "rigged")}>
          Drop the rigged file that came back from Mixamo here. Or
        </FileDrop>
      )}
      {formShown && <ReadingNote reads={reads} />}
      {formShown && (
        <fieldset disabled={props.disabled} className="bone-form">
          <h2>Map a bone</h2>
          <p className="hint">For a rig that doesn't use Mixamo's bone names: say which bone has each role.</p>
          <div className="param">
            <label htmlFor="bone-role">Role</label>
            <select id="bone-role" data-testid="bone-role" value={chosenRole} onChange={(event) => setRole(event.target.value)}>
              {roles.map((name) => (
                <option key={name} value={name}>
                  {ROLE_LABELS[name] ?? name}
                </option>
              ))}
            </select>
          </div>
          <div className="param">
            <label htmlFor="bone-name">Bone</label>
            {bones.length > 0 ? (
              <select id="bone-name" data-testid="bone-name" value={bone} onChange={(event) => setBone(event.target.value)}>
                <option value="">Choose a bone</option>
                {bones.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
            ) : (
              <input id="bone-name" data-testid="bone-name" value={bone} onChange={(event) => setBone(event.target.value)} />
            )}
          </div>
          <button
            data-testid="bone-add"
            disabled={!bone.trim()}
            onClick={() => {
              props.decide(BONE_DECISION, { role: chosenRole, bone: bone.trim() }, `Mapping ${chosenRole} to ${bone.trim()}`);
              setBone("");
            }}
          >
            Map bone
          </button>
          {mapped.length > 0 && (
            <ul data-testid="bone-decisions">
              {mapped.map((decision) => (
                <li key={decision.id}>
                  {String(decision.data.role)} → {String(decision.data.bone)}
                </li>
              ))}
            </ul>
          )}
        </fieldset>
      )}
    </div>
  );
}

interface ClipData {
  name: string;
  source: string;
  start: number;
  end: number;
  fps: number;
  loop: boolean;
  stationary?: boolean;
  speed?: number;
  still?: number;
  blink?: number[];
  wink_left?: number[];
  wink_right?: number[];
  attach?: Attach[];
}

// What a clip holds (ticket 0300): the thing, the rig's bone it sits at, and an optional shift and turn from that bone.
interface Attach {
  thing: string;
  socket: string;
  offset?: number[];
  turn?: number[];
}

type Triple = [string, string, string];

// An `attach` row as the form edits it: the three numbers of the offset and of the turn are text until saved.
interface AttachRow {
  thing: string;
  socket: string;
  offset: Triple;
  turn: Triple;
}

const DEFAULT_SOCKET = "grip_r";
const AXES = ["x", "y", "z"] as const;
const NO_NUMBERS: Triple = ["", "", ""];

function rowOf(held: Attach): AttachRow {
  const texts = (values?: number[]): Triple => (values ? [String(values[0]), String(values[1]), String(values[2])] : NO_NUMBERS);
  return { thing: held.thing, socket: held.socket, offset: texts(held.offset), turn: texts(held.turn) };
}

// A triple is empty (null, not given), or three numbers (a blank one beside a number is 0); undefined when one isn't a number.
function triple(texts: Triple): number[] | null | undefined {
  if (texts.every((text) => !text.trim())) return null;
  const numbers = texts.map((text) => (text.trim() ? Number(text) : 0));
  return numbers.every((number) => Number.isFinite(number)) ? numbers : undefined;
}

function attachOf(rows: AttachRow[]): Attach[] {
  return rows.map((row) => {
    const held: Attach = { thing: row.thing, socket: row.socket.trim() || DEFAULT_SOCKET };
    const offset = triple(row.offset);
    const turn = triple(row.turn);
    if (offset) held.offset = offset;
    if (turn) held.turn = turn;
    return held;
  });
}

interface TransitionData {
  name: string;
  from: { clip: string; frame?: number };
  to: { clip: string; frame?: number };
  length?: number;
  fps?: number;
}

const EYELIDS = [
  { key: "blink", label: "Blink", mark: "B" },
  { key: "wink_left", label: "Wink left", mark: "L" },
  { key: "wink_right", label: "Wink right", mark: "R" },
] as const;
type Eyelid = (typeof EYELIDS)[number]["key"];
type Marks = Record<Eyelid, number[]>;
const NO_MARKS: Marks = { blink: [], wink_left: [], wink_right: [] };

// A clip's timing, said short: what the row shows beside its range.
function timing(clip: ClipData): string {
  const parts: string[] = [];
  if (clip.still) parts.push(`still ${clip.still}`);
  if (clip.speed && clip.speed !== 1) parts.push(`speed ${clip.speed}`);
  for (const lid of EYELIDS) {
    const frames = clip[lid.key];
    if (frames && frames.length > 0) parts.push(`${lid.key.replace("_", " ")} ${frames.join(", ")}`);
  }
  return parts.join("; ");
}

// How many frames a clip's range gives at its frame rate: `sample_frames` in kiripix/recipes/clips.py, which a render samples. A
// looping clip ends before `end` (its first pose again); one that doesn't loop ends on it. Python's `round` takes a half to the
// even number, which `Math.round` doesn't, so it's written out.
function roundHalfEven(value: number): number {
  const floor = Math.floor(value);
  const diff = value - floor;
  if (diff < 0.5) return floor;
  if (diff > 0.5) return floor + 1;
  return floor % 2 === 0 ? floor : floor + 1;
}

export function sampleCount(start: number, end: number, sourceFps: number, fps: number, loop: boolean, speed = 1): number {
  const step = (sourceFps * speed) / fps;
  const span = end - start;
  return loop ? Math.max(1, roundHalfEven(span / step)) : Math.floor(span / step + 1e-9) + 1;
}

// The transitions (ticket 0218) and the form that decides one. A transition is a clip of its own between two poses, so it is
// listed beside the clips; the Decision's own Checks say when a frame is out of range or a clip is missing.
function TransitionsPanel(props: {
  transitions: (TransitionData & { fromBase: boolean })[];
  clips: string[];
  frames: Record<string, number>; // a built clip's frame count, once `clips` has run
  pattern: RegExp | null;
  disabled: boolean;
  decide: (name: string, data: Record<string, unknown>, label: string) => void;
}) {
  const [name, setName] = useState("");
  const [fromClip, setFromClip] = useState("");
  const [fromFrame, setFromFrame] = useState("");
  const [toClip, setToClip] = useState("");
  const [toFrame, setToFrame] = useState("");
  const [length, setLength] = useState("3");
  const [fps, setFps] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const whole = (text: string) => /^\d+$/.test(text.trim());

  function stop() {
    setEditing(null);
    setName("");
    setFromClip("");
    setFromFrame("");
    setToClip("");
    setToFrame("");
    setLength("3");
    setFps("");
  }

  function edit(entry: TransitionData) {
    setEditing(entry.name);
    setName(entry.name);
    setFromClip(entry.from.clip);
    setFromFrame(entry.from.frame === undefined ? "" : String(entry.from.frame));
    setToClip(entry.to.clip);
    setToFrame(entry.to.frame === undefined ? "" : String(entry.to.frame));
    setLength(String(entry.length ?? 3));
    setFps(entry.fps === undefined ? "" : String(entry.fps));
  }

  const problem = !name
    ? "Name the transition."
    : props.pattern && !props.pattern.test(name)
      ? "A transition's name is lower-case letters, digits and underscores, and doesn't end in a direction."
      : !fromClip || !toClip
        ? "Choose the clip it starts from and the clip it ends on."
        : (fromFrame.trim() && !whole(fromFrame)) || (toFrame.trim() && !whole(toFrame))
          ? "A frame is a whole number, from 0, or empty."
          : !whole(length) || Number(length) < 1
            ? "The length is a whole number of frames, 1 or more."
            : fps.trim() && (!whole(fps) || Number(fps) < 1)
              ? "The frame rate is a whole number, 1 or more, or empty."
              : null;
  const range = (clip: string) => (props.frames[clip] ? ` (frames 0 to ${props.frames[clip] - 1})` : "");

  function send() {
    const data: Record<string, unknown> = {
      name,
      from: { clip: fromClip, ...(fromFrame.trim() ? { frame: Number(fromFrame) } : {}) },
      to: { clip: toClip, ...(toFrame.trim() ? { frame: Number(toFrame) } : {}) },
      length: Number(length),
    };
    if (fps.trim()) data.fps = Number(fps);
    props.decide(TRANSITION_DECISION, data, editing ? `Changing the transition ${name}` : `Adding the transition ${name}`);
    stop();
  }

  const end = (value: { clip: string; frame?: number }, fallback: string) => `${value.clip}, frame ${value.frame ?? fallback}`;

  return (
    <div data-testid="transitions">
      <h2>Transitions</h2>
      {props.transitions.length === 0 ? (
        <p className="hint" data-testid="transitions-empty">No transitions yet. A transition is a clip that blends one clip's pose into another's.</p>
      ) : (
        <table className="table" data-testid="transitions-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>From</th>
              <th>To</th>
              <th>Length</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {props.transitions.map((entry) => (
              <tr key={entry.name} data-testid={`transition-row-${entry.name}`} data-from-base={entry.fromBase}>
                <td>
                  {entry.name}
                  {entry.fromBase && (
                    <>
                      {" "}
                      <small className="from-base" title="Read-only: the base's transition">
                        the base's
                      </small>
                    </>
                  )}
                </td>
                <td>{end(entry.from, "last")}</td>
                <td>{end(entry.to, "0")}</td>
                <td>{entry.length ?? 3}</td>
                <td>
                  <button data-testid={`transition-edit-${entry.name}`} disabled={props.disabled} onClick={() => edit(entry)}>
                    {entry.fromBase ? "Change on this character" : "Edit"}
                  </button>
                  <button
                    data-testid={`transition-remove-${entry.name}`}
                    disabled={props.disabled}
                    onClick={() => props.decide(REMOVE_DECISION, { name: entry.name }, `Removing the transition ${entry.name}${entry.fromBase ? " here" : ""}`)}
                  >
                    {entry.fromBase ? "Remove here" : "Remove"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <fieldset disabled={props.disabled} className="clip-form">
        <h2>{editing ? `Change the transition ${editing}` : "New transition"}</h2>
        <div className="param">
          <label htmlFor="transition-name">Name</label>
          <input id="transition-name" data-testid="transition-name" value={name} readOnly={editing !== null} placeholder="idle_to_walk" onChange={(event) => setName(event.target.value)} />
        </div>
        <div className="param">
          <label htmlFor="transition-from">From clip</label>
          <select id="transition-from" data-testid="transition-from" value={fromClip} onChange={(event) => setFromClip(event.target.value)}>
            <option value="">Choose a clip</option>
            {props.clips.map((clip) => (
              <option key={clip} value={clip}>
                {clip}
              </option>
            ))}
          </select>
        </div>
        <div className="param">
          <label htmlFor="transition-from-frame">From frame</label>
          <input id="transition-from-frame" data-testid="transition-from-frame" type="number" min={0} placeholder="the last" value={fromFrame} onChange={(event) => setFromFrame(event.target.value)} />
          {fromClip && <small className="hint">{range(fromClip)}</small>}
        </div>
        <div className="param">
          <label htmlFor="transition-to">To clip</label>
          <select id="transition-to" data-testid="transition-to" value={toClip} onChange={(event) => setToClip(event.target.value)}>
            <option value="">Choose a clip</option>
            {props.clips.map((clip) => (
              <option key={clip} value={clip}>
                {clip}
              </option>
            ))}
          </select>
        </div>
        <div className="param">
          <label htmlFor="transition-to-frame">To frame</label>
          <input id="transition-to-frame" data-testid="transition-to-frame" type="number" min={0} placeholder="0" value={toFrame} onChange={(event) => setToFrame(event.target.value)} />
          {toClip && <small className="hint">{range(toClip)}</small>}
        </div>
        <div className="param">
          <label htmlFor="transition-length">Length</label>
          <input id="transition-length" data-testid="transition-length" type="number" min={1} value={length} onChange={(event) => setLength(event.target.value)} />
          <small className="hint">The frames between the two poses, not including them.</small>
        </div>
        <div className="param">
          <label htmlFor="transition-fps">Frame rate</label>
          <input id="transition-fps" data-testid="transition-fps" type="number" min={1} placeholder="the from clip's" value={fps} onChange={(event) => setFps(event.target.value)} />
        </div>
        {problem && name && <p className="hint" data-testid="transition-problem">{problem}</p>}
        <button data-testid="transition-add" disabled={problem !== null} onClick={send}>
          {editing ? "Change transition" : "Add transition"}
        </button>
        {editing && (
          <button data-testid="transition-cancel" onClick={stop}>
            Cancel
          </button>
        )}
      </fieldset>
    </div>
  );
}

function ClipsScreen(props: {
  show: ShowData;
  detail: StageDetail;
  description: StageDescription;
  refreshes: number;
  disabled: boolean;
  onImport: (files: File[], role: ImportRole, extra?: object) => void;
  onRemoveThing: (thing: string) => void;
  decide: (name: string, data: Record<string, unknown>, label: string) => void;
  onOpen: (asset: string) => void;
}) {
  const { show, detail, description, refreshes } = props;
  const built = useDocument<ClipsDocument>(outputOf(detail, "clips.json"), refreshes);
  const rig = useDocument<RigDocument>(outputOf(show.stages.find((entry) => entry.stage === RIG_STAGE), "rig.json"), refreshes);
  const model = useDocument<ModelDocument>(outputOf(show.stages.find((entry) => entry.stage === MODEL_STAGE), "model.json"), refreshes);
  // The Model's own actions are the rig's only while the rig is the Model's own; a rigged file's come from the Probe, as
  // do each animation file's.
  const actions = !show.rigged && rig && rig.source === "model" && model ? model.actions : [];
  const files = [...(show.rigged ? [show.rigged] : []), ...show.clip_sources].map((entry) => ({ name: entry.name, path: entry.file }));
  const reads = useFileReads(show.asset, files, files.length > 0);
  interface Known {
    value: string;
    label: string;
    start: number | null;
    end: number | null;
    fps: number | null;
  }
  // A clip source names an animation file by its stem, and `stem/<full action name>` when the file holds several actions. An
  // action of the rigged file is named by its full name. `clips` reads `stem/...` as a clip source whenever the stem is one, so
  // a rigged action whose name is (or starts with) a clip source's stem can't be named, and isn't offered.
  const known: Known[] = [];
  for (const entry of show.clip_sources) {
    const found = reads.read(entry.file);
    if (!found || found.actions.length === 0) {
      known.push({ value: entry.name, label: entry.name, start: null, end: null, fps: null });
    } else if (found.actions.length === 1) {
      const only = found.actions[0];
      known.push({ value: entry.name, label: `${entry.name} (${only.start}–${only.end})`, start: only.start, end: only.end, fps: found.fps });
    } else {
      for (const action of found.actions) {
        known.push({
          value: `${entry.name}/${action.name}`,
          label: `${entry.name}, ${action.short} (${action.start}–${action.end})`,
          start: action.start,
          end: action.end,
          fps: found.fps,
        });
      }
    }
  }
  const riggedRead = show.rigged ? reads.read(show.rigged.file) : null;
  const stems = new Set(show.clip_sources.map((entry) => entry.name));
  for (const action of riggedRead?.actions ?? []) {
    if (stems.has(action.name.split("/")[0])) continue;
    known.push({ value: action.name, label: `rigged file, ${action.short} (${action.start}–${action.end})`, start: action.start, end: action.end, fps: riggedRead?.fps ?? null });
  }
  for (const action of actions) {
    known.push({ value: action.name, label: `the Model, ${action.name} (${action.start}–${action.end})`, start: action.start, end: action.end, fps: model?.fps ?? null });
  }
  // The clips as the Stage reads them (`show`'s `decisions_as_read`, ticket 0228): one per name, without the removed ones.
  // The base's are marked; a clip decided again here over the base's is the character's own.
  const clips = detail.decisions_as_read
    .filter((decision) => decision.name === CLIP_DECISION)
    .map((decision) => ({ ...(decision.data as unknown as ClipData), fromBase: decision.from_base === true }));
  const pattern = description.decisions.find((entry) => entry.name === CLIP_DECISION)?.entry_schema?.properties?.name?.pattern;
  const namePattern = pattern ? new RegExp(pattern) : null;

  const [name, setName] = useState("");
  const [source, setSource] = useState("");
  const [start, setStart] = useState("0");
  const [end, setEnd] = useState("24");
  const [fps, setFps] = useState("12");
  const [loop, setLoop] = useState(true);
  const [stationary, setStationary] = useState(false);
  const [speed, setSpeed] = useState("1");
  const [still, setStill] = useState("");
  const [marks, setMarks] = useState<Marks>(NO_MARKS);
  const [eyelid, setEyelid] = useState<Eyelid>("blink");
  const [editing, setEditing] = useState<string | null>(null); // the name of the clip the form changes, or null when it adds
  const [attach, setAttach] = useState<AttachRow[]>([]); // what the clip holds
  const [thingId, setThingId] = useState("");
  const [chosenFps, setChosenFps] = useState<number | null>(null);
  const sourceFps = known.find((entry) => entry.value === source.trim())?.fps ?? chosenFps; // the source file's: the clip's is the game's

  function chooseSource(value: string) {
    setSource(value);
    const chosen = known.find((entry) => entry.value === value);
    setChosenFps(chosen?.fps ?? null);
    const action = known.find((entry) => entry.value === value && entry.start !== null);
    if (action && action.start !== null && action.end !== null) {
      setStart(String(action.start));
      setEnd(String(action.end));
    }
  }

  function edit(clip: ClipData) {
    setEditing(clip.name);
    setName(clip.name);
    setSource(clip.source);
    setChosenFps(null);
    setStart(String(clip.start));
    setEnd(String(clip.end));
    setFps(String(clip.fps));
    setLoop(clip.loop);
    setStationary(clip.stationary ?? false);
    setSpeed(String(clip.speed ?? 1));
    setStill(clip.still ? String(clip.still) : "");
    setMarks({ blink: clip.blink ?? [], wink_left: clip.wink_left ?? [], wink_right: clip.wink_right ?? [] });
    setAttach((clip.attach ?? []).map(rowOf));
  }

  function stopEditing() {
    setEditing(null);
    setName("");
    setSpeed("1");
    setStill("");
    setMarks(NO_MARKS);
    setAttach([]);
  }

  function changeRow(index: number, change: Partial<AttachRow>) {
    setAttach(attach.map((row, at) => (at === index ? { ...row, ...change } : row)));
  }

  function toggleFrame(frame: number) {
    const has = marks[eyelid].includes(frame);
    setMarks({ ...marks, [eyelid]: (has ? marks[eyelid].filter((entry) => entry !== frame) : [...marks[eyelid], frame]).sort((a, b) => a - b) });
  }

  // The transitions as the Stage reads them, and which go with a clip if it is removed (`remove` takes them too).
  const transitions = detail.decisions_as_read
    .filter((decision) => decision.name === TRANSITION_DECISION)
    .map((decision) => ({ ...(decision.data as unknown as TransitionData), fromBase: decision.from_base === true }));
  const goWith = (clipName: string) =>
    transitions.filter((entry) => entry.from.clip === clipName || entry.to.clip === clipName).map((entry) => entry.name);

  const whole = (text: string) => /^\d+$/.test(text.trim());
  const problem = !name
    ? "Name the clip."
    : namePattern && !namePattern.test(name)
      ? "A clip's name is lower-case letters, digits and underscores, and doesn't end in a direction (_s, _sw, _w, _nw, _n, _ne, _e, _se)."
      : !source.trim()
        ? "Choose the clip's source."
        : !whole(start) || !whole(end) || !whole(fps) || Number(fps) < 1
          ? "The frames and the frame rate are whole numbers."
          : Number(start) > Number(end)
            ? "The clip starts after it ends."
            : null;
  const things: HeldThing[] = show.things ?? [];
  const attachProblem = attach.some((row) => !row.thing)
    ? "Choose the thing each row holds."
    : new Set(attach.map((row) => row.thing)).size < attach.length
      ? "A clip holds a thing once."
      : attach.some((row) => triple(row.offset) === undefined || triple(row.turn) === undefined)
        ? "The offset and the turn are numbers."
        : null;
  const speedValue = Number(speed);
  const timingProblem =
    !speed.trim() || !(speedValue > 0)
      ? "The speed is a number above 0."
      : still.trim() && !(whole(still) && Number(still) >= 1)
        ? "Still is a whole number of frames, 1 or more, or empty."
        : null;
  const rangeOk = whole(start) && whole(end) && whole(fps) && Number(fps) >= 1 && Number(start) <= Number(end);
  const frameCount =
    still.trim() && whole(still) && Number(still) >= 1
      ? Number(still)
      : sourceFps !== null && rangeOk && speedValue > 0
        ? sampleCount(Number(start), Number(end), sourceFps, Number(fps), loop, speedValue)
        : null;
  const lateMarks =
    frameCount === null ? [] : EYELIDS.flatMap((lid) => marks[lid.key].filter((frame) => frame >= frameCount).map((frame) => `${lid.key.replace("_", " ")} ${frame}`));

  function clipData(): Record<string, unknown> {
    const data: Record<string, unknown> = { name, source: source.trim(), start: Number(start), end: Number(end), fps: Number(fps), loop, stationary };
    if (speedValue !== 1) data.speed = speedValue;
    if (still.trim()) data.still = Number(still);
    for (const lid of EYELIDS) if (marks[lid.key].length > 0) data[lid.key] = marks[lid.key];
    if (attach.length > 0) data.attach = attachOf(attach);
    return data;
  }

  return (
    <div className="character-screen" data-testid="clips-screen">
      <h2>Clips</h2>
      {show.base && <BaseLink base={show.base} onOpen={props.onOpen} />}
      {clips.length === 0 ? (
        <p className="hint" data-testid="clips-empty">No clips yet.</p>
      ) : (
        <table className="table" data-testid="clips-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Source</th>
              <th>Range</th>
              <th>Frame rate</th>
              <th>Loop</th>
              <th>Stationary</th>
              <th>Frames</th>
              <th>Holds</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {clips.map((clip, index) => {
              const made = built?.clips.find((entry) => entry.name === clip.name);
              return (
                <tr key={`${clip.name}-${index}`} data-testid={`clip-row-${clip.name}`} data-from-base={clip.fromBase}>
                  <td>
                    {clip.name}
                    {clip.fromBase && (
                      <>
                        {" "}
                        <small className="from-base" data-testid={`clip-base-${clip.name}`} title="Read-only: the base's clip">
                          the base's
                        </small>
                      </>
                    )}
                  </td>
                  <td>{clip.source}</td>
                  <td>
                    {clip.start}–{clip.end}
                    {timing(clip) && (
                      <small className="hint" data-testid={`clip-timing-${clip.name}`}>
                        {" "}
                        {timing(clip)}
                      </small>
                    )}
                  </td>
                  <td>{clip.fps}</td>
                  <td>{clip.loop ? "loop" : "once"}</td>
                  <td>{clip.stationary ? "yes" : "no"}</td>
                  <td>{made ? `${made.frames.length}${made.root_motion ? " (root moves)" : ""}` : ""}</td>
                  <td data-testid={`clip-holds-${clip.name}`}>{(clip.attach ?? []).map((held) => `${held.thing} at ${held.socket}`).join(", ")}</td>
                  <td>
                    <button data-testid={`clip-edit-${clip.name}`} disabled={props.disabled} onClick={() => edit(clip)}>
                      {clip.fromBase ? "Change on this character" : "Edit"}
                    </button>
                    <button
                      data-testid={`clip-remove-${clip.name}`}
                      disabled={props.disabled}
                      onClick={() => props.decide(REMOVE_DECISION, { name: clip.name }, `Removing the clip ${clip.name}${clip.fromBase ? " here" : ""}`)}
                    >
                      {clip.fromBase ? "Remove here" : "Remove"}
                    </button>
                    {goWith(clip.name).length > 0 && (
                      <small className="hint" data-testid={`clip-remove-takes-${clip.name}`}>
                        {" "}
                        Removing it also removes the transitions {goWith(clip.name).join(", ")}.
                      </small>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}

      <ReadingNote reads={reads} />
      <fieldset disabled={props.disabled} className="clip-form">
        <h2>{editing ? `Change the clip ${editing}` : "Add a clip"}</h2>
        <div className="param">
          <label htmlFor="clip-name">Name</label>
          <input id="clip-name" data-testid="clip-name" value={name} readOnly={editing !== null} onChange={(event) => setName(event.target.value)} />
        </div>
        <div className="param">
          <label htmlFor="clip-source">Source</label>
          <input
            id="clip-source"
            data-testid="clip-source"
            list="clip-sources"
            value={source}
            onChange={(event) => chooseSource(event.target.value)}
          />
          <datalist id="clip-sources">
            {known.map((entry) => (
              <option key={entry.value} value={entry.value}>
                {entry.label}
              </option>
            ))}
          </datalist>
        </div>
        <div className="param">
          <label htmlFor="clip-start">Start frame</label>
          <input id="clip-start" data-testid="clip-start" type="number" min={0} value={start} onChange={(event) => setStart(event.target.value)} />
        </div>
        <div className="param">
          <label htmlFor="clip-end">End frame</label>
          <input id="clip-end" data-testid="clip-end" type="number" min={0} value={end} onChange={(event) => setEnd(event.target.value)} />
        </div>
        <div className="param">
          <label htmlFor="clip-fps">Frame rate</label>
          <input id="clip-fps" data-testid="clip-fps" type="number" min={1} value={fps} onChange={(event) => setFps(event.target.value)} />
          {sourceFps !== null && (
            <small className="hint" data-testid="clip-source-fps">
              The source plays at {sourceFps} frames a second.
            </small>
          )}
        </div>
        <label className="toggle">
          <input type="checkbox" data-testid="clip-loop" checked={loop} onChange={(event) => setLoop(event.target.checked)} />
          Loop
        </label>
        <label className="toggle">
          <input type="checkbox" data-testid="clip-stationary" checked={stationary} onChange={(event) => setStationary(event.target.checked)} />
          Stationary (the feet must not move)
        </label>
        <div className="param">
          <label htmlFor="clip-speed">Speed</label>
          <input id="clip-speed" data-testid="clip-speed" type="number" min={0} step="any" value={speed} onChange={(event) => setSpeed(event.target.value)} />
          <small className="hint">The action plays this many times faster, so the clip has fewer frames.</small>
        </div>
        <div className="param">
          <label htmlFor="clip-still">Still</label>
          <input id="clip-still" data-testid="clip-still" type="number" min={1} value={still} onChange={(event) => setStill(event.target.value)} />
          <small className="hint">Holds the pose at the start frame for this many frames. Empty: the clip plays.</small>
        </div>
        {frameCount !== null ? (
          <p className="hint" data-testid="clip-frame-count">
            {frameCount} frames
          </p>
        ) : null}
        {frameCount !== null && (
          <div className="param" data-testid="clip-strip-box">
            <label htmlFor="clip-eyelid">Eyes closed on</label>
            <select id="clip-eyelid" data-testid="clip-eyelid" value={eyelid} onChange={(event) => setEyelid(event.target.value as Eyelid)}>
              {EYELIDS.map((lid) => (
                <option key={lid.key} value={lid.key}>
                  {lid.label}
                </option>
              ))}
            </select>
            <div className="clip-strip" data-testid="clip-strip">
              {Array.from({ length: frameCount }, (_, frame) => {
                const on = EYELIDS.filter((lid) => marks[lid.key].includes(frame));
                return (
                  <button
                    key={frame}
                    type="button"
                    className={`clip-frame${marks[eyelid].includes(frame) ? " marked" : ""}`}
                    data-testid={`clip-frame-${frame}`}
                    data-marks={on.map((lid) => lid.key).join(" ")}
                    aria-pressed={marks[eyelid].includes(frame)}
                    title={`Frame ${frame}: click to toggle ${eyelid.replace("_", " ")}`}
                    onClick={() => toggleFrame(frame)}
                  >
                    {frame}
                    <small>{on.map((lid) => lid.mark).join("")}</small>
                  </button>
                );
              })}
            </div>
          </div>
        )}
        {lateMarks.length > 0 && (
          <p className="hint" data-testid="clip-late-marks">
            Past the last frame ({frameCount} frames, 0 to {(frameCount ?? 1) - 1}): {lateMarks.join(", ")}. Toggle them off: a still clip refuses them when saved, and another fails its run.
          </p>
        )}
        <h3>Holds</h3>
        {attach.map((row, index) => (
          <div className="param attach-row" key={index} data-testid={`clip-attach-${index}`}>
            <select aria-label="Thing" data-testid={`clip-attach-thing-${index}`} value={row.thing} onChange={(event) => changeRow(index, { thing: event.target.value })}>
              <option value="">Thing</option>
              {things.map((one) => (
                <option key={one.thing} value={one.thing}>
                  {one.thing}
                </option>
              ))}
            </select>
            <input
              aria-label="Socket"
              data-testid={`clip-attach-socket-${index}`}
              list="clip-sockets"
              placeholder={DEFAULT_SOCKET}
              value={row.socket}
              onChange={(event) => changeRow(index, { socket: event.target.value })}
            />
            {(["offset", "turn"] as const).map((field) =>
              AXES.map((axis, at) => (
                <input
                  key={`${field}-${axis}`}
                  aria-label={`${field === "offset" ? "Offset" : "Turn"} ${axis}`}
                  data-testid={`clip-attach-${field}-${axis}-${index}`}
                  className="attach-number"
                  type="number"
                  step="any"
                  placeholder={`${field} ${axis}`}
                  value={row[field][at]}
                  onChange={(event) => {
                    const next: Triple = [...row[field]];
                    next[at] = event.target.value;
                    changeRow(index, { [field]: next });
                  }}
                />
              )),
            )}
            <button type="button" data-testid={`clip-attach-remove-${index}`} onClick={() => setAttach(attach.filter((_, at) => at !== index))}>
              Let go
            </button>
          </div>
        ))}
        <datalist id="clip-sockets">
          <option value={DEFAULT_SOCKET} />
          {(model?.bones ?? []).map((bone) => (
            <option key={bone} value={bone} />
          ))}
        </datalist>
        <button
          type="button"
          data-testid="clip-attach-add"
          disabled={things.length === 0}
          title={things.length === 0 ? "Import a thing first (under Held things)" : undefined}
          onClick={() =>
            setAttach([
              ...attach,
              { thing: things.find((one) => !attach.some((row) => row.thing === one.thing))?.thing ?? "", socket: DEFAULT_SOCKET, offset: NO_NUMBERS, turn: NO_NUMBERS },
            ])
          }
        >
          Hold a thing
        </button>
        {attachProblem && <p className="hint" data-testid="clip-attach-problem">{attachProblem}</p>}
        {timingProblem && <p className="hint" data-testid="clip-timing-problem">{timingProblem}</p>}
        {problem && name && <p className="hint" data-testid="clip-problem">{problem}</p>}
        <button
          data-testid="clip-add"
          disabled={problem !== null || timingProblem !== null || attachProblem !== null}
          onClick={() => {
            props.decide(
              CLIP_DECISION,
              clipData(),
              editing ? `Changing the clip ${name}` : `Adding the clip ${name}`,
            );
            stopEditing();
          }}
        >
          {editing ? "Change clip" : "Add clip"}
        </button>
        {editing && (
          <button data-testid="clip-cancel" onClick={stopEditing}>
            Cancel
          </button>
        )}
      </fieldset>

      <TransitionsPanel
        transitions={transitions}
        clips={clips.map((clip) => clip.name)}
        frames={Object.fromEntries((built?.clips ?? []).map((entry) => [entry.name, entry.frames.length]))}
        pattern={namePattern}
        disabled={props.disabled}
        decide={props.decide}
      />

      <h2>Held things</h2>
      {things.length === 0 ? (
        <p className="hint" data-testid="things-empty">No held things yet.</p>
      ) : (
        <ul data-testid="things">
          {things.map((one) => (
            <li key={one.thing} data-testid={`thing-${one.thing}`}>
              {one.thing} <small>{one.variants.length} {one.variants.length === 1 ? "Variant" : "Variants"}</small>
              {one.materials && one.materials.length > 0 && (
                <small className="hint" data-testid={`thing-materials-${one.thing}`}>
                  {" "}
                  Materials: {one.materials.map((material) => `${material.number}${material.index !== null ? ` (${material.index})` : ""} ${material.name}`).join(", ")}.
                </small>
              )}
              {!one.materials_known && <small className="hint"> Materials are read at the next render.</small>}
              {one.attached_by.length > 0 && (
                <small className="hint" data-testid={`thing-held-by-${one.thing}`}>
                  {" "}
                  Held by {one.attached_by.join(", ")}.
                </small>
              )}{" "}
              <button
                data-testid={`thing-remove-${one.thing}`}
                disabled={props.disabled || one.attached_by.length > 0}
                title={one.attached_by.length > 0 ? "A clip holds it: let go first" : undefined}
                onClick={() => props.onRemoveThing(one.thing)}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="param">
        <label htmlFor="thing-id">Thing</label>
        <input id="thing-id" data-testid="thing-id" placeholder="phone" value={thingId} onChange={(event) => setThingId(event.target.value)} />
      </div>
      {thingId && !/^[a-z0-9_]+$/.test(thingId) && (
        <p className="hint" data-testid="thing-id-problem">A thing's name is lower-case letters, digits and underscores.</p>
      )}
      {thingId && /^[a-z0-9_]+$/.test(thingId) ? (
        <FileDrop testid="thing-drop" accept=".glb,.blend" onFiles={(files) => props.onImport(files, "thing", { thing: thingId })}>
          Drop the thing's mesh (.glb or .blend) here. Its origin and axes are its grip. Dropping it again under the same name adds a Variant. Or
        </FileDrop>
      ) : (
        <p className="hint">Name the thing, then drop its mesh.</p>
      )}

      <h2>Animation files</h2>
      {show.clip_sources.length > 0 && (
        <ul data-testid="clip-sources">
          {show.clip_sources.map((entry) => (
            <li key={entry.name} data-testid={`clip-source-${entry.name}`}>
              {entry.name} <small>{entry.imported_as ?? basename(entry.file)}</small>
              {entry.from_base && (
                <>
                  {" "}
                  <small className="from-base" data-testid={`clip-source-base-${entry.name}`} title="Read-only: in the base's folder">
                    the base's
                  </small>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
      <FileDrop testid="clip-drop" accept={MODEL_FILES} multiple onFiles={(files) => props.onImport(files, "clip-source")}>
        Drop animation files (.fbx from Mixamo, with In Place ticked) here. A clip's source is its file's name. Or
      </FileDrop>
      {actions.length > 0 && (
        <p className="hint">
          The Model's own actions: {actions.map((action) => `${action.name} (${action.start}–${action.end})`).join(", ")}.
        </p>
      )}
      {riggedRead && riggedRead.actions.length > 0 && (
        <p className="hint" data-testid="rigged-actions">
          The rigged file's actions: {riggedRead.actions.map((action) => `${action.short} (${action.start}–${action.end})`).join(", ")}.
        </p>
      )}
    </div>
  );
}

export function CharacterScreen(props: {
  stage: string;
  show: ShowData;
  detail: StageDetail;
  description: StageDescription;
  ownerAction: string | null;
  refreshes: number;
  disabled: boolean;
  onPick: (variant: string) => void;
  onImport: (files: File[], role: ImportRole, extra?: object) => void;
  onRemoveThing: (thing: string) => void;
  decide: (name: string, data: Record<string, unknown>, label: string) => void;
  onOpen: (asset: string) => void;
}) {
  if (props.stage === MODEL_STAGE) return <ModelScreen {...props} />;
  if (props.stage === RIG_STAGE) return <RigScreen {...props} />;
  return <ClipsScreen {...props} />;
}
