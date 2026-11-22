// The district view (ticket 0330, spec §11): a glob's rooms side by side, their Exits and the batch actions. What the rooms are,
// their pairing and their queue counts are `district`'s; the batch actions are `run`, `check` and `export` with `--match`. Nothing
// here decides what a district is.

import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { call, cancelJob, fileUrl, type BatchExportData, type BatchRunData, type DistrictData, type DistrictRoom, type Envelope, type Finding } from "./api";
import { FindingList, GLYPH } from "./components";

// The common prefixes of the room IDs as globs (`room.ch01_*`, `room.ch01_dungeon_*`), each shared by two rooms or more. A shortcut
// only: the glob is still matched by the Commands.
export function districtPrefixes(assets: { asset: string; kind: string }[]): string[] {
  const counts = new Map<string, number>();
  for (const { asset, kind } of assets) {
    if (kind !== "room") continue;
    const parts = asset.slice("room.".length).split("_");
    for (let at = 1; at < parts.length; at++) {
      const glob = `room.${parts.slice(0, at).join("_")}_*`;
      counts.set(glob, (counts.get(glob) ?? 0) + 1);
    }
  }
  return [...counts].filter(([, count]) => count >= 2).map(([glob]) => glob).sort();
}

// The way into the view, on the status board: a glob typed, or one of the prefixes.
export function DistrictOpen(props: { assets: { asset: string; kind: string }[]; onOpen: (glob: string) => void }) {
  const [draft, setDraft] = useState("");
  const prefixes = districtPrefixes(props.assets);
  const go = () => draft.trim() && props.onOpen(draft.trim());
  return (
    <section className="district-open" data-testid="district-open">
      <h2>District</h2>
      <div className="district-open-row">
        <input
          data-testid="district-glob"
          aria-label="District glob"
          placeholder="room.ch01_dungeon_*"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => event.key === "Enter" && go()}
        />
        <button data-testid="district-go" disabled={!draft.trim()} onClick={go}>
          Open district
        </button>
      </div>
      {prefixes.length > 0 && (
        <div className="district-prefixes">
          {prefixes.map((glob) => (
            <button key={glob} className="link" data-testid={`district-prefix-${glob}`} onClick={() => props.onOpen(glob)}>
              {glob}
            </button>
          ))}
        </div>
      )}
    </section>
  );
}

const GAP = 12;
const ACROSS = 3; // the zoom is the largest whole one that still fits this many rooms in a row (fewer rooms: all of them)
const MAX_ZOOM = 8;

// The largest whole zoom at which `across` of the widest room fit in `width`; never below 1.
export function districtZoom(width: number, widest: number, across: number): number {
  if (widest <= 0 || width <= 0) return 1;
  const fits = Math.floor((width / Math.max(1, across) - GAP) / widest);
  return Math.min(MAX_ZOOM, Math.max(1, fits));
}

// The thumbnail at a whole multiple of its own size, nearest-neighbour.
function Thumbnail(props: { room: DistrictRoom; zoom: number; version: number }) {
  const [size, setSize] = useState<[number, number] | null>(null);
  if (!props.room.thumbnail) {
    return (
      <span className="district-nothumb" title={props.room.thumbnail_reason ?? ""}>
        {props.room.thumbnail_reason ?? "no image yet"}
      </span>
    );
  }
  return (
    <img
      className="district-thumb"
      data-testid={`district-thumb-${props.room.asset}`}
      data-stage={props.room.thumbnail_stage ?? ""}
      alt={props.room.asset}
      src={fileUrl(props.room.thumbnail, props.version)}
      // Fetched when it scrolls into view (ticket 0374); until it has loaded it holds the room's size, so a lazy image has a place.
      loading="lazy"
      decoding="async"
      style={size ? { width: size[0] * props.zoom, height: size[1] * props.zoom } : { width: props.room.width * props.zoom, height: props.room.height * props.zoom }}
      onLoad={(event) => setSize([event.currentTarget.naturalWidth, event.currentTarget.naturalHeight])}
    />
  );
}

interface Outcome {
  label: string;
  lines: string[];
  findings: Finding[];
}

// A finding of a batch opens its Asset on the Stage it names.
function jumpTo(open: (asset: string, stage: string | null) => void) {
  return (finding: Finding) => {
    const asset = finding.position?.asset;
    if (asset) open(asset, finding.position?.stage ?? null);
  };
}

