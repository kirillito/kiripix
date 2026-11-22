// The NPC screen (ticket 0360, ADR 0015, spec §6.3, §11): an NPC's `choose` Stage as a figure the Owner dresses, and a crowd's strip on
// the status board. The figure is `preview --stage choose` (the base's idle, one frame per direction, Wearables stacked and colours
// swapped by the Command), drawn at a whole-number zoom and never scaled by the page. Each change is one `set` of one of `choose`'s
// parameters (`wearables`, `colours`); the screen holds the two strings the Stage holds and nothing else. What it computes is
// display math on those strings: the `id@N` order that puts a dragged Wearable between its neighbours.

import { useEffect, useRef, useState, type ReactNode } from "react";
import { call, fileUrl, type Envelope, type Finding, type ShowData, type StageDetail, type StatusData } from "./api";
import type { WearableInfo } from "./wearableScreens";
import { useInView } from "./virtualRows";

export const NPC_KIND = "npc";
export const NPC_STAGE = "choose";
const ZOOMS = [1, 2, 3, 4];

// A ramp table row with the named choices an NPC may pick (`describe project`).
interface RampRow {
  name: string;
  length: number;
  choices: Record<string, number[][]>;
}

interface PreviewData {
  path: string;
  width: number;
  height: number;
  zoom: number;
}

// What a finding of `choose` names: a Wearable of the stack or a Part of the table. `count` makes the same finding focus again.
export interface NpcFocus {
  kind: "wearable" | "part";
  name: string;
  count: number;
}

export function npcFocusOf(finding: Finding): Omit<NpcFocus, "count"> | null {
  if (!finding.code.startsWith("npc.")) return null;
  const field = finding.position?.field ?? "";
  const [head, ...rest] = field.split("/");
  const tail = rest.join("/");
  const wearable = typeof finding.data?.wearable === "string" ? finding.data.wearable : head === "wearables" ? tail : "";
  if (wearable) return { kind: "wearable", name: wearable };
  const part = typeof finding.data?.part === "string" ? finding.data.part : head === "colours" ? tail : "";
  return part ? { kind: "part", name: part } : null;
}

interface Worn {
  id: string;
  order: number | null; // this NPC's own `id@N`; null when it takes the Wearable's own
}

function parseWearables(text: unknown): Worn[] {
  if (typeof text !== "string") return [];
  return text
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => {
      const [id, order] = item.split("@");
      return { id: id.trim(), order: order !== undefined && /^-?\d+$/.test(order.trim()) ? Number(order) : null };
    });
}

function writeWearables(worn: Worn[]): string {
  return worn.map((one) => (one.order === null ? one.id : `${one.id}@${one.order}`)).join(",");
}

function parseColours(text: unknown): Record<string, string> {
  const found: Record<string, string> = {};
  if (typeof text !== "string") return found;
  for (const item of text.split(",")) {
    const [part, choice] = item.split("=");
    if (part?.trim() && choice?.trim()) found[part.trim()] = choice.trim();
  }
  return found;
}

