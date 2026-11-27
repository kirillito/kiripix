// The Sound screen (ticket 0398, ADR 0016, spec §6.8 and §11): a Sound's recording with its Takes, to listen to and keep. It holds no logic.
// The waveform and the spectrograms are `sound-sheet`'s picture, with a button laid over each Take's box; the Takes' numbers are
// `sound-takes`; a Variation's numbers are `process.json`, read through the file route. Every change is one Command: ticking, unticking
// or dragging a Take is one `decide keep` (the whole list, each Take by its span); a per-Take override is one `decide tune`. Playing
// is the browser's (soundAudio.ts) and records nothing. Parameters and the primary action are the Stage panel's, rendered from `describe`.

import { useEffect, useMemo, useRef, useState } from "react";
import { call, fileUrl, type Envelope, type FileEntry, type Finding, type ShowData, type StageDescription, type StageDetail } from "./api";
import { Player, type Clip } from "./soundAudio";

export const SOUND_KIND = "sound";
export const SOUND_STAGES = ["source", "slice", "keep", "process", "export"];

interface TakeRow {
  number: number;
  start_ms: number;
  onset_ms: number;
  end_ms: number;
  length_ms: number;
  peak_dbfs: number;
  rms_dbfs: number;
  lufs: number;
  centroid_hz: number;
  similarity: number;
  clean_rank: number;
  tail_dbfs: number;
  clipped: boolean;
  overlaps_next: boolean;
  kept: number | null;
}

interface TakesData {
  asset: string;
  rate: number;
  channels: number;
  duration_ms: number;
  mode: string;
  settings: Record<string, number | string>;
  slice_status: string;
  takes: TakeRow[];
}

interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

interface SheetData {
  path: string;
  width: number;
  height: number;
  overview: Rect;
  boxes: (Rect & { take: number; start_ms: number; end_ms: number; kept: number | null; listed: boolean })[];
  rows: { take: number; wave: Rect; processed: { variation: number; wave: Rect } | null }[];
  notes: string[];
}

interface Variation {
  variation: number;
  take: number;
  file: string;
  start_ms: number;
  end_ms: number;
  length_ms: number;
  peak_dbfs: number;
  lufs: number;
  loop: boolean;
  loop_offset: number | null;
  loop_match: number | null;
  settings: Record<string, number | string>;
  overridden: boolean;
}

interface ProcessRecord {
  use: string;
  variations: Variation[];
}

interface Span {
  start_ms: number;
  end_ms: number;
}

interface ExportPlan {
  dry_run: boolean;
  written: string[];
  would_write: string[];
  unchanged: string[];
  backed_up: string[];
  changed: string[];
  unmanaged: string[];
}

export type SoundAct = (label: string, command: string, input: object) => Promise<Envelope<unknown> | null>;
export interface Provenance {
  url: string;
  author: string;
  licence: string;
}

const STEP_MS = 450; // a walking pace, start to start

function typing(event: KeyboardEvent): boolean {
  const target = event.target as HTMLElement | null;
  return !!target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.tagName === "SELECT" || target.isContentEditable);
}

const ms = (value: number) => `${Math.round(value)} ms`;
const db = (value: number) => value.toFixed(1);

function outputOf(show: ShowData, stage: string, name: string): string | null {
  const found = show.stages.find((one) => one.stage === stage)?.outputs.find((path) => path.endsWith(`/${name}`));
  return found ?? null;
}

// The latest `keep` Decision's spans, in order: the Owner's list as it is recorded, whether or not each still matches a Take.
function keptSpans(detail: StageDetail | undefined): Span[] {
  const latest = [...(detail?.decisions ?? [])].reverse().find((entry) => entry.name === "keep");
  const takes = latest?.data.takes;
  return Array.isArray(takes) ? (takes as Span[]).map((span) => ({ start_ms: span.start_ms, end_ms: span.end_ms })) : [];
}

