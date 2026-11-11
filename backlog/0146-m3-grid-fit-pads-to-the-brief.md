---
status: done
milestone: M3
agent: imaging-engineer
type: ticket
---

# M3: grid `fit` pads up to the brief instead of failing on size

Spec §6.1 (fit) and §6.2. **Urgent:** it blocks a real room's export. Found on `room.annex_bedroom` (Urban Mystery Club).

## The gap

In `grid` mode, `fit` samples the Source's pixel grid at `scale` from `offset_x`, `offset_y`, and its size is whatever falls
out of the Source: `(source - offset) // scale` per axis (`Grid.uniform`, [resample.py](../kiripix/ops/resample.py)). The
`brief` must be whole tiles (`brief.size_not_tiles`), and `fit` must equal the brief exactly (`fit.size_mismatch`,
`check_fit` in [common.py](../kiripix/recipes/common.py)). The two rules usually conflict, and the room can't be exported.

- `room.annex_bedroom`: Source 1376 x 768, scale 4, `offset_x` 48 → fit 332 x 192. The brief can be 320 or 336 wide, never
  332, so `kiripix export` refuses.

The ways out today are all bad:

- `fit mode=downscale` crops to the brief, but it averages, and looks muddy on a Source that is already pixel art. Grid mode is
  why the Owner uses it.
- A larger `offset_x` crops from the left only. That shifts every Mask, Marker and Layer coordinate, and someone must check
  by eye that no room content is lost.
- `fit.size_mismatch` suggests `fit mode=downscale` even when the grid is right and only the size is off.
- The columns the Masks don't cover show up as `reach.unreachable_island` and `masks.open_edge` noise.

## What to build

### Padding

- In grid mode, when the grid output is **smaller** than the brief on an axis, `fit` pads it on the **right and bottom** up to
  the brief's size. Padding needs no look at the image, and padding only right and bottom keeps every existing coordinate
  (Masks, Markers, Layer clicks and boxes, y-sort lines) where it was.
- **The padding is transparent** (alpha 0, RGB 0). Decided here: the spec gives a room no matte colour, and a transparent pixel
  is already outside both palette checks. `conformance` counts only opaque pixels for `palette.off_palette`, and
  `mapping_error` reads only pixels opaque in both images. An opaque black strip would be mapped to the palette's darkest
  colour, count in `palette.mapping_error`, and draw a band in Godot. Add a test that both checks stay silent on a padded room
  anyway, so a later change to either can't break it.
- **Other checks on the padded strip.** `layers.plate_hole` must not count the padding as a hole in the Plate. `palette` must
  keep it transparent (no orphan clean-up or dithering reaches into it). The Plate + Layers recompose check still holds,
  since both sides carry the same strip.
- **Navigation.** The padded cells count as `solid` and outside navigation: `masks` ORs the strip into `solid.png` after the
  replay, derived from `grid.json`, not a Decision (so it isn't in the journal and can't be erased). `reach` gets no
  `reach.unreachable_island` from it, and since the strip is a wall on the padded side, `masks.open_edge` doesn't report that
  side. Export's collision covers it like any other `solid`.
- **`grid.json`** records `pad_right` and `pad_bottom` (target pixels, 0 when none). `width` and `height` stay the output size,
  so they equal the brief; the cells with Source pixels are `width - pad_right` by `height - pad_bottom`. Old `grid.json`
  files without the keys read as 0. `Grid` gains the two fields and keeps them through `to_json`/`from_json`.
- **Target-to-Source mapping** treats a padded cell as having no Source pixels: `target_centre` refuses it (a `ValueError` the
  Stage turns into a `StageFailure` naming the click), `mask_to_source` drops it, and `mask_to_target` leaves it off. So a
  Layer click or box in the strip, or a Runner call over it, fails clearly instead of reading past the Source's edge. A box
  that only overlaps the strip is clipped to the Source cells.
- An **info** finding, `fit.padded`, like `fit.cropped`: it says how many target pixels were padded on which side. No `fix`
  is needed for the room to work, so its `owner_action` says to widen the Source or move the offset if the strip shouldn't be
  there. (Use `owner_action` since every finding needs exactly one of the two.)

### Grid output larger than the brief

- Stays an error (cropping needs judgement). `fit.size_mismatch` in grid mode now names, as its `fix`, the brief rounded **up**
  to whole tiles from the grid output: `kiripix set <asset> brief width=336 height=192` (reuse `_whole_tiles` from
  `room.py`). With that brief, the room pads. The message also names the `offset_x`/`offset_y` that cut exactly to the current brief
  from the left and top (grid mode crops only there, so a centred crop isn't possible), for an Owner who'd rather crop.
- The existing `fit scale=<ratio>` fix stays first when the Source is an exact multiple of the brief and `scale` differs from
  that ratio. `fit mode=downscale` is suggested only when the grid itself is wrong: grid detection (`scale=0`) found no grid.
  A grid output smaller than the brief can no longer cause `fit.size_mismatch` in grid mode.

### Downscale mode

- Unchanged. `Grid.cover` always fills the brief exactly and crops the rest, so it never needs padding. A Source smaller than
  the brief still fails. Padding an averaged Source isn't asked for.

### Props

Props share `run_fit`. A prop's padding is transparent too, which a prop already handles as matte, so props get the same
behaviour. Check that `alpha_by_vote` leaves the strip at alpha 0.

### Docs

- Update the `fit` row in spec §6.1, and §6.2's "as for rooms", for the padding, its transparent fill and `fit.padded`. Update
  the `describe` text for `fit`, and the `CheckSpec` list (`fit.padded`).
- `grid.json` gains keys, but it is a Stage's rebuilt output, so an old one is rebuilt, not migrated.

## Notes

- **Painted Mask imports.** A painted Mask imported at the old fit size (332 wide) no longer matches a 336-wide room. Check
  what `masks` does with a stored import of the wrong size today. Either refuse it with a finding that names the re-import, or
  pad it with "off" on the right and bottom the same way. Say which in the PR notes.
- Bedroom Masks and Markers drawn on the 332-wide fit keep their coordinates; this is the point of padding right and bottom.
- Raising the brief changes the room's size, which changes the inputs of every Stage after `fit`. Mask clicks and floods
  may go to `needs-review`. That is expected; nothing in them should move.

## Acceptance criteria

- [x] CLI test, a fixture like the bedroom: a 1376 x 768 Source, grid scale 4, `offset_x` 48, brief 336 x 192 → a 336 x 192
      `fit.png` whose right 4 columns are transparent, `grid.json` with `pad_right` 4 and `pad_bottom` 0, and a `fit.padded`
      info.
- [x] On that fixture, Masks and Markers made before the brief changed keep their coordinates. `solid.png` covers the strip.
      There's no `reach.unreachable_island` and no `masks.open_edge` for the strip, no `layers.plate_hole`, no
      `palette.off_palette` and no `palette.mapping_error` from it, and `kiripix export` succeeds.
- [x] A `layers` click in the padded strip goes to `needs-input` with a message that names the strip and an `owner_action` that
      names the undo (a `StageFailure` naming the click is the fallback if the check is bypassed). With a fake segmenter, a click next to the strip
      reaches the same Source point as before.
- [x] Grid output larger than the brief: `fit.size_mismatch` whose `fix` is the brief rounded up to whole tiles, and whose
      message names the offsets that cut to the brief from the left and top. Running the `fix` gives a padded room with no error.
- [x] Downscale mode: the existing `fit` tests pass unchanged.
- [x] Spec §6.1's `fit` row describes the padding. `mypy` and `lint-imports` pass.

Budget: 60–100k tokens.
