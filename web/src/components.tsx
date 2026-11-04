import { useEffect, useRef, useState, type DragEvent, type KeyboardEvent, type RefObject } from "react";
import {
  fileUrl,
  type Finding,
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

export function StatusBoard(props: {
  status: StatusData | null;
  filter: Filter;
  onOpen: (asset: string, stage: string) => void;
}) {
  const assets = (props.status?.assets ?? []).filter((asset) => matches(asset.stages, props.filter));
  return (
    <div className="board" data-testid="board">
      {[...new Set(assets.map((asset) => asset.kind))].map((kind) => (
        <section key={kind}>
          <h2>{kind}</h2>
          {assets
            .filter((asset) => asset.kind === kind)
            .map((asset) => (
              <div className="board-row" key={asset.asset} data-testid={`board-${asset.asset}`}>
                <span className="board-name">{asset.asset}</span>
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
              </div>
            ))}
        </section>
      ))}
      {props.status && assets.length === 0 && <p className="hint">No Asset matches this filter.</p>}
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

  return <div className="canvas-host" ref={host} />;
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
        Drop PNGs here to import them as Variants, or{" "}
        <button className="link" onClick={() => input.current?.click()}>
          choose files
        </button>
        .
      </p>
      <input
        ref={input}
        data-testid="import-input"
        type="file"
        accept="image/png"
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
export function ParamControl(props: { spec: ParamSpec; value: Scalar | undefined; onCommit: (value: Scalar) => void }) {
  const { spec, value, onCommit } = props;
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
      <small>{spec.description}</small>
    </div>
  );
}

export function FindingList(props: { findings: Finding[]; onJump: (finding: Finding) => void; testid: string }) {
  return (
    <ul className="findings" data-testid={props.testid}>
      {props.findings.map((finding, index) => (
        <li key={`${finding.code}-${index}`} data-severity={finding.severity}>
          <button className="link" data-testid={`finding-${finding.code}`} onClick={() => props.onJump(finding)}>
            <code>{finding.code}</code>
            {finding.position?.x != null && ` (${finding.position.x}, ${finding.position.y})`}
          </button>
          <p>{finding.message}</p>
          {finding.fix && <code className="remedy">{finding.fix}</code>}
          {finding.owner_action && <p className="remedy">{finding.owner_action}</p>}
        </li>
      ))}
    </ul>
  );
}