export function SoundScreen(props: {
  show: ShowData;
  stage: string;
  stages: StageDescription[] | undefined; // the Kind's Stages from `describe`
  findings: Finding[];
  refreshes: number;
  imageVersion: number;
  disabled: boolean;
  act: SoundAct;
  onPick: (variant: string) => void;
  onImport: (file: File, provenance: Provenance) => void;
}) {
  const { show, stage, disabled, act } = props;
  const name = show.asset.slice(show.asset.indexOf(".") + 1);
  const player = useMemo(() => new Player(), []);
  const [takes, setTakes] = useState<TakesData | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [sheet, setSheet] = useState<SheetData | null>(null);
  const [sheetVersion, setSheetVersion] = useState(0);
  const [processed, setProcessed] = useState<ProcessRecord | null>(null);
  const [selected, setSelected] = useState<number | null>(null); // a Take's number
  const [heard, setHeard] = useState<"source" | "processed">("source"); // what a click plays: A or B
  const [interval, setIntervalMs] = useState(STEP_MS);
  const [sequencing, setSequencing] = useState(false);
  const [log, setLog] = useState<string[]>([]); // what has been played, for the tests and for the Owner's own record of it
  const [dragging, setDragging] = useState<number | null>(null);
  const [plan, setPlan] = useState<{ plan: ExportPlan; findings: Finding[] } | null>(null);
  const [exported, setExported] = useState<string | null>(null);

  const keepStage = show.stages.find((one) => one.stage === "keep");
  const spans = keptSpans(keepStage);
  const sourceFile = outputOf(show, "source", "source.wav");
  const processPath = outputOf(show, "process", "process.json");
  const withTakes = stage === "slice" || stage === "keep" || stage === "process";
  const buildable = (name: string) => show.stages.find((one) => one.stage === name)?.status;

  // The Takes and the picture, asked again whenever the Project's views refreshed.
  useEffect(() => {
    if (!withTakes) return;
    let live = true;
    void call<TakesData>("sound-takes", { asset: show.asset })
      .then((answer) => {
        if (!live) return;
        setTakes(answer.data);
        setNote(answer.data ? null : (answer.findings[0]?.message ?? "No Takes."));
      })
      .catch(() => live && setNote("Lost the connection to kiripix serve."));
    void call<SheetData>("sound-sheet", { asset: show.asset, out: `.kiripix/previews/sound-${name}.png` })
      .then((answer) => {
        if (!live) return;
        setSheet(answer.data);
        setSheetVersion((count) => count + 1);
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [show.asset, name, withTakes, props.refreshes, props.imageVersion]);

  useEffect(() => {
    if (!processPath || !(stage === "process" || stage === "keep" || stage === "export")) {
      setProcessed(null);
      return;
    }
    let live = true;
    void fetch(fileUrl(processPath))
      .then((response) => (response.ok ? (response.json() as Promise<ProcessRecord>) : null))
      .then((record) => live && setProcessed(record))
      .catch(() => live && setProcessed(null));
    return () => {
      live = false;
    };
  }, [processPath, stage, props.refreshes, props.imageVersion]);

  useEffect(() => () => player.stop(), [player]);

  const rows = takes?.takes ?? [];
  const byNumber = (number: number) => rows.find((one) => one.number === number);
  const variationOf = (take: TakeRow): Variation | null => {
    if (take.kept === null || !processed) return null;
    return processed.variations.find((one) => one.variation === take.kept) ?? null;
  };
  const processedFresh = buildable("process") === "done";

  const clipOf = (take: TakeRow, which: "source" | "processed"): Clip | null => {
    if (which === "processed") {
      const variation = variationOf(take);
      const file = variation && processPath ? processPath.replace(/process\.json$/, variation.file) : null;
      return variation && file ? { url: fileUrl(file), startMs: 0, endMs: null, label: `processed:${variation.variation}` } : null;
    }
    return sourceFile ? { url: fileUrl(sourceFile), startMs: take.start_ms, endMs: take.end_ms, label: `source:${take.number}` } : null;
  };
  const playTake = (number: number, which: "source" | "processed" = heard) => {
    const take = byNumber(number);
    if (!take) return;
    setSelected(number);
    const clip = clipOf(take, which);
    if (!clip) return;
    player.stop();
    setSequencing(false);
    setLog((now) => [...now, clip.label].slice(-50));
    void player.play(clip).catch(() => setLog((now) => [...now, `error:${clip.label}`]));
  };
  // A and B for the selected Take, one after the other.
  const compare = (number: number) => {
    const take = byNumber(number);
    if (!take) return;
    setSelected(number);
    const clips = (["source", "processed"] as const).map((which) => clipOf(take, which)).filter((clip): clip is Clip => clip !== null);
    setSequencing(true);
    player.sequence(
      clips,
      Math.round(take.end_ms - take.start_ms) + 250,
      (_, clip) => setLog((now) => [...now, clip.label].slice(-50)),
      () => setSequencing(false),
    );
  };
  // The kept set in order, at the interval, as the game will play it.
  const playKept = () => {
    const clips: Clip[] = [];
    spans.forEach((_, index) => {
      const take = rows.find((one) => one.kept === index + 1);
      const clip = take ? clipOf(take, heard) : null;
      if (clip) clips.push(clip);
    });
    if (clips.length === 0) return;
    setSequencing(true);
    player.sequence(
      clips,
      Math.max(20, interval),
      (_, clip) => setLog((now) => [...now, `seq:${clip.label}`].slice(-50)),
      () => setSequencing(false),
    );
  };
  const stopAll = () => {
    player.stop();
    setSequencing(false);
  };

  // Keyboard: the number keys play Take N, X is A/B (source or processed), K keeps or drops the selected Take, S plays the kept set,
  // Space plays or stops the selected Take, Esc stops.
  const keys = useRef({ playTake, stopAll, playKept, toggle: (_: number) => {}, selected, rows, sequencing });
  const toggleKept = (number: number, on: boolean) => {
    const take = byNumber(number);
    if (!take || disabled) return;
    if (on) void decideKeep([...spans, { start_ms: take.start_ms, end_ms: take.end_ms }]);
    else if (take.kept !== null) void decideKeep(spans.filter((_, index) => index !== (take.kept as number) - 1));
  };
  keys.current = { playTake, stopAll, playKept, toggle: (number) => toggleKept(number, byNumber(number)?.kept === null), selected, rows, sequencing };
  useEffect(() => {
    if (!withTakes) return;
    const onKey = (event: KeyboardEvent) => {
      if (typing(event) || event.ctrlKey || event.metaKey || event.altKey) return;
      const now = keys.current;
      const key = event.key.toLowerCase();
      if (/^[1-9]$/.test(event.key)) {
        const take = now.rows[Number(event.key) - 1];
        if (take) now.playTake(take.number);
      } else if (key === "x") setHeard((was) => (was === "source" ? "processed" : "source"));
      else if (key === "k" && stage === "keep" && now.selected !== null) now.toggle(now.selected);
      else if (key === "s") now.playKept();
      else if (key === " " && now.selected !== null) {
        event.preventDefault();
        if (now.sequencing) now.stopAll();
        else now.playTake(now.selected);
      } else if (key === "escape") now.stopAll();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [withTakes, stage]);

  // One `decide keep` of the whole list.
  const decideKeep = (next: Span[]) =>
    act("Keeping Takes", "decide", { asset: show.asset, stage: "keep", decision: JSON.stringify({ decision: "keep", data: { takes: next } }) });
  const move = (from: number, to: number) => {
    if (to < 0 || to >= spans.length || from === to || disabled) return;
    const next = [...spans];
    const [one] = next.splice(from, 1);
    next.splice(to, 0, one);
    void decideKeep(next);
  };

  // The per-Take override form is built from the `tune` Decision's schema in `describe`.
  const tune = props.stages?.find((one) => one.name === "process")?.decisions.find((one) => one.name === "tune");
  const tuneFields = Object.entries(tune?.entry_schema?.properties ?? {}).filter(([field]) => field !== "start_ms" && field !== "end_ms");
  const [tuning, setTuning] = useState<Record<string, string>>({});
  const decideTune = (variation: number) => {
    const span = spans[variation - 1];
    if (!span) return;
    const data: Record<string, unknown> = { start_ms: span.start_ms, end_ms: span.end_ms };
    for (const [field, text] of Object.entries(tuning)) {
      if (text === "") continue;
      const spec = tune?.entry_schema?.properties?.[field];
      data[field] = spec?.enum ? text : Number(text);
    }
    if (Object.keys(data).length === 2) return;
    void act("Tuning a Variation", "decide", { asset: show.asset, stage: "process", decision: JSON.stringify({ decision: "tune", data }) }).then(() => setTuning({}));
  };

  const checkExport = async () => {
    setExported(null);
    const result = await act("Checking what export writes", "export", { asset: show.asset, dry_run: true });
    if (result?.ok && result.data) setPlan({ plan: result.data as ExportPlan, findings: result.findings });
    else setPlan(null);
  };
  const approveExport = async () => {
    const result = await act(`Exporting ${show.asset}`, "export", { asset: show.asset });
    setPlan(null);
    const done = result?.data as ExportPlan | null | undefined;
    setExported(result?.ok && done ? `${done.written.length} file(s) written, ${done.unchanged.length} unchanged` : null);
  };

  const [provenance, setProvenance] = useState<Provenance>({ url: "", author: "", licence: "" });
  const choose = useRef<HTMLInputElement>(null);

  const sheetImage = sheet && withTakes && (
    <div className="sound-sheet-box" data-testid="sound-sheet" style={{ width: sheet.width, height: sheet.height }}>
      <img
        className="sound-sheet"
        data-testid="sound-sheet-image"
        src={`${fileUrl(sheet.path)}&r=${sheetVersion}`}
        width={sheet.width}
        height={sheet.height}
        alt={`${show.asset}: the recording with its Takes boxed and numbered`}
      />
      {sheet.boxes.map((box) => (
        <button
          key={`box-${box.take}`}
          className="sound-box"
          data-testid={`sheet-box-${box.take}`}
          data-kept={box.kept ?? ""}
          aria-pressed={selected === box.take}
          aria-label={`Play Take ${box.take}`}
          title={`Take ${box.take}: ${ms(box.start_ms)} to ${ms(box.end_ms)}`}
          style={{ left: box.x, top: box.y, width: box.width, height: box.height }}
          onClick={() => playTake(box.take, "source")}
        />
      ))}
      {sheet.rows.map((row) => (
        <span key={`row-${row.take}`}>
          <button
            className="sound-box"
            data-testid={`sheet-row-${row.take}`}
            aria-label={`Play Take ${row.take}`}
            style={{ left: row.wave.x, top: row.wave.y, width: row.wave.width, height: row.wave.height }}
            onClick={() => playTake(row.take, "source")}
          />
          {row.processed && (
            <button
              className="sound-box"
              data-testid={`sheet-processed-${row.take}`}
              aria-label={`Play Variation ${row.processed.variation}, processed`}
              style={{ left: row.processed.wave.x, top: row.processed.wave.y, width: row.processed.wave.width, height: row.processed.wave.height }}
              onClick={() => playTake(row.take, "processed")}
            />
          )}
        </span>
      ))}
    </div>
  );

  const flags = (take: TakeRow) => [take.clipped ? "clipped" : "", take.overlaps_next ? "runs into the next" : "", take.clean_rank === 1 ? "cleanest" : ""].filter(Boolean).join(", ");

  const transport = (
    <div className="sound-transport" data-testid="sound-transport">
      <span className="hint">Play</span>
      <button data-testid="heard-source" aria-pressed={heard === "source"} onClick={() => setHeard("source")} title="The Take as recorded">
        Source (A)
      </button>
      <button data-testid="heard-processed" aria-pressed={heard === "processed"} onClick={() => setHeard("processed")} title="The Variation after process">
        Processed (B)
      </button>
      <span className="hint">(X swaps)</span>
      <label>
        Interval{" "}
        <input
          type="number"
          data-testid="seq-interval"
          min={20}
          max={10000}
          step={10}
          value={interval}
          onChange={(event) => setIntervalMs(Number(event.target.value) || STEP_MS)}
        />{" "}
        ms
      </label>
      <button data-testid="seq-play" disabled={spans.length === 0} onClick={playKept} title="The kept Takes in order, each starting one interval after the one before (S)">
        Play the kept set (S)
      </button>
      <button data-testid="seq-stop" disabled={!sequencing} onClick={stopAll}>
        Stop
      </button>
    </div>
  );

  const takeTable = (
    <table className="sound-takes" data-testid="sound-takes">
      <thead>
        <tr>
          {stage === "keep" && <th>Keep</th>}
          <th>Take</th>
          <th>Start</th>
          <th>Length</th>
          <th>Peak dBFS</th>
          <th>LUFS</th>
          <th>Centroid</th>
          <th>Like the rest</th>
          <th>Cleanness</th>
          <th>Variation</th>
          <th />
        </tr>
      </thead>
      <tbody>
        {rows.map((take) => {
          const variation = variationOf(take);
          return (
            <tr key={take.number} data-testid={`sound-take-${take.number}`} data-selected={selected === take.number} data-kept={take.kept ?? ""}>
              {stage === "keep" && (
                <td>
                  <input
                    type="checkbox"
                    data-testid={`take-keep-${take.number}`}
                    checked={take.kept !== null}
                    disabled={disabled}
                    aria-label={`Keep Take ${take.number}`}
                    onChange={(event) => toggleKept(take.number, event.target.checked)}
                  />
                </td>
              )}
              <td>
                {take.number <= 9 && <kbd>{take.number}</kbd>} {take.number}
              </td>
              <td>{ms(take.start_ms)}</td>
              <td>{ms(take.length_ms)}</td>
              <td>{db(take.peak_dbfs)}</td>
              <td>{db(take.lufs)}</td>
              <td>{Math.round(take.centroid_hz)} Hz</td>
              <td>{Math.round(take.similarity * 100)}%</td>
              <td>
                {take.clean_rank}
                {flags(take) && <span className="hint"> {flags(take)}</span>}
              </td>
              <td>{take.kept ?? ""}</td>
              <td>
                <button data-testid={`take-play-${take.number}`} onClick={() => playTake(take.number, "source")}>
                  Play
                </button>
                {variation && (
                  <>
                    <button data-testid={`take-play-processed-${take.number}`} onClick={() => playTake(take.number, "processed")}>
                      Play processed
                    </button>
                    <button data-testid={`take-ab-${take.number}`} onClick={() => compare(take.number)} title="The Take, then the Variation">
                      A/B
                    </button>
                  </>
                )}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );

  const keptList = stage === "keep" && (
    <section className="sound-kept" data-testid="sound-kept">
      <h2>Kept Takes, in Variation order</h2>
      {spans.length === 0 ? (
        <p className="hint" data-testid="sound-kept-none">
          No Take is kept yet. Tick the Takes to keep.
        </p>
      ) : (
        <ol className="sound-kept-list">
          {spans.map((span, index) => {
            const take = rows.find((one) => one.kept === index + 1);
            return (
              <li
                key={`${span.start_ms}-${span.end_ms}`}
                className={`sound-kept-item${dragging === index ? " dragging" : ""}`}
                data-testid={`kept-${index + 1}`}
                data-take={take?.number ?? ""}
                data-missing={!take}
                draggable={!disabled}
                onDragStart={() => setDragging(index)}
                onDragEnd={() => setDragging(null)}
                onDragOver={(event) => dragging !== null && event.preventDefault()}
                onDrop={(event) => {
                  event.preventDefault();
                  if (dragging !== null) move(dragging, index);
                  setDragging(null);
                }}
              >
                <strong>{index + 1}</strong>{" "}
                {take ? (
                  <button className="link" onClick={() => playTake(take.number)}>
                    Take {take.number}
                  </button>
                ) : (
                  <span className="reason">no Take matches</span>
                )}{" "}
                <span className="hint">
                  {ms(span.start_ms)} to {ms(span.end_ms)}
                </span>
                <button data-testid={`kept-up-${index + 1}`} aria-label={`Move Variation ${index + 1} up`} disabled={disabled || index === 0} onClick={() => move(index, index - 1)}>
                  ↑
                </button>
                <button
                  data-testid={`kept-down-${index + 1}`}
                  aria-label={`Move Variation ${index + 1} down`}
                  disabled={disabled || index === spans.length - 1}
                  onClick={() => move(index, index + 1)}
                >
                  ↓
                </button>
                <button
                  data-testid={`kept-drop-${index + 1}`}
                  aria-label={`Drop Variation ${index + 1}`}
                  disabled={disabled}
                  onClick={() => void decideKeep(spans.filter((_, at) => at !== index))}
                >
                  Drop
                </button>
              </li>
            );
          })}
        </ol>
      )}
      <p className="hint">Drag to reorder, or use the arrows. Each change is one Decision.</p>
    </section>
  );

  const variations = stage === "process" && (
    <section className="sound-variations" data-testid="sound-variations">
      <h2>Variations</h2>
      {!processed || processed.variations.length === 0 ? (
        <p className="hint" data-testid="sound-variations-none">
          Nothing is processed yet. Run the Stage.
        </p>
      ) : (
        <>
          {!processedFresh && <p className="reason">What follows is from an earlier run: run the Stage again.</p>}
          <table data-testid="sound-variation-table">
            <thead>
              <tr>
                <th>Variation</th>
                <th>Take</th>
                <th>Length</th>
                <th>Peak dBFS</th>
                <th>LUFS</th>
                <th>Loop</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {processed.variations.map((one) => (
                <tr key={one.variation} data-testid={`variation-${one.variation}`} data-overridden={one.overridden}>
                  <td>{one.variation}</td>
                  <td>
                    <button className="link" onClick={() => setSelected(one.take)}>
                      {one.take}
                    </button>
                  </td>
                  <td>{ms(one.length_ms)}</td>
                  <td>{db(one.peak_dbfs)}</td>
                  <td>{db(one.lufs)}</td>
                  <td>{one.loop ? `loop${one.loop_match !== null ? ` (match ${one.loop_match.toFixed(2)})` : ""}` : ""}</td>
                  <td>
                    <button data-testid={`variation-play-${one.variation}`} onClick={() => playTake(one.take, "processed")}>
                      Play processed
                    </button>
                    <button data-testid={`variation-source-${one.variation}`} onClick={() => playTake(one.take, "source")}>
                      Play source
                    </button>
                    <button data-testid={`variation-ab-${one.variation}`} onClick={() => compare(one.take)}>
                      A/B
                    </button>
                    {one.overridden && <span className="hint"> tuned</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {tuneFields.length > 0 && selected !== null && (byNumber(selected)?.kept ?? null) !== null && (
            <details className="sound-tune" data-testid="sound-tune" open>
              <summary>Tune Variation {byNumber(selected)?.kept} only</summary>
              <p className="hint">Leave a field empty to keep the Stage's value. Filling some and pressing Tune is one Decision.</p>
              <div className="sound-tune-fields">
                {tuneFields.map(([field, spec]) => {
                  const now = processed.variations.find((one) => one.variation === byNumber(selected)?.kept)?.settings[field];
                  return (
                    <label key={field}>
                      {field}{" "}
                      {spec.enum ? (
                        <select data-testid={`tune-${field}`} value={tuning[field] ?? ""} onChange={(event) => setTuning((was) => ({ ...was, [field]: event.target.value }))}>
                          <option value="">{String(now ?? "")}</option>
                          {spec.enum.map((choice) => (
                            <option key={choice}>{choice}</option>
                          ))}
                        </select>
                      ) : (
                        <input
                          type="number"
                          data-testid={`tune-${field}`}
                          min={spec.minimum}
                          max={spec.maximum}
                          step="any"
                          placeholder={now === undefined ? "" : String(now)}
                          value={tuning[field] ?? ""}
                          onChange={(event) => setTuning((was) => ({ ...was, [field]: event.target.value }))}
                        />
                      )}
                    </label>
                  );
                })}
              </div>
              <button data-testid="tune-apply" disabled={disabled} onClick={() => decideTune(byNumber(selected)?.kept as number)}>
                Tune
              </button>
            </details>
          )}
        </>
      )}
    </section>
  );

  if (stage === "source") {
    return (
      <div className="sound-screen" data-testid="sound-screen" data-stage={stage}>
        <h2>Recordings</h2>
        {show.variants.length === 0 && (
          <p className="hint" data-testid="sound-no-recording">
            No recording is imported yet. Choose a file below (WAV, FLAC, MP3 or OGG).
          </p>
        )}
        <ul className="sound-recordings">
          {show.variants.map((variant: FileEntry, index) => (
            <li key={variant.name} data-testid={`variant-${variant.name}`} data-picked={show.picked === variant.name}>
              {index < 9 && <kbd>{index + 1}</kbd>}{" "}
              <button
                data-testid={`recording-pick-${variant.name}`}
                aria-pressed={show.picked === variant.name}
                disabled={disabled}
                onClick={() => props.onPick(variant.name)}
              >
                {show.picked === variant.name ? "Picked" : "Pick"}
              </button>{" "}
              <button
                data-testid={`recording-play-${variant.name}`}
                onClick={() => {
                  player.stop();
                  setLog((now) => [...now, `recording:${variant.name}`]);
                  void player.play({ url: fileUrl(variant.file), startMs: 0, endMs: null, label: variant.name });
                }}
              >
                Play
              </button>{" "}
              {variant.imported_as ?? variant.name}
            </li>
          ))}
        </ul>
        <h2>Import a recording</h2>
        <p className="hint">Provenance is stored as you type it, and the game credits it. Only you confirm the licence.</p>
        <div className="sound-provenance">
          {(["author", "licence", "url"] as const).map((field) => (
            <label key={field}>
              {field === "url" ? "Where from (URL or name)" : field === "author" ? "Author" : "Licence"}{" "}
              <input data-testid={`provenance-${field}`} value={provenance[field]} onChange={(event) => setProvenance((was) => ({ ...was, [field]: event.target.value }))} />
            </label>
          ))}
        </div>
        <button data-testid="sound-choose-file" disabled={disabled} onClick={() => choose.current?.click()}>
          Choose a recording
        </button>
        <input
          ref={choose}
          data-testid="sound-import-input"
          type="file"
          accept=".wav,.flac,.mp3,.ogg,audio/*"
          hidden
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) props.onImport(file, provenance);
            event.target.value = "";
          }}
        />
        <SoundLog log={log} />
      </div>
    );
  }

  if (stage === "export") {
    const files = (show.stages.find((one) => one.stage === "export")?.outputs ?? []).filter((path) => path.endsWith(".ogg"));
    return (
      <div className="sound-screen" data-testid="sound-screen" data-stage={stage}>
        <h2>Variations to export</h2>
        {files.length === 0 ? (
          <p className="hint" data-testid="sound-export-none">
            Nothing is encoded yet. Run the Stage.
          </p>
        ) : (
          <ol className="sound-files">
            {files.map((path, index) => (
              <li key={path} data-testid={`export-file-${index + 1}`}>
                {path.slice(path.lastIndexOf("/") + 1)}{" "}
                <button
                  data-testid={`export-play-${index + 1}`}
                  onClick={() => {
                    player.stop();
                    setLog((now) => [...now, `export:${index + 1}`]);
                    void player.play({ url: fileUrl(path), startMs: 0, endMs: null, label: path }).catch(() => setLog((now) => [...now, `error:export:${index + 1}`]));
                  }}
                >
                  Play
                </button>
              </li>
            ))}
          </ol>
        )}
        <div className="sound-export">
          <button className="primary" data-testid="sound-export-check" disabled={disabled || files.length === 0} onClick={() => void checkExport()}>
            Export to the game…
          </button>
          {plan && (
            <div className="sound-export-plan" data-testid="sound-export-plan">
              <p>
                Export would write {plan.plan.would_write.length} file(s) and leave {plan.plan.unchanged.length} as they are.
                {plan.plan.backed_up.length > 0 && ` It would back up and overwrite ${plan.plan.backed_up.length} the game already holds.`}
              </p>
              <ul>
                {plan.plan.would_write.map((path) => (
                  <li key={path}>{path}</li>
                ))}
              </ul>
              {plan.plan.changed.length > 0 && <p className="reason">The game changed {plan.plan.changed.join(", ")}: export refuses these without --force.</p>}
              {plan.plan.unmanaged.length > 0 && <p className="reason">The game already has {plan.plan.unmanaged.join(", ")}: export refuses these without --adopt.</p>}
              <button className="primary" data-testid="sound-export-approve" disabled={disabled} onClick={() => void approveExport()}>
                Approve the export
              </button>{" "}
              <button data-testid="sound-export-cancel" onClick={() => setPlan(null)}>
                Cancel
              </button>
            </div>
          )}
          {exported && (
            <p className="pass" data-testid="sound-exported">
              ✓ {exported}
            </p>
          )}
        </div>
        <SoundLog log={log} />
      </div>
    );
  }

  return (
    <div className="sound-screen" data-testid="sound-screen" data-stage={stage} data-playing={sequencing}>
      {note && (
        <p className="hint" data-testid="sound-note">
          {note}
        </p>
      )}
      {takes && (
        <p className="hint" data-testid="sound-summary">
          {rows.length} Take{rows.length === 1 ? "" : "s"} in {(takes.duration_ms / 1000).toFixed(2)} s ({takes.mode}
          {takes.slice_status !== "done" ? `; slice is ${takes.slice_status}: run it again` : ""}). Click a Take to hear it; keys 1 to 9 play a Take.
        </p>
      )}
      {transport}
      <div className="sound-sheet-scroll">{sheetImage}</div>
      {keptList}
      {takeTable}
      {variations}
      <SoundLog log={log} />
    </div>
  );
}

function SoundLog({ log }: { log: string[] }) {
  return <span className="sound-log" data-testid="sound-log" data-log={log.join(",")} data-plays={log.length} />;
}
