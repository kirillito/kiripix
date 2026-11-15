---
status: done
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

- [x] Playwright: on a test room with more than 8 ambiguous cells, the ninth is highlighted (`data-ambiguous`), and clicking
      the finding jumps to the first cell. 0139's test checked only that the click records no Decision; this checks the jump.

Budget: 30–60k tokens.

## Result (2026-11-14)

- `ambiguousCells()` in `web/src/markerTool.ts` reads the finding's `points` (a missing key is an empty list); the message
  regexes are gone. `Finding` in `web/src/api.ts` has the optional `points`.
- The finding's `position` has no area ID, only the area's box (corners included). The tool matches each area by that box
  (the Markers in `detail` are already snapped to the cell), so two areas with the same box would share their cells. If the
  ID is wanted in the finding, that is a backend follow-up (a `field` in the position).
- The jump in `App.tsx` needed no change: it already took `ambiguousCells(finding).cells[0]`, which is now the first point.
- Playwright (`web/e2e/area.spec.ts`): a room with a cell of 3 has 11 ambiguous cells; `data-ambiguous` lists all 11 (the
  ninth, `battle.yard@15,24`, and the eleventh), and clicking the finding focuses the first cell (`data-focus="15,0"`) with
  no Decision. Screenshot: `web/test-results/place-area-ambiguous-cell.png`.
- `npm run build` passes; `area.spec.ts` passes (3 tests, `--workers=1`).
