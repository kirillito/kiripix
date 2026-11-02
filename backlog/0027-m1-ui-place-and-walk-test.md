---
status: todo
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

## Acceptance criteria

- [ ] Playwright: placing a Spawn records one Decision; dragging it records one more and moves it.
- [ ] Playwright: in the walk test, the Body stops at a `solid` edge.
