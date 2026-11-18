import { useEffect, useRef, useState, type DragEvent, type KeyboardEvent, type RefObject } from "react";
import {
  fileUrl,
  type Finding,
  type ParamOrigin,
  type ParamSpec,
  type Scalar,
  type ShowData,
  type StageState,
  type Status,
  type StatusData,
} from "./api";
import { PixelCanvas } from "./pixelCanvas";

export const GLYPH: Record<Status, string> = {
  todo: "·",
  stale: "◐",
  done: "✓",
  "needs-input": "!",
  "needs-review": "?",
  failed: "✗",
};

export type Filter = "all" | "needs-me" | "stale" | "failing";

const FILTERS: Record<Filter, { label: string; statuses: Status[] }> = {
  all: { label: "All", statuses: ["todo", "stale", "done", "needs-input", "needs-review", "failed"] },
  "needs-me": { label: "Needs me", statuses: ["needs-input", "needs-review"] },
  stale: { label: "Stale", statuses: ["stale"] },
  failing: { label: "Failing", statuses: ["failed"] },
};

function matches(stages: StageState[], filter: Filter): boolean {
  return stages.some((stage) => FILTERS[filter].statuses.includes(stage.status));
}

export function FilterBar({ filter, onChange }: { filter: Filter; onChange: (filter: Filter) => void }) {
  return (
    <div className="filters" role="group" aria-label="Filter Assets">
      {(Object.keys(FILTERS) as Filter[]).map((name) => (
        <button key={name} data-testid={`filter-${name}`} aria-pressed={filter === name} onClick={() => onChange(name)}>
          {FILTERS[name].label}
        </button>
      ))}
    </div>
  );
}

export function AssetList(props: {
  status: StatusData | null;
  selected: string | null;
  filter: Filter;
  onSelect: (asset: string) => void;
}) {
  const [search, setSearch] = useState("");
  const assets = (props.status?.assets ?? []).filter(
    (asset) => asset.asset.includes(search.trim().toLowerCase()) && matches(asset.stages, props.filter),
  );
  const kinds = [...new Set(assets.map((asset) => asset.kind))];
  return (
    <nav className="assets" aria-label="Assets">
      <input
        type="search"
        placeholder="Search Assets"
        aria-label="Search Assets"
        value={search}
        onChange={(event) => setSearch(event.target.value)}
      />
      {kinds.map((kind) => (
        <section key={kind}>
          <h2>{kind}</h2>
          {assets
            .filter((asset) => asset.kind === kind)
            .map((asset) => (
              <button
                key={asset.asset}
                className="asset"
                data-testid={`asset-${asset.asset}`}
                aria-current={props.selected === asset.asset}
                onClick={() => props.onSelect(asset.asset)}
              >
                {asset.asset.slice(kind.length + 1)}
                <Summary stages={asset.stages} />
              </button>
            ))}
        </section>
      ))}
      {props.status && props.status.assets.length === 0 && (
        <p className="hint">
          No Assets yet. Create one: <code>kiripix new room alley --view top</code>
        </p>
      )}
    </nav>
  );
}

function Summary({ stages }: { stages: StageState[] }) {
  const worst = (["failed", "needs-review", "needs-input", "stale", "todo", "done"] as Status[]).find((status) =>
    stages.some((stage) => stage.status === status),
  );
  return worst ? (
    <span className="glyph" data-status={worst} title={worst}>
      {GLYPH[worst]}
    </span>
  ) : null;
}

// `new` for a character: its name and, if it is made from one, its base; or a parameter file for a generated one.
function NewCharacter(props: { characters: string[]; onCreate: (name: string, base: string, parameters: File | null) => void }) {
  const [name, setName] = useState("");
  const [base, setBase] = useState("");
  const [parameters, setParameters] = useState<File | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const valid = /^[a-z0-9_]+$/.test(name);
  return (
    <section className="new-character" data-testid="new-character">
      <h2>New character</h2>
      <div className="param">
        <label htmlFor="new-character-name">Name</label>
        <input id="new-character-name" data-testid="new-character-name" value={name} onChange={(event) => setName(event.target.value)} />
      </div>
      <div className="param">
        <label htmlFor="new-character-base">Made from</label>
        <select id="new-character-base" data-testid="new-character-base" value={base} onChange={(event) => setBase(event.target.value)}>
          <option value="">no base</option>
          {props.characters.map((id) => (
            <option key={id} value={id}>
              {id}
            </option>
          ))}
        </select>
      </div>
      <div className="param">
        <label>Parameter file</label>
        <button className="link" data-testid="new-character-parameters" onClick={() => input.current?.click()}>
          {parameters ? parameters.name : "choose a file (a generated character)"}
        </button>
        <input
          ref={input}
          data-testid="new-character-parameters-input"
          type="file"
          accept=".toml,.json"
          hidden
          onChange={(event) => {
            setParameters(event.target.files?.[0] ?? null);
            event.target.value = "";
          }}
        />
      </div>
      <button
        data-testid="new-character-create"
        disabled={!valid}
        onClick={() => {
          props.onCreate(name, base, parameters);
          setName("");
          setParameters(null);
        }}
      >
        Create character
      </button>
    </section>
  );
}

