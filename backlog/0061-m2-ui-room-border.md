---
status: todo
milestone: M2
agent: ui-engineer
type: ticket
parent: 0037-m2-layers-and-props.md
depends_on: [0060-m2-room-border.md]
---

# M2: the room border on the masks screen

Spec §11. Story 18 of [0037](0037-m2-layers-and-props.md). The UI half of [0060](0060-m2-room-border.md).

## What to build

- A "Wall off edges" action on the masks screen, with a toggle per side, all on by default. One click is one `decide` with the
  current Mask, followed by the `run` the rebuild option already adds.
- `masks.open_edge` shows in the findings panel, and clicking it jumps to the edge.
- `Ctrl+Z` undoes it like any other Decision. The UI works nothing out for itself: the wall comes from Command outputs.

## Acceptance criteria

- [ ] Playwright: the action records one Decision, with the chosen sides, and the wall shows on the canvas.
- [ ] Playwright: `Ctrl+Z` removes the wall.
- [ ] Playwright: in the walk test, the Body still stops at the room's edge.
