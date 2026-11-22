// The REST Commands (spec §10.6). Every answer is the result envelope, whatever its HTTP status: a Command that refuses
// or fails a Check still answers with findings, so only a lost connection throws.

export type Status = "todo" | "stale" | "done" | "needs-input" | "needs-review" | "failed";
export type Scalar = string | number | boolean;

export interface Position {
  asset: string | null;
  stage: string | null;
  file: string | null;
  x: number | null;
  y: number | null;
  field: string | null;
  width?: number | null; // a box: x, y, width, height
  height?: number | null;
  state?: string; // a Prop's state the finding is about; absent for the default
}

export interface Finding {
  code: string;
  severity: "error" | "warning" | "info";
  message: string;
  position: Position | null;
  fix: string | null;
  owner_action: string | null;
  points?: [number, number][]; // further pixels the finding is about; absent when it has none
  data?: Record<string, unknown>; // what the finding says as data (ticket 0296); absent when it has none
}

export interface Envelope<T> {
  api_version: number;
  ok: boolean;
  data: T | null;
  findings: Finding[];
}

export interface StageState {
  stage: string;
  status: Status;
  reason: string | null;
}

// What `status` answers for some Assets, and the cheap list `assets` (ticket 0373).
export interface StatusAnswer {
  project: string;
  assets: { asset: string; kind: string; stages: StageState[] }[];
}

export interface ListRow {
  asset: string;
  kind: string;
  name: string;
  base: string | null;
  body: string | null;
  reference: boolean;
}

export interface ListAnswer {
  project: string;
  assets: ListRow[];
}

// What the lists draw (ticket 0374): a row of the cheap list, with its Stages once `status` has answered for it (null until then).
export interface StatusData {
  project: string;
  assets: { asset: string; kind: string; base: string | null; body: string | null; reference: boolean; stages: StageState[] | null }[];
}

// Where a Layer sorts against the Body, as `place`'s Decisions give it: `y` is None when it is always above (or has no line).
export interface SortPosition {
  layer: string;
  above: boolean;
  marker: string | null;
  y: number | null;
  slope: number;
}

// Who gave a Stage parameter its value: the Asset's own asset.toml, its Model's generator, its base, or nobody (the default).
export type ParamOrigin = "asset" | "generated" | "base" | "default";

// A current Decision in `show`; `from_base`: the base's, never undone here.
export interface ShownDecision {
  id: string;
  name: string;
  data: Record<string, unknown>;
  from_base?: boolean;
}

export interface StageDetail extends StageState {
  failure_code?: string | null; // while failed: the code of the finding its last run gave, such as rig.base_mismatch
  sort?: SortPosition[]; // `place` only
  params: Record<string, Scalar>;
  param_sources?: Record<string, ParamOrigin>;
  decisions: ShownDecision[]; // as recorded: what undo and redo step through
  decisions_as_read: ShownDecision[]; // as the Stage reads them: a Loop's `remove` and `rename`, `clips`' `remove`, applied
  image: string | null;
  input_image: string | null;
  outputs: string[];
  markers: Record<string, unknown>[];
}

export interface Body {
  size: [number, number];
  dash: number;
}

// A stored file: `imported_as` is the name it was imported with (null before Kiripix recorded names), `size` is in bytes.
export interface FileEntry {
  name: string;
  file: string;
  imported_as?: string | null;
  size?: number;
}

export interface HeldThing {
  thing: string;
  variants: FileEntry[];
  current: FileEntry | string | null;
  materials: { name: string; number: number; index: number | null }[] | null;
  materials_known: boolean;
  attached_by: string[];
}

