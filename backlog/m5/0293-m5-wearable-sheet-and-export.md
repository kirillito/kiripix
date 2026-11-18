---
status: done
milestone: M5
agent: godot-export
type: ticket
parent: 0152-m5-character-layers.md
depends_on: [0292-m5-wearable-palette-finish.md]
---

# M5: a Wearable's `sheet` and `export`

Part of [0152](0152-m5-character-layers.md). From the trial [0153](0153-m5-character-layer-trial.md)'s Results and the Owner's answers (2026-11-18).

## What to build

- **`sheet`:** the body's cell, pivot and frame layout, so a Wearable lies pixel for pixel on the body. Colour, normal and depth
  atlases.
- **`export`:** the body's animation names (`<clip>_<dir>`), under `wearable/<name>/` in the export root and in the Manifest, and a
  Wearable record, `wearable.json` (`schema_version`, `asset`, `body`, `order`, the depth atlas, the parts and their ramps). `order`
  is the default stacking order, an integer parameter (the trial's: body, legs, jacket or coat, pack, hair). The game stacks by
  `order`, or by depth in its compositor for an exact result.
- A Wearable exports only after its body has, with the same cell; otherwise `wearable.body_not_exported`.
- Spec §9 gets a Wearable row.

## Acceptance criteria

- [x] CLI seam: a Wearable exports its atlases and `wearable.json`, listed in the Manifest; a second export writes nothing.
- [x] `--prune` removes a deleted Wearable's files.

## Result

- **`sheet`** (`kiripix/recipes/wearable_sheet.py`): the character's `sheet` run on the Wearable's `finish` frames (so the cell, pivot,
  grid and rects are the body's: the render's), plus `depth.png`, the render's 16 bit depth pass packed with the same cells (the value
  in two bytes through `pack_atlas`, then joined; 65535 where a cell has no frame pixel). `sheet.json` is the character's with
  `files.depth` and `order` added (`schema_version` still 1: new keys, only in a Wearable's). Upstream `finish` and `render`; the
  character's four sheet Checks.
- **`order`**: an int parameter of `sheet`, default 10 (the body is 0), range -1000 to 1000. Changing it makes `sheet` and `export`
  stale and nothing before. Equal orders go by Asset ID.
- **`export`** (`wearable_export.py`): `color.png`, `normal.png`, `depth.png` copied and `wearable.json` (`schema_version` 1,
  `asset`, `body`, `order`, `files`, `cell`, `pivot`, `atlas`, `directions`, `clips`, `parts` with `indexes` and `rgb`). No `ramps.png`
  or `rows`: a Wearable's ramps are in `parts`. In the game: `wearable/<name>/` with the files above, `texture.tres`, `frames.tres`
  (`character_frames`, so the body's `<clip>_<dir>` names) and `<name>.tscn` (`character_scene`), all in the Manifest; the animation
  names are its frozen clip IDs. The Exporter is `kiripix/export/wearable.py` plus `_wearable_files` in `export/__init__.py`.
- **`wearable.body_not_exported`** (error, `fix` `kiripix export <body>`, exit 1): the body's Manifest doesn't list it as exported, or
  the body's `character.json` in the game has another cell or pivot than the Wearable's. In `export --all` the body in the same call
  counts (its planned `character.json` is used), so a Wearable is planned after the others. `export_pending` counts a refused
  Wearable as pending.
- **`--prune`** needed no change: the Manifest-driven prune and the `.import` sidecars apply to any Asset.
- **The stack Check** (`wearable.stack_differs`) reads `order` now: core gives `StageRun.wearing_order` (each Wearable's `sheet`
  `order`, from `graph._wearing`), and `wearable_stack.py` sorts by (order, ID). No change to the Check's output with equal orders.
- **Version bumps:** the Wearable's `sheet` to 2 and `export` to 2 (the first that build anything; 0290's were stubs). No other Stage's
  output changed.
- Spec §9 has a Wearable row; §6.3's Wearable note says what 0293 built.
- **Tests:** `tests/cli/test_export_wearable.py` (11, on the fake Blender: the sheet's layout and atlases, `order`, the Stage's outputs,
  Manifest and a second export writing nothing, byte-identical after a rebuild, body not exported, another cell, `--all`, `--force`,
  `--adopt`, `--prune` with a sidecar) and one more in `test_wearable_stack.py` (order, not ID). No golden text file: the Wearable's
  scene, SpriteFrames and CanvasTexture come from the character's writers, whose goldens exist. No real-Godot test.
