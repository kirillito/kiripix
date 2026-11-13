---
status: todo
milestone: M4
agent: ui-engineer
type: ticket
parent: 0133-m4-rooms-for-grid-battles.md
depends_on: [0198-m4-finding-points.md]
---

# M4: the place screen reads ambiguous cells from the finding's points

Follows [0198](0198-m4-finding-points.md). Found in the review of [0139](0139-m4-ui-draw-an-area.md).

## What to build

- `ambiguousCells()` in `web/src/markerTool.ts` reads the cells from the finding's new field instead of parsing its message,
  and the area's ID from the finding's `position`, so every cell is highlighted. Delete the message regexes.
- The jump from the finding (in `App.tsx`) uses the same field.

## Acceptance criteria

- [ ] Playwright: on a test room with more than 8 ambiguous cells, the ninth is highlighted (`data-ambiguous`), and clicking
      the finding jumps to the first cell. 0139's test checked only that the click records no Decision; this checks the jump.

Budget: 30–60k tokens.