// The stack, bottom to top: the lowest order first, an equal order by ID (the Stage's own rule).
function stacked(worn: Worn[], own: (id: string) => number): { id: string; order: number }[] {
  return worn
    .map((one) => ({ id: one.id, order: one.order ?? own(one.id) }))
    .sort((a, b) => a.order - b.order || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
}

// `id` moved to `index` of the stack (bottom to top): it takes an order strictly between its new neighbours, and where there is no
// room every Wearable of the stack is numbered again in tens.
export function moveInStack(stack: { id: string; order: number }[], id: string, index: number): Worn[] {
  const rest = stack.filter((one) => one.id !== id);
  const at = Math.max(0, Math.min(index, rest.length));
  const below = rest[at - 1];
  const above = rest[at];
  let order: number | null = null;
  if (below && above) {
    const middle = Math.floor((below.order + above.order) / 2);
    if (middle > below.order && middle < above.order) order = middle;
  } else if (below) order = below.order + 10;
  else if (above) order = above.order - 10;
  else order = stack.find((one) => one.id === id)?.order ?? 10;
  if (order !== null) {
    const kept = new Map(stack.map((one) => [one.id, one.order]));
    const sequence = [...rest.slice(0, at).map((one) => one.id), id, ...rest.slice(at).map((one) => one.id)];
    return sequence.map((one) => ({ id: one, order: one === id ? order : (kept.get(one) as number) }));
  }
  const sequence = [...rest.slice(0, at), { id, order: 0 }, ...rest.slice(at)];
  return sequence.map((one, number) => ({ id: one.id, order: (number + 1) * 10 }));
}

function useRamps(refreshes: number): RampRow[] {
  const [rows, setRows] = useState<RampRow[]>([]);
  useEffect(() => {
    let live = true;
    void call<{ ramps: RampRow[] | null }>("describe", { target: "project" })
      .then((answer) => live && setRows(answer.data?.ramps ?? []))
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [refreshes]);
  return rows;
}

function typing(event: KeyboardEvent): boolean {
  const target = event.target as HTMLElement | null;
  return !!target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.tagName === "SELECT" || target.isContentEditable);
}

export function NpcScreen(props: {
  show: ShowData;
  detail: StageDetail;
  wearables: WearableInfo[]; // the Wearables made on the NPC's base
  findings: Finding[];
  focus: NpcFocus | null;
  refreshes: number;
  imageVersion: number;
  disabled: boolean;
  onSet: (name: string, value: string) => void; // one `set` of one `choose` parameter, then the Stage again
}) {
  const { show, detail, wearables, findings, focus, disabled } = props;
  const ramps = useRamps(props.refreshes);
  const [zoom, setZoom] = useState(2);
  const [preview, setPreview] = useState<PreviewData | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const [dragging, setDragging] = useState<string | null>(null);
  const focused = useRef<HTMLElement | null>(null);

  const worn = parseWearables(detail.params.wearables);
  const colours = parseColours(detail.params.colours);
  const own = (id: string) => wearables.find((one) => one.id === id)?.order ?? 0;
  const stack = stacked(worn, own); // bottom to top
  const unworn = wearables.filter((one) => !worn.some((entry) => entry.id === one.id)).sort((a, b) => a.order - b.order);
  const parts = ramps.filter((row) => Object.keys(row.choices).length > 0);
  const buildable = detail.status === "done" || detail.status === "stale" || detail.status === "needs-review";

  // The figure, drawn by the Command each time the Project's views have refreshed.
  useEffect(() => {
    let live = true;
    if (!buildable) {
      setPreview(null);
      setNote(detail.reason);
      return;
    }
    void call<PreviewData>("preview", { asset: show.asset, stage: NPC_STAGE, zoom })
      .then((answer) => {
        if (!live) return;
        setPreview(answer.data);
        setNote(answer.data ? null : (answer.findings[0]?.message ?? "No preview."));
        setVersion((count) => count + 1);
      })
      .catch(() => live && setNote("Lost the connection to kiripix serve."));
    return () => {
      live = false;
    };
  }, [show.asset, zoom, props.refreshes, props.imageVersion, buildable, detail.reason]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (typing(event) || event.ctrlKey || event.metaKey || event.altKey || event.key.toLowerCase() !== "z") return;
      setZoom((now) => ZOOMS[(ZOOMS.indexOf(now) + 1) % ZOOMS.length]);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    focused.current?.scrollIntoView({ block: "nearest" });
  }, [focus?.count]);

  const toggle = (id: string, on: boolean) => {
    const next = on ? [...stack.map((one) => one.id), id] : stack.map((one) => one.id).filter((one) => one !== id);
    const orders = new Map(worn.map((one) => [one.id, one.order]));
    props.onSet("wearables", writeWearables(next.map((one) => ({ id: one, order: orders.get(one) ?? null }))));
  };
  const move = (id: string, index: number) => {
    if (index < 0 || index >= stack.length || stack[index].id === id) return;
    // Only the moved Wearable gets an order of its own, unless the stack had to be numbered again.
    const before = new Map(worn.map((one) => [one.id, one.order]));
    const effective = new Map(stack.map((one) => [one.id, one.order]));
    const moved = moveInStack(stack, id, index).map((one) => ({
      id: one.id,
      order: one.id !== id && effective.get(one.id) === one.order ? (before.get(one.id) ?? null) : one.order,
    }));
    props.onSet("wearables", writeWearables(moved));
  };
  const pick = (part: string, choice: string | null) => {
    const next = { ...colours };
    if (choice === null) delete next[part];
    else next[part] = choice;
    props.onSet(
      "colours",
      ramps
        .filter((row) => next[row.name])
        .map((row) => `${row.name}=${next[row.name]}`)
        .join(","),
    );
  };
  const mark = (kind: NpcFocus["kind"], name: string) => (focus && focus.kind === kind && focus.name === name ? { "data-focused": "true", ref: (node: HTMLElement | null) => { if (node) focused.current = node; } } : {});

  const problems = findings.filter((finding) => finding.code.startsWith("npc."));
  const row = (id: string, order: number, index: number | null): ReactNode => (
    <li
      key={id}
      className={`npc-wearable${dragging === id ? " dragging" : ""}`}
      data-testid={`npc-wearable-${id}`}
      data-worn={index !== null}
      draggable={index !== null && !disabled}
      onDragStart={() => setDragging(id)}
      onDragEnd={() => setDragging(null)}
      onDragOver={(event) => index !== null && dragging && event.preventDefault()}
      onDrop={(event) => {
        event.preventDefault();
        if (index !== null && dragging) move(dragging, index);
        setDragging(null);
      }}
      {...mark("wearable", id)}
    >
      <label>
        <input type="checkbox" data-testid={`npc-wear-${id}`} checked={index !== null} disabled={disabled} onChange={(event) => toggle(id, event.target.checked)} />
        {id}
      </label>
      <span className="hint"> order {order}</span>
      {index !== null && (
        <>
          <button data-testid={`npc-up-${id}`} aria-label={`Move ${id} up`} disabled={disabled || index === stack.length - 1} onClick={() => move(id, index + 1)}>
            ↑
          </button>
          <button data-testid={`npc-down-${id}`} aria-label={`Move ${id} down`} disabled={disabled || index === 0} onClick={() => move(id, index - 1)}>
            ↓
          </button>
        </>
      )}
    </li>
  );

  return (
    <div className="npc-screen" data-testid="npc-screen">
      <div className="npc-figure">
        <div className="npc-controls">
          <span className="hint">Zoom</span>
          {ZOOMS.map((one) => (
            <button key={one} data-testid={`npc-zoom-${one}`} aria-pressed={zoom === one} onClick={() => setZoom(one)}>
              {one}x
            </button>
          ))}
          <span className="hint">(Z)</span>
        </div>
        {preview ? (
          <img
            className="npc-preview"
            data-testid="npc-preview"
            data-zoom={preview.zoom}
            data-width={preview.width}
            data-height={preview.height}
            data-wearing={stack.map((one) => one.id).join(",")}
            data-colours={Object.entries(colours).map(([part, choice]) => `${part}=${choice}`).join(",")}
            src={`${fileUrl(preview.path)}&r=${version}`}
            width={preview.width}
            height={preview.height}
            alt={`${show.asset}, one frame for each direction`}
          />
        ) : (
          <p className="hint" data-testid="npc-preview-note">
            {note ?? "Drawing the figure…"}
          </p>
        )}
        {preview && note && <p className="hint">{note}</p>}
      </div>
      <div className="npc-choices">
        <h2>Wearables on {show.base ?? "the base"}</h2>
        {stack.length + unworn.length === 0 ? (
          <p className="hint" data-testid="npc-no-wearables">
            No Wearable is made on this base yet.
          </p>
        ) : (
          <>
            <p className="hint">Top of the stack first. Drag to reorder, or use the arrows.</p>
            <ul className="npc-wearables" data-testid="npc-wearables">
              {[...stack].reverse().map((one, index) => row(one.id, one.order, stack.length - 1 - index))}
              {unworn.map((one) => row(one.id, one.order, null))}
            </ul>
          </>
        )}
        <h2>Colours</h2>
        {parts.length === 0 && (
          <p className="hint" data-testid="npc-no-parts">
            No Part has named choices in the ramp table.
          </p>
        )}
        {parts.map((part) => (
          <div className="npc-part" key={part.name} data-testid={`npc-part-${part.name}`} {...mark("part", part.name)}>
            <strong>{part.name}</strong>
            <div className="npc-swatches">
              <button
                className="npc-swatch npc-none"
                data-testid={`swatch-${part.name}-none`}
                aria-pressed={!colours[part.name]}
                disabled={disabled}
                onClick={() => pick(part.name, null)}
              >
                none
              </button>
              {Object.entries(part.choices).map(([choice, rgb]) => (
                <button
                  key={choice}
                  className="npc-swatch"
                  data-testid={`swatch-${part.name}-${choice}`}
                  aria-pressed={colours[part.name] === choice}
                  title={choice}
                  disabled={disabled}
                  onClick={() => pick(part.name, choice)}
                >
                  <span className="npc-ramp">
                    {rgb.map((colour, index) => (
                      <span key={index} style={{ background: `rgb(${colour[0]}, ${colour[1]}, ${colour[2]})` }} />
                    ))}
                  </span>
                  {choice}
                </button>
              ))}
            </div>
          </div>
        ))}
        {problems.length > 0 && (
          <p className="hint" data-testid="npc-problems">
            {problems.length} finding{problems.length === 1 ? "" : "s"} below; each jumps to the Wearable or Part it names.
          </p>
        )}
      </div>
    </div>
  );
}