export interface ShowData {
  asset: string;
  kind: string;
  params: Record<string, Scalar>;
  base?: string | null; // the character this one is made from
  resolution: [number, number];
  body: Body;
  variants: FileEntry[];
  picked: string | null;
  clip_sources: (FileEntry & { from_base: boolean })[]; // a character's animation files, by file stem; from_base: in the base's folder
  rigged: FileEntry | null; // a character's rigged file
  parameters?: FileEntry | null; // a generated character's parameter file, in place of Variants
  default_state?: string | null; // a Prop's default state: its picked Source's ID
  states?: {
    state: string;
    width: number;
    height: number;
    picked: string | null;
    variants: FileEntry[];
    images?: { stage: string; image: string | null; input_image: string | null }[]; // per Stage, this state's built images
  }[]; // a Prop's other states
  emotions?: {
    emotion: string;
    picked: string | null;
    made_on: string | null;
    current: boolean;
    variants: FileEntry[];
    images?: { stage: string; image: string | null; input_image: string | null }[]; // per Stage, this emotion's built images
  }[]; // a portrait's emotions
  looks?: { look: string; variants: FileEntry[]; picked: string | null }[]; // a room's Looks that have a stored edit
  sheets?: (FileEntry & { png_count: number | null })[]; // a sprite's imported sheets, named by hash
  tile?: number; // the Project's tile, px (`project.tile`)
  wearables?: { asset: string; order: number }[]; // a body's Wearables, by `order`
  things?: HeldThing[]; // a character's held things (ticket 0301)
  stages: StageDetail[];
}

// One stop the Owner owns (`queue`, ticket 0325): a Stage to review, an input only the Owner can give, or a finding.
export interface QueueStop {
  asset: string;
  kind: string;
  stage: string | null;
  type: "review" | "input" | "finding";
  input_hash: string | null;
  reason: string | null;
  owner_action: string | null;
  command: string | null;
  code: string | null;
  severity: string | null;
  position: Position | null;
  notes: { id: string; text: string }[]; // the Stage's live hand-over notes, oldest first
}

export interface QueueData {
  stops: QueueStop[];
  agent_fixable: { asset: string; count: number; fixes: { stage: string | null; code: string; command: string }[] }[];
  counts: { review: number; input: number; finding: number; total: number; agent_fixable: number; assets_clear: string[] };
}

// A district's room, Exit and Link (`district`, ticket 0328): the view shows them as the Probe gives them.
export interface DistrictRoom {
  asset: string;
  width: number;
  height: number;
  tiles_wide: number;
  tiles_high: number;
  built: StageState | null;
  waiting: StageState | null;
  queue: { review: number; input: number; finding: number; agent_fixable: number };
  thumbnail: string | null; // relative to the Project, for the file route
  thumbnail_stage: string | null;
  thumbnail_reason: string | null;
}

export interface DistrictExit {
  room: string;
  exit: string;
  side: string | null;
  target_room: string;
  target_exit: string;
  pairing: "paired" | "one_way" | "unpaired" | "outside";
  code: string | null;
  reason: string | null;
}

export interface DistrictData {
  rooms: DistrictRoom[];
  exits: DistrictExit[];
  links: { room: string; id: string; kind: string; two_way: boolean; start: number[]; end: number[] }[];
}

// What a batch Command gives that the view shows besides findings.
export interface BatchRunData {
  results: { asset: string; stage: string; outcome: string; message?: string | null }[];
}

export interface BatchExportData {
  dry_run: boolean;
  written: string[];
  would_write: string[];
  unchanged: string[];
  backed_up: string[];
  changed: string[];
  unmanaged: string[];
  assets: { asset: string }[];
}

// `probe style <id>` (ticket 0334): the Asset's measures, each reference's, and the references' range, as the Probe gives them.
export interface OutlineMeasure {
  outline_px: number;
  edge_px: number;
  density: number;
}

export interface ScaleMeasure {
  runs: number;
  gcd: number;
  median: number;
  run1_share: number;
}

export interface StyleMeasures {
  outline_density: OutlineMeasure | null;
  pixel_scale: ScaleMeasure;
}

export interface StyleRange {
  low: number;
  high: number;
  furthest: string | null;
}

