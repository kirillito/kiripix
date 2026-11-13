// The room's hand-written screens (spec §11): place, with its Marker form, and reach, with the walk test.

import { useEffect, useRef, useState, type RefObject } from "react";
import { call, fileUrl, type Finding, type ShowData, type SortPosition, type StageDetail, type StatusData } from "./api";
import { ambiguousCells, isDrawnFromTwoPoints, MarkerTool, type Marker } from "./markerTool";
import type { CanvasPixel, PixelCanvas } from "./pixelCanvas";
import { LayerHighlight, layerFiles, loadImage } from "./sortView";
import { loadMask, WalkTest, type SortedLayers } from "./walkTest";

const TYPES = ["spawn", "exit", "interactable", "light", "emitter", "ysort", "area"] as const;
const LABELS: Record<string, string> = {
  spawn: "Spawns",
  exit: "Exits",
  interactable: "Interactables",
  light: "Lights",
  emitter: "Emitters",
  ysort: "Y-sort lines",
  area: "Areas",
};

export const PLACE_DECISION = "marker";
export const ABOVE_DECISION = "above";
export const REACH_STAGE = "reach";
const PLACE_STAGE = "place";

interface Fields {
  target_room: string;
  target_exit: string;
  colour: string;
  radius: number;
  energy: number;
  name: string;
  cell: string; // px, blank for none
  walkable: boolean;
}

const DEFAULTS: Fields = {
  target_room: "",
  target_exit: "",
  colour: "#ffffff",
  radius: 32,
  energy: 1,
  name: "emitter",
  cell: "",
  walkable: false,
};

function cellSize(text: string): number | null {
  const cell = Number(text);
  return text.trim() !== "" && Number.isInteger(cell) && cell > 0 ? cell : null;
}

function sortText(entry: SortPosition | undefined): string {
  if (!entry) return "no y-sort line yet";
  if (entry.above) return "always above the Body";
  if (entry.y === null) return "no y-sort line yet";
  return `sorts at y ${entry.y}`;
}

function markersOf(detail: StageDetail | undefined): Marker[] {
  return (detail?.markers ?? []) as Marker[];
}

function freeId(type: string, markers: Marker[]): string {
  for (let number = 1; ; number++) {
    const id = `${type}.${number}`;
    if (!markers.some((marker) => marker.id === id)) return id;
  }
}

function ownFields(type: string, fields: Fields, layer: string): Record<string, unknown> {
  if (type === "ysort") return { layer };
  if (type === "exit") return { target_room: fields.target_room, target_exit: fields.target_exit };
  if (type === "light") return { colour: fields.colour, radius: fields.radius, energy: fields.energy };
  if (type === "emitter") return { name: fields.name };
  if (type === "area") {
    const cell = cellSize(fields.cell);
    return { ...(cell ? { cell } : {}), walkable: fields.walkable };
  }
  return {};
}

