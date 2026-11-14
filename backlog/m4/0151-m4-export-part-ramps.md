---
status: done
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

- [x] CLI seam: an export of the fake character with `parts` writes `ramps.png` with the ramps' exact colours, and
      `character.json` lists them; a re-export writes nothing.
- [x] In Godot 4.7 (headless, as 0113 did): a test shader swapping one row of `ramps.png` for other colours changes only that
      part's pixels on mc02.
      2026-11-13: run on mc03_female_clothes01 instead of mc02 (the owner's choice), in a scratch copy of the art Project
      (export pointed at a scratch Godot project; the art Project untouched), with `palette parts=skin,hair,jacket,jeans,shoes`.
      `export` wrote `ramps.png`; the probe (the test's `SWAP_PROBE`) in Godot 4.7.2 headless changed only the swapped row's
      part for each of the five rows (skin 41 px, hair 105, jacket 120, jeans 226, shoes 28), and kept the rest (250 fixed).
      2026-11-12: `test_godot_swapping_one_row_of_ramps_png_changes_only_that_parts_pixels` passes in Godot 4.7.2 headless
      (`KIRIPIX_GODOT` set to the console build), on the fake character. Headless runs the shader's rule in a probe script,
      not the shader itself. Not yet run on mc02: that needs mc02 rebuilt (`render`, `palette`, `export`) in a scratch copy of
      the art Project.