export interface StyleProbe {
  asset: string;
  kind: string;
  stage: string | null; // the Stage the style Checks measure; null for a Kind without them
  built: boolean;
  measures: StyleMeasures | null;
  references: { asset: string; kind: string | null; stage: string | null; built: boolean; left_out: boolean; measures: StyleMeasures | null }[];
  range: { outline_density: StyleRange | null; pixel_scale: StyleRange | null };
  limits: { outline_density_floor: number; pixel_scale_gcd: number; pixel_scale_min_runs: number };
  findings: Finding[];
}

export interface NextData {
  asset: string;
  done: boolean;
  stage: string | null;
  status: string | null;
  reason: string | null;
  command: string | null;
  owner_action: string | null;
}

export interface ParamSpec {
  name: string;
  type: "int" | "float" | "bool" | "str" | "choice";
  description: string;
  default: Scalar | null;
  minimum: number | null;
  maximum: number | null;
  choices: string[] | null;
}

export interface StageDescription {
  name: string;
  description: string;
  params: ParamSpec[];
  decisions: { name: string; description: string; entry_schema?: {
      properties?: Record<string, { minimum?: number; maximum?: number; pattern?: string; enum?: string[] }>;
    } }[];
  checks: { code: string; description: string }[];
  owner_input: string | null;
  implemented: boolean;
  available_from: string | null;
}

// One Mask of the Project (`describe room`): the top view's first, then the side's, each in file order.
export interface MaskRow {
  view: "top" | "side";
  name: string;
  colour: string | null;
  meaning: string | null;
  derived: boolean;
  blocks: boolean;
}

export interface DescribeData {
  kinds: { name: string; stages: StageDescription[] | null }[];
  masks?: MaskRow[] | null;
}

const TOKEN_KEY = "kiripix.token";
let token: string | null = readToken();

