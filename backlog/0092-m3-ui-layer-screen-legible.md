---
status: done
milestone: M3
agent: ui-engineer
type: ticket
depends_on: [0091-m3-remove-a-layer.md, 0083-m3-ui-show-that-work-is-happening.md]
---

# M3: the layer screen says what a click will do, and can remove a Layer

Spec §11. Found by the Owner at the [M2 gate](m2/0058-m2-gate.md), on `room.ch01_dungeon_r03`: "It's hard to understand how a lifted object
is extracted into a layer. Clicking an object and renaming a layer, or adding a new layer, doesn't seem to do anything", until "almost
a minute later the list of layers suddenly gets updated with layers that I was aimlessly lifting to see if it's working at all".

[0083](0083-m3-ui-show-that-work-is-happening.md) shows that work is running, and [0089](0089-m3-time-a-lift-honestly.md) looks at why a
lift is slow. This ticket is about the screen's model: which Layer a click goes to, and what happened to it.

## What to build

- **The Layer a click goes to is always visible:** named on the canvas cursor or beside it, not only selected in a list.
- **Adding or renaming a Layer shows at once** in the list, marked as having no pixels until its first lift lands, so the Owner
  doesn't add it again.
- **Each Layer in the list shows its state:** lifting, lifted (with its pixel count), or empty.
- **A click's result is shown against the click:** when the lift lands, the new pixels flash in the Layer's colour.
- **Remove a Layer** from the list, with [0091](0091-m3-remove-a-layer.md)'s Decision; undo brings it back.

## Acceptance criteria

Playwright, against a real `kiripix serve`:

- [x] A new Layer shows in the list before its first lift lands, and a click is drawn as going to it.
- [x] After a lift, the list shows the Layer's pixel count, and the new pixels are marked on the canvas.
- [x] Removing a Layer takes it out of the list and the canvas, and undo brings it back.

## Findings (UI pass)

- Built from existing Commands only; the pixel count is read from the Layer's own PNG alpha (no backend change).
- The target Layer is named beside the cursor, on a waiting click, and in a line in the panel ("A click goes to ...").
- A Layer appears in the list when it is built, has a Decision, is made with New Layer, or its ID is committed in the field (Enter or
  leaving it). Per-Layer state: lifting, N px, empty, no pixels yet. The new pixels flash in the Layer's colour for about 1.6 s.
- Remove sends `decide` `remove`, then always a plain `run layers` (no rerun); Ctrl+Z / Redo after a remove also run it. A refused
  remove (`export.id_frozen`) shows through the ordinary finding notice, and the Layer stays listed because the list follows the recorded
  Decisions, not the click. The place screen hides removed Layers in `layerFiles`.
- A Layer named only in the field and never lifted is dropped locally by Remove (nothing to record).
- Tests: `web/e2e/legible.spec.ts`; `layers.spec.ts` Plate test now waits for the Layer's state instead of its appearance.
- Screenshot: `web/test-results/layers-legible.png` (overwritten by each run).