// A Wearable on the board: the body it is worn on, and its cost (ticket 0295).
export interface WornAsset {
  body: string | null;
  cost: string;
}

export function StatusBoard(props: {
  status: StatusData | null;
  filter: Filter;
  onOpen: (asset: string, stage: string) => void;
  onCreateCharacter?: (name: string, base: string, parameters: File | null) => void;
  worn?: Record<string, WornAsset>;
}) {
  const assets = (props.status?.assets ?? []).filter((asset) => matches(asset.stages, props.filter));
  const worn = props.worn ?? {};
  const shown = new Set(assets.map((asset) => asset.asset));
  // A Wearable shows under its body when the body is on the board too; else in its own Kind's section.
  const under = (body: string) => assets.filter((asset) => asset.kind === "wearable" && worn[asset.asset]?.body === body);
  const loose = (asset: { asset: string; kind: string }) => asset.kind !== "wearable" || !shown.has(worn[asset.asset]?.body ?? "");
  const row = (asset: (typeof assets)[number], nested: boolean) => (
    <div
      className={nested ? "board-row board-worn" : "board-row"}
      key={asset.asset}
      data-testid={`board-${asset.asset}`}
      data-body={nested ? worn[asset.asset]?.body : undefined}
    >
      <span className="board-name">{nested ? "↳ " : ""}{asset.asset}</span>
      {asset.stages.map((stage) => (
        <button
          key={stage.stage}
          className="glyph-button"
          data-status={stage.status}
          title={[stage.stage, stage.status, stage.reason].filter(Boolean).join(": ")}
          onClick={() => props.onOpen(asset.asset, stage.stage)}
        >
          {stage.stage} {GLYPH[stage.status]}
        </button>
      ))}
      {worn[asset.asset]?.cost && (
        <span className="hint board-cost" data-testid={`cost-${asset.asset}`}>
          {worn[asset.asset].cost}
        </span>
      )}
    </div>
  );
  return (
    <div className="board" data-testid="board">
      {[...new Set(assets.filter(loose).map((asset) => asset.kind))].map((kind) => (
        <section key={kind}>
          <h2>{kind}</h2>
          {assets
            .filter((asset) => asset.kind === kind && loose(asset))
            .map((asset) => (
              <div key={asset.asset}>
                {row(asset, false)}
                {under(asset.asset).map((one) => row(one, true))}
              </div>
            ))}
        </section>
      ))}
      {props.status && assets.length === 0 && <p className="hint">No Asset matches this filter.</p>}
      {props.onCreateCharacter && props.status && (
        <NewCharacter
          characters={props.status.assets.filter((asset) => asset.kind === "character").map((asset) => asset.asset)}
          onCreate={props.onCreateCharacter}
        />
      )}
    </div>
  );
}

export function StageBar(props: { stages: StageState[]; selected: string | null; onSelect: (stage: string) => void }) {
  return (
    <div className="stage-bar" role="tablist" aria-label="Stages">
      {props.stages.map((stage) => (
        <button
          key={stage.stage}
          role="tab"
          aria-selected={props.selected === stage.stage}
          data-testid={`stage-${stage.stage}`}
          data-status={stage.status}
          title={[stage.status, stage.reason].filter(Boolean).join(": ")}
          onClick={() => props.onSelect(stage.stage)}
        >
          {stage.stage} <span className="glyph">{GLYPH[stage.status]}</span>
        </button>
      ))}
    </div>
  );
}

