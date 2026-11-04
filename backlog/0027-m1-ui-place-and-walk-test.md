---
status: done
milestone: M1
agent: ui-engineer
type: ticket
parent: 0010-m1-room-end-to-end.md
depends_on: [0025-m1-ui-shell.md, 0019-m1-reach.md]
---

# M1: the UI place screen and the walk test

Spec §6.1 (Walk test) and §11. User story 32 of [0010](0010-m1-room-end-to-end.md).

## What to build

- The place screen: Markers by type with an ID field; a dropdown of target rooms and Exit IDs for Exits; fields for
  lights and emitters. Dragging a Marker is one `decide` on release. Y-sort lines drawn on the canvas.
- The reach screen's walk test: the Body walks the room with the arrow keys at game resolution, on the real collision
  (the `solid` Mask and the Body's footprint, read from Command outputs, never recomputed in the UI), with foreground
  Layers drawn by their y-sort lines (none in M1). Unreachable Markers from `reach` are highlighted.

## Notes

- **`pit`** (added by [0019](0019-m1-reach.md)) stops the Body as `solid` does, and the Body's dash crosses it. Walkable
  already covers both, so read that rather than `solid` alone.
- **The walk test reads Command outputs only:** `walkable.png`, and a new `clear.png` from `place` (where the footprint
  touches no `solid`), which is what a dash may pass over. `show` gained each Stage's `outputs` and `markers`, and the
  project's `body`. Shift and an arrow dashes.
- **The dash is one rule in the UI** (the Owner's decision, 2026-11-04: the game won't have a dash, so this isn't worth a
  Command). It moves to the first walkable spot, within the dash plus the footprint, over clear spots. That repeats the
  rule of `ops.reach`, because the masks alone don't say where a dash lands. It does nothing at `dash = 0`, the default. If
  the rule in `ops.reach` changes, `web/src/walkTest.ts` has to change with it.
- **An Exit's target Exit** is a typed field with a dropdown of the room's Exits, not a closed list, because two rooms
  that point at each other can't both name an Exit that exists yet.
- **`CanvasTool`** is how a screen adds to `PixelCanvas`: draw over the image and take a gesture. The masks screen
  ([0026](0026-m1-ui-masks.md)) can use it too.

## Acceptance criteria

- [x] Playwright: placing a Spawn records one Decision; dragging it records one more and moves it.
- [x] Playwright: in the walk test, the Body stops at a `solid` edge.
