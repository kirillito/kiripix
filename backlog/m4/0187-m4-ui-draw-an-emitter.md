---
status: done
milestone: M4
agent: ui-engineer
type: ticket
parent: 0183-m4-ambient-animation.md
depends_on: [0185-m4-emitter-shape-direction-colours.md, 0139-m4-ui-draw-an-area.md]
---

# M4: draw an emitter's shape and direction, and pick its colours

Part of [0183](0183-m4-ambient-animation.md), route (a). Spec §11 (the place screen). Doesn't depend on the trial (0184).

## What to build

On the place screen, with an emitter Marker selected:
- **Shape:** a choice of point, line, box or polygon, drawn on the canvas with the area tool's box (0139) and the polygon
  tool's clicks (0080). Drag to move the shape with its Marker; drag a corner or point to change it.
- **Direction:** drag an arrow from the Marker; its end is the `direction` point. Shown as an arrow with its length in px.
- **Colours:** an eyedropper on the room (each click adds the pixel's colour) and a palette swatch grid; a strip of the
  chosen colours, reorderable, with remove. Off-palette is impossible from either tool.
- **Preview:** the shape filled at low opacity in a colour of the list, and a few still dots along the arrow in the chosen
  colours, so the Owner sees where particles start and go. No motion: the particles are the game's.
- Every change is one `marker` Decision through the Command, so `undo` works as for other Markers.

## Acceptance criteria

- [x] Playwright against `kiripix serve`: draw a box emitter, a direction and two colours; the built `place` output (`markers.json`) has them.
- [x] `undo` restores the previous shape; moving the Marker moves its shape and arrow.
- [ ] The Owner sets the kitchen cup's emitter (shape, upward arrow, steam colours) in under 2 minutes, timed and recorded here.

Budget: 100–180k tokens.

## Notes

2026-11-13 (ui-engineer):

- Built: `web/src/markerTool.ts` (emitter handles, arrow, shape preview, polygon clicks, translate-with-Marker) and
  `web/src/roomScreens.tsx` (the emitter panel: shape select, Shape/Direction/Eyedropper tools on `S`/`D`/`E`, colour strip with
  reorder and remove, palette swatch grid). Every change is one `marker` Decision with the whole emitter. Tests:
  `web/e2e/emitter.spec.ts` (box + direction + two colours + move + `undo`; polygon by clicks, remove a colour, clear direction).
  Screenshot: `web/test-results/place-emitter.png`.
- Gap, for a backend ticket: no Command lists the Project palette (the path is the `palette` setting, and `show` doesn't give
  it), so the UI reads `style/palette.gpl` through the file route. A Project that moves its palette would show no swatches, and the
  eyedropper would refuse every colour. A Command (or a field in `show`) giving the palette's colours would fix it.
- The ticket says `room.json` after `place`; `room.json` is the export Stage's, and `place`'s own output is `markers.json`. The test
  reads that.
- Behaviour to know: a box's Marker is its top-left corner, so dragging that corner resizes; the box moves by its inside. A line's
  Marker is its start; dragging the Marker moves the whole line, and its end is a handle. A new emitter stays selected after placing.
- Open for the Owner: the timed kitchen-cup run (under 2 minutes).
