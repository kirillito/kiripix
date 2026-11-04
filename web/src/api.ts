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
}

export interface Finding {
  code: string;
  severity: "error" | "warning" | "info";
  message: string;
  position: Position | null;
  fix: string | null;
  owner_action: string | null;
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

export interface StageDetail extends StageState {
  params: Record<string, Scalar>;
  decisions: { id: string; name: string; data: Record<string, unknown> }[];
  image: string | null;
  input_image: string | null;
}

export interface ShowData {
  asset: string;
  kind: string;
  params: Record<string, Scalar>;
  resolution: [number, number];
  variants: { name: string; file: string }[];
  picked: string | null;
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
  decisions: { name: string; description: string }[];
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

export async function call<T>(command: string, input: object, job?: string): Promise<Envelope<T>> {
  const response = await fetch(url(command), {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers(job) },
    body: JSON.stringify(input),
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

export async function cancelJob(job: string): Promise<void> {
  await fetch(`api/jobs/${encodeURIComponent(job)}/cancel`, { method: "POST" });
}

export function fileUrl(relative: string, version: number): string {
  return `files/${encodeURI(relative)}?v=${version}`;
}

export interface EventHandlers {
  // Files changed in the Project (or, with `null`, the stream has just connected and anything may have).
  onChange: (paths: string[] | null) => void;
  onProgress: (message: string) => void;
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
      progress: { stage: string | null; message: string | null; event: string };
    };
    onProgress([progress.stage, progress.message ?? progress.event].filter(Boolean).join(": "));
  });
  return () => source.close();
}
