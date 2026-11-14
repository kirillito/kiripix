---
status: done
milestone: M4
agent: imaging-engineer
type: ticket
parent: 0127-m4-room-looks.md
---

# M4: the `looks` Stage

Spec §6.1 (the `looks` row and Looks); ADR 0009. After [0128](0128-m4-room-look-edit-trial.md)'s numbers, and with
[0129](0129-m4-look-variants.md)'s Variants.

## What to build

- **Decisions,** each naming its Look: `look` (ID, and an optional Condition, a label the game doesn't evaluate); region `polygon`, `brush` and `difference` (box,
  tolerance, specks removed; on the image); `solid` by polygon or brush. The `masks` Stage's `snap_cell` applies to
  `solid`.
- **The build,** per Look: resize to the Source, register (`register`), fit through the room's Grid transform, regrade
  (`regrade`: `none` or `outside`), map the whole image with the `palette` Stage's parameters and Ops, then cut the region.
  Write the Look's image cropped to the region's box, one piece per foreground Layer the region meets (the pixels in
  that Layer's alpha), and its `solid`. If [0094](../m3/0094-m3-palette-stage-muddies-rooms.md) changes the mapping, Looks
  follow it, because they call the same code.
- **Replay:** a refit or a Layer change sends `difference` regions and registration to `needs-review`; a palette change
  rebuilds them to `done`. No Looks, `done`.
- **Checks:** `look.off_palette`, `look.misaligned` (error), `look.drift` (warning, count and boxes), `look.unchanged`
  (warning). Each finding has a `fix` or an `owner_action`.
- **Ops** for registration (scale and shift, estimated outside a Mask), regrade and the difference region, in `ops/`,
  pure, with golden tests.
- Calls no Runner.

## Defaults from trial 0128

Measured on three of the Owner's edits of `room.ch01_dungeon_r03` ([0128](0128-m4-room-look-edit-trial.md), Result).
ΔE is OKLab distance x 100.

- **`register`: on by default.** The Owner's model, Nano Banana 2, returned every edit at the Source's size with no scale or shift
  (0.02 Source px at most), but 0063 measured a 1 % rescale, and an estimate costs little. Limits: scale 0.985 to 1.015
  on each axis, shift 4 target px at most. Estimate from textured tiles outside the region (0128 had over 300 tiles of 96
  Source px), robustly. `look.misaligned`'s half a target pixel holds: the per-tile residual was 0.03 target px median,
  0.07 p90.
- **Measure drift and the `difference` region on the fitted image before palette, not on the mapped one.** The model
  re-renders every pixel by about 1 ΔE (median; p90 2.6), and the Project's palette steps are 2.9 ΔE apart (median), so
  34 to 40 % of the target pixels outside the region map to a neighbouring colour although nothing there was redrawn. A
  count of changed mapped pixels would warn on every edit.
- **`look.drift` tolerance: 8 ΔE** on the 3x3 mean of the fitted difference, in components of 16 target px or more. That
  gave 5 to 8 boxes of real redraw on the gate and broken edits (lamp tubes, the booth's glass, posters: 179 to 231 px),
  and the light pool on the lamp edit, which tells the Owner to grow the region over it. Report the largest boxes first.
- **`difference` default tolerance: 4 ΔE** on the same 3x3 mean, specks under 16 px removed. It picks out the whole shut
  gate and the whole broken turnstile as one blob each. A lamp's glass comes with its light pool, as the pool changes as
  much; the box limits it.
- **`regrade` defaults to `none`.** Neither the gate nor the broken edit shifted the room's light (mean ΔL -0.15 and
  -0.03), so `outside` had nothing to fix. On the lamp edit it undid about 5 % of the darkening.
- **For the Owner to decide:** inside a region, 33 to 48 % of the pixels the edit didn't change still map to a
  neighbouring palette colour, so they flicker by one step when the Look toggles. One way to avoid it: inside the region,
  keep the mapped room's pixel wherever the fitted edit is within the `difference` tolerance of the fitted room. That
  changes the Stage's build, so it isn't part of this ticket until the Owner says so.

## Acceptance criteria

- [x] Golden: registration recovers a known 1 % scale and a 3 px shift; a difference region picks out a changed patch
      and not the noise around it.
- [x] CLI seam, with the `demo` Kind or a small room: a Look over a lifted Layer gives a Plate-depth image and a piece for
      that Layer whose pixels together equal the mapped edit inside the region.
- [x] An edit with drift outside the region gives `look.drift` with its box; one shifted beyond the limits fails with
      `look.misaligned`.
- [x] A palette change rebuilds the Looks to `done`; a refit with a `difference` region gives `needs-review`.
- [x] Contract samples for the new Decisions.

## Result

- **The Stage** (`kiripix/recipes/looks.py`). Per picked Look: resize the edit to the Source (nearest, no blending), `register`
  it, fit it through the room's Grid transform (`downscale` or `sample_nearest`, as `fit` did), `regrade` if asked, replay the
  region, map the whole fitted edit with the `palette` Stage's own parameters (`StageRun.upstream_params`, new, filled by core), and cut
  it. Output: `looks.json`, and per Look `<look>/plate.png` (the region outside every Layer's alpha), `<look>/layer.<id>.png` (the region in that
  Layer's alpha) and `<look>/solid.png`, all cropped to the region's box (`box` in `looks.json`), except `solid.png` (room size, 1-bit).
  Together the pieces are the mapped edit inside the region.
- **Decisions:** `look` {look, condition?}; `polygon` {look, points, erase?}; `brush` {look, radius, points, erase?}; `difference`
  {look, x0..y1, tolerance? (4), specks? (16)}, `on_image`; `solid` {look, points, radius?, erase?} (a polygon, or a brush stroke with a
  `radius`). Region Decisions replay in order. **The build doesn't need a `look` Decision:** a Look exists once an edit is picked, and `look`
  only adds the Condition. A Decision that names a Look with no Pick gives needs-input (a `pick` fix when one edit is stored). A Look with a Pick and
  no region builds nothing and gets `look.no_region`.
- **Parameters** (the `looks` Stage's): `register` (true), `regrade` (`none`), `drift_tolerance` (8). Limits and tolerances as in the
  trial: scale 0.985 to 1.015, shift 4 target px, a median miss over 0.5 target px after registering is `look.misaligned` too.
  An edit outside the limits isn't moved.
- **Replay.** `layers` is first in the Stage's `upstream`, so the `difference` Decision's input image is the Plate: a refit or a Layer
  change gives needs-review, a palette change rebuilds to done. Registration is re-estimated at every build, so it has no review of its
  own: a refit that moves the Look only shows in `look.misaligned`.
- **The `solid`** starts as the room's `solid.png` (without the padded strip), replays the Look's `solid` Decisions, snaps to the `masks`
  Stage's `snap_cell`, and takes the strip again. A Look with no `solid` Decision has no `solid.png`: it uses the room's.
- **Checks:** `look.off_palette`, `look.misaligned` (error), `look.drift` (warning, count and boxes largest first, an `owner_action`),
  `look.unchanged` (warning), and one more, `look.no_region` (warning).
- **Ops** (`kiripix/ops/looks.py`): `register` (phase correlation on 96 px tiles for the first look, then Lucas-Kanade steps, which don't lock to
  whole pixels on a smooth picture; robust per-axis fit; 1 % and 3 px recovered to 0.1 px on a golden), `warp_nearest`, `resize_nearest`,
  `regrade`, `difference_map`, `difference_region`, `drift_boxes`, `dilate`, `mask_box`.
- **Left open.** The ticket's question for the Owner (keeping the room's pixel inside the region) is unbuilt, as it said. Registration
  needs 6 textured tiles outside the region: a small image or one mostly covered by the region is left as it is (no `look.misaligned`).
  `export` doesn't read `looks` yet (0131). `kiripix op` has no command for these Ops yet.

## Closing notes (2026-11-13)

- The Owner approved the golden images (`look_registered`, `look_difference`, `look_regrade`) on 2026-11-13.
