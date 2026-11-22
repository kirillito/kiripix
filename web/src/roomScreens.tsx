// The room's hand-written screens (spec §11): place, with its Marker form, and reach, with the walk test.

import { useEffect, useRef, useState, type RefObject } from "react";
import { call, fileUrl, projectPalette, type Finding, type ShowData, type SortPosition, type StageDetail, type StatusData } from "./api";
import {
  ambiguousCells,
  arrowLength,
  coloursOf,
  directionOf,
  isDrawnFromTwoPoints,
  isLink,
  MarkerTool,
  shapeOf,
  type EmitterGesture,
  type EmitterMode,
  type Link,
  type Marker,
} from "./markerTool";
import type { CanvasPixel, PixelCanvas } from "./pixelCanvas";
import { ReachOverlay, type IslandBox } from "./reachOverlay";
import { LayerHighlight, layerFiles, loadImage } from "./sortView";
import { CROSS_KEY, LINK_REACH, loadMask, WalkTest, type Crossing, type Crossings, type SortedLayers } from "./walkTest";

const TYPES = ["spawn", "exit", "interactable", "light", "emitter", "ysort", "area", "link"] as const;
const LABELS: Record<string, string> = {
  spawn: "Spawns",
  exit: "Exits",
  interactable: "Interactables",
  light: "Lights",
  emitter: "Emitters",
  ysort: "Y-sort lines",
  area: "Areas",
  link: "Links",
};

export const PLACE_DECISION = "marker";
export const LINK_DECISION = "link";
export const ABOVE_DECISION = "above";
export const REACH_STAGE = "reach";
const PLACE_STAGE = "place";

interface Fields {
  target_room: string;
  target_exit: string;
  one_way: boolean;
  colour: string;
  radius: number;
  energy: number;
  name: string;
  cell: string; // px, blank for none
  walkable: boolean;
  kind: string; // a Link's kind, free text in snake_case
  two_way: boolean;
  look: string; // a light's, emitter's or interactable's Look ID, blank for none
}

// The Marker types the `marker` Decision lets carry a Look (`marker.look_type` refuses the others).
const LOOK_TYPES = ["light", "emitter", "interactable"];

