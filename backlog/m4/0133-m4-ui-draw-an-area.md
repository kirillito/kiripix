---
status: todo
milestone: M4
agent: ui-engineer
type: ticket
parent: 0127-m4-rooms-for-grid-battles.md
depends_on: [0131-m4-area-marker.md]
---

# M4: draw an area on the place screen

Spec §11 (Place).

## What to build

- An area tool on the place screen: drag a box, then give it an ID and an optional cell. With a cell, the box snaps while you
  drag and shows its cell grid.
- Move and resize an existing area by its handles. Each change is one `marker` Decision with the same ID, so `undo` steps back.
- The cells from `area.ambiguous_cells` are highlighted, and the finding jumps to them.

## Acceptance criteria

- [ ] Playwright: draw an area with a cell of 32, resize it, undo, and see an ambiguous cell highlighted on a test room.

Budget: 150–250k tokens.