// `kiripix ui` hands the session token over in the URL's fragment. It moves to this tab's storage, out of the address bar.
function readToken(): string | null {
  const match = /[#&]token=([^&]+)/.exec(window.location.hash);
  if (match) {
    const given = decodeURIComponent(match[1]);
    try {
      sessionStorage.setItem(TOKEN_KEY, given);
    } catch {
      // Without storage the token lasts until a reload.
    }
    history.replaceState(null, "", window.location.pathname + window.location.search);
    return given;
  }
  try {
    return sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

function url(command: string): string {
  return "api/" + command.split(" ").join("/");
}

function headers(job?: string): Record<string, string> {
  return { ...(token ? { "X-Kiripix-Token": token } : {}), ...(job ? { "X-Kiripix-Job": job } : {}) };
}

// `keepalive` lets the request outlive the page, for a last `track` while the tab closes.
export async function call<T>(command: string, input: object, job?: string, keepalive = false): Promise<Envelope<T>> {
  const response = await fetch(url(command), {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers(job) },
    body: JSON.stringify(input),
    keepalive,
  });
  return (await response.json()) as Envelope<T>;
}

// A Command's file input is a multipart part named after its field, beside an `input` part (ADR 0007).
export async function callWithFile<T>(command: string, input: object, field: string, file: File): Promise<Envelope<T>> {
  const form = new FormData();
  form.append("input", JSON.stringify(input));
  form.append(field, file, file.name);
  const response = await fetch(url(command), { method: "POST", headers: headers(), body: form });
  return (await response.json()) as Envelope<T>;
}

// Several file inputs, a part each: a repeated field is a list input (`frames`), each part keeping the name it was sent with.
export async function callWithFiles<T>(command: string, input: object, parts: { field: string; file: File }[]): Promise<Envelope<T>> {
  const form = new FormData();
  form.append("input", JSON.stringify(input));
  for (const { field, file } of parts) form.append(field, file, file.name);
  const response = await fetch(url(command), { method: "POST", headers: headers(), body: form });
  return (await response.json()) as Envelope<T>;
}

// The Project palette, from the `palette` Command (ticket 0204): #rrggbb, lower case, in file order. Empty when it can't be read.
export async function projectPalette(): Promise<string[]> {
  const result = await call<{ colours: { hex: string }[] }>("palette", {});
  return result.ok && result.data ? result.data.colours.map((colour) => colour.hex.toLowerCase()) : [];
}

export async function cancelJob(job: string): Promise<void> {
  await fetch(`api/jobs/${encodeURIComponent(job)}/cancel`, { method: "POST" });
}

// What changed in the Project, as `changed` events named it (ticket 0369). A path is a file or a folder (a Stage's output is named by its
// folder), so a path matches another when one is the other or lies under it. Each change has a number; a file's URL carries the newest
// number of the changes that touch it, so only a file whose own change was reported is fetched again.
// An Asset ID is `<kind>.<name>`, its folder `assets/<kind>/<name>`.
export function assetFolder(id: string): string {
  const dot = id.indexOf(".");
  return dot < 0 ? `assets/${id}` : `assets/${id.slice(0, dot)}/${id.slice(dot + 1)}`;
}

let changeSeq = 0;
let everything = 0; // the number of the latest change that named no paths: anything may have changed
const changed = new Map<string, number>();
const shown = new Set<string>(); // the files the page has asked for

export function pathsRelated(a: string, b: string): boolean {
  return a === b || a.startsWith(`${b}/`) || b.startsWith(`${a}/`);
}

// The number of the newest change that touches `path` (a file or a folder); 0 when none did.
export function changeStamp(path: string): number {
  let newest = everything;
  for (const [other, seq] of changed) if (seq > newest && pathsRelated(other, path)) newest = seq;
  return newest;
}

// Record a change; true when it touches a file the page has shown. `null`: no paths known, so everything is taken as changed.
export function noteChange(paths: string[] | null): boolean {
  changeSeq += 1;
  if (paths === null) {
    everything = changeSeq;
    return true;
  }
  let touched = false;
  for (const path of paths) {
    changed.set(path, changeSeq);
    if (!touched) for (const file of shown) if (pathsRelated(path, file)) touched = true;
  }
  return touched;
}

export function fileUrl(relative: string, _version?: number): string {
  shown.add(relative);
  return `files/${encodeURI(relative)}?v=${changeStamp(relative)}`;
}

export interface EventHandlers {
  // Files changed in the Project: `paths` is null when it has just connected or more changed than the event names; `own` is the part
  // `serve`'s own Commands wrote (what this page's actions did); `hello` is the stream connecting, the first time or again.
  onChange: (change: { paths: string[] | null; own: string[]; hello: boolean }) => void;
  onProgress: (message: string, fraction: number | null) => void;
  onLost: () => void;
}

// Refreshes follow the folder watch's "changed" only, never "job_end": that one ends every Command, and a refresh is made
// of Commands. A reconnect says "hello", and what changed during the gap was reported to nobody, so that refreshes too.
export function events({ onChange, onProgress, onLost }: EventHandlers): () => void {
  const source = new EventSource("api/events");
  source.addEventListener("hello", () => onChange({ paths: null, own: [], hello: true }));
  source.addEventListener("changed", (event) => {
    const { count, paths, own } = JSON.parse((event as MessageEvent<string>).data) as { count: number; paths: string[]; own?: string[] };
    onChange({ paths: count > paths.length ? null : paths, own: own ?? [], hello: false });
  });
  source.onerror = onLost;
  source.addEventListener("progress", (event) => {
    const { progress } = JSON.parse((event as MessageEvent<string>).data) as {
      progress: { stage: string | null; message: string | null; event: string; done: number | null; total: number | null };
    };
    // A fraction only where the event gives a real one.
    const fraction = progress.total && progress.done != null ? Math.min(1, Math.max(0, progress.done / progress.total)) : null;
    onProgress([progress.stage, progress.message ?? progress.event].filter(Boolean).join(": "), fraction);
  });
  return () => source.close();
}
