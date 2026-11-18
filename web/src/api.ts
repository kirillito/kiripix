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

export interface StatusData {
  project: string;
  assets: { asset: string; kind: string; stages: StageState[] }[];
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
  emotions?: { emotion: string; picked: string | null; made_on: string | null; current: boolean; variants: FileEntry[] }[]; // a portrait's emotions
  looks?: { look: string; variants: FileEntry[]; picked: string | null }[]; // a room's Looks that have a stored edit
  sheets?: (FileEntry & { png_count: number | null })[]; // a sprite's imported sheets, named by hash
  tile?: number; // the Project's tile, px (`project.tile`)
  wearables?: { asset: string; order: number }[]; // a body's Wearables, by `order`
  stages: StageDetail[];
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

export interface DescribeData {
  kinds: { name: string; stages: StageDescription[] | null }[];
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

export function fileUrl(relative: string, version: number): string {
  return `files/${encodeURI(relative)}?v=${version}`;
}

export interface EventHandlers {
  // Files changed in the Project (or, with `null`, the stream has just connected and anything may have).
  onChange: (paths: string[] | null) => void;
  onProgress: (message: string, fraction: number | null) => void;
  onLost: () => void;
}

// Refreshes follow the folder watch's "changed" only, never "job_end": that one ends every Command, and a refresh is made
// of Commands. A reconnect says "hello", and what changed during the gap was reported to nobody, so that refreshes too.
export function events({ onChange, onProgress, onLost }: EventHandlers): () => void {
  const source = new EventSource("api/events");
  source.addEventListener("hello", () => onChange(null));
  source.addEventListener("changed", (event) => {
    const { count, paths } = JSON.parse((event as MessageEvent<string>).data) as { count: number; paths: string[] };
    onChange(count > paths.length ? null : paths);
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
