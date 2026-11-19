---
status: done
milestone: M5
agent: character-pipeline
type: ticket
parent: 0236-m5-the-games-next-needs.md
depends_on: [0302-m5-render-attached-things.md]
---

# M5: a cell per clip: a clip that doesn't fit the body's cell grows its own

Part of the held-things build chosen in [0238](0238-m5-held-things-trial.md) (the Owner, 2026-11-18): option (a), the thing
attached in the character's render for the clips that hold it, at a `grip_r` socket bone, with a cell per clip and a ramp row for a
class weapon. The trial's prototype (`backlog/m5/0238-trial/`, `held_render.py`, `grip_config.json`) is the reference.

## What to build

- **The rule (the Owner, 2026-11-18):** every clip keeps the body's cell, as today; a clip whose extent (its held thing, a long attack)
  doesn't fit gets its own larger cell and pivot. Measured in 0238 over 12 clips: the stick's `attack` 86 against the body's 78 is
  +3.4 % atlas (one cell for all: +21.6 %); the rake's 138 is +34 % (one cell: +213 %).
- `render`: cell and pivot per clip (`fit_cell` already measures per clip, 0155); `render.json` per clip.
- `sheet`: the atlas laid out by clip, each clip's cells at its own size; `sheet.json` and `character.json` carry `cell` and `pivot` per
  clip. `character.json` `schema_version` bump with its migration in `kiripix/core/settings.py`; a character whose clips all share the
  body's cell keeps the clip's `cell` equal to the character's.
- `sheet`'s Checks (stationary pivot drift, `sheet.part_vanishes`) per clip. Stage `version` bumps.

## Acceptance criteria

- [x] CLI seam: a fixture character with one wider clip: that clip's cells are larger, every other clip's are the body's, and
      `character.json` lists each clip's cell and pivot.
- [x] An old `character.json` migrates; `uv run lint-imports` and `uv run mypy` pass.

## Result

- **`render` (`recipes/render.py`, Stage `version` 3, was 2):** `clip_cells` gives the body's cell and each clip's. The body's cell is `fit_cell` over the clips that hold
  nothing (over every clip when all hold something), `cell_margin` included. A clip whose padded extent `fits_cell` keeps it; one that doesn't gets `fit_cell(height, body
  extents + its own)`, so its cell is never smaller than the body's and has the same default pivot rule (centre column, `ceil(0.1 * height)` above the bottom, more when it
  reaches lower). `render.json` keeps the top-level `frame` and `pivot` as the body's and gives every clip entry `frame` (`{"width", "height"}`) and `pivot` (`[x, y]`), the
  stationary clip's frames carry that pivot. `RENDER_SCHEMA_VERSION` stays 4 (additive keys). Blender gets the frame size and pivot as the scene's, so `_launch_cells` runs it
  once per distinct cell (the measure pass is one run, as before). A clip's key holds its own cell, not the character's: a clip that grows renders no other.
- **`sheet` (`recipes/character_sheet.py`, Stage `version` 3, was 2; also the Wearable's `sheet` and `export`, and the sprite's, which share them):** `pack_by_cell` lays the atlas out in
  blocks, one per distinct cell, the body's first as one grid of `columns` columns (the layout of today, byte for byte, when every clip shares it), each other cell below it
  as its own grid, left aligned. `sheet.json` (`schema_version` stays 1; additive) gives each clip `cell` and `pivot`; the top-level ones are the body's. `depth.png` uses the same
  layout. A render without per-clip keys (a sprite's, a Wearable's) gives every clip the top-level cell. `cast.py` places each clip by its own pivot.
- **`sheet`'s Checks run per clip:** `sheet.frame_overflow` against the clip's own cell and pivot; `sheet.pivot_drift` and `sheet.empty_frame` read the clip's frames as before (the pivot is
  per frame); `sheet.frame_count` by clip. `sheet.part_vanishes` is `finish`'s (a count of a material's pixels per frame), and needs no cell.
- **`export` (`recipes/character_export.py`, Stage `version` 2, was 1) and `character.json`:** `schema_version` **6**, written always (the points-only version 5 is gone as a write; a
  reader takes 4, 5 and 6). Each clip has `cell` and `pivot`, as in `sheet.json`; the top-level ones are the body's. `kiripix.core.settings.migrate_character_record` (pure; 4 to 5 changes
  nothing, 5 to 6 gives each clip the file's cell and pivot) is what `export.character.read_character` applies; a version below 4 is refused with `export.character_invalid`.
- **Tests:** `tests/cli/test_cell_per_clip.py` (fake Blender, with `blender-reach`): the wide held clip's own cell and the others' the body's, one Blender launch per cell size,
  body cell fitted to the clips that hold nothing, only the changed clip renders again, `sheet.json` and `character.json` per clip, atlas cells not overlapping and equal to
  `finish`'s frames, a character with one cell as before, the Checks per clip, an older `character.json` read. `tests/cli/test_blender_held.py` gains a real-Blender test (a clip's frames
  have its own cell's size).
- **Left for others:** the Wearable's `render` still draws every clip at the body's top-level cell, so over a body clip with its own larger cell a Wearable's frames don't line up;
  `wearable.body_not_exported` compares the top-level cell only (0304 and a Wearable follow-up).