export function DistrictView(props: {
  glob: string;
  refreshes: number;
  imageVersion: number;
  job: string | null; // the Run in flight, which Cancel stops
  progress: string | null;
  onOpen: (asset: string, stage: string | null) => void;
  onReview: (glob: string) => void;
  onClose: () => void;
  // One Command through the App's queue of actions; null when the connection was lost.
  batch: (command: string, input: object, label: string, cancellable: boolean) => Promise<Envelope<unknown> | null>;
  extra?: (data: DistrictData) => ReactNode; // more under the grid, such as the rooms waiting for a Source (ticket 0351)
}) {
  const { glob, refreshes } = props;
  const [data, setData] = useState<{ glob: string; value: Envelope<DistrictData> } | null>(null);
  const [lost, setLost] = useState(false);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [confirm, setConfirm] = useState<{ writes: string[]; overwrites: string[]; findings: Finding[] } | null>(null);
  const [pending, setPending] = useState(false);
  const [width, setWidth] = useState(0);
  const host = useRef<HTMLDivElement>(null);
  const asked = useRef(0);

  useEffect(() => {
    const ticket = ++asked.current;
    call<DistrictData>("district", { glob })
      .then((value) => {
        if (ticket !== asked.current) return;
        setData({ glob, value });
        setLost(false);
      })
      .catch(() => setLost(true));
  }, [glob, refreshes]);

  useEffect(() => {
    setOutcome(null);
    setConfirm(null);
  }, [glob]);

  useLayoutEffect(() => {
    const node = host.current;
    if (!node) return;
    const measure = () => setWidth(node.clientWidth);
    measure();
    const watcher = new ResizeObserver(measure);
    watcher.observe(node);
    return () => watcher.disconnect();
  }, []);

  const shown = data?.glob === glob ? data.value : null;
  const rooms = shown?.data?.rooms ?? [];
  const exits = shown?.data?.exits ?? [];
  const zoom = districtZoom(width, Math.max(0, ...rooms.map((room) => room.width)), Math.min(rooms.length, ACROSS));
  const unpaired = (room: string) => exits.filter((entry) => entry.room === room && entry.pairing === "unpaired").length;
  const working = props.job !== null || pending;
  const none = shown !== null && rooms.length === 0;

  async function act(command: string, input: object, label: string, cancellable: boolean): Promise<Envelope<unknown> | null> {
    setPending(true);
    setOutcome(null);
    setConfirm(null);
    try {
      return await props.batch(command, { ...input, match: glob }, label, cancellable);
    } finally {
      setPending(false);
    }
  }

  async function run() {
    const result = await act("run", {}, `Running ${glob}`, true);
    if (!result) return;
    const results = (result.data as BatchRunData | null)?.results ?? [];
    setOutcome({
      label: "Run",
      lines: results.map((one) => `${one.asset} ${one.stage}: ${one.outcome}${one.message ? ` (${one.message})` : ""}`),
      findings: result.findings,
    });
  }
  async function check() {
    const result = await act("check", {}, `Checking ${glob}`, false);
    if (result) setOutcome({ label: "Check", lines: [], findings: result.findings });
  }
  // Export asks first: a dry run says what it writes and what it overwrites, and nothing is written until the Owner confirms.
  async function exportDryRun() {
    const result = await act("export", { dry_run: true }, `Checking what ${glob} would export`, false);
    if (!result) return;
    const done = result.data as BatchExportData | null;
    if (!result.ok || !done) setOutcome({ label: "Export", lines: [], findings: result.findings });
    else setConfirm({ writes: done.would_write, overwrites: done.backed_up, findings: result.findings });
  }
  async function exportNow() {
    const result = await act("export", {}, `Exporting ${glob}`, false);
    if (!result) return;
    const done = result.data as BatchExportData | null;
    setOutcome({
      label: "Export",
      lines: done ? [`${done.written.length} file(s) written, ${done.unchanged.length} unchanged`] : [],
      findings: result.findings,
    });
  }

  const unpairedExits = exits.filter((entry) => entry.pairing === "unpaired");
  return (
    <section className="district" data-testid="district" aria-label="District">
      <div className="district-bar">
        <h1 data-testid="district-title">{glob}</h1>
        <span className="hint" data-testid="district-summary">
          {rooms.length} {rooms.length === 1 ? "room" : "rooms"}
          {unpairedExits.length > 0 ? `, ${unpairedExits.length} unpaired ${unpairedExits.length === 1 ? "Exit" : "Exits"}` : ""}
        </span>
        <button data-testid="district-review" disabled={none} onClick={() => props.onReview(glob)} title="Walk what waits on you in these rooms">
          Review this district
        </button>
        <button data-testid="district-run" disabled={none || working} onClick={() => void run()}>
          Run
        </button>
        <button data-testid="district-check" disabled={none || working} onClick={() => void check()}>
          Check
        </button>
        <button data-testid="district-export" disabled={none || working} onClick={() => void exportDryRun()}>
          Export
        </button>
        {props.job && (
          <button className="primary" data-testid="district-cancel" onClick={() => void cancelJob(props.job!)}>
            Cancel
          </button>
        )}
        <button className="link" data-testid="district-close" onClick={props.onClose}>
          Close
        </button>
      </div>
      {props.progress && working && (
        <p className="hint" data-testid="district-progress">
          {props.progress}
        </p>
      )}
      {lost && <p className="hint">Lost the connection to kiripix serve</p>}
      {confirm && (
        <div className="district-confirm" data-testid="district-confirm">
          <p>
            Export would write {confirm.writes.length} file(s) and overwrite {confirm.overwrites.length} the game already holds
            {confirm.overwrites.length > 0 ? " (each is saved to .kiripix/backups/ first)" : ""}.
          </p>
          {confirm.overwrites.length > 0 && (
            <ul data-testid="district-overwrites">
              {confirm.overwrites.map((path) => (
                <li key={path}>
                  <code>{path}</code>
                </li>
              ))}
            </ul>
          )}
          {confirm.findings.length > 0 && (
            <FindingList findings={confirm.findings} onJump={jumpTo(props.onOpen)} testid="district-confirm-findings" />
          )}
          <button className="primary" data-testid="district-confirm-export" onClick={() => void exportNow()}>
            Export {rooms.length} {rooms.length === 1 ? "room" : "rooms"}
          </button>
          <button data-testid="district-confirm-cancel" onClick={() => setConfirm(null)}>
            Not now
          </button>
        </div>
      )}
      {outcome && (
        <div className="district-outcome" data-testid="district-outcome" data-label={outcome.label}>
          <h2>{outcome.label}</h2>
          {outcome.lines.length > 0 && (
            <ul>
              {outcome.lines.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          )}
          {outcome.findings.length === 0 ? (
            <p className="pass" data-testid="district-outcome-clean">
              ✓ Nothing to report
            </p>
          ) : (
            <FindingList findings={outcome.findings} onJump={jumpTo(props.onOpen)} testid="district-findings" />
          )}
        </div>
      )}
      {shown && shown.findings.length > 0 && <FindingList findings={shown.findings} onJump={jumpTo(props.onOpen)} testid="district-notes" />}
      <div className="district-grid" data-testid="district-grid" data-zoom={zoom} ref={host} style={{ gap: GAP }}>
        {rooms.map((room) => (
          <button key={room.asset} className="district-room" data-testid={`district-room-${room.asset}`} onClick={() => props.onOpen(room.asset, null)}>
            <span className="district-image">
              <Thumbnail room={room} zoom={zoom} version={props.imageVersion} />
              {unpaired(room.asset) > 0 && (
                <span className="district-badge" data-testid={`district-badge-${room.asset}`} title="Exits with no Exit back">
                  {unpaired(room.asset)}
                </span>
              )}
            </span>
            <strong>{room.asset}</strong>
            <span className="hint">
              {room.tiles_wide} x {room.tiles_high} tiles
            </span>
            <span className="hint" data-testid={`district-waits-${room.asset}`}>
              {room.waiting ? `waits at ${room.waiting.stage} ${GLYPH[room.waiting.status as keyof typeof GLYPH]}` : "all done"}
            </span>
            <span className="hint" data-testid={`district-queue-${room.asset}`}>
              review {room.queue.review} · input {room.queue.input} · finding {room.queue.finding}
            </span>
          </button>
        ))}
      </div>
      {none && (
        <p className="hint" data-testid="district-empty">
          {shown?.findings[0]?.message ?? `No room matches ${glob}.`}
        </p>
      )}
      {exits.length > 0 && (
        <section className="district-exits" data-testid="district-exits">
          <h2>Exits</h2>
          <ul>
            {exits.map((entry) => {
              // The arrow's heads: two for a paired Exit, one for the rest (a one-way Exit is meant to have no way back).
              const heads = entry.pairing === "paired" ? 2 : 1;
              const text = `${entry.room} ${entry.exit} ${heads === 2 ? "↔" : "→"} ${entry.target_room} ${entry.target_exit}`;
              const bad = entry.pairing === "unpaired" || (entry.pairing === "outside" && entry.code);
              return (
                <li
                  key={`${entry.room}/${entry.exit}`}
                  data-testid={`district-exit-${entry.room}-${entry.exit}`}
                  data-pairing={entry.pairing}
                  data-heads={heads}
                  data-severity={bad ? "error" : undefined}
                >
                  {entry.pairing === "unpaired" ? (
                    <button
                      className="link"
                      data-testid={`district-exit-open-${entry.room}-${entry.exit}`}
                      onClick={() => props.onOpen(entry.room, "place")}
                    >
                      {text}
                    </button>
                  ) : (
                    <span>{text}</span>
                  )}{" "}
                  <span className="district-pairing">{entry.pairing === "one_way" ? "one way" : entry.pairing}</span>
                  {entry.reason && <small className="hint"> {entry.reason}</small>}
                </li>
              );
            })}
          </ul>
        </section>
      )}
      {shown?.data && props.extra?.(shown.data)}
    </section>
  );
}
