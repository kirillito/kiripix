---
status: todo
milestone: M3
agent: character-pipeline
type: ticket
parent: 0097-m3-characters.md
depends_on: [0111-m3-finish-stage.md, 0108-m3-sheet-ops-and-checks.md]
---

# M3: the `sheet` Stage

Spec §6.3 (sheet, Checks). Story 13 of [0097](0097-m3-characters.md). Q10 and Q12 of 0097.

## What to build

- Packs the finished colour frames into an atlas, and the normal frames into a second atlas with the same layout, with
  [0108](0108-m3-sheet-ops-and-checks.md)'s `pack_atlas`. One cell size for the character, with the pivot (the feet) at the
  same point in every cell.
- `sheet.json`: `schema_version`, the cell size, the pivot in the cell, and per clip and direction its frames (rectangles),
  frame rate and loop flag. The exporter and the UI read it; nothing reads `render`'s files after this.
- Its Checks: `sheet.pivot_drift` on the stationary clips, `sheet.frame_overflow`, `sheet.frame_count`, `sheet.empty_frame`.

## Acceptance criteria

- [ ] CLI seam, on the fake: `run` writes both atlases and `sheet.json`; the frames' rectangles line up between them.
- [ ] A fake idle whose pivot moves fails `sheet.pivot_drift` with exit 2, and the finding names the frame.
- [ ] A fake frame that is empty, and one too large for the cell, each give their finding.