export function PlacePanel(props: {
  canvas: RefObject<PixelCanvas | null>;
  show: ShowData;
  detail: StageDetail;
  status: StatusData | null;
  imageVersion: number;
  focusLayer: { layer: string; count: number } | null;
  findings: Finding[];
  decide: (marker: Record<string, unknown>) => void;
  decideAbove: (layer: string, above: boolean) => void;
  disabled: boolean;
}) {
  const { canvas, show, detail, status, imageVersion, focusLayer, findings, decide, decideAbove, disabled } = props;
  const markers = markersOf(detail);
  const [type, setType] = useState<string>(TYPES[0]);
  const [typedId, setTypedId] = useState<string | null>(null);
  const [fields, setFields] = useState(DEFAULTS);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = markers.find((marker) => marker.id === selectedId) ?? null;
  const [exits, setExits] = useState<string[]>([]);
  const id = typedId ?? freeId(type, markers);
  const files = layerFiles(show);
  const layerIds = [...files.keys()];
  const [chosenLayer, setChosenLayer] = useState<string | null>(null);
  const layer = chosenLayer !== null && files.has(chosenLayer) ? chosenLayer : (layerIds[0] ?? "");
  const sorts = detail.sort ?? [];

  const form = useRef({ type, id, fields, layer, decide, disabled, markers });
  form.current = { type, id, fields, layer, decide, disabled, markers };
  const tool = useRef<MarkerTool | null>(null);
  const highlight = useRef(new LayerHighlight());

  function choose(marker: Marker) {
    setSelectedId(marker.id);
    setType(marker.type);
    setTypedId(marker.id);
    setFields((before) => ({
      ...before,
      ...(marker as unknown as Partial<Fields>),
      cell: typeof marker.cell === "number" ? String(marker.cell) : "",
      walkable: marker.walkable === true,
    }));
    if (typeof marker.layer === "string") setChosenLayer(marker.layer);
  }

  // A `layer.no_ysort` finding jumps here: the Layer is chosen, and shown while its line is drawn.
  const jumpedLayer = focusLayer?.layer;
  const jumpCount = focusLayer?.count;
  useEffect(() => {
    if (jumpedLayer) {
      setChosenLayer(jumpedLayer);
      setType("ysort");
      setTypedId(null);
      setSelectedId(null);
    }
  }, [jumpedLayer, jumpCount]);

  useEffect(() => {
    const placing = new MarkerTool({
      place(start: CanvasPixel, end: CanvasPixel) {
        const { type: chosen, id: name, fields: own, layer: sorted, decide: record } = form.current;
        const line = isDrawnFromTwoPoints(chosen);
        if (chosen === "area") {
          // A bare click draws nothing, unless a cell makes it one cell.
          const cell = cellSize(own.cell);
          if (!cell && start.x === end.x && start.y === end.y) return;
          record({
            id: name,
            type: chosen,
            x: Math.min(start.x, end.x),
            y: Math.min(start.y, end.y),
            x2: Math.max(start.x, end.x),
            y2: Math.max(start.y, end.y),
            ...ownFields(chosen, own, sorted),
          });
          setTypedId(null);
          setSelectedId(null);
          return;
        }
        if ((line && start.x === end.x && start.y === end.y)) return;
        if (chosen === "ysort" && !sorted) return; // a line sorts a Layer, and the room has none yet
        record({
          id: name,
          type: chosen,
          x: start.x,
          y: start.y,
          ...(line ? { x2: end.x, y2: end.y } : {}),
          ...ownFields(chosen, own, sorted),
        });
        setTypedId(null);
        setSelectedId(null);
      },
      move(marker: Marker) {
        form.current.decide(marker); // queued behind a Run, never dropped (ticket 0083)
      },
      select: choose,
    });
    tool.current = placing;
    canvas.current?.setTools([highlight.current, placing]);
    return () => canvas.current?.setTools([]);
  }, [canvas]);

  // The Layer shown while its line is drawn: its own pixels, as the Stage built them.
  const shownFile = type === "ysort" ? (files.get(layer) ?? null) : null;
  useEffect(() => {
    let current = true;
    if (!shownFile) {
      highlight.current.show(null, null);
      canvas.current?.redraw();
      return;
    }
    loadImage(fileUrl(shownFile, imageVersion))
      .then((image) => {
        if (!current) return;
        highlight.current.show(layer, image);
        canvas.current?.redraw();
      })
      .catch(() => undefined); // Rebuilt while it was read; the next refresh reads it again.
    return () => {
      current = false;
    };
  }, [canvas, shownFile, layer, imageVersion]);

  // Every refresh brings a new `detail`, so a drag that was refused goes back to where the Marker is.
  const drawnCell = type === "area" ? cellSize(fields.cell) : null;
  const ambiguous = findings.flatMap((finding) => ambiguousCells(finding) ?? []);
  const ambiguousKey = JSON.stringify(ambiguous);
  useEffect(() => {
    tool.current?.setMarkers(markersOf(detail));
    tool.current?.setSelected(selectedId);
    tool.current?.setDrawing(type, drawnCell);
    tool.current?.setAmbiguous(JSON.parse(ambiguousKey) as typeof ambiguous);
    canvas.current?.redraw();
  }, [canvas, detail, selectedId, type, drawnCell, ambiguousKey]);

  // The letter A picks the area tool (spec §11: letters switch tools).
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      if (target && (target.isContentEditable || ["INPUT", "SELECT", "TEXTAREA"].includes(target.tagName))) return;
      if (event.key.toLowerCase() !== "a" || event.ctrlKey || event.metaKey || event.altKey) return;
      setType("area");
      setTypedId(null);
      setSelectedId(null);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const targetRoom = fields.target_room;
  useEffect(() => {
    let current = true;
    if (!targetRoom) {
      setExits([]);
      return;
    }
    call<ShowData>("show", { asset: targetRoom })
      .then((result) => {
        const stage = result.data?.stages.find((entry) => entry.stage === PLACE_STAGE);
        const found = markersOf(stage).filter((marker) => marker.type === "exit");
        if (current) setExits(found.map((marker) => marker.id));
      })
      .catch(() => {
        if (current) setExits([]); // The room can still be named; its Exit is typed in.
      });
    return () => {
      current = false;
    };
  }, [targetRoom]);

  const rooms = (status?.assets ?? []).filter((asset) => asset.kind === "room").map((asset) => asset.asset);
  const update = (change: Partial<Fields>) => setFields((before) => ({ ...before, ...change }));

  return (
    <fieldset disabled={disabled} className="marker-form">
      <h2>Marker</h2>
      <div className="param">
        <label htmlFor="marker-type">Type</label>
        <select
          id="marker-type"
          data-testid="marker-type"
          value={type}
          onChange={(event) => {
            setType(event.target.value);
            setTypedId(null);
            setSelectedId(null);
          }}
        >
          {TYPES.map((name) => (
            <option key={name}>{name}</option>
          ))}
        </select>
      </div>
      <div className="param">
        <label htmlFor="marker-id">ID</label>
        <input
          id="marker-id"
          data-testid="marker-id"
          value={id}
          onChange={(event) => setTypedId(event.target.value)}
        />
      </div>
      {type === "ysort" &&
        (layerIds.length === 0 ? (
          <p className="hint" data-testid="no-layers">
            The room has no Layer yet to sort: lift one on the layers screen.
          </p>
        ) : (
          <div className="param">
            <label htmlFor="marker-layer">Layer</label>
            <select
              id="marker-layer"
              data-testid="marker-layer"
              value={layer}
              onChange={(event) => setChosenLayer(event.target.value)}
            >
              {layerIds.map((name) => (
                <option key={name}>{name}</option>
              ))}
            </select>
          </div>
        ))}
      {type === "exit" && (
        <>
          <div className="param">
            <label htmlFor="marker-target-room">Target room</label>
            <select
              id="marker-target-room"
              data-testid="marker-target-room"
              value={fields.target_room}
              onChange={(event) => update({ target_room: event.target.value })}
            >
              <option value="">Choose a room</option>
              {rooms.map((room) => (
                <option key={room}>{room}</option>
              ))}
            </select>
          </div>
          <div className="param">
            <label htmlFor="marker-target-exit">Target Exit</label>
            <input
              id="marker-target-exit"
              data-testid="marker-target-exit"
              list="marker-exits"
              value={fields.target_exit}
              onChange={(event) => update({ target_exit: event.target.value })}
            />
            <datalist id="marker-exits">
              {exits.map((exit) => (
                <option key={exit} value={exit} />
              ))}
            </datalist>
          </div>
        </>
      )}
      {type === "light" && (
        <>
          <div className="param">
            <label htmlFor="marker-colour">Colour</label>
            <input
              id="marker-colour"
              data-testid="marker-colour"
              type="color"
              value={fields.colour}
              onChange={(event) => update({ colour: event.target.value })}
            />
          </div>
          <div className="param">
            <label htmlFor="marker-radius">Radius</label>
            <input
              id="marker-radius"
              data-testid="marker-radius"
              type="number"
              min={1}
              value={fields.radius}
              onChange={(event) => update({ radius: Number(event.target.value) })}
            />
          </div>
          <div className="param">
            <label htmlFor="marker-energy">Energy</label>
            <input
              id="marker-energy"
              data-testid="marker-energy"
              type="number"
              min={0}
              step="any"
              value={fields.energy}
              onChange={(event) => update({ energy: Number(event.target.value) })}
            />
          </div>
        </>
      )}
      {type === "emitter" && (
        <div className="param">
          <label htmlFor="marker-name">Name</label>
          <input
            id="marker-name"
            data-testid="marker-name"
            value={fields.name}
            onChange={(event) => update({ name: event.target.value })}
          />
        </div>
      )}
      {type === "area" && (
        <>
          <div className="param">
            <label htmlFor="marker-cell">Cell (px)</label>
            <input
              id="marker-cell"
              data-testid="marker-cell"
              type="number"
              min={1}
              placeholder="none"
              value={fields.cell}
              onChange={(event) => update({ cell: event.target.value })}
            />
          </div>
          <label className="toggle">
            <input
              type="checkbox"
              data-testid="marker-walkable"
              checked={fields.walkable}
              onChange={(event) => update({ walkable: event.target.checked })}
            />
            walkable (the area is for standing in)
          </label>
        </>
      )}
      <p className="hint">
        {isDrawnFromTwoPoints(type) ? "Drag on the canvas to draw it." : "Click the canvas to place it."} Drag a Marker to
        move it.
      </p>
      {selected && (
        <button
          data-testid="marker-save"
          onClick={() => {
            const { x, y, x2, y2 } = selected;
            decide({
              id: selected.id,
              type: selected.type,
              x,
              y,
              ...(x2 !== undefined ? { x2, y2 } : {}),
              ...ownFields(selected.type, fields, String(selected.layer ?? layer)),
            });
          }}
        >
          Save {selected.id}
        </button>
      )}
      {TYPES.filter((name) => markers.some((marker) => marker.type === name)).map((name) => (
        <section key={name} data-testid={`markers-${name}`}>
          <h2>{LABELS[name]}</h2>
          {markers
            .filter((marker) => marker.type === name)
            .map((marker) => (
              <button
                key={marker.id}
                className="link marker-row"
                data-testid={`marker-${marker.id}`}
                onClick={() => choose(marker)}
              >
                {marker.id} ({marker.x}, {marker.y}
                {marker.x2 !== undefined && marker.type === "area" ? ` to ${marker.x2}, ${marker.y2}` : ""}){typeof marker.layer === "string" ? ` for ${marker.layer}` : ""}
  </button>
            ))}
        </section>
      ))}
      {layerIds.length > 0 && (
        <section data-testid="sort-layers">
          <h2>Layers</h2>
          <ul className="layer-list">
            {layerIds.map((name) => {
              const entry = sorts.find((one) => one.layer === name);
              return (
                <li key={name}>
                  <button
                    data-testid={`sort-layer-${name}`}
                    aria-pressed={layer === name}
                    onClick={() => {
                      setChosenLayer(name);
                      setType("ysort");
                      setTypedId(null);
                      setSelectedId(null);
                    }}
                  >
                    {name}
                  </button>
                  <label className="toggle">
                    <input
                      type="checkbox"
                      data-testid={`above-${name}`}
                      checked={entry?.above ?? false}
                      onChange={(event) => decideAbove(name, event.target.checked)}
                    />
                    always above
                  </label>
                  <span className="hint" data-testid={`sort-${name}`}>
                    {sortText(entry)}
                  </span>
                </li>
              );
            })}
          </ul>
        </section>
      )}
    </fieldset>
  );
}

