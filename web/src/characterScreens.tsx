// A character's first three Stages (spec §6.3, §11): the Model, the rig and the clips. They have no image to draw on, so each
// is a screen of files and a form, and the Stage panel beside it stays the shared one (params, Decisions, Checks, the
// primary action). Everything here is a Command: `import` with a role, `pick`, `decide` for a `bone` or a `clip`, and the
// read-only `inspect` Probe, which lists a file's actions and bones (it starts Blender, so it is shown and can be cancelled).

import { useEffect, useRef, useState, type DragEvent, type ReactNode } from "react";
import { call, cancelJob, fileUrl, type Envelope, type FileEntry, type ShowData, type StageDescription, type StageDetail } from "./api";

export const CHARACTER_KIND = "character";
export const MODEL_STAGE = "model";
export const RIG_STAGE = "rig";
export const CLIPS_STAGE = "clips";
export const CHARACTER_SCREENS = [MODEL_STAGE, RIG_STAGE, CLIPS_STAGE];
export const BONE_DECISION = "bone";
export const CLIP_DECISION = "clip";

export type ImportRole = "variant" | "clip-source" | "rigged" | "sheet";
export const MODEL_FILES = ".glb,.fbx,.blend";

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

// The Model: its Variants as a list, each with its file's name and size and, for the one `model` built, its bounds.
function ModelScreen(props: {
  show: ShowData;
  detail: StageDetail;
  refreshes: number;
  onPick: (variant: string) => void;
  onImport: (files: File[], role: ImportRole) => void;
}) {
  const { show, detail, refreshes } = props;
  const model = useDocument<ModelDocument>(outputOf(detail, "model.json"), refreshes);
  const still = outputOf(detail, "still.png");
  return (
    <div className="character-screen" data-testid="model-screen">
      <h2>Models</h2>
      {still && model && (
        <img className="model-still" data-testid="model-still" alt={`The picked Model, ${model.source}`} src={fileUrl(still, refreshes)} />
      )}
      {show.variants.length === 0 ? (
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
      <FileDrop testid="model-drop" accept={MODEL_FILES} multiple onFiles={(files) => props.onImport(files, "variant")}>
        Drop a .glb, .fbx or .blend Model here to add it, then pick it with its number key. Or
      </FileDrop>
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
}) {
  const { show, detail, description, ownerAction, refreshes } = props;
  const rig = useDocument<RigDocument>(outputOf(detail, "rig.json"), refreshes);
  const upload = outputOf(show.stages.find((entry) => entry.stage === MODEL_STAGE), "mixamo_upload.fbx");
  const mapped = detail.decisions.filter((decision) => decision.name === BONE_DECISION);
  const roles = description.decisions.find((entry) => entry.name === BONE_DECISION)?.entry_schema?.properties?.role?.enum ?? [];
  const [role, setRole] = useState("");
  const [bone, setBone] = useState("");
  const chosenRole = role || roles[0] || "";
  const steps = ownerAction ? numberedSteps(ownerAction) : null;
  // The bones to choose from are the rig's: the rigged file's if there is one, else the picked Model's.
  const rigFile = show.rigged ?? show.variants.find((variant) => variant.name === show.picked) ?? null;
  const formShown = (detail.status === "failed" || mapped.length > 0) && roles.length > 0;
  const reads = useFileReads(show.asset, rigFile ? [{ name: rigFile.name, path: rigFile.file }] : [], formShown && rigFile !== null);
  const bones = rigFile ? (reads.read(rigFile.file)?.bones ?? []) : [];
  return (
    <div className="character-screen" data-testid="rig-screen">
      <h2>Rig</h2>
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
      {upload && (
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
      <FileDrop testid="rigged-drop" accept={MODEL_FILES} onFiles={(files) => props.onImport(files.slice(0, 1), "rigged")}>
        Drop the rigged file that came back from Mixamo here. Or
      </FileDrop>
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

export function sampleCount(start: number, end: number, sourceFps: number, fps: number, loop: boolean): number {
  const step = sourceFps / fps;
  const span = end - start;
  return loop ? Math.max(1, roundHalfEven(span / step)) : Math.floor(span / step + 1e-9) + 1;
}

function ClipsScreen(props: {
  show: ShowData;
  detail: StageDetail;
  description: StageDescription;
  refreshes: number;
  disabled: boolean;
  onImport: (files: File[], role: ImportRole) => void;
  decide: (name: string, data: Record<string, unknown>, label: string) => void;
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
  // One clip per name: a `clip` Decision under a name an earlier one has replaces it, keeping the earlier one's place (0156).
  const latest = new Map<string, ClipData>();
  for (const decision of detail.decisions) {
    if (decision.name === CLIP_DECISION) {
      const data = decision.data as unknown as ClipData;
      latest.set(data.name, data);
    }
  }
  const clips = [...latest.values()];
  const pattern = description.decisions.find((entry) => entry.name === CLIP_DECISION)?.entry_schema?.properties?.name?.pattern;
  const namePattern = pattern ? new RegExp(pattern) : null;

  const [name, setName] = useState("");
  const [source, setSource] = useState("");
  const [start, setStart] = useState("0");
  const [end, setEnd] = useState("24");
  const [fps, setFps] = useState("12");
  const [loop, setLoop] = useState(true);
  const [stationary, setStationary] = useState(false);
  const [editing, setEditing] = useState<string | null>(null); // the name of the clip the form changes, or null when it adds
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
  }

  function stopEditing() {
    setEditing(null);
    setName("");
  }

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

  return (
    <div className="character-screen" data-testid="clips-screen">
      <h2>Clips</h2>
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
              <th></th>
            </tr>
          </thead>
          <tbody>
            {clips.map((clip, index) => {
              const made = built?.clips.find((entry) => entry.name === clip.name);
              return (
                <tr key={`${clip.name}-${index}`} data-testid={`clip-row-${clip.name}`}>
                  <td>{clip.name}</td>
                  <td>{clip.source}</td>
                  <td>
                    {clip.start}–{clip.end}
                  </td>
                  <td>{clip.fps}</td>
                  <td>{clip.loop ? "loop" : "once"}</td>
                  <td>{clip.stationary ? "yes" : "no"}</td>
                  <td>{made ? `${made.frames.length}${made.root_motion ? " (root moves)" : ""}` : ""}</td>
                  <td>
                    <button data-testid={`clip-edit-${clip.name}`} disabled={props.disabled} onClick={() => edit(clip)}>
                      Edit
                    </button>
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
        {sourceFps !== null && whole(start) && whole(end) && whole(fps) && Number(fps) >= 1 && Number(start) <= Number(end) ? (
          <p className="hint" data-testid="clip-frame-count">
            {sampleCount(Number(start), Number(end), sourceFps, Number(fps), loop)} frames
          </p>
        ) : null}
        {problem && name && <p className="hint" data-testid="clip-problem">{problem}</p>}
        <button
          data-testid="clip-add"
          disabled={problem !== null}
          onClick={() => {
            props.decide(
              CLIP_DECISION,
              { name, source: source.trim(), start: Number(start), end: Number(end), fps: Number(fps), loop, stationary },
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

      <h2>Animation files</h2>
      {show.clip_sources.length > 0 && (
        <ul data-testid="clip-sources">
          {show.clip_sources.map((entry) => (
            <li key={entry.name} data-testid={`clip-source-${entry.name}`}>
              {entry.name} <small>{entry.imported_as ?? basename(entry.file)}</small>
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
  onImport: (files: File[], role: ImportRole) => void;
  decide: (name: string, data: Record<string, unknown>, label: string) => void;
}) {
  if (props.stage === MODEL_STAGE) return <ModelScreen {...props} />;
  if (props.stage === RIG_STAGE) return <RigScreen {...props} />;
  return <ClipsScreen {...props} />;
}
