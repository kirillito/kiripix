---
status: done
milestone: M5
agent: character-pipeline
type: ticket
depends_on: [0303-m5-cell-per-clip.md]
---

# M5: a Wearable follows its body's cell per clip

Left by [0303](0303-m5-cell-per-clip.md): a body clip that doesn't fit the body's cell now has its own larger cell and pivot,
but a Wearable's `render` still draws every clip at the body's top-level cell, so over such a clip the Wearable's frames don't
line up with the body's. `wearable.body_not_exported` compares the top-level cell only.

## What to build

- A Wearable's `render` reads each clip's `frame` and `pivot` from its body's `render.json` and draws that clip at them; its
  `sheet` lays the clip out at the same cell, as the body's does.
- `wearable.body_not_exported` (or a new finding) compares every clip's cell and pivot with the body's.
- Stage `version` bumps.

## Acceptance criteria

- [x] CLI seam: a body with one wider clip and a Wearable over it: the Wearable's frames of that clip are the clip's cell size,
      and its pivot matches the body's, frame by frame.
- [x] A body whose clip cell changed makes the Wearable's check fail with the clip named.
- [x] `uv run lint-imports` and `uv run mypy` pass.

## Result

- `kiripix/recipes/wearable_render.py`: `render` reads each clip's `frame` and `pivot` from the body's `render.json` (the body's
  top-level cell for an older one), launches Blender once per cell size, records `frame` and `pivot` on each clip, and checks
  `wearable.outside_cell` against the clip's own cell. The `cell_margin` hint is computed from the frames that don't fit their cell.
- `sheet` needed no change: 0308's shared sheet code already lays each clip out at the `frame` and `pivot` its clip carries in
  `render.json`; `test_the_sheet_lays_each_clip_out_at_its_bodys_cell` checks it.
- `kiripix/export/wearable.py`: `wearable.body_not_exported` also compares each clip's `cell` and `pivot` with the body's
  `character.json`, naming the clip. No new finding code, so no new CheckSpec (its description now says clip by clip).
- Stage versions: Wearable `render` 2 -> 3. `sheet` stays at 5 and `export` at 4: their outputs changed only in this batch's 0308 bump.
- Tests: `tests/cli/test_wearable_cell_per_clip.py` (6 tests).

### Review follow-up (2026-11-18)

- The body check migrates the body's `character.json` (`migrate_character_record`) before comparing, so an older body's record
  is compared clip by clip instead of failing on a missing key; one too old to migrate is reported as before.
- A body clip the Wearable doesn't have is reported too, with the clip named and the fix `kiripix run <wearable>` (the body
  gained a clip since the Wearable was rendered). Two new tests in `tests/cli/test_wearable_cell_per_clip.py`.
