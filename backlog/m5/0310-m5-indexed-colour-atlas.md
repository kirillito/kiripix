---
status: done
milestone: M5
agent: character-pipeline
type: ticket
parent: 0307-m5-sprite-atlas-size-trial.md
---

# M5: the colour atlas as an indexed PNG

From the trial [0307](0307-m5-sprite-atlas-size-trial.md) (the Owner, 2026-11-18: build lever E). An indexed PNG is the disk
lever: -59 to -61 % alone on the four mc03 bodies. VRAM doesn't change (Godot imports a lossless PNG as RGBA8).

## What to build

- `sheet` writes `color.png` as an 8-bit indexed PNG with transparency (index 0 transparent) when the frames hold at most 256
  colours, which a palette-mapped character always does; otherwise RGBA, with an info finding naming the count.
- The normal and depth atlases stay as they are (not palette images).
- A Wearable's colour atlas the same. Stage `version` bump.

## Acceptance criteria

- [x] CLI seam: a fixture's `color.png` is mode `P`, decodes to exactly the RGBA it replaces, and is smaller on disk.
- [x] Real-Godot test (skipped without Godot): the exported scene imports and draws the indexed atlas unchanged.
- [x] `uv run lint-imports` and `uv run mypy` pass.

## Result

- `kiripix/recipes/atlas_png.py` (new, the one place the colour atlas is encoded; ticket 0308 builds on the packer, not on this):
  `write_colour_atlas` writes an indexed PNG with per-index transparency (index 0 = transparent black) when the atlas has at most
  256 colours, else RGBA and returns the count. Decoded pixels are exactly the RGBA given. `character_sheet.py` calls it for
  `color.png`; the Wearable's `sheet` runs the same function, so it gets it too. Normal and depth atlases are unchanged.
- `sheet.colour_atlas_rgba` (info, `fix` re-runs `palette`, `data.colours`) is raised by the sheet Check when `color.png` stayed
  RGBA. Not declared as a `CheckSpec` (that is in character.py, being edited by 0312); declare it there later if wanted.
- Size, fake-Blender fixture (858 x 858): 5886 bytes as RGBA, 1863 as indexed (-68 %). PIL picks the smallest bit depth that fits
  the palette (not always 8 bit); Godot imports it all the same. The 0307 mc03 bodies were -59 to -61 %.
- Version bumps: `sheet` Stage `version` 3 -> 4 in `character.py` (the sprite's sheet inherits it) and the Wearable's `sheet`
  3 -> 4 in `wearable.py`.
- Tests: `tests/cli/test_character_sheet.py` (mode P, decodes to each finished frame, index 0 transparent, smaller; >256 colours
  stays RGBA with the info finding), `test_export_wearable.py` (colour P, normal RGBA), `test_export_character.py` (real Godot 4.7.2,
  headless: the scene's texture, as imported, hashes equal to the indexed PNG decoded to RGBA8). Existing tests that read the atlas
  as an array now `.convert("RGBA")` (test_cell_per_clip, test_read_gaps, test_character_sheet).
- Left: the Godot test reads the imported texture's pixels headlessly; it doesn't render a frame in a window.

### Review follow-up (2026-11-18)

- `sheet.colour_atlas_rgba` is declared as a CheckSpec now (0308 added it), so the note above about it not being declared is out
  of date.
- `write_colour_atlas` returns the atlas's own number of distinct colours, the same count the Check reports (it had counted the
  transparent slot even when the atlas had none), and the unused `inverse` is gone.
