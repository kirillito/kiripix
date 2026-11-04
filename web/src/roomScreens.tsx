// The room's hand-written screens (spec §11): place, with its Marker form, and reach, with the walk test.

import { useEffect, useRef, useState, type RefObject } from "react";
import { call, fileUrl, type ShowData, type StageDetail, type StatusData } from "./api";
import { isDrawnFromTwoPoints, MarkerTool, type Marker } from "./markerTool";
import type { CanvasPixel, PixelCanvas } from "./pixelCanvas";
import { loadMask, WalkTest } from "./walkTest";

const TYPES = ["spawn", "exit", "interactable", "light", "emitter", "ysort"] as const;
const LABELS: Record<string, string> = {
  spawn: "Spawns",
  exit: "Exits",
  interactable: "Interactables",
  light: "Lights",
  emitter: "Emitters",
  ysort: "Y-sort lines",
};

export const PLACE_DECISION = "marker";
export const REACH_STAGE = "reach";
const PLACE_STAGE = "place";

interface Fields {
  target_room: string;
  target_exit: string;
  colour: string;
  radius: number;
  energy: number;
  name: string;
}

const DEFAULTS: Fields = { target_room: "", target_exit: "", colour: "#ffffff", radius: 32, energy: 1, name: "emitter" };

function markersOf(detail: StageDetail | undefined): Marker[] {
  return (detail?.markers ?? []) as Marker[];
}

function freeId(type: string, markers: Marker[]): string {
  for (let number = 1; ; number++) {
    const id = `${type}.${number}`;
    if (!markers.some((marker) => marker.id === id)) return id;
  }
}

function ownFields(type: string, fields: Fields): Record<string, unknown> {
  if (type === "exit") return { target_room: fields.target_room, target_exit: fields.target_exit };
  if (type === "light") return { colour: fields.colour, radius: fields.radius, energy: fields.energy };
  if (type === "emitter") return { name: fields.name };
  return {};
}

export function PlacePanel(props: {
  canvas: RefObject<PixelCanvas | null>;
  detail: StageDetail;
  status: StatusData | null;
  decide: (marker: Record<string, unknown>) => void;
  disabled: boolean;
}) {
  const { canvas, detail, status, decide, disabled } = props;
  const markers = markersOf(detail);
  const [type, setType] = useState<string>(TYPES[0]);
  const [typedId, setTypedId] = useState<string | null>(null);
  const [fields, setFields] = useState(DEFAULTS);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = markers.find((marker) => marker.id === selectedId) ?? null;
  const [exits, setExits] = useState<string[]>([]);
  const id = typedId ?? freeId(type, markers);

  const form = useRef({ type, id, fields, decide, disabled, markers });
  form.current = { type, id, fields, decide, disabled, markers };
  const tool = useRef<MarkerTool | null>(null);

  function choose(marker: Marker) {
    setSelectedId(marker.id);
    setType(marker.type);
    setTypedId(marker.id);
    setFields((before) => ({ ...before, ...(marker as unknown as Partial<Fields>) }));
  }

  useEffect(() => {
    const placing = new MarkerTool({
      place(start: CanvasPixel, end: CanvasPixel) {
        const { type: chosen, id: name, fields: own, decide: record, disabled: off } = form.current;
        const line = isDrawnFromTwoPoints(chosen);
        if (off || (line && start.x === end.x && start.y === end.y)) return;
        record({
          id: name,
          type: chosen,
          x: start.x,
          y: start.y,
          ...(line ? { x2: end.x, y2: end.y } : {}),
          ...ownFields(chosen, own),
        });
        setTypedId(null);
        setSelectedId(null);
      },
      move(marker: Marker) {
        if (form.current.disabled) tool.current?.setMarkers(form.current.markers);
        else form.current.decide(marker);
      },
      select: choose,
    });
    tool.current = placing;
    canvas.current?.setTools([placing]);
    return () => canvas.current?.setTools([]);
  }, [canvas]);

  // Every refresh brings a new `detail`, so a drag that was refused goes back to where the Marker is.
  useEffect(() => {
    tool.current?.setMarkers(markersOf(detail));
    tool.current?.setSelected(selectedId);
    canvas.current?.redraw();
  }, [canvas, detail, selectedId]);

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
              ...ownFields(selected.type, fields),
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
                {marker.id} ({marker.x}, {marker.y})
              </button>
            ))}
        </section>
      ))}
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
  useEffect(() => {
    if (!walking || !walkable || !clear) {
      canvas.current?.setTools([tool.current]);
      return;
    }
    let walk: WalkTest | null = null;
    let current = true;
    const start = JSON.parse(first) as Marker | null;
    void Promise.all([loadMask(fileUrl(walkable, imageVersion)), loadMask(fileUrl(clear, imageVersion))]).then(
      ([ground, open]) => {
        if (!current) return;
        const x = start?.x ?? Math.floor(ground.width / 2);
        const y = start?.y ?? Math.floor(ground.height / 2);
        const body = { size: [bodyWidth, bodyHeight] as [number, number], dash };
        walk = new WalkTest(ground, open, body, x, y, () => canvas.current?.redraw());
        canvas.current?.setTools([tool.current, walk]);
      },
    );
    return () => {
      current = false;
      walk?.destroy();
      canvas.current?.setTools([tool.current]);
      if (canvas.current) delete canvas.current.element.dataset.body;
    };
  }, [canvas, walking, walkable, clear, imageVersion, first, bodyWidth, bodyHeight, dash]);

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