export function CanvasView(props: {
  after: string | null;
  before: string | null;
  frame: [number, number] | null;
  fitKey: string;
  canvas: RefObject<PixelCanvas | null>;
}) {
  const host = useRef<HTMLDivElement>(null);
  const { canvas, after, before, frame, fitKey } = props;

  useEffect(() => {
    if (!host.current) return;
    const widget = new PixelCanvas(host.current);
    canvas.current = widget;
    return () => {
      widget.destroy();
      canvas.current = null;
    };
  }, [canvas]);

  useEffect(() => canvas.current?.refit(), [canvas, fitKey]);
  useEffect(() => void canvas.current?.show(after, before), [canvas, after, before, fitKey]);
  const [frameWidth, frameHeight] = frame ?? [0, 0];
  useEffect(
    () => canvas.current?.setGameFrame(frameWidth ? [frameWidth, frameHeight] : null),
    [canvas, frameWidth, frameHeight],
  );

  return (
    <div className="canvas-wrap">
      <div className="canvas-host" ref={host} />
      <p className="canvas-hint" data-testid="canvas-hint">
        Hold <kbd>Space</kbd> and drag to pan, or use the arrow keys (<kbd>Shift</kbd> for more). The wheel zooms at the pointer,{" "}
        <kbd>Z</kbd> at the centre, <kbd>Home</kbd> fits.
      </p>
    </div>
  );
}