interface ReachReport {
  markers: { id: string; reached: boolean }[];
}

export function ReachPanel(props: {
  canvas: RefObject<PixelCanvas | null>;
  show: ShowData;
  detail: StageDetail;
  imageVersion: number;
  onWalking: (walking: boolean) => void;
}) {
  const { canvas, show, detail, imageVersion, onWalking } = props;
  const [unreachable, setUnreachable] = useState<string[]>([]);
  const [walking, setWalking] = useState(false);
  const place = show.stages.find((entry) => entry.stage === PLACE_STAGE);
  const markers = markersOf(place);
  const shown = JSON.stringify(markers);
  const report = detail.outputs.find((path) => path.endsWith("/report.json"));
  const walkable = place?.outputs.find((path) => path.endsWith("/walkable.png"));
  const clear = place?.outputs.find((path) => path.endsWith("/clear.png"));
  const tool = useRef(new MarkerTool(null));
  const sorted = useRef<SortedLayers>({ layers: [] });

  // The Layers the walk test draws over the Body, and where each sorts: `place`'s `sort`, and the Layers' own files.
  const files = layerFiles(show);
  // A string, so the effect below reloads the images only when a sort position or a file changes, not on every new `show`.
  const sortKey = JSON.stringify([place?.sort ?? [], [...files]]);
  useEffect(() => {
    let current = true;
    const [positions, found] = JSON.parse(sortKey) as [SortPosition[], [string, string][]];
    const paths = new Map(found);
    void Promise.all(
      positions
        .filter((entry) => paths.has(entry.layer) && (entry.above || entry.y !== null))
        .map(async (entry) => ({
          id: entry.layer,
          image: await loadImage(fileUrl(paths.get(entry.layer)!, imageVersion)),
          above: entry.above,
          y: entry.y,
        })),
    )
      .then((layers) => {
        if (!current) return;
        sorted.current.layers = layers;
        canvas.current?.redraw();
      })
      .catch(() => undefined); // Rebuilt while it was read; the next refresh reads it again.
    return () => {
      current = false;
    };
  }, [canvas, sortKey, imageVersion]);

  useEffect(() => {
    let current = true;
    if (!report) {
      setUnreachable([]);
      return;
    }
    fetch(fileUrl(report, imageVersion))
      .then((response) => response.json() as Promise<ReachReport>)
      .then((read) => {
        if (current) setUnreachable(read.markers.filter((marker) => !marker.reached).map((marker) => marker.id));
      })
      .catch(() => {
        if (current) setUnreachable([]); // Rebuilt while it was read; the next refresh reads it again.
      });
    return () => {
      current = false;
    };
  }, [report, imageVersion]);

  useEffect(() => {
    tool.current.setMarkers(JSON.parse(shown) as Marker[]);
    tool.current.setUnreachable(unreachable);
    canvas.current?.redraw();
  }, [canvas, shown, unreachable]);

  const first = JSON.stringify(markers.find((marker) => marker.type === "spawn") ?? markers.find((marker) => marker.type === "exit") ?? null);
  const [bodyWidth, bodyHeight] = show.body.size;
  const dash = show.body.dash;
  // One walk test for as long as the Body walks from the same start: a rebuild only swaps its Masks, so the Body keeps
  // its place and no arrow pressed during the reload is lost.
  const walk = useRef<{ from: string; test: WalkTest } | null>(null);
  const stopWalking = (): void => {
    walk.current?.test.destroy();
    walk.current = null;
    canvas.current?.setTools([tool.current]);
    if (canvas.current) delete canvas.current.element.dataset.body;
  };
  useEffect(() => {
    if (!walking) {
      stopWalking();
      return;
    }
    if (!walkable || !clear) return; // a Mask still loading keeps the Body where it is
    let current = true;
    const start = JSON.parse(first) as Marker | null;
    const from = JSON.stringify([first, bodyWidth, bodyHeight, dash]);
    void Promise.all([loadMask(fileUrl(walkable, imageVersion)), loadMask(fileUrl(clear, imageVersion))]).then(
      ([ground, open]) => {
        if (!current) return;
        const x = start?.x ?? Math.floor(ground.width / 2);
        const y = start?.y ?? Math.floor(ground.height / 2);
        if (walk.current?.from === from) {
          walk.current.test.setMasks(ground, open, x, y);
          return;
        }
        stopWalking();
        const body = { size: [bodyWidth, bodyHeight] as [number, number], dash };
        const test = new WalkTest(ground, open, body, x, y, () => canvas.current?.redraw(), sorted.current);
        walk.current = { from, test };
        canvas.current?.setTools([tool.current, test]);
      },
    );
    return () => {
      current = false;
    };
  }, [canvas, walking, walkable, clear, imageVersion, first, bodyWidth, bodyHeight, dash]);

  useEffect(() => () => stopWalking(), []);
  useEffect(() => () => canvas.current?.setTools([]), [canvas]);

  return (
    <div className="walk">
      <h2>Walk test</h2>
      {walkable && clear ? (
        <>
          <button
            data-testid="walk-toggle"
            aria-pressed={walking}
            onClick={() => {
              setWalking(!walking);
              onWalking(!walking);
            }}
          >
            {walking ? "Stop walking" : "Walk the Body"}
          </button>
          <p className="hint">
            The arrow keys walk the {bodyWidth} x {bodyHeight} Body.
            {dash > 0 && ` Shift and an arrow dashes over a pit of up to ${dash} px.`}
          </p>
        </>
      ) : (
        <p className="hint">Build place first: the Body walks on what it derives.</p>
      )}
      {unreachable.length > 0 && (
        <p className="reason" data-testid="unreachable">
          Unreachable: {unreachable.join(", ")}
        </p>
      )}
    </div>
  );
}