// A crowd is only the IDs `npc.<prefix>_NN`; nothing is stored. The strip is `cast-sheet --match`; "re-roll" is `new --reroll`.
export function crowdsOf(status: StatusData | null): { prefix: string; ids: string[] }[] {
  const found = new Map<string, string[]>();
  for (const asset of status?.assets ?? []) {
    if (asset.kind !== NPC_KIND) continue;
    const match = /^npc\.(.+)_(\d+)$/.exec(asset.asset);
    if (match) found.set(match[1], [...(found.get(match[1]) ?? []), asset.asset]);
  }
  return [...found].map(([prefix, ids]) => ({ prefix, ids: ids.sort() }));
}

function CrowdStrip(props: {
  prefix: string;
  ids: string[];
  refreshes: number;
  imageVersion: number;
  disabled: boolean;
  onOpen: (asset: string, stage: string) => void;
  onReroll: (asset: string) => Promise<Envelope<unknown> | null>;
}) {
  const { prefix, ids } = props;
  const [sheet, setSheet] = useState<PreviewData | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const [said, setSaid] = useState<Record<string, string>>({});
  // The strip is drawn (a `cast-sheet` call) only while the crowd is in view (ticket 0374).
  const section = useRef<HTMLDivElement>(null);
  const inView = useInView(section);
  useEffect(() => {
    if (!inView) return;
    let live = true;
    void call<PreviewData>("cast-sheet", { match: `npc.${prefix}_*`, scale: 2, directions: "s" })
      .then((answer) => {
        if (!live) return;
        setSheet(answer.data);
        setNote(answer.data ? null : (answer.findings.at(-1)?.message ?? "No strip."));
        setVersion((count) => count + 1);
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [prefix, ids.join(","), props.refreshes, props.imageVersion, inView]);
  const reroll = async (id: string) => {
    const result = await props.onReroll(id);
    const unsatisfied = result?.findings.find((finding) => finding.code === "new.crowd_unsatisfied");
    setSaid((now) => ({ ...now, [id]: unsatisfied ? unsatisfied.message : "" }));
  };
  return (
    <div className="npc-crowd" data-testid={`crowd-${prefix}`} ref={section}>
      <h3>
        npc.{prefix}_* <span className="hint">{ids.length} NPC{ids.length === 1 ? "" : "s"}</span>
      </h3>
      {sheet ? (
        <img
          className="npc-strip"
          data-testid={`crowd-strip-${prefix}`}
          src={`${fileUrl(sheet.path)}&r=${version}`}
          width={sheet.width}
          height={sheet.height}
          loading="lazy"
          alt={`The NPCs npc.${prefix}_*, side by side`}
        />
      ) : (
        <p className="hint">{note ?? "Drawing the strip…"}</p>
      )}
      <ul className="npc-crowd-list">
        {ids.map((id) => (
          <li key={id} data-testid={`crowd-npc-${id}`}>
            <button className="link" onClick={() => props.onOpen(id, NPC_STAGE)}>
              {id}
            </button>{" "}
            <button data-testid={`reroll-${id}`} disabled={props.disabled} onClick={() => void reroll(id)}>
              re-roll
            </button>
            {said[id] && (
              <span className="hint" data-testid={`reroll-note-${id}`}>
                {" "}
                {said[id]}
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function NpcCrowds(props: {
  status: StatusData | null;
  refreshes: number;
  imageVersion: number;
  disabled: boolean;
  onOpen: (asset: string, stage: string) => void;
  onReroll: (asset: string) => Promise<Envelope<unknown> | null>;
}) {
  const crowds = crowdsOf(props.status);
  if (crowds.length === 0) return null;
  return (
    <section className="npc-crowds" data-testid="crowds">
      <h2>Crowds</h2>
      {crowds.map((crowd) => (
        <CrowdStrip key={crowd.prefix} {...crowd} refreshes={props.refreshes} imageVersion={props.imageVersion} disabled={props.disabled} onOpen={props.onOpen} onReroll={props.onReroll} />
      ))}
    </section>
  );
}