export function VariantGrid(props: {
  show: ShowData;
  onPick: (variant: string) => void;
  onImport: (files: File[]) => void;
}) {
  const [over, setOver] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  function drop(event: DragEvent) {
    event.preventDefault();
    setOver(false);
    props.onImport([...event.dataTransfer.files]);
  }

  return (
    <div
      className="variants"
      data-testid="dropzone"
      data-over={over}
      onDragOver={(event) => {
        event.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={drop}
    >
      <div className="variant-grid">
        {props.show.variants.map((variant, index) => (
          <button
            key={variant.name}
            className="variant"
            data-testid={`variant-${variant.name}`}
            aria-pressed={props.show.picked === variant.name}
            onClick={() => props.onPick(variant.name)}
          >
            <img src={fileUrl(variant.file, 0)} alt={`Variant ${variant.name}`} />
            <span>
              {index < 9 && <kbd>{index + 1}</kbd>} {variant.name.slice(0, 8)}
              {props.show.picked === variant.name && " · picked"}
            </span>
          </button>
        ))}
      </div>
      <p className="hint">
        Drop PNGs or JPEGs here to import them as Variants, or{" "}
        <button className="link" onClick={() => input.current?.click()}>
          choose files
        </button>
        .
      </p>
      <input
        ref={input}
        data-testid="import-input"
        type="file"
        accept="image/png,image/jpeg"
        multiple
        hidden
        onChange={(event) => {
          props.onImport([...(event.target.files ?? [])]);
          event.target.value = "";
        }}
      />
    </div>
  );
}

// A draft while the Owner types; committed as one `set` on change, blur or Enter. An outside change replaces the draft.
// `origin` marks a value the Asset doesn't hold itself (its base's, or its Model's generator's); "set here" writes it to the Asset.
export function ParamControl(props: {
  spec: ParamSpec;
  value: Scalar | undefined;
  origin?: ParamOrigin;
  onCommit: (value: Scalar) => void;
}) {
  const { spec, value, onCommit, origin } = props;
  const [draft, setDraft] = useState(String(value ?? ""));
  useEffect(() => setDraft(String(value ?? "")), [value]);
  const id = `param-${spec.name}`;

  function commit() {
    if (spec.type !== "str" && draft.trim() === "") setDraft(String(value ?? ""));
    else if (draft !== String(value ?? "")) onCommit(spec.type === "str" ? draft : Number(draft));
  }

  function onKeyDown(event: KeyboardEvent) {
    if (event.key === "Enter") commit();
  }

  let control;
  if (spec.choices) {
    control = (
      <select id={id} data-testid={id} value={String(value ?? "")} onChange={(event) => onCommit(event.target.value)}>
        {spec.choices.map((choice) => (
          <option key={choice}>{choice}</option>
        ))}
      </select>
    );
  } else if (spec.type === "bool") {
    control = (
      <input
        id={id}
        data-testid={id}
        type="checkbox"
        checked={value === true}
        onChange={(event) => onCommit(event.target.checked)}
      />
    );
  } else if (spec.type === "str") {
    control = (
      <input
        id={id}
        data-testid={id}
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={commit}
        onKeyDown={onKeyDown}
      />
    );
  } else {
    const bounded = spec.minimum !== null && spec.maximum !== null;
    control = (
      <span className="number">
        {bounded && (
          <input
            type="range"
            aria-label={`${spec.name} slider`}
            min={spec.minimum ?? undefined}
            max={spec.maximum ?? undefined}
            step={spec.type === "int" ? 1 : 0.01}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onPointerUp={commit}
            onKeyUp={commit}
          />
        )}
        <input
          id={id}
          data-testid={id}
          type="number"
          min={spec.minimum ?? undefined}
          max={spec.maximum ?? undefined}
          step={spec.type === "int" ? 1 : "any"}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onBlur={commit}
          onKeyDown={onKeyDown}
        />
      </span>
    );
  }
  return (
    <div className="param">
      <label htmlFor={id} title={spec.description}>
        {spec.name}
      </label>
      {control}
      {(origin === "base" || origin === "generated") && value !== undefined && (
        <span className="param-origin" data-testid={`param-origin-${spec.name}`} data-origin={origin}>
          <small title={origin === "base" ? "The base's value" : "The generator's value"}>{origin === "base" ? "from the base" : "generated"}</small>{" "}
          <button className="link" data-testid={`param-set-${spec.name}`} onClick={() => onCommit(value)}>
            set here
          </button>
        </span>
      )}
      <small>{spec.description}</small>
    </div>
  );
}

const SEVERITY_ORDER = { error: 0, warning: 1, info: 2 } as const;

function findingKey(finding: Finding): string {
  const at = finding.position;
  return `${finding.code}|${finding.message}|${at?.stage ?? ""}|${at?.file ?? ""}|${at?.x ?? ""},${at?.y ?? ""}`;
}

// What a person reads (ticket 0093): each finding once, whichever list it came from; none that only repeats a Stage's status,
// which the Stage bar and the next line already say; errors above warnings above info.
export function readable(
  findings: Finding[],
  alreadyShown: Finding[] = [],
  stages: { stage: string; status: string }[] = [],
): Finding[] {
  const seen = new Set(alreadyShown.map(findingKey));
  const repeatsStatus = (finding: Finding) => {
    const status = finding.code === "stage.needs_review" ? "needs-review" : finding.code === "stage.needs_input" ? "needs-input" : null;
    if (!status) return false;
    const stage = finding.position?.stage;
    return stages.some((entry) => entry.status === status && (!stage || entry.stage === stage));
  };
  return findings
    .filter((finding) => {
      const key = findingKey(finding);
      if (seen.has(key) || repeatsStatus(finding)) return false;
      seen.add(key);
      return true;
    })
    .sort((a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity]);
}

// The one thing to do first: the most pressing finding that asks the Owner for something.
export function pressing(findings: Finding[]): Finding | undefined {
  return findings.find((finding) => finding.severity !== "info" && finding.owner_action);
}

export function FindingList(props: { findings: Finding[]; onJump: (finding: Finding) => void; testid: string }) {
  const [expanded, setExpanded] = useState(false);
  const info = props.findings.filter((finding) => finding.severity === "info");
  const shown = props.findings.filter((finding) => expanded || finding.severity !== "info");
  return (
    <>
      <ul className="findings" data-testid={props.testid}>
        {shown.map((finding, index) => (
          <li key={`${finding.code}-${index}`} data-severity={finding.severity}>
            <button className="link" data-testid={`finding-${finding.code}`} onClick={() => props.onJump(finding)}>
              {finding.message}
              {finding.position?.x != null && ` (${finding.position.x}, ${finding.position.y})`}
            </button>
            {finding.owner_action && <p className="remedy">{finding.owner_action}</p>}
            <small className="agent">
              <code>{finding.code}</code>
              {finding.fix && (
                <>
                  {" "}
                  <code>{finding.fix}</code>
                </>
              )}
            </small>
          </li>
        ))}
      </ul>
      {info.length > 0 && (
        <button className="link info-toggle" data-testid={`${props.testid}-info`} aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>
          {expanded ? "Hide" : "Show"} {info.length} {info.length === 1 ? "note" : "notes"}
        </button>
      )}
    </>
  );
}
