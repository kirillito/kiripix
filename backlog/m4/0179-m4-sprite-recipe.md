---
status: todo
milestone: M4
agent: character-pipeline
type: ticket
parent: 0174-m4-sprite-kind.md
depends_on: [0175-m4-sprite-pixellab-export-trial.md, 0176-m4-character-stages-read-a-named-frame-list.md, 0177-m4-sprite-ops.md, 0178-m4-import-a-sheet.md]
---

# M4: the `sprite` Recipe: `frames`, `fit`, and the character's Stages after them

Part of [0174](0174-m4-sprite-kind.md), whose "Decisions" section is this ticket's design: read it first. Spec §6.2 (`fit`),
§6.3. The recipe is `frames → fit → palette → finish → sheet → export`.

## What to build

**The Kind,** in `kiripix/recipes/sprite.py`, registered in `kiripix/recipes/__init__.py`: `sprite`, "An actor built from
imported 2D frames, such as a PixelLab figure, exported exactly as a character is." `palette`, `finish`, `sheet` and `export`
are the character's StageSpecs, made by 0176's factory with `fit` as the frame-list Stage; `finish` defaults to
`normals = height` and `placement = edge`.

**`frames`**, inputs `src/sheets/*`:
- Parameter `directions`: `8`, `4` (`s e n w`) or `1` (`s`).
- Decision `sheet`: for a PNG, `{file, clip, layout: rows|columns, directions: [...], frames}`; for a ZIP, `{file, clips:
  {"<their name>": "<clip>"}}` (optional renames). A ZIP is read by the naming rule from [0175](0175-m4-sprite-pixellab-export-trial.md):
  direction words (PixelLab's and ours), frame numbers, the clip from the animation folder, `idle` for rotations alone. A PNG
  sheet with no `sheet` Decision is `needs-input` ("say how the sheet's rows map to directions"); a ZIP needs none.
- Decision `clip`: `{name, fps, loop, stationary}`. A clip with none gets fps 8, loop on, and stationary when it has one frame.
- Output in `work/frames/`: `color/<clip>/<dir>/<NNN>.png` at source resolution and `frames.json` (each frame's file and the
  sheet it came from).
- Checks: `frames.direction_missing` (error: a clip lacks one of the directions `directions` asks for; an `owner_action` to
  import it; never mirrored), `frames.frame_count` (warning: a clip's directions have different frame counts),
  `frames.unknown_direction` (a ZIP entry the rule can't place, with its path), `clips.bad_name` and `clips.duplicate_name`
  (the character's rules: snake_case, no direction suffix).

**`fit`**, upstream `frames`, settings `character.height`:
- Parameters: `mode` (`grid` default, or `downscale`), `height` (downscale only; the Project's `[character] height` when unset),
  `chroma` (`#RRGGBB` or empty, default empty), `align_feet` (bool, default false).
- `grid`: `detect_grid` on every frame; all must share one scale and are sampled with it (`fit.grid_differs` names the frames
  that don't). `downscale`: one Grid for the whole Asset, the scale that brings the reference frame's opaque height (the first
  frame of `idle` in `s`, else the first frame) to `height`, line-keeping, as a Prop's `fit`. Then the alpha by vote: binary.
- The feet (`feet_point`) of every frame; a pivot per direction (the median of its stationary frames' feet, or of all its frames
  when no clip is stationary), unless a `pivot` Decision (`{x, y, direction?}` in the frame's target pixels; no direction means
  all) sets it. With `align_feet`, each stationary frame is placed by its own feet instead.
- Every frame is placed on one cell: the smallest that holds every frame around one cell pivot with 1 px to spare on each side
  for the outline (as `render` sizes its cell, spec §6.3).
- Output in `work/fit/`: `color/<clip>/<dir>/<NNN>.png` and `render.json` in the character's schema (`frame`, `pivot`,
  `directions` in the compass order, `clips` with `fps`, `loop`, `stationary` and each frame's `files.color`, `pivot` and `feet`).
  `sheet`'s frame counts are read from this document (0176), so no `clips.json` is needed; if `sheet` still reads
  `clips.json`, write one.
- Checks: `fit.grid_differs`, `fit.alpha_partial` (can't happen after the vote; the Check guards it), `fit.height` (info: the
  tallest figure's height against `[character] height` and the game's 46–58 band, as numbers), `fit.cell_grew` (info: a frame
  far from the others widened the cell, with the frame named).

**Docs:** the glossary's Kind line gains `sprite`, and a **Sprite** entry ("An Asset of Kind sprite: an actor built from
imported 2D frames, exported as a character is. _Avoid_: sprite for one frame (say frame), or for Godot's `Sprite2D`"). Spec
§3's Kind list, a new §6.4 from 0174's table, and §11's character screen line ("and a sprite's Stages from `fit`").

## Acceptance criteria

- [ ] CLI seam, on synthetic fixtures (0174's Testing Decisions): a 4-direction PNG sheet and a ZIP in PixelLab's layout run to
      `sheet` with no Decision but the PNG's `sheet`; a ×4 upscaled sheet fits to the same frames as its ×1 original; a sheet
      missing `w` reports `frames.direction_missing` and `export` stays blocked; a stationary idle with a 1 px hop reports
      `sheet.pivot_drift` and is quiet after `set … fit align_feet=true`; a `pivot` Decision moves the pivot, and `undo` restores it.
- [ ] `downscale` on a large test figure gives the figure `height` px tall, and every frame the same scale.
- [ ] `palette`, `finish` and `sheet` of a sprite write the same files a character's do, in the same layout (`character.json`
      schema 1 from `export`).
- [ ] `describe sprite` lists the Stages, Decisions and Checks; the contract samples pass; `lint-imports` and `mypy` pass.

Budget: 250–400k tokens.
