---
status: done
milestone: M6
agent: character-pipeline
type: ticket
---

# M6: the sheet packs a repeated cell once

Spec §6 (character `sheet`). Found by the Owner on 2026-11-21 while looking at `npc_tall_woman` (a `character`) for
[0360](0360-m6-ui-npc-screen.md)'s eye check.

## The problem

A `still` clip (M5: one pose at `start`, held for N frames so a blink lands in time) is rendered and packed as N cells.
`npc_tall_woman`'s `idle` (`still: 24`, `blink: [22]`) has 24 cells a direction and only 2 distinct images (open eyes,
the blink); over its sheet, 408 cells and 408 rects in the atlas. The repeated cells cost atlas area (and so texture memory in
the game) and nothing else: the 24 frames of timing are right, and the game plays them at the clip's `fps`.

## What to do

1. **`sheet`** packs a cell whose pixels (colour, and depth / normal where the sheet has them) and offset are the same as an
   earlier cell's of the same Asset once; every frame that shows it names the same `rect`. Compared pixel-exactly after
   trimming, across clips and directions (an idle held in `walk`'s first pose shares too). The frame list, its order and its
   count are unchanged, so blink indices, foot events and held things' points still line up.
2. `sheet`'s `version` bumps (what it writes changes). `character.json`'s format is unchanged if a shared `rect` is already
   allowed; if anything reads a rect as one frame's own (the export, `restore_cell`, the UI's frame strip, the Body sheet of
   Wearables), say what and make it work.
3. Export: Godot's `SpriteFrames` gets one `AtlasTexture` per distinct region, frames sharing it (no change in what plays).
   Collapsing a run of the same cell into one frame with a longer `duration` is **not** in this ticket: it changes the frame
   count the game and the events see.

## Acceptance criteria

- [x] CLI seam: a `still` clip of N frames packs 1 cell (2 with one `blink`) a direction; the exported `.tres` plays N frames.
- [x] On the art Project copy (never the original): `npc_tall_woman`'s atlas area before and after, in the Result.
- [x] `uv run mypy`, `uv run lint-imports`, the character and export tests pass.

## Result

- `pack_trimmed` (`kiripix/ops/sheet.py`) has `share=True`: a frame whose box, offset and pixels in every layer (colour, normal,
  depth) equal an earlier frame's gets that frame's `rect`; only the first is blitted and laid out. The `character_sheet` Stage
  (the body's, a Wearable's and a sprite's, which share `_run_sheet`) passes `share=True`. The comparison is after trimming,
  across clips and directions. The frame list, order and count are unchanged. `sheet.json`'s format is unchanged
  (`schema_version` 2; a shared `rect` was always allowed).
- **Version bumps:** the character `sheet` Stage 5 to 6, and the wearable `sheet` Stage 5 to 6 (same code). The sprite's `sheet`
  is the character's with `replace`, so it follows. `export` has no bump: its input hash changes with `sheet`.
- **Readers of a rect checked:** `restore_cell` and the checks work per frame, unchanged. The export (`character_frames` in
  `kiripix/export/godot.py`) now gives one `AtlasTexture` per distinct region and margin, the frames sharing it; every frame is
  still listed with `duration` 1 (no run is collapsed). The UI's frame strip (`web/src/frameScreen.tsx`) and the Wearables
  stacking preview (`web/src/wearableScreens.tsx`) cut each frame from its own `rect` and don't assume a rect is unique, so
  they need no change (`web/` untouched, no build run). `cast.py` reads cells through the frame's rect and offset: unchanged.
- **Test fixture:** the fake Blender tinted each frame by its output index, so a held pose rendered N different images, which a
  real render doesn't. `tests/fixtures/kiripix_test_recipes.py` now tints by the first output index of the same source frame
  (the same for every clip without a held pose). Its tint wraps (modulo 90) and depends on the direction name's length only, so
  a few frames of different clips and directions are identical images and now share a region; the older tests that expected one
  distinct rect or sub-resource per frame (`test_character_sheet`, `test_trimmed_cells`, `test_export_character`,
  `test_export_cell_per_clip`) now count distinct regions.
- **Tests:** `tests/cli/test_sheet_repeated_cell.py`: a `still: 6` clip with one `blink` packs 1 cell (2 with the blink; the
  facing-away direction `n` paints no eyes, so 1), every frame restores its finished cell, and the export lists 6 frames of
  duration 1 over 2 AtlasTextures a direction.
- **Measurement** (copy of the art Project in the scratchpad, `sheet` rebuilt on `character.npc_tall_woman` from its kept
  `finish`; no GPU or Blender needed): atlas 826 x 781 = 645,106 px before, 653 x 649 = 423,797 px after (-34 %); 408 cells and
  408 distinct rects before, 408 cells and 229 distinct rects after.
