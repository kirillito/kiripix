---
status: done
milestone: M5
agent: character-pipeline
type: ticket
parent: 0307-m5-sprite-atlas-size-trial.md
---

# M5: trimmed cells: the sheet packs each frame's opaque box, not its whole cell

From the trial [0307](0307-m5-sprite-atlas-size-trial.md) (the Owner, 2026-11-18: build lever B). Trimming is the VRAM lever:
-77 % alone on the four mc03 bodies, -5 to -10 % on disk. The trial's prototype is in `backlog/m5/0307-trial/` (`measure.py`,
`prep_godot.py`).

## What to build

- `sheet`: each frame cropped to its opaque box (colour, normal, depth and mask alike: one box per frame over every layer),
  packed into the atlas. Each frame records its packed `rect` and its `offset` inside its clip's logical cell (0303's per-clip
  `cell` and `pivot` stay the logical size), so the cell can be restored exactly.
- `sheet.json` and `character.json` carry the per-frame `offset` (a `schema_version` bump with its migration in
  `kiripix/core/settings.py`; an old file's frames have offset 0 and a rect the size of the cell).
- An empty frame (fully transparent) keeps a 1 x 1 rect, so every frame has a region.
- The `sheet` Checks read the logical cell, not the packed rect. Stage `version` bump.
- A Wearable's sheet (it shares the sheet code) trims the same way; a body and its Wearables still line up frame by frame.

## Acceptance criteria

- [x] CLI seam: a fixture character's atlas area falls, and every frame restored from `rect` + `offset` into its cell is
      byte-identical to the untrimmed frame.
- [x] An old `character.json` migrates; `uv run lint-imports` and `uv run mypy` pass.

## Result

**Built.** `sheet` cuts each frame to the opaque box it has over its colour and normal layers (any pixel that isn't all zero, so a
restore is byte-exact), packs the boxes in shelves (tallest first, 1 px gap, deterministic) and records each frame's packed `rect` and its
`offset` in its clip's logical cell. The new Ops are in `kiripix/ops/sheet.py` (`place_in_cell`, `opaque_box`, `shelf_layout`,
`pack_trimmed`, `blit_trimmed`); `character_sheet.py` uses them and the old per-cell grid packer (`pack_by_cell`) and `columns` are gone.
An empty frame has a 1 x 1 `rect` at offset 0, 0. `depth.png` (body and Wearable) is cut to the colour atlas's boxes, so it keeps the one
layout (a depth pixel outside a frame's box is far, 65535: it is outside every drawn pixel). A Wearable's sheet shares the code, so it is
trimmed with its own boxes: its `rect`s and atlas differ from the body's, its cell, pivot, clip names and frame lists are the same, so
body and Wearable line up frame by frame in the logical cell. The `sheet` Checks still read `finish`'s frames and the clip's logical
cell, never the packed rect. `restore_cell` (`character_sheet.py`) puts a trimmed frame back in its cell; `core/cast.py` uses it (the
cast sheet and snapshots draw whole cells again), and a snapshot of a version 1 sheet still draws (`core/snapshots.py` accepts 1 and 2).

**Atlas area, fake-Blender hero (8 directions, 112 frames of 78 x 78 = 681408 px of cell).** With a 3 px transparent border (the default
fixture) 824 x 824 = 678976 px (-0.4 %: the fake figure fills almost the whole cell). With a 20 px border (`finished(border=20)`) 450 x 450 =
202500 px (-70 %). The 0307 trial measured -77 % VRAM on the real mc03 bodies, whose figures fill little of the cell. Every frame, restored from
`rect` + `offset`, equals the untrimmed finish frame byte for byte (colour and normal), in `tests/cli/test_trimmed_cells.py`.

**Version and schema bumps.**
- `sheet` Stage `version` 4 -> 5 (character, which the sprite inherits; and the Wearable's); `sheet.json` `schema_version` 1 -> 2
  (`SHEET_SCHEMA_VERSION`; no migration: a Stage's rebuilt output, refused when old, naming the sheet rebuild).
- `export` Stage `version` 2 -> 3 (character) and 3 -> 4 (Wearable): the `export` input hash already follows `sheet`, bumped for the format.
- `character.json` `schema_version` 6 -> 7, with the pure migration `_add_frame_offsets` in `kiripix/core/settings.py` (a version 4, 5 or
  6 file's frames get `offset` 0, 0; their rect is already the cell). `CHARACTER_SCHEMA_VERSIONS` = 4 to 7. Tested through `kiripix export`
  with a version 6 file.
- `wearable.json` `schema_version` 1 -> 2 (each frame has `offset`, `rect` is trimmed); refused when old like the sheet (a Wearable is new in M5, no
  migration). Your call if the owner has exported ones in the game that need migrating.
- `columns` is gone from `sheet.json`, `character.json` and `wearable.json` (nothing read it).

**Fields ticket 0309 should read** (the same in `sheet.json`, `character.json` and `wearable.json`; `character.json`'s frame is
`{"index", "rect", "offset", ["points"]}`):
- `clips[i].cell` {width, height} and `clips[i].pivot` {x, y}: the clip's logical cell and pivot (0303, unchanged).
- `clips[i].directions[d][j].rect` {x, y, width, height}: the frame's box in the atlas: the `AtlasTexture.region`.
- `clips[i].directions[d][j].offset` {x, y}: where that box sits in the clip's cell. The `AtlasTexture.margin` for a clip whose cell is the
  logical cell is `Rect2(offset.x, offset.y, cell.width - rect.width - offset.x, cell.height - rect.height - offset.y)`. With 0304's `logical_cell`
  (left, top, width, height), shift by the clip's pivot: left margin `offset.x + left - pivot.x`, top `offset.y + top - pivot.y`, right
  `width - (left - pivot.x) - offset.x - rect.width`, bottom `height - (top - pivot.y) - offset.y - rect.height`. Always write a margin now (no
  frame is the whole cell any more), except a frame whose rect is its whole logical cell.
- Top level `cell`, `pivot` and `atlas` {width, height} (the atlas's size) are as before.

**Left.**
- Until 0309, the export still writes `region = rect` with no offset: the scene draws a trimmed frame un-padded (the feet are not on the
  pivot). `tests/cli/test_export_character.py` expects the real-Godot probe's region `[74, 74]` (the fixture's trimmed rect) for now; 0309 should
  assert the padded cell instead. `tests/cli/test_export_cell_per_clip.py` still passes only because its fixture's frames fill their cells.
- Declared the `sheet.colour_atlas_rgba` CheckSpec (character `sheet`, inherited by the Wearable's), the one 0310 left out.
- Not measured: the real mc03 bodies (no scratch Project built); the shelf packer was not compared with the trial's MaxRects.

### Review follow-up (2026-11-18)

- **Depth is now in the box.** The review found `depth.png` cut to the colour and normal box, so depth the render drew outside it
  (an alpha-cut edge) became far. `sheet` now cuts depth in the same pass as colour and normal (`_depth_cells`, a pixel counting
  where it is nearer than 65535), so one box covers all three and each restores byte for byte. `add_depth_atlas` is replaced by
  `run_sheet_with_depth`, which the body's and a Wearable's `sheet` use. On a real render the background depth is 65535, so the
  trim is unchanged there; the test fixture's `border` now clears the fake render's depth to 65535 as well. New test:
  `test_depth_drawn_outside_the_colour_is_inside_the_box_and_restored_byte_identical`. No further version bump (same batch).
- **`sheet.json` and `wearable.json` have no migration on purpose.** Both are rebuilt Stage outputs: an old one is refused with a
  finding that names the rebuild (`sheet` again, or `kiripix run <id> export --force` via `export.wearable_invalid`), the
  CLAUDE.md rule for rebuilt output. `character.json` is the one the game holds, so it migrates. The migration from 6 to 7 now
  also drops `columns`, which version 7 no longer has.
- Golden tests for the new Ops in `tests/golden/test_sheet.py` (`opaque_box`, `shelf_layout`, `pack_trimmed`); new image
  `tests/golden/expected/sheet_trimmed.png` for the Owner to review.
