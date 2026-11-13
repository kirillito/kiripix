---
status: done
milestone: M4
agent: ui-engineer
type: ticket
parent: 0133-m4-rooms-for-grid-battles.md
depends_on: [0137-m4-area-marker.md]
---

# M4: draw an area on the place screen

Spec §11 (Place).

## What to build

- An area tool on the place screen: drag a box, then give it an ID and an optional cell. With a cell, the box snaps while you
  drag and shows its cell grid.
- Move and resize an existing area by its handles. Each change is one `marker` Decision with the same ID, so `undo` steps back.
- The cells from `area.ambiguous_cells` are highlighted, and the finding jumps to them.

## Acceptance criteria

- [x] Playwright: draw an area with a cell of 32, resize it, undo, and see an ambiguous cell highlighted on a test room.

Budget: 150–250k tokens.

## Notes

2026-11-12:

- Built: an `area` type on the place screen's Marker form (key `A` picks it), with Cell (px) and walkable. A drag draws the box,
  snapped outward to the cell while dragging, with its cell grid. Corner handles resize; the inside of a selected area moves it
  (by whole cells with a cell). Each is one `marker` Decision with the same ID, so `undo` steps back. Code: `web/src/markerTool.ts`,
  `web/src/roomScreens.tsx`; test: `web/e2e/area.spec.ts`; screenshot: `web/test-results/place-area-ambiguous-cell.png`.
- Decided: a newly drawn area's Decision carries the corners as dragged, and the backend snaps them; a resize or move
  carries the snapped box. The preview shows the snapped box either way. A move or resize stays inside the room.
- Decided: a bare click draws nothing for an area without a cell (with a cell it draws one cell).
- **Backend gap:** `area.ambiguous_cells` has no field for its cell positions, only the message text, which lists at most 8
  ("and N more"). The UI reads the positions out of the message (`ambiguousCells` in `markerTool.ts`), so cells beyond the eighth
  are not highlighted. A structured list on the finding (for example a `cells` field) is a small backend change; when it
  lands, `ambiguousCells` is the one function to change. The jump goes to the first listed cell.
- The finding is an info finding, so it sits behind the "info" toggle of the checks list.
