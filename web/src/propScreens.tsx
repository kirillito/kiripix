// The prop's hand-written screen (spec §6.2, §11): the footprint, a canvas tool for the collision polygon and the y-sort
// origin. Every other prop Stage is a shared screen rendered from `describe`.

import { useEffect, useRef, useState, type RefObject } from "react";
import type { StageDetail } from "./api";
import { FootprintTool, type Footprint, type FootprintMode, type Point } from "./footprintTool";
import { isTyping, type PixelCanvas } from "./pixelCanvas";

export const FOOTPRINT_DECISION = "footprint";
export const FOOTPRINT_STAGE = "footprint";

// The latest Decision is the one that counts (the Stage's own rule); `show` lists only the Decisions that stand.
function standing(detail: StageDetail): Footprint {
  const found = detail.decisions.filter((decision) => decision.name === FOOTPRINT_DECISION).at(-1);
  if (!found) return { polygon: [], origin: null };
  const { polygon, origin } = found.data as { polygon?: Point[]; origin?: Point };
  return { polygon: polygon ?? [], origin: origin ?? null };
}

export function FootprintPanel(props: {
  canvas: RefObject<PixelCanvas | null>;
  detail: StageDetail;
  decide: (footprint: { polygon: Point[]; origin: Point }) => void;
  disabled: boolean;
}) {
  const { canvas, detail, decide, disabled } = props;
  const footprint = standing(detail);
  const [mode, setMode] = useState<FootprintMode>(footprint.origin ? "polygon" : "origin");
  const form = useRef({ decide, disabled });
  form.current = { decide, disabled };
  const tool = useRef<FootprintTool | null>(null);
  const shown = JSON.stringify(footprint);

  useEffect(() => {
    const drawing = new FootprintTool({
      change(next) {
        if (!form.current.disabled) form.current.decide(next);
      },
    });
    tool.current = drawing;
    canvas.current?.setTools([drawing]);
    return () => canvas.current?.setTools([]);
  }, [canvas]);

  // Every refresh brings the Decisions that stand, so a gesture that was refused goes back to where they are.
  useEffect(() => {
    if (!tool.current) return;
    tool.current.mode = mode;
    tool.current.set(JSON.parse(shown) as Footprint);
    canvas.current?.redraw();
  }, [canvas, shown, mode]);

  // `O` and `P` switch between the origin and the polygon.
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (isTyping(event.target) || event.ctrlKey || event.metaKey || event.altKey) return;
      if (event.code === "KeyO") setMode("origin");
      else if (event.code === "KeyP") setMode("polygon");
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const { polygon, origin } = footprint;
  const record = (next: Point[]) => {
    if (origin) decide({ polygon: next, origin });
  };

  return (
    <fieldset disabled={disabled} className="footprint-form">
      <h2>Footprint</h2>
      <div className="tools" role="group" aria-label="Tool">
        <button data-testid="footprint-origin" aria-pressed={mode === "origin"} onClick={() => setMode("origin")}>
          Origin (O)
        </button>
        <button
          data-testid="footprint-polygon"
          aria-pressed={mode === "polygon"}
          disabled={!origin}
          onClick={() => setMode("polygon")}
        >
          Polygon (P)
        </button>
      </div>
      <p className="hint" data-testid="footprint-hint">
        {mode === "origin"
          ? "Click the canvas to put the y-sort origin there, or drag it."
          : "Click the canvas to add a point to the collision polygon. Drag a point to move it."}
        {!origin && " Set the origin first."}
      </p>
      <p data-testid="footprint-summary">
        Origin: {origin ? `(${origin[0]}, ${origin[1]})` : "not set"}. Polygon: {polygon.length} point(s).
      </p>
      {origin && polygon.length > 0 && (
        <div className="decisions">
          <button data-testid="footprint-remove-last" onClick={() => record(polygon.slice(0, -1))}>
            Remove last point
          </button>
          <button data-testid="footprint-clear" onClick={() => record([])}>
            No collision
          </button>
        </div>
      )}
    </fieldset>
  );
}
