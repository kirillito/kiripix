---
status: todo
milestone: M4
agent: ui-engineer
type: ticket
parent: 0127-m4-room-looks.md
---

# M4: the looks screen

Spec §6.1 (Looks) and §11; ADR 0009. Needs [0130](0130-m4-looks-stage.md). Follows M3's usability work
([0092](../m3/0092-m3-ui-layer-screen-legible.md), [0093](../m3/0093-m3-ui-findings-a-person-can-read.md)), so build on what those set.

## What to build

- A list of the room's Looks, each with its ID and its Condition when it has one, and the drag-and-drop import of an edit.
- A toggle between the room and the Look, at integer zoom, so the Owner sees exactly what the game will switch.
- Region by polygon and brush, and `difference` with a box and a tolerance slider, previewed before it is recorded.
- `look.drift`'s boxes drawn on the canvas, and clicking the finding goes to them.
- The Look's `solid` painted as on the masks screen.

Every action is one Command, as everywhere else.

## Acceptance criteria

- [ ] Playwright: import an edit, name the Look, draw a region, and see the toggle change only the region.
- [ ] A drift finding's box shows on the canvas.