const DEFAULTS: Fields = {
  target_room: "",
  target_exit: "",
  one_way: false,
  colour: "#ffffff",
  radius: 32,
  energy: 1,
  name: "emitter",
  cell: "",
  walkable: false,
  kind: "hop",
  two_way: true,
  look: "",
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

const MOST_COLOURS = 16; // an emitter's colours, as the Decision allows

// A Decision leaves out an emitter's unset fields; `show` writes them as null.
function forDecision(marker: Marker): Record<string, unknown> {
  const kept: Marker = { ...marker };
  if (kept.look === null) delete kept.look; // `show` writes a room Marker's Look as null
  if (marker.type !== "emitter") return kept;
  for (const key of ["shape", "direction", "colours"]) if (kept[key] === null) delete kept[key];
  return kept;
}

// A Link's Decision: its ends, kind and direction, as `show` gives them.
function linkDecision(link: Link, change: Partial<Link> = {}): Record<string, unknown> {
  const { id, from, to, kind, two_way } = { ...link, ...change };
  return { id, from, to, kind, two_way };
}

function ownFields(type: string, fields: Fields, layer: string): Record<string, unknown> {
  const own = typeFields(type, fields, layer);
  return LOOK_TYPES.includes(type) && fields.look ? { ...own, look: fields.look } : own;
}

function typeFields(type: string, fields: Fields, layer: string): Record<string, unknown> {
  if (type === "ysort") return { layer };
  if (type === "exit") return { target_room: fields.target_room, target_exit: fields.target_exit, ...(fields.one_way ? { one_way: true } : {}) };
  if (type === "light") return { colour: fields.colour, radius: fields.radius, energy: fields.energy };
  if (type === "emitter") return { name: fields.name };
  if (type === "area") {
    const cell = cellSize(fields.cell);
    return { ...(cell ? { cell } : {}), walkable: fields.walkable };
  }
  return {};
}

const EMITTER_KEYS: Record<string, EmitterMode> = { s: "shape", d: "direction", e: "eyedrop" };

export function PlacePanel(props: {
  canvas: RefObject<PixelCanvas | null>;
  show: ShowData;
  detail: StageDetail;
  status: StatusData | null;
  imageVersion: number;
  focusLayer: { layer: string; count: number } | null;
  findings: Finding[];
  decide: (marker: Record<string, unknown>) => void;
  decideLink: (link: Record<string, unknown>) => void;
  decideAbove: (layer: string, above: boolean) => void;
  disabled: boolean;
}) {
  const { canvas, show, detail, status, imageVersion, focusLayer, findings, decide, decideLink, decideAbove, disabled } = props;
  const markers = markersOf(detail);
  const [type, setType] = useState<string>(TYPES[0]);
  const [typedId, setTypedId] = useState<string | null>(null);
  const [fields, setFields] = useState(DEFAULTS);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  // The Look whose Markers are drawn with the room's own; a Marker in another Look is hidden (ADR 0013).
  const [viewLook, setViewLook] = useState("");
  const lookIds = (show.looks ?? []).map((entry) => entry.look);
  const shownMarkers = markers.filter((marker) => typeof marker.look !== "string" || marker.look === viewLook);
  const shownKey = JSON.stringify(shownMarkers);
  const selected = markers.find((marker) => marker.id === selectedId) ?? null;
  const [exits, setExits] = useState<string[]>([]);
  const id = typedId ?? freeId(type, markers);
  const files = layerFiles(show);
  const layerIds = [...files.keys()];
  const [chosenLayer, setChosenLayer] = useState<string | null>(null);
  const layer = chosenLayer !== null && files.has(chosenLayer) ? chosenLayer : (layerIds[0] ?? "");
  const sorts = detail.sort ?? [];

  const [mode, setMode] = useState<EmitterMode>("shape");
  const [drawingPolygon, setDrawingPolygon] = useState(false);
  const [palette, setPalette] = useState<string[]>([]);
  const [hint, setHint] = useState("");
  const sampler = useRef<ImageData | null>(null);
  const send = (marker: Marker) => decide(forDecision(marker));
  const emitter = selected?.type === "emitter" ? selected : null;
  const shapeKind = drawingPolygon ? "polygon" : (emitter ? shapeOf(emitter)?.type ?? "point" : "point");
  const chosenColours = emitter ? coloursOf(emitter) : [];

  // One click of the eyedropper adds the room pixel's colour, if it is a colour of the palette.
  function pickColour(pixel: CanvasPixel) {
    const image = sampler.current;
    if (!emitter || !image) return;
    const at = (pixel.y * image.width + pixel.x) * 4;
    const [red, green, blue, alpha] = image.data.slice(at, at + 4);
    const hex = "#" + [red, green, blue].map((value) => value.toString(16).padStart(2, "0")).join("").toUpperCase();
    if (alpha === 0) setHint("That pixel is transparent; it has no colour to add.");
    else if (!palette.includes(hex)) setHint(`${hex} is not on the Project palette, so an emitter can't use it.`);
    else addColour(hex);
  }

  function addColour(hex: string) {
    if (!emitter) return;
    if (chosenColours.includes(hex)) setHint(`${hex} is already in the list.`);
    else if (chosenColours.length >= MOST_COLOURS) setHint(`An emitter has at most ${MOST_COLOURS} colours.`);
    else {
      setHint("");
      setColours([...chosenColours, hex]);
    }
  }

  function setColours(list: string[]) {
    if (emitter) send({ ...emitter, colours: list.length > 0 ? list : null });
  }

  function reorder(index: number, by: number) {
    const list = [...chosenColours];
    const [moved] = list.splice(index, 1);
    list.splice(index + by, 0, moved);
    setColours(list);
  }

  function chooseShape(kind: string) {
    if (!emitter) return;
    const room = sampler.current ?? { width: 48, height: 32 };
    if (kind === "polygon") {
      setDrawingPolygon(true);
      setMode("shape");
      return;
    }
    setDrawingPolygon(false);
    const reaching = (value: number, limit: number) => Math.min(value + 8, limit - 1);
    const shape =
      kind === "point"
        ? { type: "point" }
        : { type: kind, x2: reaching(emitter.x, room.width), y2: kind === "box" ? reaching(emitter.y, room.height) : emitter.y };
    send({ ...emitter, shape });
  }

  const form = useRef({ type, id, fields, layer, decide: send, decideLink, disabled, markers, selectedId, pickColour, drawingPolygon, mode });
  form.current = { type, id, fields, layer, decide: send, decideLink, disabled, markers, selectedId, pickColour, drawingPolygon, mode };
  const tool = useRef<MarkerTool | null>(null);
  const highlight = useRef(new LayerHighlight());

  function choose(marker: Marker) {
    setSelectedId(marker.id);
    setType(marker.type);
    setTypedId(marker.id);
    setDrawingPolygon(false);
    setHint("");
    setFields((before) => ({
      ...before,
      ...(isLink(marker) ? { kind: marker.kind, two_way: marker.two_way } : (marker as unknown as Partial<Fields>)),
      cell: typeof marker.cell === "number" ? String(marker.cell) : "",
      walkable: marker.walkable === true,
      look: typeof marker.look === "string" ? marker.look : "",
    }));
    if (typeof marker.look === "string") setViewLook(marker.look);
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
        setSelectedId(chosen === "emitter" ? name : null); // a new emitter stays selected, ready for its shape
      },
      move(marker: Marker) {
        form.current.decide(marker); // queued behind a Run, never dropped (ticket 0083)
      },
      placeLink(from: CanvasPixel, to: CanvasPixel) {
        const { id: name, fields: own, decideLink: record } = form.current;
        record({ id: name, from: [from.x, from.y], to: [to.x, to.y], kind: own.kind, two_way: own.two_way });
        setTypedId(null);
        setSelectedId(null);
      },
      moveLink(link: Link) {
        form.current.decideLink(linkDecision(link));
      },
      selectLink(link: Link) {
        choose(link as unknown as Marker);
      },
      select: choose,
      emitter(gesture: EmitterGesture) {
        const { markers: all, selectedId: current, decide: record, pickColour: pick } = form.current;
        const target = all.find((marker) => marker.id === current && marker.type === "emitter");
        if (!target) return;
        if (gesture.kind === "pick") pick(gesture.pixel);
        else if (gesture.kind === "box") {
          const [a, b] = [gesture.start, gesture.end];
          record({ ...target, x: Math.min(a.x, b.x), y: Math.min(a.y, b.y), shape: { type: "box", x2: Math.max(a.x, b.x), y2: Math.max(a.y, b.y) } });
        } else if (gesture.kind === "line") {
          record({ ...target, x: gesture.start.x, y: gesture.start.y, shape: { type: "line", x2: gesture.end.x, y2: gesture.end.y } });
        } else if (gesture.kind === "polygon") {
          record({ ...target, shape: { type: "polygon", points: gesture.points } });
          setDrawingPolygon(false);
        } else if (gesture.end.x !== target.x || gesture.end.y !== target.y) {
          record({ ...target, direction: { x: gesture.end.x, y: gesture.end.y } });
        }
      },
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
  const linkProblemKey = JSON.stringify(
    findings
      .filter((finding) => finding.code.startsWith("link.") && finding.position?.x != null && finding.position.y != null)
      .map((finding) => ({ x: finding.position!.x, y: finding.position!.y })),
  );
  useEffect(() => {
    tool.current?.setMarkers(JSON.parse(shownKey) as Marker[]);
    tool.current?.setLinking(type === "link");
    tool.current?.setLinkProblems(JSON.parse(linkProblemKey) as CanvasPixel[]);
    tool.current?.setSelected(selectedId);
    tool.current?.setDrawing(type, drawnCell);
    tool.current?.setEmitter(mode, shapeKind, drawingPolygon);
    tool.current?.setAmbiguous(JSON.parse(ambiguousKey) as typeof ambiguous);
    canvas.current?.redraw();
  }, [canvas, detail, shownKey, selectedId, type, drawnCell, ambiguousKey, linkProblemKey, mode, shapeKind, drawingPolygon]);

  // The room's pixels for the eyedropper, and the Project palette for the swatches: only an emitter needs either.
  const placeImage = detail.image ?? detail.input_image;
  const emitting = type === "emitter";
  useEffect(() => {
    if (!emitting) return;
    let current = true;
    if (placeImage) {
      loadImage(fileUrl(placeImage, imageVersion))
        .then((image) => {
          const scratch = document.createElement("canvas");
          scratch.width = image.naturalWidth;
          scratch.height = image.naturalHeight;
          const context = scratch.getContext("2d", { willReadFrequently: true })!;
          context.drawImage(image, 0, 0);
          if (current) sampler.current = context.getImageData(0, 0, scratch.width, scratch.height);
        })
        .catch(() => undefined);
    }
    projectPalette()
      .then((colours) => current && setPalette(colours.map((colour) => colour.toUpperCase())))
      .catch(() => undefined);
    return () => {
      current = false;
    };
  }, [emitting, placeImage, imageVersion]);

  // The letter A picks the area tool (spec §11: letters switch tools). With an emitter selected, S, D and E pick its shape,
  // direction and eyedropper; Enter closes a polygon and Escape drops it.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      if (target && (target.isContentEditable || ["INPUT", "SELECT", "TEXTAREA"].includes(target.tagName))) return;
      if (event.ctrlKey || event.metaKey || event.altKey) return;
      const { markers: all, selectedId: current, drawingPolygon: open } = form.current;
      const chosen = all.find((marker) => marker.id === current && marker.type === "emitter");
      const key = event.key.toLowerCase();
      if (chosen && open && event.key === "Enter") {
        const points = tool.current?.closePolygon();
        if (points) form.current.decide({ ...chosen, shape: { type: "polygon", points } });
        setDrawingPolygon(false);
        return;
      }
      if (event.key === "Escape") tool.current?.cancelLink();
      if (chosen && open && event.key === "Escape") {
        setDrawingPolygon(false);
        return;
      }
      if (chosen && key in EMITTER_KEYS) {
        setMode(EMITTER_KEYS[key]);
        setDrawingPolygon(false);
        return;
      }
      if (key === "l") {
        setType("link");
        setTypedId(null);
        setSelectedId(null);
        return;
      }
      if (key !== "a") return;
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
      {lookIds.length > 0 && (
        <div className="param">
          <label htmlFor="place-look-view">Show Look</label>
          <select id="place-look-view" data-testid="place-look-view" value={viewLook} onChange={(event) => setViewLook(event.target.value)}>
            <option value="">none (the room alone)</option>
            {lookIds.map((name) => (
              <option key={name}>{name}</option>
            ))}
          </select>
        </div>
      )}
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
      {LOOK_TYPES.includes(type) && (
        <div className="param">
          <label htmlFor="marker-look">Look</label>
          <select
            id="marker-look"
            data-testid="marker-look"
            value={fields.look}
            onChange={(event) => {
              update({ look: event.target.value });
              setViewLook(event.target.value); // the Marker is drawn only while its Look is chosen
            }}
          >
            <option value="">none (the room's own)</option>
            {lookIds.map((name) => (
              <option key={name}>{name}</option>
            ))}
          </select>
        </div>
      )}
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
          <div className="param">
            <label htmlFor="marker-one-way">One-way</label>
            <input
              id="marker-one-way"
              data-testid="marker-one-way"
              type="checkbox"
              checked={fields.one_way}
              onChange={(event) => update({ one_way: event.target.checked })}
            />
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
        <>
          <div className="param">
            <label htmlFor="marker-name">Name</label>
            <input
              id="marker-name"
              data-testid="marker-name"
              value={fields.name}
              onChange={(event) => update({ name: event.target.value })}
            />
          </div>
          {emitter ? (
            <section data-testid="emitter-panel">
              <h2>Emitter {emitter.id}</h2>
              <div className="param">
                <label htmlFor="emitter-shape">Shape</label>
                <select id="emitter-shape" data-testid="emitter-shape" value={shapeKind} onChange={(event) => chooseShape(event.target.value)}>
                  {["point", "line", "box", "polygon"].map((name) => (
                    <option key={name}>{name}</option>
                  ))}
                </select>
              </div>
              {shapeKind === "polygon" && !drawingPolygon && (
                <button data-testid="emitter-polygon-again" onClick={() => setDrawingPolygon(true)}>
                  Draw the polygon again
                </button>
              )}
              <div className="tool-row" role="group" aria-label="Emitter tool">
                {(
                  [
                    ["shape", "Shape (S)"],
                    ["direction", "Direction (D)"],
                    ["eyedrop", "Eyedropper (E)"],
                  ] as const
                ).map(([name, label]) => (
                  <button key={name} data-testid={`emitter-mode-${name}`} aria-pressed={mode === name} onClick={() => setMode(name)}>
                    {label}
                  </button>
                ))}
              </div>
              <p className="hint" data-testid="emitter-help">
                {mode === "eyedrop"
                  ? "Click the room: each click adds that pixel's colour."
                  : mode === "direction"
                    ? "Drag on the room: the arrow from the Marker to where you let go is the direction."
                    : drawingPolygon
                      ? "Click the points; click the first point or press Enter to close, Escape to drop it."
                      : shapeKind === "box" || shapeKind === "line"
                        ? "Drag on the room to draw the shape; drag a corner or point to change it, or its inside to move it."
                        : "Pick a shape above."}
              </p>
              <p data-testid="emitter-direction">
                {directionOf(emitter)
                  ? `Direction: ${arrowLength(emitter)} px, to (${directionOf(emitter)!.x}, ${directionOf(emitter)!.y})`
                  : "No direction yet"}
              </p>
              {directionOf(emitter) && (
                <button data-testid="emitter-direction-clear" onClick={() => send({ ...emitter, direction: null })}>
                  Clear the direction
                </button>
              )}
              <h2>Colours</h2>
              <div className="strip" data-testid="emitter-colours">
                {chosenColours.length === 0 && <span className="hint">None yet: the game uses its own.</span>}
                {chosenColours.map((colour, index) => (
                  <span key={colour} className="chip" data-testid={`emitter-colour-${index}`} title={colour}>
                    <span className="chip-colour" style={{ background: colour }} />
                    <button aria-label={`Move ${colour} earlier`} disabled={index === 0} onClick={() => reorder(index, -1)}>
                      {"\u2039"}
                    </button>
                    <button aria-label={`Move ${colour} later`} disabled={index === chosenColours.length - 1} onClick={() => reorder(index, 1)}>
                      {"\u203a"}
                    </button>
                    <button aria-label={`Remove ${colour}`} data-testid={`emitter-colour-remove-${index}`} onClick={() => setColours(chosenColours.filter((_, at) => at !== index))}>
                      {"\u00d7"}
                    </button>
                  </span>
                ))}
              </div>
              {hint && (
                <p className="hint" data-testid="emitter-hint">
                  {hint}
                </p>
              )}
              <div className="swatches" data-testid="palette-swatches">
                {palette.map((colour) => (
                  <button
                    key={colour}
                    className="palette-swatch"
                    data-testid={`palette-${colour}`}
                    title={colour}
                    aria-label={`Add ${colour}`}
                    style={{ background: colour }}
                    onClick={() => addColour(colour)}
                  />
                ))}
              </div>
            </section>
          ) : (
            <p className="hint">Select an emitter (a click on it, or in the list) to draw its shape and direction and pick its colours.</p>
          )}
        </>
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
      {type === "link" && (
        <>
          <div className="param">
            <label htmlFor="marker-kind">Kind</label>
            <input
              id="marker-kind"
              data-testid="marker-kind"
              value={fields.kind}
              onChange={(event) => update({ kind: event.target.value })}
            />
          </div>
          <label className="toggle">
            <input
              type="checkbox"
              data-testid="marker-two-way"
              checked={fields.two_way}
              onChange={(event) => update({ two_way: event.target.checked })}
            />
            two way (an actor can cross it back, from its to end)
          </label>
          <p className="hint" data-testid="link-help">
            Click the room for the from end, then again for the to end. Drag an end to move it. Escape drops a first click.
          </p>
        </>
      )}
      <p className="hint">
        {type === "link" ? "" : isDrawnFromTwoPoints(type) ? "Drag on the canvas to draw it." : "Click the canvas to place it."} Drag a Marker to
        move it.
      </p>
      {selected && (
        <button
          data-testid="marker-save"
          onClick={() => {
            if (isLink(selected)) {
              decideLink(linkDecision(selected, { kind: fields.kind, two_way: fields.two_way }));
              return;
            }
            const { x, y, x2, y2 } = selected;
            send({
              id: selected.id,
              type: selected.type,
              x,
              y,
              ...(x2 !== undefined ? { x2, y2 } : {}),
              ...ownFields(selected.type, fields, String(selected.layer ?? layer)),
              ...(selected.type === "emitter" ? { shape: selected.shape, direction: selected.direction, colours: selected.colours } : {}),
            } as Marker);
          }}
        >
          Save {selected.id}
        </button>
      )}
      {TYPES.filter((name) => shownMarkers.some((marker) => marker.type === name)).map((name) => (
        <section key={name} data-testid={`markers-${name}`}>
          <h2>{LABELS[name]}</h2>
          {shownMarkers
            .filter((marker) => marker.type === name)
            .map((marker) => (
              <button
                key={marker.id}
                className="link marker-row"
                data-testid={`marker-${marker.id}`}
                onClick={() => choose(marker)}
              >
                {isLink(marker)
                  ? `${marker.id} (${marker.kind}, ${marker.from.join(", ")} ${marker.two_way ? "<->" : "->"} ${marker.to.join(", ")})`
                  : `${marker.id} (${marker.x}, ${marker.y}`}
                {!isLink(marker) && (<>
                {marker.x2 !== undefined && marker.type === "area" ? ` to ${marker.x2}, ${marker.y2}` : ""}){typeof marker.layer === "string" ? ` for ${marker.layer}` : ""}{typeof marker.look === "string" ? ` in ${marker.look}` : ""}</>)}
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

interface ReachedEntry {
  markers: { id: string; reached: boolean }[];
  main: string[];
  islands: (IslandBox & { spots: number; added?: number; looks?: string[] })[];
}

// report.json (schema 1): the room's own entry, and `looks`, one entry for each Look with its own `solid`.
interface ReachReport extends ReachedEntry {
  links?: { id: string; reached: boolean }[];
  looks?: Record<string, ReachedEntry>;
}

// A file beside another in the same folder, or in a folder of it: the built files are named, not worked out.
function sibling(path: string, name: string): string {
  return `${path.slice(0, path.lastIndexOf("/") + 1)}${name}`;
}

export function ReachPanel(props: {
  canvas: RefObject<PixelCanvas | null>;
  show: ShowData;
  detail: StageDetail;
  imageVersion: number;
  onWalking: (walking: boolean) => void;
}) {
  const { canvas, show, detail, imageVersion, onWalking } = props;
  const [read, setRead] = useState<ReachReport | null>(null);
  const [walking, setWalking] = useState(false);
  const [chosenLook, setChosenLook] = useState("");
  const place = show.stages.find((entry) => entry.stage === PLACE_STAGE);
  const report = detail.outputs.find((path) => path.endsWith("/report.json"));
  const roomReachable = detail.outputs.find((path) => path.endsWith("/reachable.png"));
  const roomWalkable = place?.outputs.find((path) => path.endsWith("/walkable.png"));
  const roomClear = place?.outputs.find((path) => path.endsWith("/clear.png"));
  // Only a Look with its own `solid` has an entry in report.json; the others reach what the room does.
  const lookIds = Object.keys(read?.looks ?? {});
  const look = lookIds.includes(chosenLook) ? chosenLook : "";
  const entry: ReachedEntry | null = look ? (read?.looks?.[look] ?? null) : read;
  const unreachable = JSON.stringify(
    entry ? [...entry.markers, ...(look ? [] : (read?.links ?? []))].filter((marker) => !marker.reached).map((marker) => marker.id) : [],
  );
  // The Look's own walkable and clear, which `place` writes beside the room's; a Marker in another Look is not drawn.
  const walkable = look && roomWalkable ? sibling(roomWalkable, `looks/${look}/walkable.png`) : roomWalkable;
  const clear = look && roomClear ? sibling(roomClear, `looks/${look}/clear.png`) : roomClear;
  const markers = markersOf(place).filter((marker) => typeof marker.look !== "string" || marker.look === look);
  const shown = JSON.stringify(markers);
  const overlay = useRef(new ReachOverlay());
  const overlayFile = look && report ? sibling(report, `looks/${look}/reachable.png`) : roomReachable;
  const islandsKey = JSON.stringify(entry?.islands ?? []);
  const tool = useRef(new MarkerTool(null));
  const sorted = useRef<SortedLayers>({ layers: [] });
  const crossings = useRef<Crossings>({ links: [], reach: show.tile ?? LINK_REACH });
  crossings.current.reach = show.tile ?? LINK_REACH;

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
      setRead(null);
      return;
    }
    fetch(fileUrl(report, imageVersion))
      .then((response) => response.json() as Promise<ReachReport>)
      .then((document) => {
        if (current) setRead(document);
      })
      .catch(() => {
        if (current) setRead(null); // Rebuilt while it was read; the next refresh reads it again.
      });
    return () => {
      current = false;
    };
  }, [report, imageVersion]);

  // The reachable Mask of the room, or of the chosen Look, with its islands boxed.
  useEffect(() => {
    let current = true;
    const draw = (mask: Awaited<ReturnType<typeof loadMask>> | null) => {
      if (!current) return;
      overlay.current.set(mask, JSON.parse(islandsKey) as IslandBox[], look);
      canvas.current?.redraw();
    };
    if (!overlayFile) {
      draw(null);
      return;
    }
    loadMask(fileUrl(overlayFile, imageVersion))
      .then(draw)
      .catch(() => draw(null)); // Rebuilt while it was read; the next refresh reads it again.
    return () => {
      current = false;
    };
  }, [canvas, overlayFile, islandsKey, look, imageVersion]);

  useEffect(() => {
    const all = JSON.parse(shown) as Marker[];
    crossings.current.links = all.filter((marker) => isLink(marker)) as unknown as Crossing[];
    tool.current.setMarkers(all);
    tool.current.setUnreachable(JSON.parse(unreachable) as string[]);
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
    canvas.current?.setTools([overlay.current, tool.current]);
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
        const test = new WalkTest(ground, open, body, x, y, () => canvas.current?.redraw(), sorted.current, crossings.current);
        walk.current = { from, test };
        canvas.current?.setTools([overlay.current, tool.current, test]);
      },
    );
    return () => {
      current = false;
    };
  }, [canvas, walking, walkable, clear, imageVersion, first, bodyWidth, bodyHeight, dash]);

  useEffect(() => () => stopWalking(), []);
  useEffect(() => {
    canvas.current?.setTools([overlay.current, tool.current]);
    return () => canvas.current?.setTools([]);
  }, [canvas]);

  return (
    <div className="walk">
      {lookIds.length > 0 && (
        <section data-testid="reach-looks">
          <h2>Look</h2>
          <div className="param">
            <label htmlFor="reach-look">Reach under</label>
            <select id="reach-look" data-testid="reach-look" value={look} onChange={(event) => setChosenLook(event.target.value)}>
              <option value="">none (the room alone)</option>
              {lookIds.map((name) => (
                <option key={name}>{name}</option>
              ))}
            </select>
          </div>
        </section>
      )}
      {entry && (
        <section data-testid="reach-islands">
          <h2>{look ? `Islands under ${look}` : "Islands"}</h2>
          {entry.islands.length === 0 ? (
            <p className="hint" data-testid="reach-no-islands">
              No island: every walkable spot is reached from {entry.main.length > 0 ? entry.main.join(", ") : "a Spawn or Exit"}.
            </p>
          ) : (
            <ul>
              {entry.islands.map((island) => (
                <li key={`${island.x},${island.y}`} data-testid="reach-island">
                  {island.width} x {island.height} at ({island.x}, {island.y}), {island.spots} spots
                  {look && island.added ? `, ${island.added} the Look makes walkable` : ""}
                  {!look && island.looks && island.looks.length > 0 ? `; reached under ${island.looks.join(", ")}` : ""}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
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
            The arrow keys walk the {bodyWidth} x {bodyHeight} Body{look ? ` on the ground of ${look}` : ""}.
            {crossings.current.links.length > 0 && ` ${CROSS_KEY.toUpperCase()} crosses a Link when the Body stands near one of its ends.`}
            {dash > 0 && ` Shift and an arrow dashes over a pit of up to ${dash} px.`}
          </p>
        </>
      ) : (
        <p className="hint">Build place first: the Body walks on what it derives.</p>
      )}
      {JSON.parse(unreachable).length > 0 && (
        <p className="reason" data-testid="unreachable">
          Unreachable: {(JSON.parse(unreachable) as string[]).join(", ")}
        </p>
      )}
    </div>
  );
}
