---
status: todo
milestone: M4
agent: godot-export
type: ticket
parent: 0147-m4-character-palette-ramps.md
depends_on: [0150-m4-palette-ramps-per-part.md]
---

# M4: the export gives the game each part's ramp

Spec §9 (character export). Part of [0147](0147-m4-character-palette-ramps.md).

## What to build

- `character.json` gains `parts`: `[{"name": "skin", "materials": ["skin"], "indexes": [...], "rgb": [[r, g, b], ...]}]`, dark to
  light, in `palette`'s order. Bump its `schema_version`. With no parts, `parts` is `[]`.
- The Godot exporter writes `ramps.png` beside `color.png`: one row per part in that order, one pixel per ramp step, the row
  padded with transparent pixels to the longest ramp. The scene's root names it in `metadata/kiripix_ramps`, with the part names
  in row order in `metadata/kiripix_parts`. It is owned through the Manifest like the atlases.
- Spec §9's Character row already says what the game gets (written 2026-11-12, with 0166's Project order); check it matches.
- The row order here is `palette`'s, for one character. [0169](0169-m4-export-ramps-in-project-order.md) later puts rows in the
  Project ramp table's order, the same on every character, so write the rows from a list of part names, not by position.

## Acceptance criteria

- [ ] CLI seam: an export of the fake character with `parts` writes `ramps.png` with the ramps' exact colours, and
      `character.json` lists them; a re-export writes nothing.
- [ ] In Godot 4.7 (headless, as 0113 did): a test shader swapping one row of `ramps.png` for other colours changes only that
      part's pixels on mc02.
